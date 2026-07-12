"""Adapter that runs V3-native pre-generation reasoning."""

from __future__ import annotations

import os
from typing import Any

from pydantic import ValidationError

from .context_digest import (
    as_dict,
    clean_text,
    negative_notes_from_context,
    project_context_from_metadata,
    selected_outputs_from_context,
    selected_references_from_context,
)
from .contracts import BrainRunRequest, BrainRunResult
from .fallback import build_fallback_result, build_skipped_result
from .providers import BrainProviderError, BrainProviderUnavailable, V3LLMBrainProvider
from ..shared_capabilities.activation import TemplateCapabilityPolicy, general_capability_policy


GENERAL_SCENARIO_ID = "general_creative"
GENERAL_TEMPLATE_ID = "general_template"


class V3LLMBrainAdapter:
    """Runs a remote brain when configured and deterministic V3 fallback otherwise."""

    def __init__(self, provider: V3LLMBrainProvider | None = None) -> None:
        self.provider = provider or V3LLMBrainProvider()

    def run(self, request: BrainRunRequest) -> BrainRunResult:
        if not _enabled():
            return build_skipped_result(request, "V3 LLM Brain is disabled by configuration.")
        if not self._activation_scope_enabled(request):
            return build_skipped_result(
                request,
                "No trusted capability policy is active; the compatibility scope remains the general template.",
            )

        fallback = build_fallback_result(request)
        if request.reasoning_depth == "off":
            return build_skipped_result(request, "Reasoning depth is off for this request.")
        remote_for_request = _remote_allowed_for_request(request)
        if not self.provider.available(force=remote_for_request):
            fallback.warnings.append("远程创意脑暂不可用，已自动使用本地 V3 规划继续。")
            fallback.audit = {**fallback.audit, "remote_provider_available": False}
            return fallback
        try:
            data = self.provider.run(request)
            result = self._merge_remote_result(fallback, data)
            result.llm_used = True
            result.fallback_used = False
            result.provider = self.provider.provider
            result.model = self.provider.model
            result.audit = {
                **result.audit,
                "source": "v3_remote_brain",
                "remote_reasoning_visible": False,
                "remote_provider_available": True,
            }
            return result
        except (BrainProviderError, BrainProviderUnavailable, ValidationError) as exc:
            fallback.warnings.append(str(exc))
            fallback.audit = {**fallback.audit, "remote_provider_error": str(exc)[:260]}
            return fallback

    def build_request(
        self,
        *,
        user_input: str,
        stage: str,
        scenario_id: str | None,
        template_id: str | None,
        metadata: dict[str, Any],
        shared_capabilities: dict[str, Any] | None = None,
        uploaded_assets: list[dict[str, Any]] | None = None,
        product_profile: dict[str, Any] | None = None,
        capability_catalog: dict[str, Any] | None = None,
        pre_activation_capabilities: dict[str, Any] | None = None,
        template_capability_policy: TemplateCapabilityPolicy | None = None,
    ) -> BrainRunRequest:
        project_context = project_context_from_metadata(metadata)
        selected_outputs = selected_outputs_from_context(project_context)
        reference_assets = selected_references_from_context(project_context)
        requested_count = _bounded_count(
            metadata.get("requested_image_count")
            or as_dict(metadata.get("scenario_parameters")).get("requested_image_count")
            or 2
        )
        variation_mode = (
            clean_text(metadata.get("effective_variation_mode"), 80)
            or clean_text(metadata.get("variation_mode"), 80)
            or clean_text(metadata.get("continuation_mode"), 80)
            or None
        )
        scenario_parameters = as_dict(metadata.get("scenario_parameters"))
        capability_hints = scenario_parameters.get("capabilities")
        if not isinstance(capability_hints, list):
            capability_hints = []
        return BrainRunRequest(
            user_input=user_input,
            stage=stage,
            scenario_id=scenario_id,
            template_id=template_id,
            project_id=clean_text(metadata.get("project_id"), 120) or None,
            project_context=project_context,
            shared_capabilities=dict(shared_capabilities or {}),
            uploaded_assets=list(uploaded_assets or []),
            reference_assets=reference_assets,
            selected_output_assets=selected_outputs,
            product_profile=dict(product_profile or {}),
            requested_image_count=requested_count,
            requested_image_size=clean_text(metadata.get("requested_image_size"), 80) or None,
            reasoning_depth=_reasoning_depth(metadata),
            metadata={
                "project_context_version": project_context.get("context_version"),
                "negative_note_count": len(negative_notes_from_context(project_context)),
                "positive_context_from_selected_outputs_only": True,
                "require_real_images": bool(metadata.get("require_real_images") or metadata.get("real_image_generation")),
                "quality_mode": clean_text(metadata.get("quality_mode"), 40) or None,
                "requested_image_count": requested_count,
                "requested_image_size": clean_text(metadata.get("requested_image_size"), 80) or None,
                "variation_mode": variation_mode,
                "effective_variation_mode": variation_mode,
                "inferred_variation_mode": clean_text(metadata.get("inferred_variation_mode"), 80) or None,
                "variation_mode_source": clean_text(metadata.get("variation_mode_source"), 40) or None,
                "capability_hints": [clean_text(item, 100) for item in capability_hints if clean_text(item, 100)],
                # Only a boolean crosses the Brain boundary.  The approved
                # copy itself stays in the internal runtime envelope and is
                # bound to the frozen plan by Product API before generation.
                "internal_copy_render_plan_present": bool(
                    isinstance(metadata.get("text_pixel_delivery_internal"), dict)
                    and isinstance(metadata.get("text_pixel_delivery_internal", {}).get("copy_render_plan"), dict)
                ),
            },
            capability_catalog=dict(capability_catalog or {}),
            pre_activation_capabilities=dict(pre_activation_capabilities or {}),
            template_capability_policy=template_capability_policy or general_capability_policy(),
        )

    def _activation_scope_enabled(self, request: BrainRunRequest) -> bool:
        if not request.template_capability_policy.brain_activation_enabled:
            return False
        if request.scenario_id == GENERAL_SCENARIO_ID or request.template_id == GENERAL_TEMPLATE_ID:
            return True
        return request.template_capability_policy.policy_id != "general_template_capabilities"

    def _merge_remote_result(self, fallback: BrainRunResult, data: dict[str, Any]) -> BrainRunResult:
        payload = fallback.model_dump(mode="json")
        rejected_sections: list[str] = []
        for key in [
            "intent_summary",
            "project_memory_digest",
            "image_set_plan",
            "prompt_guidance",
            "prompt_review",
            "user_visible_summary",
            "visual_task_profile",
            "capability_activation_intent",
        ]:
            if isinstance(data.get(key), dict):
                candidate = _merge_dict(payload.get(key, {}), data[key])
                payload, accepted = _merge_validated_section(payload, key, candidate)
                if not accepted:
                    rejected_sections.append(key)
        if isinstance(data.get("checkpoints"), list):
            candidate = _merge_checkpoints(payload.get("checkpoints", []), data["checkpoints"])
            payload, accepted = _merge_validated_section(payload, "checkpoints", candidate)
            if not accepted:
                rejected_sections.append("checkpoints")
        if isinstance(data.get("warnings"), list):
            payload["warnings"] = [str(item) for item in data["warnings"] if str(item).strip()]
        if rejected_sections:
            payload["warnings"] = [
                *list(payload.get("warnings") or []),
                "Remote Brain returned incompatible structured fields; V3 kept deterministic safe values for those sections.",
            ]
            payload["audit"] = {
                **dict(payload.get("audit") or {}),
                "remote_contract_partial_fallback": True,
                "remote_contract_rejected_sections": rejected_sections,
            }
        return BrainRunResult.model_validate(payload)


def _enabled() -> bool:
    return os.getenv("V3_LLM_BRAIN_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _remote_allowed_for_request(request: BrainRunRequest) -> bool:
    raw = os.getenv("V3_LLM_BRAIN_REMOTE_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if os.getenv("V3_LLM_BRAIN_API_KEY"):
        return True
    return bool(request.metadata.get("require_real_images") or request.metadata.get("real_image_generation"))


def _reasoning_depth(metadata: dict[str, Any]) -> str:
    raw = str(metadata.get("v3_llm_brain_depth") or metadata.get("reasoning_depth") or "balanced").strip().lower()
    if raw in {"off", "balanced", "studio", "atelier"}:
        return raw
    return "balanced"


def _bounded_count(value: Any) -> int:
    try:
        return max(1, min(4, int(value or 2)))
    except (TypeError, ValueError):
        return 2


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in patch.items():
        if value is not None and value != "" and value != [] and value != {}:
            merged[key] = value
    return merged


def _merge_validated_section(
    payload: dict[str, Any],
    key: str,
    candidate: Any,
) -> tuple[dict[str, Any], bool]:
    """Accept one remote section only when the complete Brain contract remains valid."""

    probe = dict(payload)
    probe[key] = candidate
    try:
        validated = BrainRunResult.model_validate(probe).model_dump(mode="json")
    except ValidationError:
        return payload, False
    payload[key] = validated[key]
    return payload, True


def _merge_checkpoints(base: list[Any], patch: list[Any]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = [dict(item) for item in base if isinstance(item, dict)]
    index = {
        str(item.get("checkpoint_id") or "").strip(): position
        for position, item in enumerate(merged)
        if str(item.get("checkpoint_id") or "").strip()
    }
    for item in patch:
        if not isinstance(item, dict):
            continue
        checkpoint_id = str(item.get("checkpoint_id") or "").strip()
        if checkpoint_id and checkpoint_id in index:
            merged[index[checkpoint_id]] = _merge_dict(merged[index[checkpoint_id]], item)
        else:
            merged.append(dict(item))
    return merged
