"""Adapter that runs V3-native pre-generation reasoning."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import os
import re
import time
from json import JSONDecodeError
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
from .contracts import BrainCanonicalProviderPrompt, BrainRunRequest, BrainRunResult
from .fallback import build_fallback_result, build_remote_required_result, build_skipped_result
from .providers import (
    BrainDevelopmentalAgeDecisionMissing,
    BrainDevelopmentalPresenceDecisionMissing,
    BrainExecutionBudgetExceeded,
    BrainOutputTruncated,
    BrainHumanNaturalnessDecisionMissing,
    BrainProfessionalAnchorViewDecisionMissing,
    BrainProviderError,
    BrainProviderUnavailable,
    BrainReferenceChannelOwnershipDecisionMissing,
    BrainSemanticPreflightMissing,
    V3LLMBrainProvider,
    pop_transport_receipt,
)
from ..shared_capabilities.activation import REFERENCE_CHANNEL_IDS, TemplateCapabilityPolicy, general_capability_policy


GENERAL_SCENARIO_ID = "general_creative"
GENERAL_TEMPLATE_ID = "general_template"


class V3LLMBrainAdapter:
    """Runs a remote brain when configured and deterministic V3 fallback otherwise."""

    def __init__(self, provider: V3LLMBrainProvider | None = None) -> None:
        self.provider = provider or V3LLMBrainProvider()

    @contextmanager
    def execution_scope(self):
        """Scope all remote decisions for one runtime preparation together."""

        scope = getattr(self.provider, "execution_scope", None)
        with scope() if callable(scope) else nullcontext():
            yield

    def execution_budget_receipt(self) -> dict[str, Any] | None:
        """Safe aggregate timing fact for runtime/MCP provenance."""

        receipt = getattr(self.provider, "execution_budget_receipt", None)
        return receipt() if callable(receipt) else None

    def run(self, request: BrainRunRequest) -> BrainRunResult:
        if not _enabled():
            return build_skipped_result(request, "V3 LLM Brain is disabled by configuration.")
        if not self._activation_scope_enabled(request):
            return build_skipped_result(
                request,
                "No trusted capability policy is active; the compatibility scope remains the general template.",
            )

        strict_remote_contract = _requires_complete_remote_image_set(request)
        if request.reasoning_depth == "off":
            if strict_remote_contract:
                return build_remote_required_result(
                    request,
                    "Remote Brain reasoning is required for this real-image request.",
                )
            return build_skipped_result(request, "Reasoning depth is off for this request.")
        fallback = (
            build_remote_required_result(request, "Remote Brain is required for this real-image request.")
            if strict_remote_contract
            else build_fallback_result(request)
        )
        remote_for_request = _remote_allowed_for_request(request)
        if not self.provider.available(force=remote_for_request):
            fallback.warnings.append(
                "远程 Brain 暂不可用；真实图片任务已阻断，不使用本地创意 fallback。"
                if strict_remote_contract
                else "远程创意脑暂不可用，已自动使用本地 V3 规划继续。"
            )
            fallback.audit = {**fallback.audit, "remote_provider_available": False}
            return fallback
        started = time.perf_counter()
        semantic_recovery_attempted = False
        initial_rejected_sections: list[str] = []
        try:
            data = self.provider.run(request)
            transport_receipt = pop_transport_receipt(data) if isinstance(data, dict) else {}
            transport_receipt = _with_elapsed_transport_receipt(
                transport_receipt,
                stage=request.stage,
                elapsed_ms=_elapsed_ms(started),
            )
            result = self._merge_remote_result(
                fallback,
                data,
                requires_complete_image_set=strict_remote_contract,
            )
            initial_rejected_sections = _remote_contract_rejected_sections(result)
            recovery_transport_receipt: dict[str, Any] = {}
            if strict_remote_contract and initial_rejected_sections:
                # A valid transport JSON object can still violate the frozen
                # semantic schema. Give the same remote Brain one bounded
                # opportunity to re-answer the same immutable request. This
                # is not local JSON repair and it happens before any image
                # Provider operation.
                semantic_recovery_attempted = True
                recovery_request = _semantic_contract_recovery_request(
                    request,
                    rejected_sections=initial_rejected_sections,
                )
                recovery_started = time.perf_counter()
                recovery_data = self.provider.run(recovery_request)
                recovery_transport_receipt = (
                    pop_transport_receipt(recovery_data) if isinstance(recovery_data, dict) else {}
                )
                recovery_transport_receipt = _with_elapsed_transport_receipt(
                    recovery_transport_receipt,
                    stage=request.stage,
                    elapsed_ms=_elapsed_ms(recovery_started),
                )
                result = self._merge_remote_result(
                    fallback,
                    recovery_data,
                    requires_complete_image_set=True,
                )
            result.llm_used = True
            result.fallback_used = False
            result.provider = self.provider.provider
            result.model = self.provider.model
            final_rejected_sections = _remote_contract_rejected_sections(result)
            result.audit = {
                **result.audit,
                "source": "v3_remote_brain",
                "remote_reasoning_visible": False,
                "remote_provider_available": True,
                **({"remote_brain_transport": transport_receipt} if transport_receipt else {}),
                "remote_semantic_contract_recovery_attempted": semantic_recovery_attempted,
                "remote_semantic_contract_recovery_succeeded": bool(
                    semantic_recovery_attempted and not final_rejected_sections
                ),
                **(
                    {
                        "remote_semantic_contract_recovery_initial_rejected_sections": initial_rejected_sections,
                        "remote_semantic_contract_recovery_final_rejected_sections": final_rejected_sections,
                        "remote_semantic_contract_recovery_call_count": 1,
                    }
                    if semantic_recovery_attempted
                    else {}
                ),
                **(
                    {"remote_semantic_contract_recovery_transport": recovery_transport_receipt}
                    if recovery_transport_receipt
                    else {}
                ),
            }
            return result
        except (BrainProviderError, BrainProviderUnavailable, ValidationError) as exc:
            fallback.warnings.append(str(exc))
            remote_http_status_code = _remote_provider_http_status_code(exc)
            fallback.audit = {
                **fallback.audit,
                "remote_provider_error": str(exc)[:260],
                "remote_provider_error_class": _remote_provider_error_class(exc),
                **(
                    {"remote_provider_http_status_code": remote_http_status_code}
                    if remote_http_status_code is not None
                    else {}
                ),
                "remote_brain_elapsed_ms": _elapsed_ms(started),
                "remote_brain_stage": request.stage,
                **(
                    {"remote_brain_execution_budget": self.execution_budget_receipt()}
                    if self.execution_budget_receipt() is not None
                    else {}
                ),
                "remote_semantic_contract_recovery_attempted": semantic_recovery_attempted,
                "remote_semantic_contract_recovery_succeeded": False,
                **(
                    {
                        "remote_semantic_contract_recovery_initial_rejected_sections": initial_rejected_sections,
                        "remote_semantic_contract_recovery_final_rejected_sections": initial_rejected_sections,
                        "remote_semantic_contract_recovery_call_count": 1,
                    }
                    if semantic_recovery_attempted
                    else {}
                ),
            }
            return fallback

    def finalize_canonical_provider_prompts(
        self,
        request: BrainRunRequest,
    ) -> tuple[list[BrainCanonicalProviderPrompt], dict[str, Any]]:
        """Ask the remote Brain to sign final renderer text after validation.

        This intentionally bypasses the ordinary fallback-result merger.  A
        local fallback would be an unauthorized provider-prompt author, so an
        unavailable or malformed finalizer is a failure for the caller to
        block rather than a cue to reconstruct wording locally.
        """

        if not _enabled():
            raise BrainProviderUnavailable("V3 LLM Brain is disabled by configuration.")
        if not self._activation_scope_enabled(request):
            raise BrainProviderUnavailable("No trusted capability policy is active for canonical prompt signing.")
        if not self.provider.available(force=True):
            raise BrainProviderUnavailable("Remote Brain is unavailable for canonical prompt signing.")
        started = time.perf_counter()
        try:
            data = self.provider.run(request)
        except (BrainProviderError, BrainProviderUnavailable):
            raise
        except Exception as exc:  # pragma: no cover - defensive provider boundary
            raise BrainProviderError("Remote Brain failed while signing the canonical provider prompt.") from exc
        transport_receipt = pop_transport_receipt(data) if isinstance(data, dict) else {}
        transport_receipt = _with_elapsed_transport_receipt(
            transport_receipt,
            stage=request.stage,
            elapsed_ms=_elapsed_ms(started),
        )
        prompts_raw = data.get("canonical_provider_prompts") if isinstance(data, dict) else None
        expected_count = request.requested_image_count
        if not _matches_canonical_provider_prompt_cardinality(prompts_raw, expected_count=expected_count):
            raise BrainProviderError("Remote Brain returned an invalid canonical provider-prompt contract.")
        semantic_preflight_required = _requires_human_semantic_preflight(request)
        if semantic_preflight_required and not _matches_human_semantic_preflight_receipts(
            prompts_raw,
            expected_count=expected_count,
        ):
            raise BrainSemanticPreflightMissing(
                "Remote Brain did not explicitly approve the required Human Realism semantic preflight."
            )
        naturalness_decision_required = _requires_human_naturalness_decision(request)
        if naturalness_decision_required and not _matches_human_naturalness_decision_receipts(
            prompts_raw,
            expected_count=expected_count,
        ):
            raise BrainHumanNaturalnessDecisionMissing(
                "Remote Brain did not return the required Human Realism naturalness decision receipt."
            )
        reference_ownership_decision_required = _requires_reference_channel_ownership_decision(request)
        if reference_ownership_decision_required and not _matches_reference_channel_ownership_receipts(
            prompts_raw,
            expected_count=expected_count,
        ):
            raise BrainReferenceChannelOwnershipDecisionMissing(
                "Remote Brain did not return the required reference-channel ownership decision receipt."
            )
        developmental_age_requirement = _required_human_developmental_age_requirement(request)
        if developmental_age_requirement and not _matches_human_developmental_age_receipts(
            prompts_raw,
            expected_count=expected_count,
            expected_requirement=developmental_age_requirement,
        ):
            raise BrainDevelopmentalAgeDecisionMissing(
                "Remote Brain did not return the required developmental-age ownership receipt."
            )
        developmental_presence_requirement = _required_human_developmental_presence_requirement(request)
        if developmental_presence_requirement and not _matches_human_developmental_presence_receipts(
            prompts_raw,
            expected_count=expected_count,
            expected_requirement=developmental_presence_requirement,
        ):
            raise BrainDevelopmentalPresenceDecisionMissing(
                "Remote Brain did not return the required developmental-presence receipt."
            )
        professional_anchor_view_requirement = _required_professional_anchor_view_requirement(request)
        if professional_anchor_view_requirement and not _matches_professional_anchor_view_receipts(
            prompts_raw,
            expected_count=expected_count,
            expected_requirement=professional_anchor_view_requirement,
        ):
            raise BrainProfessionalAnchorViewDecisionMissing(
                "Remote Brain did not return the required frozen Professional anchor-view receipt."
            )
        try:
            prompts = [BrainCanonicalProviderPrompt.model_validate(item) for item in prompts_raw]
        except ValidationError as exc:
            raise BrainProviderError("Remote Brain returned an invalid canonical provider-prompt contract.") from exc
        return (
            prompts,
            {
                "remote_canonical_provider_prompts_received": True,
                "canonical_provider_prompt_provider": self.provider.provider,
                "canonical_provider_prompt_model": self.provider.model,
                **({"remote_brain_transport": transport_receipt} if transport_receipt else {}),
                "human_realism_semantic_preflight_required": semantic_preflight_required,
                "human_realism_semantic_preflight_signed": semantic_preflight_required,
                "human_realism_natural_presence_decision_required": naturalness_decision_required,
                "human_realism_natural_presence_decision_signed": naturalness_decision_required,
                "human_realism_natural_presence_decisions": (
                    [
                        prompt.human_naturalness_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.human_naturalness_decision is not None
                    ]
                    if naturalness_decision_required
                    else []
                ),
                "reference_channel_ownership_decision_required": reference_ownership_decision_required,
                "reference_channel_ownership_decision_signed": reference_ownership_decision_required,
                "reference_channel_ownership_decisions": (
                    [
                        prompt.reference_channel_ownership_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.reference_channel_ownership_decision is not None
                    ]
                    if reference_ownership_decision_required
                    else []
                ),
                "human_developmental_age_decision_required": bool(developmental_age_requirement),
                "human_developmental_age_decision_signed": bool(developmental_age_requirement),
                "human_developmental_age_decisions": (
                    [
                        prompt.human_developmental_age_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.human_developmental_age_decision is not None
                    ]
                    if developmental_age_requirement
                    else []
                ),
                "human_developmental_presence_decision_required": bool(
                    developmental_presence_requirement
                ),
                "human_developmental_presence_decision_signed": bool(
                    developmental_presence_requirement
                ),
                "human_developmental_presence_decisions": (
                    [
                        prompt.human_developmental_presence_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.human_developmental_presence_decision is not None
                    ]
                    if developmental_presence_requirement
                    else []
                ),
                "professional_anchor_view_decision_required": bool(professional_anchor_view_requirement),
                "professional_anchor_view_decision_signed": bool(professional_anchor_view_requirement),
                "professional_anchor_view_decisions": (
                    [
                        prompt.professional_anchor_view_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.professional_anchor_view_decision is not None
                    ]
                    if professional_anchor_view_requirement
                    else []
                ),
            },
        )
    def build_request(
        self,
        *,
        user_input: str,
        job_id: str | None = None,
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
        provider_native_text_requirements = _provider_native_text_requirements(metadata, scenario_parameters)
        ecommerce_creative_context = _ecommerce_creative_context(metadata, scenario_id)
        photography_creative_context = _photography_creative_context(metadata, scenario_id)
        approved_literal_copy = ecommerce_creative_context.get("approved_literal_copy")
        if isinstance(approved_literal_copy, str) and approved_literal_copy.strip():
            provider_native_text_requirements = list(
                dict.fromkeys([*provider_native_text_requirements, approved_literal_copy.strip()])
            )[:8]
        capability_hints = scenario_parameters.get("capabilities")
        if not isinstance(capability_hints, list):
            capability_hints = []
        specialized_plan = metadata.get("specialized_scenario_plan")
        specialized_plan_present = isinstance(specialized_plan, dict) and bool(specialized_plan.get("planning_id"))
        visual_asset_library_binding = _visual_asset_library_binding(metadata)
        request_metadata = {
            "project_context_version": project_context.get("context_version"),
            "negative_note_count": len(negative_notes_from_context(project_context)),
            "positive_context_from_selected_outputs_only": True,
            "require_real_images": bool(
                metadata.get("require_real_images")
                or metadata.get("real_image_generation")
                or visual_asset_library_binding
            ),
            "quality_mode": clean_text(metadata.get("quality_mode"), 40) or None,
            "requested_image_count": requested_count,
            "requested_image_size": clean_text(metadata.get("requested_image_size"), 80) or None,
            "variation_mode": variation_mode,
            "effective_variation_mode": variation_mode,
            "inferred_variation_mode": clean_text(metadata.get("inferred_variation_mode"), 80) or None,
            "variation_mode_source": clean_text(metadata.get("variation_mode_source"), 40) or None,
            "capability_hints": [clean_text(item, 100) for item in capability_hints if clean_text(item, 100)],
            "provider_native_text_requirements": provider_native_text_requirements,
            "specialized_scenario_plan_present": specialized_plan_present,
        }
        if ecommerce_creative_context:
            # Deliberately absent from General and Photography requests.
            request_metadata["ecommerce_creative_context"] = ecommerce_creative_context
        if photography_creative_context:
            # Deliberately absent from General and E-Commerce requests.  This
            # is a non-creative contract: it lets the remote Brain bind one
            # original direction to each frozen Photography role without
            # inheriting a local shot/camera/lighting recipe.
            request_metadata["photography_creative_context"] = photography_creative_context
        if visual_asset_library_binding:
            # This is an immutable authority receipt, not a local prompt
            # fragment. Keep it deliberately small so library source paths,
            # candidate records and planning metadata cannot cross the Brain
            # boundary.
            request_metadata["visual_asset_library_binding"] = visual_asset_library_binding
        return BrainRunRequest(
            user_input=user_input,
            job_id=job_id,
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
            metadata=request_metadata,
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

    def _merge_remote_result(
        self,
        fallback: BrainRunResult,
        data: dict[str, Any],
        *,
        requires_complete_image_set: bool = False,
    ) -> BrainRunResult:
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
            remote_section = data.get(key)
            if key == "image_set_plan" and requires_complete_image_set:
                # Validate the raw remote section before merging it with the
                # contract-shaped fallback.  Otherwise an empty remote list
                # would be ignored by _merge_dict and the fallback directions
                # could be mistaken for a real E-Commerce decision.
                if not isinstance(remote_section, dict) or not _matches_image_set_cardinality(
                    remote_section,
                    expected_count=fallback.image_set_plan.image_count,
                ):
                    rejected_sections.append(key)
                    continue
            if key == "visual_task_profile" and requires_complete_image_set:
                # A real image may not inherit a locally guessed semantic
                # profile merely because a remote response supplied the small
                # rendering-intent sub-object. The remote Brain owns semantic
                # subject/evidence judgement; the fallback profile only binds
                # non-creative job identifiers and compatibility defaults.
                if not _has_complete_remote_visual_task_profile(remote_section):
                    rejected_sections.append(key)
                    continue
            if key == "capability_activation_intent" and requires_complete_image_set:
                if not _has_complete_remote_capability_activation_intent(remote_section):
                    rejected_sections.append(key)
                    continue
            if isinstance(remote_section, dict):
                candidate = (
                    _merge_complete_remote_visual_task_profile(payload.get(key, {}), remote_section)
                    if key == "visual_task_profile" and requires_complete_image_set
                    else _merge_complete_remote_capability_activation_intent(payload.get(key, {}), remote_section)
                    if key == "capability_activation_intent" and requires_complete_image_set
                    else _merge_dict(payload.get(key, {}), remote_section)
                )
                # A remote plan may be valid JSON while still violating the
                # concrete output contract (for example, declaring one image
                # but returning three directions).  Do not truncate it at a
                # later delivery stage: keep the already-counted fallback
                # plan for this section and make the partial fallback
                # auditable.  Templates that require a remote creative Brain
                # reject this marker in ScenarioRuntime rather than turning a
                # malformed remote set into local E-Commerce directions.
                if key == "image_set_plan" and not _matches_image_set_cardinality(
                    candidate,
                    expected_count=fallback.image_set_plan.image_count,
                ):
                    rejected_sections.append(key)
                    continue
                payload, accepted = _merge_validated_section(payload, key, candidate)
                if not accepted:
                    rejected_sections.append(key)
        # Rendering medium and its scope are semantic decisions. A local
        # keyword hit (for example a cartoon print on a real garment) may
        # never override them on an LLM-first path. Keep an early remote
        # semantic decision auditable too, so a later real-image materialize
        # can safely reuse a draft plan only when it already carries this
        # explicit decision.
        if _has_remote_rendering_intent(data.get("visual_task_profile")):
            payload["audit"] = {
                **dict(payload.get("audit") or {}),
                "remote_rendering_intent_received": True,
            }
        if _has_complete_remote_visual_task_profile(data.get("visual_task_profile")):
            payload["audit"] = {
                **dict(payload.get("audit") or {}),
                "remote_visual_task_profile_received": True,
            }
        elif requires_complete_image_set and "visual_task_profile" not in rejected_sections:
            rejected_sections.append("visual_task_profile.rendering_intent")
        if _has_complete_remote_capability_activation_intent(data.get("capability_activation_intent")):
            payload["audit"] = {
                **dict(payload.get("audit") or {}),
                "remote_capability_activation_intent_received": True,
            }
        elif requires_complete_image_set and "capability_activation_intent" not in rejected_sections:
            rejected_sections.append("capability_activation_intent")
        # A normal planning response may include an early draft of renderer
        # wording for human inspection, but only the later finalizer response
        # is allowed to become a Provider instruction.
        remote_prompts = data.get("canonical_provider_prompts")
        if remote_prompts is not None:
            if _matches_canonical_provider_prompt_cardinality(
                remote_prompts,
                expected_count=fallback.image_set_plan.image_count,
            ):
                payload, accepted = _merge_validated_section(
                    payload,
                    "canonical_provider_prompts",
                    remote_prompts,
                )
                if not accepted:
                    rejected_sections.append("canonical_provider_prompts")
            else:
                rejected_sections.append("canonical_provider_prompts")
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
                (
                    "Remote Brain returned incompatible structured fields; strict real-image execution kept only "
                    "non-creative contract identities and remains blocked."
                    if requires_complete_image_set
                    else "Remote Brain returned incompatible structured fields; V3 kept deterministic safe values for those sections."
                ),
            ]
            payload["audit"] = {
                **dict(payload.get("audit") or {}),
                "remote_contract_partial_fallback": True,
                "remote_contract_rejected_sections": rejected_sections,
            }
        return BrainRunResult.model_validate(payload)


def _provider_native_text_requirements(metadata: dict[str, Any], scenario_parameters: dict[str, Any]) -> list[str]:
    """Flatten approved literal copy without leaking template geometry or roles."""

    raw = (
        metadata.get("provider_native_text_requirements")
        or scenario_parameters.get("provider_native_text")
        or scenario_parameters.get("approved_copy")
    )
    if isinstance(raw, dict):
        values = list(raw.values())
    elif isinstance(raw, list):
        values = raw
    else:
        values = [raw]
    return list(dict.fromkeys(str(value).strip() for value in values if str(value or "").strip()))[:8]


def _remote_contract_rejected_sections(result: BrainRunResult) -> list[str]:
    raw = result.audit.get("remote_contract_rejected_sections") if isinstance(result.audit, dict) else None
    if not isinstance(raw, list):
        return []
    return list(dict.fromkeys(str(item).strip() for item in raw if str(item).strip()))


def _semantic_contract_recovery_request(
    request: BrainRunRequest,
    *,
    rejected_sections: list[str],
) -> BrainRunRequest:
    """Add a server-owned schema marker without changing frozen task facts."""

    metadata = dict(request.metadata)
    metadata["remote_semantic_contract_recovery"] = {
        "contract_version": "v3_remote_semantic_contract_recovery_v1",
        "attempt": 1,
        "rejected_sections": list(rejected_sections),
        "same_frozen_request": True,
    }
    return request.model_copy(update={"metadata": metadata}, deep=True)


def _visual_asset_library_binding(metadata: dict[str, Any]) -> dict[str, Any]:
    """Return the small, immutable library-authority receipt for Brain input."""

    raw = metadata.get("visual_asset_library_binding")
    if not isinstance(raw, dict):
        return {}
    claims = raw.get("claims")
    if not isinstance(claims, list) or not claims:
        return {}
    safe_claims: list[dict[str, Any]] = []
    for item in claims:
        if not isinstance(item, dict):
            return {}
        claim = {
            key: item.get(key)
            for key in (
                "project_id",
                "asset_type",
                "asset_id",
                "asset_version_id",
                "owned_channels",
                "evidence_ids",
            )
        }
        if not all(str(claim.get(key) or "").strip() for key in ("project_id", "asset_type", "asset_id", "asset_version_id")):
            return {}
        if not isinstance(claim["owned_channels"], list) or not isinstance(claim["evidence_ids"], list):
            return {}
        safe_claims.append(claim)
    return {
        key: raw.get(key)
        for key in ("contract_version", "project_id", "job_id", "binding_set_id")
    } | {"claims": safe_claims}


def _ecommerce_creative_context(metadata: dict[str, Any], scenario_id: str | None) -> dict[str, Any]:
    """Pass only the server-shaped factual context to the E-Commerce Brain."""

    if str(scenario_id or "").strip().lower() != "ecommerce":
        return {}
    raw = metadata.get("ecommerce_creative_context")
    if not isinstance(raw, dict):
        return {}
    allowed = {
        "context_id",
        "source_version",
        "product_truth",
        "apparel_on_model_evidence_profile",
        "platform_constraints",
        "category_evidence_questions",
        "seller_inputs",
        "approved_literal_copy",
        "copy_locale",
        "claim_risk_warnings",
        "warnings",
        "metadata",
    }
    return {key: raw[key] for key in allowed if key in raw}


def _photography_creative_context(metadata: dict[str, Any], scenario_id: str | None) -> dict[str, Any]:
    """Expose only Photography's frozen, non-creative contract to the Brain."""

    if str(scenario_id or "").strip().lower() != "photography":
        return {}
    specialized = metadata.get("specialized_scenario_plan")
    if not isinstance(specialized, dict):
        return {}
    execution = specialized.get("execution_plan")
    if not isinstance(execution, dict):
        return {}
    recipes = execution.get("role_recipes")
    if not isinstance(recipes, list):
        return {}
    role_ids = [
        str(item.get("role_key") or "").strip()
        for item in recipes
        if isinstance(item, dict) and str(item.get("role_key") or "").strip()
    ]
    if not role_ids:
        return {}

    binding = metadata.get("photographer_profile_binding")
    binding = binding if isinstance(binding, dict) else {}
    parameters = as_dict(metadata.get("scenario_parameters"))
    explicit_controls = {
        key: parameters[key]
        for key in (
            "input_mode",
            "delivery_mode",
            "scene_domain",
            "reshoot_strength",
            "preservation_controls",
            "aspect_ratio",
        )
        if parameters.get(key) not in (None, "", [], {})
    }
    facts = specialized.get("capability_contribution_draft")
    facts = facts.get("facts") if isinstance(facts, dict) and isinstance(facts.get("facts"), dict) else {}
    reference_policy = facts.get("reference_policy") if isinstance(facts, dict) else {}
    reference_policy = dict(reference_policy) if isinstance(reference_policy, dict) else {}
    return {
        "contract_version": "photography_llm_first_v1",
        "template_id": "photographer_template",
        "scenario_id": "photography",
        "role_ids": role_ids,
        "role_count": len(role_ids),
        "pinned_profile_checksum": clean_text(binding.get("technique_package_checksum"), 180) or None,
        "reference_channel_ownership": reference_policy,
        "explicit_controls": explicit_controls,
        "forbidden_cross_template_roles": [
            "general_suite_direction",
            "general_cover_hero",
            "ecommerce_deliverable_role",
        ],
        "creative_direction_requirement": (
            "Return exactly one original natural-language whole-image direction per role ID. "
            "The role IDs are structural bindings only; do not reuse local camera, crop, pose, lighting, "
            "scene, overlay, or slot recipes."
        ),
    }


def _enabled() -> bool:
    return os.getenv("V3_LLM_BRAIN_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _remote_allowed_for_request(request: BrainRunRequest) -> bool:
    raw = os.getenv("V3_LLM_BRAIN_REMOTE_ENABLED")
    if raw is not None:
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if os.getenv("V3_LLM_BRAIN_API_KEY"):
        return True
    return bool(request.metadata.get("require_real_images") or request.metadata.get("real_image_generation"))


def _requires_complete_remote_image_set(request: BrainRunRequest) -> bool:
    """Require a complete creative answer whenever a real image is requested.

    This mirrors the compact remote-payload boundary.  It deliberately does
    not alter ordinary General draft planning, where the compatibility
    fallback remains valid, but it prevents a partial remote response from
    being combined with a local image direction for a real Provider job.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    return bool(
        request.template_capability_policy.requires_remote_creative_brain
        or metadata.get("require_real_images")
        or metadata.get("real_image_generation")
    )


def _elapsed_ms(started: float) -> int:
    return max(0, int(round((time.perf_counter() - started) * 1000)))


def _with_elapsed_transport_receipt(
    receipt: dict[str, Any],
    *,
    stage: str,
    elapsed_ms: int,
) -> dict[str, Any]:
    """Add safe phase timing without exposing request bodies or provider data."""

    return {
        **dict(receipt or {}),
        "stage": str(stage),
        "elapsed_ms": max(0, int(elapsed_ms)),
    }


def _remote_provider_error_class(exc: Exception) -> str:
    """Normalize a remote Brain failure for public-safe job provenance."""

    chain = _exception_chain(exc)
    if any(isinstance(item, BrainExecutionBudgetExceeded) for item in chain):
        return "execution_budget_exhausted"
    if any(isinstance(item, BrainOutputTruncated) for item in chain):
        return "truncated_response"
    if any(isinstance(item, JSONDecodeError) for item in chain):
        return "invalid_response"
    text = " ".join(str(item or "") for item in chain).lower()
    if "content_policy" in text or "content policy" in text:
        return "content_policy"
    if any(token in text for token in ("timed out", "timeout", "readtimeout", "connecttimeout")):
        return "timeout"
    if any(token in text for token in ("context canceled", "cancelled", "canceled")):
        return "canceled"
    if any(token in text for token in ("non-json", "empty output", "json")):
        return "invalid_response"
    if _remote_provider_http_status_code(exc) is not None or any(
        token in text for token in ("status code", "error code", "http")
    ):
        return "upstream_http_error"
    return "provider_error"


def _remote_provider_http_status_code(exc: Exception) -> int | None:
    """Extract only an HTTP status code; never persist the raw provider error."""

    for item in _exception_chain(exc):
        match = re.search(r"(?:status|error)\s+code\s*[:=]?\s*(\d{3})", str(item or ""), flags=re.IGNORECASE)
        if not match:
            continue
        code = int(match.group(1))
        if 100 <= code <= 599:
            return code
    return None


def _exception_chain(exc: BaseException) -> list[BaseException]:
    """Return a finite exception chain without persisting its raw details."""

    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen and len(chain) < 8:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or current.__context__
    return chain


def _reasoning_depth(metadata: dict[str, Any]) -> str:
    raw = str(metadata.get("v3_llm_brain_depth") or metadata.get("reasoning_depth") or "balanced").strip().lower()
    if raw in {"off", "balanced", "studio", "atelier"}:
        return raw
    return "balanced"


def _bounded_count(value: Any) -> int:
    try:
        return max(1, int(value or 2))
    except (TypeError, ValueError):
        return 2


def _merge_dict(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base or {})
    for key, value in patch.items():
        if value is not None and value != "" and value != [] and value != {}:
            merged[key] = value
    return merged


def _matches_image_set_cardinality(candidate: dict[str, Any], *, expected_count: int) -> bool:
    """Require a remote image-set plan to be internally and request consistent.

    The Pydantic shape accepts arbitrary list lengths, because it is also used
    to read historical records.  New runtime plans must be stricter: one
    requested output means exactly one natural-language direction.  This is a
    validation boundary, never a request to slice or pad a remote plan.
    """

    try:
        image_count = int(candidate.get("image_count"))
    except (TypeError, ValueError):
        return False
    directions = [str(item).strip() for item in candidate.get("shot_plan", []) if str(item).strip()]
    return image_count == expected_count and len(directions) == expected_count


def _matches_canonical_provider_prompt_cardinality(candidate: Any, *, expected_count: int) -> bool:
    """Require exactly one approved, Brain-authored prompt per output."""

    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    indexes: list[int] = []
    for item in candidate:
        if not isinstance(item, dict):
            return False
        try:
            index = int(item.get("output_index"))
        except (TypeError, ValueError):
            return False
        prompt = " ".join(str(item.get("prompt") or "").split())
        if index < 1 or len(prompt) < 24 or str(item.get("review_status") or "approved") != "approved":
            return False
        indexes.append(index)
    return indexes == list(range(1, expected_count + 1))


def _requires_human_semantic_preflight(request: BrainRunRequest) -> bool:
    """Read the frozen finalizer requirement without interpreting prompt text.

    The typed Human Realism capability contract remains the source of truth.
    This tiny helper only decides whether the remote finalizer must explicitly
    acknowledge its whole-image semantic check; it never creates a prompt
    rule or infers a demographic from user language.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    requirement = context.get("final_prompt_semantic_preflight")
    return (
        isinstance(requirement, dict)
        and bool(requirement.get("required"))
        and str(requirement.get("owner") or "") == "remote_v3_llm_brain"
        and str(requirement.get("scope") or "") == "whole_image_human_photographic_plausibility"
        and str(requirement.get("revision_mode") or "") == "rewrite_complete_canonical_prompt"
    )


def _matches_human_semantic_preflight_receipts(candidate: Any, *, expected_count: int) -> bool:
    """Require an explicit remote receipt for each new Human Realism output."""

    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and item.get("semantic_preflight_status") == "approved"
        for index, item in enumerate(candidate, start=1)
    )


def _requires_human_naturalness_decision(request: BrainRunRequest) -> bool:
    """Require a schema receipt for the Brain-owned Human Realism sign-off.

    The forward path combines canonical prompt authoring and naturalness
    signing in one finalizer request. The old dedicated re-sign stage remains
    readable for historical requests, but new requests declare the same typed
    receipt in their frozen context. This checks only that contract boundary;
    it does not inspect creative language or classify people from prompt
    keywords.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("human_naturalness_decision")
    return bool(
        _requires_human_semantic_preflight(request)
        and (
            request.stage in {
                "provider_prompt_human_naturalness_resign",
                "provider_prompt_developmental_presence_verify",
                "provider_prompt_professional_capture_resign",
            }
            or (
                isinstance(decision, dict)
                and decision.get("required") is True
                and decision.get("contract_version") == "v3_human_naturalness_decision_v1"
                and decision.get("owner") == "remote_v3_llm_brain"
                and isinstance(decision.get("frozen_binding"), dict)
            )
        )
    )


def _matches_human_naturalness_decision_receipts(candidate: Any, *, expected_count: int) -> bool:
    """Validate the public-safe Doc142 receipt before Pydantic projection."""

    expected_keys = {"contract_version", "status", "owner"}
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("human_naturalness_decision"), dict)
        and set(item["human_naturalness_decision"]) == expected_keys
        and item["human_naturalness_decision"].get("contract_version") == "v3_human_naturalness_decision_v1"
        and item["human_naturalness_decision"].get("status") in {"approved", "rewritten"}
        and item["human_naturalness_decision"].get("owner") == "remote_v3_llm_brain"
        for index, item in enumerate(candidate, start=1)
    )


def _requires_reference_channel_ownership_decision(request: BrainRunRequest) -> bool:
    """Require Brain reconciliation only for an applicable frozen Doc93 package."""

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("reference_channel_ownership_decision")
    return bool(
        isinstance(decision, dict)
        and decision.get("required") is True
        and decision.get("contract_version") == "v3_reference_channel_ownership_decision_v1"
        and decision.get("owner") == "remote_v3_llm_brain"
        and isinstance(decision.get("frozen_binding"), dict)
        and isinstance(decision.get("reference_owned_channels"), list)
        and isinstance(decision.get("current_request_owned_channels"), list)
    )


def _matches_reference_channel_ownership_receipts(candidate: Any, *, expected_count: int) -> bool:
    """Validate only the schema receipt; creative interpretation remains remote."""

    expected_keys = {"contract_version", "status", "owner"}
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("reference_channel_ownership_decision"), dict)
        and set(item["reference_channel_ownership_decision"]) == expected_keys
        and item["reference_channel_ownership_decision"].get("contract_version")
        == "v3_reference_channel_ownership_decision_v1"
        and item["reference_channel_ownership_decision"].get("status") in {"approved", "rewritten"}
        and item["reference_channel_ownership_decision"].get("owner") == "remote_v3_llm_brain"
        for index, item in enumerate(candidate, start=1)
    )


def _required_human_developmental_age_requirement(request: BrainRunRequest) -> dict[str, str]:
    """Return the exact frozen age-ownership decision, if applicable."""

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("human_developmental_age_decision")
    if not isinstance(decision, dict):
        return {}
    expected = {
        "contract_version": "v3_human_developmental_age_decision_v2",
        "age_fidelity": "follow_explicit_prompt",
        "source_age_inheritance": "not_automatic_when_current_prompt_assigns_age",
        "developmental_age_coherence": "whole_person_requested_stage",
        "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
        "owner": "remote_v3_llm_brain",
    }
    if not (
        decision.get("required") is True
        and all(decision.get(key) == value for key, value in expected.items())
        and isinstance(decision.get("frozen_binding"), dict)
    ):
        raise BrainDevelopmentalAgeDecisionMissing(
            "The frozen developmental-age ownership requirement is malformed."
        )
    return expected


def _matches_human_developmental_age_receipts(
    candidate: Any,
    *,
    expected_count: int,
    expected_requirement: dict[str, str],
) -> bool:
    """Validate exact ownership parity without reading renderer prose."""

    expected_keys = {*expected_requirement, "status"}
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("human_developmental_age_decision"), dict)
        and set(item["human_developmental_age_decision"]) == expected_keys
        and all(
            item["human_developmental_age_decision"].get(key) == value
            for key, value in expected_requirement.items()
        )
        and item["human_developmental_age_decision"].get("status") in {"approved", "rewritten"}
        for index, item in enumerate(candidate, start=1)
    )


def _required_human_developmental_presence_requirement(
    request: BrainRunRequest,
) -> dict[str, str]:
    """Return the exact age-general facial-presence decision, if applicable."""

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("human_developmental_presence_decision")
    if not isinstance(decision, dict):
        return {}
    expected = {
        "contract_version": "v3_human_developmental_presence_decision_v2",
        "developmental_presence": "integrated_stage_coherent_face_attention_and_affect",
        "resolution_mode": (
            "holistic_person_and_situation_resolution"
        ),
        "owner": "remote_v3_llm_brain",
    }
    if not (
        decision.get("required") is True
        and all(decision.get(key) == value for key, value in expected.items())
        and isinstance(decision.get("frozen_binding"), dict)
    ):
        raise BrainDevelopmentalPresenceDecisionMissing(
            "The frozen developmental-presence requirement is malformed."
        )
    return expected


def _matches_human_developmental_presence_receipts(
    candidate: Any,
    *,
    expected_count: int,
    expected_requirement: dict[str, str],
) -> bool:
    """Validate exact semantic-signoff parity without inspecting prompt words."""

    expected_keys = {*expected_requirement, "status"}
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("human_developmental_presence_decision"), dict)
        and set(item["human_developmental_presence_decision"]) == expected_keys
        and all(
            item["human_developmental_presence_decision"].get(key) == value
            for key, value in expected_requirement.items()
        )
        and item["human_developmental_presence_decision"].get("status")
        in {"approved", "rewritten"}
        for index, item in enumerate(candidate, start=1)
    )


def _required_professional_anchor_view_requirement(request: BrainRunRequest) -> dict[str, str]:
    """Return the exact server-frozen anchor receipt contract, if required.

    This reads only a typed contract. It deliberately does not inspect the
    user request or canonical prompt for view words.
    """

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("professional_anchor_view_decision")
    if not isinstance(decision, dict):
        return {}
    target = str(decision.get("target_view_role") or "").strip()
    version = str(decision.get("contract_version") or "").strip()
    capture = str(decision.get("capture_presentation") or "").strip()
    continuity = str(decision.get("capture_continuity") or "").strip()
    if not (
        decision.get("required") is True
        and version in {
            "v3_professional_anchor_view_decision_v1",
            "v3_professional_anchor_view_decision_v2",
            "v3_professional_anchor_view_decision_v3",
        }
        and decision.get("owner") == "remote_v3_llm_brain"
        and isinstance(decision.get("frozen_binding"), dict)
        and target in {"standard_front", "three_quarter", "profile"}
    ):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The frozen Professional anchor-view requirement is malformed."
        )
    if version == "v3_professional_anchor_view_decision_v2" and capture != "neutral_identity_evidence_capture":
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The frozen Professional neutral-capture requirement is missing or contradictory."
        )
    if version == "v3_professional_anchor_view_decision_v1" and capture:
        raise BrainProfessionalAnchorViewDecisionMissing(
            "A historical Professional anchor-view requirement cannot claim a v2 capture decision."
        )
    if version == "v3_professional_anchor_view_decision_v3":
        expected_continuity = (
            "establish_neutral_capture"
            if target == "standard_front"
            else "preserve_approved_prior_capture"
        )
        if capture != "neutral_identity_evidence_capture" or continuity != expected_continuity:
            raise BrainProfessionalAnchorViewDecisionMissing(
                "The frozen Professional serial-capture continuity requirement is missing or contradictory."
            )
    elif continuity:
        raise BrainProfessionalAnchorViewDecisionMissing(
            "A historical Professional anchor-view requirement cannot claim a v3 continuity decision."
        )
    return {
        "contract_version": version,
        "target_view_role": target,
        **({"capture_presentation": capture} if capture else {}),
        **({"capture_continuity": continuity} if continuity else {}),
    }


def _matches_professional_anchor_view_receipts(
    candidate: Any,
    *,
    expected_count: int,
    expected_requirement: dict[str, str],
) -> bool:
    """Validate exact structural role parity without reading prompt prose."""

    expected_version = expected_requirement.get("contract_version")
    expected_target_view_role = expected_requirement.get("target_view_role")
    expected_capture = expected_requirement.get("capture_presentation")
    expected_continuity = expected_requirement.get("capture_continuity")
    expected_keys = {"contract_version", "target_view_role", "status", "owner"}
    if expected_capture:
        expected_keys.add("capture_presentation")
    if expected_continuity:
        expected_keys.add("capture_continuity")
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("professional_anchor_view_decision"), dict)
        and set(item["professional_anchor_view_decision"]) == expected_keys
        and item["professional_anchor_view_decision"].get("contract_version")
        == expected_version
        and item["professional_anchor_view_decision"].get("target_view_role")
        == expected_target_view_role
        and (
            item["professional_anchor_view_decision"].get("capture_presentation") == expected_capture
            if expected_capture
            else "capture_presentation" not in item["professional_anchor_view_decision"]
        )
        and (
            item["professional_anchor_view_decision"].get("capture_continuity")
            == expected_continuity
            if expected_continuity
            else "capture_continuity" not in item["professional_anchor_view_decision"]
        )
        and item["professional_anchor_view_decision"].get("status") in {"approved", "rewritten"}
        and item["professional_anchor_view_decision"].get("owner") == "remote_v3_llm_brain"
        for index, item in enumerate(candidate, start=1)
    )


def _has_remote_rendering_intent(candidate: Any) -> bool:
    """Confirm that semantics came from the Brain rather than a fallback."""

    if not isinstance(candidate, dict):
        return False
    intent = candidate.get("rendering_intent")
    if not isinstance(intent, dict):
        return False
    return (
        str(intent.get("rendering_mode") or "") in {"photoreal", "stylized", "mixed", "unknown"}
        and str(intent.get("stylization_scope") or "") in {"whole_image", "object_surface", "none", "ambiguous"}
        and str(intent.get("decision_owner") or "") == "remote_brain"
    )


def _has_complete_remote_visual_task_profile(candidate: Any) -> bool:
    """Accept only a complete remote semantic profile for a real-image job.

    This is a contract-shape gate, not a local subject classifier.  It never
    derives a person, age, product, style, or renderer phrase from user text.
    It merely refuses to let a partial remote answer inherit those semantic
    decisions from the deterministic compatibility fallback.
    """

    if not _has_remote_rendering_intent(candidate) or not isinstance(candidate, dict):
        return False
    required_profile_fields = {
        "developmental_age_intent",
        "reference_channel_ownership_intent",
        "subject_entities",
        "visual_intent_tags",
        "unknown_requirements",
        "confidence",
        "evidence",
    }
    if not required_profile_fields.issubset(candidate):
        return False
    entities = candidate.get("subject_entities")
    evidence = candidate.get("evidence")
    tags = candidate.get("visual_intent_tags")
    unknowns = candidate.get("unknown_requirements")
    confidence = candidate.get("confidence")
    developmental_age_intent = candidate.get("developmental_age_intent")
    reference_ownership = candidate.get("reference_channel_ownership_intent")
    if not all(isinstance(value, list) for value in (entities, evidence, tags, unknowns)):
        return False
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0.0 <= confidence <= 1.0:
        return False
    if developmental_age_intent not in {
        "current_request_assigns_stage",
        "preserve_reference_stage",
        "not_applicable",
        "ambiguous",
    }:
        return False
    if not _has_remote_reference_channel_ownership_intent(reference_ownership):
        return False
    entity_fields = {
        "entity_id",
        "entity_type",
        "role",
        "source_asset_ids",
        "visible_in_target",
        "preservation_level",
        "confidence",
        "attributes",
    }
    evidence_fields = {"evidence_id", "evidence_type", "source", "value", "confidence", "metadata"}
    if any(
        not isinstance(entity, dict)
        or not entity_fields.issubset(entity)
        or not isinstance(entity.get("source_asset_ids"), list)
        or not isinstance(entity.get("visible_in_target"), bool)
        or not isinstance(entity.get("attributes"), dict)
        or not isinstance(entity.get("confidence"), (int, float))
        or isinstance(entity.get("confidence"), bool)
        or not 0.0 <= entity["confidence"] <= 1.0
        for entity in entities
    ):
        return False
    if any(
        not isinstance(item, dict)
        or not evidence_fields.issubset(item)
        or not isinstance(item.get("metadata"), dict)
        or not isinstance(item.get("confidence"), (int, float))
        or isinstance(item.get("confidence"), bool)
        or not 0.0 <= item["confidence"] <= 1.0
        for item in evidence
    ):
        return False
    return all(isinstance(item, str) and item.strip() for item in [*tags, *unknowns])


def _merge_complete_remote_visual_task_profile(base: Any, remote: dict[str, Any]) -> dict[str, Any]:
    """Bind structural IDs locally while preserving every remote semantic choice.

    The generic compatibility merger intentionally omits empty values. That is
    unsafe for a complete remote profile: an explicit empty `subject_entities`
    or `evidence` list is a deliberate Brain decision, not an absent patch.
    """

    merged = _merge_dict(base if isinstance(base, dict) else {}, remote)
    for key in (
        "rendering_intent",
        "developmental_age_intent",
        "reference_channel_ownership_intent",
        "subject_entities",
        "visual_intent_tags",
        "unknown_requirements",
        "confidence",
        "evidence",
    ):
        merged[key] = remote[key]
    return merged


def _has_remote_reference_channel_ownership_intent(candidate: Any) -> bool:
    if not isinstance(candidate, dict):
        return False
    required = {
        "applicability",
        "decision_owner",
        "reference_owned_channels",
        "current_request_owned_channels",
        "evidence_ids",
        "confidence",
    }
    if not required.issubset(candidate):
        return False
    if candidate.get("decision_owner") != "remote_brain":
        return False
    if candidate.get("applicability") not in {"applicable", "not_applicable", "ambiguous"}:
        return False
    reference_owned = candidate.get("reference_owned_channels")
    current_owned = candidate.get("current_request_owned_channels")
    evidence_ids = candidate.get("evidence_ids")
    confidence = candidate.get("confidence")
    if not all(isinstance(value, list) for value in (reference_owned, current_owned, evidence_ids)):
        return False
    if not all(isinstance(item, str) and item.strip() for item in [*reference_owned, *current_owned, *evidence_ids]):
        return False
    if any(channel not in REFERENCE_CHANNEL_IDS for channel in [*reference_owned, *current_owned]):
        return False
    if set(reference_owned) & set(current_owned):
        return False
    return isinstance(confidence, (int, float)) and not isinstance(confidence, bool) and 0.0 <= confidence <= 1.0


def _has_complete_remote_capability_activation_intent(candidate: Any) -> bool:
    """Validate a Brain-owned capability proposal without interpreting content."""

    if not isinstance(candidate, dict):
        return False
    required_fields = {"requested_capabilities", "rejected_capabilities", "unresolved_signals", "confidence"}
    if not required_fields.issubset(candidate):
        return False
    requested = candidate.get("requested_capabilities")
    rejected = candidate.get("rejected_capabilities")
    unresolved = candidate.get("unresolved_signals")
    confidence = candidate.get("confidence")
    if not all(isinstance(value, list) for value in (requested, rejected, unresolved)):
        return False
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0.0 <= confidence <= 1.0:
        return False
    requested_fields = {
        "capability_id",
        "activation_mode",
        "reason_codes",
        "evidence_ids",
        "requested_profile",
        "confidence",
    }
    rejected_fields = {"capability_id", "reason_code", "evidence_ids", "confidence"}
    if any(
        not isinstance(item, dict)
        or not requested_fields.issubset(item)
        or not isinstance(item.get("reason_codes"), list)
        or not isinstance(item.get("evidence_ids"), list)
        or not isinstance(item.get("confidence"), (int, float))
        or isinstance(item.get("confidence"), bool)
        or not 0.0 <= item["confidence"] <= 1.0
        for item in requested
    ):
        return False
    if any(
        not isinstance(item, dict)
        or not rejected_fields.issubset(item)
        or not isinstance(item.get("evidence_ids"), list)
        or not isinstance(item.get("confidence"), (int, float))
        or isinstance(item.get("confidence"), bool)
        or not 0.0 <= item["confidence"] <= 1.0
        for item in rejected
    ):
        return False
    return all(isinstance(item, str) and item.strip() for item in unresolved)


def _merge_complete_remote_capability_activation_intent(base: Any, remote: dict[str, Any]) -> dict[str, Any]:
    """Keep local binding IDs while honoring empty remote capability decisions."""

    merged = _merge_dict(base if isinstance(base, dict) else {}, remote)
    for key in ("requested_capabilities", "rejected_capabilities", "unresolved_signals", "confidence"):
        merged[key] = remote[key]
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
