"""V3 ScenarioRuntime implementation."""

from __future__ import annotations

import os
from typing import Any

from ..brand_memory.profile_service import BrandProfileService
from ..creative_core.pipeline import run_creative_planning, run_generation_loop
from ..generation_router import GenerationRouter
from ..creative_core.rules import RULE_VERSION, stable_id
from ..llm_brain import BrainRunResult, V3LLMBrainAdapter
from ..scenario_packs import ScenarioPackRegistry, ScenarioPackResolution, ScenarioSelection
from ..shared_capabilities import (
    VISUAL_CAPABILITY_CLUSTER_ID,
    VISUAL_CLUSTER_CHILD_MODULE_IDS,
    CapabilityInput,
    CapabilityRunResult,
    CapabilityRunStatus,
    CapabilityWarning,
    SharedCapabilityRegistry,
    UploadedAssetInfo,
)
from ..shared_capabilities.activation import (
    CapabilityActivationError,
    CapabilityActivationIntent,
    CapabilityActivationPlan,
    CapabilityActivationPlanner,
    CapabilityContribution,
    CapabilityContributionComposer,
    CapabilityExecutionEnvelope,
    ComposedVisualContribution,
    NormalizedV3JobIntent,
    ResolvedConstraintEntry,
    ResolvedConstraintLedger,
    TemplateDeliverable,
    TemplateDeliverablePlan,
    TemplateCapabilityPolicy,
    VisualCapabilityManifest,
    VisualCapabilityRegistry,
    VisualTaskProfile,
    compatibility_policy,
)
from ..shared_capabilities.visual_cluster.plugins import VisualCapabilityPlugin, VisualClusterPluginRegistry
from ..schemas import PlanningResult, ProviderStrategy
from .contracts import (
    CapabilityPreparationResult,
    ScenarioRuntimeRequest,
    ScenarioRuntimeResult,
    ScenarioRuntimeStatus,
    SpecializedScenarioPlanningContext,
    SpecializedScenarioPlanningResult,
)
from .specialized_planning import (
    PhotographyScenarioPlanningAdapter,
    SpecializedScenarioPlanningAdapter,
    SpecializedScenarioPlanningError,
)


class ScenarioRuntime:
    """Resolve Scenario Packs and safely delegate active scenarios to the central brain."""

    def __init__(
        self,
        brand_profile_service: BrandProfileService | None = None,
        scenario_registry: ScenarioPackRegistry | None = None,
        shared_capability_registry: SharedCapabilityRegistry | None = None,
        llm_brain_adapter: V3LLMBrainAdapter | None = None,
        generation_router: GenerationRouter | None = None,
        specialized_planning_adapters: list[SpecializedScenarioPlanningAdapter] | None = None,
    ) -> None:
        self.brand_profile_service = brand_profile_service or BrandProfileService()
        self.scenario_registry = scenario_registry or ScenarioPackRegistry()
        self.shared_capability_registry = shared_capability_registry or SharedCapabilityRegistry.with_default_modules()
        self.visual_capability_registry = VisualCapabilityRegistry.with_default_manifests(self.shared_capability_registry)
        self.capability_activation_planner = CapabilityActivationPlanner(self.visual_capability_registry)
        self.capability_contribution_composer = CapabilityContributionComposer(self.visual_capability_registry)
        self.visual_cluster_plugin_registry = VisualClusterPluginRegistry()
        self.llm_brain_adapter = llm_brain_adapter or V3LLMBrainAdapter()
        self.generation_router = generation_router
        adapters = specialized_planning_adapters or [PhotographyScenarioPlanningAdapter()]
        self.specialized_planning_adapters = {adapter.scenario_id: adapter for adapter in adapters}

    def register_visual_capability(
        self,
        manifest: VisualCapabilityManifest,
        executor_ref: str,
        plugin: VisualCapabilityPlugin,
    ) -> None:
        """Hot-plug a manifest and contribution plugin without changing Brain source."""

        if manifest.capability_id != plugin.capability_id:
            raise ValueError("manifest and plugin capability IDs must match")
        self.visual_capability_registry.register_manifest(manifest, executor_ref)
        try:
            self.visual_cluster_plugin_registry.register(plugin)
        except Exception:
            self.visual_capability_registry.unregister_manifest(manifest.capability_id)
            raise

    def plan_job(self, request: ScenarioRuntimeRequest | dict[str, Any]) -> ScenarioRuntimeResult:
        runtime_request = self._coerce_request(request)
        resolution = self.scenario_registry.resolve(runtime_request.scenario_selection)
        if not resolution.can_create_jobs:
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.BLOCKED,
                scenario_resolution=resolution,
                warnings=list(resolution.warnings),
                metadata=self._runtime_metadata(runtime_request, "blocked"),
            )
        try:
            preparation = self._prepare_capability_execution(runtime_request, resolution, stage="plan")
        except CapabilityActivationError as exc:
            return self._activation_blocked_result(runtime_request, resolution, exc)
        capability_run = preparation.combined_capability_run
        if capability_run is not None and capability_run.status == CapabilityRunStatus.FAILED:
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.BLOCKED,
                scenario_resolution=resolution,
                capability_run=capability_run,
                warnings=[*resolution.warnings, *self._capability_warning_messages(capability_run)],
                metadata={
                    **self._runtime_metadata(runtime_request, "blocked"),
                    "shared_capabilities": self._capability_metadata(capability_run),
                },
            )

        brain_result = preparation.brain_result
        capability_metadata = self._capability_metadata(capability_run)
        planning_metadata = self._brain_runtime_metadata(runtime_request, resolution, brain_result=brain_result)
        planning_metadata["shared_capabilities"] = capability_metadata
        planning_metadata["visual_cluster"] = capability_metadata.get("visual_cluster", {})
        planning_metadata.update(self._activation_metadata(preparation))
        planning_result = run_creative_planning(
            user_input=runtime_request.user_input,
            optional_brand_id=runtime_request.optional_brand_id,
            optional_template_id=self._job_scope(runtime_request, resolution),
            brand_profile_service=self.brand_profile_service,
            runtime_metadata=planning_metadata,
            generation_router=self.generation_router,
        )
        planning_result = self._enrich_result(planning_result, runtime_request, resolution, capability_run)
        planning_result = self._enrich_activation_result(planning_result, preparation)
        return ScenarioRuntimeResult(
            status=ScenarioRuntimeStatus.PLANNED,
            scenario_resolution=resolution,
            capability_run=capability_run,
            planning_result=planning_result,
            warnings=[*resolution.warnings, *self._capability_warning_messages(capability_run)],
            metadata={
                **self._runtime_metadata(runtime_request, "planned"),
                "shared_capabilities": self._capability_metadata(capability_run),
                "llm_brain": brain_result.safe_metadata(),
                **self._activation_metadata(preparation),
                **self._specialized_metadata(preparation),
            },
        )

    def generate_job(
        self,
        request: ScenarioRuntimeRequest | dict[str, Any],
        mock_profile: str = "balanced",
        apply_memory_update: bool = False,
        provider_strategy: ProviderStrategy = ProviderStrategy.MOCK_GENERATION,
        quality_mode: str = "standard",
    ) -> ScenarioRuntimeResult:
        runtime_request = self._coerce_request(request)
        resolution = self.scenario_registry.resolve(runtime_request.scenario_selection)
        if not resolution.can_create_jobs:
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.BLOCKED,
                scenario_resolution=resolution,
                warnings=list(resolution.warnings),
                metadata=self._runtime_metadata(runtime_request, "blocked"),
            )
        try:
            preparation = self._prepare_capability_execution(
                runtime_request,
                resolution,
                stage="generate",
                quality_mode=quality_mode,
            )
        except CapabilityActivationError as exc:
            return self._activation_blocked_result(runtime_request, resolution, exc)
        capability_run = preparation.combined_capability_run
        if capability_run is not None and capability_run.status == CapabilityRunStatus.FAILED:
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.BLOCKED,
                scenario_resolution=resolution,
                capability_run=capability_run,
                warnings=[*resolution.warnings, *self._capability_warning_messages(capability_run)],
                metadata={
                    **self._runtime_metadata(runtime_request, "blocked"),
                    "shared_capabilities": self._capability_metadata(capability_run),
                },
            )

        brain_result = preparation.brain_result
        capability_metadata = self._capability_metadata(capability_run)
        generation_metadata = self._brain_runtime_metadata(
            runtime_request,
            resolution,
            quality_mode=quality_mode,
            brain_result=brain_result,
        )
        generation_metadata["shared_capabilities"] = capability_metadata
        generation_metadata["visual_cluster"] = capability_metadata.get("visual_cluster", {})
        generation_metadata.update(self._activation_metadata(preparation))
        generation_result = run_generation_loop(
            user_input=runtime_request.user_input,
            optional_brand_id=runtime_request.optional_brand_id,
            optional_template_id=self._job_scope(runtime_request, resolution),
            brand_profile_service=self.brand_profile_service,
            mock_profile=mock_profile,
            apply_memory_update=apply_memory_update,
            provider_strategy=provider_strategy,
            runtime_metadata=generation_metadata,
            generation_router=self.generation_router,
        )
        generation_result = self._enrich_result(generation_result, runtime_request, resolution, capability_run)
        generation_result = self._enrich_activation_result(generation_result, preparation)
        return ScenarioRuntimeResult(
            status=ScenarioRuntimeStatus.GENERATED,
            scenario_resolution=resolution,
            capability_run=capability_run,
            generation_result=generation_result,
            warnings=[*resolution.warnings, *self._capability_warning_messages(capability_run)],
            metadata={
                **self._runtime_metadata(runtime_request, "generated"),
                "shared_capabilities": self._capability_metadata(capability_run),
                "llm_brain": brain_result.safe_metadata(),
                **self._activation_metadata(preparation),
                **self._specialized_metadata(preparation),
            },
        )

    def _prepare_capability_execution(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        stage: str,
        quality_mode: str | None = None,
    ) -> CapabilityPreparationResult:
        mode = self._capability_activation_mode(request)
        specialized_plan = self._prepare_specialized_scenario_plan(request, resolution)
        normalized_intent = self._normalize_v3_job_intent(request, resolution)
        if resolution.manifest.scenario_id == "photography" and mode != "enforced":
            raise CapabilityActivationError("Photography production activation requires enforced capability execution")
        policy = self._resolve_template_capability_policy(request, resolution)
        if mode == "legacy":
            capability_run = self._run_shared_capabilities(request, resolution)
            brain_result = self._run_llm_brain(
                request,
                resolution,
                capability_run,
                stage=stage,
                quality_mode=quality_mode,
            )
            self._require_remote_creative_brain(request, policy, brain_result)
            deliverable_plan = self._build_template_deliverable_plan(
                normalized_intent,
                policy,
                brain_result,
                specialized_plan,
            )
            return CapabilityPreparationResult(
                brain_result=brain_result,
                combined_capability_run=capability_run,
                activation_mode=mode,
                normalized_job_intent=normalized_intent,
                template_deliverable_plan=deliverable_plan,
                specialized_scenario_plan=specialized_plan,
            )

        pre_activation_run = self._run_pre_activation_capabilities(request, resolution)
        template_id = self._template_id(request, resolution)
        catalog = self.visual_capability_registry.catalog_snapshot(template_id, resolution.manifest.scenario_id)

        if mode == "shadow":
            legacy_run = self._run_shared_capabilities(request, resolution)
            brain_result = self._run_llm_brain(
                request,
                resolution,
                legacy_run,
                stage=stage,
                quality_mode=quality_mode,
                template_capability_policy=policy,
            )
            self._require_remote_creative_brain(request, policy, brain_result)
            plan = self._reuse_or_build_activation_plan(
                request,
                resolution,
                brain_result,
                policy,
                catalog.catalog_version,
                mode,
            )
            deliverable_plan = self._build_template_deliverable_plan(
                normalized_intent,
                policy,
                brain_result,
                specialized_plan,
            )
            return CapabilityPreparationResult(
                pre_activation_run=pre_activation_run,
                brain_result=brain_result,
                activation_plan=plan,
                combined_capability_run=legacy_run,
                activation_mode=mode,
                normalized_job_intent=normalized_intent,
                template_deliverable_plan=deliverable_plan,
                specialized_scenario_plan=specialized_plan,
            )

        brain_result = self._run_llm_brain(
            request,
            resolution,
            pre_activation_run,
            stage=stage,
            quality_mode=quality_mode,
            capability_catalog=catalog.safe_metadata(),
            pre_activation_capabilities=self._capability_metadata(pre_activation_run),
            template_capability_policy=policy,
        )
        self._require_remote_creative_brain(request, policy, brain_result)
        plan = self._reuse_or_build_activation_plan(
            request,
            resolution,
            brain_result,
            policy,
            catalog.catalog_version,
            mode,
        )
        deliverable_plan = self._build_template_deliverable_plan(
            normalized_intent,
            policy,
            brain_result,
            specialized_plan,
        )
        active_run = self._run_active_capabilities(request, resolution, plan, pre_activation_run)
        combined = self._combine_capability_runs(request, resolution, pre_activation_run, active_run, plan)
        ledger = self._build_resolved_constraint_ledger(
            request,
            plan,
            combined,
            normalized_intent,
            deliverable_plan,
        )
        envelope = self._build_capability_execution_envelope(
            plan,
            combined,
            normalized_intent,
            deliverable_plan,
            ledger,
        )
        return CapabilityPreparationResult(
            pre_activation_run=pre_activation_run,
            brain_result=brain_result,
            activation_plan=plan,
            active_capability_run=active_run,
            combined_capability_run=combined,
            capability_execution_envelope=envelope,
            normalized_job_intent=normalized_intent,
            template_deliverable_plan=deliverable_plan,
            resolved_constraint_ledger=ledger,
            activation_mode=mode,
            specialized_scenario_plan=specialized_plan,
        )

    def _require_remote_creative_brain(
        self,
        request: ScenarioRuntimeRequest,
        policy: TemplateCapabilityPolicy,
        brain_result: BrainRunResult,
    ) -> None:
        """Fail closed for templates whose creative answer cannot be local.

        General and Photography keep their current policy values.  The check
        therefore adds no behavior to their planning/generation paths.
        """

        if not policy.requires_remote_creative_brain:
            return
        if not brain_result.llm_used or brain_result.fallback_used:
            raise CapabilityActivationError("remote_creative_brain_required_for_template")
        expected = self._requested_image_count_for_brain(request)
        image_plan = brain_result.image_set_plan
        directions = [str(item).strip() for item in image_plan.shot_plan if str(item).strip()]
        if image_plan.image_count != expected or len(directions) != expected:
            raise CapabilityActivationError("remote_creative_brain_output_count_mismatch")

    def _requested_image_count_for_brain(self, request: ScenarioRuntimeRequest) -> int:
        frozen_intent = request.metadata.get("normalized_v3_job_intent")
        if isinstance(frozen_intent, dict):
            normalized = NormalizedV3JobIntent.model_validate(frozen_intent)
            return normalized.effective_image_count
        parameters = request.scenario_selection.parameters if request.scenario_selection else {}
        raw = (
            request.metadata.get("requested_image_count")
            or (parameters.get("requested_image_count") if isinstance(parameters, dict) else None)
            or 2
        )
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 2

    def _normalize_v3_job_intent(
        self,
        request: ScenarioRuntimeRequest,
        resolution: ScenarioPackResolution,
    ) -> NormalizedV3JobIntent:
        """Freeze count, canvas, text policy, and provenance once at runtime entry.

        A declared platform or provider cap is a contract, never a reason to
        silently change a user's requested count.  The caller is blocked when
        it asks beyond a declared cap; an undeclared cap remains unassumed.
        """

        metadata = dict(request.metadata or {})
        parameters = dict(request.scenario_selection.parameters) if request.scenario_selection else {}
        raw_count = metadata.get("requested_image_count", parameters.get("requested_image_count", 2))
        try:
            requested_count = max(1, int(raw_count))
        except (TypeError, ValueError):
            raise CapabilityActivationError("requested_image_count_invalid") from None
        declared_limit, limit_source = self._declared_image_count_limit(metadata, parameters)
        if declared_limit is not None and requested_count > declared_limit:
            raise CapabilityActivationError("requested_image_count_not_supported_by_declared_contract")
        requested_size = str(
            metadata.get("requested_image_size")
            or parameters.get("requested_image_size")
            or ""
        ).strip() or None
        explicit_text = any(
            value not in (None, "", [], {})
            for value in (
                metadata.get("provider_native_text_requirements"),
                metadata.get("approved_literal_copy"),
                parameters.get("provider_native_text_requirements"),
                parameters.get("approved_literal_copy"),
            )
        )
        template_id = self._template_id(request, resolution)
        normalized = NormalizedV3JobIntent(
            intent_id=stable_id(
                "normalized_v3_job_intent",
                metadata.get("job_id"),
                template_id,
                resolution.manifest.scenario_id,
                request.user_input,
                requested_count,
                requested_size,
                declared_limit,
                explicit_text,
            ),
            template_id=template_id,
            scenario_id=resolution.manifest.scenario_id,
            protected_user_intent=request.user_input,
            requested_image_count=requested_count,
            effective_image_count=requested_count,
            declared_image_count_limit=declared_limit,
            count_limit_source=limit_source,
            requested_image_size=requested_size,
            effective_image_size=requested_size,
            text_policy="provider_native_explicit_text" if explicit_text else "provider_native_no_forced_text",
            provenance=[
                {
                    "source": "ScenarioRuntime._normalize_v3_job_intent",
                    "requested_image_count": requested_count,
                    "declared_image_count_limit": declared_limit,
                    "count_limit_source": limit_source,
                }
            ],
        )
        metadata.update(
            {
                "requested_image_count": normalized.effective_image_count,
                "normalized_v3_job_intent": normalized.model_dump(mode="json"),
                "normalized_v3_job_intent_id": normalized.intent_id,
            }
        )
        if normalized.effective_image_size:
            metadata["requested_image_size"] = normalized.effective_image_size
        request.metadata = metadata
        return normalized

    def _declared_image_count_limit(
        self,
        metadata: dict[str, Any],
        parameters: dict[str, Any],
    ) -> tuple[int | None, str]:
        sources = (
            ("provider_max_requested_images", metadata.get("provider_max_requested_images")),
            ("platform_max_requested_images", metadata.get("platform_max_requested_images")),
            ("max_requested_images", metadata.get("max_requested_images")),
            ("provider_max_requested_images", parameters.get("provider_max_requested_images")),
            ("platform_max_requested_images", parameters.get("platform_max_requested_images")),
            ("max_requested_images", parameters.get("max_requested_images")),
        )
        for source, value in sources:
            try:
                parsed = int(value)
            except (TypeError, ValueError):
                continue
            if parsed >= 1:
                return parsed, source
        return None, "undeclared"

    def _build_template_deliverable_plan(
        self,
        normalized_intent: NormalizedV3JobIntent,
        policy: TemplateCapabilityPolicy,
        brain_result: BrainRunResult,
        specialized_plan: SpecializedScenarioPlanningResult | None,
    ) -> TemplateDeliverablePlan:
        directions = [str(item).strip() for item in brain_result.image_set_plan.shot_plan if str(item).strip()]
        expected = normalized_intent.effective_image_count
        if brain_result.image_set_plan.image_count != expected or len(directions) != expected:
            raise CapabilityActivationError("template_deliverable_plan_output_count_mismatch")
        role_recipes = (
            specialized_plan.execution_plan.get("role_recipes", [])
            if specialized_plan is not None and isinstance(specialized_plan.execution_plan, dict)
            else []
        )
        creative_owner = str(policy.metadata.get("creative_direction_owner") or "central_brain")
        deliverables: list[TemplateDeliverable] = []
        for index, direction in enumerate(directions, 1):
            recipe = role_recipes[index - 1] if index <= len(role_recipes) and isinstance(role_recipes[index - 1], dict) else {}
            deliverables.append(
                TemplateDeliverable(
                    deliverable_id=stable_id("template_deliverable", normalized_intent.intent_id, index, direction),
                    output_index=index,
                    image_intent=direction,
                    source=creative_owner,
                    factual_acceptance=(
                        ["product_truth", "platform_factual_constraints"]
                        if normalized_intent.scenario_id == "ecommerce"
                        else []
                    ),
                    metadata=(
                        {"specialized_role_key": recipe.get("role_key")}
                        if recipe.get("role_key")
                        else {}
                    ),
                )
            )
        return TemplateDeliverablePlan(
            plan_id=stable_id(
                "template_deliverable_plan",
                normalized_intent.intent_id,
                policy.deliverable_role_owner,
                directions,
            ),
            template_id=normalized_intent.template_id,
            scenario_id=normalized_intent.scenario_id,
            owner=policy.deliverable_role_owner,
            creative_direction_owner=creative_owner,
            requested_image_count=normalized_intent.requested_image_count,
            effective_image_count=expected,
            deliverables=deliverables,
            provenance=[
                {
                    "source": "ScenarioRuntime._build_template_deliverable_plan",
                    "creative_direction_owner": creative_owner,
                    "static_recipe_present": False,
                }
            ],
        )

    def _prepare_specialized_scenario_plan(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
    ) -> SpecializedScenarioPlanningResult | None:
        """Freeze one planner contribution before Central Brain and activation.

        A persisted plan is verified and reused on every generation/retry.  A
        specialized pack cannot receive raw profile-selection controls or
        re-plan a job merely because a retry is occurring.
        """

        adapter = self.specialized_planning_adapters.get(resolution.manifest.scenario_id)
        if adapter is None:
            return None
        existing = self._specialized_scenario_plan_from_metadata(request, resolution)
        if existing is not None:
            metadata = dict(request.metadata or {})
            if existing.requested_image_count is not None:
                metadata["requested_image_count"] = existing.requested_image_count
            if existing.execution_plan:
                metadata["specialized_role_execution_plan"] = dict(existing.execution_plan)
            request.metadata = metadata
            return existing
        metadata = dict(request.metadata or {})
        project_context = metadata.get("project_context_snapshot")
        frozen = metadata.get("capability_activation_plan")
        frozen_plan = CapabilityActivationPlan.model_validate(frozen) if isinstance(frozen, dict) and frozen.get("plan_id") else None
        context = SpecializedScenarioPlanningContext(
            job_key=str(
                metadata.get("job_id")
                or stable_id(
                    "specialized_scenario_job",
                    request.user_input,
                    metadata.get("project_id"),
                    resolution.manifest.scenario_id,
                )
            ),
            user_input=request.user_input,
            scenario_resolution=resolution,
            selected_mode_id=resolution.selected_mode_id,
            uploaded_assets=self._uploaded_assets(request),
            project_context_snapshot=dict(project_context) if isinstance(project_context, dict) else {},
            photographer_profile_binding=(
                dict(metadata.get("photographer_profile_binding"))
                if isinstance(metadata.get("photographer_profile_binding"), dict)
                else None
            ),
            frozen_capability_activation_plan=frozen_plan,
            metadata={
                "scenario_parameters": dict(request.scenario_selection.parameters)
                if request.scenario_selection is not None
                else {},
                "template_id": self._template_id(request, resolution),
            },
        )
        try:
            specialized = adapter.plan(context)
        except SpecializedScenarioPlanningError as exc:
            raise CapabilityActivationError(str(exc)) from exc
        if specialized.scenario_id != resolution.manifest.scenario_id:
            raise CapabilityActivationError("specialized planning scenario does not match the resolved scenario")
        if specialized.template_id != self._template_id(request, resolution):
            raise CapabilityActivationError("specialized planning template does not match the resolved template")
        metadata["specialized_scenario_plan"] = specialized.model_dump(mode="json")
        if specialized.requested_image_count is not None:
            metadata["requested_image_count"] = specialized.requested_image_count
        if specialized.execution_plan:
            # Kept opaque to Central Brain.  The shared pipeline reads this
            # only when it assigns each generated asset its frozen role.
            metadata["specialized_role_execution_plan"] = dict(specialized.execution_plan)
        request.metadata = metadata
        return specialized

    def _specialized_scenario_plan_from_metadata(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
    ) -> SpecializedScenarioPlanningResult | None:
        raw = request.metadata.get("specialized_scenario_plan")
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise CapabilityActivationError("specialized scenario plan has an invalid persisted shape")
        specialized = SpecializedScenarioPlanningResult.model_validate(raw)
        if specialized.scenario_id != resolution.manifest.scenario_id:
            raise CapabilityActivationError("persisted specialized plan scenario does not match this job")
        if specialized.template_id != self._template_id(request, resolution):
            raise CapabilityActivationError("persisted specialized plan template does not match this job")
        return specialized

    def _run_pre_activation_capabilities(self, request: ScenarioRuntimeRequest, resolution) -> CapabilityRunResult | None:
        module_ids: list[str] = []
        if request.uploaded_assets or request.uploaded_asset_ids:
            module_ids.extend(["asset_role_analyzer", "asset_binding_planner"])
        if request.metadata.get("project_context_snapshot") or request.optional_brand_id:
            module_ids.append("history_reference")
        if not module_ids:
            return None
        return self.shared_capability_registry.run(
            self._capability_input(request, resolution, metadata={"capability_phase": "pre_activation"}),
            module_ids=self._dedupe_preserve_order(module_ids),
        )

    def _run_active_capabilities(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        plan: CapabilityActivationPlan,
        pre_activation_run: CapabilityRunResult | None,
    ) -> CapabilityRunResult | None:
        executor_ids: list[str] = []
        for capability_id in plan.dependency_order:
            executor_ref = self.visual_capability_registry.executor_ref(capability_id)
            if executor_ref:
                executor_ids.append(executor_ref)
            if capability_id == "product_identity" and request.product_profile:
                executor_ids.append("information_integrity_lock")
        parameters = request.scenario_selection.parameters if request.scenario_selection else {}
        if isinstance(parameters, dict) and parameters.get("use_case_library"):
            executor_ids.extend(["case_library_retriever", "visual_grammar_lock"])
        if any(item in plan.dependency_order for item in ("visual_grammar", "universal_visual_quality", "human_realism", "portrait_identity", "nonhuman_subject_identity", "product_identity", "scene_continuity", "typography_layout", "suite_direction")):
            executor_ids.append("prompt_constraint_compiler")
        already_run = {result.module_id for result in pre_activation_run.results} if pre_activation_run else set()
        executor_ids = [item for item in self._dedupe_preserve_order(executor_ids) if item not in already_run]
        if not executor_ids:
            return None
        required_executor_ids = {
            self.visual_capability_registry.executor_ref(item.capability_id)
            for item in plan.base_capabilities
        }
        run = self.shared_capability_registry.run(
            self._capability_input(
                request,
                resolution,
                prior_results=list(pre_activation_run.results) if pre_activation_run else [],
                metadata={
                    "capability_phase": "active",
                    "capability_activation_plan": plan.model_dump(mode="json"),
                    "capability_activation_plan_summary": plan.summary(),
                },
            ),
            module_ids=executor_ids,
            required_module_ids=[item for item in required_executor_ids if item],
        )
        return self._attach_composed_contribution(run, plan, request, resolution)

    def _attach_composed_contribution(
        self,
        run: CapabilityRunResult,
        plan: CapabilityActivationPlan,
        request: ScenarioRuntimeRequest,
        resolution,
    ) -> CapabilityRunResult:
        cluster_result = next((item for item in run.results if item.module_id == VISUAL_CAPABILITY_CLUSTER_ID), None)
        cluster = (
            dict(cluster_result.facts.get("visual_capability_cluster") or {})
            if cluster_result is not None
            else {}
        )
        contributions = self._capability_contributions(plan, cluster, request, resolution)
        composed = self.capability_contribution_composer.compose(plan, contributions)
        updated_results = []
        for result in run.results:
            if result.module_id != VISUAL_CAPABILITY_CLUSTER_ID:
                updated_results.append(result)
                continue
            cluster_payload = dict(result.facts.get("visual_capability_cluster") or {})
            cluster_payload.update(
                {
                    "capability_activation_plan_summary": plan.summary(),
                    "capability_contributions": [item.model_dump(mode="json") for item in contributions],
                    "composed_visual_contribution": composed.model_dump(mode="json"),
                }
            )
            updated_results.append(
                result.model_copy(
                    update={
                        "facts": {
                            **dict(result.facts),
                            "visual_capability_cluster": cluster_payload,
                            "capability_contributions": [item.model_dump(mode="json") for item in contributions],
                            "composed_visual_contribution": composed.model_dump(mode="json"),
                        },
                        "metadata": {
                            **dict(result.metadata),
                            "capability_activation_plan_id": plan.plan_id,
                            "active_capability_ids": list(plan.dependency_order),
                        },
                    }
                )
            )
        return run.model_copy(
            update={
                "results": updated_results,
                "metadata": {
                    **dict(run.metadata),
                    "activation_plan_id": plan.plan_id,
                    "active_capability_ids": list(plan.dependency_order),
                    "composed_visual_contribution": composed.model_dump(mode="json"),
                },
            }
        )

    def _build_capability_execution_envelope(
        self,
        plan: CapabilityActivationPlan,
        capability_run: CapabilityRunResult | None,
        normalized_intent: NormalizedV3JobIntent,
        template_deliverable_plan: TemplateDeliverablePlan,
        resolved_constraint_ledger: ResolvedConstraintLedger,
    ) -> CapabilityExecutionEnvelope:
        """Freeze the active executor output before provider/review/retry use it.

        The projection is intentionally derived once from accepted executor
        results.  Downstream code receives this envelope, never the mutable
        visual-cluster metadata that preceded activation.
        """

        raw_cluster: dict[str, Any] = {}
        if capability_run is not None:
            for result in capability_run.results:
                if result.module_id == VISUAL_CAPABILITY_CLUSTER_ID:
                    raw_cluster = dict(result.facts.get("visual_capability_cluster") or {})
                    break
        raw_composed = raw_cluster.get("composed_visual_contribution")
        if not isinstance(raw_composed, dict) and capability_run is not None:
            candidate = capability_run.metadata.get("composed_visual_contribution")
            raw_composed = candidate if isinstance(candidate, dict) else None
        if not isinstance(raw_composed, dict):
            raise CapabilityActivationError("accepted active execution did not produce a composed contribution")
        composed = ComposedVisualContribution.model_validate(raw_composed)
        projection = {
            "visual_cluster": raw_cluster,
            "composed_visual_contribution": composed.model_dump(mode="json"),
        }
        execution_fingerprint = stable_id(
            "capability_execution",
            plan.fingerprint,
            plan.activation_mode,
            composed.model_dump(mode="json"),
            raw_cluster,
        )
        return CapabilityExecutionEnvelope(
            envelope_id=stable_id("capability_execution_envelope", plan.plan_id, execution_fingerprint),
            execution_fingerprint=execution_fingerprint,
            job_id=plan.job_id,
            template_id=plan.template_id,
            scenario_id=plan.scenario_id,
            activation_mode=plan.activation_mode,
            activation_plan=plan,
            normalized_job_intent=normalized_intent,
            template_deliverable_plan=template_deliverable_plan,
            resolved_constraint_ledger=resolved_constraint_ledger,
            active_capability_ids=list(plan.dependency_order),
            composed_visual_contribution=composed,
            provider_projection=projection,
            review_contracts=list(composed.review_contracts),
            retry_contracts=list(composed.retry_contracts),
            provenance=[
                *list(composed.provenance),
                {
                    "source": "ScenarioRuntime._build_capability_execution_envelope",
                    "execution_fingerprint": execution_fingerprint,
                    "facts_source": "accepted_active_executor_results",
                },
            ],
        )

    def _build_resolved_constraint_ledger(
        self,
        request: ScenarioRuntimeRequest,
        plan: CapabilityActivationPlan,
        capability_run: CapabilityRunResult | None,
        normalized_intent: NormalizedV3JobIntent,
        template_deliverable_plan: TemplateDeliverablePlan,
    ) -> ResolvedConstraintLedger:
        """Resolve runtime constraints once instead of appending prompt strings.

        The ledger keeps ownership and precedence explicit.  The existing
        contribution composer remains a producer of evidence, but it is no
        longer the downstream policy resolver.
        """

        raw_cluster: dict[str, Any] = {}
        if capability_run is not None:
            for result in capability_run.results:
                if result.module_id == VISUAL_CAPABILITY_CLUSTER_ID:
                    raw_cluster = dict(result.facts.get("visual_capability_cluster") or {})
                    break
        raw_composed = raw_cluster.get("composed_visual_contribution")
        if not isinstance(raw_composed, dict) and capability_run is not None:
            candidate = capability_run.metadata.get("composed_visual_contribution")
            raw_composed = candidate if isinstance(candidate, dict) else None
        if not isinstance(raw_composed, dict):
            raise CapabilityActivationError("accepted active execution did not produce a resolved constraint contribution")
        composed = ComposedVisualContribution.model_validate(raw_composed)
        entries: list[ResolvedConstraintEntry] = [
            ResolvedConstraintEntry(
                constraint_id=stable_id("constraint", normalized_intent.intent_id, "user_intent"),
                channel="user_intent",
                owner="user",
                strength="hard",
                precedence=100,
                requested_value=normalized_intent.protected_user_intent,
                resolved_value=normalized_intent.protected_user_intent,
                resolution="accepted",
                provenance=[{"source": "NormalizedV3JobIntent"}],
            ),
            ResolvedConstraintEntry(
                constraint_id=stable_id("constraint", normalized_intent.intent_id, "canvas"),
                channel="canvas",
                owner="user",
                strength="hard",
                precedence=95,
                requested_value=normalized_intent.requested_image_size,
                resolved_value=normalized_intent.effective_image_size,
                resolution="accepted",
                provenance=[{"source": "NormalizedV3JobIntent", "count": normalized_intent.effective_image_count}],
            ),
            ResolvedConstraintEntry(
                constraint_id=stable_id("constraint", normalized_intent.intent_id, "text_policy"),
                channel="text_policy",
                owner="user",
                strength="hard",
                precedence=94,
                requested_value=normalized_intent.text_policy,
                resolved_value=normalized_intent.text_policy,
                resolution="accepted",
                provenance=[{"source": "NormalizedV3JobIntent"}],
            ),
        ]
        for deliverable in template_deliverable_plan.deliverables:
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=stable_id("constraint", template_deliverable_plan.plan_id, deliverable.deliverable_id),
                    channel="deliverable_role",
                    owner=template_deliverable_plan.owner,
                    strength="hard",
                    precedence=90,
                    requested_value=deliverable.image_intent,
                    resolved_value=deliverable.image_intent,
                    resolution="accepted",
                    provenance=[{"source": deliverable.source, "output_index": deliverable.output_index}],
                )
            )
        for key, value in sorted(dict(request.product_profile or {}).items()):
            if value in (None, "", [], {}):
                continue
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=stable_id("constraint", normalized_intent.intent_id, "product_truth", key),
                    channel="product_truth",
                    owner="product_identity",
                    strength="hard",
                    precedence=92,
                    requested_value=value,
                    resolved_value=value,
                    resolution="accepted",
                    provenance=[{"source": "product_profile", "field": key}],
                )
            )
        for capability_id, fragment in enumerate(composed.prompt_additions, 1):
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=stable_id("constraint", plan.plan_id, "quality", capability_id, fragment),
                    channel="quality_guidance",
                    owner="active_capability",
                    strength="soft",
                    precedence=50,
                    requested_value=fragment,
                    resolved_value=fragment,
                    resolution="accepted",
                    provenance=[{"source": "ComposedVisualContribution", "activation_plan_id": plan.plan_id}],
                )
            )
        hard_capabilities = {
            "product_identity",
            "portrait_identity",
            "nonhuman_subject_identity",
            "human_realism",
        }
        hard_semantic_contract = bool(
            set(plan.dependency_order) & hard_capabilities
            or normalized_intent.scenario_id == "ecommerce"
            or normalized_intent.text_policy == "provider_native_explicit_text"
            or normalized_intent.effective_image_count > 1
        )
        provider_projection = {
            "protected_user_intent": normalized_intent.protected_user_intent,
            "effective_image_count": normalized_intent.effective_image_count,
            "requested_image_size": normalized_intent.effective_image_size,
            "text_policy": normalized_intent.text_policy,
            "template_deliverable_plan": template_deliverable_plan.model_dump(mode="json"),
            "visual_cluster": raw_cluster,
            "generic_human_realism": raw_cluster.get("human_photorealism_guidance")
            if isinstance(raw_cluster.get("human_photorealism_guidance"), dict)
            else {},
            "composed_visual_contribution": composed.model_dump(mode="json"),
        }
        applied_ids = [entry.constraint_id for entry in entries if entry.resolution == "accepted"]
        translated_ids = [entry.constraint_id for entry in entries if entry.resolution == "translated"]
        rejected_ids = [entry.constraint_id for entry in entries if entry.resolution == "rejected"]
        return ResolvedConstraintLedger(
            ledger_id=stable_id(
                "resolved_constraint_ledger",
                plan.plan_id,
                normalized_intent.intent_id,
                template_deliverable_plan.plan_id,
                [(entry.channel, entry.owner, entry.resolved_value) for entry in entries],
            ),
            intent_id=normalized_intent.intent_id,
            template_id=normalized_intent.template_id,
            scenario_id=normalized_intent.scenario_id,
            entries=entries,
            conflicts=[],
            provider_projection=provider_projection,
            audit_summary={
                "ledger_id": stable_id(
                    "resolved_constraint_ledger",
                    plan.plan_id,
                    normalized_intent.intent_id,
                    template_deliverable_plan.plan_id,
                    [(entry.channel, entry.owner, entry.resolved_value) for entry in entries],
                ),
                "intent_id": normalized_intent.intent_id,
                "effective_image_count": normalized_intent.effective_image_count,
                "effective_image_size": normalized_intent.effective_image_size,
                "text_policy": normalized_intent.text_policy,
                "deliverable_owner": template_deliverable_plan.owner,
                "applied_constraint_ids": applied_ids,
                "translated_constraint_ids": translated_ids,
                "rejected_constraint_ids": rejected_ids,
            },
            review_contracts=list(composed.review_contracts),
            retry_contracts=list(composed.retry_contracts),
            hard_semantic_contract=hard_semantic_contract,
            provenance=[
                {
                    "source": "ScenarioRuntime._build_resolved_constraint_ledger",
                    "active_capability_ids": list(plan.dependency_order),
                    "string_append_is_not_resolution": True,
                }
            ],
        )

    def _capability_contributions(
        self,
        plan: CapabilityActivationPlan,
        cluster: dict[str, Any],
        request: ScenarioRuntimeRequest,
        resolution,
    ) -> list[CapabilityContribution]:
        contributions = self.visual_cluster_plugin_registry.contributions(plan, cluster)
        specialized = self._specialized_scenario_plan_from_metadata(request, resolution)
        if specialized is None:
            return contributions
        draft = specialized.capability_contribution_draft
        if not plan.is_active(draft.capability_id):
            raise CapabilityActivationError(
                f"specialized planning capability is not active in the frozen plan: {draft.capability_id}"
            )
        active = plan.active(draft.capability_id)
        if active is None or active.version != draft.capability_version:
            raise CapabilityActivationError("specialized planning contribution does not match the frozen capability version")
        contributions.append(draft.model_copy(update={"activation_plan_id": plan.plan_id}))
        return contributions

    def _build_activation_plan(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        brain_result: BrainRunResult,
        policy: TemplateCapabilityPolicy,
        catalog_version: str,
        mode: str,
    ) -> CapabilityActivationPlan:
        profile = brain_result.visual_task_profile
        intent = brain_result.capability_activation_intent
        if profile is None or intent is None:
            raise CapabilityActivationError("Brain did not produce a valid capability activation profile")
        plan = self.capability_activation_planner.plan(
            task_profile=profile,
            intent=intent,
            template_policy=policy,
            catalog_version=catalog_version,
            activation_mode=mode,
            fallback_used=brain_result.fallback_used,
        )
        explicit_required = self._required_capability_ids(request)
        missing_required = [item for item in explicit_required if not plan.is_active(item)]
        if missing_required:
            raise CapabilityActivationError(
                "required capability is unavailable or not safely activated: " + ", ".join(missing_required)
            )
        return plan

    def _reuse_or_build_activation_plan(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        brain_result: BrainRunResult,
        policy: TemplateCapabilityPolicy,
        catalog_version: str,
        mode: str,
    ) -> CapabilityActivationPlan:
        frozen = request.metadata.get("capability_activation_plan")
        if isinstance(frozen, dict) and frozen.get("plan_id"):
            if not request.trusted_capability_plan_reuse:
                raise CapabilityActivationError("untrusted_frozen_capability_activation_plan")
            plan = CapabilityActivationPlan.model_validate(frozen)
            provenance = request.metadata.get("capability_plan_provenance")
            if not self._trusted_frozen_plan_provenance_matches(plan, provenance):
                raise CapabilityActivationError("capability_activation_plan_provenance_mismatch")
            if plan.template_id != self._template_id(request, resolution):
                raise CapabilityActivationError("frozen capability plan template does not match this job")
            if plan.scenario_id != resolution.manifest.scenario_id:
                raise CapabilityActivationError("frozen capability plan scenario does not match this job")
            stored_profile = request.metadata.get("visual_task_profile")
            stored_intent = request.metadata.get("capability_activation_intent")
            if isinstance(stored_profile, dict):
                brain_result.visual_task_profile = VisualTaskProfile.model_validate(stored_profile)
            if isinstance(stored_intent, dict):
                brain_result.capability_activation_intent = CapabilityActivationIntent.model_validate(stored_intent)
            return plan
        return self._build_activation_plan(
            request,
            resolution,
            brain_result,
            policy,
            catalog_version,
            mode,
        )

    @staticmethod
    def _trusted_frozen_plan_provenance_matches(
        plan: CapabilityActivationPlan,
        provenance: Any,
    ) -> bool:
        """Verify the Product API's immutable plan hand-off before reuse.

        The Scenario Runtime deliberately does not query Product API storage.
        Its public-facing callers therefore cannot turn an arbitrary metadata
        plan into execution truth: Product API must first validate the parent
        record, then attach this exact server-issued binding.
        """

        if not isinstance(provenance, dict):
            return False
        return (
            provenance.get("authority") == "v3_product_api"
            and str(provenance.get("plan_id") or "") == plan.plan_id
            and str(provenance.get("plan_fingerprint") or "") == plan.fingerprint
            and bool(str(provenance.get("issued_for_job_id") or "").strip())
        )

    def _combine_capability_runs(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        pre_activation_run: CapabilityRunResult | None,
        active_run: CapabilityRunResult | None,
        plan: CapabilityActivationPlan,
    ) -> CapabilityRunResult | None:
        runs = [run for run in (pre_activation_run, active_run) if run is not None]
        if not runs:
            return None
        results = []
        warnings = []
        required_failures = []
        seen: set[str] = set()
        for run in runs:
            for result in run.results:
                if result.module_id not in seen:
                    seen.add(result.module_id)
                    results.append(result)
            warnings.extend(run.warnings)
            required_failures.extend(run.required_failures)
        # In enforced mode the frozen activation plan is the only selector.
        # Every result here was accepted by an executor chosen from that plan
        # (or by its pre-activation dependency).  Reapplying the old
        # scenario-derived selector silently discarded valid hot-plug results.
        if required_failures:
            status = CapabilityRunStatus.FAILED
        elif any(run.status != CapabilityRunStatus.COMPLETE for run in runs):
            status = CapabilityRunStatus.DEGRADED
        else:
            status = CapabilityRunStatus.COMPLETE
        return CapabilityRunResult(
            status=status,
            results=results,
            warnings=warnings,
            required_failures=sorted(set(required_failures)),
            metadata={
                "pre_activation_module_ids": [result.module_id for result in pre_activation_run.results] if pre_activation_run else [],
                "activation_plan_id": plan.plan_id,
                "activation_plan_version": plan.plan_version,
                "active_capability_ids": list(plan.dependency_order),
                "catalog_version": plan.catalog_version,
                "activation_mode": plan.activation_mode,
            },
        )

    def _capability_input(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        prior_results: list | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CapabilityInput:
        return CapabilityInput(
            job_id=stable_id("capability_job", request.user_input, request.optional_brand_id, resolution.manifest.scenario_id),
            scenario_id=resolution.manifest.scenario_id,
            user_input=request.user_input,
            campaign=dict(request.metadata.get("campaign", {})) if isinstance(request.metadata.get("campaign"), dict) else {},
            brand_context=self._brand_context(request.optional_brand_id),
            uploaded_assets=self._uploaded_assets(request),
            product_profile=dict(request.product_profile),
            prior_results=list(prior_results or []),
            metadata={
                **dict(request.metadata),
                "scenario_mode_id": resolution.selected_mode_id,
                "scenario_preset_id": resolution.selected_preset_id,
                **dict(metadata or {}),
            },
        )

    def _resolve_template_capability_policy(self, request: ScenarioRuntimeRequest, resolution) -> TemplateCapabilityPolicy:
        return compatibility_policy(self._template_id(request, resolution), resolution.manifest.scenario_id)

    def _template_id(self, request: ScenarioRuntimeRequest, resolution) -> str:
        metadata = dict(request.metadata or {})
        return str(
            metadata.get("template_id")
            or metadata.get("template_manifest_id")
            or (
                "ecommerce_template"
                if resolution.manifest.scenario_id == "ecommerce"
                else "photographer_template"
                if resolution.manifest.scenario_id == "photography"
                else "general_template"
            )
        )

    def _capability_activation_mode(self, request: ScenarioRuntimeRequest | None = None) -> str:
        # New jobs must use the frozen, selective runtime by default.  The
        # explicit legacy/shadow values remain available for a controlled
        # rollback, and an existing job keeps the mode recorded in its frozen
        # plan so that retries cannot silently change execution semantics.
        mode = os.getenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced").strip().lower()
        mode = mode if mode in {"legacy", "shadow", "enforced"} else "legacy"
        frozen = request.metadata.get("capability_activation_plan") if request is not None else None
        if isinstance(frozen, dict):
            frozen_mode = str(frozen.get("activation_mode") or "").lower()
            if frozen_mode in {"legacy", "shadow", "enforced"}:
                return frozen_mode
        return mode

    def _activation_metadata(self, preparation: CapabilityPreparationResult) -> dict[str, Any]:
        plan = preparation.activation_plan
        if plan is None:
            return {"capability_activation_mode": preparation.activation_mode}
        metadata = {
            "visual_task_profile": preparation.brain_result.visual_task_profile.model_dump(mode="json")
            if preparation.brain_result.visual_task_profile
            else None,
            "capability_activation_intent": preparation.brain_result.capability_activation_intent.model_dump(mode="json")
            if preparation.brain_result.capability_activation_intent
            else None,
            "capability_activation_plan": plan.model_dump(mode="json"),
            "capability_activation_plan_id": plan.plan_id,
            "capability_catalog_version": plan.catalog_version,
            "capability_activation_mode": preparation.activation_mode,
        }
        if preparation.normalized_job_intent is not None:
            metadata["normalized_v3_job_intent"] = preparation.normalized_job_intent.model_dump(mode="json")
            metadata["normalized_v3_job_intent_id"] = preparation.normalized_job_intent.intent_id
        if preparation.template_deliverable_plan is not None:
            metadata["template_deliverable_plan"] = preparation.template_deliverable_plan.model_dump(mode="json")
            metadata["template_deliverable_plan_id"] = preparation.template_deliverable_plan.plan_id
        if preparation.resolved_constraint_ledger is not None:
            metadata["resolved_constraint_ledger"] = preparation.resolved_constraint_ledger.model_dump(mode="json")
            metadata["resolved_constraint_ledger_id"] = preparation.resolved_constraint_ledger.ledger_id
        if preparation.capability_execution_envelope is not None:
            envelope = preparation.capability_execution_envelope.safe_metadata()
            metadata.update(
                {
                    "capability_execution_envelope": envelope,
                    "capability_execution_envelope_id": envelope["envelope_id"],
                }
            )
        return metadata

    def _specialized_metadata(self, preparation: CapabilityPreparationResult) -> dict[str, Any]:
        specialized = preparation.specialized_scenario_plan
        if specialized is None:
            return {}
        return {
            # The internal frozen contribution is persisted by Product API;
            # public result surfaces only receive this auditable summary.
            "specialized_scenario_plan": specialized.model_dump(mode="json"),
            "specialized_scenario_plan_summary": dict(specialized.safe_summary),
            "specialized_execution_summary": {
                "requested_image_count": specialized.execution_plan.get("requested_image_count"),
                "role_keys": [
                    str(item.get("role_key"))
                    for item in specialized.execution_plan.get("role_recipes", [])
                    if isinstance(item, dict) and item.get("role_key")
                ],
                "shared_execution_only": True,
            }
            if specialized.execution_plan
            else {},
        }

    def _activation_blocked_result(self, request: ScenarioRuntimeRequest, resolution, exc: Exception) -> ScenarioRuntimeResult:
        required_failures = self._required_capability_ids(request)
        capability_run = CapabilityRunResult(
            status=CapabilityRunStatus.FAILED,
            warnings=[
                CapabilityWarning(
                    code="capability_activation_failed",
                    message=str(exc)[:240],
                    severity="error",
                )
            ],
            required_failures=required_failures,
            metadata={"activation_mode": self._capability_activation_mode(request)},
        )
        return ScenarioRuntimeResult(
            status=ScenarioRuntimeStatus.BLOCKED,
            scenario_resolution=resolution,
            capability_run=capability_run,
            warnings=[*resolution.warnings, f"capability_activation_failed: {str(exc)[:240]}"],
            metadata={
                **self._runtime_metadata(request, "blocked"),
                "capability_activation_mode": self._capability_activation_mode(request),
                "capability_activation_error": type(exc).__name__,
            },
        )

    def _coerce_request(self, request: ScenarioRuntimeRequest | dict[str, Any]) -> ScenarioRuntimeRequest:
        if isinstance(request, ScenarioRuntimeRequest):
            return request
        return ScenarioRuntimeRequest.model_validate(request)

    def _job_scope(self, request: ScenarioRuntimeRequest, resolution: ScenarioPackResolution) -> str:
        metadata = dict(request.metadata or {})
        parts = [
            metadata.get("project_id"),
            metadata.get("template_id") or metadata.get("template_manifest_id") or resolution.manifest.scenario_id,
            metadata.get("project_job_sequence"),
        ]
        return "::".join(str(part) for part in parts if part not in {None, ""})

    def _enrich_result(
        self,
        result: PlanningResult,
        request: ScenarioRuntimeRequest,
        resolution,
        capability_run: CapabilityRunResult | None,
    ) -> PlanningResult:
        capability_metadata = self._capability_metadata(capability_run)
        result_capability_metadata = (
            result.metadata.get("shared_capabilities")
            if isinstance(result.metadata.get("shared_capabilities"), dict)
            else {}
        )
        result_visual_cluster = result.metadata.get("visual_cluster")
        if not isinstance(result_visual_cluster, dict) and isinstance(result_capability_metadata, dict):
            result_visual_cluster = result_capability_metadata.get("visual_cluster")
        if isinstance(result_capability_metadata, dict) and result_capability_metadata:
            capability_metadata = {**capability_metadata, **result_capability_metadata}
        if isinstance(result_visual_cluster, dict) and result_visual_cluster:
            capability_metadata["visual_cluster"] = result_visual_cluster
        creative_job = result.creative_job.model_copy(
            update={
                "uploaded_asset_ids": self._uploaded_asset_ids(request),
                "metadata": {
                    **result.creative_job.metadata,
                    "scenario_id": resolution.manifest.scenario_id,
                    "scenario_status": resolution.status.value,
                    "selected_mode_id": resolution.selected_mode_id,
                    "selected_preset_id": resolution.selected_preset_id,
                    "product_profile": dict(request.product_profile),
                    "scenario_runtime": "v3",
                    "shared_capabilities": capability_metadata,
                },
            }
        )
        return result.model_copy(
            update={
                "creative_job": creative_job,
                "metadata": {
                    **result.metadata,
                    "scenario_id": resolution.manifest.scenario_id,
                    "scenario_display_name": resolution.manifest.display_name,
                    "scenario_status": resolution.status.value,
                    "selected_mode_id": resolution.selected_mode_id,
                    "selected_preset_id": resolution.selected_preset_id,
                    "scenario_runtime": "v3",
                    "uploaded_asset_ids": self._uploaded_asset_ids(request),
                    "product_profile": dict(request.product_profile),
                    "shared_capabilities": capability_metadata,
                },
            }
        )

    def _enrich_activation_result(
        self,
        result: PlanningResult,
        preparation: CapabilityPreparationResult,
    ) -> PlanningResult:
        activation_metadata = self._activation_metadata(preparation)
        specialized_metadata = self._specialized_metadata(preparation)
        public_specialized_metadata = {
            "specialized_scenario_plan_summary": specialized_metadata["specialized_scenario_plan_summary"]
        } if "specialized_scenario_plan_summary" in specialized_metadata else {}
        creative_job = result.creative_job.model_copy(
            update={
                "metadata": {
                    **dict(result.creative_job.metadata),
                    **activation_metadata,
                    **public_specialized_metadata,
                }
            }
        )
        return result.model_copy(
            update={
                "creative_job": creative_job,
                "metadata": {
                    **dict(result.metadata),
                    **activation_metadata,
                    **public_specialized_metadata,
                },
            }
        )

    def _run_shared_capabilities(self, request: ScenarioRuntimeRequest, resolution) -> CapabilityRunResult | None:
        module_ids = self._selected_capability_ids(request, resolution)
        if not module_ids:
            return None
        required_ids = self._required_capability_ids(request)
        return self.shared_capability_registry.run(
            self._capability_input(request, resolution, metadata={"capability_phase": "legacy"}),
            module_ids=module_ids,
            required_module_ids=required_ids,
        )

    def _brain_runtime_metadata(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        quality_mode: str | None = None,
        brain_result: BrainRunResult | None = None,
    ) -> dict[str, Any]:
        selection = request.scenario_selection
        parameters = dict(selection.parameters) if selection is not None else {}
        parameters.setdefault("mode", resolution.selected_mode_id)
        parameters.setdefault("preset", resolution.selected_preset_id)
        metadata = {
            **dict(request.metadata),
            "scenario_id": resolution.manifest.scenario_id,
            "scenario_display_name": resolution.manifest.display_name,
            "scenario_status": resolution.status.value,
            "scenario_mode_id": resolution.selected_mode_id,
            "scenario_preset_id": resolution.selected_preset_id,
            "scenario_parameters": parameters,
            "platform_profile": selection.platform_profile if selection is not None else None,
            "uploaded_assets": [asset.model_dump(mode="json") for asset in self._uploaded_assets(request)],
            "uploaded_asset_ids": self._uploaded_asset_ids(request),
            "reference_assets": self._reference_assets_from_request_metadata(request),
            "product_profile": dict(request.product_profile),
        }
        if quality_mode is not None:
            metadata["quality_mode"] = quality_mode
        if brain_result is not None:
            metadata["llm_brain"] = brain_result.safe_metadata()
        return metadata

    def _run_llm_brain(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        capability_run: CapabilityRunResult | None,
        *,
        stage: str,
        quality_mode: str | None = None,
        capability_catalog: dict[str, Any] | None = None,
        pre_activation_capabilities: dict[str, Any] | None = None,
        template_capability_policy: TemplateCapabilityPolicy | None = None,
    ) -> BrainRunResult:
        base_metadata = self._brain_runtime_metadata(request, resolution, quality_mode=quality_mode)
        uploaded_assets = [asset.model_dump(mode="json") for asset in self._uploaded_assets(request)]
        brain_request = self.llm_brain_adapter.build_request(
            user_input=request.user_input,
            stage=stage,
            scenario_id=resolution.manifest.scenario_id,
            template_id=self._template_id(request, resolution),
            metadata=base_metadata,
            shared_capabilities=self._capability_metadata(capability_run),
            uploaded_assets=uploaded_assets,
            product_profile=dict(request.product_profile),
            capability_catalog=capability_catalog,
            pre_activation_capabilities=pre_activation_capabilities,
            template_capability_policy=template_capability_policy,
        )
        return self.llm_brain_adapter.run(brain_request)

    def _selected_capability_ids(self, request: ScenarioRuntimeRequest, resolution) -> list[str]:
        parameters = request.scenario_selection.parameters if request.scenario_selection else {}
        explicit = parameters.get("capabilities") if isinstance(parameters, dict) else None
        module_ids: list[str] = []
        if isinstance(explicit, list):
            module_ids.extend(str(item) for item in explicit if str(item).strip())
        if resolution.manifest.scenario_id == "general_creative":
            preset_id = resolution.selected_preset_id or ""
            mode_id = resolution.selected_mode_id or ""
            case_guided_presets = {
                "campaign_poster",
                "social_cover",
                "brand_key_visual",
                "product_style_hero",
            }
            if preset_id in case_guided_presets or mode_id in case_guided_presets:
                module_ids.extend(["case_library_retriever", "visual_grammar_lock", "prompt_constraint_compiler"])
            if request.optional_brand_id:
                module_ids.extend(["history_reference", "prompt_constraint_compiler"])
        if resolution.manifest.scenario_id == "ecommerce":
            module_ids.extend(
                [
                    "case_library_retriever",
                    "visual_grammar_lock",
                    "information_integrity_lock",
                    "prompt_constraint_compiler",
                    "output_review",
                ]
            )
            if request.uploaded_assets or request.uploaded_asset_ids:
                module_ids[0:0] = ["asset_role_analyzer", "asset_binding_planner"]
            if request.optional_brand_id:
                module_ids.append("history_reference")
        if request.uploaded_assets or request.uploaded_asset_ids:
            module_ids.extend(["asset_role_analyzer", "asset_binding_planner", "prompt_constraint_compiler"])
        if request.product_profile:
            module_ids.extend(["information_integrity_lock", "prompt_constraint_compiler"])
        use_case_library = isinstance(parameters, dict) and bool(parameters.get("use_case_library"))
        if use_case_library:
            module_ids.extend(["case_library_retriever", "visual_grammar_lock", "prompt_constraint_compiler"])
        if "visual_grammar_lock" in module_ids and "case_library_retriever" not in module_ids and not (request.uploaded_assets or request.uploaded_asset_ids):
            module_ids.insert(0, "case_library_retriever")
        if "asset_binding_planner" in module_ids and "asset_role_analyzer" not in module_ids:
            module_ids.insert(0, "asset_role_analyzer")
        if "prompt_constraint_compiler" not in module_ids and any(
            item in module_ids
            for item in ["asset_role_analyzer", "asset_binding_planner", "visual_grammar_lock", "information_integrity_lock", "history_reference"]
        ):
            module_ids.append("prompt_constraint_compiler")
        project_context = request.metadata.get("project_context_snapshot")
        if isinstance(project_context, dict) and project_context:
            if "history_reference" not in module_ids:
                module_ids.append("history_reference")
            if "visual_grammar_lock" not in module_ids and (
                project_context.get("selected_output_assets")
                or project_context.get("selected_reference_assets")
                or project_context.get("uploaded_reference_assets")
            ):
                module_ids.extend(["case_library_retriever", "visual_grammar_lock"])
            if "prompt_constraint_compiler" not in module_ids:
                module_ids.append("prompt_constraint_compiler")
        if any(item in VISUAL_CLUSTER_CHILD_MODULE_IDS for item in module_ids) or isinstance(project_context, dict):
            module_ids.append(VISUAL_CAPABILITY_CLUSTER_ID)
        return self._dedupe_preserve_order(module_ids)

    def _required_capability_ids(self, request: ScenarioRuntimeRequest) -> list[str]:
        parameters = request.scenario_selection.parameters if request.scenario_selection else {}
        required = parameters.get("required_capabilities") if isinstance(parameters, dict) else None
        explicit = required if isinstance(required, list) else []
        resolution = self.scenario_registry.resolve(request.scenario_selection)
        specialized = self._specialized_scenario_plan_from_metadata(request, resolution)
        planned = specialized.required_capability_ids if specialized is not None else []
        return self._dedupe_preserve_order([str(item) for item in [*explicit, *planned] if str(item).strip()])

    def _uploaded_assets(self, request: ScenarioRuntimeRequest) -> list[UploadedAssetInfo]:
        assets = list(request.uploaded_assets)
        existing = {asset.asset_id for asset in assets}
        for asset_id in request.uploaded_asset_ids:
            if asset_id not in existing:
                assets.append(UploadedAssetInfo(asset_id=asset_id))
        return assets

    def _uploaded_asset_ids(self, request: ScenarioRuntimeRequest) -> list[str]:
        return self._dedupe_preserve_order([asset.asset_id for asset in self._uploaded_assets(request)])

    def _reference_assets_from_request_metadata(self, request: ScenarioRuntimeRequest) -> list[dict[str, Any]]:
        metadata = dict(request.metadata or {})
        refs = metadata.get("reference_assets")
        if isinstance(refs, list):
            return [dict(item) for item in refs if isinstance(item, dict)]
        context = metadata.get("project_context_snapshot")
        if not isinstance(context, dict):
            return []
        gathered: list[dict[str, Any]] = []
        for key in (
            "strong_reference_bindings",
            "selected_visual_references",
            "selected_reference_assets",
            "uploaded_reference_assets",
        ):
            values = context.get(key)
            if not isinstance(values, list):
                continue
            gathered.extend(dict(item) for item in values if isinstance(item, dict))
        return self._dedupe_reference_assets(gathered)

    def _dedupe_reference_assets(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in references:
            key = str(
                item.get("file_path")
                or item.get("output_id")
                or item.get("asset_id")
                or item.get("asset_ref_id")
                or item.get("source_id")
                or item.get("reference_id")
                or ""
            ).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique

    def _brand_context(self, brand_id: str | None) -> dict[str, Any]:
        if not brand_id:
            return {}
        profile = self.brand_profile_service.load_profile(brand_id)
        if profile is None:
            return {}
        return profile.model_dump(mode="json")

    def _capability_warning_messages(self, capability_run: CapabilityRunResult | None) -> list[str]:
        if capability_run is None:
            return []
        return [f"{warning.code}: {warning.message}" for warning in capability_run.warnings]

    def _capability_metadata(self, capability_run: CapabilityRunResult | None) -> dict[str, Any]:
        if capability_run is None:
            return {"enabled": False, "module_ids": [], "warnings": []}
        return {
            "enabled": True,
            "status": capability_run.status.value,
            "module_ids": [result.module_id for result in capability_run.results],
            "result_statuses": {result.module_id: result.status.value for result in capability_run.results},
            "warnings": [warning.model_dump(mode="json") for warning in capability_run.warnings],
            "results": [result.model_dump(mode="json") for result in capability_run.results],
            "visual_cluster": self._visual_cluster_metadata(capability_run),
            "required_failures": list(capability_run.required_failures),
        }

    def _visual_cluster_metadata(self, capability_run: CapabilityRunResult | None) -> dict[str, Any]:
        if capability_run is None:
            return {}
        for result in capability_run.results:
            if result.module_id == VISUAL_CAPABILITY_CLUSTER_ID:
                return self._public_visual_cluster_metadata(dict(result.facts.get("visual_capability_cluster") or {}))
        return {}

    def _public_visual_cluster_metadata(self, cluster: dict[str, Any]) -> dict[str, Any]:
        policy = cluster.get("template_consistency_policy") if isinstance(cluster.get("template_consistency_policy"), dict) else {}
        policy_id = str(policy.get("policy_id") or "")
        if policy_id == "ecommerce_product_truth":
            return cluster
        public_cluster = dict(cluster)
        public_cluster.pop("commercial_output_selection", None)
        for report in public_cluster.get("quality_review_reports", []) or []:
            if not isinstance(report, dict):
                continue
            scores = report.get("scores")
            if isinstance(scores, dict) and "commercial_usability" in scores:
                scores["delivery_usability"] = scores.pop("commercial_usability")
        return self._sanitize_general_public_visual_value(public_cluster)

    def _sanitize_general_public_visual_value(self, value: Any) -> Any:
        if isinstance(value, dict):
            clean: dict[str, Any] = {}
            for key, item in value.items():
                key_text = str(key)
                lowered = key_text.lower()
                if key_text in {
                    "capability_version",
                    "activation_plan_id",
                    "capability_activation_plan_id",
                }:
                    clean[key_text] = item
                    continue
                if "commercial" in lowered or "ecommerce" in lowered:
                    continue
                if "product" in lowered:
                    if key_text == "product_lock":
                        continue
                    key_text = key_text.replace("product", "subject").replace("Product", "Subject")
                clean[key_text] = self._sanitize_general_public_visual_value(item)
            return clean
        if isinstance(value, list):
            return [self._sanitize_general_public_visual_value(item) for item in value]
        if isinstance(value, str):
            return (
                value.replace("commercial", "polished")
                .replace("Commercial", "Polished")
                .replace("ecommerce", "creative")
                .replace("Ecommerce", "Creative")
                .replace("product", "subject")
                .replace("Product", "Subject")
            )
        return value

    def _dedupe_preserve_order(self, items: list[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item and item not in seen:
                seen.add(item)
                result.append(item)
        return result

    def _runtime_metadata(self, request: ScenarioRuntimeRequest, runtime_status: str) -> dict[str, Any]:
        return {
            "source": "ScenarioRuntime",
            "rules_version": RULE_VERSION,
            "runtime_status": runtime_status,
            "has_uploaded_assets": bool(request.uploaded_asset_ids or request.uploaded_assets),
            "has_product_profile": bool(request.product_profile),
        }
