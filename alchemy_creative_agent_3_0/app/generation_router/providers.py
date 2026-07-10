"""V3-owned generation provider contracts."""

from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import threading
import time
from typing import Any

from pydantic import BaseModel, Field

from ..creative_core.prompt_language import product_language_allowed
from ..creative_core.rules import stable_id
from ..condition_engine.providers import ProviderCapabilities
from ..schemas import AssetSpec, CandidateResult, ConditionPlan, GenerationPlan, LayoutPlan, PromptCompilationResult
from ..shared_capabilities.visual_cluster.casebook_recipes import provider_casebook_prompt_lines


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
        for source in (request.metadata, request.generation_plan.metadata, request.prompt_compilation.provider_notes):
            value = source.get("mode_role_recipe") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        return {}

    def _role_specific_generation_plan(self, request: GenerationRequest) -> dict[str, Any]:
        for source in (request.metadata, request.generation_plan.metadata):
            value = source.get("role_specific_generation_plan") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        cluster = request.metadata.get("visual_cluster") if isinstance(request.metadata, dict) else None
        value = cluster.get("role_specific_generation_plan") if isinstance(cluster, dict) else None
        return dict(value) if isinstance(value, dict) else {}

    def _mode_execution_policy(self, request: GenerationRequest) -> dict[str, Any]:
        for source in (request.metadata, request.generation_plan.metadata):
            value = source.get("mode_execution_policy") if isinstance(source, dict) else None
            if isinstance(value, dict):
                return dict(value)
        plan = self._role_specific_generation_plan(request)
        value = plan.get("policy") if isinstance(plan, dict) else None
        return dict(value) if isinstance(value, dict) else {}

    def _visual_cluster(self, request: GenerationRequest) -> dict[str, Any]:
        cluster = request.metadata.get("visual_cluster") if isinstance(request.metadata, dict) else None
        if isinstance(cluster, dict):
            return dict(cluster)
        shared = request.metadata.get("shared_capabilities") if isinstance(request.metadata, dict) else None
        if isinstance(shared, dict) and isinstance(shared.get("visual_cluster"), dict):
            return dict(shared["visual_cluster"])
        return {}

    def _human_photorealism_guidance(self, request: GenerationRequest) -> dict[str, Any]:
        cluster = self._visual_cluster(request)
        guidance = cluster.get("human_photorealism_guidance") if isinstance(cluster, dict) else None
        return dict(guidance) if isinstance(guidance, dict) and guidance.get("applies") else {}

    def _strong_reference_closure_package(self, request: GenerationRequest) -> dict[str, Any]:
        cluster = self._visual_cluster(request)
        package = cluster.get("strong_reference_closure_package") if isinstance(cluster, dict) else None
        return dict(package) if isinstance(package, dict) and package.get("active") else {}

    def _resolved_reference_policy_package(self, request: GenerationRequest) -> dict[str, Any]:
        cluster = self._visual_cluster(request)
        package = cluster.get("resolved_reference_policy_package") if isinstance(cluster, dict) else None
        if not isinstance(package, dict):
            role_plan = self._role_specific_generation_plan(request)
            metadata = role_plan.get("metadata") if isinstance(role_plan.get("metadata"), dict) else {}
            package = metadata.get("resolved_reference_policy_package") if isinstance(metadata, dict) else None
        return dict(package) if isinstance(package, dict) and package.get("applies") else {}

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
        cluster = self._visual_cluster(request)
        profile = cluster.get("mode_quality_profile") if isinstance(cluster, dict) else None
        return dict(profile) if isinstance(profile, dict) else {}


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
                return (0.61 - index * 0.02, ["commercial_hook_missing"] if index == 0 else ["fake_text_risk"])
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
    provider_version = "v3.8b-provider-output-production"
    # Keep the production path lossless by default. A numeric limit can still be
    # set by tests or a future provider-specific guard when a hard upstream
    # limit is proven, but normal local/VPS generation should use the same full
    # V3-compiled provider prompt.
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
        final_provider_prompt = str(app_request.prompt_plan.variables.get("generation_prompt") or "")
        negative_constraints = self._negative_constraints(request)
        llm_brain = request.metadata.get("llm_brain") if isinstance(request.metadata.get("llm_brain"), dict) else {}
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
            raise ValueError("V3 production provider returned no image outputs.")
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
                    "reference_asset_count": len(reference_assets),
                    "provider_reference_image_count": provider_reference_image_count,
                    "provider_input_plan": provider_input_plan,
                    "reference_truth_package": reference_truth_package,
                    "provider_reference_assets": provider_reference_assets,
                    "compiled_visual_direction": request.prompt_compilation.visual_prompt,
                    "final_provider_prompt": final_provider_prompt,
                    "negative_constraints": negative_constraints,
                    "style_notes": list(request.prompt_compilation.style_notes),
                    "layout_notes": list(request.prompt_compilation.layout_notes),
                    "llm_brain": llm_brain,
                    "llm_brain_summary": request.prompt_compilation.provider_notes.get("llm_brain_summary", {}),
                    "llm_brain_consistency_strategy": request.prompt_compilation.provider_notes.get("llm_brain_consistency_strategy"),
                    "shared_capabilities": shared_capabilities,
                    "visual_capability_cluster": visual_cluster,
                    "reference_asset_ids": [asset.get("asset_id") for asset in reference_assets],
                    "reference_truth_source_ids": reference_truth_package.get("truth_source_ids") or [],
                    "reference_truth_derivative_ids": reference_truth_package.get("truth_derivative_ids") or [],
                    "provider_raw_summary": getattr(result, "raw_response_summary", {}) or {},
                    "provider_failure_retry": provider_failure_retry,
                    "api_operation": output.get("api_operation"),
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
                        "reference_asset_count": len(reference_assets),
                        "provider_reference_image_count": provider_reference_image_count,
                        "provider_input_plan": provider_input_plan,
                        "reference_truth_package": reference_truth_package,
                        "provider_reference_assets": provider_reference_assets,
                        "compiled_visual_direction": request.prompt_compilation.visual_prompt,
                        "final_provider_prompt": final_provider_prompt,
                        "negative_constraints": negative_constraints,
                        "style_notes": list(request.prompt_compilation.style_notes),
                        "layout_notes": list(request.prompt_compilation.layout_notes),
                        "llm_brain": llm_brain,
                        "llm_brain_summary": request.prompt_compilation.provider_notes.get("llm_brain_summary", {}),
                        "llm_brain_consistency_strategy": request.prompt_compilation.provider_notes.get("llm_brain_consistency_strategy"),
                        "shared_capabilities": shared_capabilities,
                        "visual_capability_cluster": visual_cluster,
                        "reference_asset_ids": [asset.get("asset_id") for asset in reference_assets],
                        "reference_truth_source_ids": reference_truth_package.get("truth_source_ids") or [],
                        "reference_truth_derivative_ids": reference_truth_package.get("truth_derivative_ids") or [],
                        "provider_failure_retry": provider_failure_retry,
                        "api_operation": output.get("api_operation"),
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
                "reference_asset_count": len(reference_assets),
                "provider_reference_image_count": provider_reference_image_count,
                "provider_input_plan": provider_input_plan,
                "reference_truth_package": reference_truth_package,
                "provider_reference_assets": provider_reference_assets,
                "reference_asset_ids": [asset.get("asset_id") for asset in reference_assets],
                "reference_truth_source_ids": reference_truth_package.get("truth_source_ids") or [],
                "reference_truth_derivative_ids": reference_truth_package.get("truth_derivative_ids") or [],
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
            },
            warnings=warnings,
        )

    async def _generate_with_app_provider(self, provider_name: str, app_request):
        provider = self._app_provider(provider_name)
        return await provider.generate(app_request)

    def _run_app_provider_with_timeout_retry(self, provider_name: str, app_request, reference_assets: list[dict[str, Any]]):
        timeout_seconds = self._app_provider_timeout_seconds(reference_assets)
        max_attempts = 2
        attempts: list[dict[str, Any]] = []
        last_error: BaseException | None = None
        self._last_provider_failure_retry_summary = {
            "executed_count": 0,
            "max_attempts": max_attempts,
            "fresh_upstream_requests": 0,
            "final_status": "skipped",
            "attempts": attempts,
            "reference_asset_count": len(reference_assets),
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
        provider_name = self._select_provider(reference_assets)
        size = self._size_for_request(request)
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
                "generation_prompt": self._generation_prompt(request, reference_assets),
                "asset_plan": asset_plan,
                "v3_prompt_compilation_id": request.prompt_compilation.prompt_compilation_id,
                "v3_generation_plan_id": request.generation_plan.generation_plan_id,
                "v3_provider_strategy": request.generation_plan.provider_strategy.value,
                "requested_image_count": self._group_count_for_request(request),
                "requested_image_size": size,
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

    def _app_provider(self, provider_name: str):
        if provider_name == "doubao_image":
            from app.providers.doubao_image import DoubaoImageProvider

            return DoubaoImageProvider()
        if provider_name == "gemini_image":
            from app.providers.gemini_image import GeminiImageProvider

            return GeminiImageProvider()
        from app.providers.openai_image import OpenAIGPTImageProvider

        return OpenAIGPTImageProvider()

    def _select_provider(self, reference_assets: list[dict[str, Any]]) -> str:
        from app.config import settings

        self._import_v1_v2_provider_config(settings)
        default_provider = str(settings.default_image_provider or "openai_gpt_image")
        if reference_assets:
            ordered = [default_provider, "openai_gpt_image", "gemini_image", "doubao_image"]
        else:
            ordered = [default_provider, "openai_gpt_image", "doubao_image", "gemini_image"]
        errors: list[str] = []
        for provider_name in _dedupe(ordered):
            if provider_name == "mock_image":
                continue
            if provider_name == "openai_gpt_image":
                if settings.openai_api_key:
                    return provider_name
                errors.append("OPENAI_API_KEY is not configured")
            elif provider_name == "doubao_image":
                if reference_assets:
                    errors.append("DOUBAO_IMAGE_API_KEY cannot be used with uploaded reference images")
                    continue
                if settings.doubao_image_api_key:
                    return provider_name
                errors.append("DOUBAO_IMAGE_API_KEY is not configured")
            elif provider_name == "gemini_image":
                if settings.gemini_image_api_key and settings.gemini_image_generation_enabled:
                    return provider_name
                errors.append("GEMINI_IMAGE_API_KEY is not configured or Gemini image generation is disabled")
        raise ValueError(
            "No configured real image provider is available for V3 generation. "
            "Reuse the V1/V2 provider settings by configuring OPENAI_API_KEY/OPENAI_BASE_URL, "
            "DOUBAO_IMAGE_API_KEY/DOUBAO_IMAGE_BASE_URL, or GEMINI_IMAGE_API_KEY. "
            f"Checked: {'; '.join(_dedupe(errors))}."
        )

    def _import_v1_v2_provider_config(self, settings) -> None:
        if not settings.openai_api_key and getattr(settings, "lab_openai_api_key", None):
            settings.openai_api_key = settings.lab_openai_api_key
        if not settings.openai_base_url and getattr(settings, "lab_openai_base_url", None):
            settings.openai_base_url = settings.lab_openai_base_url
        if not settings.doubao_image_api_key and getattr(settings, "lab_doubao_vision_api_key", None):
            settings.doubao_image_api_key = settings.lab_doubao_vision_api_key
        if not settings.doubao_image_base_url and getattr(settings, "lab_doubao_vision_base_url", None):
            settings.doubao_image_base_url = settings.lab_doubao_vision_base_url

    def _reference_assets(self, request: GenerationRequest) -> list[dict[str, Any]]:
        raw_assets = request.metadata.get("uploaded_assets")
        if not isinstance(raw_assets, list):
            raw_assets = request.generation_plan.metadata.get("uploaded_assets", [])
        raw_project_refs = request.metadata.get("reference_assets")
        if not isinstance(raw_project_refs, list):
            raw_project_refs = request.generation_plan.metadata.get("reference_assets", [])
        combined_assets = [
            *(raw_assets if isinstance(raw_assets, list) else []),
            *(raw_project_refs if isinstance(raw_project_refs, list) else []),
        ]
        assets: list[dict[str, Any]] = []
        seen_evidence: dict[tuple[str, str], int] = {}
        for item in combined_assets:
            data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item or {})
            path = data.get("file_path")
            if not path:
                continue
            try:
                file_path = Path(str(path))
            except TypeError:
                continue
            if not file_path.exists() or not file_path.is_file():
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
                source_type = str(data.get("source_type") or (data.get("metadata") or {}).get("source_type") or "")
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
        return assets[:6]

    def _reference_evidence_role(self, role: str, use_policy: str) -> str:
        value = f"{role} {use_policy}".lower()
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
            if policy_rules:
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
            derivatives = self._reference_truth_derivatives(asset, truth_layers)
            for derivative in derivatives:
                assets.append(
                    {
                        "asset_id": f"{asset['asset_id']}::{derivative['derivative_kind']}",
                        "source_asset_id": asset["asset_id"],
                        "role": self._truth_layer_provider_role(derivative.get("truth_layer"), asset.get("role")),
                        "priority": self._truth_layer_priority(derivative.get("truth_layer"), asset, index),
                        "provider_input_mode": "reference_image",
                        "storage_path": derivative["path"],
                        "filename": derivative.get("path_name") or asset.get("filename"),
                        "mime_type": "image/jpeg",
                        "prompt_constraints": [self._truth_layer_constraint(derivative.get("truth_layer"), asset)],
                        "negative_constraints": closure_negative_rules[:8],
                        "strength": asset.get("strength"),
                        "use_policy": asset.get("use_policy"),
                        "reference_truth_layer": derivative.get("truth_layer"),
                        "truth_layers": truth_layers,
                        "provider_reference_derivative": True,
                        "derivative_kind": derivative.get("derivative_kind"),
                        "fallback_to_original": bool(derivative.get("fallback_to_original")),
                        "identity_color_neutralized": bool(derivative.get("identity_color_neutralized")),
                        "identity_background_neutralized": bool(derivative.get("identity_background_neutralized")),
                        "identity_context_reduced_by_tight_crop": bool(
                            derivative.get("identity_context_reduced_by_tight_crop")
                        ),
                    }
                )
            if self._should_include_original_reference(
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
        truth_package = {
            **truth_package,
            "truth_derivative_ids": [
                item["asset_id"]
                for item in assets
                if item.get("provider_reference_derivative") and item.get("provider_input_mode") == "reference_image"
            ],
            "provider_reference_image_count": len(assets),
        }
        return {
            "asset_mode": "advanced",
            "assets": assets,
            "provider_requirements": {"needs_image_reference": bool(assets), "needs_image_edit": False},
            "provider_input_plan": {
                "operation": "image_edit_with_reference_images" if assets else "generate",
                "reference_image_asset_ids": [item["asset_id"] for item in assets],
                "reference_image_count": len(assets),
                "original_reference_asset_ids": [asset["asset_id"] for asset in reference_assets],
                "suppressed_full_frame_identity_asset_ids": suppressed_original_ids,
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
            },
        }

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
        sources: dict[str, dict[str, Any]] = {}
        source_order: list[str] = []
        truth_source_ids: list[str] = []
        for index, asset in enumerate(reference_assets):
            asset_id = str(asset.get("asset_id") or f"reference_{index + 1}")
            source_order.append(asset_id)
            is_selected = self._is_selected_generated_source(asset)
            is_product = self._is_product_truth_reference(asset, allow_product_language=allow_product_language)
            is_human = self._is_human_truth_reference(
                asset,
                human_photo_context=human_photo_context,
                allow_product_language=allow_product_language,
            )
            layers: list[str] = []
            priority_note = "style_or_context_reference"
            channel_policy = self._reference_channel_policy_for_asset(request, asset)
            if channel_policy:
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
                if is_selected and (has_uploaded_human_truth or has_uploaded_product_truth):
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
            "source_order": source_order,
            "truth_source_ids": truth_source_ids,
            "truth_derivative_ids": [],
            "sources": sources,
            "priority_rules": [
                "uploaded human or product truth remains highest for identity-critical details",
                "selected generated outputs contribute only their resolved channels and never replace uploaded truth or a new explicit prompt",
                "reference truth beats generic archetype wording",
            ],
            "structured_appearance_context": structured_context,
        }

    def _reference_truth_derivatives(self, asset: dict[str, Any], truth_layers: list[str]) -> list[dict[str, Any]]:
        provider_layers = [layer for layer in truth_layers if layer in {"portrait_identity_truth", "product_identity_truth", "structured_appearance_truth"}]
        if not provider_layers:
            return []
        try:
            from app.services.provider_reference import prepare_reference_truth_derivatives

            return prepare_reference_truth_derivatives(
                asset.get("file_path"),
                asset_id=str(asset.get("asset_id") or ""),
                truth_layers=provider_layers,
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
        if layer in {"product_identity_truth", "structured_appearance_truth"}:
            return "subject_reference"
        return _v1_reference_role(str(fallback_role or "unknown_reference"))

    def _truth_layer_priority(self, truth_layer: Any, asset: dict[str, Any], index: int) -> int:
        layer = str(truth_layer or "")
        source_bonus = 40 if self._is_uploaded_truth_source(asset) else 0
        base = {
            "portrait_identity_truth": 260,
            "product_identity_truth": 255,
            "structured_appearance_truth": 250,
        }.get(layer, 180)
        return base + source_bonus - index

    def _original_reference_priority(self, asset: dict[str, Any], truth_layers: list[str], index: int) -> int:
        source_bonus = 30 if self._is_uploaded_truth_source(asset) else 0
        if any(layer in {"portrait_identity_truth", "product_identity_truth", "structured_appearance_truth"} for layer in truth_layers):
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
                    "identity_background_neutralized": bool(item.get("identity_background_neutralized")),
                    "identity_context_reduced_by_tight_crop": bool(
                        item.get("identity_context_reduced_by_tight_crop")
                    ),
                    "filename": item.get("filename"),
                }
            )
        return summaries

    def _generation_prompt(self, request: GenerationRequest, reference_assets: list[dict[str, Any]]) -> str:
        prompt = request.prompt_compilation
        asset = request.asset_spec
        layout = request.layout_plan
        allow_product_language = self._product_language_allowed(request, reference_assets)
        human_guidance = self._human_photorealism_guidance(request)
        human_photo_context = bool(human_guidance) or self._looks_like_human_photo_request(request)
        reference_channel_contract = self._reference_channel_prompt_guidance(request)
        portrait_identity_contract = self._portrait_bone_structure_prompt_guidance(request)
        parts = [
            (
                "Create a camera-real, directly usable creative image asset for a human photo, with publishable craft but no beauty-filter retouch."
                if human_photo_context and not allow_product_language
                else
                "Create a polished, directly usable commercial product image asset."
                if allow_product_language
                else "Create a polished, directly usable creative image asset."
            ),
            f"Visual direction: {prompt.visual_prompt}",
            reference_channel_contract,
            portrait_identity_contract,
            f"Asset purpose: {asset.purpose}" if asset else "",
            f"Platform: {asset.platform.value}; aspect ratio: {asset.aspect_ratio}" if asset else "",
            f"Composition: {layout.product_area.position}" if layout else "",
            f"Visual hierarchy: {', '.join(layout.visual_hierarchy)}" if layout and layout.visual_hierarchy else "",
            "Generate exactly one complete image frame for this output. Do not create a collage, split screen, contact sheet, storyboard, before-after comparison, duplicated frame, or grid of separate images inside the same output.",
            "Reserve clean blank areas for later UI/text overlay outside the generated pixels.",
            (
                "Do not add any new visible text, captions, typography, icons, badges, seals, claim strips, infographic footers, watermarks, signatures, AI-generated marks, or product claims inside the image."
                if allow_product_language
                else "Do not add any new visible text, captions, typography, icons, badges, seals, claim strips, infographic footers, watermarks, signatures, or AI-generated marks inside the image."
            ),
            *(
                [
                    "Only preserve text already visible on the supplied product label if it remains in frame; keep it readable and unobscured, and do not translate, rewrite, enlarge, blur, darken, cover, crop, or invent label copy.",
                    "Preserve supplied product facts, visible product identity, logos, label placement, material cues, proportions, and packaging silhouette.",
                ]
                if allow_product_language
                else [
                    "Preserve the requested subject, scene, style, lighting, composition, and natural proportions.",
                    "Do not add unrelated props, unrelated labels, logos, distracting objects, or objects not requested by the user.",
                ]
            ),
            f"Style notes: {', '.join(prompt.style_notes)}" if prompt.style_notes else "",
            f"Layout notes: {', '.join(prompt.layout_notes)}" if prompt.layout_notes else "",
            f"Hard constraints: {'; '.join(prompt.hard_constraints)}" if prompt.hard_constraints else "",
        ]
        role_guidance = self._mode_role_prompt_guidance(request)
        if role_guidance:
            parts.append("Role-specific generation contract:\n" + "\n".join(role_guidance))
        mode_quality = self._mode_quality_profile(request)
        if mode_quality:
            mode_lines = [
                f"Mode quality: {mode_quality.get('user_visible_label') or mode_quality.get('mode')}",
                "Review priorities: " + "; ".join(self._string_list(mode_quality.get("review_priorities"))[:5]),
                "Pass conditions: " + "; ".join(self._string_list(mode_quality.get("pass_conditions"))[:4]),
                "Mode guidance: " + "; ".join(self._string_list(mode_quality.get("prompt_guidance"))[:4]),
            ]
            parts.append("Mode quality contract:\n" + "\n".join(line for line in mode_lines if not line.endswith(": ")))
        if human_guidance or (human_photo_context and not allow_product_language):
            positive = self._string_list(human_guidance.get("positive_prompt_fragments"))
            do_not_inherit = self._string_list(human_guidance.get("reference_do_not_inherit_rules"))
            lines = []
            lines.append(
                "Polish interpretation: if any earlier line says polished, refined, premium, or beauty, resolve it as camera-ready real-person photography, not skin blur, face slimming, enlarged eyes, V-shaped chin, or idol-card retouch."
            )
            lines.append(
                "Attractive realism balance: keep a healthy clear complexion, fresh bright skin tone from soft natural bounce light, gentle cheek warmth, natural lip color, and awake eyes; preserve natural skin tone and real texture, avoiding skin whitening, dull complexion, muddy color cast, underexposed face, harsh facial shadow, or overly matte documentary plainness."
            )
            lines.append(
                "Identity continuity: preserve the requested person's recognizable face and body identity when identity continuity is part of the task; Human Realism must not expand reference inheritance into hair, wardrobe, lighting, scene, camera, or style."
            )
            lines.append(
                "East Asian portrait aesthetic guard: for East Asian fresh, beauty, or summer portrait requests with no explicit tan, dark, or bronze instruction, keep a clean fair luminous complexion from high-key daylight, soft bounce light, exposure, and color balance; do not darken or tan the skin by default; avoid fake whitening masks or skin smoothing; preserve natural head-to-body, neck, shoulder, and upper-body proportions."
            )
            if positive:
                lines.append("Photoreal human rendering: " + "; ".join(positive[:8]))
            if do_not_inherit and reference_assets:
                lines.append("Reference cleanup: " + "; ".join(do_not_inherit[:4]))
            if lines:
                parts.append("Human realism contract:\n" + "\n".join(lines))
        closure = self._strong_reference_closure_package(request)
        if closure:
            closure_lines = [
                "Reference strength: " + str(closure.get("reference_strength") or "strong"),
                "Provider reference ids: " + ", ".join(self._string_list(closure.get("provider_reference_required_ids"))[:6]),
                "Keep: " + "; ".join(self._string_list(closure.get("identity_keep_rules"))[:5]),
                "Allow variation: " + "; ".join(self._string_list(closure.get("allowed_variations"))[:5]),
                "Do not drift: " + "; ".join(self._string_list(closure.get("forbidden_drift"))[:5]),
                "Provider rules: " + "; ".join(self._string_list(closure.get("provider_prompt_rules"))[:5]),
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
            conflict_rules = self._reference_identity_conflict_rules(request, reference_assets)
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
        if prompt.negative_prompt:
            parts.append(f"Avoid: {prompt.negative_prompt}")
        return self._provider_prompt_for_delivery("\n".join(part for part in parts if str(part or "").strip()))

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
            "Reference truth has priority over generic archetype wording in the text prompt.",
            "Uploaded truth sources remain identity-critical; selected generated references contribute only their Doc93-assigned channels and never override a new explicit prompt.",
        ]
        for asset_id, item in sources.items():
            layers = self._string_list(item.get("truth_layers"))
            if not layers:
                continue
            label = str(item.get("priority_note") or "reference")
            lines.append(f"- {asset_id}: {', '.join(layers)} ({label})")
        if any("portrait_identity_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "For portrait identity truth, preserve exact facial feature relationships, face shape direction, eyebrow/eye/nose/mouth/jaw/chin relationships, natural age impression, body identity direction, and natural skin-tone direction; follow the current prompt for hair, makeup, wardrobe, accessories, camera, crop, scene, light, mood, and style unless an individual channel is explicitly locked."
            )
            lines.append(
                "Same-person identity is stricter than same archetype: do not narrow or sharpen the face, make a V-shaped chin, enlarge eyes, shrink the mouth, reshape lips, or recast the reference into a scenario-specific beauty template."
            )
            lines.append(
                "Forbidden portrait drift: generic AI beauty replacement, beauty-app face, face slimming, enlarged eyes, V-chin distortion, new ethnicity direction, new age band, forced tan/darkened skin, or washing the uploaded person into a merely similar model."
            )
        if any("product_identity_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "For product identity truth, preserve exact product shape, proportions, material, color, packaging silhouette, surface finish, and visible label/logo placement; vary scene, crop, camera angle, and lighting without inventing a new product."
            )
        if any("structured_appearance_truth" in self._string_list(item.get("truth_layers")) for item in sources.values()):
            lines.append(
                "For structured appearance truth, preserve silhouette, layer order, collar/neckline, sleeve/cuff, closure/sash/belt, material behavior, transparency family, pattern/embroidery family, trim placement, and accessory placement while changing pose, camera, crop, scene, and fabric motion."
            )
        return "\n".join(lines)

    def _provider_prompt_for_delivery(self, raw_prompt: str) -> str:
        raw_prompt = str(raw_prompt or "").strip()
        if not raw_prompt:
            return ""
        max_chars = self.max_provider_prompt_chars
        if max_chars is None or max_chars <= 0:
            return raw_prompt
        return self._compact_provider_prompt(raw_prompt, max_chars=max_chars)

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

    def _compact_provider_prompt(self, raw_prompt: str, *, max_chars: int | None = None) -> str:
        lines = self._normalised_unique_prompt_lines(raw_prompt)
        if not lines:
            return ""
        body: list[tuple[int, int, str]] = []
        avoid: list[tuple[int, int, str]] = []
        for index, line in enumerate(lines):
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
        avoid_budget = min(700, max(450, max_chars // 5))
        selected = self._fit_prompt_lines(
            sorted(body, key=lambda item: (item[0], item[1])),
            max_chars=max_chars - avoid_budget,
        )
        remaining = max_chars - len("\n".join(selected)) - (1 if selected else 0)
        selected.extend(
            self._fit_prompt_lines(
                sorted(avoid, key=lambda item: (item[0], item[1])),
                max_chars=max(0, remaining),
            )
        )
        compacted = "\n".join(line for line in selected if line).strip()
        if len(compacted) <= max_chars:
            return compacted
        return compacted[: max_chars - 1].rstrip() + "..."

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
        if "human realism" in lowered or "photoreal human" in lowered or "east asian portrait" in lowered:
            return 1
        if "attractive realism" in lowered or "identity continuity" in lowered or "subject identity" in lowered:
            return 1
        if line.startswith("Generate exactly one") or line.startswith("Do not add any new visible text"):
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
        effective_owners = package.get("effective_channel_owners")
        owner_lines = []
        if isinstance(effective_owners, dict):
            owner_lines = [
                f"{channel}={owner}"
                for channel, owner in effective_owners.items()
                if str(owner or "").startswith("reference:")
            ]
        lines = [
            "Doc93 reference-channel contract: reference images may influence only their assigned channels.",
            *prompt_rules[:10],
            "Effective reference-owned channels: " + "; ".join(owner_lines[:10]) if owner_lines else "",
        ]
        return "Reference channel policy:\n" + "\n".join(line for line in lines if line)

    def _portrait_bone_structure_prompt_guidance(self, request: GenerationRequest) -> str:
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
        identity_truth_rules = (
            self._string_list(balance_policy.get("uploaded_identity_truth_rules")) if isinstance(balance_policy, dict) else []
        )
        approved_anchor_rules = (
            self._string_list(balance_policy.get("approved_visual_anchor_rules")) if isinstance(balance_policy, dict) else []
        )
        ordering_rules = (
            self._string_list(balance_policy.get("prompt_ordering_rules")) if isinstance(balance_policy, dict) else []
        )
        compact_negatives = (
            self._string_list(balance_policy.get("compact_negative_guidance")) if isinstance(balance_policy, dict) else []
        )
        lines = [
            "Doc88 balance contract: keep current prompt mood, uploaded identity truth, and approved visual direction together."
            if balance_policy
            else "",
            *prompt_truth_rules[:3],
            "Reference inheritance boundary: Identity comes from the reference; direction comes from the prompt."
            if reference_rules
            else "",
            *reference_rules[:3],
            *identity_truth_rules[:3],
            *approved_anchor_rules[:3],
            *ordering_rules[:3],
            "Prompt-owned channels: " + "; ".join(prompt_owned[:8]) if prompt_owned else "",
            "Do not inherit from source reference: " + "; ".join(blocked_channels[:8]) if blocked_channels else "",
            "Same person under changed styling; not a similar-looking new model.",
            "Styling may change; preserve the reference face without redesigning the face.",
            *prompt_rules[:3],
            "Bone structure to preserve: " + "; ".join(bone_traits[:6]) if bone_traits else "",
            "Facial-feature relationships to preserve: " + "; ".join(feature_traits[:6]) if feature_traits else "",
            "Allowed surface styling changes: " + "; ".join(allowed[:6]) if allowed else "",
            "Forbidden identity drift: " + "; ".join(_dedupe([*compact_negatives[:4], *forbidden[:5]])) if forbidden else "",
            "Styling scope: " + "; ".join(styling_rules[:3]) if styling_rules else "",
        ]
        return "Portrait identity contract:\n" + "\n".join(line for line in lines if line)

    def _mode_role_prompt_guidance(self, request: GenerationRequest) -> list[str]:
        recipe = self._mode_role_recipe(request)
        if not recipe:
            return []
        policy = self._mode_execution_policy(request)
        lines = [
            f"Mode: {policy.get('mode') or recipe.get('metadata', {}).get('mode') or 'delivery_suite'}",
            f"This image role: {recipe.get('label') or recipe.get('role_key')}",
            f"Purpose: {recipe.get('purpose')}" if recipe.get("purpose") else "",
            f"Required shot: {recipe.get('prompt_pressure')}" if recipe.get("prompt_pressure") else "",
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
        role_plan = self._role_specific_generation_plan(request)
        plan_prompt_additions = self._string_list(role_plan.get("prompt_additions"))
        if plan_prompt_additions:
            lines.append("Suite director rules: " + "; ".join(plan_prompt_additions[:8]))
        plan_metadata = role_plan.get("metadata") if isinstance(role_plan.get("metadata"), dict) else {}
        identity_plan = plan_metadata.get("identity_hero_selection_plan") if isinstance(plan_metadata, dict) else {}
        if isinstance(identity_plan, dict) and identity_plan.get("applies"):
            identity_rules = self._string_list(identity_plan.get("prompt_additions"))
            if identity_rules:
                lines.append("Identity hero selection: " + "; ".join(identity_rules[:4]))
        subject_identity_card = plan_metadata.get("subject_identity_card") if isinstance(plan_metadata, dict) else {}
        portrait_bone_lock = plan_metadata.get("portrait_bone_structure_lock") if isinstance(plan_metadata, dict) else {}
        styling_delta_policy = plan_metadata.get("styling_delta_policy") if isinstance(plan_metadata, dict) else {}
        portrait_reference_policy = (
            plan_metadata.get("portrait_reference_influence_policy") if isinstance(plan_metadata, dict) else {}
        )
        portrait_balance_policy = (
            plan_metadata.get("portrait_reference_balance_policy") if isinstance(plan_metadata, dict) else {}
        )
        if isinstance(portrait_balance_policy, dict) and portrait_balance_policy.get("applies"):
            prompt_truth = self._string_list(portrait_balance_policy.get("current_prompt_truth_rules"))
            approved_anchor = self._string_list(portrait_balance_policy.get("approved_visual_anchor_rules"))
            ordering = self._string_list(portrait_balance_policy.get("prompt_ordering_rules"))
            if prompt_truth:
                lines.append("Doc88 prompt mood protection: " + "; ".join(prompt_truth[:3]))
            if approved_anchor:
                lines.append("Doc88 approved visual anchor: " + "; ".join(approved_anchor[:3]))
            if ordering:
                lines.append("Doc88 prompt order: " + "; ".join(ordering[:3]))
        if isinstance(portrait_reference_policy, dict) and portrait_reference_policy.get("applies"):
            policy_rules = self._string_list(portrait_reference_policy.get("prompt_rules"))
            prompt_owned = self._string_list(portrait_reference_policy.get("prompt_owned_channels"))
            blocked = self._string_list(portrait_reference_policy.get("blocked_reference_channels"))
            lines.append("Reference inheritance boundary: " + "; ".join(policy_rules[:4]))
            if prompt_owned:
                lines.append("Prompt-owned style channels: " + "; ".join(prompt_owned[:8]))
            if blocked:
                lines.append("Do not inherit source reference channels: " + "; ".join(blocked[:8]))
        if isinstance(portrait_bone_lock, dict) and portrait_bone_lock.get("applies"):
            prompt_rules = self._string_list(portrait_bone_lock.get("prompt_rules"))
            bone_traits = self._string_list(portrait_bone_lock.get("stable_bone_traits"))
            feature_traits = self._string_list(portrait_bone_lock.get("stable_feature_relationships"))
            allowed_surface = self._string_list(portrait_bone_lock.get("allowed_surface_changes"))
            forbidden = self._string_list(portrait_bone_lock.get("forbidden_geometry_drift"))
            lines.append("Portrait bone-structure identity lock: " + "; ".join([*prompt_rules[:3], *bone_traits[:3], *feature_traits[:3]]))
            if allowed_surface:
                lines.append("Allowed styling changes: " + "; ".join(allowed_surface[:6]))
            if forbidden:
                lines.append("Forbidden face-geometry drift: " + "; ".join(forbidden[:8]))
        if isinstance(styling_delta_policy, dict) and styling_delta_policy.get("applies"):
            policy_rules = self._string_list(styling_delta_policy.get("prompt_rules"))
            disallowed = self._string_list(styling_delta_policy.get("disallowed_identity_changes"))
            if policy_rules:
                lines.append("Styling delta policy: " + "; ".join(policy_rules[:3]))
            if disallowed:
                lines.append("Styling must not change: " + "; ".join(disallowed[:8]))
        if isinstance(subject_identity_card, dict) and subject_identity_card.get("applies"):
            keep_rules = self._string_list(subject_identity_card.get("identity_keep_rules"))
            feature_rules = self._string_list(subject_identity_card.get("facial_feature_integrity_rules"))
            realism_rules = self._string_list(subject_identity_card.get("beautiful_realism_rules"))
            appearance_rules = self._string_list(subject_identity_card.get("appearance_structure_rules"))
            allowed_variations = self._string_list(subject_identity_card.get("allowed_variations"))
            forbidden_drift = self._string_list(subject_identity_card.get("forbidden_drift"))
            if keep_rules or feature_rules:
                lines.append("Subject identity card: " + "; ".join([*keep_rules[:4], *feature_rules[:4]]))
            if realism_rules:
                lines.append("Beautiful realism balance: " + "; ".join(realism_rules[:4]))
            if appearance_rules:
                lines.append("Structured appearance lock: " + "; ".join(appearance_rules[:4]))
            if allowed_variations:
                lines.append("Allowed identity-safe variation: " + "; ".join(allowed_variations[:6]))
            if forbidden_drift:
                lines.append("Identity drift to avoid: " + "; ".join(forbidden_drift[:8]))
        strict_policy = plan_metadata.get("strict_visual_review_policy") if isinstance(plan_metadata, dict) else {}
        if isinstance(strict_policy, dict) and strict_policy.get("applies"):
            strict_rules = self._string_list(strict_policy.get("prompt_additions"))
            if strict_rules:
                lines.append("Strict visual review rules: " + "; ".join(strict_rules[:8]))
            pass_conditions = self._string_list(strict_policy.get("pass_conditions"))
            if pass_conditions:
                lines.append("Strict visual pass conditions: " + "; ".join(pass_conditions[:5]))
            negative_rules = self._string_list(strict_policy.get("negative_additions"))
            if negative_rules:
                priority_negative_rules = [
                    rule
                    for rule in negative_rules
                    if rule
                    in {
                        "Korean glass skin",
                        "oily shiny face",
                        "nose-tip highlight",
                        "silicone face",
                        "over-smoothed skin",
                        "plastic texture",
                        "same type but different person",
                        "style changed face geometry",
                        "3D render",
                    }
                ]
                lines.append("Strict visual avoid: " + "; ".join(_dedupe([*priority_negative_rules, *negative_rules[:16]])[:24]))
            strict_avoid = self._string_list(strict_policy.get("negative_additions"))
            if strict_avoid:
                lines.append("Strict visual avoid: " + "; ".join(strict_avoid[:16]))
        lines.extend(provider_casebook_prompt_lines(recipe))
        if keep:
            lines.append("Keep: " + "; ".join(keep[:5]))
        if avoid:
            lines.append("Do not: " + "; ".join(avoid[:5]))
        return [line for line in lines if str(line or "").strip()]

    def _negative_constraints(self, request: GenerationRequest) -> list[str]:
        allow_product_language = self._product_language_allowed(request, [])
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
        return list(dict.fromkeys(values))

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

    def _looks_like_human_photo_request(self, request: GenerationRequest) -> bool:
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
        return any(term in text for term in english_terms) or any(term in text for term in chinese_terms)

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
            return max(1, min(4, int(raw)))
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
        except Exception:
            value = 240.0
        return max(30.0, float(value) + 15.0)

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


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result
