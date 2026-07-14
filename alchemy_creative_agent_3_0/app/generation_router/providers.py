"""V3-owned generation provider contracts."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import re
import threading
import time
from typing import Any

from pydantic import BaseModel, Field

from ..creative_core.prompt_language import (
    product_language_allowed,
    split_positive_and_negative_prompt,
    strip_negated_product_phrases,
)
from ..creative_core.rules import stable_id
from ..condition_engine.providers import ProviderCapabilities
from ..schemas import AssetSpec, CandidateResult, ConditionPlan, GenerationPlan, LayoutPlan, PromptCompilationResult
from ..shared_capabilities.visual_cluster.casebook_recipes import provider_casebook_prompt_lines
from ..shared_capabilities.visual_cluster.adaptive_reference import infer_target_framing, infer_target_view


class GenerationRequest(BaseModel):
    asset_spec: AssetSpec | None = None
    layout_plan: LayoutPlan | None = None
    prompt_compilation: PromptCompilationResult
    condition_plan: ConditionPlan
    generation_plan: GenerationPlan
    metadata: dict = Field(default_factory=dict)


class GenerationResponse(BaseModel):
    candidates: list[CandidateResult]
    provider_metadata: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class GenerationProvider:
    """Provider interface for V3 generation and deterministic mock generation."""

    provider_name = "generation_provider"
    provider_version = "v3.2-generation-loop-mvp"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_generation=True,
            supports_batch=True,
            requires_gpu=False,
            requires_network=False,
            is_deterministic=True,
        )

    def is_available(self) -> bool:
        return True

    def health_check(self) -> dict:
        return {"provider_name": self.provider_name, "available": self.is_available()}

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        raise NotImplementedError

    def _retry_patch(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            patch = projection.get("retry_patch") if isinstance(projection, dict) else None
            return dict(patch) if isinstance(patch, dict) else {}
        patch = request.metadata.get("visual_retry_patch")
        return dict(patch) if isinstance(patch, dict) else {}

    def _retry_attempt(self, request: GenerationRequest) -> int:
        raw = request.metadata.get("visual_auto_retry_attempt") or request.metadata.get("retry_attempt") or 0
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            return 0

    def _string_list(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [part.strip() for part in value.split(",") if part.strip()]
        return []

    def _mode_role_recipe(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            if isinstance(projection, dict) and projection.get("template_id") == "ecommerce_template":
                # E-Commerce's Brain direction already belongs to the
                # template deliverable plan.  Do not relabel it as a generic
                # mode recipe or reintroduce a shared role vocabulary.
                return {}
            deliverables = projection.get("deliverables") if isinstance(projection, dict) else None
            if not isinstance(deliverables, list):
                return {}
            priority = getattr(request.asset_spec, "priority", None) if request.asset_spec is not None else None
            try:
                index = max(1, int(priority or 1))
            except (TypeError, ValueError):
                index = 1
            item = deliverables[index - 1] if index <= len(deliverables) else None
            if not isinstance(item, dict):
                return {}
            direction = str(item.get("image_intent") or "").strip()
            if not direction:
                return {}
            metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
            specialized_contract = metadata.get("specialized_role_contract")
            if isinstance(specialized_contract, dict) and specialized_contract.get("role_key"):
                # This contract entered the provider projection through the
                # frozen TemplateDeliverablePlan.  It is not a raw metadata
                # fallback: only active specialized templates can bind this
                # record before the execution envelope is frozen.
                role = dict(specialized_contract)
                role_metadata = role.get("metadata") if isinstance(role.get("metadata"), dict) else {}
                role["role_key"] = str(metadata.get("specialized_role_key") or role["role_key"])
                role["metadata"] = {
                    **dict(role_metadata),
                    "source": "resolved_constraint_ledger",
                    "template_role_contract": True,
                    "static_recipe_present": False,
                }
                if isinstance(projection, dict) and projection.get("template_id") == "photographer_template":
                    # Photography's frozen record validates role lineage only.
                    # Materialize the actual provider direction exclusively
                    # from the remote Brain deliverable, never from a local
                    # role recipe.
                    role["purpose"] = direction
                    role["prompt_pressure"] = direction
                    role["metadata"] = {
                        **dict(role["metadata"]),
                        "creative_direction_owner": "remote_v3_llm_brain",
                        "remote_image_intent_bound": True,
                    }
                return role
            return {
                "role_key": str(
                    metadata.get("specialized_role_key")
                    or item.get("deliverable_id")
                    or f"general_output_{index}"
                ),
                "label": f"Output {index}",
                "purpose": direction,
                "prompt_pressure": direction,
                "metadata": {
                    "source": "resolved_constraint_ledger",
                    "static_recipe_present": False,
                    **dict(metadata),
                },
            }
        for source in (request.metadata, request.generation_plan.metadata, request.prompt_compilation.provider_notes):
            value = source.get("mode_role_recipe") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        return {}

    def _role_specific_generation_plan(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            deliverables = projection.get("deliverables") if isinstance(projection, dict) else None
            priority = getattr(request.asset_spec, "priority", None) if request.asset_spec is not None else None
            try:
                index = max(1, int(priority or 1))
            except (TypeError, ValueError):
                index = 1
            item = deliverables[index - 1] if isinstance(deliverables, list) and index <= len(deliverables) else None
            metadata = item.get("metadata") if isinstance(item, dict) and isinstance(item.get("metadata"), dict) else {}
            if isinstance(metadata.get("specialized_role_contract"), dict):
                # A specialized Template already froze the role that this
                # deliverable must perform.  The shared Suite Director cannot
                # append an older generic cover/context/detail recipe on top
                # of that contract.  Shared identity and Human Realism
                # capabilities are consumed through their own contributions.
                return {}
            if not self._active_capability(request, "suite_direction"):
                return {}
            cluster = self._visual_cluster(request)
            value = cluster.get("role_specific_generation_plan") if isinstance(cluster, dict) else None
            return dict(value) if isinstance(value, dict) else {}
        for source in (request.metadata, request.generation_plan.metadata):
            value = source.get("role_specific_generation_plan") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        cluster = request.metadata.get("visual_cluster") if isinstance(request.metadata, dict) else None
        value = cluster.get("role_specific_generation_plan") if isinstance(cluster, dict) else None
        return dict(value) if isinstance(value, dict) else {}

    def _mode_execution_policy(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            deliverables = projection.get("deliverables") if isinstance(projection, dict) else None
            priority = getattr(request.asset_spec, "priority", None) if request.asset_spec is not None else None
            try:
                index = max(1, int(priority or 1))
            except (TypeError, ValueError):
                index = 1
            item = deliverables[index - 1] if isinstance(deliverables, list) and index <= len(deliverables) else None
            metadata = item.get("metadata") if isinstance(item, dict) and isinstance(item.get("metadata"), dict) else {}
            specialized_policy = metadata.get("specialized_execution_policy")
            if isinstance(specialized_policy, dict) and specialized_policy:
                return dict(specialized_policy)
            cluster = self._visual_cluster(request)
            value = cluster.get("mode_execution_policy") if isinstance(cluster, dict) else None
            if isinstance(value, dict):
                return dict(value)
            plan = self._role_specific_generation_plan(request)
            value = plan.get("policy") if isinstance(plan, dict) else None
            return dict(value) if isinstance(value, dict) else {}
        for source in (request.metadata, request.generation_plan.metadata):
            value = source.get("mode_execution_policy") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        plan = self._role_specific_generation_plan(request)
        value = plan.get("policy") if isinstance(plan, dict) else None
        return dict(value) if isinstance(value, dict) else {}

    def _visual_cluster(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else None
            cluster = projection.get("capability_projection") if isinstance(projection, dict) else None
            return dict(cluster) if isinstance(cluster, dict) else {}
        cluster = request.metadata.get("visual_cluster") if isinstance(request.metadata, dict) else None
        if isinstance(cluster, dict):
            return dict(cluster)
        shared = request.metadata.get("shared_capabilities") if isinstance(request.metadata, dict) else None
        if isinstance(shared, dict) and isinstance(shared.get("visual_cluster"), dict):
            return dict(shared["visual_cluster"])
        return {}

    def _activation_plan_summary(self, request: GenerationRequest) -> dict[str, Any]:
        envelope = self._execution_envelope(request)
        if envelope:
            plan = envelope.get("activation_plan")
            if isinstance(plan, dict):
                return dict(plan)
        if self._legacy_enforced_plan_marker(request):
            # This marker is a fail-closed boundary check, not a legacy
            # provider input.  It prevents a pre-envelope enforced request
            # from reviving old cluster fields below.
            return {"activation_mode": "enforced", "legacy_envelope_missing": True}
        for source in (request.metadata, request.generation_plan.metadata):
            if not isinstance(source, dict):
                continue
            plan = source.get("capability_activation_plan")
            if isinstance(plan, dict):
                return dict(plan)
            summary = source.get("capability_activation_plan_summary")
            if isinstance(summary, dict):
                return dict(summary)
        # This legacy branch intentionally reads the raw payload directly.
        # Calling _visual_cluster() here would recurse because that helper
        # first asks whether activation is enforced.
        raw_metadata = request.metadata if isinstance(request.metadata, dict) else {}
        cluster = raw_metadata.get("visual_cluster") if isinstance(raw_metadata.get("visual_cluster"), dict) else {}
        shared = raw_metadata.get("shared_capabilities") if isinstance(raw_metadata.get("shared_capabilities"), dict) else {}
        if not cluster and isinstance(shared.get("visual_cluster"), dict):
            cluster = shared["visual_cluster"]
        summary = cluster.get("capability_activation_plan_summary") if isinstance(cluster, dict) else None
        return dict(summary) if isinstance(summary, dict) else {}

    def _activation_enforced(self, request: GenerationRequest) -> bool:
        plan = self._activation_plan_summary(request)
        return str(plan.get("activation_mode") or "").lower() == "enforced"

    def _active_capability(self, request: GenerationRequest, capability_id: str) -> bool:
        plan = self._activation_plan_summary(request)
        if not plan:
            return True
        values = plan.get("dependency_order") or plan.get("active_capability_ids") or []
        return capability_id in {str(item) for item in values}

    def _composed_visual_contribution(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else None
            if not isinstance(projection, dict):
                return {}
            return {
                "prompt_additions": self._string_list(projection.get("quality_guidance")),
                "negative_additions": self._string_list(projection.get("negative_guidance")),
            }
        cluster = self._visual_cluster(request)
        value = cluster.get("composed_visual_contribution") if isinstance(cluster, dict) else None
        if isinstance(value, dict):
            return dict(value)
        for source in (request.metadata, request.generation_plan.metadata):
            value = source.get("composed_visual_contribution") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        return {}

    def _human_photorealism_guidance(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request) and not self._active_capability(request, "human_realism"):
            return {}
        cluster = self._visual_cluster(request)
        guidance = cluster.get("human_photorealism_guidance") if isinstance(cluster, dict) else None
        return dict(guidance) if isinstance(guidance, dict) and guidance.get("applies") else {}

    def _strong_reference_closure_package(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request) and not self._active_capability(request, "portrait_identity"):
            return {}
        cluster = self._visual_cluster(request)
        package = cluster.get("strong_reference_closure_package") if isinstance(cluster, dict) else None
        return dict(package) if isinstance(package, dict) and package.get("active") else {}

    def _resolved_reference_policy_package(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request) and not self._active_capability(request, "reference_channel_policy"):
            return {}
        cluster = self._visual_cluster(request)
        package = cluster.get("resolved_reference_policy_package") if isinstance(cluster, dict) else None
        if not isinstance(package, dict):
            role_plan = self._role_specific_generation_plan(request)
            metadata = role_plan.get("metadata") if isinstance(role_plan.get("metadata"), dict) else {}
            package = metadata.get("resolved_reference_policy_package") if isinstance(metadata, dict) else None
        return dict(package) if isinstance(package, dict) and package.get("applies") else {}

    def _adaptive_reference_selection_plan(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request) and not any(
            self._active_capability(request, item)
            for item in ("portrait_identity", "product_identity", "scene_continuity")
        ):
            return {}
        cluster = self._visual_cluster(request)
        plan = cluster.get("adaptive_reference_selection_plan") if isinstance(cluster, dict) else None
        return dict(plan) if isinstance(plan, dict) and plan.get("applies") else {}

    def _identity_repair_strategy_plan(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request) and not self._active_capability(request, "portrait_identity"):
            return {}
        cluster = self._visual_cluster(request)
        plan = cluster.get("identity_repair_strategy_plan") if isinstance(cluster, dict) else None
        return dict(plan) if isinstance(plan, dict) and plan.get("applies") else {}

    def _reference_channel_policy_for_asset(
        self,
        request: GenerationRequest,
        asset: dict[str, Any],
    ) -> dict[str, Any]:
        package = self._resolved_reference_policy_package(request)
        policies = package.get("policies") if isinstance(package, dict) else None
        if not isinstance(policies, list):
            return {}
        asset_ids = {
            str(value)
            for value in (
                asset.get("asset_id"),
                asset.get("source_id"),
                asset.get("asset_ref_id"),
                asset.get("output_id"),
            )
            if value
        }
        for policy in policies:
            if not isinstance(policy, dict):
                continue
            if str(policy.get("source_asset_id") or "") in asset_ids:
                return dict(policy)
        return {}

    def _mode_quality_profile(self, request: GenerationRequest) -> dict[str, Any]:
        if self._activation_enforced(request) and not self._active_capability(request, "suite_direction"):
            return {}
        cluster = self._visual_cluster(request)
        profile = cluster.get("mode_quality_profile") if isinstance(cluster, dict) else None
        return dict(profile) if isinstance(profile, dict) else {}

    def _execution_envelope(self, request: GenerationRequest) -> dict[str, Any]:
        generation_plan = getattr(request, "generation_plan", None)
        generation_metadata = getattr(generation_plan, "metadata", {}) if generation_plan is not None else {}
        for source in (request.metadata, generation_metadata):
            if not isinstance(source, dict):
                continue
            envelope = source.get("capability_execution_envelope")
            if isinstance(envelope, dict) and isinstance(envelope.get("activation_plan"), dict):
                return dict(envelope)
        return {}

    def _resolved_constraint_ledger(self, request: GenerationRequest) -> dict[str, Any]:
        envelope = self._execution_envelope(request)
        ledger = envelope.get("resolved_constraint_ledger") if isinstance(envelope, dict) else None
        if isinstance(ledger, dict) and isinstance(ledger.get("provider_projection"), dict):
            return dict(ledger)
        return {}

    def _legacy_enforced_plan_marker(self, request: GenerationRequest) -> bool:
        generation_plan = getattr(request, "generation_plan", None)
        generation_metadata = getattr(generation_plan, "metadata", {}) if generation_plan is not None else {}
        for source in (request.metadata, generation_metadata):
            if not isinstance(source, dict):
                continue
            plan = source.get("capability_activation_plan")
            if isinstance(plan, dict) and str(plan.get("activation_mode") or "").lower() == "enforced":
                return True
            summary = source.get("capability_activation_plan_summary")
            if isinstance(summary, dict) and str(summary.get("activation_mode") or "").lower() == "enforced":
                return True
        return False


class PlanningOnlyGenerationProvider(GenerationProvider):
    provider_name = "planning_only_generation_provider"
    provider_version = "v3.0-foundation"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        candidate = CandidateResult(
            candidate_id=stable_id("candidate", request.generation_plan.asset_id, request.prompt_compilation.prompt_compilation_id),
            asset_id=request.generation_plan.asset_id,
            provider=self.provider_name,
            prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
            condition_plan_id=request.condition_plan.condition_plan_id,
            is_mock=True,
            metadata={"runtime_mode": "planning_only", "provider_version": self.provider_version},
        )
        return GenerationResponse(
            candidates=[candidate],
            provider_metadata={"provider_name": self.provider_name, "provider_version": self.provider_version},
            warnings=["No real image generation is executed in V3.0 foundation."],
        )


class MockGenerationProvider(GenerationProvider):
    """Deterministic V3.2 candidate provider used by the closed-loop MVP."""

    provider_name = "mock_generation_provider"
    provider_version = "v3.2-generation-loop-mvp"

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        candidate_count = max(1, request.generation_plan.candidate_count)
        refine_round = int(request.metadata.get("refine_round", request.generation_plan.metadata.get("refine_round", 0) or 0))
        profile = str(request.generation_plan.metadata.get("mock_profile", request.metadata.get("mock_profile", "balanced")))
        retry_attempt = self._retry_attempt(request)
        candidates: list[CandidateResult] = []
        warnings: list[str] = []

        for index in range(candidate_count):
            quality_score, problem_codes = self._candidate_profile(profile, index, refine_round)
            hard_failure = "provider_failure" in problem_codes or "missing_product_area" in problem_codes
            candidate_id_parts = [
                "candidate",
                request.generation_plan.asset_id,
                request.prompt_compilation.prompt_compilation_id,
                self.provider_name,
                refine_round,
                index,
                profile,
            ]
            if retry_attempt:
                candidate_id_parts.append(f"retry_{retry_attempt}")
            candidate_id = stable_id(
                *candidate_id_parts,
            )
            candidates.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    asset_id=request.generation_plan.asset_id,
                    uri=f"mock://v3/{candidate_id}",
                    provider=self.provider_name,
                    prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                    condition_plan_id=request.condition_plan.condition_plan_id,
                    is_mock=True,
                    metadata={
                        "runtime_mode": "mock_generation",
                        "provider_version": self.provider_version,
                        "candidate_index": index,
                        "refine_round": refine_round,
                        "mock_profile": profile,
                        "mock_quality_score": quality_score,
                        "forced_problem_codes": problem_codes,
                        "hard_failure": hard_failure,
                        "asset_id": request.generation_plan.asset_id,
                        "visual_auto_retry_attempt": retry_attempt,
                        "visual_retry_reason_codes": self._string_list(request.metadata.get("visual_retry_reason_codes")),
                        "retry_patch": self._retry_patch(request),
                        "mode_execution_policy": self._mode_execution_policy(request),
                        "role_specific_generation_plan": self._role_specific_generation_plan(request),
                        "mode_role_recipe": self._mode_role_recipe(request),
                        "mode_role_key": self._mode_role_recipe(request).get("role_key"),
                        "mode_role_label": self._mode_role_recipe(request).get("label"),
                    },
                )
            )
        if profile == "all_hard_failure":
            warnings.append("Mock profile produced only hard-failure candidates.")
        return GenerationResponse(
            candidates=candidates,
            provider_metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "runtime_mode": "mock_generation",
                "refine_round": refine_round,
                "mock_profile": profile,
            },
            warnings=warnings,
        )

    def _candidate_profile(self, profile: str, index: int, refine_round: int) -> tuple[float, list[str]]:
        if profile == "needs_refinement":
            if refine_round == 0:
                return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["provider_native_text_fidelity_failure"])
            return (0.86 - index * 0.03, [])
        if profile == "exhaust_retries":
            return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["brand_style_missing"])
        if profile == "hard_failure_first":
            if index == 0:
                return (0.30, ["missing_product_area"])
            return (0.84 - index * 0.02, [])
        if profile == "all_hard_failure":
            return (0.25, ["missing_product_area"])
        if index == 0:
            return (0.86, [])
        if index == 1:
            return (0.80, [])
        if index == 2:
            return (0.67, ["commercial_hook_missing"])
        return (0.42, ["provider_failure"])


class ProductionImageGenerationProvider(GenerationProvider):
    """V3-owned adapter that reuses configured V1/V2 image provider credentials."""

    provider_name = "production_image_generation_provider"
    provider_version = "v3.8e-doc100-gpt-image-2-sole-renderer"
    # Live GPT Image 2 reference runs showed that framework-expanded prompts
    # above roughly 16k characters can be rejected by an otherwise valid image
    # edit gateway. Keep the user's positive request lossless, but materialize
    # module-owned guidance into a concise provider transport contract.
    provider_prompt_target_chars = 15000
    max_provider_prompt_chars: int | None = None

    def __init__(self, output_store: Any | None = None) -> None:
        if output_store is None:
            from ..product_api.outputs import V3GeneratedOutputStore

            output_store = V3GeneratedOutputStore()
        self.output_store = output_store
        self._last_provider_failure_retry_summary: dict[str, Any] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.provider_name,
            version=self.provider_version,
            supports_generation=True,
            supports_batch=True,
            requires_gpu=False,
            requires_network=True,
            is_deterministic=False,
        )

    def generate(self, request: GenerationRequest) -> GenerationResponse:
        app_request, provider_name, reference_assets = self._build_app_request(request)
        asset_plan = app_request.prompt_plan.variables.get("asset_plan") if getattr(app_request.prompt_plan, "variables", None) else {}
        asset_plan = asset_plan if isinstance(asset_plan, dict) else {}
        provider_input_plan = asset_plan.get("provider_input_plan") if isinstance(asset_plan.get("provider_input_plan"), dict) else {}
        provider_reference_image_count = int(provider_input_plan.get("reference_image_count") or 0)
        reference_truth_package = provider_input_plan.get("reference_truth_package") if isinstance(provider_input_plan.get("reference_truth_package"), dict) else {}
        provider_reference_assets = self._provider_reference_asset_summary(asset_plan)
        provider_reference_resolution_audit = asset_plan.get("provider_reference_resolution_audit", {})
        reference_asset_ids = _dedupe([str(asset.get("asset_id") or "") for asset in reference_assets])
        reference_asset_count = len(reference_asset_ids)
        final_provider_prompt = str(app_request.prompt_plan.variables.get("generation_prompt") or "")
        negative_constraints = self._negative_constraints(request)
        llm_brain = request.metadata.get("llm_brain") if isinstance(request.metadata.get("llm_brain"), dict) else {}
        if self._activation_enforced(request):
            ledger = self._resolved_constraint_ledger(request)
            projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
            shared_capabilities = {
                "source": "resolved_constraint_ledger",
                "active_capability_ids": list(
                    (self._activation_plan_summary(request).get("dependency_order") or [])
                ),
            }
            visual_cluster = (
                dict(projection.get("capability_projection") or {})
                if isinstance(projection, dict)
                else {}
            )
        else:
            shared_capabilities = (
                request.metadata.get("shared_capabilities") if isinstance(request.metadata.get("shared_capabilities"), dict) else {}
            )
            visual_cluster = request.metadata.get("visual_cluster") if isinstance(request.metadata.get("visual_cluster"), dict) else {}
            if not visual_cluster and isinstance(shared_capabilities.get("visual_cluster"), dict):
                visual_cluster = shared_capabilities["visual_cluster"]
        mode_role_recipe = self._mode_role_recipe(request)
        role_specific_plan = self._role_specific_generation_plan(request)
        mode_policy = self._mode_execution_policy(request)
        strong_reference_closure = self._strong_reference_closure_package(request)
        mode_quality_profile = self._mode_quality_profile(request)
        auto_identity_anchor_applied = bool(request.metadata.get("auto_batch_identity_anchor_applied"))
        result = self._run_app_provider_with_timeout_retry(provider_name, app_request, reference_assets)
        provider_failure_retry = dict(self._last_provider_failure_retry_summary or {})
        candidates: list[CandidateResult] = []
        warnings: list[str] = []
        outputs = list(getattr(result, "outputs", []) or [])
        requested_group_count = self._group_count_for_request(request)
        retry_attempt = self._retry_attempt(request)
        if not outputs:
            # A transport can complete without raising while returning an
            # empty OpenAI-compatible ``data`` array.  That is still one
            # failed upstream request, not a successful generation and not a
            # reason for V3 to replay a gateway-managed call. Preserve a safe
            # response summary so the job record distinguishes this from a
            # local lifecycle error or a visual-review rejection.
            from app.providers.base import ProviderRuntimeError

            raw_summary = getattr(result, "raw_response_summary", {})
            safe_summary = {
                str(key): value
                for key, value in dict(raw_summary or {}).items()
                if str(key)
                in {
                    "output_count",
                    "requests",
                    "gateway_managed_failover",
                    "sdk_max_retries",
                    "client_timeout_seconds",
                }
                and isinstance(value, (str, int, float, bool, type(None)))
            }
            failed_attempts = [dict(item) for item in provider_failure_retry.get("attempts", []) if isinstance(item, dict)]
            if failed_attempts:
                failed_attempts[-1] = {
                    **failed_attempts[-1],
                    "status": "failed",
                    "classification": "empty_provider_output",
                    "error_type": "ProviderRuntimeError",
                    "message": "OpenAI-compatible image provider returned no image outputs.",
                    "retryable": True,
                }
            else:
                failed_attempts = [
                    {
                        "attempt": 1,
                        "status": "failed",
                        "classification": "empty_provider_output",
                        "error_type": "ProviderRuntimeError",
                        "message": "OpenAI-compatible image provider returned no image outputs.",
                        "retryable": True,
                    }
                ]
            provider_failure_retry = {
                **provider_failure_retry,
                "executed_count": 0,
                "fresh_upstream_requests": max(1, int(provider_failure_retry.get("fresh_upstream_requests") or 0)),
                "final_status": "failed",
                "final_classification": "empty_provider_output",
                "attempts": failed_attempts,
                "provider_response_summary": safe_summary,
            }
            self._last_provider_failure_retry_summary = dict(provider_failure_retry)
            error = ProviderRuntimeError(
                "OpenAI-compatible image provider returned no image outputs.",
                provider=str(getattr(result, "provider", provider_name) or provider_name),
                detail={
                    "provider_response_summary": safe_summary,
                    "requested_output_count": requested_group_count,
                    "runtime_transport": provider_failure_retry.get("execution_audit", {}),
                },
            )
            setattr(error, "provider_failure_retry", dict(provider_failure_retry))
            raise error
        for index, output in enumerate(outputs):
            encoded = output.get("b64_json")
            if not encoded:
                warnings.append("Provider output did not include image bytes and was skipped.")
                continue
            candidate_id_parts = [
                "candidate",
                request.generation_plan.asset_id,
                request.prompt_compilation.prompt_compilation_id,
                getattr(result, "provider", provider_name),
                getattr(result, "model", ""),
                index,
            ]
            if retry_attempt:
                candidate_id_parts.append(f"retry_{retry_attempt}")
            candidate_id = stable_id(
                *candidate_id_parts,
            )
            record = self.output_store.save_base64_output(
                job_id=str(request.metadata.get("job_id") or request.generation_plan.metadata.get("job_id") or "v3_job"),
                candidate_id=candidate_id,
                asset_id=request.generation_plan.asset_id,
                provider=str(getattr(result, "provider", provider_name)),
                model=str(getattr(result, "model", "") or ""),
                encoded_image=str(encoded),
                mime_type=output.get("mime_type"),
                output_format=output.get("format") or app_request.prompt_plan.output_format,
                width=output.get("width"),
                height=output.get("height"),
                metadata={
                    "source": self.provider_name,
                    "provider_version": self.provider_version,
                    "prompt_compilation_id": request.prompt_compilation.prompt_compilation_id,
                    "condition_plan_id": request.condition_plan.condition_plan_id,
                    "reference_asset_count": reference_asset_count,
                    "provider_reference_image_count": provider_reference_image_count,
                    "provider_input_plan": provider_input_plan,
                    "reference_truth_package": reference_truth_package,
                    "provider_reference_assets": provider_reference_assets,
                    "provider_reference_resolution_audit": provider_reference_resolution_audit,
                    "compiled_visual_direction": request.prompt_compilation.visual_prompt,
                    "final_provider_prompt": final_provider_prompt,
                    "final_provider_prompt_chars": len(final_provider_prompt),
                    "provider_prompt_target_chars": self.max_provider_prompt_chars or self.provider_prompt_target_chars,
                    "provider_prompt_materialization": "v3_semantic_budget_user_direction_lossless",
                    "provider_prompt_audit": app_request.prompt_plan.variables.get("provider_prompt_audit", {}),
                    "negative_constraints": negative_constraints,
                    "style_notes": list(request.prompt_compilation.style_notes),
                    "layout_notes": list(request.prompt_compilation.layout_notes),
                    "llm_brain": llm_brain,
                    "llm_brain_summary": request.prompt_compilation.provider_notes.get("llm_brain_summary", {}),
                    "llm_brain_consistency_strategy": request.prompt_compilation.provider_notes.get("llm_brain_consistency_strategy"),
                    "shared_capabilities": shared_capabilities,
                    "visual_capability_cluster": visual_cluster,
                    "reference_asset_ids": reference_asset_ids,
                    "reference_truth_source_ids": reference_truth_package.get("truth_source_ids") or [],
                    "reference_truth_derivative_ids": reference_truth_package.get("truth_derivative_ids") or [],
                    "provider_raw_summary": getattr(result, "raw_response_summary", {}) or {},
                    "provider_failure_retry": provider_failure_retry,
                    "api_operation": output.get("api_operation"),
                    "input_fidelity_requested": output.get("input_fidelity_requested"),
                    "input_fidelity_required": bool(output.get("input_fidelity_required")),
                    "input_fidelity_applied": output.get("input_fidelity_applied"),
                    "input_fidelity_support_state": output.get("input_fidelity_support_state"),
                    "input_fidelity_fallback_reason": output.get("input_fidelity_fallback_reason"),
                    "identity_local_repair": bool(output.get("identity_local_repair")),
                    "request_index": output.get("request_index"),
                    "requested_image_count": requested_group_count,
                    "requested_image_size": app_request.prompt_plan.size,
                    "project_id": request.metadata.get("project_id"),
                    "template_id": request.metadata.get("template_id"),
                    "veyra_user_id": request.metadata.get("veyra_user_id"),
                    "visual_auto_retry_attempt": retry_attempt,
                    "visual_retry_reason_codes": self._string_list(request.metadata.get("visual_retry_reason_codes")),
                    "retry_patch": self._retry_patch(request),
                    "auto_batch_identity_anchor_applied": auto_identity_anchor_applied,
                    "auto_batch_identity_anchor_policy": request.metadata.get("auto_batch_identity_anchor_policy", {}),
                    "auto_batch_identity_anchor_source_output_id": request.metadata.get("auto_batch_identity_anchor_source_output_id"),
                    "auto_batch_identity_anchor_source_candidate_id": request.metadata.get("auto_batch_identity_anchor_source_candidate_id"),
                    "mode_execution_policy": mode_policy,
                    "role_specific_generation_plan": role_specific_plan,
                    "mode_role_recipe": mode_role_recipe,
                    "mode_role_key": mode_role_recipe.get("role_key"),
                    "mode_role_label": mode_role_recipe.get("label"),
                    "strong_reference_closure_package": strong_reference_closure,
                    "mode_quality_profile": mode_quality_profile,
                },
            )
            candidates.append(
                CandidateResult(
                    candidate_id=candidate_id,
                    asset_id=request.generation_plan.asset_id,
                    file_path=record.file_path,
                    uri=record.thumbnail_url,
                    provider=str(getattr(result, "provider", provider_name)),
                    prompt_compilation_id=request.prompt_compilation.prompt_compilation_id,
                    condition_plan_id=request.condition_plan.condition_plan_id,
                    is_mock=False,
                    metadata={
                        "runtime_mode": "production_image_generation",
                        "provider_version": self.provider_version,
                        "actual_provider": str(getattr(result, "provider", provider_name)),
                        "actual_model": str(getattr(result, "model", "") or ""),
                        "output_id": record.output_id,
                        "url": record.download_url,
                        "download_url": record.download_url,
                        "preview_url": record.preview_url,
                        "thumbnail_url": record.thumbnail_url,
                        "mime_type": record.mime_type,
                        "format": record.output_format,
                        "width": record.width,
                        "height": record.height,
                        "reference_asset_count": reference_asset_count,
                        "provider_reference_image_count": provider_reference_image_count,
                        "provider_input_plan": provider_input_plan,
                        "reference_truth_package": reference_truth_package,
                        "provider_reference_assets": provider_reference_assets,
                        "provider_reference_resolution_audit": provider_reference_resolution_audit,
                        "compiled_visual_direction": request.prompt_compilation.visual_prompt,
                        "final_provider_prompt": final_provider_prompt,
                        "final_provider_prompt_chars": len(final_provider_prompt),
                        "provider_prompt_target_chars": self.max_provider_prompt_chars or self.provider_prompt_target_chars,
                        "provider_prompt_materialization": "v3_semantic_budget_user_direction_lossless",
                        "provider_prompt_audit": app_request.prompt_plan.variables.get("provider_prompt_audit", {}),
                        "negative_constraints": negative_constraints,
                        "style_notes": list(request.prompt_compilation.style_notes),
                        "layout_notes": list(request.prompt_compilation.layout_notes),
                        "llm_brain": llm_brain,
                        "llm_brain_summary": request.prompt_compilation.provider_notes.get("llm_brain_summary", {}),
                        "llm_brain_consistency_strategy": request.prompt_compilation.provider_notes.get("llm_brain_consistency_strategy"),
                        "shared_capabilities": shared_capabilities,
                        "visual_capability_cluster": visual_cluster,
                        "reference_asset_ids": reference_asset_ids,
                        "reference_truth_source_ids": reference_truth_package.get("truth_source_ids") or [],
                        "reference_truth_derivative_ids": reference_truth_package.get("truth_derivative_ids") or [],
                        "provider_failure_retry": provider_failure_retry,
                        "api_operation": output.get("api_operation"),
                        "input_fidelity_requested": output.get("input_fidelity_requested"),
                        "input_fidelity_required": bool(output.get("input_fidelity_required")),
                        "input_fidelity_applied": output.get("input_fidelity_applied"),
                        "input_fidelity_support_state": output.get("input_fidelity_support_state"),
                        "input_fidelity_fallback_reason": output.get("input_fidelity_fallback_reason"),
                        "identity_local_repair": bool(output.get("identity_local_repair")),
                        "request_index": output.get("request_index"),
                        "v3_owned_output": True,
                        "requested_image_count": requested_group_count,
                        "requested_image_size": app_request.prompt_plan.size,
                        "project_id": request.metadata.get("project_id"),
                        "template_id": request.metadata.get("template_id"),
                        "veyra_user_id": request.metadata.get("veyra_user_id"),
                        "visual_auto_retry_attempt": retry_attempt,
                        "visual_retry_reason_codes": self._string_list(request.metadata.get("visual_retry_reason_codes")),
                        "retry_patch": self._retry_patch(request),
                        "auto_batch_identity_anchor_applied": auto_identity_anchor_applied,
                        "auto_batch_identity_anchor_policy": request.metadata.get("auto_batch_identity_anchor_policy", {}),
                        "auto_batch_identity_anchor_source_output_id": request.metadata.get("auto_batch_identity_anchor_source_output_id"),
                        "auto_batch_identity_anchor_source_candidate_id": request.metadata.get("auto_batch_identity_anchor_source_candidate_id"),
                        "mode_execution_policy": mode_policy,
                        "role_specific_generation_plan": role_specific_plan,
                        "mode_role_recipe": mode_role_recipe,
                        "mode_role_key": mode_role_recipe.get("role_key"),
                        "mode_role_label": mode_role_recipe.get("label"),
                        "strong_reference_closure_package": strong_reference_closure,
                        "mode_quality_profile": mode_quality_profile,
                    },
                )
            )
        if not candidates:
            raise ValueError("V3 production provider could not persist any generated image outputs.")
        return GenerationResponse(
            candidates=candidates,
            provider_metadata={
                "provider_name": self.provider_name,
                "provider_version": self.provider_version,
                "runtime_mode": "production_image_generation",
                "actual_provider": str(getattr(result, "provider", provider_name)),
                "actual_model": str(getattr(result, "model", "") or ""),
                "reference_asset_count": reference_asset_count,
                "provider_reference_image_count": provider_reference_image_count,
                "provider_input_plan": provider_input_plan,
                "reference_truth_package": reference_truth_package,
                "provider_reference_assets": provider_reference_assets,
                "provider_reference_resolution_audit": provider_reference_resolution_audit,
                "reference_asset_ids": reference_asset_ids,
                "reference_truth_source_ids": reference_truth_package.get("truth_source_ids") or [],
                "reference_truth_derivative_ids": reference_truth_package.get("truth_derivative_ids") or [],
                "final_provider_prompt_chars": len(final_provider_prompt),
                "provider_prompt_target_chars": self.max_provider_prompt_chars or self.provider_prompt_target_chars,
                "provider_prompt_materialization": "v3_semantic_budget_user_direction_lossless",
                "provider_prompt_audit": app_request.prompt_plan.variables.get("provider_prompt_audit", {}),
                "llm_brain": llm_brain,
                "shared_capabilities": shared_capabilities,
                "visual_capability_cluster": visual_cluster,
                "requested_image_count": requested_group_count,
                "requested_image_size": app_request.prompt_plan.size,
                "project_id": request.metadata.get("project_id"),
                "template_id": request.metadata.get("template_id"),
                "veyra_user_id": request.metadata.get("veyra_user_id"),
                "mode_execution_policy": mode_policy,
                "auto_batch_identity_anchor_applied": auto_identity_anchor_applied,
                "auto_batch_identity_anchor_policy": request.metadata.get("auto_batch_identity_anchor_policy", {}),
                "role_specific_generation_plan": role_specific_plan,
                "mode_role_recipe": mode_role_recipe,
                "strong_reference_closure_package": strong_reference_closure,
                "mode_quality_profile": mode_quality_profile,
                "provider_failure_retry": provider_failure_retry,
                "api_operations": [output.get("api_operation") for output in outputs if output.get("api_operation")],
                "input_fidelity_requested": next(
                    (output.get("input_fidelity_requested") for output in outputs if output.get("input_fidelity_requested")),
                    None,
                ),
                "input_fidelity_required": any(bool(output.get("input_fidelity_required")) for output in outputs),
                "input_fidelity_applied": next(
                    (output.get("input_fidelity_applied") for output in outputs if output.get("input_fidelity_applied")),
                    None,
                ),
                "input_fidelity_support_states": _dedupe(
                    [str(output.get("input_fidelity_support_state")) for output in outputs if output.get("input_fidelity_support_state")]
                ),
            },
            warnings=warnings,
        )

    async def _generate_with_app_provider(self, provider_name: str, app_request):
        provider = self._app_provider(provider_name)
        return await provider.generate(app_request)

    def _run_app_provider_with_timeout_retry(self, provider_name: str, app_request, reference_assets: list[dict[str, Any]]):
        timeout_seconds = self._app_provider_timeout_seconds(reference_assets)
        max_attempts = self._app_provider_max_attempts()
        execution_audit = self._provider_execution_audit(
            reference_assets=reference_assets,
            outer_timeout_seconds=timeout_seconds,
            max_attempts=max_attempts,
        )
        attempts: list[dict[str, Any]] = []
        last_error: BaseException | None = None
        provider_prompt_chars = self._app_request_prompt_chars(app_request)
        self._last_provider_failure_retry_summary = {
            "executed_count": 0,
            "max_attempts": max_attempts,
            "fresh_upstream_requests": 0,
            "final_status": "skipped",
            "attempts": attempts,
            "reference_asset_count": len(reference_assets),
            "provider_prompt_chars": provider_prompt_chars,
            "execution_audit": execution_audit,
        }
        for attempt in range(1, max_attempts + 1):
            retry_metadata = self._provider_failure_retry_metadata(
                attempt=attempt,
                max_attempts=max_attempts,
                previous_error=last_error,
            )
            self._apply_provider_retry_metadata(app_request, retry_metadata)
            try:
                result = _run_async_blocking(
                    self._generate_with_app_provider(provider_name, app_request),
                    timeout_seconds=timeout_seconds,
                )
                attempts.append({"attempt": attempt, "status": "succeeded"})
                self._last_provider_failure_retry_summary = {
                    "executed_count": max(0, attempt - 1),
                    "max_attempts": max_attempts,
                    "fresh_upstream_requests": attempt,
                    "final_status": "succeeded",
                    "attempts": attempts,
                    "reference_asset_count": len(reference_assets),
                    "provider_prompt_chars": provider_prompt_chars,
                    "execution_audit": execution_audit,
                }
                return result
            except BaseException as exc:
                last_error = exc
                classification = self._classify_provider_failure(exc)
                retryable = classification in {"retryable_provider_failure", "unknown_retryable_failure"}
                attempts.append(
                    {
                        "attempt": attempt,
                        "status": "failed",
                        "classification": classification,
                        "error_type": exc.__class__.__name__,
                        "message": self._provider_failure_message(exc),
                        "retryable": retryable,
                        **self._provider_error_transport_audit(exc),
                    }
                )
                if attempt >= max_attempts or not retryable:
                    self._last_provider_failure_retry_summary = {
                        "executed_count": max(0, attempt - 1),
                        "max_attempts": max_attempts,
                        "fresh_upstream_requests": attempt,
                        "final_status": "failed",
                        "attempts": attempts,
                        "reference_asset_count": len(reference_assets),
                        "provider_prompt_chars": provider_prompt_chars,
                        "execution_audit": execution_audit,
                        "final_classification": classification,
                    }
                    try:
                        setattr(exc, "provider_failure_retry", dict(self._last_provider_failure_retry_summary))
                    except Exception:
                        pass
                    raise
                time.sleep(self._app_provider_transient_cooldown_seconds())
        if last_error is not None:
            raise last_error
        raise TimeoutError("V3 production provider timed out.")

    def _provider_execution_audit(
        self,
        *,
        reference_assets: list[dict[str, Any]],
        outer_timeout_seconds: float,
        max_attempts: int,
    ) -> dict[str, Any]:
        """Persist the owning V3 deadline without leaking provider secrets."""

        try:
            from app.config import settings as app_settings

            managed = bool(getattr(app_settings, "openai_image_gateway_managed_failover", False))
            managed_timeout = float(app_settings.openai_image_gateway_managed_failover_timeout_seconds)
        except Exception:
            managed = False
            managed_timeout = None
        return {
            "gateway_managed_failover": managed,
            "gateway_managed_failover_timeout_seconds": managed_timeout,
            "outer_timeout_seconds": float(outer_timeout_seconds),
            "outer_max_attempts": int(max_attempts),
            "operation": "image_edit" if reference_assets else "image_generate",
        }

    @staticmethod
    def _provider_error_transport_audit(exc: BaseException) -> dict[str, Any]:
        detail = getattr(exc, "detail", None)
        if not isinstance(detail, dict):
            return {}
        transport = detail.get("runtime_transport")
        return {"runtime_transport": dict(transport)} if isinstance(transport, dict) else {}

    def _app_request_prompt_chars(self, app_request) -> int:
        prompt_plan = getattr(app_request, "prompt_plan", None)
        variables = getattr(prompt_plan, "variables", None)
        if isinstance(variables, dict):
            return len(str(variables.get("generation_prompt") or ""))
        return 0

    def _provider_failure_retry_metadata(self, *, attempt: int, max_attempts: int, previous_error: BaseException | None) -> dict[str, Any]:
        metadata = {
            "provider_failure_retry_attempt": attempt,
            "provider_failure_retry_max_attempts": max_attempts,
            "fresh_upstream_request": True,
        }
        if previous_error is not None:
            metadata["previous_provider_error_type"] = previous_error.__class__.__name__
            metadata["previous_provider_error"] = self._provider_failure_message(previous_error)
        return metadata

    def _apply_provider_retry_metadata(self, app_request, retry_metadata: dict[str, Any]) -> None:
        existing = dict(getattr(app_request, "metadata", {}) or {})
        merged = {**existing, **retry_metadata}
        try:
            app_request.metadata = merged
        except Exception:
            return

    def _classify_provider_failure(self, exc: BaseException) -> str:
        code = str(getattr(exc, "code", "") or "").lower()
        detail = getattr(exc, "detail", None)
        detail_text = ""
        if isinstance(detail, dict):
            detail_text = " ".join(str(value) for value in detail.values() if value is not None).lower()
        message = f"{exc.__class__.__name__} {code} {str(exc)} {detail_text}".lower()
        wrapped_reference_upstream_failure = (
            "image reference generation failed" in message
            and "bad_response_status_code" in message
            and "openai_error" in message
        )
        if wrapped_reference_upstream_failure:
            # Some OpenAI-compatible gateways wrap a transient upstream rejection
            # in HTTP 400. Permit the existing single fresh-request retry without
            # making explicit client-side 400 errors retryable.
            return "retryable_provider_failure"
        non_retryable_markers = [
            "provider_capability_mismatch",
            "transport_profile",
            "only supports 1024x1024 text-to-image generation",
            "supports text-to-image generation only",
            "provider_not_configured",
            "not configured",
            "missing api key",
            "invalid api key",
            "authentication",
            "unauthorized",
            "insufficient",
            "balance",
            "policy",
            "safety",
            "invalid uploaded asset",
            "source file was not found",
            "unsupported media type",
            "bad request",
            "400",
        ]
        if any(marker in message for marker in non_retryable_markers):
            return "non_retryable_provider_failure"
        retryable_markers = [
            "timeouterror",
            "timeout",
            "timed out",
            "image reference generation failed",
            "image generation failed",
            "could not be downloaded",
            "no image outputs",
            "did not include image bytes",
            "bad_response_status_code",
            "gateway timeout",
            "bad gateway",
            "502",
            "503",
            "504",
            "500",
            "408",
            "429",
            "transport",
            "connection",
            "read timeout",
            "internal_server_error",
        ]
        if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or any(marker in message for marker in retryable_markers):
            return "retryable_provider_failure"
        return "unknown_retryable_failure"

    def _provider_failure_message(self, exc: BaseException) -> str:
        message = str(exc).strip() or exc.__class__.__name__
        detail = getattr(exc, "detail", None)
        if isinstance(detail, dict):
            detail_message = str(detail.get("message") or detail.get("error_message") or detail.get("error_type") or "").strip()
            if detail_message and detail_message not in message:
                message = f"{message} {detail_message}"
        return message[:500]

    def _build_app_request(self, request: GenerationRequest):
        from app import schemas as app_schemas

        image_request_cls = getattr(app_schemas, "ImageGenerationRequest")
        prompt_plan_cls = getattr(app_schemas, "Image" + "PromptPlan")

        reference_assets = self._reference_assets(request)
        asset_plan = self._asset_plan(request, reference_assets)
        asset_plan["provider_reference_resolution_audit"] = dict(
            request.metadata.get("provider_reference_resolution_audit") or {}
        )
        self._assert_nonhuman_identity_reference_materialized(request, asset_plan)
        provider_name = self._select_provider(reference_assets)
        size = self._size_for_request(request)
        generation_prompt = self._generation_prompt(request, reference_assets, asset_plan=asset_plan)
        protected_user_direction = self._provider_user_direction(request)
        prompt_audit = self._provider_prompt_audit(generation_prompt, protected_user_direction)
        input_fidelity = self._input_fidelity_for_asset_plan(asset_plan)
        prompt_plan = prompt_plan_cls(
            main_subject=request.asset_spec.purpose if request.asset_spec else request.prompt_compilation.asset_id,
            scene=self._scene_for_request(request),
            style=", ".join(request.prompt_compilation.style_notes),
            composition=self._composition_for_request(request),
            brand_constraints=list(request.prompt_compilation.hard_constraints),
            negative_constraints=self._negative_constraints(request),
            text={},
            count=1,
            size=size,
            quality=self._quality_for_request(request),
            output_format="png",
            variables={
                "generation_prompt": generation_prompt,
                "provider_prompt_chars": len(generation_prompt),
                "provider_prompt_target_chars": self.max_provider_prompt_chars or self.provider_prompt_target_chars,
                "protected_user_direction_chars": len(protected_user_direction),
                "provider_prompt_materialization": "v3_semantic_budget_user_direction_lossless",
                "provider_prompt_audit": prompt_audit,
                "asset_plan": asset_plan,
                "v3_prompt_compilation_id": request.prompt_compilation.prompt_compilation_id,
                "v3_generation_plan_id": request.generation_plan.generation_plan_id,
                "v3_provider_strategy": request.generation_plan.provider_strategy.value,
                "requested_image_count": self._group_count_for_request(request),
                "requested_image_size": size,
                "input_fidelity": input_fidelity,
                "input_fidelity_required": self._input_fidelity_is_required(asset_plan),
                "identity_repair_canvas_path": request.metadata.get("identity_repair_canvas_path"),
                "identity_repair_mask_path": request.metadata.get("identity_repair_mask_path"),
            },
        )
        return (
            image_request_cls(
                prompt_plan=prompt_plan,
                asset_ids=[item["asset_id"] for item in asset_plan.get("assets", [])],
                asset_mode="advanced" if reference_assets else "basic",
                asset_plan=asset_plan if reference_assets else None,
                provider_preference=provider_name,
                idempotency_key=stable_id(
                    "v3_image",
                    request.metadata.get("job_id"),
                    request.generation_plan.asset_id,
                    request.prompt_compilation.prompt_compilation_id,
                ),
                trace_id=stable_id("trace", request.metadata.get("job_id"), request.generation_plan.asset_id),
            ),
            provider_name,
            reference_assets,
        )

    def _input_fidelity_for_asset_plan(self, asset_plan: dict[str, Any]) -> str | None:
        input_plan = asset_plan.get("provider_input_plan") if isinstance(asset_plan, dict) else {}
        truth_layers = input_plan.get("reference_truth_layers") if isinstance(input_plan, dict) else []
        for item in truth_layers if isinstance(truth_layers, list) else []:
            if not isinstance(item, dict):
                continue
            if str(item.get("truth_layer") or "") in {
                "portrait_identity_truth",
                "product_identity_truth",
                "nonhuman_subject_identity_truth",
            }:
                return "high"
        return None

    def _input_fidelity_is_required(self, asset_plan: dict[str, Any]) -> bool:
        input_plan = asset_plan.get("provider_input_plan") if isinstance(asset_plan, dict) else {}
        truth_layers = input_plan.get("reference_truth_layers") if isinstance(input_plan, dict) else []
        return any(
            isinstance(item, dict) and str(item.get("truth_layer") or "") == "nonhuman_subject_identity_truth"
            for item in (truth_layers if isinstance(truth_layers, list) else [])
        )

    def _assert_nonhuman_identity_reference_materialized(
        self,
        request: GenerationRequest,
        asset_plan: dict[str, Any],
    ) -> None:
        raw_plan = request.metadata.get("capability_activation_plan")
        plan = dict(raw_plan) if isinstance(raw_plan, dict) else {}
        active_ids = self._string_list(plan.get("dependency_order")) if plan else []
        raw_assets = request.metadata.get("uploaded_assets") if isinstance(request.metadata.get("uploaded_assets"), list) else []
        raw_requires_native_reference = any(
            self._is_nonhuman_truth_reference(
                item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item or {})
            )
            for item in raw_assets
        )
        requires_native_reference = "nonhuman_subject_identity" in active_ids or raw_requires_native_reference
        if not requires_native_reference:
            return
        if self._input_fidelity_is_required(asset_plan):
            return
        from app.providers.base import ProviderCapabilityMismatchError

        raise ProviderCapabilityMismatchError(
            "Non-human subject identity requires a readable typed reference image and cannot fall back to text-only conditioning.",
            provider=self.provider_name,
            detail={
                "capability_id": "nonhuman_subject_identity",
                "required_asset_role": "nonhuman_identity_reference",
                "fallback": "blocked",
            },
        )

    def _app_provider(self, provider_name: str):
        if provider_name != "openai_gpt_image":
            raise ValueError(f"V3 production rendering requires GPT Image 2, not {provider_name}.")
        from app.providers.openai_image import OpenAIGPTImageProvider

        return OpenAIGPTImageProvider(model="gpt-image-2")

    def _select_provider(self, reference_assets: list[dict[str, Any]]) -> str:
        from app.config import settings

        self._import_v1_v2_provider_config(settings)
        if settings.openai_api_key:
            return "openai_gpt_image"
        raise ValueError(
            "GPT Image 2 is the sole production renderer for V3 and its OpenAI-compatible "
            "API is not configured. Configure OPENAI_API_KEY/OPENAI_BASE_URL or the shared "
            "Lab OpenAI-compatible settings before starting real V3 generation."
        )

    def _import_v1_v2_provider_config(self, settings) -> None:
        if not settings.openai_api_key and getattr(settings, "lab_openai_api_key", None):
            settings.openai_api_key = settings.lab_openai_api_key
        if not settings.openai_base_url and getattr(settings, "lab_openai_base_url", None):
            settings.openai_base_url = settings.lab_openai_base_url

    def _reference_assets(self, request: GenerationRequest) -> list[dict[str, Any]]:
        raw_assets = request.metadata.get("uploaded_assets")
        if not isinstance(raw_assets, list):
            raw_assets = request.generation_plan.metadata.get("uploaded_assets", [])
        raw_project_refs = request.metadata.get("reference_assets")
        if not isinstance(raw_project_refs, list):
            raw_project_refs = request.generation_plan.metadata.get("reference_assets", [])
        combined_assets = [
            *(raw_project_refs if isinstance(raw_project_refs, list) else []),
            *(raw_assets if isinstance(raw_assets, list) else []),
        ]
        combined_assets = self._apply_adaptive_reference_selection(request, combined_assets)
        assets: list[dict[str, Any]] = []
        seen_evidence: dict[tuple[str, str], int] = {}
        resolution_audit: dict[str, Any] = {
            "retained": [],
            "suppressed": [],
            "unresolved": [],
        }
        for item in combined_assets:
            data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item or {})
            path = data.get("file_path")
            metadata = data.get("metadata") if isinstance(data.get("metadata"), dict) else {}
            source_type = str(data.get("source_type") or metadata.get("source_type") or "")
            source_id = str(
                data.get("output_id")
                or data.get("asset_id")
                or data.get("asset_ref_id")
                or data.get("reference_id")
                or ""
            )
            is_selected_generated = source_type in {"selected_output", "generated_selected"}
            requires_canonical_binding = bool(
                is_selected_generated
                and (
                    request.metadata.get("project_id")
                    or data.get("provider_input_required")
                    or metadata.get("selected_project_anchor")
                )
            )
            selected_file_is_materialized = False
            if path:
                try:
                    selected_file_is_materialized = Path(str(path)).is_file()
                except TypeError:
                    selected_file_is_materialized = False
            has_canonical_binding = bool(
                data.get("output_id")
                and path
                and (metadata.get("canonical_output_binding") or data.get("source_integrity_id") or metadata.get("source_integrity_id"))
                and selected_file_is_materialized
            )
            if requires_canonical_binding and not has_canonical_binding:
                resolution_audit["unresolved"].append(
                    {
                        "source_id": source_id,
                        "reason": "selected_generated_output_not_materialized"
                        if path and not selected_file_is_materialized
                        else "selected_generated_output_not_canonical",
                    }
                )
                continue
            if not path:
                resolution_audit["suppressed"].append({"source_id": source_id, "reason": "missing_file_path"})
                continue
            try:
                file_path = Path(str(path))
            except TypeError:
                resolution_audit["suppressed"].append({"source_id": source_id, "reason": "invalid_file_path"})
                continue
            if not file_path.exists() or not file_path.is_file():
                resolution_audit["suppressed"].append({"source_id": source_id, "reason": "file_not_available"})
                continue
            resolved_path = str(file_path.resolve())
            role = str(data.get("role") or data.get("use_policy") or "unknown_reference")
            use_policy = str(data.get("use_policy") or "")
            lock_targets = tuple(
                sorted(str(value).strip() for value in data.get("lock_targets", []) if str(value).strip())
            )
            content_fingerprint = self._reference_content_fingerprint(file_path)
            canonical_role = self._reference_evidence_role(role, use_policy)
            evidence_key = (content_fingerprint or f"path:{resolved_path}", canonical_role)
            if evidence_key in seen_evidence:
                existing = assets[seen_evidence[evidence_key]]
                existing["lock_targets"] = sorted(set(existing.get("lock_targets", [])) | set(lock_targets))
                if not existing.get("use_policy") and use_policy:
                    existing["use_policy"] = use_policy
                if not existing.get("source_type") and source_type:
                    existing["source_type"] = source_type
                existing["provider_input_required"] = bool(
                    existing.get("provider_input_required") or data.get("provider_input_required")
                )
                metadata = dict(existing.get("metadata") or {})
                duplicate_ids = self._string_list(metadata.get("deduplicated_source_asset_ids"))
                duplicate_ids.append(
                    str(data.get("asset_id") or data.get("source_id") or data.get("output_id") or file_path.stem)
                )
                metadata["deduplicated_source_asset_ids"] = _dedupe(duplicate_ids)
                metadata["doc93_content_role_deduplicated"] = True
                existing["metadata"] = metadata
                resolution_audit["suppressed"].append(
                    {"source_id": source_id, "reason": "duplicate_source_content", "retained_source_id": existing.get("asset_id")}
                )
                continue
            seen_evidence[evidence_key] = len(assets)
            assets.append(
                {
                    "asset_id": str(data.get("asset_id") or data.get("source_id") or data.get("output_id") or file_path.stem),
                    "role": role,
                    "source_type": str(data.get("source_type") or (data.get("metadata") or {}).get("source_type") or ""),
                    "asset_ref_id": data.get("asset_ref_id") or data.get("reference_id"),
                    "output_id": data.get("output_id"),
                    "filename": data.get("filename") or file_path.name,
                    "mime_type": data.get("mime_type"),
                    "file_path": str(file_path),
                    "uri": data.get("uri"),
                    "strength": data.get("strength"),
                    "use_policy": use_policy,
                    "lock_targets": list(lock_targets),
                    "provider_input_required": bool(data.get("provider_input_required")),
                    "prompt_only_fallback": bool(data.get("prompt_only_fallback")),
                    "metadata": data.get("metadata") if isinstance(data.get("metadata"), dict) else {},
                }
            )
            resolution_audit["retained"].append(
                {
                    "source_id": source_id or str(data.get("asset_id") or file_path.stem),
                    "source_integrity_id": data.get("source_integrity_id") or metadata.get("source_integrity_id") or content_fingerprint,
                    "output_id": data.get("output_id"),
                }
            )
        required_unresolved = [
            entry
            for entry in resolution_audit["unresolved"]
            if entry.get("source_id")
        ]
        resolution_audit["no_substitution"] = True
        resolution_audit["required_reference_unresolved"] = bool(required_unresolved)
        request.metadata["provider_reference_resolution_audit"] = resolution_audit
        if required_unresolved:
            raise ValueError("A required selected generated reference is not materialized; no substitute provider input is allowed.")
        return assets[:6]

    def _apply_adaptive_reference_selection(
        self,
        request: GenerationRequest,
        combined_assets: list[Any],
    ) -> list[dict[str, Any]]:
        cluster = self._visual_cluster(request)
        plan = cluster.get("adaptive_reference_selection_plan") if isinstance(cluster, dict) else None
        package = cluster.get("subject_continuity_asset_package") if isinstance(cluster, dict) else None
        if not isinstance(plan, dict) or not plan.get("applies") or not isinstance(package, dict):
            return [item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item or {}) for item in combined_assets]

        evidence_items = package.get("evidence") if isinstance(package.get("evidence"), list) else []
        evidence_by_alias: dict[str, dict[str, Any]] = {}
        for evidence in evidence_items:
            if not isinstance(evidence, dict):
                continue
            for value in (evidence.get("source_id"), evidence.get("asset_id"), evidence.get("output_id")):
                if value:
                    evidence_by_alias[str(value)] = evidence

        role_recipe = self._mode_role_recipe(request)
        runtime_direction = " ".join(
            value
            for value in (
                self._provider_user_direction(request),
                str(role_recipe.get("angle_rule") or ""),
                str(role_recipe.get("camera_distance") or ""),
                str(role_recipe.get("crop_rule") or ""),
                str(role_recipe.get("shot_family") or ""),
            )
            if value
        )

        runtime_view = infer_target_view(runtime_direction)
        runtime_framing = infer_target_framing(runtime_direction)
        if runtime_view == "unknown":
            runtime_view = str(plan.get("target_view") or "unknown")
        if runtime_framing == "unknown":
            runtime_framing = str(plan.get("target_framing") or "unknown")

        requested_order = [str(value) for value in plan.get("ordered_source_ids", []) if value]
        requested_rank = {source_id: index for index, source_id in enumerate(requested_order)}
        excluded = {str(value) for value in plan.get("excluded_source_ids", []) if value}
        try:
            max_identity_sources = max(1, min(int(plan.get("max_identity_sources") or 3), 6))
        except (TypeError, ValueError):
            max_identity_sources = 3
        prepared: list[tuple[dict[str, Any], dict[str, Any] | None, str]] = []
        for raw in combined_assets:
            data = raw.model_dump(mode="json") if hasattr(raw, "model_dump") else dict(raw or {})
            aliases = [
                str(value)
                for value in (
                    data.get("source_id"),
                    data.get("asset_id"),
                    data.get("asset_ref_id"),
                    data.get("reference_id"),
                    data.get("output_id"),
                    data.get("created_from_output_id"),
                )
                if value
            ]
            evidence = next((evidence_by_alias[value] for value in aliases if value in evidence_by_alias), None)
            source_id = str(evidence.get("source_id") or aliases[0]) if evidence else (aliases[0] if aliases else "")
            if evidence and source_id in excluded and source_id not in requested_rank:
                continue
            metadata = dict(data.get("metadata") or {})
            if evidence:
                metadata.update(
                    {
                        "doc97_subject_continuity": True,
                        "subject_continuity_source_id": source_id,
                        "subject_continuity_authority": evidence.get("authority"),
                        "subject_continuity_view_hint": evidence.get("view_hint"),
                        "subject_continuity_framing_hint": evidence.get("framing_hint"),
                        "subject_continuity_trust_score": evidence.get("trust_score"),
                    }
                )
            data["metadata"] = metadata
            prepared.append((data, evidence, source_id))

        identity_entries = [item for item in prepared if item[1] is not None]
        other_entries = [item for item in prepared if item[1] is None]
        identity_entries.sort(
            key=lambda item: self._adaptive_reference_sort_key(
                item[1] or {},
                source_id=item[2],
                requested_rank=requested_rank,
                target_view=runtime_view,
                target_framing=runtime_framing,
            )
        )
        identity_entries = identity_entries[:max_identity_sources]
        applied_ids = [item[2] for item in identity_entries if item[2]]
        ordered_assets = [item[0] for item in [*identity_entries, *other_entries]]
        for data in ordered_assets:
            metadata = dict(data.get("metadata") or {})
            metadata["doc97_adaptive_reference_selection"] = {
                "requested_source_ids": requested_order,
                "applied_source_ids": applied_ids,
                "target_view": runtime_view,
                "target_framing": runtime_framing,
                "max_identity_sources": max_identity_sources,
            }
            data["metadata"] = metadata
        return ordered_assets

    def _adaptive_reference_sort_key(
        self,
        evidence: dict[str, Any],
        *,
        source_id: str,
        requested_rank: dict[str, int],
        target_view: str,
        target_framing: str,
    ) -> tuple[int, int, int, int, float]:
        authority = str(evidence.get("authority") or "")
        authority_rank = {
            "user_selected_master": 0,
            "uploaded_root_truth": 1,
            "reviewed_generated_support": 2,
            "unreviewed_generated_support": 3,
        }.get(authority, 4)
        view_hint = str(evidence.get("view_hint") or "unknown")
        framing_hint = str(evidence.get("framing_hint") or "unknown")
        view_rank = 0 if _doc97_view_matches(view_hint, target_view) else 1 if view_hint == "unknown" else 2
        framing_rank = 0 if target_framing == "unknown" or framing_hint == target_framing else 1
        return (
            authority_rank,
            view_rank,
            framing_rank,
            requested_rank.get(source_id, len(requested_rank) + 1),
            -_doc97_score(evidence.get("trust_score")),
        )

    def _reference_evidence_role(self, role: str, use_policy: str) -> str:
        value = f"{role} {use_policy}".lower()
        if "nonhuman_identity_reference" in value or "nonhuman_subject_identity" in value:
            return "nonhuman_subject_identity"
        if any(term in value for term in ("face", "portrait", "identity", "person", "character")):
            return "portrait_identity"
        if any(term in value for term in ("product", "packaging", "sku")):
            return "product_identity"
        if any(term in value for term in ("appearance", "wardrobe", "garment", "outfit", "clothing")):
            return "structured_appearance"
        if any(term in value for term in ("scene", "background")):
            return "scene"
        if any(term in value for term in ("style", "mood", "lighting", "color", "composition")):
            return "visual_direction"
        return value.strip() or "generic_reference"

    def _reference_content_fingerprint(self, file_path: Path) -> str:
        try:
            digest = hashlib.sha256()
            with file_path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except OSError:
            return ""

    def _asset_plan(self, request: GenerationRequest, reference_assets: list[dict[str, Any]]) -> dict[str, Any]:
        allow_product_language = self._product_language_allowed(request, reference_assets)
        human_guidance = self._human_photorealism_guidance(request)
        human_photo_context = bool(human_guidance) or self._looks_like_human_photo_request(request)
        truth_package = self._reference_truth_package(
            request,
            reference_assets,
            allow_product_language=allow_product_language,
            human_photo_context=human_photo_context,
        )
        closure = self._strong_reference_closure_package(request)
        adaptive_reference_plan = self._adaptive_reference_selection_plan(request)
        adaptive_reference_audit = next(
            (
                dict((asset.get("metadata") or {}).get("doc97_adaptive_reference_selection") or {})
                for asset in reference_assets
                if isinstance(asset.get("metadata"), dict)
                and isinstance((asset.get("metadata") or {}).get("doc97_adaptive_reference_selection"), dict)
            ),
            {},
        )
        do_not_inherit_rules = self._string_list(human_guidance.get("reference_do_not_inherit_rules"))
        reference_conflict_rules = self._reference_identity_conflict_rules(request, reference_assets)
        closure_provider_ids = set(self._string_list(closure.get("provider_reference_required_ids")))
        closure_prompt_rules = self._string_list(closure.get("provider_prompt_rules"))
        closure_negative_rules = self._string_list(closure.get("negative_prompt_rules"))
        prompt_constraint = (
            "Use this uploaded image as visual evidence for product identity, material, style, or composition."
            if allow_product_language
            else "Use this uploaded image only for the visual channels assigned by the resolved reference policy."
            if human_photo_context
            else "Use this uploaded image as visual evidence for subject style, lighting, composition, or mood."
        )
        assets = []
        suppressed_original_ids: list[str] = []
        reference_sanitization_records: list[dict[str, Any]] = []
        for index, asset in enumerate(reference_assets):
            role = str(asset.get("role") or "")
            use_policy = str(asset.get("use_policy") or role)
            truth_entry = dict((truth_package.get("sources") or {}).get(asset["asset_id"]) or {})
            truth_layers = self._string_list(truth_entry.get("truth_layers"))
            reference_policy = self._reference_channel_policy_for_asset(request, asset)
            policy_rules = self._string_list(reference_policy.get("provider_prompt_rules"))
            lock_targets = (
                self._string_list(reference_policy.get("explicit_user_locks"))
                if reference_policy
                else [str(item) for item in asset.get("lock_targets", []) if str(item).strip()]
            )
            if "nonhuman_subject_identity_truth" in truth_layers:
                reference_constraint = self._truth_layer_constraint("nonhuman_subject_identity_truth", asset)
            elif policy_rules:
                reference_constraint = " ".join(policy_rules[:4])
            elif "product" in use_policy:
                reference_constraint = (
                    "Use as a strong product identity reference; preserve shape, material, color, proportions, "
                    "logo/label position, and existing label readability without rewriting, translating, blurring, "
                    "darkening, cropping, or covering the label/logo."
                )
            elif "identity" in use_policy or "face" in role:
                if "portrait_identity_truth" in truth_layers:
                    reference_constraint = (
                        "Use as exact same-person portrait identity truth, not as a whole-image style, lighting, scene, "
                        "or beauty-template anchor. Preserve face outline width, face width/length ratio, temple-cheek-jaw "
                        "contour, cheek fullness, eye spacing and base eye size, eyebrow-eye relationship, nose-mouth "
                        "relationship, mouth scale, lip contour family, jaw/chin direction, age impression, body type, "
                        "and natural skin-tone direction. The prompt may change makeup, wardrobe, hair styling, lighting, "
                        "pose, expression, head angle, camera angle, crop, scene, and mood, but it must not turn the person "
                        "into a narrower, sharper, larger-eyed, smaller-mouthed, or generic scenario-specific beauty model."
                    )
                else:
                    reference_constraint = (
                        "Use as a strong identity anchor; preserve broad face shape, eye shape and spacing, "
                        "nose-mouth relationship, jawline direction, age impression, body type, and broad hair color/length "
                        "while allowing natural expression, pose, head angle, camera angle, crop, small hair styling variation, "
                        "and prompt-owned lighting or scene changes."
                    )
                if do_not_inherit_rules:
                    reference_constraint = f"{reference_constraint} Do not inherit: {'; '.join(do_not_inherit_rules[:4])}."
            elif human_photo_context:
                reference_constraint = (
                    "Use as a same-person portrait identity reference; preserve recognizable facial feature "
                    "relationships, face shape direction, age impression, body type, and skin-tone direction. The written "
                    "prompt controls hair, makeup, wardrobe, scene, lighting, camera, mood, and style unless explicitly locked."
                )
            elif "brand" in use_policy or "logo" in role:
                reference_constraint = "Use as a strong brand asset reference; preserve brand colors, symbol shape, and placement logic."
            else:
                reference_constraint = prompt_constraint
            if lock_targets:
                reference_constraint = f"{reference_constraint} Lock: {', '.join(lock_targets[:5])}."
            if closure_prompt_rules and (asset["asset_id"] in closure_provider_ids or not closure_provider_ids):
                reference_constraint = f"{reference_constraint} Selected-reference closure: {'; '.join(closure_prompt_rules[:4])}."
            if reference_conflict_rules and human_photo_context and "product" not in use_policy and "brand" not in use_policy:
                reference_constraint = f"{reference_constraint} Prompt conflict rule: {'; '.join(reference_conflict_rules[:4])}."
            derivatives = self._reference_truth_derivatives(
                asset,
                truth_layers,
                reference_policy=reference_policy,
            )
            for derivative in derivatives:
                assets.append(
                    {
                        "asset_id": f"{asset['asset_id']}::{derivative['derivative_kind']}",
                        "source_asset_id": asset["asset_id"],
                        "role": self._truth_layer_provider_role(derivative.get("truth_layer"), asset.get("role")),
                        "priority": self._truth_layer_priority(derivative.get("truth_layer"), asset, index)
                        + (8 if derivative.get("derivative_kind") == "portrait_identity_crop" else 0),
                        "provider_input_mode": "reference_image",
                        "storage_path": derivative["path"],
                        "filename": derivative.get("path_name") or asset.get("filename"),
                        "mime_type": "image/jpeg",
                        "prompt_constraints": [
                            self._truth_derivative_constraint(derivative, asset)
                        ],
                        "negative_constraints": closure_negative_rules[:8],
                        "strength": asset.get("strength"),
                        "use_policy": asset.get("use_policy"),
                        "reference_truth_layer": derivative.get("truth_layer"),
                        "truth_layers": truth_layers,
                        "provider_reference_derivative": True,
                        "derivative_kind": derivative.get("derivative_kind"),
                        "fallback_to_original": bool(derivative.get("fallback_to_original")),
                        "identity_color_neutralized": bool(derivative.get("identity_color_neutralized")),
                        "identity_color_retention": derivative.get("identity_color_retention"),
                        "identity_outer_color_retention": derivative.get("identity_outer_color_retention"),
                        "identity_channel_isolation_applied": bool(
                            derivative.get("identity_channel_isolation_applied")
                        ),
                        "identity_channel_isolation_profile": derivative.get(
                            "identity_channel_isolation_profile"
                        ),
                        "identity_prompt_owned_channels": derivative.get("identity_prompt_owned_channels") or [],
                        "identity_outer_context_softened": bool(
                            derivative.get("identity_outer_context_softened")
                        ),
                        "identity_background_neutralized": bool(derivative.get("identity_background_neutralized")),
                        "identity_context_reduced_by_tight_crop": bool(
                            derivative.get("identity_context_reduced_by_tight_crop")
                        ),
                        "identity_gateway_min_edge_px": derivative.get("identity_gateway_min_edge_px"),
                        "identity_evidence_scope": derivative.get("identity_evidence_scope"),
                        "identity_evidence_group_id": (
                            f"portrait_identity::{asset['asset_id']}"
                            if derivative.get("truth_layer") == "portrait_identity_truth"
                            else None
                        ),
                        "provider_reference_bytes": self._provider_reference_file_size(derivative.get("path")),
                    }
                )
            reference_sanitization = self._full_frame_reference_sanitization(
                asset,
                derivatives=derivatives,
            )
            if not reference_sanitization.get("applies") and self._should_include_original_reference(
                truth_layers=truth_layers,
                derivatives=derivatives,
                reference_policy=reference_policy,
            ):
                assets.append(
                    {
                        "asset_id": asset["asset_id"],
                        "role": _v1_reference_role(asset.get("role")),
                        "priority": self._original_reference_priority(asset, truth_layers, index),
                        "provider_input_mode": "reference_image",
                        "storage_path": asset["file_path"],
                        "filename": asset.get("filename"),
                        "mime_type": asset.get("mime_type"),
                        "prompt_constraints": [reference_constraint],
                        "negative_constraints": closure_negative_rules[:8],
                        "strength": asset.get("strength"),
                        "use_policy": asset.get("use_policy"),
                        "source_type": asset.get("source_type"),
                        "reference_truth_layer": (
                            "style_context_truth"
                            if "style_context_truth" in truth_layers
                            else truth_layers[0]
                            if truth_layers
                            else None
                        ),
                        "truth_layers": truth_layers,
                        "provider_reference_derivative": False,
                    }
                )
            else:
                suppressed_original_ids.append(asset["asset_id"])
                if reference_sanitization.get("applies"):
                    reference_sanitization_records.append(
                        {
                            "source_asset_id": asset["asset_id"],
                            "action": "suppress_full_frame_provider_reference",
                            "reason_codes": reference_sanitization.get("reason_codes") or [],
                            "retained_derivative_ids": [
                                f"{asset['asset_id']}::{item['derivative_kind']}"
                                for item in derivatives
                                if item.get("derivative_kind")
                            ],
                        }
                    )
        # Keep the provider boundary idempotent even when a historical job or
        # a legacy-to-envelope adapter supplied the same logical source twice.
        # Runtime normalization is the primary defence; this guard prevents a
        # duplicate source from becoming duplicate crop/original uploads and
        # therefore avoids extra model inputs, cost, and competing evidence.
        assets = self._dedupe_provider_reference_assets(assets)
        suppressed_original_ids = _dedupe(suppressed_original_ids)
        reference_sanitization_records = self._dedupe_reference_sanitization_records(reference_sanitization_records)
        truth_package = {
            **truth_package,
            "truth_derivative_ids": _dedupe([
                item["asset_id"]
                for item in assets
                if item.get("provider_reference_derivative") and item.get("provider_input_mode") == "reference_image"
            ]),
            "provider_reference_image_count": len(assets),
            "reference_sanitization": reference_sanitization_records,
        }
        return {
            "asset_mode": "advanced",
            "assets": assets,
            "provider_requirements": {"needs_image_reference": bool(assets), "needs_image_edit": False},
            "provider_input_plan": {
                "operation": "image_edit_with_reference_images" if assets else "generate",
                "reference_image_asset_ids": [item["asset_id"] for item in assets],
                "reference_image_count": len(assets),
                "provider_reference_total_bytes": sum(
                    int(item.get("provider_reference_bytes") or 0) for item in assets
                ),
                "identity_evidence_scopes": _dedupe(
                    [
                        str(item.get("identity_evidence_scope") or "")
                        for item in assets
                        if item.get("identity_evidence_scope")
                    ]
                ),
                "original_reference_asset_ids": _dedupe([asset["asset_id"] for asset in reference_assets]),
                "suppressed_full_frame_identity_asset_ids": suppressed_original_ids,
                "suppressed_full_frame_reference_asset_ids": suppressed_original_ids,
                "reference_sanitization": reference_sanitization_records,
                "reference_truth_layers": [
                    {
                        "asset_id": item.get("asset_id"),
                        "source_asset_id": item.get("source_asset_id") or item.get("asset_id"),
                        "role": item.get("role"),
                        "truth_layer": item.get("reference_truth_layer"),
                        "truth_layers": item.get("truth_layers") or [],
                        "derivative_kind": item.get("derivative_kind"),
                        "provider_reference_derivative": bool(item.get("provider_reference_derivative")),
                        "fallback_to_original": bool(item.get("fallback_to_original")),
                    }
                    for item in assets
                    if item.get("provider_input_mode") == "reference_image"
                ],
                "reference_truth_package": truth_package,
                "requires_image_reference": bool(assets),
                "adaptive_reference_selection_plan": adaptive_reference_plan,
                "adaptive_reference_selection_applied": bool(adaptive_reference_plan),
                "adaptive_reference_requested_source_ids": self._string_list(
                    adaptive_reference_audit.get("requested_source_ids")
                ),
                "adaptive_reference_applied_source_ids": self._string_list(
                    adaptive_reference_audit.get("applied_source_ids")
                ),
                "adaptive_reference_target_view": adaptive_reference_audit.get("target_view"),
                "adaptive_reference_target_framing": adaptive_reference_audit.get("target_framing"),
            },
        }

    def _dedupe_provider_reference_assets(self, assets: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Coalesce repeated physical provider inputs without collapsing distinct truth sources."""

        unique: list[dict[str, Any]] = []
        index_by_key: dict[tuple[str, str], int] = {}
        for asset in assets:
            source_id = str(asset.get("source_asset_id") or asset.get("asset_id") or "").strip()
            derivative_kind = str(asset.get("derivative_kind") or "original").strip()
            key = (source_id, derivative_kind)
            if not source_id or key not in index_by_key:
                index_by_key[key] = len(unique)
                unique.append(dict(asset))
                continue

            retained = unique[index_by_key[key]]
            retained["prompt_constraints"] = _dedupe(
                [
                    *self._string_list(retained.get("prompt_constraints")),
                    *self._string_list(asset.get("prompt_constraints")),
                ]
            )
            retained["negative_constraints"] = _dedupe(
                [
                    *self._string_list(retained.get("negative_constraints")),
                    *self._string_list(asset.get("negative_constraints")),
                ]
            )
            retained["truth_layers"] = _dedupe(
                [
                    *self._string_list(retained.get("truth_layers")),
                    *self._string_list(asset.get("truth_layers")),
                ]
            )
            retained["priority"] = max(
                int(retained.get("priority") or 0),
                int(asset.get("priority") or 0),
            )
            retained["provider_input_deduplicated"] = True
        return unique

    @staticmethod
    def _dedupe_reference_sanitization_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for record in records:
            key = (str(record.get("source_asset_id") or ""), str(record.get("action") or ""))
            if key in seen:
                continue
            seen.add(key)
            unique.append(record)
        return unique

    def _should_include_original_reference(
        self,
        *,
        truth_layers: list[str],
        derivatives: list[dict[str, Any]],
        reference_policy: dict[str, Any],
    ) -> bool:
        if not derivatives or not reference_policy:
            return True
        if set(truth_layers) != {"portrait_identity_truth"}:
            return True
        has_identity_crop = any(
            item.get("derivative_kind") == "portrait_identity_crop"
            for item in derivatives
        )
        if not has_identity_crop:
            return True
        non_identity_channels = (
            "hair_direction",
            "makeup_style",
            "wardrobe_structure",
            "accessory_system",
            "lighting_color",
            "scene_background",
            "camera_composition",
            "mood_art_direction",
            "style_finish",
        )
        has_explicit_reference_channel = any(
            str(reference_policy.get(channel) or "") in {"hard", "medium", "soft"}
            for channel in non_identity_channels
        )
        return has_explicit_reference_channel

    def _full_frame_reference_sanitization(
        self,
        asset: dict[str, Any],
        *,
        derivatives: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply an explicit, auditable source-artifact policy to provider input.

        The original upload is always retained in project history.  This policy
        only withholds its full frame from the upstream provider when a caller
        has established that a source artifact (for example, a social watermark)
        is not product, person, or subject truth and a focused truth derivative
        is available to retain the required evidence.
        """
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        raw_policy = metadata.get("reference_sanitization")
        policy = dict(raw_policy) if isinstance(raw_policy, dict) else {}
        requested = bool(policy.get("suppress_full_frame_provider_reference"))
        usable_derivatives = [
            item
            for item in derivatives
            if item.get("derivative_kind") and not bool(item.get("fallback_to_original"))
        ]
        if not requested or not usable_derivatives:
            return {"applies": False}
        reason_codes = self._string_list(policy.get("reason_codes"))
        return {
            "applies": True,
            "reason_codes": reason_codes or ["source_artifact_excluded_from_truth"],
        }

    def _reference_truth_package(
        self,
        request: GenerationRequest,
        reference_assets: list[dict[str, Any]],
        *,
        allow_product_language: bool,
        human_photo_context: bool,
    ) -> dict[str, Any]:
        if not reference_assets:
            return {}
        resolved_policy_package = self._resolved_reference_policy_package(request)
        policy_payloads = resolved_policy_package.get("policies") if isinstance(resolved_policy_package, dict) else []
        structured_context = any(
            isinstance(policy, dict)
            and str(policy.get("wardrobe_structure") or "") in {"hard", "medium"}
            for policy in (policy_payloads if isinstance(policy_payloads, list) else [])
        )
        has_uploaded_human_truth = any(
            self._is_uploaded_truth_source(asset)
            and self._is_human_truth_reference(asset, human_photo_context=human_photo_context, allow_product_language=allow_product_language)
            for asset in reference_assets
        )
        has_uploaded_product_truth = any(
            self._is_uploaded_truth_source(asset)
            and self._is_product_truth_reference(asset, allow_product_language=allow_product_language)
            for asset in reference_assets
        )
        has_uploaded_nonhuman_truth = any(
            self._is_uploaded_truth_source(asset) and self._is_nonhuman_truth_reference(asset)
            for asset in reference_assets
        )
        sources: dict[str, dict[str, Any]] = {}
        source_order: list[str] = []
        truth_source_ids: list[str] = []
        for index, asset in enumerate(reference_assets):
            asset_id = str(asset.get("asset_id") or f"reference_{index + 1}")
            source_order.append(asset_id)
            is_selected = self._is_selected_generated_source(asset)
            is_nonhuman = self._is_nonhuman_truth_reference(asset)
            is_product = self._is_product_truth_reference(asset, allow_product_language=allow_product_language)
            is_human = self._is_human_truth_reference(
                asset,
                human_photo_context=human_photo_context,
                allow_product_language=allow_product_language,
            )
            layers: list[str] = []
            priority_note = "style_or_context_reference"
            channel_policy = self._reference_channel_policy_for_asset(request, asset)
            if is_nonhuman:
                layers = ["nonhuman_subject_identity_truth"]
                priority_note = (
                    "selected_nonhuman_identity_truth_source"
                    if is_selected and not has_uploaded_nonhuman_truth
                    else "nonhuman_subject_identity_truth_source"
                )
            elif channel_policy:
                if str(channel_policy.get("product_identity") or "") in {"hard", "medium"}:
                    layers.append("product_identity_truth")
                if str(channel_policy.get("identity_geometry") or "") in {"hard", "medium"}:
                    layers.append("portrait_identity_truth")
                if str(channel_policy.get("wardrobe_structure") or "") in {"hard", "medium"}:
                    layers.append("structured_appearance_truth")
                if any(
                    str(channel_policy.get(channel) or "") in {"hard", "medium", "soft"}
                    for channel in (
                        "lighting_color",
                        "scene_background",
                        "camera_composition",
                        "mood_art_direction",
                        "style_finish",
                    )
                ):
                    layers.append("style_context_truth")
                priority_note = "doc93_channel_policy_truth_source"
                if is_selected and (has_uploaded_human_truth or has_uploaded_product_truth or has_uploaded_nonhuman_truth):
                    priority_note = "selected_output_channels_below_uploaded_truth"
            elif is_product:
                if is_selected and has_uploaded_product_truth:
                    layers = ["style_context_truth"]
                    priority_note = "selected_output_context_below_uploaded_product_truth"
                else:
                    layers = ["product_identity_truth", "style_context_truth"]
                    priority_note = "product_truth_source"
            elif is_human:
                if is_selected and has_uploaded_human_truth:
                    layers = ["style_context_truth"]
                    priority_note = "selected_output_context_below_uploaded_portrait_truth"
                else:
                    layers = ["portrait_identity_truth", "style_context_truth"]
                    priority_note = "portrait_identity_truth_source"
                    if self._asset_mentions_structured_appearance(asset):
                        layers.insert(1, "structured_appearance_truth")
                        priority_note = "portrait_and_structured_appearance_truth_source"
            else:
                layers = ["style_context_truth"]
            if any(layer.endswith("_truth") and layer != "style_context_truth" for layer in layers):
                truth_source_ids.append(asset_id)
            sources[asset_id] = {
                "asset_id": asset_id,
                "source_type": asset.get("source_type") or "",
                "role": asset.get("role") or "",
                "use_policy": asset.get("use_policy") or "",
                "truth_layers": layers,
                "priority_note": priority_note,
                "uploaded_truth_source": self._is_uploaded_truth_source(asset),
                "selected_generated_source": is_selected,
                "source_rank": index + 1,
            }
        return {
            "version": "doc85_reference_truth_v1",
            "active": bool(sources),
            "source_order": _dedupe(source_order),
            "truth_source_ids": _dedupe(truth_source_ids),
            "truth_derivative_ids": [],
            "sources": sources,
            "priority_rules": [
                "uploaded human, product, or non-human subject truth remains highest for identity-critical details",
                "selected generated outputs contribute only their resolved channels and never replace uploaded truth or a new explicit prompt",
                "reference truth beats generic archetype wording",
            ],
            "structured_appearance_context": structured_context,
        }

    def _reference_truth_derivatives(
        self,
        asset: dict[str, Any],
        truth_layers: list[str],
        *,
        reference_policy: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        provider_layers = [layer for layer in truth_layers if layer in {"portrait_identity_truth", "product_identity_truth", "structured_appearance_truth"}]
        if not provider_layers:
            return []
        try:
            from app.services.provider_reference import prepare_reference_truth_derivatives

            return prepare_reference_truth_derivatives(
                asset.get("file_path"),
                asset_id=str(asset.get("asset_id") or ""),
                truth_layers=provider_layers,
                reference_policy=reference_policy,
            )
        except Exception:
            return []

    def _is_uploaded_truth_source(self, asset: dict[str, Any]) -> bool:
        source_type = str(asset.get("source_type") or "").lower()
        if "upload" in source_type:
            return True
        if asset.get("asset_ref_id") and not asset.get("output_id"):
            return True
        asset_id = str(asset.get("asset_id") or "").lower()
        return asset_id.startswith("v3_asset") or asset_id.startswith("uploaded")

    def _is_selected_generated_source(self, asset: dict[str, Any]) -> bool:
        source_type = str(asset.get("source_type") or "").lower()
        if "selected" in source_type or "generated" in source_type:
            return True
        asset_id = str(asset.get("asset_id") or "").lower()
        return bool(asset.get("output_id")) or asset_id.startswith("v3_output")

    def _is_product_truth_reference(self, asset: dict[str, Any], *, allow_product_language: bool) -> bool:
        text = self._asset_reference_text(asset)
        if "product" in text or "packaging" in text or "logo" in text or "brand" in text:
            return allow_product_language or "product" in text
        return False

    def _is_nonhuman_truth_reference(self, asset: dict[str, Any]) -> bool:
        role = str(asset.get("role") or "").strip().lower()
        use_policy = str(asset.get("use_policy") or "").strip().lower()
        return role in {"nonhuman_identity_reference", "nonhuman_subject_identity"} or use_policy in {
            "nonhuman_identity_reference",
            "nonhuman_subject_identity",
        }

    def _is_human_truth_reference(
        self,
        asset: dict[str, Any],
        *,
        human_photo_context: bool,
        allow_product_language: bool,
    ) -> bool:
        text = self._asset_reference_text(asset)
        if any(term in text for term in ["portrait", "identity", "face", "character", "person", "human"]):
            return not self._is_product_truth_reference(asset, allow_product_language=allow_product_language)
        return human_photo_context and not allow_product_language and "logo" not in text and "brand" not in text

    def _asset_mentions_structured_appearance(self, asset: dict[str, Any]) -> bool:
        text = self._asset_reference_text(asset)
        terms = [
            "outfit",
            "wardrobe",
            "garment",
            "clothing",
            "dress",
            "robe",
            "collar",
            "sleeve",
            "sash",
            "belt",
            "layer",
            "pattern",
            "embroidery",
            "trim",
            "accessory",
        ]
        return any(term in text for term in terms)

    def _asset_reference_text(self, asset: dict[str, Any]) -> str:
        parts = [
            asset.get("role"),
            asset.get("use_policy"),
            asset.get("strength"),
            asset.get("filename"),
            asset.get("source_type"),
            " ".join(str(item) for item in asset.get("lock_targets", []) if str(item).strip()),
        ]
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        parts.extend(str(value) for value in metadata.values() if isinstance(value, (str, int, float)))
        return " ".join(str(part or "") for part in parts).lower()

    def _truth_layer_provider_role(self, truth_layer: Any, fallback_role: Any) -> str:
        layer = str(truth_layer or "")
        if layer == "portrait_identity_truth":
            return "portrait_identity"
        if layer == "nonhuman_subject_identity_truth":
            return "subject_reference"
        if layer in {"product_identity_truth", "structured_appearance_truth"}:
            return "subject_reference"
        return _v1_reference_role(str(fallback_role or "unknown_reference"))

    def _truth_layer_priority(self, truth_layer: Any, asset: dict[str, Any], index: int) -> int:
        layer = str(truth_layer or "")
        source_bonus = 40 if self._is_uploaded_truth_source(asset) else 0
        base = {
            "portrait_identity_truth": 260,
            "nonhuman_subject_identity_truth": 258,
            "product_identity_truth": 255,
            "structured_appearance_truth": 250,
        }.get(layer, 180)
        return base + source_bonus - index

    def _original_reference_priority(self, asset: dict[str, Any], truth_layers: list[str], index: int) -> int:
        source_bonus = 30 if self._is_uploaded_truth_source(asset) else 0
        if any(layer in {"portrait_identity_truth", "nonhuman_subject_identity_truth", "product_identity_truth", "structured_appearance_truth"} for layer in truth_layers):
            return 170 + source_bonus - index
        return (120 if asset.get("strength") == "hard" else 100) + source_bonus - index

    def _truth_layer_constraint(self, truth_layer: Any, asset: dict[str, Any]) -> str:
        layer = str(truth_layer or "")
        filename = asset.get("filename") or asset.get("asset_id") or "uploaded reference"
        if layer == "portrait_identity_truth":
            return (
                f"Reference truth layer from {filename}: exact portrait identity truth. Preserve the same recognizable person, "
                "including face outline width, face width/length ratio, temple-cheek-jaw contour, cheek fullness, eye shape and spacing, "
                "base eye size, eyelid direction, eyebrow arc and thickness, nose-mouth relationship, mouth scale, lip contour family, "
                "jaw/chin direction, midface temperament, natural age impression, body identity direction, and natural skin-tone direction. "
                "The prompt may change expression, gaze, pose, head angle, camera angle, crop, scene, lighting, makeup, and costume, "
                "but must not replace the face with a narrower, sharper, larger-eyed, smaller-mouthed, V-chin, or generic AI beauty model."
            )
        if layer == "nonhuman_subject_identity_truth":
            return (
                f"Reference truth layer from {filename}: exact individual non-human subject identity truth. Preserve stable morphology, "
                "head geometry, body proportions, distinctive markings or pattern, and visible coat, feather, scale, or surface character. "
                "The prompt may change habitat, action, camera, lighting, color treatment, and finish, but must not replace the individual "
                "or use the source habitat, lighting, or whole-image style as an unrequested template."
            )
        if layer == "product_identity_truth":
            return (
                f"Reference truth layer from {filename}: exact product truth. Preserve the same product instance, shape, proportions, material identity, "
                "color identity, packaging silhouette, surface finish, and visible label/logo placement. The scene, crop, camera angle, and lighting may change, "
                "but do not invent a new product or drift label/logo positions."
            )
        if layer == "structured_appearance_truth":
            return (
                f"Reference truth layer from {filename}: exact structured appearance truth. Preserve silhouette, layer order, collar or neckline logic, "
                "sleeve and cuff logic, closure/sash/belt logic, material behavior, transparency family, pattern or embroidery family, trim placement, "
                "and accessory placement while allowing pose, crop, camera, scene, and fabric motion to vary."
            )
        return f"Use {filename} as style and context truth only."

    def _truth_derivative_constraint(self, derivative: dict[str, Any], asset: dict[str, Any]) -> str:
        base = self._truth_layer_constraint(derivative.get("truth_layer"), asset)
        kind = str(derivative.get("derivative_kind") or "")
        if kind == "portrait_identity_crop":
            return (
                "Complementary crop 1 of one single uploaded person, not a separate candidate: use this feature-detail "
                "view for brow-eye geometry, eye shape and spacing, nose bridge/tip/wings, nose-mouth relationship, "
                "philtrum, mouth width, and lip contour. Ignore its hair styling, clothing, background, light, and color grade. "
                + base
            )
        if kind == "portrait_identity_geometry_crop":
            return (
                "Complementary crop 2 of the same single uploaded person, not a separate candidate: use this head-geometry "
                "view for forehead-midface-lower-face proportion, temple-cheek-jaw contour, face width/length, cheek volume, "
                "jaw slope, and chin scale. Ignore its hair styling, clothing, background, light, and color grade. "
                + base
            )
        return base

    def _provider_reference_file_size(self, path: Any) -> int | None:
        try:
            return int(Path(str(path)).stat().st_size)
        except (OSError, TypeError, ValueError):
            return None

    def _provider_reference_asset_summary(self, asset_plan: dict[str, Any]) -> list[dict[str, Any]]:
        summaries: list[dict[str, Any]] = []
        for item in asset_plan.get("assets", []) if isinstance(asset_plan, dict) else []:
            if item.get("provider_input_mode") != "reference_image":
                continue
            summaries.append(
                {
                    "asset_id": item.get("asset_id"),
                    "source_asset_id": item.get("source_asset_id") or item.get("asset_id"),
                    "role": item.get("role"),
                    "truth_layer": item.get("reference_truth_layer"),
                    "truth_layers": item.get("truth_layers") or [],
                    "provider_reference_derivative": bool(item.get("provider_reference_derivative")),
                    "derivative_kind": item.get("derivative_kind"),
                    "fallback_to_original": bool(item.get("fallback_to_original")),
                    "identity_color_neutralized": bool(item.get("identity_color_neutralized")),
                    "identity_color_retention": item.get("identity_color_retention"),
                    "identity_outer_color_retention": item.get("identity_outer_color_retention"),
                    "identity_channel_isolation_applied": bool(
                        item.get("identity_channel_isolation_applied")
                    ),
                    "identity_channel_isolation_profile": item.get("identity_channel_isolation_profile"),
                    "identity_prompt_owned_channels": item.get("identity_prompt_owned_channels") or [],
                    "identity_outer_context_softened": bool(item.get("identity_outer_context_softened")),
                    "identity_background_neutralized": bool(item.get("identity_background_neutralized")),
                    "identity_context_reduced_by_tight_crop": bool(
                        item.get("identity_context_reduced_by_tight_crop")
                    ),
                    "identity_gateway_min_edge_px": item.get("identity_gateway_min_edge_px"),
                    "identity_evidence_scope": item.get("identity_evidence_scope"),
                    "identity_evidence_group_id": item.get("identity_evidence_group_id"),
                    "provider_reference_bytes": item.get("provider_reference_bytes"),
                    "filename": item.get("filename"),
                }
            )
        return summaries

    def _generation_prompt(
        self,
        request: GenerationRequest,
        reference_assets: list[dict[str, Any]],
        *,
        asset_plan: dict[str, Any] | None = None,
    ) -> str:
        prompt = request.prompt_compilation
        asset = request.asset_spec
        layout = request.layout_plan
        user_direction = self._provider_user_direction(request)
        remote_general_contract = self._uses_remote_brain_native_general_contract(request)
        visual_direction = self._provider_visual_direction(request, user_direction=user_direction)
        allow_product_language = self._product_language_allowed(request, reference_assets)
        provider_text_instruction = self._provider_native_text_instruction(
            request,
            product_language_allowed=allow_product_language,
        )
        human_guidance = self._human_photorealism_guidance(request)
        human_photo_context = bool(human_guidance) or self._looks_like_human_photo_request(request)
        reference_channel_contract = self._reference_channel_prompt_guidance(request)
        portrait_identity_contract = self._portrait_bone_structure_prompt_guidance(request)
        # A real General image whose remote Brain plan has been frozen already
        # owns its creative direction.  General's optional suite helpers may
        # describe lineage in the audit trail, but must not re-expand a single
        # Brain-authored image into local camera, role, crop, or scene recipes.
        role_guidance = [] if remote_general_contract else self._mode_role_prompt_guidance(request)
        apparel_construction_guidance = self._apparel_construction_prompt_guidance(request)
        include_supporting_notes = (allow_product_language or len(user_direction) < 180) and not remote_general_contract
        resolved_reference_policy = self._resolved_reference_policy_package(request)
        identity_evidence_prompt = self._identity_evidence_prompt(asset_plan)
        provider_hard_constraints = self._provider_hard_constraints(
            request,
            has_role_guidance=bool(role_guidance),
            has_reference_policy=bool(resolved_reference_policy),
        )
        if remote_general_contract:
            # The lossless user intent and the matched remote shot direction
            # carry the factual visual contract.  Retaining a generic reminder
            # avoids replaying the local prompt compiler's duplicated recipe
            # stack into GPT Image 2.
            provider_hard_constraints = [
                "The user's explicit factual, safety, and negative constraints are mandatory."
            ]
        composed = self._composed_visual_contribution(request) if self._activation_enforced(request) else {}
        composed_prompt = [] if remote_general_contract else self._string_list(composed.get("prompt_additions"))
        parts = [
            (
                "Create a camera-real, directly usable creative image asset for a human photo, with publishable craft but no beauty-filter retouch."
                if human_photo_context and not allow_product_language
                else
                "Create a polished, directly usable commercial product image asset."
                if allow_product_language
                else "Create a polished, directly usable creative image asset."
            ),
            (
                "Primary operation: identity-preserving portrait edit. Depict the exact same person shown in the supplied portrait evidence; edit that person's styling and scene instead of casting, averaging, beautifying, or generating a similar-looking new model. Same-person facial geometry outranks generic beauty, premium, delicate, elegant, genre, or style words."
                if identity_evidence_prompt
                else ""
            ),
            self._identity_local_repair_prompt(request),
            f"Visual direction:\n{visual_direction}",
            (
                "Active capability guidance:\n" + "\n".join(f"- {item}" for item in composed_prompt[:24])
                if composed_prompt
                else ""
            ),
            reference_channel_contract,
            portrait_identity_contract,
            identity_evidence_prompt,
            f"Asset purpose: {asset.purpose}" if asset and not remote_general_contract else "",
            (
                "Output goal: create a polished, directly usable image with a clear subject and atmosphere."
                if not remote_general_contract and not allow_product_language and len(user_direction) < 180
                else ""
            ),
            self._asset_canvas_instruction(request, asset),
            "Composition is owned by the LLM creative brief and image provider; use any planning focus only as advisory context, never as fixed coordinates or overlay lanes.",
            "Generate exactly one image; it must be a single complete image frame. Do not create a collage, split screen, contact sheet, storyboard, before-after comparison, duplicated frame, or grid of separate images inside the same output.",
            provider_text_instruction,
            *(
                [
                    "Only preserve text already visible on the supplied product label if it remains in frame; keep it readable and unobscured, and do not translate, rewrite, enlarge, blur, darken, cover, crop, or invent label copy.",
                    "Preserve supplied product facts, visible product identity, logos, label placement, material cues, proportions, and packaging silhouette.",
                ]
                if allow_product_language
                else [
                    (
                        "Preserve the requested subject, scene, style, and mood, plus explicit lighting, composition, and natural proportions."
                        if not remote_general_contract
                        else "Preserve the remote Brain's matched image direction without adding an unrelated scene or subject."
                    ),
                    "Do not add unrelated props, unrelated labels, logos, distracting objects, or objects not requested by the user.",
                ]
            ),
            f"Style notes: {', '.join(prompt.style_notes)}" if include_supporting_notes and prompt.style_notes else "",
            f"Layout notes: {', '.join(prompt.layout_notes)}" if include_supporting_notes and prompt.layout_notes else "",
            f"Hard constraints: {'; '.join(provider_hard_constraints)}" if provider_hard_constraints else "",
            apparel_construction_guidance,
        ]
        if role_guidance:
            parts.append("Role-specific generation contract:\n" + "\n".join(role_guidance))
        mode_quality = {} if remote_general_contract else self._mode_quality_profile(request)
        if mode_quality:
            mode_lines = [
                f"Mode quality: {mode_quality.get('user_visible_label') or mode_quality.get('mode')}",
                "Mode guidance: " + "; ".join(self._string_list(mode_quality.get("prompt_guidance"))[:4]),
            ]
            parts.append("Mode quality contract:\n" + "\n".join(line for line in mode_lines if not line.endswith(": ")))
        if human_guidance or (human_photo_context and not allow_product_language):
            positive = self._string_list(human_guidance.get("positive_prompt_fragments"))
            do_not_inherit = self._string_list(human_guidance.get("reference_do_not_inherit_rules"))
            lines = (
                [
                    "Real-person fidelity: preserve the requested age direction, natural proportions, visible skin texture, and believable hands; never beauty-filter, adultify, or reshape the person.",
                    "Human Realism improves rendering quality only and does not override the remote Brain's prompt-owned wardrobe, scene, lighting, camera, or styling decisions.",
                ]
                if remote_general_contract
                else [
                    "Polish interpretation: camera-ready real-person photography, never beauty-app face reshaping, face slimming, enlarged eyes, V-shaped chin, or skin-blur retouch.",
                    "Attractive realism balance: the reference person's own feature geometry and individual attractiveness are identity-owned; present them through prompt-consistent makeup, expression, camera, light, complexion, and believable texture without facial optimization, whitening, tanning, or beauty-filter remodeling.",
                    "Identity continuity: Human Realism improves rendering only; it never expands reference ownership into hair, wardrobe, lighting, scene, camera, or style.",
                    "Universal complexion and proportion guard: preserve reference or explicit prompt complexion, age direction, and natural head-to-body, neck, shoulder, and upper-body proportions; do not impose demographic lightness, tanning, or beauty-template geometry.",
                    "Batch naturalness: vary expression, gaze, pose, and angle; do not use the same expression as every output.",
                ]
            )
            if positive:
                lines.append("Photoreal human rendering: " + "; ".join(positive[:4]))
            if do_not_inherit and reference_assets:
                lines.append("Reference cleanup: " + "; ".join(do_not_inherit[:2]))
            if lines:
                parts.append("Human realism contract:\n" + "\n".join(lines))
        closure = self._strong_reference_closure_package(request)
        if closure:
            closure_lines = [
                "Reference strength: " + str(closure.get("reference_strength") or "strong"),
                "Use selected references as identity truth only for their resolved identity channels.",
                "Allow variation: " + "; ".join(self._string_list(closure.get("allowed_variations"))[:4]),
                "Do not drift: " + "; ".join(self._string_list(closure.get("forbidden_drift"))[:4]),
            ]
            parts.append("Selected reference closure:\n" + "\n".join(line for line in closure_lines if not line.endswith(": ")))
        if reference_assets:
            reference_lines = [
                (
                    f"{index + 1}. {asset.get('role') or 'reference'}"
                    f" ({asset.get('strength') or 'normal'}) - {asset.get('filename') or asset.get('asset_id')}"
                )
                for index, asset in enumerate(reference_assets)
            ]
            parts.append("Uploaded reference images must guide the result:\n" + "\n".join(reference_lines))
            conflict_rules = (
                []
                if resolved_reference_policy
                else self._reference_identity_conflict_rules(request, reference_assets)
            )
            if conflict_rules:
                parts.append("Uploaded portrait reference priority:\n" + "\n".join(conflict_rules[:6]))
            if not self._resolved_reference_policy_package(request):
                strong_reference_rules = []
                for asset in reference_assets:
                    use_policy = str(asset.get("use_policy") or asset.get("role") or "")
                    if "product" in use_policy:
                        strong_reference_rules.append(
                            "Preserve the selected product identity instead of inventing a new product; keep existing label/logo details readable and unobscured when visible."
                        )
                    elif "identity" in use_policy or human_photo_context:
                        strong_reference_rules.append(
                            "Use the portrait reference as same-person identity truth while the current prompt controls hair, makeup, wardrobe, lighting, scene, camera, mood, and style."
                        )
                    elif "brand" in use_policy:
                        strong_reference_rules.append("Preserve selected brand asset colors, symbol shape, and placement logic.")
                if strong_reference_rules:
                    parts.append("Strong reference rules: " + " ".join(dict.fromkeys(strong_reference_rules)))
            truth_prompt = self._reference_truth_prompt(
                request,
                reference_assets,
                allow_product_language=allow_product_language,
                human_photo_context=human_photo_context,
            )
            if truth_prompt:
                parts.append(truth_prompt)
        retry_guidance = self._retry_prompt_guidance(request)
        if retry_guidance:
            parts.append("Retry repair guidance: " + " ".join(retry_guidance))
        negative_guidance = self._provider_negative_guidance(request)
        if negative_guidance:
            parts.append(f"Avoid: {negative_guidance}")
        return self._provider_prompt_for_delivery(
            "\n".join(part for part in parts if str(part or "").strip()),
            protected_user_direction=user_direction,
        )

    def _apparel_construction_prompt_guidance(self, request: GenerationRequest) -> str:
        """Materialize only the frozen garment facts from the resolved ledger."""

        if not self._activation_enforced(request):
            return ""
        ledger = self._resolved_constraint_ledger(request)
        projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
        package = projection.get("apparel_construction") if isinstance(projection, dict) else None
        if not isinstance(package, dict) or not package.get("applies"):
            return ""
        facts = package.get("facts")
        if not isinstance(facts, list):
            return ""
        labels = {
            "product_silhouette": "silhouette and proportion",
            "product_pattern_registration": "print or pattern placement and scale",
            "product_layer_topology": "layer order and transparency or mesh topology",
            "product_construction_detail": "seams, hems, trim, fastenings, and accessory placement",
            "product_material_response": "material weight and surface response",
            "product_drape_behavior": "fold, tension, gravity, and drape behavior",
        }
        lines: list[str] = []
        for fact in facts:
            if not isinstance(fact, dict):
                continue
            values = self._string_list(fact.get("values"))
            label = labels.get(str(fact.get("channel") or ""))
            if label and values:
                strength = str(fact.get("strength") or "soft")
                action = "Preserve" if strength == "hard" else "Keep materially consistent" if strength == "strong" else "Treat as a soft supplied signal for"
                lines.append(f"- {action} {label}: {'; '.join(values)}")
        if not lines:
            return ""
        lines.append("These are garment construction facts only; the current brief still owns pose, expression, camera, scene, lighting, mood, and styling unless separately constrained.")
        return "Garment construction truth:\n" + "\n".join(lines)

    def _identity_local_repair_prompt(self, request: GenerationRequest) -> str:
        if not bool(request.metadata.get("identity_local_repair_active")):
            return ""
        return (
            "Identity-local repair operation: image 1 is the current generated canvas and its transparent mask is the only repair region. "
            "Restore the uploaded person's face width/length, forehead-midface-lower-face proportion, brow-eye geometry, eye spacing, "
            "nose-mouth relationship, cheek-jaw contour, and chin scale inside that region. Preserve the canvas outside the mask and keep "
            "its prompt-owned makeup direction, expression, hairstyle, wardrobe, pose, scene, lighting, camera, mood, and finish. Do not "
            "cast a new model, face-slim, enlarge eyes, sharpen the chin, copy source hair, or copy the source scene."
        )

    def _identity_evidence_prompt(self, asset_plan: dict[str, Any] | None) -> str:
        assets = asset_plan.get("assets", []) if isinstance(asset_plan, dict) else []
        identity_assets = [
            item
            for item in assets
            if item.get("reference_truth_layer") == "portrait_identity_truth"
            and item.get("provider_input_mode") == "reference_image"
        ]
        scopes = {
            str(item.get("identity_evidence_scope") or "")
            for item in identity_assets
            if item.get("identity_evidence_scope")
        }
        if not {"feature_detail", "head_geometry"}.issubset(scopes):
            return ""
        source_ids = _dedupe(
            [str(item.get("source_asset_id") or "") for item in identity_assets if item.get("source_asset_id")]
        )
        if len(source_ids) != 1:
            return ""
        return "\n".join(
            [
                "Portrait identity evidence:",
                "The two portrait reference images are complementary crops of one single uploaded person, not two people and not alternative identities.",
                "Use the feature-detail crop for brow-eye, eye spacing, nose-mouth, philtrum, mouth width, and lip-contour relationships.",
                "Use the head-geometry crop for face width/length, forehead-midface-lower-face proportion, temple-cheek-jaw contour, cheek volume, jaw slope, and chin scale.",
                "Fuse both crops into the same-person identity. Do not average them into a generic beauty face, and do not inherit their hair styling, clothing, background, lighting, or color grade unless the reference-channel policy explicitly assigns that channel.",
            ]
        )

    def _provider_user_direction(self, request: GenerationRequest) -> str:
        ledger = self._resolved_constraint_ledger(request) if self._activation_enforced(request) else {}
        projection = ledger.get("provider_projection") if isinstance(ledger, dict) else {}
        raw = str(
            projection.get("protected_user_intent")
            if isinstance(projection, dict) and projection.get("protected_user_intent")
            else request.metadata.get("normalized_input")
            or request.metadata.get("user_input")
            or ""
        ).strip()
        if not raw:
            return ""
        positive, _explicit_negative = split_positive_and_negative_prompt(raw)
        value = str(positive or raw)
        if not self._product_language_allowed(request, []):
            value = strip_negated_product_phrases(value)
        return " ".join(value.split()).strip()

    def _provider_visual_direction(self, request: GenerationRequest, *, user_direction: str) -> str:
        remote_direction = self._remote_brain_native_general_direction(request)
        if remote_direction:
            lines = [f"User request (verbatim): {user_direction}"] if user_direction else []
            lines.append(f"Remote Central Brain image direction: {remote_direction}")
            return "\n".join(lines)
        if not user_direction:
            return str(request.prompt_compilation.visual_prompt or "").strip()
        lines = [f"User request (verbatim): {user_direction}"]
        llm_brain = request.metadata.get("llm_brain") if isinstance(request.metadata.get("llm_brain"), dict) else {}
        guidance = llm_brain.get("prompt_guidance") if isinstance(llm_brain.get("prompt_guidance"), dict) else {}
        if llm_brain.get("llm_used"):
            refinements = self._provider_brain_refinement_clauses(
                str(guidance.get("optimized_direction") or ""),
                user_direction=user_direction,
            )
            if refinements:
                lines.append("Brain-refined visual decisions: " + "; ".join(refinements[:4]))
        elif len(user_direction) < 180:
            refinements = self._provider_brain_refinement_clauses(
                str(request.prompt_compilation.visual_prompt or ""),
                user_direction=user_direction,
            )
            if refinements:
                lines.append("Provider-neutral refined direction: " + "; ".join(refinements[:4]))
        if len(user_direction) < 180:
            style_notes = self._string_list(guidance.get("style_notes"))
            if style_notes:
                lines.append("Brain-refined style: " + "; ".join(_dedupe(style_notes)[:4]))
        consistency = " ".join(str(guidance.get("consistency_strategy") or "").split()).strip()
        if consistency and not self._provider_text_overlaps_user(consistency, user_direction):
            lines.append("Project continuity decision: " + consistency)
        return "\n".join(lines)

    def _uses_remote_brain_native_general_contract(self, request: GenerationRequest) -> bool:
        """Recognize the real-image General path that must stay LLM-first."""

        metadata = dict(request.metadata or {})
        scenario_id = str(
            metadata.get("scenario_id")
            or request.generation_plan.metadata.get("scenario_id")
            or ""
        ).strip()
        if scenario_id != "general_creative" or not bool(metadata.get("require_real_images")):
            return False
        llm_brain = metadata.get("llm_brain")
        if not isinstance(llm_brain, dict) or not llm_brain.get("llm_used") or llm_brain.get("fallback_used"):
            return False
        plan = llm_brain.get("image_set_plan")
        return bool(isinstance(plan, dict) and self._string_list(plan.get("shot_plan")))

    def _remote_brain_native_general_direction(self, request: GenerationRequest) -> str:
        if not self._uses_remote_brain_native_general_contract(request):
            return ""
        metadata = dict(request.metadata or {})
        llm_brain = metadata.get("llm_brain") if isinstance(metadata.get("llm_brain"), dict) else {}
        plan = llm_brain.get("image_set_plan") if isinstance(llm_brain.get("image_set_plan"), dict) else {}
        directions = self._string_list(plan.get("shot_plan"))
        try:
            output_index = int(metadata.get("output_index") or request.generation_plan.metadata.get("output_index") or 0)
        except (TypeError, ValueError):
            output_index = 0
        if output_index < 0 or output_index >= len(directions):
            return ""
        return directions[output_index]

    def _provider_brain_refinement_clauses(self, value: str, *, user_direction: str) -> list[str]:
        text = " ".join(str(value or "").split()).strip()
        if not text:
            return []
        clauses = re.split(r"(?<=[.!?。！？])\s*|\s*[;；]\s*", text)
        selected: list[str] = []
        generic_fragments = (
            "create a professionally polished image set for",
            "create a commercially polished image set for",
            "use clean composition",
            "no generated text overlays",
        )
        for clause in clauses:
            clean = " ".join(str(clause or "").split()).strip(" .;；")
            if not clean:
                continue
            lowered = clean.lower()
            if any(marker in lowered for marker in generic_fragments):
                continue
            if self._provider_text_overlaps_user(clean, user_direction):
                continue
            if clean not in selected:
                selected.append(clean)
            if len(selected) >= 4:
                break
        return selected

    def _provider_text_overlaps_user(self, value: str, user_direction: str) -> bool:
        def semantic_key(text: str) -> str:
            return "".join(character.lower() for character in str(text or "") if character.isalnum())

        value_key = semantic_key(value)
        user_key = semantic_key(user_direction)
        if not value_key or not user_key:
            return False
        if value_key in user_key or user_key in value_key:
            return True
        if len(value_key) >= 24:
            windows = [value_key[index : index + 24] for index in range(0, len(value_key) - 23, 12)]
            return bool(windows) and sum(1 for window in windows if window in user_key) >= max(1, len(windows) // 2)
        return False

    def _provider_negative_guidance(self, request: GenerationRequest) -> str:
        raw_user = str(request.metadata.get("normalized_input") or request.metadata.get("user_input") or "")
        _positive, explicit_negative = split_positive_and_negative_prompt(raw_user)
        llm_brain = request.metadata.get("llm_brain") if isinstance(request.metadata.get("llm_brain"), dict) else {}
        guidance = llm_brain.get("prompt_guidance") if isinstance(llm_brain.get("prompt_guidance"), dict) else {}
        brain_negative = self._string_list(guidance.get("negative_prompt_addons"))[:8]
        human_negative = self._string_list(self._human_photorealism_guidance(request).get("negative_prompt_fragments"))[:8]
        compiled_negative = [
            part.strip()
            for part in str(request.prompt_compilation.negative_prompt or "").replace("，", ",").split(",")
            if part.strip()
        ]
        approved_literals = self._provider_native_text_literals(request)
        framework_negative: list[str] = []
        priority_markers = (
            "identity",
            "face",
            "skin",
            "watermark",
            "text",
            "collage",
            "split screen",
            "contact sheet",
            "distorted",
            "artifact",
            "unrelated",
            "unrequested",
            "clutter",
        )
        for value in compiled_negative:
            value = self._text_safe_negative_constraint(value, approved_literals)
            if any(marker in value.lower() for marker in priority_markers):
                framework_negative.append(value)
            if len(framework_negative) >= 18:
                break
        return ", ".join(_dedupe([*explicit_negative, *brain_negative, *human_negative, *framework_negative]))

    def _reference_truth_prompt(
        self,
        request: GenerationRequest,
        reference_assets: list[dict[str, Any]],
        *,
        allow_product_language: bool,
        human_photo_context: bool,
    ) -> str:
        package = self._reference_truth_package(
            request,
            reference_assets,
            allow_product_language=allow_product_language,
            human_photo_context=human_photo_context,
        )
        sources = package.get("sources") if isinstance(package, dict) else {}
        if not isinstance(sources, dict) or not sources:
            return ""
        lines = [
            "Reference truth layering contract:",
            "Uploaded truth sources remain identity-critical for their assigned channels; selected generated references never override uploaded truth or a new explicit prompt.",
        ]
        if any("portrait_identity_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "Portrait identity truth: preserve the same person's face geometry, feature relationships, age and body direction; the current prompt still owns hair, makeup, wardrobe, camera, scene, light, mood, and style unless explicitly locked."
            )
            lines.append(
                "Same-person identity is stricter than same archetype; same archetype is not enough."
            )
            lines.append(
                "Forbidden portrait drift: generic AI beauty replacement, face slimming, enlarged eyes, V-chin distortion, new age or ethnicity direction, or a merely similar model."
            )
        if any("nonhuman_subject_identity_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "Non-human subject identity truth: preserve the referenced individual's stable morphology, head geometry, body proportions, distinctive markings or pattern, and visible coat, feather, scale, or surface character; the current prompt owns habitat, action, camera, lighting, color treatment, and finish."
            )
            lines.append(
                "Do not replace the individual with a generic subject or inherit the source habitat, lighting, or whole-image style by default."
            )
        if any("product_identity_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "Product identity truth: preserve product shape, proportions, material, color, packaging silhouette, surface finish, and visible label/logo placement while scene and camera may vary."
            )
        if any("structured_appearance_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "Structured appearance truth: preserve silhouette, layer order, neckline, sleeve/cuff, closure, material, pattern/trim, and accessory placement while pose, camera, scene, and fabric motion may vary."
            )
        return "\n".join(lines)

    def _provider_prompt_for_delivery(self, raw_prompt: str, *, protected_user_direction: str = "") -> str:
        raw_prompt = str(raw_prompt or "").strip()
        if not raw_prompt:
            return ""
        normalized_prompt = "\n".join(self._normalised_unique_prompt_lines(raw_prompt)).strip()
        configured_max = self._transport_prompt_char_cap() or self.max_provider_prompt_chars or self.provider_prompt_target_chars
        internal_budget = 6000
        max_chars = min(configured_max, len(protected_user_direction) + internal_budget) if protected_user_direction else min(configured_max, internal_budget)
        if max_chars <= 0 or len(normalized_prompt) <= max_chars:
            return normalized_prompt
        return self._compact_provider_prompt(
            normalized_prompt,
            max_chars=max_chars,
            protected_user_direction=protected_user_direction,
        )

    def _transport_prompt_char_cap(self) -> int:
        try:
            from app.config import settings

            return max(0, int(getattr(settings, "openai_image_transport_max_prompt_chars", 0) or 0))
        except (ImportError, TypeError, ValueError):
            return 0

    def _provider_prompt_audit(self, prompt: str, protected_user_direction: str) -> dict[str, Any]:
        prompt = str(prompt or "")
        user_chars = len(str(protected_user_direction or ""))
        internal_chars = max(0, len(prompt) - user_chars)
        return {
            "user_direction_chars": user_chars,
            "internal_guidance_chars": internal_chars,
            "final_provider_prompt_chars": len(prompt),
            "internal_guidance_target_chars": 6000,
            "prompt_budget_warning": internal_chars > 6000,
            "protected_sections": [
                *(["user_direction"] if protected_user_direction else []),
                *(["identity_operation"] if "Primary operation:" in prompt else []),
                *(["reference_channel_policy"] if "Reference channel policy:" in prompt else []),
                *(["identity_repair_delta"] if "Identity-local repair operation:" in prompt else []),
            ],
            "user_direction_lossless": bool(not protected_user_direction or protected_user_direction in prompt),
        }

    def _provider_hard_constraints(
        self,
        request: GenerationRequest,
        *,
        has_role_guidance: bool,
        has_reference_policy: bool,
    ) -> list[str]:
        values = self._string_list(request.prompt_compilation.hard_constraints)
        retained: list[str] = []
        generic_prefixes = (
            "use the v3-owned generation strategy",
            "generated subject, scene, style, and mood must match the user request",
            "preserve the user's detailed scene literally",
            "each generated output must be one single complete image frame",
            "each output is one single complete image frame",
            "preserve the user's requested subject and usage scenario",
            "do not change the core subject identity",
            "follow the planned suite roles",
            "follow active project reference images",
            "keep confirmed style:",
        )
        role_prefixes = (
            "follow the role-specific output direction",
            "do not repeat another planned role",
            "role difference requirement",
            "same recognizable person direction",
            "same body identity direction",
            "prompt-directed hair, wardrobe, and lighting",
            "preserve broad face shape",
            "allow expression, gaze, pose, crop",
            "identity consistency must come from stable traits",
        )
        reference_prefixes = (
            "current prompt owns its explicit visual channels",
            "reference v3_asset",
            "preserve underlying face geometry",
            "follow the current prompt for hair styling",
            "do not copy the reference image's original lighting",
            "uploaded person identity has highest priority",
            "prompt person descriptors guide styling",
            "preserve same-person bone structure",
            "keep facial features attractive",
            "realism must not make the face less beautiful",
            "keep clean attractive eyebrow design",
            "\u4fdd\u6301\u540c\u4e00\u4eba\u7269\u53ef\u8bc6\u522b\u8138\u90e8\u7ed3\u6784",
            "\u4e0d\u5f97\u6539\u53d8\u4e94\u5b98\u6bd4\u4f8b",
            "\u4e0d\u5f97\u590d\u5236\u53c2\u8003\u56fe\u539f\u59cb\u6574\u4f53\u98ce\u683c",
        )
        for value in values:
            lowered = value.lower().strip()
            if lowered.startswith("avoid:"):
                continue
            if lowered.startswith(generic_prefixes):
                continue
            if has_role_guidance and lowered.startswith(role_prefixes):
                continue
            if has_reference_policy and lowered.startswith(reference_prefixes):
                continue
            if lowered.startswith("\u4e0d\u5f97\u751f\u6210\u6587\u5b57"):
                continue
            retained.append(value)
        return _dedupe(retained)

    def _reference_identity_conflict_rules(
        self,
        request: GenerationRequest,
        reference_assets: list[dict[str, Any]],
    ) -> list[str]:
        if not reference_assets:
            return []
        if self._product_language_allowed(request, reference_assets):
            return []
        if not (self._human_photorealism_guidance(request) or self._looks_like_human_photo_request(request)):
            return []
        prompt_text = " ".join(
            str(value or "")
            for value in [
                request.prompt_compilation.visual_prompt,
                request.prompt_compilation.negative_prompt,
                " ".join(request.prompt_compilation.hard_constraints or []),
            ]
        )
        strict_face_terms = [
            "different face",
            "new face",
            "replace face",
            "change identity",
            "\u6362\u8138",
            "\u6362\u4e00\u4e2a\u4eba",
            "\u6539\u6210\u53e6\u4e00\u4e2a\u4eba",
        ]
        lower = prompt_text.lower()
        reference_policy_package = self._resolved_reference_policy_package(request)
        effective_owners = (
            reference_policy_package.get("effective_channel_owners")
            if isinstance(reference_policy_package.get("effective_channel_owners"), dict)
            else {}
        )
        wardrobe_owner = str(effective_owners.get("wardrobe_structure") or "")
        structured_appearance = wardrobe_owner.startswith("reference:") and wardrobe_owner.rsplit(":", 1)[-1] in {
            "hard",
            "medium",
        }
        rules = [
            "The uploaded portrait reference has higher priority for identity than generic beauty words in the written prompt.",
            "Generic beauty, mood, wardrobe, and scene wording must not replace facial feature relationships from the uploaded portrait identity truth.",
            "Preserve the same recognizable person: face outline width, face width/length ratio, temple-cheek-jaw contour, cheek fullness, eye shape and spacing, base eye size, nose-mouth relationship, mouth scale, lip contour family, jaw/chin direction, age impression, body type, and natural skin-tone direction.",
            (
                "Allow the prompt to change pose, expression, gaze, camera angle, scene, lighting, crop, and limited fabric motion; do not redesign the core appearance asset unless the user explicitly asks for a new one."
                if structured_appearance
                else "Allow the prompt to change pose, expression, gaze, camera angle, scene, lighting, crop, and wardrobe styling unless the user explicitly asks for exact copy."
            ),
            "Do not force a new facial geometry, narrower/sharper face, V-shaped chin, enlarged eyes, smaller mouth, new ethnicity, new age band, darker/tanned skin, or generic AI-beauty face just because the prompt asks for a mood, outfit, styling change, or location.",
        ]
        if any(term in lower or term in prompt_text for term in strict_face_terms):
            rules.append("If the prompt explicitly asks to replace the identity, follow only when it is clear; otherwise keep the uploaded reference identity.")
        return rules

    def _compact_provider_prompt(
        self,
        raw_prompt: str,
        *,
        max_chars: int | None = None,
        protected_user_direction: str = "",
    ) -> str:
        lines = self._normalised_unique_prompt_lines(raw_prompt)
        if not lines:
            return ""
        protected_indexes: set[int] = set()
        critical_prefixes = (
            "Create ",
            "Primary operation: identity-preserving portrait edit",
            "Identity-local repair operation:",
            "Reference channel policy:",
            "Doc93 channel rule:",
            "Current prompt owns",
            "Do not copy the reference image's original lighting",
            "Portrait identity contract:",
            "Reference inheritance boundary:",
            "Same person under changed styling",
            "Bone structure to preserve:",
            "Facial-feature relationships to preserve:",
            "Styling may change; preserve the reference face",
            "Forbidden identity drift:",
            "Do not inherit from source reference:",
            "Identity hero selection:",
            "Allowed identity-safe variation:",
            "Structured appearance lock:",
            "Portrait identity evidence:",
            "The two portrait reference images are complementary crops",
            "Use the feature-detail crop",
            "Use the head-geometry crop",
            "Fuse both crops into the same-person identity",
            "Generate exactly one image; it must be a single complete image frame",
            "Render user-approved literal text",
            "No literal copy is preselected",
            "Do not invent marketing text",
            "The final provider-rendered image must contain no added visible text",
            "Preserve the requested subject, scene, style, and mood",
            # These labels are the shared, ledger-backed garment truth
            # contract.  They are dynamic fact values, not a recipe: once
            # declared hard/strong truth reaches the provider boundary, prompt
            # compaction must not silently erase it.
            "Garment construction truth:",
            "- Preserve silhouette and proportion:",
            "- Preserve print or pattern placement and scale:",
            "- Preserve layer order and transparency or mesh topology:",
            "- Preserve seams, hems, trim, fastenings, and accessory placement:",
            "- Keep materially consistent material weight and surface response:",
            "- Keep materially consistent fold, tension, gravity, and drape behavior:",
            "These are garment construction facts only;",
        )
        for index, line in enumerate(lines):
            if line.startswith(critical_prefixes):
                protected_indexes.add(index)
        if protected_user_direction:
            for index, line in enumerate(lines):
                if line.startswith("User request (verbatim):") or protected_user_direction in line:
                    protected_indexes.add(index)
                    if index > 0 and lines[index - 1] == "Visual direction:":
                        protected_indexes.add(index - 1)
        protected_lines = [line for index, line in enumerate(lines) if index in protected_indexes]
        body: list[tuple[int, int, str]] = []
        avoid: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines):
            if index in protected_indexes:
                continue
            clipped = self._clip_prompt_line(line, self._provider_prompt_line_limit(line))
            priority = self._provider_prompt_priority(line)
            item = (priority, index, clipped)
            if priority >= 90:
                avoid.append(item)
            else:
                body.append(item)

        if max_chars is None:
            max_chars = self.max_provider_prompt_chars
        if max_chars is None or max_chars <= 0:
            return str(raw_prompt or "").strip()
        protected_text = "\n".join(protected_lines)
        if len(protected_text) >= max_chars:
            return protected_text
        avoid_budget = min(700, max(450, max_chars // 5))
        selected = self._fit_prompt_lines(
            sorted(body, key=lambda item: (item[0], item[1])),
            max_chars=max_chars - len(protected_text) - (1 if protected_text else 0) - avoid_budget,
        )
        used_text = "\n".join([*protected_lines, *selected])
        remaining = max_chars - len(used_text) - (1 if used_text else 0)
        selected.extend(
            self._fit_prompt_lines(
                sorted(avoid, key=lambda item: (item[0], item[1])),
                max_chars=max(0, remaining),
            )
        )
        selected_values = set(selected)
        selected_by_index = {
            index: value
            for _priority, index, value in [*body, *avoid]
            if value in selected_values
        }
        compacted = "\n".join(
            line if index in protected_indexes else selected_by_index[index]
            for index, line in enumerate(lines)
            if index in protected_indexes or index in selected_by_index
        ).strip()
        if len(compacted) <= max_chars:
            return compacted
        return protected_text or compacted[: max_chars - 1].rstrip() + "..."

    def _normalised_unique_prompt_lines(self, raw_prompt: str) -> list[str]:
        lines: list[str] = []
        seen: set[str] = set()
        for raw_line in str(raw_prompt or "").splitlines():
            line = " ".join(str(raw_line or "").split()).strip()
            if not line:
                continue
            key = line.lower()
            if key in seen:
                continue
            seen.add(key)
            lines.append(line)
        return lines

    def _fit_prompt_lines(self, items: list[tuple[int, int, str]], *, max_chars: int) -> list[str]:
        if max_chars <= 0:
            return []
        selected: list[str] = []
        used = 0
        for _priority, _index, line in items:
            if not line:
                continue
            extra = len(line) + (1 if selected else 0)
            if used + extra <= max_chars:
                selected.append(line)
                used += extra
                continue
            remaining = max_chars - used - (1 if selected else 0)
            if remaining >= 80:
                selected.append(self._clip_prompt_line(line, remaining))
            break
        return selected

    def _provider_prompt_priority(self, line: str) -> int:
        lowered = line.lower()
        if line.startswith("Create ") or line.startswith("Visual direction:"):
            return 0
        if line.startswith("Primary operation:") or line.startswith("Identity-local repair operation:"):
            return 0
        if "doc90" in lowered or "advanced reference priority" in lowered or "doc93" in lowered or "reference channel policy" in lowered:
            return 0
        if "doc88 prompt truth" in lowered or "doc88 balance contract" in lowered:
            return 0
        if "portrait identity contract" in lowered or "bone-structure identity" in lowered:
            return 1
        if line.startswith("Reference truth layering contract") or line.startswith("Uploaded portrait reference priority"):
            return 0
        if "portrait identity truth" in lowered or "same-person identity is stricter" in lowered:
            return 1
        if "human realism" in lowered or "photoreal human" in lowered or "universal complexion" in lowered:
            return 1
        if "attractive realism" in lowered or "identity continuity" in lowered or "subject identity" in lowered:
            return 1
        if (
            line.startswith("Generate exactly one")
            or line.startswith("Render user-approved literal text")
            or line.startswith("No literal copy is preselected")
            or line.startswith("Do not invent marketing text")
            or line.startswith("The final provider-rendered image must contain no added visible text")
            or line.startswith("Preserve the requested subject, scene, style, and mood")
        ):
            return 4
        if line.startswith("Role-specific generation contract") or line.startswith("Mode:") or line.startswith("This image role:"):
            return 3
        if line.startswith("Purpose:") or line.startswith("Required shot:") or line.startswith("Suite director rules:"):
            return 3
        if "strict visual" in lowered or "mode quality" in lowered or "pass conditions" in lowered:
            return 4
        if "reference" in lowered or line.startswith("Keep:") or line.startswith("Allow variation:") or line.startswith("Do not drift:"):
            return 5
        if line.startswith("Avoid:") or lowered.startswith("do not:") or " avoid:" in lowered:
            return 90
        return 20

    def _provider_prompt_line_limit(self, line: str) -> int:
        if line.startswith("Visual direction:"):
            return 1200
        if line.startswith("Avoid:"):
            return 700
        if "Doc90" in line or "advanced reference priority" in line or "Doc93" in line or "Reference channel policy" in line:
            return 900
        if line.startswith("Reference truth layering contract") or "portrait identity truth" in line:
            return 760
        if "Human realism" in line or "Photoreal human" in line or "Identity continuity" in line:
            return 520
        if "Reference inheritance boundary" in line:
            return 720
        if "Portrait identity" in line or "bone-structure" in line:
            return 700
        if "Strict visual" in line or "Suite director rules" in line or "Subject identity" in line:
            return 420
        if "reference" in line.lower():
            return 420
        return 360

    def _clip_prompt_line(self, line: str, max_chars: int) -> str:
        value = str(line or "").strip()
        if max_chars <= 0 or len(value) <= max_chars:
            return value
        return value[: max(1, max_chars - 3)].rstrip(" ,;") + "..."

    def _reference_channel_prompt_guidance(self, request: GenerationRequest) -> str:
        package = self._resolved_reference_policy_package(request)
        if not package:
            return ""
        prompt_rules = self._string_list(package.get("provider_prompt_rules"))
        selected_rules: list[str] = []
        for marker in (
            "current prompt owns",
            "preserve underlying face geometry",
        ):
            match = next((rule for rule in prompt_rules if marker in rule.lower()), None)
            if match and match not in selected_rules:
                selected_rules.append(match)
        channel_rules = [
            rule
            for rule in prompt_rules
            if "current-prompt-owned" in rule.lower()
        ]
        for rule in channel_rules:
            if rule not in selected_rules:
                selected_rules.append(rule)
        fallback_markers = (
            ("do not copy the reference image's original lighting",)
            if channel_rules
            else (
                "follow the current prompt",
                "do not copy the reference image's original lighting",
            )
        )
        for marker in fallback_markers:
            match = next((rule for rule in prompt_rules if marker in rule.lower()), None)
            if match and match not in selected_rules:
                selected_rules.append(match)
        effective_owners = package.get("effective_channel_owners")
        owner_lines = []
        if isinstance(effective_owners, dict):
            owner_lines = [
                f"{channel}={str(owner).rsplit(':', 1)[-1]}"
                for channel, owner in effective_owners.items()
                if str(owner or "").startswith("reference:")
            ]
        lines = [
            "Doc93 reference-channel contract: reference images may influence only their assigned channels.",
            *(f"Doc93 channel rule: {rule}" for rule in selected_rules[:10]),
            "Effective reference-owned channels: " + "; ".join(owner_lines[:10]) if owner_lines else "",
        ]
        return "Reference channel policy:\n" + "\n".join(line for line in lines if line)

    def _portrait_bone_structure_prompt_guidance(self, request: GenerationRequest) -> str:
        if self._activation_enforced(request) and not self._active_capability(request, "portrait_identity"):
            return ""
        role_plan = self._role_specific_generation_plan(request)
        plan_metadata = role_plan.get("metadata") if isinstance(role_plan.get("metadata"), dict) else {}
        cluster = self._visual_cluster(request)
        lock = plan_metadata.get("portrait_bone_structure_lock")
        if not isinstance(lock, dict) or not lock.get("applies"):
            lock = cluster.get("portrait_bone_structure_lock") if isinstance(cluster.get("portrait_bone_structure_lock"), dict) else {}
        styling = plan_metadata.get("styling_delta_policy")
        if not isinstance(styling, dict) or not styling.get("applies"):
            styling = cluster.get("styling_delta_policy") if isinstance(cluster.get("styling_delta_policy"), dict) else {}
        reference_policy = plan_metadata.get("portrait_reference_influence_policy")
        if not isinstance(reference_policy, dict) or not reference_policy.get("applies"):
            reference_policy = (
                cluster.get("portrait_reference_influence_policy")
                if isinstance(cluster.get("portrait_reference_influence_policy"), dict)
                else {}
            )
        balance_policy = plan_metadata.get("portrait_reference_balance_policy")
        if not isinstance(balance_policy, dict) or not balance_policy.get("applies"):
            balance_policy = (
                cluster.get("portrait_reference_balance_policy")
                if isinstance(cluster.get("portrait_reference_balance_policy"), dict)
                else {}
            )
        if not isinstance(lock, dict) or not lock.get("applies"):
            return ""
        prompt_rules = self._string_list(lock.get("prompt_rules"))
        bone_traits = self._string_list(lock.get("stable_bone_traits"))
        feature_traits = self._string_list(lock.get("stable_feature_relationships"))
        allowed = self._string_list(lock.get("allowed_surface_changes"))
        forbidden = self._string_list(lock.get("forbidden_geometry_drift"))
        styling_rules = self._string_list(styling.get("prompt_rules")) if isinstance(styling, dict) else []
        reference_rules = (
            self._string_list(reference_policy.get("prompt_rules")) if isinstance(reference_policy, dict) else []
        )
        blocked_channels = (
            self._string_list(reference_policy.get("blocked_reference_channels"))
            if isinstance(reference_policy, dict)
            else []
        )
        prompt_owned = (
            self._string_list(reference_policy.get("prompt_owned_channels")) if isinstance(reference_policy, dict) else []
        )
        prompt_truth_rules = (
            self._string_list(balance_policy.get("current_prompt_truth_rules")) if isinstance(balance_policy, dict) else []
        )
        compact_negatives = (
            self._string_list(balance_policy.get("compact_negative_guidance")) if isinstance(balance_policy, dict) else []
        )
        approved_anchor_rules = (
            self._string_list(balance_policy.get("approved_visual_anchor_rules")) if isinstance(balance_policy, dict) else []
        )
        approved_anchor_rule = next(
            (rule for rule in approved_anchor_rules if "positive visual direction anchors" in rule.lower()),
            approved_anchor_rules[0] if approved_anchor_rules else "",
        )
        selected_bone_traits = _dedupe(bone_traits[:6])
        selected_feature_traits = _dedupe(feature_traits[:7])
        lines = [
            "Doc88 balance contract: keep current prompt mood, uploaded identity truth, and approved visual direction together."
            if balance_policy
            else "",
            *prompt_truth_rules[:1],
            "Reference inheritance boundary: Identity comes from the reference; direction comes from the prompt."
            if reference_rules
            else "",
            *reference_rules[:1],
            approved_anchor_rule,
            "Prompt-owned channels: " + "; ".join(prompt_owned[:8]) if prompt_owned else "",
            "Do not inherit from source reference: " + "; ".join(blocked_channels[:8]) if blocked_channels else "",
            "Same person under changed styling; not a similar-looking new model.",
            "Same-person identity is stricter than same archetype; same archetype is not enough.",
            "Styling may change; preserve the reference face without redesigning the face.",
            *prompt_rules[:1],
            "Bone structure to preserve: " + "; ".join(selected_bone_traits) if selected_bone_traits else "",
            "Facial-feature relationships to preserve: " + "; ".join(selected_feature_traits) if selected_feature_traits else "",
            "Allowed surface styling changes: " + "; ".join(allowed[:5]) if allowed else "",
            "Forbidden identity drift: " + "; ".join(_dedupe([*compact_negatives[:3], *forbidden[:7]])) if forbidden else "",
            "Styling scope: " + "; ".join(styling_rules[:1]) if styling_rules else "",
        ]
        return "Portrait identity contract:\n" + "\n".join(line for line in lines if line)

    def _mode_role_prompt_guidance(self, request: GenerationRequest) -> list[str]:
        recipe = self._mode_role_recipe(request)
        role_plan = self._role_specific_generation_plan(request)
        if not recipe:
            role_recipes = role_plan.get("role_recipes") if isinstance(role_plan.get("role_recipes"), list) else []
            recipe = next((dict(item) for item in role_recipes if isinstance(item, dict)), {})
        if not recipe:
            return []
        policy = self._mode_execution_policy(request)
        lines = [
            f"Mode: {policy.get('mode') or recipe.get('metadata', {}).get('mode') or 'delivery_suite'}",
            f"This image role: {recipe.get('label') or recipe.get('role_key')}",
            f"Purpose: {recipe.get('purpose')}" if recipe.get("purpose") else "",
            (
                f"Required shot: {self._role_prompt_pressure_for_provider(str(recipe.get('prompt_pressure') or ''))}"
                if recipe.get("prompt_pressure")
                else ""
            ),
            f"Shot family: {recipe.get('shot_family')}" if recipe.get("shot_family") else "",
            f"Camera distance: {recipe.get('camera_distance')}" if recipe.get("camera_distance") else "",
            f"Angle: {recipe.get('angle_rule')}" if recipe.get("angle_rule") else "",
            f"Crop/layout: {recipe.get('crop_rule')}" if recipe.get("crop_rule") else "",
            f"Scene: {recipe.get('scene_rule')}" if recipe.get("scene_rule") else "",
            f"Role difference rule: {policy.get('role_difference_requirement')}" if policy.get("role_difference_requirement") else "",
        ]
        keep = self._string_list(recipe.get("must_keep_rules"))
        avoid = self._string_list(recipe.get("must_not_rules"))
        variation_axes = self._string_list(recipe.get("variation_axes"))
        metadata = recipe.get("metadata") if isinstance(recipe.get("metadata"), dict) else {}
        role_lanes = [
            ("Role expression lane", metadata.get("expression_lane")),
            ("Role gaze lane", metadata.get("gaze_lane")),
            ("Role pose lane", metadata.get("pose_lane")),
            ("Role gesture lane", metadata.get("gesture_lane")),
            ("Role subject scale", metadata.get("subject_scale_lane")),
            ("Role scene depth", metadata.get("scene_depth_lane")),
            ("Clone avoidance", metadata.get("clone_avoidance_rule")),
        ]
        if variation_axes:
            lines.append("Role variation axes: " + "; ".join(variation_axes[:8]))
        for label, value in role_lanes:
            text = str(value or "").strip()
            if text:
                lines.append(f"{label}: {text}")
        plan_prompt_additions = self._string_list(role_plan.get("prompt_additions"))
        if plan_prompt_additions:
            concise_additions: list[str] = []
            for marker in (
                "doc90 person priority",
                "doc90 conflict rule",
                "doc90 identity geometry",
                "output 1 must serve the role",
            ):
                value = next((item for item in plan_prompt_additions if marker in item.lower()), "")
                concise = self._role_prompt_pressure_for_provider(value)
                if concise and concise not in concise_additions:
                    concise_additions.append(concise)
            if concise_additions:
                lines.append("Suite director rules: " + "; ".join(concise_additions))
        plan_metadata = role_plan.get("metadata") if isinstance(role_plan.get("metadata"), dict) else {}
        identity_plan = plan_metadata.get("identity_hero_selection_plan") if isinstance(plan_metadata, dict) else {}
        if isinstance(identity_plan, dict) and identity_plan.get("applies"):
            identity_rules = self._string_list(identity_plan.get("prompt_additions"))
            if identity_rules:
                lines.append("Identity hero selection: " + "; ".join(identity_rules[:2]))
        subject_identity_card = plan_metadata.get("subject_identity_card") if isinstance(plan_metadata, dict) else {}
        if isinstance(subject_identity_card, dict) and subject_identity_card.get("applies"):
            keep_rules = self._string_list(subject_identity_card.get("identity_keep_rules"))
            feature_rules = self._string_list(subject_identity_card.get("facial_feature_integrity_rules"))
            realism_rules = self._string_list(subject_identity_card.get("beautiful_realism_rules"))
            appearance_rules = self._string_list(subject_identity_card.get("appearance_structure_rules"))
            allowed_variations = self._string_list(subject_identity_card.get("allowed_variations"))
            forbidden_drift = self._string_list(subject_identity_card.get("forbidden_drift"))
            if keep_rules or feature_rules:
                lines.append("Subject identity card: " + "; ".join([*keep_rules[:1], *feature_rules[:1]]))
            if realism_rules:
                lines.append("Beautiful realism balance: " + "; ".join(realism_rules[:1]))
            if appearance_rules:
                selected_appearance = _dedupe(
                    [
                        *appearance_rules[:1],
                        *[rule for rule in appearance_rules if "pattern family" in rule.lower()][:1],
                    ]
                )
                lines.append("Structured appearance lock: " + "; ".join(selected_appearance))
            if allowed_variations:
                lines.append("Allowed identity-safe variation: " + "; ".join(allowed_variations[:4]))
            if forbidden_drift:
                lines.append("Identity drift to avoid: " + "; ".join(forbidden_drift[:3]))
        strict_policy = plan_metadata.get("strict_visual_review_policy") if isinstance(plan_metadata, dict) else {}
        if isinstance(strict_policy, dict) and strict_policy.get("applies"):
            strict_rules = self._string_list(strict_policy.get("prompt_additions"))
            if strict_rules:
                selected_strict = [
                    strict_rules[index]
                    for index in (0, 2, 3)
                    if index < len(strict_rules)
                ]
                lines.append("Strict visual review rules: " + "; ".join(selected_strict))
            pass_conditions = self._string_list(strict_policy.get("pass_conditions"))
            if pass_conditions:
                lines.append("Strict visual pass conditions: " + "; ".join(_dedupe([pass_conditions[0], pass_conditions[-1]])))
            negative_rules = self._string_list(strict_policy.get("negative_additions"))
            if negative_rules:
                priority_negative_rules = [
                    rule
                    for rule in negative_rules
                    if rule
                    in {
                        "poreless glass-like skin",
                        "oily shiny face",
                        "nose-tip highlight",
                        "silicone face",
                        "over-smoothed skin",
                        "plastic texture",
                        "generic AI beauty identity",
                        "same type but different person",
                        "style changed face geometry",
                        "3D render",
                        "generic stock photo finish",
                        "overprocessed HDR finish",
                    }
                ]
                lines.append("Strict visual avoid: " + "; ".join(_dedupe(priority_negative_rules)))
        lines.extend(self._concise_module_prompt_line(line, max_items=3) for line in provider_casebook_prompt_lines(recipe))
        if keep:
            lines.append("Keep: " + "; ".join(keep[:3]))
        if avoid:
            approved_literals = self._provider_native_text_literals(request)
            lines.append(
                "Do not: "
                + "; ".join(
                    self._text_safe_negative_constraint(value, approved_literals)
                    for value in avoid[:3]
                )
            )
        return [line for line in lines if str(line or "").strip()]

    def _role_prompt_pressure_for_provider(self, value: str) -> str:
        text = " ".join(str(value or "").split()).strip()
        for marker in (
            "Use a real-photo portrait atom stack:",
            "Real-camera imperfection should win over beauty-app polish",
            "; real camera photograph",
        ):
            if marker in text:
                text = text.split(marker, 1)[0].rstrip(" ;.")
        return text

    def _concise_module_prompt_line(self, value: str, *, max_items: int = 4) -> str:
        line = " ".join(str(value or "").split()).strip()
        heading, separator, body = line.partition(":")
        if not separator:
            return line
        items = [item.strip() for item in body.split(";") if item.strip()]
        return f"{heading}: {'; '.join(items[:max_items])}" if items else line

    def _negative_constraints(self, request: GenerationRequest) -> list[str]:
        allow_product_language = self._product_language_allowed(request, [])
        approved_literals = self._provider_native_text_literals(request)
        values = [
            "new visible text",
            "invented captions",
            "typography overlays",
            "infographic icons",
            "claim badges",
            "bottom feature strips",
            "unreadable text",
            "fake brand marks",
            "watermarks",
            "signatures",
            "AI-generated marks",
            "cluttered composition",
            "collage",
            "split screen",
            "multi-panel layout",
            "contact sheet",
            "storyboard",
            "before-after comparison",
            "duplicated frames",
            "grid of separate images inside one output",
        ]
        if allow_product_language:
            values.extend(["unsupported product claims", "distorted product identity"])
        else:
            values.extend(
                [
                    "unrelated props",
                    "unrelated labels",
                    "unrequested distracting objects",
                ]
            )
        if request.prompt_compilation.negative_prompt:
            values.extend(part.strip() for part in request.prompt_compilation.negative_prompt.split(",") if part.strip())
        retry_patch = self._retry_patch(request)
        values.extend(self._string_list(retry_patch.get("negative_additions")))
        values.extend(self._string_list(retry_patch.get("negative_prompt_additions")))
        values.extend(self._string_list(retry_patch.get("object_removal_instruction")))
        values.extend(self._string_list(retry_patch.get("artifact_repair")))
        role_recipe = self._mode_role_recipe(request)
        values.extend(self._string_list(role_recipe.get("negative_pressure")))
        values.extend(self._string_list(role_recipe.get("must_not_rules")))
        role_plan = self._role_specific_generation_plan(request)
        values.extend(self._string_list(role_plan.get("negative_additions")))
        human_guidance = self._human_photorealism_guidance(request)
        values.extend(self._string_list(human_guidance.get("negative_prompt_fragments")))
        closure = self._strong_reference_closure_package(request)
        values.extend(self._string_list(closure.get("negative_prompt_rules")))
        mode_quality = self._mode_quality_profile(request)
        values.extend(self._string_list(mode_quality.get("negative_guidance")))
        if self._activation_enforced(request):
            values.extend(
                self._string_list(self._composed_visual_contribution(request).get("negative_additions"))
            )
        return list(
            dict.fromkeys(
                self._text_safe_negative_constraint(value, approved_literals)
                for value in values
                if value
            )
        )

    def _retry_prompt_guidance(self, request: GenerationRequest) -> list[str]:
        retry_patch = self._retry_patch(request)
        guidance: list[str] = []
        prompt_additions = self._string_list(retry_patch.get("prompt_additions"))
        if prompt_additions:
            guidance.append("Improve: " + "; ".join(prompt_additions))
        identity = self._string_list(retry_patch.get("identity_reinforcement"))
        if identity:
            guidance.append("Keep identity: " + "; ".join(identity))
        product = self._string_list(retry_patch.get("product_reinforcement"))
        if product:
            guidance.append("Keep product: " + "; ".join(product))
        composition = self._string_list(retry_patch.get("composition_repair"))
        if composition:
            guidance.append("Fix composition: " + "; ".join(composition))
        artifacts = self._string_list(retry_patch.get("artifact_repair"))
        if artifacts:
            guidance.append("Fix artifacts: " + "; ".join(artifacts))
        removals = self._string_list(retry_patch.get("object_removal_instruction"))
        if removals:
            guidance.append("Remove: " + "; ".join(removals))
        references = self._string_list(retry_patch.get("reference_requirements"))
        if references:
            guidance.append("Strengthen references: " + "; ".join(references))
        return guidance

    def _product_language_allowed(self, request: GenerationRequest, reference_assets: list[dict[str, Any]]) -> bool:
        if self._activation_enforced(request):
            return self._active_capability(request, "product_identity")
        asset = request.asset_spec
        return product_language_allowed(
            template_id=request.metadata.get("template_id"),
            scenario_id=request.metadata.get("scenario_id"),
            industry=request.metadata.get("industry"),
            asset_type=asset.asset_type if asset else None,
            platform=asset.platform if asset else None,
            user_input=request.metadata.get("user_input"),
            metadata=request.metadata,
            uploaded_assets=request.metadata.get("uploaded_assets", []),
            reference_assets=[*request.metadata.get("reference_assets", []), *reference_assets],
        )

    def _provider_native_text_instruction(
        self,
        request: GenerationRequest,
        *,
        product_language_allowed: bool,
    ) -> str:
        """Express text intent to the image provider without a local overlay contract."""

        notes = request.prompt_compilation.provider_notes
        policy = str(notes.get("provider_native_text_policy") or request.prompt_compilation.text_policy or "")
        approved = self._provider_native_text_literals(request)
        if policy == "provider_native_text_forbidden" or bool(notes.get("model_text_forbidden")):
            reference_text_clause = (
                "Existing product-label evidence may remain only when supplied by the reference."
                if product_language_allowed
                else "Existing reference text may remain only when supplied by the reference."
            )
            return (
                "The final provider-rendered image must contain no added visible text, captions, badges, or claims. "
                f"Check the final pixels for text artifacts; {reference_text_clause}"
            )
        if approved:
            literals = "; ".join(f'"{value}"' for value in approved)
            return (
                f"Render user-approved literal text exactly once as part of this single complete image: {literals}. "
                "Choose typography and placement from the creative brief, generate it in the image pixels, add no extra generated text, "
                "and never create a local overlay, footer strip, or fixed text lane."
            )
        if policy == "provider_native_text_optional":
            return (
                "No literal copy is preselected. Let the LLM creative brief decide whether in-image text materially improves the requested image; "
                "do not use a canned promotional phrase, unsupported claim, watermarks, signatures, AI-generated marks, or external overlay. "
                "Any chosen text must be generated in the final image pixels and reviewed there."
            )
        prohibited = (
            "marketing copy, captions, badges, seals, watermarks, signatures, AI-generated marks, or product claims"
            if product_language_allowed
            else "marketing copy, captions, badges, seals, watermarks, signatures, AI-generated marks, or unsupported claims"
        )
        return (
            f"Do not invent {prohibited}. If the user explicitly requests in-image text, "
            "render it directly in this complete provider-generated image rather than using a local overlay."
        )

    def _provider_native_text_literals(self, request: GenerationRequest) -> list[str]:
        notes = request.prompt_compilation.provider_notes
        raw_text = notes.get("provider_native_text")
        values = raw_text if isinstance(raw_text, list) else [raw_text]
        return list(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))

    def _text_safe_negative_constraint(self, value: str, approved_literals: list[str]) -> str:
        """Keep generic no-text safeguards from negating approved literal copy."""

        text = str(value or "").strip()
        if not text or not approved_literals:
            return text
        normalized = " ".join(text.lower().replace("-", " ").split())
        conflicting = {
            "new visible text",
            "visible text",
            "do not add visible text",
            "do not add any visible text",
            "unintended generated text",
        }
        if normalized in conflicting:
            return "extra generated text beyond the approved literal"
        return text

    def _looks_like_human_photo_request(self, request: GenerationRequest) -> bool:
        if self._activation_enforced(request):
            return self._active_capability(request, "human_realism")
        recipe = self._mode_role_recipe(request)
        metadata = recipe.get("metadata") if isinstance(recipe.get("metadata"), dict) else {}
        if str(metadata.get("subject_type") or "").strip().lower() == "character":
            return True
        text = " ".join(
            [
                str(request.metadata.get("user_input") or ""),
                str(request.prompt_compilation.visual_prompt or ""),
                str(request.asset_spec.purpose if request.asset_spec else ""),
                str(recipe.get("purpose") or ""),
                str(recipe.get("prompt_pressure") or ""),
            ]
        ).lower()
        english_terms = (
            "portrait",
            "human photo",
            "real person",
            "person",
            "woman",
            "girl",
            "man",
            "model",
            "face",
            "beauty photo",
            "fashion photo",
            "editorial photo",
        )
        chinese_terms = (
            "\u4eba\u50cf",
            "\u771f\u4eba",
            "\u5199\u771f",
            "\u6444\u5f71",
            "\u6a21\u7279",
            "\u7f8e\u5973",
            "\u4eba\u7269",
            "\u5973\u751f",
            "\u5973\u5b69",
            "\u8138",
        )
        return any(
            re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) for term in english_terms
        ) or any(term in text for term in chinese_terms)

    def _scene_for_request(self, request: GenerationRequest) -> str | None:
        if request.layout_plan and request.layout_plan.background_strategy:
            return request.layout_plan.background_strategy
        if request.asset_spec:
            return request.asset_spec.purpose
        return None

    def _composition_for_request(self, request: GenerationRequest) -> str | None:
        layout = request.layout_plan
        if not layout:
            return None
        notes = [layout.product_area.position, *layout.visual_hierarchy]
        return ", ".join(item for item in notes if item)

    def _group_count_for_request(self, request: GenerationRequest) -> int:
        raw = (
            request.metadata.get("requested_image_count")
            or request.generation_plan.metadata.get("requested_image_count")
            or 2
        )
        try:
            return max(1, int(raw))
        except (TypeError, ValueError):
            return 2

    def _size_for_request(self, request: GenerationRequest) -> str:
        requested_size = str(
            request.metadata.get("requested_image_size")
            or request.generation_plan.metadata.get("requested_image_size")
            or ""
        ).strip()
        allowed_sizes = {"1024x1024", "1024x1536", "1536x1024"}
        if requested_size in allowed_sizes:
            return requested_size
        ratio = str((request.asset_spec.aspect_ratio if request.asset_spec else "") or "").strip()
        mapping = {
            "1:1": "1024x1024",
            "2:3": "1024x1536",
            "3:4": "1024x1536",
            "4:5": "1024x1536",
            "9:16": "1024x1536",
            "3:2": "1536x1024",
            "4:3": "1536x1024",
            "5:4": "1536x1024",
            "16:9": "1536x1024",
        }
        return mapping.get(ratio, "1024x1024")

    def _asset_canvas_instruction(self, request: GenerationRequest, asset: AssetSpec | None) -> str:
        if asset is None:
            return ""
        requested_size = str(
            request.metadata.get("requested_image_size")
            or request.generation_plan.metadata.get("requested_image_size")
            or ""
        ).strip()
        explicit_ratio = {
            "1024x1024": "1:1",
            "1024x1536": "2:3",
            "1536x1024": "3:2",
        }.get(requested_size)
        aspect_ratio = explicit_ratio or asset.aspect_ratio
        return f"Platform: {asset.platform.value}; aspect ratio: {aspect_ratio}"

    def _quality_for_request(self, request: GenerationRequest) -> str:
        quality_mode = str(request.metadata.get("quality_mode") or request.generation_plan.metadata.get("quality_mode") or "standard")
        return "high" if quality_mode == "strict" else "medium"

    def _app_provider_timeout_seconds(self, reference_assets: list[dict[str, Any]]) -> float:
        try:
            from app.config import settings as app_settings

            value = (
                app_settings.openai_image_edit_request_timeout_seconds
                if reference_assets
                else app_settings.openai_image_request_timeout_seconds
            )
            if bool(getattr(app_settings, "openai_image_gateway_managed_failover", False)):
                # This is V3's end-to-end client deadline. It includes a
                # finalization margin beyond the gateway's own image budget,
                # so V3 records the gateway terminal result instead of
                # canceling a final line switch prematurely. Keep this outer
                # guard slightly later than the provider's HTTP deadline so
                # the provider can convert its terminal timeout into a normal
                # failed job rather than leaving a canceled request behind.
                value = app_settings.openai_image_gateway_managed_failover_timeout_seconds
                return max(660.0, float(value)) + 5.0
        except Exception:
            value = 240.0
        return max(30.0, float(value) + 15.0)

    def _app_provider_max_attempts(self) -> int:
        try:
            from app.config import settings as app_settings

            if bool(getattr(app_settings, "openai_image_gateway_managed_failover", False)):
                return 1
        except Exception:
            pass
        return 2

    def _app_provider_transient_cooldown_seconds(self) -> float:
        try:
            from app.config import settings as app_settings

            value = app_settings.openai_image_edit_transient_cooldown_seconds
        except Exception:
            value = 12.0
        return max(0.0, min(float(value), 30.0))

def _run_async_blocking(coro, *, timeout_seconds: float | None = None):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if timeout_seconds and timeout_seconds > 0:
            return asyncio.run(asyncio.wait_for(coro, timeout=timeout_seconds))
        return asyncio.run(coro)

    result: dict[str, Any] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            result["error"] = exc

    thread = threading.Thread(target=runner, name="v3-production-provider", daemon=True)
    thread.start()
    thread.join(timeout=max(0.0, float(timeout_seconds or 0.0)) or None)
    if thread.is_alive():
        raise TimeoutError(f"V3 production provider timed out after {timeout_seconds:.0f} seconds.")
    if "error" in result:
        raise result["error"]
    return result.get("value")


def _v1_reference_role(role: str | None) -> str:
    mapping = {
        "product_reference": "subject_reference",
        "unknown_reference": "subject_reference",
        "logo_reference": "logo_overlay",
        "face_reference": "portrait_identity",
        "portrait_identity": "portrait_identity",
        "identity_reference": "portrait_identity",
        "character_reference": "portrait_identity",
        "background_reference": "background_reference",
        "composition_reference": "composition_reference",
        "style_reference": "style_reference",
        "color_reference": "style_reference",
        "negative_reference": "negative_reference",
    }
    return mapping.get(str(role or ""), "subject_reference")


def _doc97_view_matches(view_hint: str, target_view: str) -> bool:
    if target_view == "unknown":
        return view_hint in {"front", "unknown"}
    if target_view == "profile":
        return view_hint in {"left_profile", "right_profile", "profile"}
    return view_hint == target_view


def _doc97_score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
