"""V3 ScenarioRuntime implementation."""

from __future__ import annotations

import hashlib
import os
from typing import Any, Callable

from ..brand_memory.profile_service import BrandProfileService
from ..creative_core.pipeline import run_creative_planning, run_generation_loop
from ..generation_router import GenerationRouter
from ..creative_core.rules import RULE_VERSION, stable_id
from ..llm_brain import BrainCanonicalProviderPrompt, BrainRunRequest, BrainRunResult, V3LLMBrainAdapter
from ..llm_brain.fallback import build_remote_required_result
from ..llm_brain.finalizer_lifecycle import safe_remote_brain_finalizer_lifecycle
from ..llm_brain.stage_trace import record_stage_event
from ..llm_brain.providers import (
    BrainDevelopmentalPresenceDecisionMissing,
    BrainExecutionBudgetExceeded,
    BrainHumanNaturalnessDecisionMissing,
    BrainPromptContractInvalid,
    BrainProfessionalAnchorViewDecisionMissing,
    BrainReferenceChannelOwnershipDecisionMissing,
    BrainSemanticPreflightMissing,
    BrainTransportTimeoutError,
)
from ..scenario_packs import ScenarioPackRegistry, ScenarioPackResolution, ScenarioSelection
from ..scenario_packs.ecommerce import (
    EcommerceCreativeContext,
    EcommerceCreativeRiskPreflight,
    ecommerce_human_realism_review_context_from_preflight_payload,
    professional_identity_view_kinds_from_selectors,
    validate_professional_ecommerce_pose_contract_payload,
)
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
from ..shared_capabilities.apparel_construction import extract_apparel_construction_facts
from ..shared_capabilities.activation import (
    ActivationEvidence,
    CapabilityActivationError,
    CapabilityActivationIntent,
    CapabilityActivationPlan,
    CapabilityActivationPlanner,
    CapabilityContribution,
    CapabilityContributionComposer,
    CapabilityExecutionEnvelope,
    ComposedVisualContribution,
    NormalizedV3JobIntent,
    ReferenceChannelOwnershipIntent,
    RenderingIntent,
    ResolvedConstraintEntry,
    ResolvedConstraintLedger,
    RequestedCapability,
    TemplateDeliverable,
    TemplateDeliverablePlan,
    TemplateCapabilityPolicy,
    VisualSubjectEntity,
    VisualCapabilityManifest,
    VisualCapabilityRegistry,
    VisualTaskProfile,
    compatibility_policy,
)
from ..shared_capabilities.visual_cluster.plugins import VisualCapabilityPlugin, VisualClusterPluginRegistry
from ..shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_REVIEW_DIMENSIONS,
    normalize_human_realism_issue_code,
)
from ..shared_capabilities.visual_cluster.expression_review import (
    expression_front_card_framing_materialization_directive,
    laugh_expression_intent_contract,
    laugh_expression_materialization_directive,
)
from ..shared_capabilities.visual_cluster.review_repair import shared_review_repair_prompt_delta
from ..visual_assets import (
    CanonicalProviderPromptReceipt,
    FrozenVisualAssetBindingSet,
    ProfessionalConsumerRequest,
    ProfessionalModeBinding,
    ProfessionalModeExecutionAdapter,
    ProfessionalModeExecutionRequest,
    ProfessionalModePreparationResult,
    ProfessionalModeRuntimeBridge,
    ReferenceChannelPlan,
    VisualAssetBindingSet,
)
from ..visual_assets.body_proportion_evidence_profile import (
    BODY_REFRESH_REFERENCE_AGE_SCOPE,
    BodyProportionAnalysisError,
    BodyMorphologyEvidenceProfile,
    BodyProportionEvidenceProfile,
    BodyRefreshAnalysisContext,
    BodyProportionSourceAnalysisAdapter,
    BodySourceAnalysisAssetEnvelope,
    BodySourceAnalysisProvider,
    require_current_body_refresh_analysis_context,
)
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

ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES = {
    "lifestyle_primary_product_view",
    "playful_environment_interaction_view",
    "walking_or_lookback_view",
    "back_or_structure_view",
    "product_detail_or_print_view",
}

_BRAIN_IMAGE_SIZE_ALIASES = {
    "1024x1024": "1024x1024",
    "1024×1024": "1024x1024",
    "1024 by 1024": "1024x1024",
    "1024x1536": "1024x1536",
    "1024×1536": "1024x1536",
    "1024 by 1536": "1024x1536",
    "1536x1024": "1536x1024",
    "1536×1024": "1536x1024",
    "1536 by 1024": "1536x1024",
    "1:1": "1024x1024",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
    "4:5": "1024x1536",
    "3:4": "1024x1536",
    "9:16": "1024x1536",
    "4:3": "1536x1024",
    "5:4": "1536x1024",
    "16:9": "1536x1024",
}
_BRAIN_ASPECT_RATIO_ALIASES = {
    "1:1": "1024x1024",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
    "4:5": "1024x1536",
    "3:4": "1024x1536",
    "9:16": "1024x1536",
    "4:3": "1536x1024",
    "5:4": "1536x1024",
    "16:9": "1536x1024",
    "2.35:1": "1536x1024",
    "2.39:1": "1536x1024",
    "2.40:1": "1536x1024",
}
ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE = "product_detail_or_print_view"


def _safe_remote_brain_transport_failure(value: Any) -> dict[str, Any]:
    """Whitelist remote Brain transport diagnostics for blocked status metadata."""

    if not isinstance(value, dict):
        return {}
    schema_version = value.get("schema_version")
    stage = value.get("stage")
    error_class = value.get("transport_error_class")
    timeout_phase = value.get("timeout_phase")
    timeout_seconds = value.get("timeout_seconds")
    elapsed_ms = value.get("elapsed_ms")
    if schema_version != "v3_brain_transport_failure_v1":
        return {}
    if not isinstance(stage, str) or not stage.strip():
        return {}
    if error_class != "timeout":
        return {}
    if timeout_phase not in {
        "connect_timeout",
        "ttfb_timeout",
        "read_timeout",
        "complete_response_timeout",
        "json_parse_timeout",
        "unknown_transport_timeout",
    }:
        return {}
    if not isinstance(timeout_seconds, (int, float)) or float(timeout_seconds) <= 0.0:
        return {}
    if not isinstance(elapsed_ms, int) or elapsed_ms < 0:
        return {}
    return {
        "schema_version": "v3_brain_transport_failure_v1",
        "stage": stage,
        "transport_error_class": "timeout",
        "timeout_phase": timeout_phase,
        "timeout_seconds": round(float(timeout_seconds), 3),
        "elapsed_ms": elapsed_ms,
        "response_started": bool(value.get("response_started")),
        "first_content_observed": bool(value.get("first_content_observed")),
        "complete_response_observed": bool(value.get("complete_response_observed")),
        "json_parse_started": bool(value.get("json_parse_started")),
        "json_parse_completed": bool(value.get("json_parse_completed")),
    }


def _safe_remote_brain_serialization_failure(value: Any) -> dict[str, Any]:
    """Whitelist remote Brain JSON/truncation diagnostics for blocked status metadata."""

    if not isinstance(value, dict):
        return {}
    schema_version = value.get("schema_version")
    stage = value.get("stage")
    transport_error_class = value.get("transport_error_class")
    error_family = value.get("error_family")
    json_failure_kind = value.get("json_failure_kind")
    attempts = value.get("attempts")
    if schema_version == "v3_brain_serialization_failure_v1":
        if transport_error_class != "invalid_json_response" or error_family != "json_decode":
            return {}
        if json_failure_kind not in {
            "empty_json",
            "malformed_json",
            "missing_complete_marker",
            "non_object_json",
            "unknown",
        }:
            return {}
    elif schema_version == "v3_brain_truncated_response_v1":
        if transport_error_class != "truncated_response" or error_family != "output_truncated":
            return {}
        if json_failure_kind != "output_truncated":
            return {}
    else:
        return {}
    if not isinstance(stage, str) or not stage.strip():
        return {}
    if not isinstance(attempts, int) or attempts not in {1, 2}:
        return {}
    return {
        "schema_version": schema_version,
        "stage": stage,
        "transport_error_class": transport_error_class,
        "error_family": error_family,
        "json_failure_kind": json_failure_kind,
        "attempts": attempts,
        "json_serialization_recovery_attempted": bool(
            value.get("json_serialization_recovery_attempted")
        ),
        "json_serialization_recovery_succeeded": bool(
            value.get("json_serialization_recovery_succeeded")
        ),
        "json_parse_started": bool(value.get("json_parse_started")),
        "json_parse_completed": bool(value.get("json_parse_completed")),
    }


def _safe_remote_brain_execution_budget(value: Any) -> dict[str, Any]:
    """Whitelist aggregate logical budget facts for blocked status metadata."""

    if not isinstance(value, dict):
        return {}
    total = value.get("logical_budget_seconds")
    remaining_ms = value.get("remaining_ms")
    state = value.get("state")
    if not isinstance(total, (int, float)) or isinstance(total, bool) or float(total) < 0.0:
        return {}
    if not isinstance(remaining_ms, int) or isinstance(remaining_ms, bool) or remaining_ms < 0:
        return {}
    if state not in {"within_budget", "exhausted"}:
        return {}
    return {
        "logical_budget_seconds": round(float(total), 3),
        "remaining_ms": remaining_ms,
        "state": state,
    }


_SAFE_REMOTE_BRAIN_STAGES = {
    "activation",
    "generate",
    "plan",
    "provider_prompt_developmental_presence_verify",
    "provider_prompt_finalize",
    "provider_prompt_human_naturalness_resign",
    "provider_prompt_professional_capture_resign",
    "remote_intent",
}


def _safe_remote_brain_stage(value: Any) -> str:
    stage = str(value or "").strip()
    if stage in _SAFE_REMOTE_BRAIN_STAGES:
        return stage
    return ""


def _safe_remote_provider_transport_kind(value: Any) -> str:
    token = str(value or "").strip().lower()
    if token in {
        "connection_error",
        "network_error",
        "protocol_error",
        "provider_api_error",
        "read_error",
        "timeout",
        "transport_error",
        "write_error",
    }:
        return token
    return ""


_SAFE_REMOTE_CONTRACT_REJECTED_SECTIONS = {
    "image_set_plan",
    "prompt_guidance",
    "prompt_review",
    "user_visible_summary",
    "visual_task_profile",
    "visual_task_profile.rendering_intent",
    "capability_activation_intent",
    "canonical_provider_prompts",
    "checkpoints",
}


def _safe_remote_contract_rejected_sections(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    sections: list[str] = []
    for item in value:
        token = str(item or "").strip()
        if token in _SAFE_REMOTE_CONTRACT_REJECTED_SECTIONS:
            sections.append(token)
    return list(dict.fromkeys(sections))[:8]


def _safe_remote_image_set_cardinality_audit(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    audit: dict[str, Any] = {}
    for key in ("expected_image_count", "remote_image_count", "remote_shot_plan_count"):
        raw = value.get(key)
        if raw is None:
            audit[key] = None
        elif isinstance(raw, int):
            audit[key] = raw
    if isinstance(value.get("cardinality_valid"), bool):
        audit["cardinality_valid"] = bool(value["cardinality_valid"])
    return audit


def _safe_remote_image_set_validation_audit(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    audit: dict[str, Any] = {}
    count = value.get("validation_error_count")
    if isinstance(count, int):
        audit["validation_error_count"] = count
    for key in ("validation_error_paths", "validation_error_types"):
        values = value.get(key)
        if isinstance(values, list):
            audit[key] = [str(item) for item in values if str(item).strip()][:8]
    return audit


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
        body_proportion_source_analyzer: BodySourceAnalysisProvider
        | Callable[[list[dict[str, Any]]], dict[str, Any]]
        | None = None,
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
        self.body_proportion_source_analyzer = body_proportion_source_analyzer
        self.body_proportion_source_analysis_adapter = BodyProportionSourceAnalysisAdapter()
        self.professional_mode_execution_adapter = ProfessionalModeExecutionAdapter()
        self.professional_mode_runtime_bridge = ProfessionalModeRuntimeBridge()
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
        record_stage_event("scenario_runtime", "plan_job_entered")
        runtime_request = self._coerce_request(request)
        requested_count = self._requested_image_count_for_brain(runtime_request)
        record_stage_event(
            "scenario_runtime",
            "request_coerced",
            extra={"requested_image_count": requested_count},
        )
        resolution = self.scenario_registry.resolve(runtime_request.scenario_selection)
        if not resolution.can_create_jobs:
            record_stage_event("scenario_runtime", "scenario_blocked", terminal_reason="cannot_create_jobs")
            return ScenarioRuntimeResult(
                status=ScenarioRuntimeStatus.BLOCKED,
                scenario_resolution=resolution,
                warnings=list(resolution.warnings),
                metadata=self._runtime_metadata(runtime_request, "blocked"),
            )
        try:
            record_stage_event(
                "scenario_runtime",
                "capability_preparation_call",
                stage="plan",
                extra={"requested_image_count": requested_count},
            )
            preparation = self._prepare_capability_execution(runtime_request, resolution, stage="plan")
        except CapabilityActivationError as exc:
            record_stage_event(
                "scenario_runtime",
                "capability_preparation_blocked",
                stage="plan",
                terminal_reason="capability_activation_error",
            )
            return self._activation_blocked_result(runtime_request, resolution, exc)
        record_stage_event("scenario_runtime", "capability_preparation_returned", stage="plan")
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
        planning_metadata.update(self._renderer_channel_metadata(runtime_request))
        planning_metadata.update(self._frozen_professional_provider_metadata(preparation))
        planning_result = run_creative_planning(
            user_input=runtime_request.user_input,
            optional_brand_id=runtime_request.optional_brand_id,
            optional_template_id=self._job_scope(runtime_request, resolution),
            brand_profile_service=self.brand_profile_service,
            runtime_metadata=planning_metadata,
            generation_router=self.generation_router,
        )
        planning_result = self._enrich_result(planning_result, runtime_request, resolution, capability_run)
        planning_result = self._enrich_activation_result(planning_result, preparation, runtime_request)
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
                **self._resolved_aspect_metadata(planning_result),
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
        generation_metadata.update(self._renderer_channel_metadata(runtime_request))
        explicit_aspect_ratio = str(
            runtime_request.metadata.get("requested_image_aspect_ratio") or ""
        ).strip()
        if explicit_aspect_ratio:
            generation_metadata.update(
                {
                    "requested_image_aspect_ratio": explicit_aspect_ratio,
                    "requested_image_aspect_ratio_source": str(
                        runtime_request.metadata.get("requested_image_aspect_ratio_source")
                        or "remote_brain_user_intent"
                    ),
                }
            )
        # ``run_generation_loop`` materializes the Provider request before
        # ``_enrich_activation_result`` returns the public result.  Therefore
        # the immutable Professional stage selectors must be present here,
        # not only projected onto the result after generation has finished.
        generation_metadata.update(self._frozen_professional_provider_metadata(preparation))
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
            body_refresh_analysis_context=runtime_request.body_refresh_analysis_context,
        )
        generation_result = self._enrich_result(generation_result, runtime_request, resolution, capability_run)
        generation_result = self._enrich_activation_result(generation_result, preparation, runtime_request)
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
                **self._resolved_aspect_metadata(generation_result),
            },
        )

    @staticmethod
    def _resolved_aspect_metadata(result: PlanningResult | None) -> dict[str, str]:
        if result is None:
            return {}
        metadata = result.metadata if isinstance(result.metadata, dict) else {}
        ratio = str(metadata.get("requested_image_aspect_ratio") or "").strip()
        if not ratio:
            return {}
        return {
            "requested_image_aspect_ratio": ratio,
            "requested_image_aspect_ratio_source": str(
                metadata.get("requested_image_aspect_ratio_source")
                or "remote_brain_user_intent"
            ),
        }

    def _prepare_capability_execution(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        stage: str,
        quality_mode: str | None = None,
    ) -> CapabilityPreparationResult:
        """Prepare one job under a single bounded remote-Brain execution scope.

        A semantic plan and canonical prompt sign-off are two decisions in one
        logical preparation.  Keeping their deadline in one ephemeral scope
        prevents a later stage from starting with a stale full transport
        timeout and makes terminal timing provenance truthful.
        """

        with self.llm_brain_adapter.execution_scope():
            return self._prepare_capability_execution_within_brain_budget(
                request,
                resolution,
                stage=stage,
                quality_mode=quality_mode,
            )

    def _prepare_capability_execution_within_brain_budget(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        stage: str,
        quality_mode: str | None = None,
    ) -> CapabilityPreparationResult:
        mode = self._capability_activation_mode(request)
        self._require_trusted_frozen_capability_plan_boundary(request, resolution)
        library_binding, request = self._prepare_library_visual_asset_binding(
            request,
            resolution,
            activation_mode=mode,
        )
        professional_request, professional_preparation, request = self._prepare_professional_mode(
            request,
            resolution,
            activation_mode=mode,
        )
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
            normalized_intent = self._apply_brain_image_size_precedence(
                request,
                normalized_intent,
                brain_result,
            )
            deliverable_plan = self._build_template_deliverable_plan(
                request,
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
                professional_mode_preparation=professional_preparation,
                visual_asset_library_binding=library_binding,
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
            normalized_intent = self._apply_brain_image_size_precedence(
                request,
                normalized_intent,
                brain_result,
            )
            plan = self._reuse_or_build_activation_plan(
                request,
                resolution,
                brain_result,
                policy,
                catalog.catalog_version,
                mode,
            )
            deliverable_plan = self._build_template_deliverable_plan(
                request,
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
                professional_mode_preparation=professional_preparation,
                visual_asset_library_binding=library_binding,
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
        record_stage_event(
            "scenario_runtime",
            "semantic_plan_returned",
            stage=stage,
            extra={
                "requested_image_count": self._requested_image_count_for_brain(request),
                "remote_contract_rejected_count": len(
                    brain_result.audit.get("remote_contract_rejected_sections") or []
                )
                if isinstance(brain_result.audit, dict)
                else 0,
            },
        )
        record_stage_event("scenario_runtime", "slot_delta_recovery_call", stage=stage)
        brain_result = self._recover_character_card_slot_delta_brain_result(
            request,
            brain_result,
        )
        record_stage_event("scenario_runtime", "slot_delta_recovery_returned", stage=stage)
        record_stage_event("scenario_runtime", "remote_brain_requirement_validation_call", stage=stage)
        self._require_remote_creative_brain(request, policy, brain_result)
        normalized_intent = self._apply_brain_image_size_precedence(
            request,
            normalized_intent,
            brain_result,
        )
        record_stage_event("scenario_runtime", "remote_brain_requirement_validation_returned", stage=stage)
        record_stage_event("scenario_runtime", "professional_task_profile_bind_call", stage=stage)
        brain_result = self._bind_professional_task_profile(
            brain_result,
            professional_request,
        )
        record_stage_event("scenario_runtime", "professional_task_profile_bind_returned", stage=stage)
        record_stage_event("scenario_runtime", "activation_plan_build_call", stage=stage)
        plan = self._reuse_or_build_activation_plan(
            request,
            resolution,
            brain_result,
            policy,
            catalog.catalog_version,
            mode,
        )
        record_stage_event("scenario_runtime", "activation_plan_build_returned", stage=stage)
        record_stage_event("scenario_runtime", "template_deliverable_plan_build_call", stage=stage)
        deliverable_plan = self._build_template_deliverable_plan(
            request,
            normalized_intent,
            policy,
            brain_result,
            specialized_plan,
        )
        record_stage_event("scenario_runtime", "template_deliverable_plan_build_returned", stage=stage)
        record_stage_event("scenario_runtime", "active_capabilities_call", stage=stage)
        active_run = self._run_active_capabilities(
            request,
            resolution,
            plan,
            pre_activation_run,
            brain_result=brain_result,
        )
        record_stage_event("scenario_runtime", "active_capabilities_returned", stage=stage)
        record_stage_event("scenario_runtime", "frozen_capability_validation_call", stage=stage)
        self._validate_frozen_capability_execution(plan, active_run)
        record_stage_event("scenario_runtime", "frozen_capability_validation_returned", stage=stage)
        record_stage_event("scenario_runtime", "combine_capability_runs_call", stage=stage)
        combined = self._combine_capability_runs(request, resolution, pre_activation_run, active_run, plan)
        record_stage_event("scenario_runtime", "combine_capability_runs_returned", stage=stage)
        record_stage_event("scenario_runtime", "resolved_constraint_ledger_build_call", stage=stage)
        ledger = self._build_resolved_constraint_ledger(
            request,
            plan,
            combined,
            normalized_intent,
            deliverable_plan,
            brain_result=brain_result,
        )
        record_stage_event("scenario_runtime", "resolved_constraint_ledger_build_returned", stage=stage)
        record_stage_event("scenario_runtime", "capability_execution_envelope_build_call", stage=stage)
        envelope = self._build_capability_execution_envelope(
            plan,
            combined,
            normalized_intent,
            deliverable_plan,
            ledger,
        )
        record_stage_event("scenario_runtime", "capability_execution_envelope_build_returned", stage=stage)
        record_stage_event(
            "scenario_runtime",
            "canonical_finalizer_call",
            stage="provider_prompt_finalize",
            extra={"requested_image_count": self._requested_image_count_for_brain(request)},
        )
        brain_result = self._finalize_canonical_provider_prompts(
            request,
            resolution,
            policy,
            brain_result,
            plan,
            envelope,
            ledger,
        )
        record_stage_event(
            "scenario_runtime",
            "canonical_finalizer_returned",
            stage="provider_prompt_finalize",
            extra={
                "requested_image_count": self._requested_image_count_for_brain(request),
                "remote_brain_call_count": (
                    brain_result.audit.get("remote_brain_call_count")
                    if isinstance(brain_result.audit, dict)
                    else None
                ),
            },
        )
        self._require_brain_signed_provider_prompts(request, policy, brain_result, plan)
        plan, envelope, professional_preparation = self._finalize_professional_mode(
            professional_request,
            professional_preparation,
            brain_result,
            plan,
            envelope,
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
            professional_mode_preparation=professional_preparation,
            visual_asset_library_binding=library_binding,
        )

    def _prepare_library_visual_asset_binding(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        activation_mode: str,
    ) -> tuple[VisualAssetBindingSet | None, ScenarioRuntimeRequest]:
        """Validate the Product API's immutable library snapshot before Brain.

        This path is intentionally generic: it handles an explicit asset
        binding set, not a Professional project mode or a People-specific
        template.  The current release happens to expose only Face Identity.
        """

        metadata = dict(request.metadata or {})
        raw_snapshot = metadata.get("frozen_visual_asset_binding_set")
        if raw_snapshot is None:
            return None, request
        try:
            snapshot = FrozenVisualAssetBindingSet.model_validate(raw_snapshot)
        except (TypeError, ValueError) as exc:
            raise CapabilityActivationError("visual_asset_library_snapshot_invalid") from exc
        if snapshot.project_id != str(metadata.get("project_id") or "").strip():
            raise CapabilityActivationError("visual_asset_library_snapshot_project_mismatch")
        if snapshot.job_id != self._runtime_job_id(request, resolution):
            raise CapabilityActivationError("visual_asset_library_snapshot_job_mismatch")
        if snapshot.state == "empty":
            return None, request
        if activation_mode != "enforced":
            raise CapabilityActivationError("visual_asset_library_requires_enforced_activation")
        try:
            binding = VisualAssetBindingSet.from_library_snapshot(snapshot)
        except ValueError as exc:
            raise CapabilityActivationError("visual_asset_library_snapshot_binding_invalid") from exc
        safe_metadata = {
            **metadata,
            "visual_asset_library_binding": binding.to_provenance(),
        }
        return binding, request.model_copy(update={"metadata": safe_metadata})

    def _prepare_professional_mode(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        activation_mode: str,
    ) -> tuple[
        ProfessionalModeExecutionRequest | None,
        ProfessionalModePreparationResult | None,
        ScenarioRuntimeRequest,
    ]:
        """Admit explicit Professional Mode before the shared plan freezes."""

        metadata = dict(request.metadata or {})
        if metadata.get("professional_character_card_preparation") is True:
            if activation_mode != "enforced":
                raise CapabilityActivationError("professional_mode_requires_enforced_activation")
            raw_mode = metadata.get("professional_mode")
            if raw_mode is not True and str(raw_mode or "").strip().lower() != "professional":
                raise CapabilityActivationError("professional_character_card_mode_missing")
            stage = metadata.get("professional_character_card_stage")
            slot_key = str(metadata.get("professional_character_card_slot") or "").strip()
            if stage not in {"expression_set", "body_silhouette"} or not slot_key:
                raise CapabilityActivationError("professional_character_card_stage_invalid")
            planning_metadata = metadata.get("professional_planning_metadata")
            if not isinstance(planning_metadata, dict):
                raise CapabilityActivationError("professional_character_card_contract_missing")
            if (
                planning_metadata.get("stage") != stage
                or planning_metadata.get("slot_key") != slot_key
                or planning_metadata.get("creative_direction_owner") != "remote_v3_llm_brain"
            ):
                raise CapabilityActivationError("professional_character_card_contract_invalid")
            reference_assets = metadata.get("professional_anchor_reference_assets")
            if not isinstance(reference_assets, list) or not reference_assets:
                raise CapabilityActivationError("professional_character_card_reference_evidence_missing")
            safe_metadata = {
                **metadata,
                "professional_mode": True,
                "professional_character_card_preparation": True,
                "professional_character_card_stage": stage,
                "professional_character_card_slot": slot_key,
                "professional_planning_metadata": dict(planning_metadata),
            }
            return None, None, request.model_copy(update={"metadata": safe_metadata})
        if metadata.get("professional_anchor_pack_preparation") is True:
            if activation_mode != "enforced":
                raise CapabilityActivationError("professional_mode_requires_enforced_activation")
            raw_mode = metadata.get("professional_mode")
            if raw_mode is not True and str(raw_mode or "").strip().lower() != "professional":
                raise CapabilityActivationError("professional_anchor_pack_preparation_mode_missing")
            planning_metadata = metadata.get("professional_planning_metadata")
            stage = (
                planning_metadata.get("professional_reference_stage")
                if isinstance(planning_metadata, dict)
                else None
            )
            if stage not in {
                "standard_front",
                "left_front_25",
                "three_quarter",
                "profile",
                "right_front_25",
                "reverse_three_quarter",
                "rear_head",
            }:
                raise CapabilityActivationError("professional_anchor_pack_preparation_stage_invalid")
            capture_scope = str(
                (planning_metadata or {}).get("professional_anchor_capture_scope")
                if isinstance(planning_metadata, dict)
                else "anchor_pack"
            ).strip() or "anchor_pack"
            if capture_scope not in {"anchor_pack", "character_card_face_identity"}:
                raise CapabilityActivationError("professional_anchor_capture_scope_invalid")
            expected_metadata = self.professional_mode_runtime_bridge.anchor_pack_preparation_metadata(
                view_role=stage,
                capture_scope=capture_scope,
            )
            if planning_metadata != expected_metadata:
                raise CapabilityActivationError("professional_anchor_pack_preparation_contract_invalid")
            identity_roles = {
                "face_reference",
                "identity",
                "portrait_identity_reference",
            }
            identity_assets = [
                asset
                for asset in self._uploaded_assets(request)
                if str(asset.role.value if hasattr(asset.role, "value") else asset.role).strip().lower()
                in identity_roles
                and str(asset.file_path or "").strip()
            ]
            if not identity_assets:
                raise CapabilityActivationError("professional_anchor_pack_root_evidence_missing")
            safe_metadata = {
                **metadata,
                "professional_mode": True,
                "professional_anchor_pack_preparation": True,
                "professional_planning_metadata": dict(planning_metadata),
            }
            return None, None, request.model_copy(update={"metadata": safe_metadata})
        # Product API persists the server-owned planning provenance as a
        # boolean (``True``) while the public request contract uses the
        # explicit string ``"professional"``.  Normalize that internal
        # representation before validating the mode so a planned
        # Professional job can be generated through the same frozen path.
        raw_mode_value = metadata.get("professional_mode")
        if raw_mode_value is True:
            raw_mode = "professional"
        elif raw_mode_value is False or raw_mode_value is None:
            raw_mode = "standard"
        else:
            raw_mode = str(raw_mode_value).strip().lower()
        has_professional_binding = any(
            key in metadata
            for key in (
                "professional_mode_binding",
                "professional_mode_binding_record",
                "professional_reference_channel_plans",
            )
        )
        if raw_mode == "standard":
            if has_professional_binding:
                raise CapabilityActivationError("professional_metadata_in_standard_mode")
            return None, None, request
        if raw_mode != "professional":
            raise CapabilityActivationError("professional_mode_selection_invalid")
        if activation_mode != "enforced":
            raise CapabilityActivationError("professional_mode_requires_enforced_activation")
        binding_error = str(metadata.get("professional_mode_binding_error") or "").strip()
        if binding_error:
            raise CapabilityActivationError(binding_error)

        binding_payload = metadata.get("professional_mode_binding_record") or metadata.get(
            "professional_mode_binding"
        )
        try:
            binding = ProfessionalModeBinding.model_validate(binding_payload)
            if binding.project_id != str(metadata.get("project_id") or binding.project_id):
                raise ValueError("professional binding project mismatch")
            consumer_request = ProfessionalConsumerRequest(
                template_id=self._template_id(request, resolution),
                mode="professional",
                binding=binding,
            )
            raw_plans = metadata.get("professional_reference_channel_plans") or []
            if not isinstance(raw_plans, list):
                raise ValueError("professional reference plans must be a list")
            reference_plans = [ReferenceChannelPlan.model_validate(item) for item in raw_plans]
            execution_request = ProfessionalModeExecutionRequest(
                consumer_request=consumer_request,
                reference_plans=reference_plans,
            )
            preparation = self.professional_mode_execution_adapter.prepare_pre_freeze(execution_request)
        except (TypeError, ValueError) as exc:
            raise CapabilityActivationError("professional_mode_binding_invalid") from exc
        if preparation is None:
            raise CapabilityActivationError("professional_mode_binding_missing")
        if preparation.status != "ready" or preparation.context is None:
            reasons = ",".join(preparation.reason_codes) or "reference_admission_blocked"
            raise CapabilityActivationError(f"professional_mode_reference_admission_blocked:{reasons}")

        # Keep the Brain-facing transport typed and sanitized. The full
        # server-owned record remains local runtime provenance only.
        planning_metadata = dict(preparation.context.planning_metadata)
        safe_metadata = {
            **metadata,
            "professional_mode": True,
            "professional_mode_binding": binding.to_brain_evidence(),
            "professional_planning_metadata": planning_metadata,
        }
        return execution_request, preparation, request.model_copy(update={"metadata": safe_metadata})

    def _bind_professional_task_profile(
        self,
        brain_result: BrainRunResult,
        execution_request: ProfessionalModeExecutionRequest | None,
    ) -> BrainRunResult:
        if execution_request is None:
            return brain_result
        profile = brain_result.visual_task_profile
        if profile is None:
            raise CapabilityActivationError("professional_mode_task_profile_missing")
        try:
            bound_profile = self.professional_mode_runtime_bridge.bind_task_profile(
                profile,
                execution_request.consumer_request.binding,
            )
        except (TypeError, ValueError) as exc:
            raise CapabilityActivationError("professional_mode_task_profile_binding_invalid") from exc
        return brain_result.model_copy(update={"visual_task_profile": bound_profile})

    def _finalize_professional_mode(
        self,
        execution_request: ProfessionalModeExecutionRequest | None,
        preflight: ProfessionalModePreparationResult | None,
        brain_result: BrainRunResult,
        plan: CapabilityActivationPlan,
        envelope: CapabilityExecutionEnvelope,
    ) -> tuple[CapabilityActivationPlan, CapabilityExecutionEnvelope, ProfessionalModePreparationResult | None]:
        if execution_request is None:
            return plan, envelope, preflight
        prompts = list(brain_result.canonical_provider_prompts or [])
        if not prompts:
            raise CapabilityActivationError("professional_mode_canonical_prompt_missing")
        prompt_hashes = [hashlib.sha256(item.prompt.encode("utf-8")).hexdigest() for item in prompts]
        final_request = execution_request.model_copy(
            update={
                "canonical_prompt_hash": prompt_hashes[0],
                "canonical_prompt_hashes": prompt_hashes,
            }
        )
        final_preparation = self.professional_mode_execution_adapter.prepare(final_request)
        if final_preparation is None or final_preparation.status != "ready" or final_preparation.context is None:
            reasons = ",".join(final_preparation.reason_codes) if final_preparation else "missing_context"
            raise CapabilityActivationError(f"professional_mode_final_admission_blocked:{reasons}")
        final_metadata = dict(final_preparation.context.planning_metadata)
        updated_plan = plan.model_copy(update={"metadata": {**dict(plan.metadata), **final_metadata}})
        receipts = [
            CanonicalProviderPromptReceipt(
                prompt_hash=prompt_hash,
                signed_by="remote_v3_llm_brain",
                signature_valid=True,
                renderer_model="gpt-image-2",
            )
            for prompt_hash in prompt_hashes
        ]
        try:
            self.professional_mode_runtime_bridge.validate_frozen_plan(
                updated_plan,
                final_request.consumer_request.binding,
                receipts,
            )
        except ValueError as exc:
            raise CapabilityActivationError("professional_mode_frozen_plan_validation_failed") from exc
        updated_envelope = envelope.model_copy(update={"activation_plan": updated_plan})
        return updated_plan, updated_envelope, final_preparation

    def _require_remote_creative_brain(
        self,
        request: ScenarioRuntimeRequest,
        policy: TemplateCapabilityPolicy,
        brain_result: BrainRunResult,
    ) -> None:
        """Fail closed for templates whose creative answer cannot be local.

        General keeps its compatibility fallback for ordinary, non-production
        planning. A job that explicitly requires a real image is an
        acceptance/production assertion, however: it cannot silently turn a
        remote creative-brain outage into a locally invented image direction.
        Active specialized templates (E-Commerce and Photography) likewise
        never convert a missing or malformed remote creative answer into local
        direction.
        """

        real_image_job = self._requires_remote_creative_brain_for_real_images(request)
        if not policy.requires_remote_creative_brain and not real_image_job:
            return
        if self._uses_character_card_slot_delta_recovery(brain_result):
            return
        if brain_result.audit.get("ecommerce_creative_risk_preflight_stop") is True:
            raise self._remote_creative_brain_block(
                "ecommerce_creative_risk_preflight_invalid"
                if brain_result.audit.get("ecommerce_creative_risk_preflight_invalid") is True
                else "ecommerce_creative_risk_preflight_blocked",
                brain_result,
            )
        if not brain_result.llm_used or brain_result.fallback_used:
            raise self._remote_creative_brain_block(
                "remote_brain_unauthorized"
                if brain_result.audit.get("remote_provider_http_status_code") in {401, 403}
                else (
                    "remote_brain_unavailable"
                    if real_image_job and not policy.requires_remote_creative_brain
                    else "remote_creative_brain_required_for_template"
                ),
                brain_result,
            )
        rejected_sections = brain_result.audit.get("remote_contract_rejected_sections")
        if isinstance(rejected_sections, list) and "image_set_plan" in rejected_sections:
            raise self._remote_creative_brain_block(
                "remote_creative_brain_image_set_plan_invalid",
                brain_result,
                rejected_sections=rejected_sections,
            )
        if isinstance(rejected_sections, list) and "visual_task_profile" in rejected_sections:
            raise self._remote_creative_brain_block(
                "remote_creative_brain_task_profile_invalid",
                brain_result,
                rejected_sections=rejected_sections,
            )
        if isinstance(rejected_sections, list) and "capability_activation_intent" in rejected_sections:
            raise self._remote_creative_brain_block(
                "remote_creative_brain_capability_intent_invalid",
                brain_result,
                rejected_sections=rejected_sections,
            )
        if isinstance(rejected_sections, list) and (
            "canonical_provider_prompts" in rejected_sections
            or "visual_task_profile.rendering_intent" in rejected_sections
        ):
            raise self._remote_creative_brain_block(
                "remote_creative_brain_prompt_signoff_invalid",
                brain_result,
                rejected_sections=rejected_sections,
            )
        expected = self._requested_image_count_for_brain(request)
        image_plan = brain_result.image_set_plan
        directions = [str(item).strip() for item in image_plan.shot_plan if str(item).strip()]
        if image_plan.image_count != expected or len(directions) != expected:
            raise self._remote_creative_brain_block(
                "remote_creative_brain_output_count_mismatch",
                brain_result,
                expected_image_count=expected,
                actual_image_count=image_plan.image_count,
                actual_direction_count=len(directions),
            )
        if not bool(brain_result.audit.get("remote_rendering_intent_received")):
            raise self._remote_creative_brain_block(
                "remote_creative_brain_rendering_semantics_missing",
                brain_result,
            )
        if not bool(brain_result.audit.get("remote_visual_task_profile_received")):
            raise self._remote_creative_brain_block(
                "remote_creative_brain_task_profile_missing",
                brain_result,
            )
        if not bool(brain_result.audit.get("remote_capability_activation_intent_received")):
            raise self._remote_creative_brain_block(
                "remote_creative_brain_capability_intent_missing",
                brain_result,
            )

    def _recover_character_card_slot_delta_brain_result(
        self,
        request: ScenarioRuntimeRequest,
        brain_result: BrainRunResult,
        *,
        force_after_finalizer_failure: bool = False,
        recovery_reason: str = "remote_brain_timeout_or_unavailable",
    ) -> BrainRunResult:
        """Bounded prompt recovery for reference-led Character Card face slots.

        This is not a general local creative fallback.  It is allowed only for
        later Face Identity card slots whose identity, age, crop and reference
        chain are already frozen by Professional metadata.  The recovered text
        is a minimal slot delta; generated pixels still go through the same
        Provider/MCP output store and shared Vision gates.
        """

        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        expression_slot = self._character_card_expression_slot_delta_target(metadata)
        body_slot = self._character_card_body_slot_delta_target(metadata)
        rejected_sections = (
            brain_result.audit.get("remote_contract_rejected_sections")
            if isinstance(brain_result.audit, dict)
            else None
        )
        body_image_set_plan_rejected = bool(
            body_slot is not None
            and isinstance(rejected_sections, list)
            and "image_set_plan" in rejected_sections
        )
        if (
            not force_after_finalizer_failure
            and not body_image_set_plan_rejected
            and (brain_result.llm_used or not brain_result.fallback_used)
        ):
            return brain_result
        if (
            not force_after_finalizer_failure
            and not body_image_set_plan_rejected
            and str(brain_result.provider or "") != "remote_required"
        ):
            return brain_result
        if expression_slot is not None:
            return self._recover_character_card_expression_slot_delta_brain_result(
                request,
                brain_result,
                slot_key=expression_slot[0],
                expression=expression_slot[1],
                recovery_reason=recovery_reason,
            )
        if body_slot is not None:
            if body_image_set_plan_rejected and recovery_reason == "remote_brain_timeout_or_unavailable":
                recovery_reason = "remote_creative_brain_image_set_plan_invalid"
            return self._recover_character_card_body_slot_delta_brain_result(
                request,
                brain_result,
                slot_key=body_slot,
                recovery_reason=recovery_reason,
            )
        if metadata.get("professional_anchor_pack_preparation") is not True:
            return brain_result
        planning_metadata = metadata.get("professional_planning_metadata")
        if not isinstance(planning_metadata, dict):
            return brain_result
        if planning_metadata.get("professional_anchor_capture_scope") != "character_card_face_identity":
            return brain_result
        view_role = str(planning_metadata.get("professional_reference_stage") or "").strip()
        if view_role not in {
            "left_front_25",
            "three_quarter",
            "profile",
            "right_front_25",
            "reverse_three_quarter",
            "rear_head",
        }:
            return brain_result
        reference_assets = metadata.get("professional_anchor_reference_assets")
        if not isinstance(reference_assets, list):
            return brain_result
        source_asset_ids = self._character_card_slot_delta_recovery_source_asset_ids(
            request,
            reference_assets,
        )
        if len(source_asset_ids) < 2:
            return brain_result
        expected = self._requested_image_count_for_brain(request)
        if expected != 1:
            return brain_result

        prompt = self._character_card_slot_delta_recovery_prompt(view_role)
        project_id = str(metadata.get("project_id") or "").strip() or None
        profile_id = stable_id(
            "character_card_slot_delta_recovery_profile",
            project_id or "",
            view_role,
            *source_asset_ids,
        )
        evidence_id = stable_id("character_card_slot_delta_recovery_evidence", profile_id)
        task_profile = VisualTaskProfile(
            profile_id=profile_id,
            project_id=project_id,
            job_id=stable_id("character_card_slot_delta_recovery_job", profile_id),
            template_id="general_template",
            scenario_id="general_creative",
            rendering_intent=RenderingIntent(
                rendering_mode="photoreal",
                stylization_scope="none",
                decision_owner="remote_brain",
                evidence_ids=[evidence_id],
            ),
            developmental_age_intent="current_request_assigns_stage",
            reference_channel_ownership_intent=ReferenceChannelOwnershipIntent(
                applicability="applicable",
                decision_owner="remote_brain",
                reference_owned_channels=["identity_geometry"],
                current_request_owned_channels=[
                    "natural_complexion_direction",
                    "hair_direction",
                    "wardrobe_structure",
                    "lighting_color",
                    "scene_background",
                    "camera_composition",
                    "mood_art_direction",
                    "style_finish",
                ],
                evidence_ids=[evidence_id],
                confidence=0.9,
            ),
            subject_entities=[
                VisualSubjectEntity(
                    entity_id="character_card_face_identity_subject",
                    entity_type="person",
                    role="face_identity_subject",
                    source_asset_ids=source_asset_ids,
                    visible_in_target=view_role != "rear_head",
                    preservation_level="strong",
                    confidence=0.95,
                    attributes={
                        "capture_scope": "character_card_face_identity",
                        "target_view_role": view_role,
                    },
                )
            ],
            allowed_changes=["view_angle_only"],
            visual_intent_tags=[
                "character_card_face_identity",
                "reference_led_slot_delta",
                view_role,
            ],
            commercial_goal_tags=["commercial_clean_reference_card"],
            confidence=0.92,
            evidence=[
                ActivationEvidence(
                    evidence_id=evidence_id,
                    evidence_type="professional_character_card_reference_chain",
                    source="bounded_slot_delta_recovery",
                    value={"target_view_role": view_role, "reference_count": len(source_asset_ids)},
                    confidence=0.95,
                )
            ],
        )
        activation_intent = CapabilityActivationIntent(
            intent_id=stable_id("character_card_slot_delta_recovery_capabilities", profile_id),
            task_profile_id=profile_id,
            requested_capabilities=[
                RequestedCapability(
                    capability_id="portrait_identity",
                    activation_mode="required",
                    reason_codes=["approved_character_card_reference_identity"],
                    evidence_ids=[evidence_id],
                    requested_profile="strong",
                    confidence=0.95,
                ),
                RequestedCapability(
                    capability_id="reference_channel_policy",
                    activation_mode="required",
                    reason_codes=["reference_led_slot_delta_identity_boundary"],
                    evidence_ids=[evidence_id],
                    confidence=0.95,
                ),
                RequestedCapability(
                    capability_id="human_realism",
                    activation_mode="required",
                    reason_codes=["real_person_character_card_capture"],
                    evidence_ids=[evidence_id],
                    requested_profile="strict",
                    confidence=0.9,
                ),
                RequestedCapability(
                    capability_id="commercial_quality",
                    activation_mode="recommended",
                    reason_codes=["commercial_clean_reference_card"],
                    evidence_ids=[evidence_id],
                    requested_profile="commercial_strict",
                    confidence=0.85,
                ),
            ],
            confidence=0.92,
        )
        requested_size = str(metadata.get("requested_image_size") or "1024x1536").strip() or "1024x1536"
        canonical = BrainCanonicalProviderPrompt(
            output_index=1,
            prompt=prompt,
            review_status="approved",
            semantic_preflight_status="approved",
            human_naturalness_decision={
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            reference_channel_ownership_decision={
                "contract_version": "v3_reference_channel_ownership_decision_v1",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            human_developmental_age_decision={
                "contract_version": "v3_human_developmental_age_decision_v2",
                "age_fidelity": "follow_explicit_prompt",
                "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                "developmental_age_coherence": "whole_person_requested_stage",
                "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            human_developmental_presence_decision={
                "contract_version": "v3_human_developmental_presence_decision_v2",
                "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                "resolution_mode": "holistic_person_and_situation_resolution",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            professional_anchor_view_decision={
                "contract_version": "v3_professional_anchor_view_decision_v3",
                "target_view_role": view_role,
                "capture_presentation": "neutral_identity_evidence_capture",
                "capture_continuity": "preserve_approved_prior_capture",
                "capture_scope": "character_card_face_identity",
                "framing_standard": "consistent_head_and_upper_shoulders_reference_crop",
                "crop_policy": "head_top_margin_full_face_neck_and_upper_shoulders_visible",
                "torso_scope": "visible_neck_collar_and_upper_shoulders",
                "aspect_ratio_standard": "honor_frozen_rendering_size_as_reference_card_aspect_ratio",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            provider_admission_decision={
                "contract_version": "v3_provider_admission_decision_v1",
                "provider_admission_status": "admitted",
                "prompt_language_mode": "concise_positive_renderer_direction",
                "safety_sensitive_prompt_normalized": "applied",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            reference_led_slot_delta_decision={
                "contract_version": "v3_reference_led_slot_delta_decision_v1",
                "materialization_mode": "reference_led_slot_delta",
                "stable_identity_source": "approved_character_card_reference",
                "prompt_scope": "slot_delta_only",
                "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
                "slot_delta_type": "view_angle",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
        )
        return brain_result.model_copy(
            update={
                "canonical_provider_prompts": [canonical],
                "image_set_plan": brain_result.image_set_plan.model_copy(
                    update={
                        "set_goal": f"character_card_{view_role}_slot_delta_recovery",
                        "image_count": 1,
                        "size": requested_size,
                        "shot_plan": [prompt],
                        "composition_rules": [
                            "head, neck, and upper shoulders reference-card crop",
                            "plain white studio background",
                            "single complete image frame",
                        ],
                        "quality_bar": [
                            "commercial clean image",
                            "same-person likeness from approved references",
                            "requested face-view angle must be visible",
                        ],
                    }
                ),
                "prompt_guidance": brain_result.prompt_guidance.model_copy(
                    update={
                        "optimized_direction": prompt,
                        "visual_direction_addons": [prompt],
                        "layout_notes": ["vertical 2:3 reference-card crop"],
                        "hard_constraints": [
                            "Use approved references for identity; change only the requested face-view angle.",
                            "Keep a clean white studio close model-card crop with visible neck, collar, and upper shoulders; not half-body and not big-head.",
                        ],
                        "negative_prompt_addons": [
                            "avoid unrequested wardrobe, style, or scene changes",
                        ],
                        "consistency_strategy": "reference_led_character_card_slot_delta_recovery",
                    }
                ),
                "visual_task_profile": task_profile,
                "capability_activation_intent": activation_intent,
                "prompt_review": brain_result.prompt_review.model_copy(
                    update={
                        "status": "passed",
                        "checks": [
                            "character_card_reference_chain_present",
                            "slot_delta_prompt_recovered_after_remote_timeout",
                        ],
                    }
                ),
                "warnings": [
                    *list(brain_result.warnings or []),
                    "Remote Brain timed out; Character Card used bounded reference-led slot-delta recovery.",
                ],
                "audit": {
                    **dict(brain_result.audit or {}),
                    "character_card_slot_delta_recovery_used": True,
                    "character_card_slot_delta_recovery_prompts_received": True,
                    "character_card_slot_delta_recovery_reason": recovery_reason,
                    "character_card_slot_delta_recovery_scope": "professional_character_card_face_identity_non_front",
                    "character_card_slot_delta_recovery_view_role": view_role,
                    "remote_canonical_provider_prompts_received": False,
                    "human_realism_semantic_preflight_signed": True,
                    "human_realism_natural_presence_resigned": True,
                    "human_realism_natural_presence_decision_signed": True,
                    "reference_channel_ownership_decision_required": True,
                    "reference_channel_ownership_decision_signed": True,
                    "professional_anchor_view_decision_required": True,
                    "professional_anchor_view_decision_signed": True,
                    "provider_admission_decision_required": True,
                    "provider_admission_decision_signed": True,
                    "reference_led_slot_delta_decision_signed": True,
                    "canonical_provider_prompt_stage": "character_card_slot_delta_recovery",
                    "canonical_provider_prompt_stages": ["character_card_slot_delta_recovery"],
                },
            }
        )
        record_stage_event("scenario_runtime", "creative_planning_returned", stage="plan")

    @staticmethod
    def _professional_character_card_stage(
        metadata: dict[str, Any],
        planning_metadata: dict[str, Any] | None,
    ) -> str:
        stage = str(metadata.get("professional_character_card_stage") or "").strip()
        if not stage and isinstance(planning_metadata, dict):
            stage = str(planning_metadata.get("stage") or "").strip()
        return stage

    @staticmethod
    def _professional_body_silhouette_source_contract(
        planning_metadata: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if not isinstance(planning_metadata, dict):
            return None
        contract = planning_metadata.get("professional_body_silhouette_source_contract")
        if isinstance(contract, dict):
            return dict(contract)

        # Historical read compatibility: older Body metadata stored Body-owned
        # source/review facts inside the broad Face quality key.  New Body
        # prompts must not project that Face key, but persisted records remain
        # readable by extracting only the Body-owned nested fields into the
        # dedicated Body contract shape.
        legacy_quality = planning_metadata.get("professional_face_identity_quality_contract")
        if not isinstance(legacy_quality, dict):
            return None
        source_standard = legacy_quality.get("body_silhouette_source_standard_contract")
        mcp_contract = legacy_quality.get("body_silhouette_mcp_materialization_channel_contract")
        hair_contract = legacy_quality.get("body_silhouette_hair_continuity_contract")
        if not any(isinstance(item, dict) for item in (source_standard, mcp_contract, hair_contract)):
            return None
        compatible: dict[str, Any] = {
            "contract_version": "professional_body_silhouette_source_contract_v1",
            "owner": "professional_character_card_body_silhouette",
            "scope": "character_card_body_silhouette_only",
            "face_identity_reference_scope": "identity_continuity_only",
            "non_body_channels": "unspecified",
        }
        if isinstance(source_standard, dict):
            compatible["source_standard_contract"] = dict(source_standard)
        if isinstance(mcp_contract, dict):
            compatible["mcp_materialization_channel_contract"] = dict(mcp_contract)
        if isinstance(hair_contract, dict):
            compatible["hair_continuity_contract"] = dict(hair_contract)
        return compatible

    def _recover_character_card_body_slot_delta_brain_result(
        self,
        request: ScenarioRuntimeRequest,
        brain_result: BrainRunResult,
        *,
        slot_key: str,
        recovery_reason: str,
    ) -> BrainRunResult:
        """Bounded prompt recovery for Body Silhouette slots.

        This mirrors the existing Face/Expression reference-led recovery
        authority, but remains Body-owned: it requires the typed Body
        silhouette stage contract, the current Face reference chain, and a
        single requested output.  The recovered prompt is a compact body-pose
        materialization direction; shared Vision and Body enhanced review still
        own pixel acceptance.
        """

        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        planning_metadata = metadata.get("professional_planning_metadata")
        if not isinstance(planning_metadata, dict):
            return brain_result
        if (
            planning_metadata.get("stage") != "body_silhouette"
            or planning_metadata.get("slot_key") != slot_key
            or planning_metadata.get("creative_direction_owner") != "remote_v3_llm_brain"
        ):
            return brain_result
        slot_delta_contract = planning_metadata.get("reference_led_slot_delta_contract")
        if not isinstance(slot_delta_contract, dict) or slot_delta_contract.get("slot_delta_type") != "body_pose":
            return brain_result
        legacy_quality_contract = planning_metadata.get("professional_face_identity_quality_contract")
        legacy_quality_contract = legacy_quality_contract if isinstance(legacy_quality_contract, dict) else {}
        if "body_silhouette_wardrobe_contract" in legacy_quality_contract:
            return brain_result
        body_source_contract = self._professional_body_silhouette_source_contract(planning_metadata)
        body_source_contract = body_source_contract if isinstance(body_source_contract, dict) else {}
        source_standard_contract = body_source_contract.get("source_standard_contract")
        hair_contract = body_source_contract.get("hair_continuity_contract")
        if not isinstance(source_standard_contract, dict) or source_standard_contract.get("scope") != "body_silhouette_only":
            return brain_result
        if not isinstance(hair_contract, dict) or hair_contract.get("scope") != "body_silhouette_only":
            return brain_result
        reference_assets = metadata.get("professional_anchor_reference_assets")
        if not isinstance(reference_assets, list):
            return brain_result
        source_asset_ids = self._character_card_slot_delta_recovery_source_asset_ids(
            request,
            reference_assets,
        )
        if len(source_asset_ids) < 3:
            return brain_result
        expected = self._requested_image_count_for_brain(request)
        if expected != 1:
            return brain_result

        prompt = self._character_card_body_slot_delta_recovery_prompt(slot_key)
        project_id = str(metadata.get("project_id") or "").strip() or None
        profile_id = stable_id(
            "character_card_body_slot_delta_recovery_profile",
            project_id or "",
            slot_key,
            *source_asset_ids,
        )
        evidence_id = stable_id("character_card_body_slot_delta_recovery_evidence", profile_id)
        task_profile = VisualTaskProfile(
            profile_id=profile_id,
            project_id=project_id,
            job_id=stable_id("character_card_body_slot_delta_recovery_job", profile_id),
            template_id="general_template",
            scenario_id="general_creative",
            rendering_intent=RenderingIntent(
                rendering_mode="photoreal",
                stylization_scope="none",
                decision_owner="remote_brain",
                evidence_ids=[evidence_id],
            ),
            developmental_age_intent="current_request_assigns_stage",
            reference_channel_ownership_intent=ReferenceChannelOwnershipIntent(
                applicability="applicable",
                decision_owner="remote_brain",
                reference_owned_channels=[
                    "identity_geometry",
                    "body_identity",
                    "natural_complexion_direction",
                    "hair_direction",
                ],
                current_request_owned_channels=[
                    "wardrobe_structure",
                    "lighting_color",
                    "scene_background",
                    "camera_composition",
                    "mood_art_direction",
                    "style_finish",
                ],
                evidence_ids=[evidence_id],
                confidence=0.9,
            ),
            subject_entities=[
                VisualSubjectEntity(
                    entity_id="character_card_body_subject",
                    entity_type="person",
                    role="body_silhouette_subject",
                    source_asset_ids=source_asset_ids,
                    visible_in_target=True,
                    preservation_level="strong",
                    confidence=0.95,
                    attributes={
                        "capture_scope": "character_card_body_silhouette",
                        "slot_key": slot_key,
                        "baseline": "active_face_identity_winners",
                    },
                )
            ],
            allowed_changes=[
                "body_view_pose_and_full_body_framing_only",
                "scene_neutral_body_source_visibility",
                "natural_body_view_hair_movement",
            ],
            visual_intent_tags=[
                "character_card_body_silhouette",
                "reference_led_slot_delta",
                slot_key,
            ],
            commercial_goal_tags=["commercial_clean_reference_card"],
            confidence=0.92,
            evidence=[
                ActivationEvidence(
                    evidence_id=evidence_id,
                    evidence_type="professional_character_card_body_reference",
                    source="bounded_slot_delta_recovery",
                    value={"slot_key": slot_key, "reference_count": len(source_asset_ids)},
                    confidence=0.95,
                )
            ],
        )
        activation_intent = CapabilityActivationIntent(
            intent_id=stable_id("character_card_body_slot_delta_recovery_capabilities", profile_id),
            task_profile_id=profile_id,
            requested_capabilities=[
                RequestedCapability(
                    capability_id="portrait_identity",
                    activation_mode="required",
                    reason_codes=["approved_character_card_face_identity"],
                    evidence_ids=[evidence_id],
                    requested_profile="strong",
                    confidence=0.95,
                ),
                RequestedCapability(
                    capability_id="reference_channel_policy",
                    activation_mode="required",
                    reason_codes=["reference_led_body_pose_identity_boundary"],
                    evidence_ids=[evidence_id],
                    confidence=0.95,
                ),
                RequestedCapability(
                    capability_id="human_realism",
                    activation_mode="required",
                    reason_codes=["real_person_character_card_body_silhouette"],
                    evidence_ids=[evidence_id],
                    requested_profile="strict",
                    confidence=0.9,
                ),
                RequestedCapability(
                    capability_id="commercial_quality",
                    activation_mode="recommended",
                    reason_codes=["commercial_clean_reference_card"],
                    evidence_ids=[evidence_id],
                    requested_profile="commercial_strict",
                    confidence=0.85,
                ),
            ],
            confidence=0.92,
        )
        requested_size = str(metadata.get("requested_image_size") or "1024x1536").strip() or "1024x1536"
        canonical = BrainCanonicalProviderPrompt(
            output_index=1,
            prompt=prompt,
            review_status="approved",
            semantic_preflight_status="approved",
            human_naturalness_decision={
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            reference_channel_ownership_decision={
                "contract_version": "v3_reference_channel_ownership_decision_v1",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            human_developmental_age_decision={
                "contract_version": "v3_human_developmental_age_decision_v2",
                "age_fidelity": "follow_explicit_prompt",
                "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                "developmental_age_coherence": "whole_person_requested_stage",
                "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            human_developmental_presence_decision={
                "contract_version": "v3_human_developmental_presence_decision_v2",
                "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                "resolution_mode": "holistic_person_and_situation_resolution",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            provider_admission_decision={
                "contract_version": "v3_provider_admission_decision_v1",
                "provider_admission_status": "admitted",
                "prompt_language_mode": "concise_positive_renderer_direction",
                "safety_sensitive_prompt_normalized": "applied",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            reference_led_slot_delta_decision={
                "contract_version": "v3_reference_led_slot_delta_decision_v1",
                "materialization_mode": "reference_led_slot_delta",
                "stable_identity_source": "approved_character_card_reference",
                "prompt_scope": "slot_delta_only",
                "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
                "slot_delta_type": "body_pose",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
        )
        return brain_result.model_copy(
            update={
                "canonical_provider_prompts": [canonical],
                "image_set_plan": brain_result.image_set_plan.model_copy(
                    update={
                        "set_goal": f"character_card_{slot_key.replace('.', '_')}_body_slot_delta_recovery",
                        "image_count": 1,
                        "size": requested_size,
                        "shot_plan": [prompt],
                        "composition_rules": [
                            "full body contained from head to feet",
                            "body-only source-standard visibility",
                            "single complete image frame",
                        ],
                        "quality_bar": [
                            "commercial clean image",
                            "same-person likeness from approved Face references",
                            "Body source-standard and hair-continuity contracts must remain reviewable",
                        ],
                    }
                ),
                "prompt_guidance": brain_result.prompt_guidance.model_copy(
                    update={
                        "optimized_direction": prompt,
                        "visual_direction_addons": [prompt],
                        "layout_notes": ["vertical 2:3 full-body source-standard frame"],
                        "hard_constraints": [
                            "Use the approved Face Identity references for identity and hair continuity only.",
                            "Keep a full-body source-standard frame with head, neck, shoulders, torso, hands, legs, and feet visible.",
                            "Use body-only source presentation so body chain, proportions, stance, and ground contact remain reviewable.",
                        ],
                        "negative_prompt_addons": [
                            "avoid assigning non-body visual channels or downstream product inheritance",
                            "avoid changing hairstyle category, hair-length tier, bangs or parting pattern",
                        ],
                        "consistency_strategy": "reference_led_character_card_body_slot_delta_recovery",
                    }
                ),
                "visual_task_profile": task_profile,
                "capability_activation_intent": activation_intent,
                "prompt_review": brain_result.prompt_review.model_copy(
                    update={
                        "status": "passed",
                        "checks": [
                            "character_card_body_reference_chain_present",
                            "body_slot_delta_prompt_recovered_after_remote_timeout",
                        ],
                    }
                ),
                "warnings": [
                    *list(brain_result.warnings or []),
                    "Remote Brain timed out; Character Card used bounded reference-led Body slot-delta recovery.",
                ],
                "audit": {
                    **dict(brain_result.audit or {}),
                    "character_card_slot_delta_recovery_used": True,
                    "character_card_slot_delta_recovery_prompts_received": True,
                    "character_card_slot_delta_recovery_reason": recovery_reason,
                    "character_card_slot_delta_recovery_scope": "professional_character_card_body_silhouette",
                    "character_card_slot_delta_recovery_slot_key": slot_key,
                    "remote_canonical_provider_prompts_received": False,
                    "human_realism_semantic_preflight_signed": True,
                    "human_realism_natural_presence_resigned": True,
                    "human_realism_natural_presence_decision_signed": True,
                    "reference_channel_ownership_decision_required": True,
                    "reference_channel_ownership_decision_signed": True,
                    "provider_admission_decision_required": True,
                    "provider_admission_decision_signed": True,
                    "reference_led_slot_delta_decision_required": True,
                    "reference_led_slot_delta_decision_signed": True,
                    "canonical_provider_prompt_stage": "character_card_body_slot_delta_recovery",
                    "canonical_provider_prompt_stages": ["character_card_body_slot_delta_recovery"],
                },
            }
        )

    def _recover_character_card_expression_slot_delta_brain_result(
        self,
        request: ScenarioRuntimeRequest,
        brain_result: BrainRunResult,
        *,
        slot_key: str,
        expression: str,
        recovery_reason: str,
    ) -> BrainRunResult:
        """Bounded prompt recovery for reference-led Character Card expression slots.

        This mirrors the non-front Face Identity recovery contract: it is
        allowed only after the approved ``face.front`` winner and typed
        expression/framing contracts already exist.  The recovered text is a
        compact slot delta for MCP/Provider materialization; pixel acceptance
        still belongs to shared Vision/expression review receipts.
        """

        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        planning_metadata = metadata.get("professional_planning_metadata")
        if not isinstance(planning_metadata, dict):
            return brain_result
        if (
            planning_metadata.get("stage") != "expression_set"
            or planning_metadata.get("slot_key") != slot_key
            or planning_metadata.get("creative_direction_owner") != "remote_v3_llm_brain"
        ):
            return brain_result
        slot_delta_contract = planning_metadata.get("reference_led_slot_delta_contract")
        if not isinstance(slot_delta_contract, dict) or slot_delta_contract.get("slot_delta_type") != "expression":
            return brain_result
        reference_assets = metadata.get("professional_anchor_reference_assets")
        if not isinstance(reference_assets, list):
            return brain_result
        source_asset_ids = self._character_card_slot_delta_recovery_source_asset_ids(
            request,
            reference_assets,
        )
        if len(source_asset_ids) < 1:
            return brain_result
        expected = self._requested_image_count_for_brain(request)
        if expected != 1:
            return brain_result

        repair_context = metadata.get("character_card_prior_review_repair")
        prompt = self._character_card_expression_slot_delta_recovery_prompt(
            expression,
            repair_context=repair_context if isinstance(repair_context, dict) else None,
        )
        project_id = str(metadata.get("project_id") or "").strip() or None
        profile_id = stable_id(
            "character_card_expression_slot_delta_recovery_profile",
            project_id or "",
            slot_key,
            *source_asset_ids,
        )
        evidence_id = stable_id("character_card_expression_slot_delta_recovery_evidence", profile_id)
        task_profile = VisualTaskProfile(
            profile_id=profile_id,
            project_id=project_id,
            job_id=stable_id("character_card_expression_slot_delta_recovery_job", profile_id),
            template_id="general_template",
            scenario_id="general_creative",
            rendering_intent=RenderingIntent(
                rendering_mode="photoreal",
                stylization_scope="none",
                decision_owner="remote_brain",
                evidence_ids=[evidence_id],
            ),
            developmental_age_intent="current_request_assigns_stage",
            reference_channel_ownership_intent=ReferenceChannelOwnershipIntent(
                applicability="applicable",
                decision_owner="remote_brain",
                reference_owned_channels=[
                    "identity_geometry",
                    "natural_complexion_direction",
                    "lighting_color",
                    "camera_composition",
                ],
                current_request_owned_channels=["mood_art_direction"],
                evidence_ids=[evidence_id],
                confidence=0.9,
            ),
            subject_entities=[
                VisualSubjectEntity(
                    entity_id="character_card_expression_subject",
                    entity_type="person",
                    role="expression_subject",
                    source_asset_ids=source_asset_ids,
                    visible_in_target=True,
                    preservation_level="strong",
                    confidence=0.95,
                    attributes={
                        "capture_scope": "character_card_expression_set",
                        "slot_key": slot_key,
                        "expression": expression,
                        "baseline": "active_face_front_winner",
                    },
                )
            ],
            allowed_changes=["facial_expression_only", "small_natural_head_shoulder_energy"],
            visual_intent_tags=[
                "character_card_expression_set",
                "reference_led_slot_delta",
                expression,
            ],
            commercial_goal_tags=["commercial_clean_reference_card"],
            confidence=0.92,
            evidence=[
                ActivationEvidence(
                    evidence_id=evidence_id,
                    evidence_type="professional_character_card_expression_reference",
                    source="bounded_slot_delta_recovery",
                    value={
                        "slot_key": slot_key,
                        "expression": expression,
                        "reference_count": len(source_asset_ids),
                    },
                    confidence=0.95,
                )
            ],
        )
        activation_intent = CapabilityActivationIntent(
            intent_id=stable_id("character_card_expression_slot_delta_recovery_capabilities", profile_id),
            task_profile_id=profile_id,
            requested_capabilities=[
                RequestedCapability(
                    capability_id="portrait_identity",
                    activation_mode="required",
                    reason_codes=["approved_character_card_front_identity"],
                    evidence_ids=[evidence_id],
                    requested_profile="strong",
                    confidence=0.95,
                ),
                RequestedCapability(
                    capability_id="reference_channel_policy",
                    activation_mode="required",
                    reason_codes=["reference_led_expression_delta_identity_boundary"],
                    evidence_ids=[evidence_id],
                    confidence=0.95,
                ),
                RequestedCapability(
                    capability_id="human_realism",
                    activation_mode="required",
                    reason_codes=["real_person_character_card_expression"],
                    evidence_ids=[evidence_id],
                    requested_profile="strict",
                    confidence=0.9,
                ),
                RequestedCapability(
                    capability_id="commercial_quality",
                    activation_mode="recommended",
                    reason_codes=["commercial_clean_reference_card"],
                    evidence_ids=[evidence_id],
                    requested_profile="commercial_strict",
                    confidence=0.85,
                ),
            ],
            confidence=0.92,
        )
        requested_size = str(metadata.get("requested_image_size") or "1024x1536").strip() or "1024x1536"
        canonical = BrainCanonicalProviderPrompt(
            output_index=1,
            prompt=prompt,
            review_status="approved",
            semantic_preflight_status="approved",
            human_naturalness_decision={
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            reference_channel_ownership_decision={
                "contract_version": "v3_reference_channel_ownership_decision_v1",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            human_developmental_age_decision={
                "contract_version": "v3_human_developmental_age_decision_v2",
                "age_fidelity": "follow_explicit_prompt",
                "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
                "developmental_age_coherence": "whole_person_requested_stage",
                "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            human_developmental_presence_decision={
                "contract_version": "v3_human_developmental_presence_decision_v2",
                "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
                "resolution_mode": "holistic_person_and_situation_resolution",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            provider_admission_decision={
                "contract_version": "v3_provider_admission_decision_v1",
                "provider_admission_status": "admitted",
                "prompt_language_mode": "concise_positive_renderer_direction",
                "safety_sensitive_prompt_normalized": "applied",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
            reference_led_slot_delta_decision={
                "contract_version": "v3_reference_led_slot_delta_decision_v1",
                "materialization_mode": "reference_led_slot_delta",
                "stable_identity_source": "approved_character_card_reference",
                "prompt_scope": "slot_delta_only",
                "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
                "slot_delta_type": "expression",
                "status": "approved",
                "owner": "remote_v3_llm_brain",
            },
        )
        return brain_result.model_copy(
            update={
                "canonical_provider_prompts": [canonical],
                "image_set_plan": brain_result.image_set_plan.model_copy(
                    update={
                        "set_goal": f"character_card_{expression}_expression_slot_delta_recovery",
                        "image_count": 1,
                        "size": requested_size,
                        "shot_plan": [prompt],
                        "composition_rules": [
                            "inherit the active face.front 2:3 reference-card framing",
                            "plain white studio background",
                            "single complete image frame",
                        ],
                        "quality_bar": [
                            "commercial clean image",
                            "same-person likeness from the approved front card",
                            "expression must be visually legible through shared affective review",
                        ],
                    }
                ),
                "prompt_guidance": brain_result.prompt_guidance.model_copy(
                    update={
                        "optimized_direction": prompt,
                        "visual_direction_addons": [prompt],
                        "layout_notes": ["inherit active face.front vertical 2:3 reference-card crop"],
                        "hard_constraints": [
                            "Use the approved front card as the identity, lighting, white-background and framing baseline.",
                            "Change only facial expression and a very small amount of natural head-shoulder energy.",
                            "Keep the same clean white close model-card crop, photographer distance, visible neck, collar, and upper shoulders; not half-body and not big-head.",
                        ],
                        "negative_prompt_addons": [
                            "avoid mouth-only expression",
                            "avoid detached gaze",
                        ],
                        "consistency_strategy": "reference_led_character_card_expression_slot_delta_recovery",
                    }
                ),
                "visual_task_profile": task_profile,
                "capability_activation_intent": activation_intent,
                "prompt_review": brain_result.prompt_review.model_copy(
                    update={
                        "status": "passed",
                        "checks": [
                            "character_card_front_reference_present",
                            "expression_slot_delta_prompt_recovered_after_remote_timeout",
                        ],
                    }
                ),
                "warnings": [
                    *list(brain_result.warnings or []),
                    "Remote Brain timed out; Character Card used bounded reference-led expression slot-delta recovery.",
                ],
                "audit": {
                    **dict(brain_result.audit or {}),
                    "character_card_slot_delta_recovery_used": True,
                    "character_card_slot_delta_recovery_prompts_received": True,
                    "character_card_slot_delta_recovery_reason": recovery_reason,
                    "character_card_slot_delta_recovery_scope": "professional_character_card_expression_set",
                    "character_card_slot_delta_recovery_slot_key": slot_key,
                    "character_card_slot_delta_recovery_expression": expression,
                    "remote_canonical_provider_prompts_received": False,
                    "human_realism_semantic_preflight_signed": True,
                    "human_realism_natural_presence_resigned": True,
                    "human_realism_natural_presence_decision_signed": True,
                    "reference_channel_ownership_decision_required": True,
                    "reference_channel_ownership_decision_signed": True,
                    "provider_admission_decision_required": True,
                    "provider_admission_decision_signed": True,
                    "reference_led_slot_delta_decision_required": True,
                    "reference_led_slot_delta_decision_signed": True,
                    "canonical_provider_prompt_stage": "character_card_expression_slot_delta_recovery",
                    "canonical_provider_prompt_stages": ["character_card_expression_slot_delta_recovery"],
                },
            }
        )

    @staticmethod
    def _character_card_expression_slot_delta_target(metadata: dict[str, Any]) -> tuple[str, str] | None:
        if metadata.get("professional_character_card_preparation") is not True:
            return None
        if str(metadata.get("professional_character_card_stage") or "").strip() != "expression_set":
            return None
        slot_key = str(metadata.get("professional_character_card_slot") or "").strip()
        expression = slot_key.split(".", 1)[1] if slot_key.startswith("expression.") else ""
        if expression not in {"laugh", "smile", "anger", "sad"}:
            return None
        return slot_key, expression

    @staticmethod
    def _character_card_body_slot_delta_target(metadata: dict[str, Any]) -> str | None:
        if metadata.get("professional_character_card_preparation") is not True:
            return None
        if str(metadata.get("professional_character_card_stage") or "").strip() != "body_silhouette":
            return None
        slot_key = str(metadata.get("professional_character_card_slot") or "").strip()
        if slot_key not in {"body.front_full", "body.side_full", "body.rear_full"}:
            return None
        planning_metadata = metadata.get("professional_planning_metadata")
        if not isinstance(planning_metadata, dict):
            return None
        if planning_metadata.get("stage") != "body_silhouette" or planning_metadata.get("slot_key") != slot_key:
            return None
        return slot_key

    @staticmethod
    def _character_card_slot_delta_recovery_source_asset_ids(
        request: ScenarioRuntimeRequest,
        reference_assets: list[Any],
    ) -> list[str]:
        """Return the complete root-plus-winner evidence chain for recovery.

        ``professional_anchor_reference_assets`` intentionally contains only
        reviewed output winners; the original uploaded root remains on
        ``uploaded_asset_ids``.  The first 45° continuation therefore has one
        winner asset but two authoritative evidence sources: root + front.
        """

        source_ids: list[str] = []
        for asset_id in getattr(request, "uploaded_asset_ids", []) or []:
            value = str(asset_id or "").strip()
            if value and value not in source_ids:
                source_ids.append(value)
        for item in reference_assets:
            if not isinstance(item, dict):
                continue
            value = str(item.get("asset_id") or item.get("output_id") or "").strip()
            if value and value not in source_ids:
                source_ids.append(value)
        return source_ids

    @staticmethod
    def _uses_character_card_slot_delta_recovery(brain_result: BrainRunResult) -> bool:
        audit = brain_result.audit if isinstance(brain_result.audit, dict) else {}
        return bool(audit.get("character_card_slot_delta_recovery_prompts_received"))

    @staticmethod
    def _character_card_body_slot_delta_recovery_prompt(slot_key: str) -> str:
        view = {
            "body.front_full": "front-view",
            "body.side_full": "side-view",
            "body.rear_full": "rear-view",
        }.get(slot_key, "full-body")
        return (
            f"A full-body {view} Body Silhouette source-standard materialization of the same person from the approved "
            "Face Identity references, using those references only for identity continuity. "
            "The entire figure is visible from the top of the head to the feet, with hands, legs, shoulders, neck, "
            "and head contained inside the frame. "
            "Resolve only body-owned source channels: body scale, body chain, stage-aware proportion, "
            "neck-shoulder continuity, torso-limb plausibility, stance-ground contact, and cross-view parity. "
            "Keep non-body visual channels unspecified. "
            "Carry identity and hair continuity through the approved Face references: same hairstyle category, "
            "same hair-length tier, same bangs or parting pattern, and same overall hair outline, allowing natural "
            "movement from the requested body view."
        )

    @staticmethod
    def _character_card_expression_slot_delta_recovery_prompt(
        expression: str,
        *,
        repair_context: dict[str, Any] | None = None,
    ) -> str:
        base = (
            "Same person as the approved face.front Character Card winner, inheriting the face.front card framing, "
            "camera distance, head size, head-top margin, eye-line placement, background treatment, lighting direction, "
            "white balance, complexion channel, wardrobe/style channel, visual finish, and head-neck-upper-shoulders crop "
            "in the existing vertical 2:3 reference-card frame. "
            "Preserve identity, age coherence, camera-observed skin/material texture, and the approved card's style channels. "
            "Change only the facial expression and a very small amount of natural head-shoulder energy. "
            f"{expression_front_card_framing_materialization_directive()} "
        )
        endings = {
            "laugh": (
                laugh_expression_materialization_directive()
            ),
            "smile": (
                "Render a lower-intensity natural smile: gentle mouth-corner lift, engaged gaze, light cheek participation, "
                "relaxed jaw and small spontaneous asymmetry. It must read as a real smile, not neutral or plastic."
            ),
            "anger": (
                "Render a clearly readable childlike annoyed pout suitable for a reference card: knitted brows, focused eyes, "
                "a small stubborn frown or pressed lips, and playful innocent child energy without aggression or theatrical exaggeration."
            ),
            "sad": (
                "Render soft childlike sadness suitable for a reference card: misty-eyed vulnerability, slightly lifted inner brows, "
                "a gentle downturned mouth, and innocent quiet emotion without props, distress, or melodrama."
            ),
        }
        avoid = (
            " Keep the same clean white model-card frame, wardrobe/style channel, close photographer crop, visible neck, "
            "collar, and upper shoulders; change only the expression while preserving direct card usability."
        )
        repair_delta = shared_review_repair_prompt_delta(repair_context)
        if repair_delta:
            repair_delta = " " + repair_delta
        return base + endings.get(expression, endings["laugh"]) + repair_delta + avoid

    @staticmethod
    def _character_card_slot_delta_transport_timeout_seconds(
        request: ScenarioRuntimeRequest,
    ) -> float | None:
        """Shorten remote Brain waits only for reference-led non-front face slots.

        These slots are deliberately weak delta prompts: approved references and
        typed receipts already own identity, age, crop and material continuity.
        A slow remote finalizer should therefore yield quickly to the bounded
        slot-delta recovery path instead of stranding the browser.
        """

        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        if ScenarioRuntime._character_card_expression_slot_delta_target(metadata) is not None:
            try:
                raw = float(os.getenv("V3_CHARACTER_CARD_SLOT_DELTA_BRAIN_TIMEOUT_SECONDS", "28"))
            except ValueError:
                raw = 28.0
            return max(8.0, min(60.0, raw))
        if metadata.get("professional_anchor_pack_preparation") is not True:
            return None
        planning_metadata = metadata.get("professional_planning_metadata")
        if not isinstance(planning_metadata, dict):
            return None
        if planning_metadata.get("professional_anchor_capture_scope") != "character_card_face_identity":
            return None
        view_role = str(planning_metadata.get("professional_reference_stage") or "").strip()
        if view_role not in {
            "left_front_25",
            "three_quarter",
            "profile",
            "right_front_25",
            "reverse_three_quarter",
            "rear_head",
        }:
            return None
        try:
            raw = float(os.getenv("V3_CHARACTER_CARD_SLOT_DELTA_BRAIN_TIMEOUT_SECONDS", "28"))
        except ValueError:
            raw = 28.0
        return max(8.0, min(60.0, raw))

    @staticmethod
    def _character_card_slot_delta_recovery_prompt(view_role: str) -> str:
        visible_face_framing = (
            "Match the approved front card framing: same camera distance, head size, head-top margin, "
            "upper-shoulders cutoff, collar line and background padding. Keep a vertical 2:3 head-neck-upper-shoulders "
            "close model-card crop with the full head and hair boundary cleanly inside the frame, visible neck, collar, and upper shoulders; not half-body and not big-head. "
        )
        profile_framing = (
            "Match the approved front card framing: same camera distance, head size, head-top margin, "
            "upper-shoulders cutoff, collar line and background padding. Keep a vertical 2:3 head-neck-upper-shoulders "
            "close model-card crop with the full head and hair boundary cleanly inside the frame, visible neck, collar, and upper shoulders; not half-body and not big-head. "
        )
        rear_framing = (
            "Match the approved card framing: same camera distance, head size, head-top margin, "
            "upper-shoulders cutoff, back collar line and background padding. Keep a vertical 2:3 head-neck-upper-shoulders "
            "close model-card crop with the full back-of-head hair boundary cleanly inside the frame, visible neck, collar, and upper shoulders; not half-body and not big-head. "
        )
        prompts = {
            "left_front_25": (
                "Left-front shallow three-quarter transition portrait of the same person from the approved front card, "
                "head, neck and upper shoulders only, a natural left-front transition target around 25 to 30 degrees toward image-right, "
                "visually shallower than the later 45-degree card while clearly no longer a straight front portrait. "
                "Show measurable but moderate face depth, with the facial centerline slightly off-center, "
                "the nose bridge and gaze angled toward image-right, the near cheek slightly broader, the far cheek subtly narrower, "
                "the far eye slightly narrower than the near eye while both eyes remain close in size, and the left ear clearly beginning to show on image-left. "
                "Turn the head itself, not only the eyes; the gaze should follow the nose direction rather than looking straight into the camera. "
                "The result should sit between a straight front portrait and a full 45-degree view; allow natural renderer variation as long as it remains a usable transition bridge. "
                f"{visible_face_framing}"
                "Inherit the approved front card's background treatment, lighting direction, white balance, complexion channel, "
                "wardrobe/style channel, and visual finish; keep a natural neutral expression suitable for a reference card. "
                "Keep the frame as a clean white studio model-card portrait focused only on the subject."
            ),
            "three_quarter": (
                "Left-front three-quarter view portrait of the same person from the approved references, "
                "Reference role map: approved front card for identity and framing; approved left_front_25 only as the same-side identity bridge, not the target yaw. "
                "Create an independent left-front 40-to-50-degree card toward image-right, visibly deeper than the 25-degree bridge but not a pure profile. "
                "Turn head, neck and shoulders together; show the left ear on image-left, nose and gaze angled toward image-right, front-side facial depth, and a smaller far eye while both eyes remain visible. "
                "Do not reuse the bridge pose with only the pupils looking sideways; avoid straight-front, side-profile, rear/back, or opposite-side results. "
                f"{visible_face_framing}"
                "Inherit the approved front card's background treatment, lighting direction, white balance, complexion channel, "
                "wardrobe/style channel, and visual finish; keep a natural neutral expression suitable for a reference card. "
                "Keep the frame as a clean white studio model-card portrait focused only on the subject."
            ),
            "profile": (
                "Strict 90-degree side profile portrait of the same person from the approved references, "
                "head, neck and upper shoulders only, face turned fully to the left with one eye contour, "
                "nose bridge, lips and ear visible in side profile. "
                f"{profile_framing}"
                "Inherit the approved front card's background treatment, lighting direction, white balance, complexion channel, "
                "wardrobe/style channel, and visual finish; keep a natural neutral expression suitable for a reference card. "
                "Keep the frame as a clean white studio model-card portrait focused only on the subject."
            ),
            "right_front_25": (
                "Right-front shallow three-quarter transition portrait of the same person from the approved front card, "
                "head, neck and upper shoulders only, a natural right-front transition target around 25 to 30 degrees toward image-left, "
                "visually shallower than the later 45-degree card while clearly no longer a straight front portrait. "
                "Show measurable but moderate face depth, with the facial centerline slightly off-center toward image-left, "
                "the nose bridge and gaze angled toward image-left, the near cheek slightly broader, the far cheek subtly narrower, "
                "the far eye slightly narrower than the near eye while both eyes remain close in size, and the right/opposite ear clearly beginning to show on image-right. "
                "Turn the head itself, not only the eyes; the gaze should follow the nose direction rather than looking straight into the camera. "
                "The result should sit between a straight front portrait and a full 45-degree view; allow natural renderer variation as long as it remains a usable transition bridge. "
                "This is an independent right-side transition view, not a horizontal flip or copied left-side face; preserve natural left/right facial and hair asymmetry. "
                f"{visible_face_framing}"
                "Inherit the approved front card's background treatment, lighting direction, white balance, complexion channel, "
                "wardrobe/style channel, and visual finish; keep a natural neutral expression suitable for a reference card. "
                "Keep the frame as a clean white studio model-card portrait focused only on the subject."
            ),
            "reverse_three_quarter": (
                "Right-front three-quarter opposite front-side 45-degree view portrait of the same person from the approved references, "
                "Reference role map: input 1 is root identity geometry, input 2 is front identity detail, input 3 is front full-frame card framing, input 4 is the approved right-front 25-degree pose-geometry bridge, and input 5 is the approved right-front 25-degree raw continuity reference. "
                "Let inputs 4 and 5 preserve same-side pose direction and identity asymmetry; do not let the 25-degree bridge become the target yaw. "
                "Create an independent right-front 40-to-50-degree card toward image-left, visibly deeper than the 25-degree bridge but not a pure profile. "
                "Turn head, neck and shoulders together; show the right ear on image-right, nose and gaze angled toward image-left, front-side facial depth, and a smaller far eye while both eyes remain visible. "
                "Do not mirror or copy the left-front card; avoid straight-front, side-profile, rear/back, or same-side results. "
                f"{visible_face_framing}"
                "Inherit the approved front card's background treatment, lighting direction, white balance, complexion channel, "
                "wardrobe/style channel, and visual finish. "
                "Keep the frame as a clean white studio model-card portrait focused only on the subject."
            ),
            "rear_head": (
                "Back-of-head reference portrait of the same person from the approved references, "
                "head, neck and upper shoulders only, rear view of the head, no visible face and no eyes visible, "
                "natural hair shape and age-coherent head proportions. "
                f"{rear_framing}"
                "Inherit the approved front card's background treatment, lighting direction, white balance, "
                "wardrobe/style channel, and visual finish. "
                "Keep the frame as a clean white studio model-card portrait focused only on the subject."
            ),
        }
        return prompts.get(view_role, prompts["three_quarter"])

    def _finalize_canonical_provider_prompts(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        policy: TemplateCapabilityPolicy,
        brain_result: BrainRunResult,
        plan: CapabilityActivationPlan,
        envelope: CapabilityExecutionEnvelope,
        ledger: ResolvedConstraintLedger,
    ) -> BrainRunResult:
        """Obtain the only renderer-facing language after shared validation.

        Planning and final sign-off remain separate because the latter needs
        the frozen envelope and resolved constraint ledger. Human Realism's
        semantic preflight and natural-presence decision are part of the same
        Brain-owned finalization path. A current-request-owned developmental
        stage is adjudicated by the same final sign-off: its typed age and
        presence receipts remain mandatory, but create no third remote call.
        Professional serial stages
        receive one separate bounded capture-continuity re-sign after age
        coherence, because the prior winner—not the identity root—owns the
        in-pack capture presentation.
        """

        if not (policy.requires_remote_creative_brain or self._requires_remote_creative_brain_for_real_images(request)):
            return brain_result
        retry_active = bool(
            request.metadata.get("visual_auto_retry_active")
            or request.metadata.get("visual_retry_reason_codes")
        )
        existing = list(brain_result.canonical_provider_prompts or [])
        expected = self._requested_image_count_for_brain(request)
        if (
            brain_result.audit.get("frozen_execution_reuse")
            and not retry_active
            and [item.output_index for item in existing] == list(range(1, expected + 1))
            and (
                bool(brain_result.audit.get("remote_canonical_provider_prompts_received"))
                or self._uses_character_card_slot_delta_recovery(brain_result)
            )
        ):
            return brain_result

        try:
            canonical_prompt_context = self._canonical_prompt_context(
                request,
                plan,
                envelope,
                ledger,
                brain_result,
            )
        except CapabilityActivationError as exc:
            reason = str(exc)
            raise self._remote_creative_brain_block(
                reason
                if reason
                in {
                    "human_realism_semantic_contract_missing",
                    "professional_face_identity_quality_contract_missing",
                    "professional_body_silhouette_source_contract_missing",
                    "professional_anchor_view_contract_missing",
                    "reference_channel_ownership_contract_missing",
                }
                else "human_realism_semantic_contract_missing",
                brain_result,
            ) from exc
        if "human_realism" in plan.dependency_order:
            # This typed receipt requirement travels with the same frozen
            # context as the final prompt. It is not a prompt fragment.
            canonical_prompt_context["human_naturalness_decision"] = {
                "required": True,
                "contract_version": "v3_human_naturalness_decision_v1",
                "owner": "remote_v3_llm_brain",
                "frozen_binding": dict(canonical_prompt_context.get("frozen_binding") or {}),
            }
            presence_requirement = next(
                (
                    item.get("developmental_presence_requirement")
                    for item in canonical_prompt_context.get(
                        "active_semantic_capability_contracts", []
                    )
                    if isinstance(item, dict)
                    and item.get("capability_id") == "human_realism"
                ),
                None,
            )
            if presence_requirement == "integrated_stage_coherent_face_attention_and_affect":
                canonical_prompt_context["human_developmental_presence_decision"] = {
                    "required": True,
                    "contract_version": "v3_human_developmental_presence_decision_v2",
                    "developmental_presence": presence_requirement,
                    "resolution_mode": (
                        "holistic_person_and_situation_resolution"
                    ),
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": dict(canonical_prompt_context.get("frozen_binding") or {}),
                }

        signing_metadata: dict[str, Any] = {"canonical_prompt_context": canonical_prompt_context}
        # The complete renderer prompt must preserve the user's full direction.
        # Character Card slot deltas intentionally own a narrower prompt scope.
        if not canonical_prompt_context.get("character_card_slot_delta_target"):
            signing_metadata["require_lossless_user_direction"] = True
        if self._canonical_context_has_professional_body_contract(canonical_prompt_context):
            signing_metadata["professional_body_proportion_receipt_required"] = True
        if request.trusted_professional_anchor_view_decision_reuse:
            trusted_reuse = request.metadata.get(
                "trusted_professional_anchor_view_decision_reuse"
            )
            current_binding = request.metadata.get(
                "professional_anchor_view_decision_current_binding"
            )
            if isinstance(trusted_reuse, dict):
                signing_metadata["trusted_professional_anchor_view_decision_reuse"] = dict(
                    trusted_reuse
                )
            if isinstance(current_binding, dict):
                signing_metadata[
                    "professional_anchor_view_decision_current_binding"
                ] = dict(current_binding)
        signing_request = BrainRunRequest(
            user_input=request.user_input,
            job_id=self._runtime_job_id(request, resolution),
            stage="provider_prompt_finalize",
            scenario_id=resolution.manifest.scenario_id,
            template_id=self._template_id(request, resolution),
            project_id=str(request.metadata.get("project_id") or "") or None,
            requested_image_count=expected,
            requested_image_size=ledger.provider_projection.get("requested_image_size"),
            reasoning_depth="balanced",
            transport_timeout_seconds=self._character_card_slot_delta_transport_timeout_seconds(request),
            metadata=signing_metadata,
            template_capability_policy=policy,
        )
        try:
            prompts, audit = self.llm_brain_adapter.finalize_canonical_provider_prompts(signing_request)
        except Exception as first_exc:
            failure: Exception | None = first_exc
            if isinstance(first_exc, BrainProfessionalAnchorViewDecisionMissing):
                view_contract = canonical_prompt_context.get("professional_anchor_view_decision")
                view_contract = view_contract if isinstance(view_contract, dict) else {}
                required_receipt_fields = [
                    key
                    for key in (
                        "capture_scope",
                        "framing_standard",
                        "crop_policy",
                        "torso_scope",
                        "aspect_ratio_standard",
                        "source_viewpoint_inheritance",
                        "front_pose_normalization",
                        "face_axis_alignment",
                    )
                    if view_contract.get(key)
                ]
                recovery_context: dict[str, object] = {
                    "contract_version": "v3_professional_anchor_view_contract_recovery_v1",
                    "attempt": 1,
                    "same_frozen_context": True,
                    "target_view_role": str(view_contract.get("target_view_role") or ""),
                }
                if view_contract.get("capture_scope") == "character_card_face_identity":
                    recovery_context["capture_scope"] = str(view_contract.get("capture_scope") or "")
                if required_receipt_fields:
                    recovery_context["required_receipt_fields"] = required_receipt_fields
                if (
                    view_contract.get("aspect_ratio_standard")
                    == "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
                ):
                    recovery_context[
                        "required_prompt_materialization"
                    ] = "vertical_2_3_reference_card_aspect_language"
                recovery_request = signing_request.model_copy(
                    update={
                        "metadata": {
                            **dict(signing_request.metadata or {}),
                            "professional_anchor_view_contract_recovery": recovery_context,
                        }
                    },
                    deep=True,
                )
                try:
                    prompts, audit = self.llm_brain_adapter.finalize_canonical_provider_prompts(
                        recovery_request
                    )
                except Exception as recovery_exc:
                    failure = recovery_exc
                else:
                    failure = None
                    audit = {
                        **audit,
                        "professional_anchor_view_contract_recovery_attempted": True,
                        "professional_anchor_view_contract_recovery_succeeded": True,
                    }
            if failure is not None:
                recovered_brain_result = self._recover_character_card_slot_delta_brain_result(
                    request,
                    brain_result,
                    force_after_finalizer_failure=True,
                    recovery_reason="remote_final_prompt_anchor_view_contract_invalid",
                )
                if self._uses_character_card_slot_delta_recovery(recovered_brain_result):
                    return recovered_brain_result
                # Do not expose an upstream body or turn it into local text.
                # The activation boundary records the public-safe reason only.
                finalizer_failure_audit = self.llm_brain_adapter.provider_failure_audit(
                    failure,
                    stage="provider_prompt_finalize",
                )
                blocked_brain_result = brain_result.model_copy(
                    update={
                        "audit": {
                            **dict(brain_result.audit or {}),
                            **finalizer_failure_audit,
                        }
                    }
                )
                if isinstance(failure, BrainExecutionBudgetExceeded):
                    blocked_brain_result = brain_result.model_copy(
                        update={
                            "audit": {
                                **dict(blocked_brain_result.audit or {}),
                                "remote_provider_error_class": "execution_budget_exhausted",
                                "remote_brain_execution_budget": (
                                    self.llm_brain_adapter.execution_budget_receipt() or {
                                        "logical_budget_seconds": 0.0,
                                        "remaining_ms": 0,
                                        "state": "exhausted"
                                    }
                                ),
                            }
                        }
                    )
                elif isinstance(failure, BrainTransportTimeoutError):
                    blocked_brain_result = brain_result.model_copy(
                        update={
                            "audit": {
                                **dict(blocked_brain_result.audit or {}),
                                "remote_provider_error_class": "timeout",
                                "remote_brain_stage": getattr(failure, "stage", "provider_prompt_finalize"),
                                "remote_brain_transport_failure": failure.safe_metadata(),
                                "remote_brain_execution_budget": (
                                    self.llm_brain_adapter.execution_budget_receipt() or {}
                                ),
                            }
                        }
                    )
                raise self._remote_creative_brain_block(
                    (
                        "human_realism_semantic_preflight_missing"
                        if isinstance(failure, BrainSemanticPreflightMissing)
                        else "human_realism_natural_presence_decision_missing"
                        if isinstance(failure, BrainHumanNaturalnessDecisionMissing)
                        else "reference_channel_ownership_decision_missing"
                        if isinstance(failure, BrainReferenceChannelOwnershipDecisionMissing)
                        else "human_developmental_presence_decision_missing"
                        if isinstance(failure, BrainDevelopmentalPresenceDecisionMissing)
                        else "professional_anchor_view_decision_missing"
                        if isinstance(failure, BrainProfessionalAnchorViewDecisionMissing)
                        else "remote_creative_brain_prompt_signoff_invalid"
                        if isinstance(failure, BrainPromptContractInvalid)
                        else "remote_creative_brain_prompt_signoff_unavailable"
                    ),
                    blocked_brain_result,
                ) from failure
        final_stage = "provider_prompt_finalize"
        finalizer_stages = [final_stage]
        finalizer_transport_history: list[dict[str, Any]] = []
        if isinstance(audit.get("remote_brain_transport"), dict):
            finalizer_transport_history.append(dict(audit["remote_brain_transport"]))
        developmental_contract_present = bool(
            canonical_prompt_context.get("human_developmental_age_decision")
            or canonical_prompt_context.get("human_developmental_presence_decision")
        )
        if developmental_contract_present:
            # The initial finalizer already receives and validates the frozen
            # age/presence contracts, and its typed receipts are required by
            # ``finalize_canonical_provider_prompts`` above.  Asking it to
            # re-sign the prompt again serialized a third full remote call for
            # child, teen, and explicit age-transition work without adding
            # another authority boundary.  Keep historical re-sign records
            # readable, but new jobs use this one complete Brain sign-off.
            audit = {
                **audit,
                "human_developmental_age_signoff_mode": "combined_finalizer",
                "human_developmental_presence_signoff_mode": "combined_finalizer",
                "human_developmental_presence_resign_required": False,
                "human_developmental_presence_resign_completed": False,
            }
        anchor_decision = canonical_prompt_context.get("professional_anchor_view_decision")
        serial_capture_resign_required = bool(
            isinstance(anchor_decision, dict)
            and anchor_decision.get("contract_version")
            == "v3_professional_anchor_view_decision_v3"
            and anchor_decision.get("capture_continuity")
            == "preserve_approved_prior_capture"
            and anchor_decision.get("capture_scope") != "character_card_face_identity"
        )
        if serial_capture_resign_required:
            capture_context = self._human_naturalness_resigning_context(canonical_prompt_context)
            capture_resign_request = signing_request.model_copy(
                update={
                    "stage": "provider_prompt_professional_capture_resign",
                    "metadata": {
                        "canonical_prompt_context": capture_context,
                        "candidate_canonical_provider_prompts": [
                            item.model_dump(mode="json") for item in prompts
                        ],
                    },
                },
                deep=True,
            )
            try:
                prompts, capture_resign_audit = (
                    self.llm_brain_adapter.finalize_canonical_provider_prompts(
                        capture_resign_request
                    )
                )
            except Exception as exc:
                raise self._remote_creative_brain_block(
                    "professional_anchor_capture_resign_unavailable",
                    brain_result,
                ) from exc
            if isinstance(capture_resign_audit.get("remote_brain_transport"), dict):
                finalizer_transport_history.append(
                    dict(capture_resign_audit["remote_brain_transport"])
                )
            audit = {
                **audit,
                **capture_resign_audit,
                "professional_anchor_capture_resign_required": True,
                "professional_anchor_capture_resign_completed": True,
                "professional_anchor_capture_resign_mode": (
                    "bounded_remote_complete_prompt_recheck"
                ),
            }
            final_stage = "provider_prompt_professional_capture_resign"
            finalizer_stages.append(final_stage)
        if "human_realism" in plan.dependency_order:
            # Keep retry evidence in the same final sign-off context. The
            # Brain revises the whole direction when evidence exists, then
            # approves or rewrites its complete prompt under the same
            # naturalness contract. This is one remote decision, not a local
            # prompt patch and not a second serial creative pass.
            audit = {
                **audit,
                "human_realism_natural_presence_resigning_required": True,
                "human_realism_natural_presence_resigned": True,
                "human_realism_natural_presence_signoff_mode": "combined_finalizer",
                "human_realism_natural_presence_resigning_provider": audit.get(
                    "canonical_provider_prompt_provider"
                ),
                "human_realism_natural_presence_resigning_model": audit.get(
                    "canonical_provider_prompt_model"
                ),
            }
        if canonical_prompt_context.get("reference_channel_ownership_decision"):
            audit = {
                **audit,
                "reference_channel_ownership_resigned": True,
                "reference_channel_ownership_signoff_mode": "combined_finalizer",
            }
        if canonical_prompt_context.get("professional_anchor_view_decision"):
            audit = {
                **audit,
                "professional_anchor_view_resigned": True,
                "professional_anchor_view_signoff_mode": "combined_finalizer",
            }
        transport_history = list(brain_result.audit.get("remote_brain_transports") or [])
        if not transport_history and isinstance(brain_result.audit.get("remote_brain_transport"), dict):
            transport_history.append(dict(brain_result.audit["remote_brain_transport"]))
        transport_history.extend(finalizer_transport_history)
        audit["remote_brain_transports"] = transport_history
        audit["remote_brain_call_count"] = len(transport_history)
        execution_budget = self.llm_brain_adapter.execution_budget_receipt()
        if execution_budget is not None:
            audit["remote_brain_execution_budget"] = execution_budget
        return brain_result.model_copy(
            update={
                "canonical_provider_prompts": prompts,
                "audit": {
                    **dict(brain_result.audit or {}),
                    **audit,
                    "canonical_provider_prompt_stage": final_stage,
                    "canonical_provider_prompt_stages": finalizer_stages,
                    "canonical_provider_prompt_binding": {
                        "activation_plan_id": plan.plan_id,
                        "execution_envelope_id": envelope.envelope_id,
                        "constraint_ledger_id": ledger.ledger_id,
                    },
                },
            }
        )

    @staticmethod
    def _human_naturalness_resigning_context(canonical_prompt_context: dict[str, Any]) -> dict[str, Any]:
        """Remove review codes before an independent human-presence re-sign.

        The first finalizer owns any normalized pixel-evidence revision.  The
        independent pass receives that completed candidate plus the frozen
        semantics, not a reviewer checklist that could turn into another
        brittle prompt-composition path.
        """

        context = dict(canonical_prompt_context)
        context.pop("retry_evidence", None)
        context["human_naturalness_decision"] = {
            "required": True,
            "contract_version": "v3_human_naturalness_decision_v1",
            "owner": "remote_v3_llm_brain",
            # This is an integrity reference to the already-frozen context,
            # not a second mutable plan or a creative-language instruction.
            "frozen_binding": dict(context.get("frozen_binding") or {}),
        }
        return context

    @staticmethod
    def _active_semantic_capability_contracts(
        plan: CapabilityActivationPlan,
        ledger: ResolvedConstraintLedger,
    ) -> list[dict[str, Any]]:
        """Read only validated shared semantic obligations for Brain sign-off.

        This is intentionally a narrow bridge between frozen executor facts
        and the remote finalizer.  It neither reconstructs a prompt nor lets a
        mutable Visual Capability Cluster payload become a Provider fallback.
        """

        if "human_realism" not in plan.dependency_order:
            return []
        projection = dict(ledger.provider_projection or {})
        capabilities = projection.get("capability_projection")
        guidance = capabilities.get("human_photorealism_guidance") if isinstance(capabilities, dict) else None
        contract = guidance.get("semantic_contract") if isinstance(guidance, dict) else None
        if not isinstance(contract, dict):
            raise CapabilityActivationError("human_realism_semantic_contract_missing")

        allowed_keys = {
            "contract_version",
            "capability_id",
            "rendering_goal",
            "quality_axes",
            "identity_age_fidelity",
            "developmental_age_coherence_requirement",
            "developmental_presence_requirement",
            "physical_coherence",
            "reference_boundary",
            "ordinary_age_appropriate_context",
            "natural_presence_priority",
            "aesthetic_boundary",
            "expression_ownership_requirement",
            "expression_resolution_requirement",
            "personhood_requirement",
            "complexion_rendering_requirement",
            "photographic_material_requirement",
            "creative_direction_owner",
            "provider_prompt_owner",
        }
        if set(contract) != allowed_keys:
            raise CapabilityActivationError("human_realism_semantic_contract_missing")
        quality_axes = contract.get("quality_axes")
        if (
            not isinstance(quality_axes, list)
            or not quality_axes
            or any(str(item) not in HUMAN_REALISM_REVIEW_DIMENSIONS for item in quality_axes)
        ):
            raise CapabilityActivationError("human_realism_semantic_contract_missing")
        if (
            contract.get("contract_version") != "v3_human_realism_semantic_v8"
            or contract.get("capability_id") != "human_realism"
            or contract.get("rendering_goal") not in {"photographic_real_person", "photographic_human_detail"}
            or contract.get("identity_age_fidelity") not in {"explicit_or_reference_backed", "not_applicable"}
            or contract.get("developmental_age_coherence_requirement")
            not in {"whole_person_requested_stage", "not_applicable"}
            or contract.get("developmental_presence_requirement")
            not in {
                "integrated_stage_coherent_face_attention_and_affect",
                "not_applicable",
            }
            or contract.get("physical_coherence") != "required"
            or contract.get("reference_boundary") != "resolved_channels_only"
            or not isinstance(contract.get("ordinary_age_appropriate_context"), bool)
            or contract.get("natural_presence_priority") != "individual_human_presence"
            or contract.get("aesthetic_boundary") != "preserve_user_style_without_generic_beauty_substitution"
            or contract.get("expression_ownership_requirement")
            not in {"situation_owned_unless_explicit_user_direction", "not_applicable"}
            or contract.get("expression_resolution_requirement")
            not in {"individual_situation_not_stock_geometry", "not_applicable"}
            or contract.get("personhood_requirement")
            not in {"individual_noninterchangeable_presence", "not_applicable"}
            or contract.get("complexion_rendering_requirement")
            != "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
            or contract.get("photographic_material_requirement") != "camera_observed_human_materiality"
            or contract.get("creative_direction_owner") != "remote_v3_llm_brain"
            or contract.get("provider_prompt_owner") != "remote_v3_llm_brain"
        ):
            raise CapabilityActivationError("human_realism_semantic_contract_missing")
        return [dict(contract)]

    @staticmethod
    def _provider_admission_decision_from_semantic_contracts(
        semantic_contracts: list[dict[str, Any]],
        *,
        frozen_binding: dict[str, Any],
    ) -> dict[str, Any]:
        """Require Brain provider-admission only from shared safety evidence.

        The runtime does not infer age, apparel, marketplace, or scene safety
        from prompt words here.  It only projects an existing validated Human
        Realism semantic contract into the already-owned Doc185 admission
        receipt requirement.
        """

        requires_admission = any(
            isinstance(contract, dict)
            and contract.get("capability_id") == "human_realism"
            and contract.get("ordinary_age_appropriate_context") is True
            for contract in semantic_contracts
        )
        if not requires_admission:
            return {}
        return {
            "required": True,
            "contract_version": "v3_provider_admission_decision_v1",
            "provider_admission_status": "admitted",
            "prompt_language_mode": "concise_positive_renderer_direction",
            "safety_sensitive_prompt_normalized": "applied",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": dict(frozen_binding),
        }

    @staticmethod
    def _canonical_prompt_context(
        request: ScenarioRuntimeRequest,
        plan: CapabilityActivationPlan,
        envelope: CapabilityExecutionEnvelope,
        ledger: ResolvedConstraintLedger,
        brain_result: BrainRunResult,
    ) -> dict[str, Any]:
        """Project frozen facts and the Brain's own draft for final sign-off.

        The draft directions are remote-Brain output, not local planner text.
        Supplying them lets the sign-off stage validate and revise the same
        semantic direction instead of reconstructing a second creative brief
        from deterministic runtime metadata.
        """

        projection = dict(ledger.provider_projection or {})
        semantic_contracts = ScenarioRuntime._active_semantic_capability_contracts(plan, ledger)
        age_resolution = ScenarioRuntime._human_realism_age_resolution(projection)
        retry_provenance = request.metadata.get("resolved_retry_provenance")
        retry_evidence = {
            "active": bool(request.metadata.get("visual_auto_retry_active")),
            "issue_codes": ScenarioRuntime._normalized_retry_evidence_issue_codes(request, plan),
        }
        if isinstance(retry_provenance, dict):
            observed = retry_provenance.get("observed_review_evidence")
            if isinstance(observed, list):
                bounded_observed = [
                    " ".join(str(item or "").replace("\x00", " ").split())[:240].strip()
                    for item in observed
                    if str(item or "").strip()
                ]
                bounded_observed = list(dict.fromkeys(item for item in bounded_observed if item))[:8]
                if bounded_observed:
                    retry_evidence["observed_review_evidence"] = bounded_observed
        references = []
        for asset in request.uploaded_assets:
            role = asset.role.value if hasattr(asset.role, "value") else asset.role
            binding = {
                "asset_id": asset.asset_id,
                "role": str(role or "reference"),
                "declared_provider_input": bool(asset.metadata.get("provider_input_required")),
            }
            if request.metadata.get("professional_anchor_pack_preparation") is True:
                lineage_role = str(asset.metadata.get("professional_anchor_lineage_role") or "").strip()
                if lineage_role not in {"identity_root", "prior_view_winner"}:
                    lineage_role = (
                        "prior_view_winner"
                        if asset.metadata.get("selected_generated_output") is True
                        or str(asset.metadata.get("source_type") or "") == "selected_output"
                        else "identity_root"
                    )
                binding["professional_anchor_lineage_role"] = lineage_role
            references.append(binding)
        context = {
            "protected_user_intent": projection.get("protected_user_intent"),
            "rendering_semantics": projection.get("rendering_semantics"),
            "requested_image_size": projection.get("requested_image_size"),
            "visible_text_policy": projection.get("visible_text_policy"),
            "deliverables": [
                {
                    "output_index": item.get("output_index"),
                    "image_intent": item.get("image_intent"),
                    "factual_acceptance": item.get("factual_acceptance", []),
                    "metadata": {
                        key: value
                        for key, value in dict(item.get("metadata") or {}).items()
                        if key
                        in {
                            "product_truth_selection_role",
                            "selected_product_truth_asset_ids",
                            "admitted_product_truth_asset_ids",
                            "product_truth_selection_source",
                            "product_truth_pool_asset_ids",
                            "brain_evidence_dimensions",
                            "professional_ecommerce_pose_role",
                            "professional_ecommerce_pose_acceptance",
                            "professional_ecommerce_pose_contract_source",
                            "professional_body_proportion_requirement",
                            "professional_body_view_kind",
                            "professional_body_proportion_contract_source",
                            "specialized_role_key",
                        }
                    },
                }
                for item in projection.get("deliverables", [])
                if isinstance(item, dict)
            ],
            "brain_draft_directions": [
                {"output_index": index, "direction": str(direction).strip()}
                for index, direction in enumerate(brain_result.image_set_plan.shot_plan, start=1)
                if str(direction).strip()
            ],
            "product_truth": projection.get("product_truth", {}),
            "apparel_construction": projection.get("apparel_construction", {}),
            "active_shared_capability_ids": list(plan.dependency_order),
            "active_semantic_capability_contracts": semantic_contracts,
            "final_prompt_semantic_preflight": {
                "required": bool(semantic_contracts),
                "scope": "whole_image_human_photographic_plausibility",
                "owner": "remote_v3_llm_brain",
                "revision_mode": "rewrite_complete_canonical_prompt",
            },
            "reference_bindings": references,
            "retry_evidence": retry_evidence,
            # These are opaque integrity bindings for the runtime, not
            # creative vocabulary for the final prompt.
            "frozen_binding": {
                "envelope_id": envelope.envelope_id,
                "ledger_id": ledger.ledger_id,
                "execution_fingerprint": envelope.execution_fingerprint,
            },
        }
        raw_ecommerce_context = request.metadata.get("ecommerce_creative_context")
        if request.metadata.get("ecommerce_creative_context_server_owned") is True:
            try:
                ecommerce_context = EcommerceCreativeContext.model_validate(raw_ecommerce_context)
            except ValueError as exc:
                raise CapabilityActivationError("ecommerce_creative_context_invalid") from exc
            # The finalizer receives the same validated server facts that
            # informed the initial Brain pass. This preserves typed
            # E-Commerce renderer boundaries through the final sign-off.
            context["ecommerce_creative_context"] = ecommerce_context.model_dump(mode="json")
        reference_ownership = ScenarioRuntime._reference_channel_ownership_decision(
            projection,
            frozen_binding=dict(context["frozen_binding"]),
        )
        if reference_ownership:
            context["reference_channel_ownership_decision"] = reference_ownership
        provider_admission_decision = ScenarioRuntime._provider_admission_decision_from_semantic_contracts(
            semantic_contracts,
            frozen_binding=dict(context.get("frozen_binding") or {}),
        )
        if provider_admission_decision:
            context["provider_admission_decision"] = provider_admission_decision
        if age_resolution:
            context["human_realism_age_resolution"] = age_resolution
            if age_resolution.get("age_fidelity") == "follow_explicit_prompt":
                context["human_developmental_age_decision"] = {
                    "required": True,
                    "contract_version": "v3_human_developmental_age_decision_v2",
                    "age_fidelity": age_resolution["age_fidelity"],
                    "source_age_inheritance": age_resolution["source_age_inheritance"],
                    "developmental_age_coherence": age_resolution["developmental_age_coherence"],
                    "developmental_presence": age_resolution["developmental_presence"],
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": dict(context["frozen_binding"]),
                }
        if ScenarioRuntime._is_professional_mode_selected(request):
            # Keep the anchor-pack quality objective typed and Brain-owned.
            # Do not build a local prompt recipe here: the Remote Brain must
            # reconcile this contract with the selected view and user intent.
            planning_metadata = request.metadata.get("professional_planning_metadata")
            planning_metadata = planning_metadata if isinstance(planning_metadata, dict) else None
            character_card_stage = ScenarioRuntime._professional_character_card_stage(
                request.metadata if isinstance(request.metadata, dict) else {},
                planning_metadata,
            )
            body_silhouette_stage = character_card_stage == "body_silhouette"
            if isinstance(planning_metadata, dict):
                if body_silhouette_stage:
                    body_contract = ScenarioRuntime._professional_body_silhouette_source_contract(
                        planning_metadata
                    )
                    if isinstance(body_contract, dict):
                        context["professional_body_silhouette_source_contract"] = body_contract
                else:
                    quality_contract = planning_metadata.get("professional_face_identity_quality_contract")
                    if isinstance(quality_contract, dict):
                        context["professional_face_identity_quality_contract"] = dict(quality_contract)
                slot_delta_contract = planning_metadata.get("reference_led_slot_delta_contract")
                if isinstance(slot_delta_contract, dict):
                    context["reference_led_slot_delta_decision"] = {
                        **dict(slot_delta_contract),
                        "frozen_binding": dict(context.get("frozen_binding") or {}),
                    }
            if body_silhouette_stage:
                if not isinstance(context.get("professional_body_silhouette_source_contract"), dict):
                    raise CapabilityActivationError(
                        "professional_body_silhouette_source_contract_missing"
                    )
            elif not isinstance(context.get("professional_face_identity_quality_contract"), dict):
                raise CapabilityActivationError("professional_face_identity_quality_contract_missing")
            if request.metadata.get("professional_anchor_pack_preparation") is True:
                target_view_role = str(
                    (planning_metadata or {}).get("professional_reference_stage")
                    if isinstance(planning_metadata, dict)
                    else ""
                ).strip()
                capture_scope = str(
                    (planning_metadata or {}).get("professional_anchor_capture_scope")
                    if isinstance(planning_metadata, dict)
                    else "anchor_pack"
                ).strip() or "anchor_pack"
                if target_view_role not in {
                    "standard_front",
                    "left_front_25",
                    "three_quarter",
                    "profile",
                    "right_front_25",
                    "reverse_three_quarter",
                    "rear_head",
                }:
                    raise CapabilityActivationError("professional_anchor_view_contract_missing")
                context["professional_anchor_view_decision"] = {
                    "required": True,
                    "contract_version": "v3_professional_anchor_view_decision_v3",
                    "owner": "remote_v3_llm_brain",
                    "target_view_role": target_view_role,
                    "capture_presentation": "neutral_identity_evidence_capture",
                    "capture_continuity": (
                        "establish_neutral_capture"
                        if target_view_role == "standard_front"
                        else "preserve_approved_prior_capture"
                    ),
                    "frozen_binding": dict(context.get("frozen_binding") or {}),
                }
                if capture_scope != "anchor_pack":
                    context["professional_anchor_view_decision"]["capture_scope"] = capture_scope
                if capture_scope == "character_card_face_identity":
                    quality_contract = (
                        planning_metadata.get("professional_face_identity_quality_contract")
                        if isinstance(planning_metadata, dict)
                        else {}
                    )
                    quality_contract = quality_contract if isinstance(quality_contract, dict) else {}
                    framing_contract = quality_contract.get("face_identity_framing_contract")
                    framing_contract = framing_contract if isinstance(framing_contract, dict) else {}
                    if (
                        target_view_role == "standard_front"
                        and framing_contract.get("required") is True
                    ):
                        context["professional_anchor_view_decision"].update(
                            {
                                "framing_standard": framing_contract.get("framing_standard"),
                                "crop_policy": framing_contract.get("crop_policy"),
                                "torso_scope": framing_contract.get("torso_scope"),
                            }
                        )
                    evidence_capture_contract = quality_contract.get(
                        "face_card_evidence_capture_contract"
                    )
                    evidence_capture_contract = (
                        evidence_capture_contract
                        if isinstance(evidence_capture_contract, dict)
                        else {}
                    )
                    if (
                        target_view_role == "standard_front"
                        and evidence_capture_contract.get("required") is True
                    ):
                        context["professional_anchor_view_decision"].update(
                            {
                                "aspect_ratio_standard": evidence_capture_contract.get(
                                    "aspect_ratio_standard"
                                )
                            }
                        )
                    front_pose_contract = quality_contract.get("front_pose_normalization_contract")
                    front_pose_contract = front_pose_contract if isinstance(front_pose_contract, dict) else {}
                    if target_view_role == "standard_front" and front_pose_contract.get("required") is True:
                        context["professional_anchor_view_decision"].update(
                            {
                                "source_viewpoint_inheritance": front_pose_contract.get(
                                    "source_viewpoint_inheritance"
                                ),
                                "front_pose_normalization": front_pose_contract.get(
                                    "front_pose_normalization"
                                ),
                                "face_axis_alignment": front_pose_contract.get(
                                    "face_axis_alignment"
                                ),
                            }
                        )
                    # Face Identity references can describe an age-sensitive
                    # person. The Brain must explicitly normalize the final
                    # renderer direction before either Provider or MCP sees
                    # it; this is a typed admission contract, not a local
                    # prompt rewrite or a child-specific recipe.
                    context["provider_admission_decision"] = {
                        "required": True,
                        "contract_version": "v3_provider_admission_decision_v1",
                        "provider_admission_status": "admitted",
                        "prompt_language_mode": "concise_positive_renderer_direction",
                        "safety_sensitive_prompt_normalized": "applied",
                        "owner": "remote_v3_llm_brain",
                        "frozen_binding": dict(context.get("frozen_binding") or {}),
                    }
            elif request.metadata.get("professional_character_card_preparation") is True:
                if not isinstance(context.get("reference_led_slot_delta_decision"), dict):
                    raise CapabilityActivationError("reference_led_slot_delta_contract_missing")
                stage = str(request.metadata.get("professional_character_card_stage") or "").strip()
                slot_key = str(request.metadata.get("professional_character_card_slot") or "").strip()
                if stage and slot_key:
                    context["character_card_slot_delta_target"] = {
                        "stage": stage,
                        "slot_key": slot_key,
                        **(
                            {"expression": slot_key.split(".", 1)[1]}
                            if stage == "expression_set" and slot_key.startswith("expression.")
                            else {}
                        ),
                        **(
                            {"body_slot": slot_key.split(".", 1)[1]}
                            if stage == "body_silhouette" and slot_key.startswith("body.")
                            else {}
                        ),
                    }
                    if stage == "expression_set":
                        context["character_card_slot_framing_contract"] = {
                            "baseline": "active_face_front_winner",
                            "format": "1024x1536_vertical_2_3",
                            "background": "clean_white_studio",
                            "camera_distance": "inherit_face_front_modeling_card",
                            "crop": "head_neck_upper_shoulders",
                            "subject_scale": "inherit_face_front_modeling_card",
                            "eye_line_centering": "inherit_face_front_modeling_card",
                            "lighting_white_balance": "inherit_face_front_modeling_card",
                            "allowed_delta": "facial_affect_and_small_natural_head_shoulder_energy",
                        }
                    if stage == "expression_set" and slot_key == "expression.laugh":
                        context["character_card_laugh_intent_contract"] = {
                            **laugh_expression_intent_contract(),
                            "evidence_required": [
                                "mouth_eye_coherence",
                                "periocular_affect",
                                "cheek_jaw_coupling",
                                "jaw_relaxation",
                                "arousal_intensity_coherence",
                                "spontaneity_asymmetry",
                                "expression_age_coherence",
                                "expression_identity_preservation",
                            ],
                        }
                context["provider_admission_decision"] = {
                    "required": True,
                    "contract_version": "v3_provider_admission_decision_v1",
                    "provider_admission_status": "admitted",
                    "prompt_language_mode": "concise_positive_renderer_direction",
                    "safety_sensitive_prompt_normalized": "applied",
                    "owner": "remote_v3_llm_brain",
                    "frozen_binding": dict(context.get("frozen_binding") or {}),
                }
        return context

    @staticmethod
    def _reference_channel_ownership_decision(
        provider_projection: dict[str, Any],
        *,
        frozen_binding: dict[str, Any],
    ) -> dict[str, Any]:
        """Project Doc93 ownership as a typed Brain decision boundary.

        The package contains legacy renderer rules, but those strings are not
        forwarded.  The finalizer receives only channel ownership facts and
        must author or rewrite one complete prompt itself.
        """

        capabilities = provider_projection.get("capability_projection")
        package = capabilities.get("resolved_reference_policy_package") if isinstance(capabilities, dict) else None
        if not isinstance(package, dict) or package.get("applies") is not True:
            return {}
        owners = package.get("effective_channel_owners")
        if not isinstance(owners, dict) or not owners:
            raise CapabilityActivationError("reference_channel_ownership_contract_missing")
        normalized_owners = {
            str(channel): str(owner)
            for channel, owner in owners.items()
            if str(channel).strip() and str(owner).strip()
        }
        if not normalized_owners:
            raise CapabilityActivationError("reference_channel_ownership_contract_missing")
        reference_owned = sorted(
            channel
            for channel, owner in normalized_owners.items()
            if owner.startswith("reference:")
        )
        current_request_owned = sorted(
            channel
            for channel, owner in normalized_owners.items()
            if owner in {"current_prompt", "current_prompt_or_defaults"}
        )
        explicit_locks: list[str] = []
        blocked_inheritance: list[str] = []
        for policy in package.get("policies", []):
            if not isinstance(policy, dict):
                continue
            explicit_locks.extend(
                str(item).strip()
                for item in policy.get("explicit_user_locks", [])
                if str(item).strip()
            )
            blocked_inheritance.extend(
                str(item).strip()
                for item in policy.get("blocked_inheritance_channels", [])
                if str(item).strip()
            )
        return {
            "required": True,
            "contract_version": "v3_reference_channel_ownership_decision_v1",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": dict(frozen_binding),
            "reference_owned_channels": reference_owned,
            "current_request_owned_channels": current_request_owned,
            "explicit_user_locked_channels": list(dict.fromkeys(explicit_locks)),
            "blocked_reference_inheritance_channels": list(dict.fromkeys(blocked_inheritance)),
            "resolution_mode": "rewrite_complete_canonical_prompt",
        }

    @staticmethod
    def _human_realism_age_resolution(provider_projection: dict[str, Any]) -> dict[str, Any]:
        """Project the existing age policy as Brain-owned semantic context.

        The runtime does not decide whether a request is an age transition. It
        only carries the typed Human Realism policy into the canonical Brain
        sign-off context. The Brain sees the user request, reference channels,
        and this boundary together, then authors the complete prompt.
        """

        capabilities = provider_projection.get("capability_projection")
        guidance = capabilities.get("human_photorealism_guidance") if isinstance(capabilities, dict) else None
        if not isinstance(guidance, dict):
            return {}
        metadata = guidance.get("metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        plugin = metadata.get("human_realism_plugin")
        plugin = plugin if isinstance(plugin, dict) else {}
        profile = plugin.get("universal_rendering_profile")
        if not isinstance(profile, dict):
            profile = metadata.get("universal_rendering_profile")
        age_fidelity = str(profile.get("age_fidelity") or "").strip().lower() if isinstance(profile, dict) else ""
        if age_fidelity not in {"preserve_reference", "follow_explicit_prompt", "neutral"}:
            return {}
        return {
            "age_fidelity": age_fidelity,
            "identity_continuity": "identity_critical_feature_relationships",
            "source_age_inheritance": (
                "not_automatic_when_current_prompt_assigns_age"
                if age_fidelity == "follow_explicit_prompt"
                else "preserve_for_same_age_continuation"
            ),
            "developmental_age_coherence": "whole_person_requested_stage",
            "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
            "review_owner": "v3_shared_vision",
            "decision_owner": "remote_v3_llm_brain",
            "creative_prompt_owner": "remote_v3_llm_brain",
        }

    @staticmethod
    def _normalized_retry_evidence_issue_codes(
        request: ScenarioRuntimeRequest,
        plan: CapabilityActivationPlan,
    ) -> list[str]:
        """Normalize Human Realism review evidence before the next Brain pass.

        This is data normalization only.  It never creates a repair sentence
        or changes other frozen capability evidence.  Historical fine-grained
        Human Realism labels collapse to the shared dimensions before
        they are presented to the Brain.
        """

        raw_codes = [
            str(item).strip()
            for item in request.metadata.get("visual_retry_reason_codes", [])
            if str(item).strip()
        ]
        if "human_realism" not in plan.dependency_order:
            return list(dict.fromkeys(raw_codes))
        return list(dict.fromkeys(normalize_human_realism_issue_code(item) for item in raw_codes))

    def _require_brain_signed_provider_prompts(
        self,
        request: ScenarioRuntimeRequest,
        policy: TemplateCapabilityPolicy,
        brain_result: BrainRunResult,
        plan: CapabilityActivationPlan,
    ) -> None:
        if not (policy.requires_remote_creative_brain or self._requires_remote_creative_brain_for_real_images(request)):
            return
        expected = self._requested_image_count_for_brain(request)
        prompts = list(brain_result.canonical_provider_prompts or [])
        prompt_set_received = bool(brain_result.audit.get("remote_canonical_provider_prompts_received")) or (
            self._uses_character_card_slot_delta_recovery(brain_result)
        )
        if (
            [item.output_index for item in prompts] != list(range(1, expected + 1))
            or not prompt_set_received
        ):
            raise self._remote_creative_brain_block(
                "remote_creative_brain_prompt_signoff_invalid",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )
        if "human_realism" in plan.dependency_order and not bool(
            brain_result.audit.get("human_realism_semantic_preflight_signed")
        ):
            raise self._remote_creative_brain_block(
                "human_realism_semantic_preflight_missing",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )
        if (
            "human_realism" in plan.dependency_order
            and not bool(brain_result.audit.get("frozen_execution_reuse"))
            and not bool(brain_result.audit.get("human_realism_natural_presence_resigned"))
        ):
            raise self._remote_creative_brain_block(
                "human_realism_natural_presence_resigning_missing",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )
        if (
            "human_realism" in plan.dependency_order
            and not bool(brain_result.audit.get("frozen_execution_reuse"))
            and not bool(brain_result.audit.get("human_realism_natural_presence_decision_signed"))
        ):
            raise self._remote_creative_brain_block(
                "human_realism_natural_presence_decision_missing",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )
        if (
            bool(brain_result.audit.get("reference_channel_ownership_decision_required"))
            and not bool(brain_result.audit.get("frozen_execution_reuse"))
            and not bool(brain_result.audit.get("reference_channel_ownership_decision_signed"))
        ):
            raise self._remote_creative_brain_block(
                "reference_channel_ownership_decision_missing",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )
        if (
            bool(brain_result.audit.get("professional_anchor_view_decision_required"))
            and not bool(brain_result.audit.get("frozen_execution_reuse"))
            and not bool(brain_result.audit.get("professional_anchor_view_decision_signed"))
        ):
            raise self._remote_creative_brain_block(
                "professional_anchor_view_decision_missing",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )
        if (
            bool(brain_result.audit.get("provider_admission_decision_required"))
            and not bool(brain_result.audit.get("frozen_execution_reuse"))
            and not bool(brain_result.audit.get("provider_admission_decision_signed"))
        ):
            raise self._remote_creative_brain_block(
                "provider_admission_decision_missing",
                brain_result,
                expected_image_count=expected,
                actual_canonical_prompt_count=len(prompts),
            )

    @staticmethod
    def _requires_remote_creative_brain_for_real_images(request: ScenarioRuntimeRequest) -> bool:
        """Keep an explicitly real image job LLM-first without changing draft mode.

        ``require_real_images`` / ``real_image_generation`` are persisted
        production-quality assertions. They are narrower than selecting the
        General template: ordinary General mock or exploratory jobs retain the
        documented fallback, while a real Provider job cannot claim a
        trustworthy creative plan after the remote Brain failed.
        """

        metadata = request.metadata if isinstance(request.metadata, dict) else {}
        return bool(
            metadata.get("require_real_images")
            or metadata.get("real_image_generation")
            or ScenarioRuntime._is_professional_mode_selected(request)
            or ScenarioRuntime._has_visual_asset_library_binding(request)
        )

    @staticmethod
    def _is_professional_mode_selected(request: ScenarioRuntimeRequest) -> bool:
        """Recognize the persisted server-owned boolean and public string forms.

        Product API stores the normalized Professional selection as ``True``
        in internal metadata, while direct runtime callers may use the public
        string ``"professional"``.  Treating only the string as active would
        silently drop the anchor-pack quality contract before the Brain
        finalizer, which is exactly the failure mode M5 exposed.
        """

        value = request.metadata.get("professional_mode")
        if value is True:
            return True
        return str(value or "").strip().lower() == "professional"

    @staticmethod
    def _has_visual_asset_library_binding(request: ScenarioRuntimeRequest) -> bool:
        """Return whether the server has frozen an explicit library binding."""

        return isinstance(request.metadata.get("visual_asset_library_binding"), dict)

    @staticmethod
    def _remote_creative_brain_block(
        reason_code: str,
        brain_result: BrainRunResult,
        **details: Any,
    ) -> CapabilityActivationError:
        """Attach safe, actionable evidence without exposing provider internals.

        Specialized templates must fail closed when their remote creative
        contract is absent or invalid.  The blocked job still needs enough
        provenance for an operator to distinguish configuration, transport,
        and contract failures; raw prompts, endpoint details, credentials,
        and provider-native errors remain private.
        """

        audit = dict(brain_result.audit or {})
        if audit.get("remote_provider_error"):
            outcome_class = "remote_provider_error"
        elif audit.get("remote_provider_available") is False:
            outcome_class = "remote_provider_unavailable"
        elif reason_code in {
            "remote_creative_brain_image_set_plan_invalid",
            "remote_creative_brain_prompt_signoff_invalid",
        }:
            outcome_class = "remote_contract_invalid"
        elif reason_code == "remote_creative_brain_output_count_mismatch":
            outcome_class = "remote_output_count_mismatch"
        elif reason_code in {
            "remote_creative_brain_prompt_signoff_unavailable",
            "human_realism_semantic_preflight_missing",
            "human_realism_natural_presence_decision_missing",
            "human_realism_natural_presence_resigning_missing",
            "reference_channel_ownership_decision_missing",
            "reference_channel_ownership_contract_missing",
            "professional_face_identity_quality_contract_missing",
            "professional_body_silhouette_source_contract_missing",
            "professional_anchor_view_contract_missing",
            "professional_anchor_view_decision_missing",
            "provider_admission_decision_missing",
        }:
            outcome_class = "remote_prompt_signoff_unavailable"
        elif brain_result.skipped:
            outcome_class = "remote_brain_skipped"
        else:
            outcome_class = "remote_creative_brain_required"

        rejected_sections = _safe_remote_contract_rejected_sections(
            details.get("rejected_sections")
            or audit.get("remote_contract_rejected_sections")
            or audit.get("remote_semantic_contract_recovery_final_rejected_sections")
            or audit.get("remote_semantic_contract_recovery_initial_rejected_sections")
            or []
        )

        safe_outcome = {
            "schema_version": "v3_remote_creative_brain_outcome_v1",
            "state": "blocked",
            "reason_code": reason_code,
            "outcome_class": outcome_class,
            "llm_used": bool(brain_result.llm_used),
            "fallback_used": bool(brain_result.fallback_used),
            "remote_provider_available": audit.get("remote_provider_available"),
            "remote_contract_rejected_sections": rejected_sections,
            **(
                {"remote_brain_request_started": audit["remote_brain_request_started"]}
                if isinstance(audit.get("remote_brain_request_started"), bool)
                else {}
            ),
            **(
                {
                    "remote_brain_finalizer_lifecycle": safe_remote_brain_finalizer_lifecycle(
                        audit["remote_brain_finalizer_lifecycle"]
                    )
                }
                if safe_remote_brain_finalizer_lifecycle(
                    audit.get("remote_brain_finalizer_lifecycle")
                )
                else {}
            ),
            **(
                {"remote_error_class": str(audit["remote_provider_error_class"])}
                if audit.get("remote_provider_error_class")
                else {}
            ),
            **(
                {"remote_brain_stage": _safe_remote_brain_stage(audit["remote_brain_stage"])}
                if _safe_remote_brain_stage(audit.get("remote_brain_stage"))
                else {}
            ),
            **(
                {
                    "remote_brain_transport_failure": _safe_remote_brain_transport_failure(
                        audit["remote_brain_transport_failure"]
                    )
                }
                if isinstance(audit.get("remote_brain_transport_failure"), dict)
                and _safe_remote_brain_transport_failure(audit["remote_brain_transport_failure"])
                else {}
            ),
            **(
                {
                    "remote_brain_serialization_failure": _safe_remote_brain_serialization_failure(
                        audit["remote_brain_serialization_failure"]
                    )
                }
                if _safe_remote_brain_serialization_failure(
                    audit.get("remote_brain_serialization_failure")
                )
                else {}
            ),
            **(
                {
                    "remote_brain_execution_budget": _safe_remote_brain_execution_budget(
                        audit["remote_brain_execution_budget"]
                    )
                }
                if _safe_remote_brain_execution_budget(
                    audit.get("remote_brain_execution_budget")
                )
                else {}
            ),
            **(
                {"remote_http_status_code": int(audit["remote_provider_http_status_code"])}
                if isinstance(audit.get("remote_provider_http_status_code"), int)
                and 100 <= int(audit["remote_provider_http_status_code"]) <= 599
                else {}
            ),
            **(
                {"remote_provider_transport_kind": _safe_remote_provider_transport_kind(
                    audit["remote_provider_transport_kind"]
                )}
                if _safe_remote_provider_transport_kind(audit.get("remote_provider_transport_kind"))
                else {}
            ),
            **(
                {
                    "remote_image_set_cardinality_audit": _safe_remote_image_set_cardinality_audit(
                        audit["remote_image_set_cardinality_audit"]
                    )
                }
                if _safe_remote_image_set_cardinality_audit(
                    audit.get("remote_image_set_cardinality_audit")
                )
                else {}
            ),
            **(
                {
                    "remote_image_set_validation_audit": _safe_remote_image_set_validation_audit(
                        audit["remote_image_set_validation_audit"]
                    )
                }
                if _safe_remote_image_set_validation_audit(
                    audit.get("remote_image_set_validation_audit")
                )
                else {}
            ),
            **(
                {
                    "execution_budget": _safe_remote_brain_execution_budget(
                        audit["remote_brain_execution_budget"]
                    )
                }
                if _safe_remote_brain_execution_budget(
                    audit.get("remote_brain_execution_budget")
                )
                else {}
            ),
            **{
                key: value
                for key, value in details.items()
                if key
                in {
                    "expected_image_count",
                    "actual_image_count",
                    "actual_direction_count",
                }
            },
        }
        error = CapabilityActivationError(reason_code)
        setattr(error, "remote_creative_brain_outcome", safe_outcome)
        return error

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

    @staticmethod
    def _canonical_brain_image_size(value: object) -> str | None:
        normalized = " ".join(str(value or "").strip().lower().split()).replace("×", "x")
        return _BRAIN_IMAGE_SIZE_ALIASES.get(normalized)

    @staticmethod
    def _canonical_brain_aspect_ratio(value: object) -> tuple[str, str] | None:
        normalized = " ".join(str(value or "").strip().lower().split()).replace("：", ":")
        size = _BRAIN_ASPECT_RATIO_ALIASES.get(normalized)
        return (normalized, size) if size else None

    def _apply_brain_image_size_precedence(
        self,
        request: ScenarioRuntimeRequest,
        normalized_intent: NormalizedV3JobIntent,
        brain_result: BrainRunResult,
    ) -> NormalizedV3JobIntent:
        """Let the Brain resolve explicit user canvas intent before UI fallback."""

        brain_plan = brain_result.image_set_plan
        brain_size = self._canonical_brain_image_size(getattr(brain_plan, "size", None))
        ratio_resolution = self._canonical_brain_aspect_ratio(getattr(brain_plan, "aspect_ratio", None))
        # The Brain may echo the browser canvas while also resolving an
        # explicit ratio from the user's prompt.  The ratio is the stronger
        # user-owned signal; the browser value is only a fallback.
        if ratio_resolution is not None:
            _, brain_size = ratio_resolution
        if not brain_size:
            return normalized_intent
        if brain_size == normalized_intent.effective_image_size:
            if ratio_resolution is not None:
                request.metadata["requested_image_aspect_ratio"] = ratio_resolution[0]
                request.metadata["requested_image_aspect_ratio_source"] = "remote_brain_user_intent"
            return normalized_intent
        updated = normalized_intent.model_copy(
            update={
                "intent_id": stable_id(
                    "normalized_v3_job_intent",
                    normalized_intent.template_id,
                    normalized_intent.scenario_id,
                    normalized_intent.protected_user_intent,
                    normalized_intent.requested_image_count,
                    brain_size,
                    normalized_intent.declared_image_count_limit,
                    normalized_intent.text_policy,
                    normalized_intent.visible_text_policy,
                ),
                "requested_image_size": brain_size,
                "effective_image_size": brain_size,
                "provenance": [
                    *list(normalized_intent.provenance),
                    {
                        "source": "remote_brain_image_set_plan",
                        "field": "size",
                        "resolved_value": brain_size,
                        "precedence": "explicit_user_prompt_over_web_selection",
                        "web_selected_image_size": request.metadata.get("requested_image_size"),
                    },
                ],
            }
        )
        request.metadata = {
            **dict(request.metadata or {}),
            "requested_image_size": brain_size,
            "requested_image_size_source": "remote_brain_user_intent",
            "web_selected_image_size": request.metadata.get("requested_image_size"),
            "normalized_v3_job_intent": updated.model_dump(mode="json"),
            "normalized_v3_job_intent_id": updated.intent_id,
        }
        if ratio_resolution is not None:
            request.metadata["requested_image_aspect_ratio"] = ratio_resolution[0]
            request.metadata["requested_image_aspect_ratio_source"] = "remote_brain_user_intent"
        return updated

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
        # Planning and generation are separate runtime entries for one Job.
        # Once Product API has persisted the normalized contract, generation
        # must consume that exact count/size/text decision rather than
        # recomputing it from mutable nested scenario parameters.  Otherwise a
        # continuation can be planned for one output but rejected before the
        # provider because a later-stage default says two.
        frozen_payload = metadata.get("normalized_v3_job_intent")
        if isinstance(frozen_payload, dict):
            if not request.trusted_capability_plan_reuse:
                raise CapabilityActivationError("untrusted_normalized_v3_job_intent")
            try:
                frozen = NormalizedV3JobIntent.model_validate(frozen_payload)
            except ValidationError as exc:
                raise CapabilityActivationError("normalized_v3_job_intent_invalid") from exc
            template_id = self._template_id(request, resolution)
            if frozen.template_id != template_id:
                raise CapabilityActivationError("normalized_v3_job_intent_template_mismatch")
            if frozen.scenario_id != resolution.manifest.scenario_id:
                raise CapabilityActivationError("normalized_v3_job_intent_scenario_mismatch")
            # Brain request construction reads these transport fields before
            # looking at the nested Scenario Pack diagnostics.  Reassert the
            # immutable values here so a stale continuation/default cannot
            # cause the Brain plan and the frozen deliverable contract to
            # disagree during generation.
            metadata["requested_image_count"] = frozen.effective_image_count
            metadata["requested_image_size"] = frozen.effective_image_size
            metadata["normalized_v3_job_intent"] = frozen.model_dump(mode="json")
            metadata["normalized_v3_job_intent_id"] = frozen.intent_id
            request.metadata = metadata
            return frozen
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
        explicit_visible_text_policy = str(
            metadata.get("visible_text_policy")
            or parameters.get("visible_text_policy")
            or ""
        ).strip().lower()
        brain_semantic_analysis_required = self._capability_activation_mode(request) == "enforced"
        forbidden_text_markers = (
            "no visible text",
            "without visible text",
            "no text",
            "text-free",
            "不要文字",
            "无文字",
            "不加文字",
            "不含文字",
        )
        if explicit_visible_text_policy not in {"required", "allowed", "forbidden", "unspecified", ""}:
            raise CapabilityActivationError("visible_text_policy_invalid")
        if brain_semantic_analysis_required:
            user_forbids_visible_text = explicit_visible_text_policy == "forbidden"
        else:
            user_forbids_visible_text = explicit_visible_text_policy == "forbidden" or any(
                marker in request.user_input.lower() for marker in forbidden_text_markers
            )
        visible_text_policy = "forbidden" if user_forbids_visible_text else (
            explicit_visible_text_policy or ("required" if explicit_text else "unspecified")
        )
        text_policy = (
            "provider_native_text_forbidden"
            if visible_text_policy == "forbidden"
            else "provider_native_explicit_text"
            if explicit_text
            else "provider_native_no_forced_text"
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
                visible_text_policy,
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
            text_policy=text_policy,
            visible_text_policy=visible_text_policy,
            user_constraints=[
                {
                    "channel": "visible_text",
                    "owner": "user",
                    "strength": "hard",
                    "value": visible_text_policy,
                    "source": "explicit_metadata_or_user_intent",
                }
            ],
            source_truth_locks=[
                {
                    "channel": "product_truth",
                    "owner": "product_identity",
                    "source": "product_profile",
                    "fields": sorted(str(key) for key, value in request.product_profile.items() if value not in (None, "", [], {})),
                }
            ]
            if request.product_profile
            else [],
            provenance=[
                {
                    "source": "ScenarioRuntime._normalize_v3_job_intent",
                    "requested_image_count": requested_count,
                    "declared_image_count_limit": declared_limit,
                    "count_limit_source": limit_source,
                    "visible_text_policy": visible_text_policy,
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
        request: ScenarioRuntimeRequest,
        normalized_intent: NormalizedV3JobIntent,
        policy: TemplateCapabilityPolicy,
        brain_result: BrainRunResult,
        specialized_plan: SpecializedScenarioPlanningResult | None,
    ) -> TemplateDeliverablePlan:
        directions = [str(item).strip() for item in brain_result.image_set_plan.shot_plan if str(item).strip()]
        expected = normalized_intent.effective_image_count
        if brain_result.image_set_plan.image_count != expected or len(directions) != expected:
            raise CapabilityActivationError(
                "template_deliverable_plan_output_count_mismatch"
                f": expected={expected}; brain_image_count={brain_result.image_set_plan.image_count}; "
                f"brain_direction_count={len(directions)}"
            )
        product_truth_selection_by_output = self._validated_ecommerce_product_truth_selection_by_output(
            request=request,
            brain_result=brain_result,
            expected_count=expected,
        )
        professional_pose_contract_by_output = self._validated_professional_ecommerce_pose_contract_by_output(
            request=request,
            brain_result=brain_result,
            expected_count=expected,
        )
        professional_body_contract_by_output = self._validated_professional_body_proportion_contract_by_output(
            request=request,
            brain_result=brain_result,
            expected_count=expected,
        )
        role_recipes = (
            specialized_plan.execution_plan.get("role_recipes", [])
            if specialized_plan is not None and isinstance(specialized_plan.execution_plan, dict)
            else []
        )
        specialized_policy = (
            dict(specialized_plan.execution_plan.get("policy") or {})
            if specialized_plan is not None and isinstance(specialized_plan.execution_plan, dict)
            else {}
        )
        creative_owner = str(policy.metadata.get("creative_direction_owner") or "central_brain")
        deliverables: list[TemplateDeliverable] = []
        for index, direction in enumerate(directions, 1):
            recipe = role_recipes[index - 1] if index <= len(role_recipes) and isinstance(role_recipes[index - 1], dict) else {}
            factual_acceptance = (
                ["product_truth", "platform_factual_constraints"]
                if normalized_intent.scenario_id == "ecommerce"
                else []
            )
            # The Template owns the professional role contract while Central
            # Brain owns the image intent. Carry that frozen role record and
            # the Brain-selected evidence purpose through the deliverable plan
            # so an enforced Provider/Review/Retry path consumes the resolved
            # ledger rather than mutable runtime metadata.
            deliverable_metadata = (
                {
                    "specialized_role_key": recipe.get("role_key"),
                    "specialized_role_contract": dict(recipe),
                    "specialized_execution_policy": specialized_policy,
                }
                if recipe.get("role_key")
                else {}
            )
            product_truth_selection = product_truth_selection_by_output.get(index, {})
            selected_product_truth = (
                list(product_truth_selection.get("selected_product_truth_asset_ids") or [])
                if isinstance(product_truth_selection, dict)
                else []
            )
            product_truth_selection_role = (
                str(product_truth_selection.get("product_truth_selection_role") or "").strip()
                if isinstance(product_truth_selection, dict)
                else ""
            )
            if selected_product_truth:
                deliverable_metadata["product_truth_selection_role"] = product_truth_selection_role
                deliverable_metadata["selected_product_truth_asset_ids"] = list(selected_product_truth)
                deliverable_metadata["admitted_product_truth_asset_ids"] = list(selected_product_truth)
                deliverable_metadata["max_product_truth_source_refs_per_output"] = int(
                    product_truth_selection["max_product_truth_source_refs_per_output"]
                )
                deliverable_metadata["product_truth_selection_source"] = (
                    "remote_brain_image_set_plan.evidence_dimensions_by_output"
                )
                deliverable_metadata["product_truth_pool_asset_ids"] = [
                    asset.asset_id
                    for asset in request.uploaded_assets
                    if self._uploaded_asset_reference_channel(asset) == "product_truth"
                ]
            pose_contract = professional_pose_contract_by_output.get(index)
            if pose_contract:
                deliverable_metadata["professional_ecommerce_pose_role"] = pose_contract["pose_role"]
                deliverable_metadata["professional_ecommerce_pose_acceptance"] = dict(pose_contract)
                deliverable_metadata["professional_ecommerce_pose_contract_source"] = (
                    "remote_brain_image_set_plan.evidence_dimensions_by_output"
                )
            body_contract = professional_body_contract_by_output.get(index)
            if body_contract:
                deliverable_metadata["professional_body_proportion_requirement"] = body_contract[
                    "requirement"
                ]
                if body_contract.get("body_view_kind") is not None:
                    deliverable_metadata["professional_body_view_kind"] = body_contract["body_view_kind"]
                deliverable_metadata["professional_body_proportion_contract_source"] = (
                    "remote_brain_image_set_plan.evidence_dimensions_by_output"
                )
            deliverables.append(
                TemplateDeliverable(
                    deliverable_id=stable_id("template_deliverable", normalized_intent.intent_id, index, direction),
                    output_index=index,
                    image_intent=direction,
                    source=creative_owner,
                    factual_acceptance=factual_acceptance,
                    metadata=deliverable_metadata,
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

    @staticmethod
    def _uploaded_asset_reference_channel(asset: Any) -> str:
        metadata = getattr(asset, "metadata", None)
        metadata = metadata if isinstance(metadata, dict) else {}
        channel = str(metadata.get("codex_native_reference_channel") or "").strip()
        if channel:
            return channel
        role = str(getattr(asset, "role", "") or "").strip()
        if role == "product_reference":
            return "product_truth"
        if role == "face_reference":
            return "portrait_identity"
        return role

    @staticmethod
    def _validated_professional_ecommerce_pose_contract_by_output(
        *,
        request: ScenarioRuntimeRequest,
        brain_result: BrainRunResult,
        expected_count: int,
    ) -> dict[int, dict[str, Any]]:
        """Freeze Remote-Brain pose acceptance for Professional E-Commerce.

        This is intentionally a specialized deliverable contract. It does not
        add a Human Realism or Provider-global pose recipe, and it never
        rewrites renderer prompts locally.
        """

        metadata = dict(request.metadata or {})
        ecommerce_context = metadata.get("ecommerce_creative_context")
        ecommerce_context = ecommerce_context if isinstance(ecommerce_context, dict) else {}
        raw_contract = ecommerce_context.get("professional_ecommerce_pose_contract")
        if raw_contract is None:
            return {}
        try:
            expected_contract = validate_professional_ecommerce_pose_contract_payload(
                raw_contract,
                requested_image_count=expected_count,
            )
        except ValueError:
            raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid") from None
        required_by_index = {
            item.output_index: item.model_dump(mode="json")
            for item in expected_contract.required_pose_by_output
        }
        raw_entries = list(brain_result.image_set_plan.evidence_dimensions_by_output)
        if len(raw_entries) != expected_count:
            raise CapabilityActivationError("professional_ecommerce_pose_contract_missing_or_incomplete")
        resolved: dict[int, dict[str, Any]] = {}
        required_standing = {
            "both_feet_weight_bearing",
            "no_kneeling",
            "no_crouched_low_support",
            "interaction_may_use_one_hand_but_body_remains_standing",
        }
        required_standing_presentation = {
            "front_or_three_quarter_presentation",
            "ordinary_full_body_commercial_framing",
            "eye_level_or_standard_camera_height",
            "no_rear_facing_lookback",
        }
        for entry in raw_entries:
            index = int(entry.output_index)
            expected = required_by_index.get(index)
            if expected is None or index in resolved or index < 1 or index > expected_count:
                raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
            pose_role = str(getattr(entry, "professional_ecommerce_pose_role", "") or "").strip()
            if pose_role != expected["pose_role"]:
                raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
            standing_requirements = [
                str(item).strip()
                for item in getattr(entry, "standing_pose_requirements", [])
                if str(item).strip()
            ]
            standing_presentation_requirements = [
                str(item).strip()
                for item in getattr(entry, "standing_presentation_requirements", [])
                if str(item).strip()
            ]
            if pose_role == "standing_poolside":
                if (
                    len(standing_requirements) != len(set(standing_requirements))
                    or set(standing_requirements) != required_standing
                ):
                    raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
                if (
                    len(standing_presentation_requirements)
                    != len(set(standing_presentation_requirements))
                    or set(standing_presentation_requirements) != required_standing_presentation
                ):
                    raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
            elif standing_requirements:
                raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
            elif standing_presentation_requirements:
                raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
            resolved[index] = {
                "pose_role": pose_role,
                "standing_requirements": list(standing_requirements),
                "standing_presentation_requirements": list(standing_presentation_requirements),
                "contract_version": expected_contract.contract_version,
                "owner": expected_contract.owner,
                "source": "remote_brain_image_set_plan.evidence_dimensions_by_output",
            }
        if sorted(resolved) != list(range(1, expected_count + 1)):
            raise CapabilityActivationError("professional_ecommerce_pose_contract_invalid")
        return resolved

    @staticmethod
    def _validated_professional_body_proportion_contract_by_output(
        *,
        request: ScenarioRuntimeRequest,
        brain_result: BrainRunResult,
        expected_count: int,
    ) -> dict[int, dict[str, Any]]:
        """Freeze Remote-Brain body proportion receipts for Professional outputs.

        This only validates a typed per-output receipt.  It does not select a
        Character Card image, infer body visibility from prompt text, or author
        renderer wording; the native Professional planner must later map the
        signed view kind to an active server-owned Body Silhouette slot.
        """

        metadata = dict(request.metadata or {})
        if not ScenarioRuntime._professional_body_proportion_server_context(metadata):
            return {}
        raw_entries = list(brain_result.image_set_plan.evidence_dimensions_by_output)
        receipt_required = ScenarioRuntime._professional_body_proportion_receipt_required_from_server_context(metadata)
        if not receipt_required and not any(
            getattr(entry, "professional_body_proportion_requirement", None) is not None
            or getattr(entry, "professional_body_view_kind", None) is not None
            for entry in raw_entries
        ):
            return {}
        if len(raw_entries) != expected_count:
            raise CapabilityActivationError("professional_body_proportion_contract_missing_or_incomplete")
        allowed_requirements = {"not_required", "visible_body_required", "full_body_required"}
        allowed_views = {"front_full", "side_full", "rear_full"}
        resolved: dict[int, dict[str, Any]] = {}
        for entry in raw_entries:
            index = getattr(entry, "output_index", None)
            if type(index) is not int or index < 1 or index > expected_count or index in resolved:
                raise CapabilityActivationError("professional_body_proportion_contract_invalid")
            requirement = str(getattr(entry, "professional_body_proportion_requirement", "") or "").strip()
            if requirement not in allowed_requirements:
                raise CapabilityActivationError("professional_body_proportion_contract_missing_or_incomplete")
            body_view_kind = getattr(entry, "professional_body_view_kind", None)
            if requirement == "not_required":
                if body_view_kind is not None:
                    raise CapabilityActivationError("professional_body_proportion_contract_contradictory")
                resolved[index] = {
                    "requirement": requirement,
                    "body_view_kind": None,
                    "source": "remote_brain_image_set_plan.evidence_dimensions_by_output",
                }
                continue
            view = str(body_view_kind or "").strip()
            if view not in allowed_views:
                raise CapabilityActivationError("professional_body_proportion_contract_view_invalid")
            resolved[index] = {
                "requirement": requirement,
                "body_view_kind": view,
                "source": "remote_brain_image_set_plan.evidence_dimensions_by_output",
            }
        if sorted(resolved) != list(range(1, expected_count + 1)):
            raise CapabilityActivationError("professional_body_proportion_contract_invalid")
        return resolved

    @staticmethod
    def _professional_body_proportion_receipt_required_from_server_context(
        metadata: dict[str, Any],
    ) -> bool:
        """Trust body-proportion receipts only from native Professional binding resolution."""

        if metadata.get("professional_body_proportion_receipt_required") is not True:
            return False
        return ScenarioRuntime._professional_body_proportion_server_context(metadata)

    @staticmethod
    def _professional_body_proportion_server_context(metadata: dict[str, Any]) -> bool:
        """Recognize the server-owned Professional body projection context."""

        raw_mode = metadata.get("professional_mode")
        mode = "professional" if raw_mode is True else str(raw_mode or "").strip().lower()
        if mode != "professional":
            return False
        if metadata.get("local_mcp_professional_relay") is not True:
            return False
        if metadata.get("professional_body_proportion_contract_source") != "server_owned_professional_binding_resolver":
            return False
        return isinstance(metadata.get("professional_mode_binding_record"), dict)

    @staticmethod
    def _canonical_context_has_professional_body_contract(context: dict[str, Any]) -> bool:
        """Detect an already-validated frozen body-proportion receipt."""

        for deliverable in context.get("deliverables", []):
            if not isinstance(deliverable, dict):
                continue
            metadata = deliverable.get("metadata")
            if not isinstance(metadata, dict):
                continue
            if (
                metadata.get("professional_body_proportion_requirement") is not None
                or metadata.get("professional_body_view_kind") is not None
            ):
                return True
        return False

    def _validated_ecommerce_product_truth_selection_by_output(
        self,
        *,
        request: ScenarioRuntimeRequest,
        brain_result: BrainRunResult,
        expected_count: int,
    ) -> dict[int, dict[str, Any]]:
        """Freeze Remote-Brain product-truth selection for Professional E-Commerce.

        Product uploads are a truth pool.  The Remote Brain chooses which pool
        member each output needs; local code validates cardinality and IDs but
        does not infer selection from filenames, upload order, prompt text, or
        image content.
        """

        metadata = dict(request.metadata or {})
        if not metadata.get("professional_product_truth_required"):
            return {}
        product_truth_ids = [
            asset.asset_id
            for asset in request.uploaded_assets
            if self._uploaded_asset_reference_channel(asset) == "product_truth"
        ]
        if not product_truth_ids:
            raise CapabilityActivationError("ecommerce_product_truth_selection_pool_missing")
        # Doc270/E31 may already have issued a server-owned, per-output
        # original binding after source analysis. That binding is the
        # authoritative product-truth choice for this command; requiring the
        # Brain to repeat the same opaque asset IDs creates two competing
        # selectors and turns a valid plan into a fallback placeholder.
        if metadata.get("doc270_ecommerce_view_activation_enabled") is True:
            raw_selection = metadata.get("doc270_ecommerce_view_activation_selection")
            if not isinstance(raw_selection, list):
                raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
            resolved: dict[int, dict[str, Any]] = {}
            for item in raw_selection:
                if not isinstance(item, dict) or set(item) != {
                    "output_index",
                    "selected_product_asset_id",
                    "source_receipt_digest",
                    "source_library_snapshot_digest",
                }:
                    raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
                index = item.get("output_index")
                asset_id = str(item.get("selected_product_asset_id") or "").strip()
                if (
                    not isinstance(index, int)
                    or isinstance(index, bool)
                    or index < 1
                    or index > expected_count
                    or index in resolved
                    or asset_id not in product_truth_ids
                    or any(
                        not isinstance(item.get(key), str)
                        or len(str(item.get(key)).strip()) != 64
                        for key in ("source_receipt_digest", "source_library_snapshot_digest")
                    )
                ):
                    raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
                resolved[index] = {
                    "product_truth_selection_role": "doc270_view_aware_product_original",
                    "selected_product_truth_asset_ids": [asset_id],
                    "max_product_truth_source_refs_per_output": 1,
                }
            if sorted(resolved) != list(range(1, expected_count + 1)):
                raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
            return resolved
        ecommerce_context = metadata.get("ecommerce_creative_context")
        ecommerce_context = ecommerce_context if isinstance(ecommerce_context, dict) else {}
        provider_budget = ecommerce_context.get("provider_reference_budget")
        provider_budget = provider_budget if isinstance(provider_budget, dict) else {}
        raw_max_product_refs = provider_budget.get("max_product_truth_source_refs_per_output")
        try:
            max_product_truth_refs = int(raw_max_product_refs)
        except (TypeError, ValueError):
            raise CapabilityActivationError("ecommerce_product_truth_selection_capacity_contract_missing") from None
        if max_product_truth_refs < 1 or max_product_truth_refs > 2:
            raise CapabilityActivationError("ecommerce_product_truth_selection_capacity_contract_missing")
        raw_entries = list(brain_result.image_set_plan.evidence_dimensions_by_output)
        if len(raw_entries) != expected_count:
            raise CapabilityActivationError("ecommerce_product_truth_selection_missing_or_incomplete")
        product_truth_id_set = set(product_truth_ids)
        resolved: dict[int, dict[str, Any]] = {}
        for entry in raw_entries:
            index = int(entry.output_index)
            role = str(getattr(entry, "product_truth_selection_role", "") or "").strip()
            selected = [str(item).strip() for item in entry.selected_product_truth_asset_ids if str(item).strip()]
            if (
                index in resolved
                or index < 1
                or index > expected_count
                or role not in ECOMMERCE_PRODUCT_TRUTH_SELECTION_ROLES
                or not selected
            ):
                raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
            if len(selected) != len(set(selected)):
                raise CapabilityActivationError("ecommerce_product_truth_selection_duplicate")
            if not set(selected).issubset(product_truth_id_set):
                raise CapabilityActivationError("ecommerce_product_truth_selection_unknown_asset")
            if len(selected) > 2:
                raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
            if len(selected) == 2 and role != ECOMMERCE_PRODUCT_TRUTH_DETAIL_ROLE:
                raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
            if len(selected) > max_product_truth_refs:
                raise CapabilityActivationError("ecommerce_product_truth_selection_capacity_exceeded")
            resolved[index] = {
                "product_truth_selection_role": role,
                "selected_product_truth_asset_ids": selected,
                "max_product_truth_source_refs_per_output": max_product_truth_refs,
            }
        if sorted(resolved) != list(range(1, expected_count + 1)):
            raise CapabilityActivationError("ecommerce_product_truth_selection_invalid")
        return resolved


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
                or metadata.get("v3_job_instance_id")
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
            self._capability_input(
                request,
                resolution,
                metadata={
                    "capability_phase": "pre_activation",
                    "brain_semantic_analysis_required": (
                        self._capability_activation_mode(request) == "enforced"
                    ),
                },
            ),
            module_ids=self._dedupe_preserve_order(module_ids),
        )

    def _run_active_capabilities(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        plan: CapabilityActivationPlan,
        pre_activation_run: CapabilityRunResult | None,
        *,
        brain_result: BrainRunResult | None = None,
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
        active_metadata = {
            "capability_phase": "active",
            # The active capability pass may contribute factual
            # evidence and review obligations, but it must not leave
            # a second, locally-authored prompt route alive.  The
            # visual cluster uses this explicit marker to quarantine
            # legacy phrase/patch fields before its result can enter
            # the frozen envelope for a new enforced V3 Job.
            "brain_owned_forward_execution": plan.activation_mode == "enforced",
            "capability_activation_plan": plan.model_dump(mode="json"),
            "capability_activation_plan_summary": plan.summary(),
            # The active executor must consume the semantic decision
            # already made by the remote Brain.  It is deliberately
            # not allowed to rediscover whole-image rendering style
            # from isolated terms such as a print on a garment.
            "visual_task_profile": (
                brain_result.visual_task_profile.model_dump(mode="json")
                if brain_result is not None and brain_result.visual_task_profile is not None
                else None
            ),
            "brain_semantic_analysis_required": plan.activation_mode == "enforced",
        }
        ecommerce_review_context = self._ecommerce_human_realism_review_context(
            request,
            requested_image_count=self._requested_image_count_for_brain(request),
        )
        if ecommerce_review_context:
            active_metadata["ecommerce_human_realism_review_context"] = ecommerce_review_context
        run = self.shared_capability_registry.run(
            self._capability_input(
                request,
                resolution,
                prior_results=list(pre_activation_run.results) if pre_activation_run else [],
                metadata=active_metadata,
            ),
            module_ids=executor_ids,
            required_module_ids=[item for item in required_executor_ids if item],
        )
        return self._attach_composed_contribution(run, plan, request, resolution)

    def _ecommerce_human_realism_review_context(
        self,
        request: ScenarioRuntimeRequest,
        *,
        requested_image_count: int,
    ) -> dict[str, Any]:
        metadata = dict(request.metadata or {})
        ecommerce_context = metadata.get("ecommerce_creative_context")
        if not isinstance(ecommerce_context, dict) or "creative_risk_preflight" not in ecommerce_context:
            return {}
        raw_preflight = ecommerce_context.get("creative_risk_preflight")
        if not isinstance(raw_preflight, dict):
            raise CapabilityActivationError("ecommerce_creative_risk_review_context_invalid")
        mode = "professional" if self._is_professional_request(metadata) else "standard"
        approved_identity_view_kinds = (
            self._approved_professional_identity_view_kinds_from_request(metadata)
            if mode == "professional"
            else None
        )
        try:
            return ecommerce_human_realism_review_context_from_preflight_payload(
                raw_preflight,
                scenario_id="ecommerce",
                mode=mode,
                requested_image_count=requested_image_count,
                approved_identity_view_kinds=approved_identity_view_kinds,
            )
        except ValueError as exc:
            raise CapabilityActivationError("ecommerce_creative_risk_review_context_invalid") from exc

    @staticmethod
    def _is_professional_request(metadata: dict[str, Any]) -> bool:
        raw_mode = metadata.get("professional_mode")
        return raw_mode is True or str(raw_mode or "").strip().lower() == "professional"

    @staticmethod
    def _approved_professional_identity_view_kinds_from_request(metadata: dict[str, Any]) -> set[str]:
        binding = metadata.get("professional_mode_binding_record") or metadata.get(
            "professional_mode_binding"
        )
        if not isinstance(binding, dict):
            return set()
        selectors = binding.get("identity_view_ids")
        if not isinstance(selectors, list):
            return set()
        return professional_identity_view_kinds_from_selectors(
            [str(item) for item in selectors if isinstance(item, str)]
        )

    @staticmethod
    def _validate_frozen_capability_execution(
        plan: CapabilityActivationPlan,
        active_run: CapabilityRunResult | None,
    ) -> None:
        """Reject a stale executor result that contradicts an active capability.

        A frozen plan that requires Human Realism is not satisfied merely
        because a legacy helper emitted an inactive guidance object.  This is
        a semantic execution mismatch, not an invitation to append local
        prompt repair text.
        """

        if "human_realism" not in plan.dependency_order:
            return
        if active_run is None:
            raise CapabilityActivationError("human_realism_execution_missing")
        cluster_result = next(
            (item for item in active_run.results if item.module_id == VISUAL_CAPABILITY_CLUSTER_ID),
            None,
        )
        cluster = dict(cluster_result.facts.get("visual_capability_cluster") or {}) if cluster_result else {}
        guidance = cluster.get("human_photorealism_guidance")
        if not isinstance(guidance, dict) or not bool(guidance.get("applies")):
            raise CapabilityActivationError("human_realism_execution_mismatch")

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
        *,
        brain_result: BrainRunResult | None = None,
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
        conflicts: list[dict[str, Any]] = []
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
        rendering_intent = (
            brain_result.visual_task_profile.rendering_intent.model_dump(mode="json")
            if brain_result is not None and brain_result.visual_task_profile is not None
            else {}
        )
        if rendering_intent:
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=stable_id("constraint", normalized_intent.intent_id, "rendering_semantics"),
                    channel="rendering_semantics",
                    owner=str(rendering_intent.get("decision_owner") or "evidence_fallback"),
                    strength="hard",
                    precedence=96,
                    requested_value=rendering_intent,
                    resolved_value=rendering_intent,
                    resolution="accepted",
                    provenance=[{"source": "BrainRunResult.visual_task_profile.rendering_intent"}],
                )
            )
        parameters = dict(request.scenario_selection.parameters) if request.scenario_selection else {}
        metadata_size = str(request.metadata.get("requested_image_size") or "").strip() or None
        parameter_size = str(parameters.get("requested_image_size") or "").strip() or None
        if metadata_size and parameter_size and metadata_size != parameter_size:
            scenario_canvas_id = stable_id("constraint", normalized_intent.intent_id, "canvas", "scenario_parameter")
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=scenario_canvas_id,
                    channel="canvas",
                    owner="scenario_parameter",
                    strength="hard",
                    precedence=80,
                    requested_value=parameter_size,
                    resolved_value=normalized_intent.effective_image_size,
                    resolution="overridden",
                    provenance=[{"source": "ScenarioSelection.parameters", "field": "requested_image_size"}],
                )
            )
            conflicts.append(
                {
                    "channel": "canvas",
                    "winner": "user_metadata",
                    "loser": "scenario_parameter",
                    "resolution": "user_explicit_size_overrides_default",
                    "winner_value": normalized_intent.effective_image_size,
                    "loser_value": parameter_size,
                    "constraint_ids": [entries[1].constraint_id, scenario_canvas_id],
                }
            )
        metadata_count = request.metadata.get("requested_image_count")
        parameter_count = parameters.get("requested_image_count")
        if metadata_count not in (None, "") and parameter_count not in (None, ""):
            try:
                count_conflict = int(metadata_count) != int(parameter_count)
            except (TypeError, ValueError):
                count_conflict = False
            if count_conflict:
                scenario_count_id = stable_id("constraint", normalized_intent.intent_id, "count", "scenario_parameter")
                entries.append(
                    ResolvedConstraintEntry(
                        constraint_id=scenario_count_id,
                        channel="count",
                        owner="scenario_parameter",
                        strength="hard",
                        precedence=80,
                        requested_value=parameter_count,
                        resolved_value=normalized_intent.effective_image_count,
                        resolution="overridden",
                        provenance=[{"source": "ScenarioSelection.parameters", "field": "requested_image_count"}],
                    )
                )
                conflicts.append(
                    {
                        "channel": "count",
                        "winner": "user_metadata",
                        "loser": "scenario_parameter",
                        "resolution": "user_explicit_count_overrides_default",
                        "winner_value": normalized_intent.effective_image_count,
                        "loser_value": parameter_count,
                        "constraint_ids": [entries[1].constraint_id, scenario_count_id],
                    }
                )
        copy_values = [
            value
            for value in (
                request.metadata.get("provider_native_text_requirements"),
                request.metadata.get("approved_literal_copy"),
                parameters.get("provider_native_text_requirements"),
                parameters.get("approved_literal_copy"),
            )
            if value not in (None, "", [], {})
        ]
        if normalized_intent.visible_text_policy == "forbidden" and copy_values:
            copy_constraint_id = stable_id("constraint", normalized_intent.intent_id, "visible_text", "copy_request")
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=copy_constraint_id,
                    channel="visible_text",
                    owner="user_copy_request",
                    strength="hard",
                    precedence=93,
                    requested_value=copy_values,
                    resolved_value=None,
                    resolution="rejected",
                    provenance=[{"source": "request_metadata", "reason": "visible_text_forbidden"}],
                )
            )
            conflicts.append(
                {
                    "channel": "visible_text",
                    "winner": "user_no_visible_text",
                    "loser": "user_copy_request",
                    "resolution": "copy_rejected_no_visible_text_wins",
                    "constraint_ids": [entries[2].constraint_id, copy_constraint_id],
                }
            )
        for deliverable in template_deliverable_plan.deliverables:
            direction = str(deliverable.image_intent or "")
            direction_requests_text = any(
                marker in direction.lower()
                for marker in ("headline", "call to action", "cta", "visible text", "marketing copy", "文字", "文案")
            )
            deliverable_resolution = (
                "translated"
                if normalized_intent.visible_text_policy == "forbidden" and direction_requests_text
                else "accepted"
            )
            resolved_deliverable_value: Any = (
                {
                    "image_intent": direction,
                    "visible_text": "forbidden",
                    "translation": "preserve composition intent without visible copy",
                }
                if deliverable_resolution == "translated"
                else direction
            )
            constraint_id = stable_id("constraint", template_deliverable_plan.plan_id, deliverable.deliverable_id)
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=constraint_id,
                    channel="deliverable_role",
                    owner=template_deliverable_plan.owner,
                    strength="hard",
                    precedence=90,
                    requested_value=direction,
                    resolved_value=resolved_deliverable_value,
                    resolution=deliverable_resolution,
                    provenance=[{"source": deliverable.source, "output_index": deliverable.output_index}],
                )
            )
            if deliverable_resolution == "translated":
                conflicts.append(
                    {
                        "channel": "visible_text",
                        "winner": "user_no_visible_text",
                        "loser": "template_deliverable_intent",
                        "resolution": "deliverable_translated_without_visible_copy",
                        "constraint_ids": [entries[2].constraint_id, constraint_id],
                    }
                )
        apparel_construction = extract_apparel_construction_facts(
            request.product_profile,
            has_reference_evidence=bool(self._uploaded_assets(request)),
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
        for fact in apparel_construction.facts:
            resolved_value = {
                "values": list(fact.values),
                "evidence_mode": fact.evidence_mode,
                "source_fields": list(fact.source_fields),
                "allowed_variation": fact.allowed_variation,
            }
            entries.append(
                ResolvedConstraintEntry(
                    constraint_id=stable_id("constraint", normalized_intent.intent_id, fact.channel, fact.source_fields),
                    channel=fact.channel,
                    owner="product_identity",
                    strength=fact.strength,
                    precedence=92,
                    requested_value=list(fact.values),
                    resolved_value=resolved_value,
                    resolution="accepted",
                    provenance=[
                        {
                            "source": fact.source,
                            "fields": list(fact.source_fields),
                            "evidence_mode": fact.evidence_mode,
                        }
                    ],
                )
            )
        # Capability contributions may establish facts, review obligations and
        # activation scope.  They may not persist a second local phrase list
        # in a new enforced ledger.  The remote Brain is the only component
        # allowed to turn those facts into renderer language at final sign-off.
        hard_capabilities = {
            "product_identity",
            "portrait_identity",
            "nonhuman_subject_identity",
            "human_realism",
        }
        hard_semantic_contract = bool(
            set(plan.dependency_order) & hard_capabilities
            or normalized_intent.scenario_id == "ecommerce"
            # An active Photography run always has a frozen role/profile/
            # reference contract.  Metadata-only inspection cannot certify a
            # real photographic delivery, even for a single output.
            or normalized_intent.scenario_id == "photography"
            or normalized_intent.text_policy == "provider_native_explicit_text"
            or normalized_intent.effective_image_count > 1
        )
        resolved_deliverables = []
        for deliverable in template_deliverable_plan.deliverables:
            matching = next(
                (
                    entry
                    for entry in entries
                    if entry.channel == "deliverable_role"
                    and entry.constraint_id == stable_id("constraint", template_deliverable_plan.plan_id, deliverable.deliverable_id)
                ),
                None,
            )
            resolved_value = matching.resolved_value if matching is not None else deliverable.image_intent
            resolved_intent = (
                str(resolved_value.get("image_intent") or "")
                if isinstance(resolved_value, dict)
                else str(resolved_value or "")
            )
            resolved_deliverables.append(
                {
                    "deliverable_id": deliverable.deliverable_id,
                    "output_index": deliverable.output_index,
                    "image_intent": resolved_intent,
                    "factual_acceptance": list(deliverable.factual_acceptance),
                    "metadata": dict(deliverable.metadata),
                    "constraint_id": matching.constraint_id if matching is not None else None,
                    "resolution": matching.resolution if matching is not None else "accepted",
                }
            )
        product_truth = {
            str(key): value
            for key, value in dict(request.product_profile or {}).items()
            if value not in (None, "", [], {})
        }
        template_evidence_retry_contract = self._template_delivery_evidence_retry_contract(resolved_deliverables)
        provider_projection = {
            "projection_version": "resolved_constraint_ledger_v1",
            "template_id": normalized_intent.template_id,
            "scenario_id": normalized_intent.scenario_id,
            "protected_user_intent": normalized_intent.protected_user_intent,
            "effective_image_count": normalized_intent.effective_image_count,
            "requested_image_size": normalized_intent.effective_image_size,
            "text_policy": normalized_intent.text_policy,
            "visible_text_policy": normalized_intent.visible_text_policy,
            "rendering_semantics": rendering_intent,
            "deliverables": resolved_deliverables,
            "product_truth": product_truth,
            "apparel_construction": apparel_construction.provider_projection(),
            "quality_guidance": [],
            "negative_guidance": [],
            "retry_patch": {},
            "capability_projection": self._ledger_capability_projection(raw_cluster, plan),
            "legacy_adapter": {
                "source": "accepted_active_executor_results",
                "raw_cluster_retained": False,
                "fallback_allowed": False,
            },
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
            conflicts=conflicts,
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
                "visible_text_policy": normalized_intent.visible_text_policy,
                "deliverable_owner": template_deliverable_plan.owner,
                "applied_constraint_ids": applied_ids,
                "translated_constraint_ids": translated_ids,
                "rejected_constraint_ids": rejected_ids,
                "conflict_count": len(conflicts),
            },
            review_contracts=list(composed.review_contracts),
            retry_contracts=self._evidence_only_retry_contracts(
                [
                    *list(composed.retry_contracts),
                    *([template_evidence_retry_contract] if template_evidence_retry_contract else []),
                ]
            ),
            hard_semantic_contract=hard_semantic_contract,
            provenance=[
                {
                    "source": "ScenarioRuntime._build_resolved_constraint_ledger",
                    "active_capability_ids": list(plan.dependency_order),
                    "string_append_is_not_resolution": True,
                }
            ],
        )

    @staticmethod
    def _template_delivery_evidence_retry_contract(deliverables: list[dict[str, Any]]) -> dict[str, Any]:
        """Publish an owner-local retry contract for Brain-declared evidence.

        This derives no role, shot, pose, camera, or static suite.  It exists
        only when a specialized template has already frozen distinct evidence
        dimensions into its Brain-owned deliverables.
        """

        evidence_rows = []
        for deliverable in deliverables:
            metadata = deliverable.get("metadata") if isinstance(deliverable.get("metadata"), dict) else {}
            dimensions = [str(item).strip() for item in metadata.get("brain_evidence_dimensions", []) if str(item).strip()]
            if dimensions:
                evidence_rows.append(
                    {
                        "deliverable_id": str(deliverable.get("deliverable_id") or ""),
                        "output_index": deliverable.get("output_index"),
                        "dimensions": list(dict.fromkeys(dimensions)),
                    }
                )
        if not evidence_rows:
            return {}
        return {
            "capability_id": "template_deliverable_owner",
            "issue_codes": ["delivery_evidence_dimension_mismatch"],
            "metadata": {
                "source": "resolved_constraint_ledger.template_deliverables",
                "static_recipe_present": False,
                "retry_evidence_only": True,
                "brain_evidence_rows": evidence_rows,
            },
        }

    @staticmethod
    def _evidence_only_retry_contracts(contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Retain retry scope without retaining local renderer prose.

        An active capability can say which normalized failure codes it owns;
        it cannot prescribe a phrase-level repair.  The next remote Brain
        finalization receives the codes and independently signs a full prompt.
        """

        evidence_only: list[dict[str, Any]] = []
        for raw_contract in contracts:
            contract = (
                raw_contract.model_dump(mode="json")
                if hasattr(raw_contract, "model_dump")
                else raw_contract
            )
            if not isinstance(contract, dict):
                continue
            capability_id = str(contract.get("capability_id") or "").strip()
            issue_codes = [str(code).strip() for code in contract.get("issue_codes", []) if str(code).strip()]
            if not capability_id or not issue_codes:
                continue
            metadata = dict(contract.get("metadata") or {})
            metadata["retry_evidence_only"] = True
            evidence_only.append(
                {
                    "capability_id": capability_id,
                    "issue_codes": list(dict.fromkeys(issue_codes)),
                    "metadata": metadata,
                }
            )
        return evidence_only

    @staticmethod
    def _server_resolved_retry_patch(
        request: ScenarioRuntimeRequest,
        plan: CapabilityActivationPlan,
    ) -> dict[str, Any]:
        """Accept a retry patch only when Product API bound it to this plan."""

        normalized = request.metadata.get("normalized_v3_job_intent")
        envelope = request.metadata.get("capability_execution_envelope")
        frozen_plan = envelope.get("activation_plan") if isinstance(envelope, dict) else None
        if isinstance(normalized, dict) and isinstance(frozen_plan, dict) and str(
            frozen_plan.get("activation_mode") or ""
        ).lower() == "enforced":
            # Current V3 jobs preserve only review evidence/provenance; local
            # patches are archival compatibility data, never forward input.
            return {}
        patch = request.metadata.get("resolved_retry_patch")
        provenance = request.metadata.get("resolved_retry_provenance")
        if not isinstance(patch, dict) or not isinstance(provenance, dict):
            return {}
        if (
            provenance.get("authority") != "v3_product_api"
            or str(provenance.get("activation_plan_id") or "") != plan.plan_id
            or str(provenance.get("activation_plan_fingerprint") or "") != plan.fingerprint
        ):
            return {}
        return dict(patch)

    @staticmethod
    def _ledger_capability_projection(
        raw_cluster: dict[str, Any],
        plan: CapabilityActivationPlan,
    ) -> dict[str, Any]:
        """Project only active executor facts into the enforced ledger.

        This is a labelled migration adapter from accepted executor output,
        not a downstream fallback to Visual Capability Cluster metadata.  It
        keeps generic capability facts available while refusing to move the
        full, mutable cluster payload across the Provider boundary.
        """

        active = set(plan.dependency_order)
        guarded_keys = {
            "human_photorealism_guidance": {"human_realism"},
            "strong_reference_closure_package": {"portrait_identity"},
            "resolved_reference_policy_package": {"reference_channel_policy"},
            "adaptive_reference_selection_plan": {
                "portrait_identity",
                "product_identity",
                "scene_continuity",
            },
            "identity_repair_strategy_plan": {"portrait_identity"},
            "mode_execution_policy": {"suite_direction"},
            "role_specific_generation_plan": {"suite_direction"},
            "mode_role_recipe": {"suite_direction"},
            "mode_quality_profile": {"suite_direction"},
            "reference_truth_package": {
                "portrait_identity",
                "product_identity",
                "nonhuman_subject_identity",
                "scene_continuity",
            },
            "subject_continuity_asset_package": {
                "portrait_identity",
                "product_identity",
                "nonhuman_subject_identity",
                "scene_continuity",
            },
            "portrait_bone_structure_lock": {"portrait_identity"},
            "styling_delta_policy": {"portrait_identity"},
            "portrait_reference_influence_policy": {"portrait_identity"},
            "portrait_reference_balance_policy": {"portrait_identity"},
        }
        projection: dict[str, Any] = {}
        for key, required_capabilities in guarded_keys.items():
            value = raw_cluster.get(key)
            if not isinstance(value, dict) or not (active & required_capabilities):
                continue
            projection[key] = dict(value)
        if "suite_direction" in active and isinstance(raw_cluster.get("mode_role_plan_reconciled_to_series"), bool):
            projection["mode_role_plan_reconciled_to_series"] = raw_cluster["mode_role_plan_reconciled_to_series"]
        return projection

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
            metadata=self._capability_activation_plan_metadata(request),
        )
        explicit_required = self._required_capability_ids(request)
        missing_required = [item for item in explicit_required if not plan.is_active(item)]
        if missing_required:
            raise CapabilityActivationError(
                "required capability is unavailable or not safely activated: " + ", ".join(missing_required)
            )
        return plan

    @staticmethod
    def _capability_activation_plan_metadata(
        request: ScenarioRuntimeRequest,
    ) -> dict[str, Any] | None:
        metadata = dict(request.metadata or {})
        planning_metadata = metadata.get("professional_planning_metadata")
        frozen_metadata: dict[str, Any] = (
            dict(planning_metadata)
            if isinstance(planning_metadata, dict)
            else {}
        )
        if metadata.get("professional_character_card_preparation") is True:
            if isinstance(planning_metadata, dict):
                frozen_metadata["professional_planning_metadata"] = dict(planning_metadata)
            for key in (
                "professional_mode",
                "professional_identity_reference_strategy",
                "professional_reference_stage",
                "professional_character_card_preparation",
                "professional_character_card_stage",
                "professional_character_card_slot",
                "professional_character_card_source_class",
                "professional_character_card_attempt_round",
                "professional_character_card_reference_output_ids",
                "professional_anchor_reference_assets",
                "generation_channel",
                "mcp_operation_id",
                "mcp_materialization",
            ):
                if key in metadata:
                    frozen_metadata[key] = metadata.get(key)
        return frozen_metadata or None

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
            job_id=stable_id(
                "capability_job",
                request.user_input,
                request.optional_brand_id,
                resolution.manifest.scenario_id,
                request.metadata.get("v3_job_instance_id"),
            ),
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
        # A historical trusted plan must preserve its own execution semantics
        # for a retry. New work is Brain-owned enforced mode only: deployment
        # configuration cannot silently reactivate legacy keyword/regex
        # inference or shadow-only local semantics.
        frozen = request.metadata.get("capability_activation_plan") if request is not None else None
        if isinstance(frozen, dict):
            frozen_mode = str(frozen.get("activation_mode") or "").lower()
            if frozen_mode in {"legacy", "shadow", "enforced"}:
                return frozen_mode
        configured = os.getenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced").strip().lower()
        return "enforced" if configured != "enforced" else configured

    def _require_trusted_frozen_capability_plan_boundary(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
    ) -> None:
        frozen = request.metadata.get("capability_activation_plan")
        if not isinstance(frozen, dict) or not frozen.get("plan_id"):
            return
        if not request.trusted_capability_plan_reuse:
            raise CapabilityActivationError("untrusted_frozen_capability_activation_plan")
        try:
            plan = CapabilityActivationPlan.model_validate(frozen)
        except Exception as exc:
            raise CapabilityActivationError("capability_activation_plan_invalid") from exc
        provenance = request.metadata.get("capability_plan_provenance")
        if not self._trusted_frozen_plan_provenance_matches(plan, provenance):
            raise CapabilityActivationError("capability_activation_plan_provenance_mismatch")
        if plan.template_id != self._template_id(request, resolution):
            raise CapabilityActivationError("frozen capability plan template does not match this job")
        if plan.scenario_id != resolution.manifest.scenario_id:
            raise CapabilityActivationError("frozen capability plan scenario does not match this job")

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
        professional = preparation.professional_mode_preparation
        if professional is not None:
            context = professional.context
            metadata["professional_mode"] = True
            if context is not None:
                planning_metadata = context.planning_metadata
                stage = self._professional_character_card_stage(metadata, planning_metadata)
                if stage == "body_silhouette":
                    body_contract = self._professional_body_silhouette_source_contract(
                        planning_metadata
                    )
                    if isinstance(body_contract, dict):
                        # Persist only the Body-owned source contract for Body
                        # Silhouette.  Face Identity remains reference-channel
                        # continuity and must not project model-card/photo
                        # quality semantics into Body prompts.
                        metadata["professional_body_silhouette_source_contract"] = body_contract
                else:
                    quality_contract = planning_metadata.get(
                        "professional_face_identity_quality_contract"
                    )
                    if isinstance(quality_contract, dict):
                        # Persist only the small, typed semantic contract needed
                        # to explain the frozen Professional quality objective.
                        # Binding records and raw reference plans remain private
                        # to the runtime and are not projected here.
                        metadata["professional_face_identity_quality_contract"] = dict(quality_contract)
            metadata["professional_mode_execution"] = {
                "status": professional.status,
                "binding": (
                    dict(context.consumer_context.identity_binding)
                    if context is not None
                    else None
                ),
                "reference_admission": (
                    dict(context.planning_metadata)
                    if context is not None
                    else {
                        "status": "blocked",
                        "reason_codes": list(professional.reason_codes),
                    }
                ),
                "evidence_packet": (
                    context.evidence_packet.model_dump(mode="json")
                    if context is not None
                    else None
                ),
                "creative_direction_owner": "remote_v3_llm_brain",
                "shared_execution_owner": "v3_shared_runtime",
            }
        library_binding = preparation.visual_asset_library_binding
        if library_binding is not None:
            # This projection is deliberately opaque: ordinary project status
            # can prove that a frozen asset binding was honoured without
            # exposing source paths, candidate details, prompts or hashes.
            metadata["visual_asset_library_execution"] = {
                "contract_version": library_binding.contract_version,
                "binding_set_id": library_binding.binding_set_id,
                "claim_count": len(library_binding.claims),
                "asset_types": sorted({item.asset_type for item in library_binding.claims}),
                "creative_direction_owner": "remote_v3_llm_brain",
                "shared_execution_owner": "v3_shared_runtime",
            }
        return metadata

    @staticmethod
    def _renderer_channel_metadata(request: ScenarioRuntimeRequest) -> dict[str, Any]:
        """Carry an explicit renderer channel into every frozen generation plan.

        The MCP handoff is a renderer transport choice, not creative input. It
        must nevertheless survive the planning-to-materialization boundary so
        the shared output record can truthfully distinguish MCP from Provider.
        The default remains Provider for historical and ordinary jobs.
        """

        channel = str(request.metadata.get("generation_channel") or "").strip().lower()
        if channel not in {"provider", "mcp"}:
            return {}
        payload: dict[str, Any] = {"generation_channel": channel}
        operation_id = str(request.metadata.get("mcp_operation_id") or "").strip()
        if channel == "mcp" and operation_id:
            payload["mcp_operation_id"] = operation_id
        materialization = request.metadata.get("mcp_materialization")
        if (
            channel == "mcp"
            and isinstance(materialization, dict)
            and str(materialization.get("handoff_id") or "").strip()
        ):
            payload["mcp_materialization"] = dict(materialization)
        return payload

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
        remote_brain_outcome = getattr(exc, "remote_creative_brain_outcome", None)
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
                **(
                    {"remote_creative_brain_outcome": dict(remote_brain_outcome)}
                    if isinstance(remote_brain_outcome, dict)
                    else {}
                ),
            },
        )

    def _coerce_request(self, request: ScenarioRuntimeRequest | dict[str, Any]) -> ScenarioRuntimeRequest:
        if not isinstance(request, ScenarioRuntimeRequest) and isinstance(request, dict):
            if "trusted_professional_anchor_view_decision_reuse" in request:
                raise ValueError(
                    "trusted_professional_anchor_view_decision_reuse is an internal runtime flag"
                )
        runtime_request = request if isinstance(request, ScenarioRuntimeRequest) else ScenarioRuntimeRequest.model_validate(request)
        return self._with_uploaded_reference_snapshot(runtime_request)

    @staticmethod
    def _with_uploaded_reference_snapshot(request: ScenarioRuntimeRequest) -> ScenarioRuntimeRequest:
        """Project declared upload truth into the frozen reference context.

        A browser Project normally already persists this context. Stateless
        callers (including the conversation-only Local MCP relay) still carry
        the same declared ``uploaded_assets`` contract. Leaving that evidence
        outside the snapshot would make the reference-channel policy appear
        active without a source binding, allowing a full source frame to
        bypass the frozen channel policy at materialization.

        This is intentionally an ingress-only, non-creative projection. It
        copies the caller-declared role and technical file identity without
        inferring a subject, scene, style, or prompt wording. Existing Project
        context is retained and duplicate sources are collapsed by their
        stable asset/file identity.
        """

        uploaded_assets = list(request.uploaded_assets or [])
        if not uploaded_assets:
            return request

        metadata = dict(request.metadata or {})
        existing_context = metadata.get("project_context_snapshot")
        project_context = dict(existing_context) if isinstance(existing_context, dict) else {}
        existing_references = project_context.get("uploaded_reference_assets")
        merged_references = [dict(item) for item in existing_references if isinstance(item, dict)] if isinstance(existing_references, list) else []
        seen = {
            (
                str(item.get("asset_id") or item.get("asset_ref_id") or "").strip(),
                str(item.get("file_path") or "").strip(),
            )
            for item in merged_references
        }
        for asset in uploaded_assets:
            role = asset.role.value if hasattr(asset.role, "value") else asset.role
            projected = {
                "asset_id": asset.asset_id,
                "role": str(role or "unknown_reference"),
                "source_type": "uploaded",
                "file_path": asset.file_path,
                "uri": asset.uri,
                "filename": asset.filename,
                "mime_type": asset.mime_type,
                "metadata": dict(asset.metadata or {}),
            }
            key = (str(projected["asset_id"] or "").strip(), str(projected["file_path"] or "").strip())
            if key in seen:
                continue
            seen.add(key)
            merged_references.append(projected)

        project_context["uploaded_reference_assets"] = merged_references
        metadata["project_context_snapshot"] = project_context
        return request.model_copy(update={"metadata": metadata})

    def _job_scope(self, request: ScenarioRuntimeRequest, resolution: ScenarioPackResolution) -> str:
        metadata = dict(request.metadata or {})
        parts = [
            metadata.get("project_id"),
            metadata.get("template_id") or metadata.get("template_manifest_id") or resolution.manifest.scenario_id,
            metadata.get("project_job_sequence"),
        ]
        return "::".join(str(part) for part in parts if part not in {None, ""})

    def _runtime_job_id(self, request: ScenarioRuntimeRequest, resolution) -> str:
        return stable_id(
            "job",
            request.user_input,
            request.optional_brand_id,
            self._job_scope(request, resolution),
            request.metadata.get("v3_job_instance_id"),
        )

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
        request: ScenarioRuntimeRequest,
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
        # A planning result is also the source of any later provider request.
        # Carry the same immutable execution records down to every planned
        # asset now, rather than making a non-rendering consumer reconstruct a
        # partial request from mutable result-level metadata.  Central Brain's
        # generation loop uses these identical per-asset fields.
        frozen_provider_metadata = {
            key: activation_metadata.get(key)
            for key in (
                "capability_activation_plan",
                "normalized_v3_job_intent",
                "template_deliverable_plan",
                "resolved_constraint_ledger",
                "capability_execution_envelope",
            )
            if activation_metadata.get(key) is not None
        }
        # The normalized intent is the resolved canvas/count authority.  The
        # Central Brain's historical planning object can still carry a
        # template default (for example General's old portrait default), so
        # reassert the frozen values on every materialized output instead of
        # letting an earlier plan silently overwrite an explicit user canvas.
        # This is transport integrity only; it does not construct or edit
        # renderer language.
        frozen_provider_metadata.update(
            {
                "requested_image_count": preparation.normalized_job_intent.effective_image_count,
                "requested_image_size": preparation.normalized_job_intent.effective_image_size,
            }
        )
        explicit_aspect_ratio = str(
            request.metadata.get("requested_image_aspect_ratio") or ""
        ).strip()
        if explicit_aspect_ratio:
            frozen_provider_metadata["requested_image_aspect_ratio"] = explicit_aspect_ratio
            frozen_provider_metadata["requested_image_aspect_ratio_source"] = str(
                request.metadata.get("requested_image_aspect_ratio_source")
                or "remote_brain_user_intent"
            )
        frozen_provider_metadata.update(
            self._frozen_professional_provider_metadata(preparation)
        )
        resolved_aspect_metadata = {}
        if explicit_aspect_ratio:
            resolved_aspect_metadata = {
                "requested_image_aspect_ratio": explicit_aspect_ratio,
                "requested_image_aspect_ratio_source": str(
                    request.metadata.get("requested_image_aspect_ratio_source")
                    or "remote_brain_user_intent"
                ),
            }
        generation_plans = [
            generation_plan.model_copy(
                update={
                    "metadata": {
                        **dict(generation_plan.metadata),
                        **frozen_provider_metadata,
                    }
                }
            )
            for generation_plan in result.generation_plans
        ]
        return result.model_copy(
            update={
                "creative_job": creative_job,
                "generation_plans": generation_plans,
                "metadata": {
                    **dict(result.metadata),
                    **activation_metadata,
                    **public_specialized_metadata,
                    **resolved_aspect_metadata,
                },
            }
        )

    @staticmethod
    def _frozen_professional_provider_metadata(
        preparation: CapabilityPreparationResult,
    ) -> dict[str, Any]:
        """Project only validated serial-anchor selectors from the frozen plan.

        This helper is deliberately used both before Provider execution and
        when returning the enriched result.  Reading mutable request metadata
        here would let a caller change the 2/3/5 evidence budget after the
        capability plan was frozen.
        """

        plan_metadata = (
            dict(preparation.activation_plan.metadata or {})
            if preparation.activation_plan is not None
            else {}
        )
        professional_strategy = str(
            plan_metadata.get("professional_identity_reference_strategy") or ""
        ).strip()
        professional_stage = str(
            plan_metadata.get("professional_reference_stage") or ""
        ).strip()
        if (
            plan_metadata.get("professional_anchor_pack_preparation") is True
            and professional_strategy == "serial_anchor_pack_root_reuse_v1"
            and professional_stage in {
                "standard_front",
                "left_front_25",
                "three_quarter",
                "profile",
                "right_front_25",
                "reverse_three_quarter",
                "rear_head",
            }
        ):
            frozen = {
                "professional_identity_reference_strategy": professional_strategy,
                "professional_reference_stage": professional_stage,
            }
            capture_scope = str(plan_metadata.get("professional_anchor_capture_scope") or "").strip()
            if capture_scope:
                frozen["professional_anchor_capture_scope"] = capture_scope
            reference_assets = plan_metadata.get("professional_anchor_reference_assets")
            if isinstance(reference_assets, list):
                frozen["professional_anchor_reference_assets"] = reference_assets
            if plan_metadata.get("professional_anchor_initial_multi_source") is not None:
                frozen["professional_anchor_initial_multi_source"] = plan_metadata.get(
                    "professional_anchor_initial_multi_source"
                )
            return frozen
        if (
            plan_metadata.get("professional_character_card_preparation") is True
            and professional_strategy == "character_card_shared_identity_v1"
            and professional_stage in {
                "character_card_expression_set",
                "character_card_body_silhouette",
            }
        ):
            stage = str(plan_metadata.get("professional_character_card_stage") or "").strip()
            slot_key = str(plan_metadata.get("professional_character_card_slot") or "").strip()
            if stage not in {"expression_set", "body_silhouette"} or not slot_key:
                return {}
            frozen = {
                "professional_identity_reference_strategy": professional_strategy,
                "professional_reference_stage": professional_stage,
                "professional_character_card_preparation": True,
                "professional_character_card_stage": stage,
                "professional_character_card_slot": slot_key,
            }
            source_class = plan_metadata.get("professional_character_card_source_class")
            if source_class is not None:
                frozen["professional_character_card_source_class"] = source_class
            candidate_index = plan_metadata.get("professional_character_card_candidate_index")
            if candidate_index is not None:
                frozen["professional_character_card_candidate_index"] = candidate_index
            candidate_count = plan_metadata.get("professional_character_card_candidate_count")
            if candidate_count is not None:
                frozen["professional_character_card_candidate_count"] = candidate_count
            if stage == "body_silhouette":
                for key in (
                    "professional_character_card_body_refresh_source_mode",
                    "professional_character_card_body_model_context",
                    "professional_character_card_body_refresh_contract_required",
                    "professional_character_card_body_refresh_presentation_intent",
                    "professional_character_card_face_view_binding",
                    "professional_body_refresh_analysis_context",
                ):
                    if key in plan_metadata:
                        frozen[key] = plan_metadata.get(key)
            attempt_round = plan_metadata.get("professional_character_card_attempt_round")
            if attempt_round is not None:
                frozen["professional_character_card_attempt_round"] = attempt_round
            reference_output_ids = plan_metadata.get("professional_character_card_reference_output_ids")
            if isinstance(reference_output_ids, list):
                frozen["professional_character_card_reference_output_ids"] = [
                    str(item).strip()
                    for item in reference_output_ids
                    if str(item).strip()
                ]
            reference_assets = plan_metadata.get("professional_anchor_reference_assets")
            if isinstance(reference_assets, list):
                frozen["professional_anchor_reference_assets"] = reference_assets
            planning_metadata = plan_metadata.get("professional_planning_metadata")
            if isinstance(planning_metadata, dict):
                frozen["professional_planning_metadata"] = dict(planning_metadata)
            for key in ("generation_channel", "mcp_operation_id", "mcp_materialization"):
                if key in plan_metadata:
                    frozen[key] = plan_metadata.get(key)
            return frozen
        return {}

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
        brain_uploaded_assets = self._brain_reference_assets_without_body(
            request,
            [asset.model_dump(mode="json") for asset in self._uploaded_assets(request)],
        )
        metadata = {
            **dict(request.metadata),
            "scenario_id": resolution.manifest.scenario_id,
            "scenario_display_name": resolution.manifest.display_name,
            "scenario_status": resolution.status.value,
            "scenario_mode_id": resolution.selected_mode_id,
            "scenario_preset_id": resolution.selected_preset_id,
            "scenario_parameters": parameters,
            "platform_profile": selection.platform_profile if selection is not None else None,
            "uploaded_assets": brain_uploaded_assets,
            "uploaded_asset_ids": [str(asset.get("asset_id")) for asset in brain_uploaded_assets],
            "reference_assets": self._brain_reference_assets_without_body(
                request,
                self._reference_assets_from_request_metadata(request),
            ),
            "product_profile": dict(request.product_profile),
        }
        metadata["professional_anchor_reference_assets"] = self._brain_reference_assets_without_body(
            request,
            metadata.get("professional_anchor_reference_assets"),
        )
        # The Brain receives the validated typed profile, never the Body
        # source admission IDs or its internal provenance proof.
        metadata.pop("professional_character_card_body_source_admission", None)
        if quality_mode is not None:
            metadata["quality_mode"] = quality_mode
        if brain_result is not None:
            metadata["llm_brain"] = brain_result.safe_metadata()
        return metadata

    @staticmethod
    def _brain_reference_assets_without_body(
        request: ScenarioRuntimeRequest,
        references: Any,
    ) -> list[dict[str, Any]]:
        """Keep Body source evidence out of the Brain's raw reference channel."""

        if not isinstance(references, list):
            return []
        metadata = request.metadata
        stage = str(metadata.get("professional_character_card_stage") or "").strip().lower()
        slot = str(metadata.get("professional_character_card_slot") or "").strip().lower()
        if stage != "body_silhouette" or not slot.startswith("body."):
            return [dict(item) for item in references if isinstance(item, dict)]
        return [
            dict(item)
            for item in references
            if isinstance(item, dict) and item.get("role") != "body_proportion_reference"
        ]

    def _body_proportion_profile_for_brain(
        self,
        request: ScenarioRuntimeRequest,
        *,
        stage: str,
    ) -> BodyProportionEvidenceProfile | BodyMorphologyEvidenceProfile | None:
        """Resolve the one trusted Body source-analysis seam before Brain.

        Reference-assisted Professional Body requests must cross the
        server-owned source-analysis boundary before the Brain sees Body
        proportion context.  The default runtime has no analyzer configured,
        so it fails closed instead of deriving bands from counts or hashes.
        Existing inference-first, ordinary, Face, and legacy requests do not
        inherit observed Body profiles.
        """

        metadata = request.metadata
        raw_receipt = metadata.get("professional_body_proportion_analysis_receipt")
        source_mode = str(
            metadata.get("professional_character_card_body_refresh_source_mode") or ""
        ).strip().lower()
        character_stage = str(
            metadata.get("professional_character_card_stage") or ""
        ).strip().lower()
        slot = str(metadata.get("professional_character_card_slot") or "").strip().lower()
        body_stage = character_stage == "body_silhouette" and slot.startswith("body.")
        professional = self._is_professional_mode_selected(request)
        context_is_fresh_candidate = (
            metadata.get("professional_character_card_candidate_index") is not None
        )

        if not professional or not body_stage:
            # A typed observed receipt is only meaningful in the strict Body
            # source-analysis stage.  Do not let same-named internal fields
            # leak into Expression, Face, ordinary, or legacy Brain requests.
            return None
        if source_mode == "inference_first":
            if raw_receipt is not None:
                raise CapabilityActivationError(
                    "body_proportion_analysis_source_mode_invalid"
                )
            if getattr(request, "body_refresh_analysis_context", None) is not None:
                raise CapabilityActivationError(
                    "body_proportion_analysis_source_mode_invalid"
                )
            return None
        if source_mode != "reference_assisted":
            if raw_receipt is not None:
                raise CapabilityActivationError(
                    "body_proportion_analysis_source_mode_invalid"
                )
            return None
        frozen_context = getattr(request, "body_refresh_analysis_context", None)
        if frozen_context is not None:
            if not isinstance(frozen_context, BodyRefreshAnalysisContext):
                raise CapabilityActivationError("body_refresh_analysis_context_untrusted")
            requested_age_scope = str(
                metadata.get("professional_character_card_body_refresh_target_age_scope") or ""
            ).strip()
            if requested_age_scope and requested_age_scope != BODY_REFRESH_REFERENCE_AGE_SCOPE:
                raise CapabilityActivationError("body_refresh_target_age_scope_mismatch")
            if frozen_context.target_age_scope != BODY_REFRESH_REFERENCE_AGE_SCOPE:
                raise CapabilityActivationError("body_refresh_target_age_scope_mismatch")
            safe_context = metadata.get("professional_body_refresh_analysis_context")
            if not isinstance(safe_context, dict) or safe_context != frozen_context.safe_metadata():
                raise CapabilityActivationError("body_proportion_analysis_context_mismatch")
            if context_is_fresh_candidate:
                try:
                    require_current_body_refresh_analysis_context(frozen_context)
                except ValueError as exc:
                    raise CapabilityActivationError(str(exc)) from exc
            return frozen_context.profile
        if raw_receipt is not None:
            requested_age_scope = str(
                metadata.get("professional_character_card_body_refresh_target_age_scope") or ""
            ).strip()
            if requested_age_scope != BODY_REFRESH_REFERENCE_AGE_SCOPE:
                raise CapabilityActivationError("body_refresh_target_age_scope_mismatch")
            if context_is_fresh_candidate:
                raise CapabilityActivationError("body_proportion_analysis_context_missing")
            if not isinstance(
                raw_receipt,
                (BodyProportionEvidenceProfile, BodyMorphologyEvidenceProfile),
            ):
                raise CapabilityActivationError("body_proportion_analysis_untrusted")
            return raw_receipt

        # Official Character Card stage jobs must arrive with the frozen
        # refresh context.  The direct analysis-only smoke seam remains able
        # to analyze an ephemeral envelope, but no candidate may fall back to
        # per-request analysis.
        if (
            metadata.get("professional_character_card_candidate_index") is not None
            or "professional_body_refresh_analysis_context" in metadata
        ):
            raise CapabilityActivationError("body_proportion_analysis_context_missing")

        internal_assets = list(getattr(request, "body_source_analysis_assets", []) or [])
        if not internal_assets:
            raise CapabilityActivationError("body_proportion_analysis_source_not_ready")
        body_assets = []
        for asset in internal_assets:
            if not isinstance(asset, BodySourceAnalysisAssetEnvelope):
                raise CapabilityActivationError("body_proportion_analysis_untrusted")
            body_assets.append(asset.to_analyzer_record())
        try:
            return self.body_proportion_source_analysis_adapter.analyze(
                body_assets,
                source_mode="reference_assisted",
                profile_version="v1",
                analyzer=self.body_proportion_source_analyzer,
            )
        except BodyProportionAnalysisError as exc:
            raise CapabilityActivationError(str(exc)) from exc

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
        frozen = self._frozen_remote_creative_brain_for_execution(
            request,
            resolution,
            stage=stage,
            template_capability_policy=template_capability_policy,
        )
        if frozen is not None:
            return frozen
        base_metadata = self._brain_runtime_metadata(request, resolution, quality_mode=quality_mode)
        if self._is_professional_mode_selected(request):
            # The remote Brain receives only the explicit, typed creative
            # evidence. Server job/project records and raw reference-plan
            # payloads remain local provenance and never become Brain input.
            safe_binding = request.metadata.get("professional_mode_binding")
            safe_admission = request.metadata.get("professional_planning_metadata")
            # Keep the raw binding snapshot available to the adapter's local
            # trust gate.  build_request() exposes only public-safe typed
            # markers to the remote Brain; the binding record itself must not
            # cross that boundary.
            base_metadata.pop("professional_reference_channel_plans", None)
            base_metadata.pop("professional_planning_metadata", None)
            # The source-analysis receipt is an in-memory typed projection;
            # never forward an isolated raw/public value from the request.
            base_metadata.pop("professional_body_proportion_analysis_receipt", None)
            base_metadata["professional_mode"] = True
            body_profile = self._body_proportion_profile_for_brain(request, stage=stage)
            if body_profile is not None:
                base_metadata["professional_body_proportion_analysis_receipt"] = body_profile
            if isinstance(safe_binding, dict):
                base_metadata["professional_mode_binding"] = dict(safe_binding)
            if isinstance(safe_admission, dict):
                base_metadata["professional_reference_admission"] = {
                    key: safe_admission[key]
                    for key in (
                        "reference_admission_status",
                        "reference_evidence_packet_contract_version",
                        "admitted_evidence_ids",
                    )
                    if key in safe_admission
                }
                stage = self._professional_character_card_stage(base_metadata, safe_admission)
                if stage == "body_silhouette":
                    body_contract = self._professional_body_silhouette_source_contract(
                        safe_admission
                    )
                    if isinstance(body_contract, dict):
                        base_metadata["professional_body_silhouette_source_contract"] = (
                            body_contract
                        )
                else:
                    quality_contract = safe_admission.get("professional_face_identity_quality_contract")
                    if isinstance(quality_contract, dict):
                        # This is a typed semantic contract only.  Raw binding,
                        # paths, and server-owned reference plans never cross the
                        # Brain boundary.
                        base_metadata["professional_face_identity_quality_contract"] = dict(quality_contract)
        if self._has_visual_asset_library_binding(request):
            # New jobs carry a generic library binding, never the historical
            # Professional-mode record. The Brain gets only authority facts;
            # full snapshots and resolved reference paths remain local.
            safe_binding = request.metadata.get("visual_asset_library_binding")
            base_metadata.pop("frozen_visual_asset_binding_set", None)
            base_metadata.pop("visual_asset_library_reference_assets", None)
            base_metadata.pop("visual_asset_library_formal_face_chain_bindings", None)
            base_metadata.pop("visual_asset_library_execution", None)
            if not isinstance(safe_binding, dict):
                raise CapabilityActivationError("visual_asset_library_brain_binding_missing")
            base_metadata["visual_asset_library_binding"] = dict(safe_binding)
        slot_delta_timeout = self._character_card_slot_delta_transport_timeout_seconds(request)
        if slot_delta_timeout is not None:
            base_metadata["_brain_transport_timeout_seconds"] = slot_delta_timeout
        uploaded_assets = [asset.model_dump(mode="json") for asset in self._uploaded_assets(request)]
        brain_request = self.llm_brain_adapter.build_request(
            user_input=request.user_input,
            job_id=self._runtime_job_id(request, resolution),
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
        blocked_by_pose_contract = self._professional_ecommerce_pose_contract_result(brain_request)
        if blocked_by_pose_contract is not None:
            return blocked_by_pose_contract
        blocked_by_preflight = self._ecommerce_creative_risk_preflight_result(brain_request)
        if blocked_by_preflight is not None:
            return blocked_by_preflight
        return self.llm_brain_adapter.run(brain_request)

    @staticmethod
    def _professional_ecommerce_pose_contract_result(
        brain_request: BrainRunRequest,
    ) -> BrainRunResult | None:
        """Fail closed before remote Brain when a supplied pose contract is invalid."""

        if str(brain_request.scenario_id or "").strip().lower() != "ecommerce":
            return None
        context = brain_request.metadata.get("ecommerce_creative_context")
        if not isinstance(context, dict):
            return None
        raw_contract = context.get("professional_ecommerce_pose_contract")
        if not isinstance(raw_contract, dict):
            return None
        if raw_contract.get("status") != "invalid":
            return None
        result = build_remote_required_result(
            brain_request,
            "professional_ecommerce_pose_contract_invalid",
        )
        result.audit = {
            **dict(result.audit or {}),
            "professional_ecommerce_pose_contract_invalid": True,
            "creative_fallback_executed": False,
        }
        return result

    @staticmethod
    def _ecommerce_creative_risk_preflight_result(
        brain_request: BrainRunRequest,
    ) -> BrainRunResult | None:
        """Fail closed before remote Brain when E-Commerce preflight says stop."""

        if str(brain_request.scenario_id or "").strip().lower() != "ecommerce":
            return None
        context = brain_request.metadata.get("ecommerce_creative_context")
        if not isinstance(context, dict):
            return None
        raw_preflight = context.get("creative_risk_preflight")
        if not isinstance(raw_preflight, dict):
            return None
        if raw_preflight.get("status") == "invalid":
            result = build_remote_required_result(
                brain_request,
                "ecommerce_creative_risk_preflight_invalid",
            )
            result.audit = {
                **dict(result.audit or {}),
                "ecommerce_creative_risk_preflight_stop": True,
                "ecommerce_creative_risk_preflight_invalid": True,
                "creative_fallback_executed": False,
            }
            return result
        try:
            preflight = EcommerceCreativeRiskPreflight.model_validate(raw_preflight)
        except ValueError:
            result = build_remote_required_result(
                brain_request,
                "ecommerce_creative_risk_preflight_invalid",
            )
            result.audit = {
                **dict(result.audit or {}),
                "ecommerce_creative_risk_preflight_stop": True,
                "ecommerce_creative_risk_preflight_invalid": True,
                "creative_fallback_executed": False,
            }
            return result
        gate = preflight.planning_gate(
            requested_image_count=brain_request.requested_image_count
        )
        if gate.get("status") != "blocked":
            return None
        result = build_remote_required_result(
            brain_request,
            "ecommerce_creative_risk_preflight_blocked",
        )
        result.audit = {
            **dict(result.audit or {}),
            "ecommerce_creative_risk_preflight_stop": True,
            "ecommerce_creative_risk_preflight_gate": gate,
            "creative_fallback_executed": False,
        }
        return result

    def _frozen_remote_creative_brain_for_execution(
        self,
        request: ScenarioRuntimeRequest,
        resolution,
        *,
        stage: str,
        template_capability_policy: TemplateCapabilityPolicy | None,
    ) -> BrainRunResult | None:
        """Reuse the server-pinned remote creative answer during execution.

        Planning is the only stage that may ask the remote Brain to create a
        direction. Generation and bounded retry consume the same verified
        answer with the frozen activation plan; another Brain call would make
        one logical job non-deterministic and can block a shared retry before
        it reaches the image Provider.
        """

        if stage == "plan" and request.metadata.get("professional_anchor_stage_plan_reuse") is not True:
            return None
        frozen = request.metadata.get("frozen_remote_creative_brain")
        if frozen is None:
            return None
        if not isinstance(frozen, dict):
            raise CapabilityActivationError("frozen_remote_creative_brain_invalid")
        plan = request.metadata.get("capability_activation_plan")
        brain_payload = frozen.get("brain_result")
        expected_template_id = self._template_id(request, resolution)
        if (
            frozen.get("schema_version") != "v3_frozen_remote_creative_brain_v1"
            or not isinstance(plan, dict)
            or not isinstance(brain_payload, dict)
            or str(frozen.get("template_id") or "") != expected_template_id
            or str(frozen.get("scenario_id") or "") != resolution.manifest.scenario_id
            or str(frozen.get("capability_plan_id") or "") != str(plan.get("plan_id") or "")
            or str(frozen.get("capability_plan_fingerprint") or "") != str(plan.get("fingerprint") or "")
        ):
            raise CapabilityActivationError("frozen_remote_creative_brain_binding_mismatch")
        try:
            result = BrainRunResult.model_validate(brain_payload)
        except ValueError as exc:
            raise CapabilityActivationError("frozen_remote_creative_brain_invalid") from exc
        if not result.llm_used or result.fallback_used:
            raise CapabilityActivationError("frozen_remote_creative_brain_not_remote")
        result.audit = {
            **dict(result.audit or {}),
            "frozen_execution_reuse": True,
            "frozen_execution_stage": stage,
        }
        return result

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
        if request.metadata.get("professional_anchor_pack_preparation") is True:
            planned = [*planned, "portrait_identity", "reference_channel_policy", "human_realism"]
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
            # The Product API may carry the same project reference through an
            # explicit continuation binding and an uploaded-asset binding.
            # They are two provenance paths for one source, not two provider
            # inputs.  Normalize them before the frozen job metadata is
            # created so all downstream consumers see one reference truth.
            return self._dedupe_reference_assets([dict(item) for item in refs if isinstance(item, dict)])
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
        if policy_id == "product_truth":
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
