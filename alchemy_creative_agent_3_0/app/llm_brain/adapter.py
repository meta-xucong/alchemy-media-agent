"""Adapter that runs V3-native pre-generation reasoning."""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
import os
import re
import time
from json import JSONDecodeError
from typing import Any, Mapping

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
from .finalizer_lifecycle import (
    REMOTE_BRAIN_FINALIZER_LIFECYCLE_FAILURE_CODES,
    build_remote_brain_finalizer_lifecycle,
    safe_remote_brain_finalizer_lifecycle,
)
from .providers import (
    BrainDevelopmentalAgeDecisionMissing,
    BrainDevelopmentalPresenceDecisionMissing,
    BrainExecutionBudgetExceeded,
    BrainInvalidJsonResponse,
    BrainOutputTruncated,
    BrainHumanNaturalnessDecisionMissing,
    BrainPromptContractInvalid,
    BrainProfessionalAnchorViewDecisionMissing,
    BrainProviderAdmissionDecisionMissing,
    BrainProviderError,
    BrainProviderUnavailable,
    BrainReferenceChannelOwnershipDecisionMissing,
    BrainSemanticPreflightMissing,
    BrainTransportTimeoutError,
    V3LLMBrainProvider,
    pop_transport_receipt,
)
from .stage_trace import record_stage_event
from ..scenario_packs.ecommerce import (
    EcommerceCreativeRiskPreflight,
    professional_identity_view_kinds_from_selectors,
    validate_ecommerce_creative_risk_preflight_payload,
    validate_professional_ecommerce_pose_contract_payload,
)
from ..shared_capabilities.activation import REFERENCE_CHANNEL_IDS, TemplateCapabilityPolicy, general_capability_policy
from ..visual_assets.body_silhouette_source_standard import (
    body_silhouette_mcp_materialization_prompt_findings,
)
from ..visual_assets.body_proportion_evidence_profile import (
    BodyMorphologyEvidenceProfile,
    BodyProportionEvidenceProfile,
)


GENERAL_SCENARIO_ID = "general_creative"
_INVALID_ECOMMERCE_CREATIVE_RISK_PREFLIGHT = {
    "contract_version": "ecommerce_creative_risk_preflight_v1",
    "owner": "ecommerce_specialized_preflight",
    "applies_to": "ecommerce",
    "status": "invalid",
}
_INVALID_PROFESSIONAL_ECOMMERCE_POSE_CONTRACT = {
    "contract_version": "professional_ecommerce_pose_contract_v2",
    "owner": "professional_ecommerce_deliverable_pose_acceptance",
    "status": "invalid",
}
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

    def provider_failure_audit(self, exc: Exception, *, stage: str) -> dict[str, Any]:
        """Project one remote-provider exception into public-safe audit facts."""

        transport_failure = _remote_brain_transport_failure(exc)
        serialization_failure = _remote_brain_finalizer_serialization_failure(exc)
        execution_budget = self.execution_budget_receipt()
        http_status_code = _remote_provider_http_status_code(exc)
        transport_kind = _remote_provider_transport_kind(exc)
        finalizer_lifecycle = safe_remote_brain_finalizer_lifecycle(
            getattr(exc, "_remote_brain_finalizer_lifecycle", None)
        )
        return {
            "remote_provider_error_class": _remote_provider_error_class(exc),
            "remote_brain_stage": _safe_remote_brain_stage(stage),
            **(
                {"remote_brain_request_started": finalizer_lifecycle["remote_brain_request_started"]}
                if finalizer_lifecycle
                else {}
            ),
            **(
                {"remote_brain_finalizer_lifecycle": finalizer_lifecycle}
                if finalizer_lifecycle
                else {}
            ),
            **(
                {"remote_provider_http_status_code": http_status_code}
                if http_status_code is not None
                else {}
            ),
            **(
                {"remote_provider_transport_kind": transport_kind}
                if transport_kind
                else {}
            ),
            **(
                {"remote_brain_transport_failure": transport_failure}
                if transport_failure
                else {}
            ),
            **(
                {"remote_brain_serialization_failure": serialization_failure}
                if serialization_failure
                else {}
            ),
            **(
                {"remote_brain_execution_budget": execution_budget}
                if execution_budget is not None
                else {}
            ),
        }

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
        initial_contract_validation_audit: dict[str, Any] = {}
        final_contract_validation_audit: dict[str, Any] = {}
        try:
            record_stage_event(
                "brain_adapter",
                "semantic_plan_provider_call",
                stage=request.stage,
                extra={"requested_image_count": request.requested_image_count},
            )
            data = self.provider.run(request)
            record_stage_event("brain_adapter", "semantic_plan_provider_returned", stage=request.stage)
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
                requires_product_truth_selection=_requires_product_truth_selection(request),
            )
            initial_rejected_sections = _remote_contract_rejected_sections(result)
            image_set_cardinality_audit = _remote_image_set_cardinality_audit(result)
            image_set_validation_audit = _remote_image_set_validation_audit(result)
            initial_contract_validation_audit = _remote_contract_validation_audit(result)
            record_stage_event(
                "brain_adapter",
                "semantic_plan_schema_validated",
                stage=request.stage,
                extra={
                    "remote_contract_rejected_count": len(initial_rejected_sections),
                    "remote_contract_rejected_sections": initial_rejected_sections,
                    **image_set_cardinality_audit,
                    **image_set_validation_audit,
                    **_remote_contract_validation_stage_fields(initial_contract_validation_audit),
                },
            )
            recovery_transport_receipt: dict[str, Any] = {}
            if strict_remote_contract and initial_rejected_sections:
                # A valid transport JSON object can still violate the frozen
                # semantic schema. Give the same remote Brain one bounded
                # opportunity to re-answer the same immutable request. This
                # is not local JSON repair and it happens before any image
                # Provider operation.
                semantic_recovery_attempted = True
                record_stage_event(
                    "brain_adapter",
                    "semantic_recovery_provider_call",
                    stage=request.stage,
                    extra={
                        "remote_contract_rejected_count": len(initial_rejected_sections),
                        "remote_contract_rejected_sections": initial_rejected_sections,
                        **image_set_cardinality_audit,
                        **image_set_validation_audit,
                        **_remote_contract_validation_stage_fields(initial_contract_validation_audit),
                    },
                )
                recovery_request = _semantic_contract_recovery_request(
                    request,
                    rejected_sections=initial_rejected_sections,
                )
                recovery_started = time.perf_counter()
                recovery_data = self.provider.run(recovery_request)
                record_stage_event("brain_adapter", "semantic_recovery_provider_returned", stage=request.stage)
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
                    requires_product_truth_selection=_requires_product_truth_selection(request),
                )
                final_contract_validation_audit = _remote_contract_validation_audit(result)
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
                    {
                        "remote_semantic_contract_recovery_initial_validation_audit": initial_contract_validation_audit,
                    }
                    if semantic_recovery_attempted and initial_contract_validation_audit
                    else {}
                ),
                **(
                    {
                        "remote_semantic_contract_recovery_final_validation_audit": final_contract_validation_audit,
                    }
                    if semantic_recovery_attempted and final_contract_validation_audit
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
            serialization_failure = _remote_brain_serialization_failure(exc)
            record_stage_event(
                "brain_adapter",
                "semantic_plan_blocked",
                stage=request.stage,
                terminal_reason=_remote_provider_error_class(exc),
                extra=serialization_failure,
            )
            fallback.warnings.append(str(exc))
            remote_http_status_code = _remote_provider_http_status_code(exc)
            remote_transport_failure = _remote_brain_transport_failure(exc)
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
                    {"remote_brain_transport_failure": remote_transport_failure}
                    if remote_transport_failure
                    else {}
                ),
                **(
                    {"remote_brain_serialization_failure": serialization_failure}
                    if serialization_failure
                    else {}
                ),
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
            exc = BrainProviderUnavailable("V3 LLM Brain is disabled by configuration.")
            _attach_remote_brain_finalizer_lifecycle(
                exc,
                stage=request.stage,
                provider_available=False,
                remote_brain_request_started=False,
                response_started=False,
                failure_code="provider_unavailable",
            )
            raise exc
        if not self._activation_scope_enabled(request):
            exc = BrainProviderUnavailable("No trusted capability policy is active for canonical prompt signing.")
            _attach_remote_brain_finalizer_lifecycle(
                exc,
                stage=request.stage,
                provider_available=False,
                remote_brain_request_started=False,
                response_started=False,
                failure_code="provider_unavailable",
            )
            raise exc
        if not self.provider.available(force=True):
            exc = BrainProviderUnavailable("Remote Brain is unavailable for canonical prompt signing.")
            _attach_remote_brain_finalizer_lifecycle(
                exc,
                stage=request.stage,
                provider_available=False,
                remote_brain_request_started=False,
                response_started=False,
                failure_code="provider_unavailable",
            )
            raise exc
        started = time.perf_counter()
        try:
            record_stage_event(
                "brain_adapter",
                "canonical_finalizer_provider_call",
                stage=request.stage,
                extra={"requested_image_count": request.requested_image_count},
            )
            data = self.provider.run(request)
            record_stage_event("brain_adapter", "canonical_finalizer_provider_returned", stage=request.stage)
        except (BrainProviderError, BrainProviderUnavailable) as exc:
            _attach_remote_brain_finalizer_lifecycle(
                exc,
                stage=request.stage,
                provider_available=True,
                remote_brain_request_started=True,
                response_started=_remote_brain_finalizer_response_started(exc),
                failure_code=_remote_brain_finalizer_failure_code(exc),
            )
            failure_audit = self.provider_failure_audit(exc, stage=request.stage)
            execution_budget = failure_audit.get("remote_brain_execution_budget")
            execution_budget = execution_budget if isinstance(execution_budget, dict) else {}
            transport_failure = failure_audit.get("remote_brain_transport_failure")
            transport_failure = transport_failure if isinstance(transport_failure, dict) else {}
            serialization_failure = failure_audit.get("remote_brain_serialization_failure")
            serialization_failure = serialization_failure if isinstance(serialization_failure, dict) else {}
            record_stage_event(
                "brain_adapter",
                "canonical_finalizer_provider_error",
                stage=request.stage,
                terminal_reason=failure_audit.get("remote_provider_error_class"),
                extra={
                    **transport_failure,
                    **serialization_failure,
                    **(
                        {"remote_http_status_code": failure_audit.get("remote_provider_http_status_code")}
                        if isinstance(failure_audit.get("remote_provider_http_status_code"), int)
                        else {}
                    ),
                    **(
                        {"remote_provider_transport_kind": failure_audit.get("remote_provider_transport_kind")}
                        if failure_audit.get("remote_provider_transport_kind")
                        else {}
                    ),
                    "logical_budget_seconds": execution_budget.get("logical_budget_seconds"),
                    "remaining_ms": execution_budget.get("remaining_ms"),
                    "state": execution_budget.get("state"),
                },
            )
            raise
        except Exception as exc:  # pragma: no cover - defensive provider boundary
            record_stage_event(
                "brain_adapter",
                "canonical_finalizer_provider_error",
                stage=request.stage,
                terminal_reason=exc.__class__.__name__,
            )
            raise BrainProviderError("Remote Brain failed while signing the canonical provider prompt.") from exc
        transport_receipt = pop_transport_receipt(data) if isinstance(data, dict) else {}
        transport_receipt = _with_elapsed_transport_receipt(
            transport_receipt,
            stage=request.stage,
            elapsed_ms=_elapsed_ms(started),
        )
        prompts_raw = data.get("canonical_provider_prompts") if isinstance(data, dict) else None
        expected_count = request.requested_image_count
        record_stage_event(
            "brain_adapter",
            "canonical_finalizer_schema_validation_started",
            stage=request.stage,
            extra={"requested_image_count": expected_count},
        )
        if not _matches_canonical_provider_prompt_cardinality(prompts_raw, expected_count=expected_count):
            raise BrainPromptContractInvalid("Remote Brain returned an invalid canonical provider-prompt contract.")
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
        professional_anchor_view_reuse_applied = False
        professional_anchor_view_reuse_provenance = ""
        if professional_anchor_view_requirement and not _matches_professional_anchor_view_receipts(
            prompts_raw,
            expected_count=expected_count,
            expected_requirement=professional_anchor_view_requirement,
        ):
            reuse = _trusted_professional_anchor_view_decision_reuse(
                request,
                expected_count=expected_count,
                expected_requirement=professional_anchor_view_requirement,
            )
            if reuse and not _has_any_professional_anchor_view_receipt(prompts_raw):
                prompts_raw = _with_reused_professional_anchor_view_receipts(
                    prompts_raw,
                    decision=reuse["decision"],
                )
                professional_anchor_view_reuse_applied = True
                professional_anchor_view_reuse_provenance = str(reuse["provenance"])
            if not _matches_professional_anchor_view_receipts(
                prompts_raw,
                expected_count=expected_count,
                expected_requirement=professional_anchor_view_requirement,
            ):
                raise BrainProfessionalAnchorViewDecisionMissing(
                    "Remote Brain did not return the required frozen Professional anchor-view receipt."
                )
        provider_admission_requirement = _required_provider_admission_requirement(request)
        if provider_admission_requirement and not _matches_provider_admission_receipts(
            prompts_raw,
            expected_count=expected_count,
            expected_requirement=provider_admission_requirement,
        ):
            raise BrainProviderAdmissionDecisionMissing(
                "Remote Brain did not return the required provider-admission receipt."
            )
        slot_delta_requirement = _required_reference_led_slot_delta_requirement(request)
        if slot_delta_requirement and not _matches_reference_led_slot_delta_receipts(
            prompts_raw,
            expected_count=expected_count,
            expected_requirement=slot_delta_requirement,
        ):
            raise BrainProviderAdmissionDecisionMissing(
                "Remote Brain did not return the required reference-led slot-delta receipt."
            )
        stage_prompt_scope_violations = _character_card_stage_prompt_scope_violations(
            prompts_raw,
            request=request,
        )
        if stage_prompt_scope_violations:
            raise BrainProviderAdmissionDecisionMissing(
                "Remote Brain signed a Character Card stage prompt outside the requested slot target."
            )
        anchor_prompt_scope_violations = _professional_anchor_prompt_scope_violations(
            prompts_raw,
            expected_requirement=professional_anchor_view_requirement,
        )
        if anchor_prompt_scope_violations:
            raise BrainProfessionalAnchorViewDecisionMissing(
                "Remote Brain signed a Character Card Face Identity prompt outside the frozen face/head slot scope."
            )
        try:
            prompts = [BrainCanonicalProviderPrompt.model_validate(item) for item in prompts_raw]
        except ValidationError as exc:
            raise BrainPromptContractInvalid("Remote Brain returned an invalid canonical provider-prompt contract.") from exc
        record_stage_event(
            "brain_adapter",
            "canonical_finalizer_schema_validated",
            stage=request.stage,
            extra={"requested_image_count": expected_count},
        )
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
                "professional_anchor_view_decision_reuse_applied": professional_anchor_view_reuse_applied,
                "professional_anchor_view_decision_reuse_provenance": professional_anchor_view_reuse_provenance,
                "professional_anchor_prompt_scope_checked": bool(
                    professional_anchor_view_requirement
                    and professional_anchor_view_requirement.get("capture_scope")
                    == "character_card_face_identity"
                ),
                "professional_anchor_view_decisions": (
                    [
                        prompt.professional_anchor_view_decision.model_dump(
                            mode="json", exclude_none=True
                        )
                        for prompt in prompts
                        if prompt.professional_anchor_view_decision is not None
                    ]
                    if professional_anchor_view_requirement
                    else []
                ),
                "provider_admission_decision_required": bool(provider_admission_requirement),
                "provider_admission_decision_signed": bool(provider_admission_requirement),
                "provider_admission_decisions": (
                    [
                        prompt.provider_admission_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.provider_admission_decision is not None
                    ]
                    if provider_admission_requirement
                    else []
                ),
                "reference_led_slot_delta_decision_required": bool(slot_delta_requirement),
                "reference_led_slot_delta_decision_signed": bool(slot_delta_requirement),
                "reference_led_slot_delta_decisions": (
                    [
                        prompt.reference_led_slot_delta_decision.model_dump(mode="json")
                        for prompt in prompts
                        if prompt.reference_led_slot_delta_decision is not None
                    ]
                    if slot_delta_requirement
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
        ecommerce_creative_context = _ecommerce_creative_context(
            metadata,
            scenario_id,
            requested_image_count=requested_count,
        )
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
        if metadata.get("professional_product_truth_required") is not None:
            request_metadata["professional_product_truth_required"] = bool(
                metadata.get("professional_product_truth_required")
            )
        if metadata.get("doc270_ecommerce_view_activation_enabled") is True and isinstance(
            metadata.get("doc270_ecommerce_view_activation_selection"), list
        ):
            # E31 owns the already-verified per-output original binding. The
            # Brain still owns image intent, but must not be asked to repeat
            # the same opaque source choice as a second authority.
            request_metadata["doc270_ecommerce_view_activation_authoritative"] = True
        if metadata.get("professional_product_model_planning") is not None:
            request_metadata["professional_product_model_planning"] = bool(
                metadata.get("professional_product_model_planning")
            )
        body_proportion_profile = self._validated_body_proportion_profile(metadata)
        if self._professional_body_proportion_receipt_required(metadata):
            request_metadata["professional_body_proportion_receipt_required"] = True
            request_metadata["professional_body_proportion_server_context"] = {
                "professional_mode": "professional",
                "local_mcp_professional_relay": True,
                "professional_body_proportion_contract_source": "server_owned_professional_binding_resolver",
                "professional_mode_binding_record": {
                    "server_owned_binding_resolver_validated": True,
                },
            }
            if body_proportion_profile is not None:
                request_metadata["professional_body_proportion_server_context"][
                    "body_proportion_evidence_profile"
                ] = body_proportion_profile.model_dump(mode="json")
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
            transport_timeout_seconds=_brain_transport_timeout_seconds(metadata),
            metadata=request_metadata,
            capability_catalog=dict(capability_catalog or {}),
            pre_activation_capabilities=dict(pre_activation_capabilities or {}),
            template_capability_policy=template_capability_policy or general_capability_policy(),
        )

    @staticmethod
    def _professional_body_proportion_receipt_required(metadata: Mapping[str, Any]) -> bool:
        """Expose body-proportion receipt only from server-owned Professional planning.

        Public metadata can contain arbitrary keys, so the Brain payload must
        not trust a lone boolean.  The native Professional planner sets the
        relay marker, binding record, and closed source marker after resolving
        a server-owned Character Card binding.
        """

        if metadata.get("professional_body_proportion_receipt_required") is not True:
            return False
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
    def _validated_body_proportion_profile(
        metadata: Mapping[str, Any],
    ) -> BodyProportionEvidenceProfile | BodyMorphologyEvidenceProfile | None:
        """Consume only a typed, server-owned observed Body profile.

        Raw public metadata, partitions, hashes, and counts are never promoted
        here.  The in-memory Pydantic instance is the trusted handoff from the
        Body source-analysis owner; ProductApi separately rejects the same key
        at its public boundary unless its trusted preparation path is active.
        """

        if "professional_body_proportion_evidence_profile" in metadata:
            raise ValueError("body_proportion_analysis_untrusted")
        if not V3LLMBrainAdapter._professional_body_proportion_receipt_required(metadata):
            return None
        raw_mode = metadata.get("professional_character_card_body_refresh_source_mode")
        source_mode = str(raw_mode or "").strip().lower()
        raw_receipt = metadata.get("professional_body_proportion_analysis_receipt")
        if source_mode == "inference_first":
            if raw_receipt is not None:
                raise ValueError("body_proportion_analysis_source_mode_invalid")
            return None
        if source_mode != "reference_assisted":
            return None
        if str(metadata.get("professional_character_card_stage") or "").strip().lower() != "body_silhouette":
            if raw_receipt is not None:
                raise ValueError("body_proportion_analysis_stage_invalid")
            return None
        if raw_receipt is None:
            raise ValueError("body_proportion_analysis_missing")
        if not isinstance(
            raw_receipt,
            (BodyProportionEvidenceProfile, BodyMorphologyEvidenceProfile),
        ):
            raise ValueError("body_proportion_analysis_untrusted")
        if (
            metadata.get("professional_character_card_candidate_index") is not None
            and not isinstance(raw_receipt, BodyMorphologyEvidenceProfile)
        ):
            raise ValueError("body_refresh_analysis_context_superseded")
        return raw_receipt

    def _activation_scope_enabled(self, request: BrainRunRequest) -> bool:
        policy = request.template_capability_policy
        if not policy.brain_activation_enabled:
            return False
        if request.scenario_id == GENERAL_SCENARIO_ID or request.template_id == GENERAL_TEMPLATE_ID:
            return True
        return policy.policy_id != "general_template_capabilities"

    def _merge_remote_result(
        self,
        fallback: BrainRunResult,
        data: dict[str, Any],
        *,
        requires_complete_image_set: bool = False,
        requires_product_truth_selection: bool = False,
    ) -> BrainRunResult:
        payload = fallback.model_dump(mode="json")
        rejected_sections: list[str] = []
        cardinality_audit: dict[str, Any] = {}
        image_set_validation_audit: dict[str, Any] = {}
        contract_validation_sections: dict[str, dict[str, Any]] = {}
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
                cardinality_audit = _image_set_cardinality_audit(
                    remote_section,
                    expected_count=fallback.image_set_plan.image_count,
                )
                if not cardinality_audit["cardinality_valid"]:
                    rejected_sections.append(key)
                    continue
                if requires_product_truth_selection and not _product_truth_selection_contract_valid(
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
                    contract_validation_sections[key] = _visual_task_profile_shape_validation_audit(remote_section)
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
                if key == "image_set_plan":
                    candidate_cardinality_audit = _image_set_cardinality_audit(
                        candidate,
                        expected_count=fallback.image_set_plan.image_count,
                    )
                if key == "image_set_plan" and not candidate_cardinality_audit["cardinality_valid"]:
                    cardinality_audit = candidate_cardinality_audit
                    rejected_sections.append(key)
                    continue
                if key == "image_set_plan":
                    payload, accepted, validation_audit = _merge_validated_section_with_audit(
                        payload,
                        key,
                        candidate,
                    )
                else:
                    payload, accepted, validation_audit = _merge_validated_section_with_audit(
                        payload,
                        key,
                        candidate,
                    )
                if not accepted:
                    if key == "image_set_plan" and validation_audit:
                        image_set_validation_audit = validation_audit
                    if validation_audit:
                        contract_validation_sections[key] = validation_audit
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
                **(
                    {
                        "remote_image_set_cardinality_audit": cardinality_audit,
                    }
                    if "image_set_plan" in rejected_sections and cardinality_audit
                    else {}
                ),
                **(
                    {
                        "remote_image_set_validation_audit": image_set_validation_audit,
                    }
                    if "image_set_plan" in rejected_sections and image_set_validation_audit
                    else {}
                ),
                **(
                    {
                        "remote_contract_validation_audit": _remote_contract_validation_audit_payload(
                            contract_validation_sections
                        ),
                    }
                    if contract_validation_sections
                    else {}
                ),
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


def _remote_image_set_cardinality_audit(result: BrainRunResult) -> dict[str, Any]:
    raw = result.audit.get("remote_image_set_cardinality_audit") if isinstance(result.audit, dict) else None
    if not isinstance(raw, dict):
        return {}
    audit: dict[str, Any] = {}
    for key in ("expected_image_count", "remote_image_count", "remote_shot_plan_count"):
        value = raw.get(key)
        if value is None:
            audit[key] = None
        elif isinstance(value, int):
            audit[key] = value
    if isinstance(raw.get("cardinality_valid"), bool):
        audit["cardinality_valid"] = bool(raw["cardinality_valid"])
    return audit


def _remote_image_set_validation_audit(result: BrainRunResult) -> dict[str, Any]:
    raw = result.audit.get("remote_image_set_validation_audit") if isinstance(result.audit, dict) else None
    if not isinstance(raw, dict):
        return {}
    audit: dict[str, Any] = {}
    count = raw.get("validation_error_count")
    if isinstance(count, int):
        audit["validation_error_count"] = count
    for key in ("validation_error_paths", "validation_error_types"):
        values = raw.get(key)
        if isinstance(values, list):
            audit[key] = [str(item) for item in values if str(item).strip()][:8]
    return audit


def _remote_contract_validation_audit(result: BrainRunResult) -> dict[str, Any]:
    raw = result.audit.get("remote_contract_validation_audit") if isinstance(result.audit, dict) else None
    if not isinstance(raw, dict):
        return {}
    if raw.get("schema_version") != "v3_remote_contract_validation_audit_v1":
        return {}
    sections = raw.get("sections")
    if not isinstance(sections, dict):
        return {}
    safe_sections: dict[str, dict[str, Any]] = {}
    for section, audit in sections.items():
        section_key = str(section or "").strip()
        if section_key not in {"image_set_plan", "visual_task_profile", "capability_activation_intent"}:
            continue
        if not isinstance(audit, dict):
            continue
        count = audit.get("validation_error_count")
        paths = audit.get("validation_error_paths")
        types = audit.get("validation_error_types")
        safe_sections[section_key] = {
            "validation_error_count": count if isinstance(count, int) else 0,
            "validation_error_paths": [
                _safe_validation_path(str(item).split("."), section=section_key)
                for item in (paths if isinstance(paths, list) else [])
                if str(item).strip()
            ][:8],
            "validation_error_types": [
                _safe_validation_type(item)
                for item in (types if isinstance(types, list) else [])
                if str(item).strip()
            ][:8],
        }
        safe_sections[section_key]["validation_error_paths"] = [
            item for item in safe_sections[section_key]["validation_error_paths"] if item
        ]
    if not safe_sections:
        return {}
    return {
        "schema_version": "v3_remote_contract_validation_audit_v1",
        "sections": safe_sections,
    }


def _remote_contract_validation_stage_fields(audit: dict[str, Any]) -> dict[str, Any]:
    sections = audit.get("sections") if isinstance(audit, dict) else None
    if not isinstance(sections, dict):
        return {}
    paths: list[str] = []
    types: list[str] = []
    count = 0
    for section_audit in sections.values():
        if not isinstance(section_audit, dict):
            continue
        raw_count = section_audit.get("validation_error_count")
        if isinstance(raw_count, int):
            count += raw_count
        raw_paths = section_audit.get("validation_error_paths")
        if isinstance(raw_paths, list):
            paths.extend(str(item) for item in raw_paths if str(item).strip())
        raw_types = section_audit.get("validation_error_types")
        if isinstance(raw_types, list):
            types.extend(str(item) for item in raw_types if str(item).strip())
    if not paths and not types:
        return {}
    return {
        "validation_error_count": count,
        "validation_error_paths": list(dict.fromkeys(paths))[:8],
        "validation_error_types": list(dict.fromkeys(types))[:8],
    }


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


def _ecommerce_creative_context(
    metadata: dict[str, Any],
    scenario_id: str | None,
    *,
    requested_image_count: int,
) -> dict[str, Any]:
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
        "product_truth_reference_pool",
        "platform_constraints",
        "product_set_style",
        "role_specific_creative_intent",
        "provider_reference_budget",
        "professional_ecommerce_pose_contract",
        "category_evidence_questions",
        "seller_inputs",
        "approved_literal_copy",
        "copy_locale",
        "claim_risk_warnings",
        "warnings",
        "metadata",
    }
    context = {key: raw[key] for key in allowed if key in raw}
    if "professional_ecommerce_pose_contract" in raw:
        context["professional_ecommerce_pose_contract"] = _professional_ecommerce_pose_contract(
            raw["professional_ecommerce_pose_contract"],
            requested_image_count=requested_image_count,
        )
    if "creative_risk_preflight" in raw:
        context["creative_risk_preflight"] = _ecommerce_creative_risk_preflight(
            raw["creative_risk_preflight"],
            metadata=metadata,
            requested_image_count=requested_image_count,
        )
    return context


def _professional_ecommerce_pose_contract(
    raw: Any,
    *,
    requested_image_count: int,
) -> dict[str, Any]:
    """Return a typed pose contract or a sanitized invalid sentinel."""

    if raw is None or not isinstance(raw, dict):
        return dict(_INVALID_PROFESSIONAL_ECOMMERCE_POSE_CONTRACT)
    try:
        return validate_professional_ecommerce_pose_contract_payload(
            raw,
            requested_image_count=requested_image_count,
        ).model_dump(mode="json")
    except ValueError:
        return dict(_INVALID_PROFESSIONAL_ECOMMERCE_POSE_CONTRACT)


def _ecommerce_creative_risk_preflight(
    raw: Any,
    *,
    metadata: dict[str, Any],
    requested_image_count: int,
) -> dict[str, Any]:
    """Return typed E-Commerce preflight or a sanitized invalid sentinel."""

    if raw is None:
        return dict(_INVALID_ECOMMERCE_CREATIVE_RISK_PREFLIGHT)
    if not isinstance(raw, dict):
        return dict(_INVALID_ECOMMERCE_CREATIVE_RISK_PREFLIGHT)
    try:
        preflight = EcommerceCreativeRiskPreflight.model_validate(raw)
    except ValueError:
        return dict(_INVALID_ECOMMERCE_CREATIVE_RISK_PREFLIGHT)
    if preflight.mode != "professional":
        return preflight.model_dump(mode="json")
    has_professional_hint = any(
        item.professional_identity_hint is not None
        for item in preflight.risk_items_by_output
    )
    if not has_professional_hint:
        return preflight.model_dump(mode="json")
    try:
        approved_view_kinds = _approved_professional_identity_view_kinds(metadata)
        if not approved_view_kinds:
            raise ValueError("professional_binding_views_required")
        validate_ecommerce_creative_risk_preflight_payload(
            preflight.model_dump(mode="json"),
            scenario_id="ecommerce",
            mode="professional",
            requested_image_count=requested_image_count,
            approved_identity_view_kinds=approved_view_kinds,
        )
    except ValueError:
        return dict(_INVALID_ECOMMERCE_CREATIVE_RISK_PREFLIGHT)
    return preflight.model_dump(mode="json")


def _approved_professional_identity_view_kinds(metadata: dict[str, Any]) -> set[str]:
    raw_mode = metadata.get("professional_mode")
    if raw_mode is True:
        mode = "professional"
    else:
        mode = str(raw_mode or "").strip().lower()
    if mode != "professional":
        return set()
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


def _safe_remote_brain_stage(stage: Any) -> str:
    value = str(stage or "").strip()
    if value in _SAFE_REMOTE_BRAIN_STAGES:
        return value
    return "unknown"


def _attach_remote_brain_finalizer_lifecycle(
    exc: Exception,
    *,
    stage: str,
    provider_available: bool,
    remote_brain_request_started: bool,
    response_started: bool,
    failure_code: str,
) -> None:
    lifecycle = build_remote_brain_finalizer_lifecycle(
        stage=stage,
        provider_available=provider_available,
        remote_brain_request_started=remote_brain_request_started,
        response_started=response_started,
        failure_code=failure_code,
    )
    if lifecycle:
        setattr(exc, "_remote_brain_finalizer_lifecycle", lifecycle)


def _remote_brain_finalizer_failure_code(exc: Exception) -> str:
    if isinstance(exc, BrainProviderUnavailable):
        return "provider_unavailable"
    error_class = _remote_provider_error_class(exc)
    return (
        error_class
        if error_class in REMOTE_BRAIN_FINALIZER_LIFECYCLE_FAILURE_CODES
        else "provider_error"
    )


def _remote_brain_finalizer_response_started(exc: Exception) -> bool:
    transport = _remote_brain_transport_failure(exc)
    if isinstance(transport.get("response_started"), bool):
        return bool(transport["response_started"])
    serialization = _remote_brain_finalizer_serialization_failure(exc)
    if serialization:
        return True
    return False


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
    if any(isinstance(item, BrainTransportTimeoutError) for item in chain):
        return "timeout"
    if any(isinstance(item, BrainExecutionBudgetExceeded) for item in chain):
        return "execution_budget_exhausted"
    if any(isinstance(item, BrainOutputTruncated) for item in chain):
        return "truncated_response"
    if any(isinstance(item, BrainInvalidJsonResponse) for item in chain):
        return "invalid_response"
    if any(isinstance(item, JSONDecodeError) for item in chain):
        return "invalid_response"
    transport_kind = _remote_provider_transport_kind(exc)
    if transport_kind == "timeout":
        return "timeout"
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
    if transport_kind:
        return "upstream_transport_error"
    return "provider_error"


def _remote_brain_transport_failure(exc: Exception) -> dict[str, Any]:
    """Extract only safe remote transport diagnostics from known provider errors."""

    for item in _exception_chain(exc):
        if isinstance(item, BrainTransportTimeoutError):
            return item.safe_metadata()
    return {}


def _remote_brain_serialization_failure(exc: Exception) -> dict[str, Any]:
    """Extract only safe JSON serialization diagnostics from known provider errors."""

    for item in _exception_chain(exc):
        if isinstance(item, BrainOutputTruncated):
            return {}
        if isinstance(item, BrainInvalidJsonResponse):
            return item.safe_metadata()
    return {}


def _remote_brain_finalizer_serialization_failure(exc: Exception) -> dict[str, Any]:
    """Extract safe finalizer serialization diagnostics, including truncation."""

    for item in _exception_chain(exc):
        if isinstance(item, BrainOutputTruncated):
            return item.safe_metadata()
        if isinstance(item, BrainInvalidJsonResponse):
            return item.safe_metadata()
    return {}


def _remote_provider_http_status_code(exc: Exception) -> int | None:
    """Extract only an HTTP status code; never persist the raw provider error."""

    for item in _exception_chain(exc):
        for candidate in (
            getattr(item, "status_code", None),
            getattr(getattr(item, "response", None), "status_code", None),
        ):
            if isinstance(candidate, int) and not isinstance(candidate, bool) and 100 <= candidate <= 599:
                return candidate
        match = re.search(r"(?:status|error)\s+code\s*[:=]?\s*(\d{3})", str(item or ""), flags=re.IGNORECASE)
        if not match:
            continue
        code = int(match.group(1))
        if 100 <= code <= 599:
            return code
    return None


def _remote_provider_transport_kind(exc: Exception) -> str:
    """Classify transport-layer exception causes without exposing provider details."""

    if _remote_provider_http_status_code(exc) is not None:
        return ""
    for item in _exception_chain(exc):
        if isinstance(item, (BrainTransportTimeoutError, BrainExecutionBudgetExceeded)):
            continue
        module = str(item.__class__.__module__ or "").lower()
        name = str(item.__class__.__name__ or "").lower()
        qualified = f"{module}.{name}"
        if not (
            module.startswith("httpx")
            or module.startswith("httpcore")
            or module.startswith("openai")
            or "transport" in qualified
            or "protocol" in qualified
        ):
            continue
        if "timeout" in name:
            return "timeout"
        if "protocol" in name:
            return "protocol_error"
        if "connect" in name or "connection" in name:
            return "connection_error"
        if "read" in name:
            return "read_error"
        if "write" in name:
            return "write_error"
        if "network" in name:
            return "network_error"
        if "apierror" in name or name == "api_error":
            return "provider_api_error"
        return "transport_error"
    return ""


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


def _brain_transport_timeout_seconds(metadata: dict[str, Any]) -> float | None:
    raw = metadata.get("_brain_transport_timeout_seconds")
    if raw is None:
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return max(1.0, min(210.0, value))


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


def _image_set_cardinality_audit(candidate: Any, *, expected_count: int) -> dict[str, Any]:
    image_count: int | None = None
    shot_plan_count = 0
    if isinstance(candidate, dict):
        try:
            image_count = int(candidate.get("image_count"))
        except (TypeError, ValueError):
            image_count = None
        shot_plan = candidate.get("shot_plan")
        if isinstance(shot_plan, list):
            shot_plan_count = len([str(item).strip() for item in shot_plan if str(item).strip()])
    return {
        "expected_image_count": int(expected_count),
        "remote_image_count": image_count,
        "remote_shot_plan_count": shot_plan_count,
        "cardinality_valid": image_count == expected_count and shot_plan_count == expected_count,
    }


def _requires_product_truth_selection(request: BrainRunRequest) -> bool:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    return (
        metadata.get("professional_product_truth_required") is True
        and metadata.get("doc270_ecommerce_view_activation_authoritative") is not True
    )


def _product_truth_selection_contract_valid(candidate: Any, *, expected_count: int) -> bool:
    """Require the Brain to return one typed product-truth decision per output.

    This checks only contract presence and cardinality. Asset identity, role
    values, and renderer capacity remain validated by the professional runtime
    that owns the frozen product-truth pool.
    """

    if not isinstance(candidate, dict):
        return False
    entries = candidate.get("evidence_dimensions_by_output")
    if not isinstance(entries, list) or len(entries) != expected_count:
        return False
    indexes: list[int] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return False
        try:
            index = int(entry.get("output_index"))
        except (TypeError, ValueError):
            return False
        role = str(entry.get("product_truth_selection_role") or "").strip()
        selected = entry.get("selected_product_truth_asset_ids")
        if index < 1 or index > expected_count or not role:
            return False
        if not isinstance(selected, list) or not selected or any(
            not isinstance(item, str) or not item.strip() for item in selected
        ):
            return False
        indexes.append(index)
    return indexes == list(range(1, expected_count + 1))


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
    capture_scope = str(decision.get("capture_scope") or "").strip()
    framing_standard = str(decision.get("framing_standard") or "").strip()
    crop_policy = str(decision.get("crop_policy") or "").strip()
    torso_scope = str(decision.get("torso_scope") or "").strip()
    aspect_ratio_standard = str(decision.get("aspect_ratio_standard") or "").strip()
    source_viewpoint_inheritance = str(
        decision.get("source_viewpoint_inheritance") or ""
    ).strip()
    front_pose_normalization = str(decision.get("front_pose_normalization") or "").strip()
    face_axis_alignment = str(decision.get("face_axis_alignment") or "").strip()
    if not (
        decision.get("required") is True
        and version in {
            "v3_professional_anchor_view_decision_v1",
            "v3_professional_anchor_view_decision_v2",
            "v3_professional_anchor_view_decision_v3",
        }
        and decision.get("owner") == "remote_v3_llm_brain"
        and isinstance(decision.get("frozen_binding"), dict)
        and target in {
            "standard_front",
            "left_front_25",
            "three_quarter",
            "profile",
            "right_front_25",
            "reverse_three_quarter",
            "rear_head",
        }
        and capture_scope in {"", "character_card_face_identity"}
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
    if capture_scope == "character_card_face_identity":
        if target == "standard_front" and (
            framing_standard != "consistent_head_and_upper_shoulders_reference_crop"
            or crop_policy != "head_top_margin_full_face_neck_and_upper_shoulders_visible"
            or torso_scope != "visible_neck_collar_and_upper_shoulders"
            or aspect_ratio_standard
            != "honor_frozen_rendering_size_as_reference_card_aspect_ratio"
        ):
            raise BrainProfessionalAnchorViewDecisionMissing(
                "The frozen Character Card Face Identity framing requirement is missing or contradictory."
            )
        if target != "standard_front" and any(
            (
                framing_standard,
                crop_policy,
                torso_scope,
                aspect_ratio_standard,
                source_viewpoint_inheritance,
                front_pose_normalization,
                face_axis_alignment,
            )
        ):
            raise BrainProfessionalAnchorViewDecisionMissing(
                "Non-front Character Card Face Identity receipts must not repeat standard-front framing fields."
            )
        if target == "standard_front" and (
            source_viewpoint_inheritance
            != "identity_only_do_not_inherit_source_pose_angle"
            or front_pose_normalization
            != "standard_front_model_card_view"
            or face_axis_alignment
            != "camera_facing_front_model_card_view"
        ):
            raise BrainProfessionalAnchorViewDecisionMissing(
                "The frozen Character Card front-pose normalization requirement is missing or contradictory."
            )
    elif any(
        (
            framing_standard,
            crop_policy,
            torso_scope,
            aspect_ratio_standard,
            source_viewpoint_inheritance,
            front_pose_normalization,
            face_axis_alignment,
        )
    ):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "Ordinary Professional anchor-view requirements cannot claim Character Card framing fields."
        )
    return {
        "contract_version": version,
        "target_view_role": target,
        **({"capture_presentation": capture} if capture else {}),
        **({"capture_continuity": continuity} if continuity else {}),
        **({"capture_scope": capture_scope} if capture_scope else {}),
        **(
            {
                "framing_standard": framing_standard,
                "crop_policy": crop_policy,
                "torso_scope": torso_scope,
                "aspect_ratio_standard": aspect_ratio_standard,
            }
            if capture_scope == "character_card_face_identity"
            and target == "standard_front"
            else {}
        ),
        **(
            {
                "source_viewpoint_inheritance": source_viewpoint_inheritance,
                "front_pose_normalization": front_pose_normalization,
                "face_axis_alignment": face_axis_alignment,
            }
            if capture_scope == "character_card_face_identity" and target == "standard_front"
            else {}
        ),
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
    expected_scope = expected_requirement.get("capture_scope")
    expected_keys = {"contract_version", "target_view_role", "status", "owner"}
    optional_expected_keys = (
        "capture_presentation",
        "capture_continuity",
        "capture_scope",
        "framing_standard",
        "crop_policy",
        "torso_scope",
        "aspect_ratio_standard",
        "source_viewpoint_inheritance",
        "front_pose_normalization",
        "face_axis_alignment",
    )
    for key in optional_expected_keys:
        if expected_requirement.get(key):
            expected_keys.add(key)
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
        and all(
            item["professional_anchor_view_decision"].get(key) == expected_requirement.get(key)
            for key in optional_expected_keys
            if expected_requirement.get(key)
        )
        and all(
            key not in item["professional_anchor_view_decision"]
            for key in optional_expected_keys
            if not expected_requirement.get(key)
        )
        and item["professional_anchor_view_decision"].get("status") in {"approved", "rewritten"}
        and item["professional_anchor_view_decision"].get("owner") == "remote_v3_llm_brain"
        for index, item in enumerate(candidate, start=1)
    )


_PROFESSIONAL_ANCHOR_REUSE_BINDING_FIELDS = (
    "project_id",
    "source_asset_id",
    "source_sha256",
    "target_view_role",
    "capture_scope",
    "reference_semantics",
    "rendering_contract",
    "candidate_contract",
    "operation_context",
)


def _has_any_professional_anchor_view_receipt(candidate: Any) -> bool:
    if not isinstance(candidate, list):
        return False
    return any(
        isinstance(item, dict)
        and isinstance(item.get("professional_anchor_view_decision"), dict)
        for item in candidate
    )


def _trusted_professional_anchor_view_decision_reuse(
    request: BrainRunRequest,
    *,
    expected_count: int,
    expected_requirement: dict[str, str],
) -> dict[str, Any]:
    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    payload = metadata.get("trusted_professional_anchor_view_decision_reuse")
    if not isinstance(payload, dict):
        return {}
    if (
        payload.get("contract_version")
        != "v3_professional_anchor_view_decision_reuse_v1"
        or payload.get("provenance") != "trusted_prior_remote_brain_decision_v1"
    ):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The trusted Professional anchor-view reuse provenance is invalid."
        )
    source_binding = payload.get("source_binding")
    current_binding = payload.get("current_binding")
    actual_current_binding = metadata.get("professional_anchor_view_decision_current_binding")
    if not isinstance(source_binding, dict) or not isinstance(current_binding, dict):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The trusted Professional anchor-view reuse binding is missing."
        )
    if not isinstance(actual_current_binding, dict):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The current Professional anchor-view binding is missing."
        )
    for field in _PROFESSIONAL_ANCHOR_REUSE_BINDING_FIELDS:
        source_value = str(source_binding.get(field) or "").strip()
        current_value = str(current_binding.get(field) or "").strip()
        actual_value = str(actual_current_binding.get(field) or "").strip()
        if (
            not source_value
            or not current_value
            or not actual_value
            or source_value != current_value
            or current_value != actual_value
        ):
            raise BrainProfessionalAnchorViewDecisionMissing(
                "The trusted Professional anchor-view reuse binding does not match."
            )
    if current_binding.get("target_view_role") != expected_requirement.get("target_view_role"):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The trusted Professional anchor-view reuse view role does not match."
        )
    if current_binding.get("capture_scope") != expected_requirement.get("capture_scope"):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The trusted Professional anchor-view reuse capture scope does not match."
        )
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The trusted Professional anchor-view reuse decision is missing."
        )
    probe = [
        {
            "output_index": index,
            "professional_anchor_view_decision": dict(decision),
        }
        for index in range(1, expected_count + 1)
    ]
    if not _matches_professional_anchor_view_receipts(
        probe,
        expected_count=expected_count,
        expected_requirement=expected_requirement,
    ):
        raise BrainProfessionalAnchorViewDecisionMissing(
            "The trusted Professional anchor-view reuse decision does not match the frozen requirement."
        )
    return {
        "decision": dict(decision),
        "provenance": payload.get("provenance"),
    }


def _with_reused_professional_anchor_view_receipts(
    candidate: Any,
    *,
    decision: dict[str, Any],
) -> Any:
    if not isinstance(candidate, list):
        return candidate
    return [
        {
            **dict(item),
            "professional_anchor_view_decision": dict(decision),
        }
        for item in candidate
        if isinstance(item, dict)
    ]


def _professional_anchor_prompt_scope_violations(
    candidate: Any,
    *,
    expected_requirement: dict[str, str],
) -> list[str]:
    """Reject obvious prompt/channel drift after a signed Character Card receipt.

    The Remote Brain still owns renderer wording.  This is not a local prompt
    recipe, a child-specific aesthetic list, or a repair patch.  It only
    verifies that a signed Character Card Face Identity prompt has not left
    the frozen face/head identity-capture slot and become a body, wardrobe or
    location scene.  Those channels belong to later modules or the current
    project prompt, not the reusable Face Identity base.
    """

    if (
        not expected_requirement
        or expected_requirement.get("capture_scope") != "character_card_face_identity"
    ):
        return []
    if not isinstance(candidate, list):
        return ["canonical_provider_prompts"]

    target = str(expected_requirement.get("target_view_role") or "").strip()
    forbidden_scope_terms = (
        "full-body",
        "full body",
        "full-length",
        "full length",
        "head to toe",
        "head-to-toe",
        "whole body",
        "entire body",
        "from head to toe",
        "standing in a",
        "standing on a",
        "walking in a",
        "sunlit park",
        "park with",
        "garden",
        "beach",
        "street",
        "forest",
        "outdoor",
        "golden backlight",
        "cinematic focus",
        "fashion shoot",
        "body silhouette",
        "body proportion",
        "height estimate",
        "extreme close-up",
        "tight close-up",
        "big head",
        "big-head",
        "half-body",
        "half body",
        "waist-up",
        "waist up",
        "chest-up",
        "chest up",
        "upper body",
        "torso",
        "全身",
        "全身照",
        "全身像",
        "全身照片",
        "全身肖像",
        "从头到脚",
        "头到脚",
        "半身",
        "半身照",
        "半身像",
        "半身照片",
        "胸像",
        "胸部以上",
        "胸口以上",
        "腰部以上",
        "上半身",
        "身体轮廓",
        "身体比例",
        "身材比例",
        "身高估计",
        "站在公园",
        "站在花园",
        "户外",
        "花园",
        "海边",
        "街道",
        "森林",
        "电影感",
        "时装拍摄",
    )
    required_framing_terms = (
        "head-and-shoulders",
        "head and shoulders",
        "head-and-upper-shoulders",
        "head and upper shoulders",
        "reference-card",
        "reference card",
        "model-card",
        "model card",
        "modeling-card",
        "modeling card",
        "face card",
        "neck, collar and upper shoulders",
        "visible neck, collar and upper shoulders",
        "头部、颈部和上肩",
        "头部、颈部、上肩",
        "头部、完整面部、颈部和上肩",
        "完整面部、颈部和上肩",
        "完整脸部、颈部和上肩",
        "头颈上肩",
        "头颈和上肩",
        "头部和上肩",
        "颈部和上肩",
        "上肩景别",
        "头颈上肩景别",
    )

    def _forbidden_scope_match(text: str, term: str) -> bool:
        start = text.find(term)
        while start >= 0:
            prefix = text[max(0, start - 36): start]
            if any(
                negation in prefix
                for negation in (
                    "not ",
                    "not a ",
                    "no ",
                    "avoid ",
                    "without ",
                    "不是",
                    "不要",
                    "非",
                    "无",
                )
            ):
                start = text.find(term, start + len(term))
                continue
            return True
        return False

    view_requirements = {
        "standard_front": (
            "front-facing",
            "front facing",
            "standard-front",
            "front view",
            "frontal",
            "standard front",
            "facing the camera",
            "directly facing",
            "straight-on",
            "straight on",
            "正面",
            "标准正面",
            "正面角色卡",
            "正面视觉资产",
            "直面镜头",
            "真正直面镜头",
            "正对镜头",
            "面对镜头",
            "面向镜头",
        ),
        "three_quarter": (
            "left-front",
            "left front",
            "front-left",
            "front left",
            "left-side 45",
            "left 45",
            "left-front 45",
            "left front 45",
            "left three-quarter",
            "左前45",
            "左侧前方",
        ),
        "left_front_25": (
            "left-front 25",
            "left front 25",
            "left-front transition",
            "left front transition",
            "shallow left-front",
            "25-degree transition",
            "25 degree transition",
            "左前25",
            "25度过渡",
        ),
        "profile": (
            "profile",
            "side profile",
            "side view",
            "90-degree",
            "90 degree",
            "90°",
            "90度",
            "侧面",
            "正侧面",
        ),
        "reverse_three_quarter": (
            "opposite three-quarter",
            "opposite front-side",
            "opposite front side",
            "opposite-side 45",
            "opposite 45",
            "right-front",
            "right front",
            "front-right",
            "front right",
            "right-front 45",
            "right front 45",
            "right 45",
            "right-side 45",
            "反侧前方",
            "另一侧45",
            "另一侧前方",
            "右前45",
            "右侧前方",
        ),
        "right_front_25": (
            "right-front 25",
            "right front 25",
            "opposite 25",
            "right-front transition",
            "right front transition",
            "shallow right-front",
            "opposite transition",
            "25-degree transition",
            "25 degree transition",
            "右前25",
            "反侧25",
            "25度过渡",
        ),
        "rear_head": (
            "rear head",
            "back of head",
            "rear view",
            "back view",
            "头部背面",
            "后脑",
            "背面",
            "后视图",
        ),
    }
    rear_view_terms = (
        "rear three-quarter",
        "rear 3/4",
        "back three-quarter",
        "back 3/4",
        "back of head dominant",
        "rear of head dominant",
        "back-of-head dominant",
        "face turned mostly away",
        "face mostly hidden",
        "back-of-head reference",
        "背后三分之四",
        "背后四分之三",
        "后脑为主",
        "背向为主",
        "脸部大部分背向",
        "背面45度",
        "头部背面",
    )
    front_gaze_terms = (
        "looking at the camera",
        "direct eye contact",
        "front-facing eyes",
        "面对镜头",
        "直视镜头",
        "正脸",
        "正面",
    )
    violations: list[str] = []
    for index, item in enumerate(candidate, start=1):
        prompt = str(item.get("prompt") or "") if isinstance(item, dict) else ""
        normalized = re.sub(r"\s+", " ", prompt.lower()).strip()
        if not normalized:
            violations.append(f"output_{index}:empty_prompt")
            continue
        leaked = next(
            (term for term in forbidden_scope_terms if _forbidden_scope_match(normalized, term)),
            "",
        )
        if leaked:
            violations.append(f"output_{index}:scope_leak:{leaked}")
        if not any(term in normalized for term in required_framing_terms):
            violations.append(f"output_{index}:framing_not_standard")
        required_view_terms = view_requirements.get(target, ())
        if required_view_terms and not any(term in normalized for term in required_view_terms):
            violations.append(f"output_{index}:view_not_materialized:{target}")
        if target != "rear_head":
            leaked_rear_view = next(
                (term for term in rear_view_terms if _forbidden_scope_match(normalized, term)),
                "",
            )
            if leaked_rear_view:
                violations.append(f"output_{index}:view_conflict:{leaked_rear_view}")
        if target == "rear_head":
            leaked_front_gaze = next(
                (term for term in front_gaze_terms if _forbidden_scope_match(normalized, term)),
                "",
            )
            if leaked_front_gaze:
                violations.append(f"output_{index}:rear_allows_front_face")
        if target == "standard_front" and (
            expected_requirement.get("front_pose_normalization")
            == "standard_front_model_card_view"
        ):
            straight_terms = (
                "straight-on",
                "straight on",
                "front-facing",
                "front facing",
                "standard-front",
                "standard front",
                "真正直面镜头",
                "直面镜头",
                "标准正面",
                "正对镜头",
                "面对镜头",
                "面向镜头",
            )
            model_card_terms = (
                "model-card",
                "model card",
                "character card",
                "人物卡",
                "角色卡",
            )
            if not any(term in normalized for term in straight_terms):
                violations.append(f"output_{index}:front_pose_not_model_card_front")
            if not any(term in normalized for term in model_card_terms):
                violations.append(f"output_{index}:front_framing_not_model_card")
    return violations


def _required_provider_admission_requirement(request: BrainRunRequest) -> dict[str, str]:
    """Return the exact provider-admission contract for sensitive card stages."""

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("provider_admission_decision")
    if not isinstance(decision, dict):
        return {}
    expected = {
        "contract_version": "v3_provider_admission_decision_v1",
        "provider_admission_status": "admitted",
        "prompt_language_mode": "concise_positive_renderer_direction",
        "safety_sensitive_prompt_normalized": "applied",
        "owner": "remote_v3_llm_brain",
    }
    if not (
        decision.get("required") is True
        and all(decision.get(key) == value for key, value in expected.items())
        and isinstance(decision.get("frozen_binding"), dict)
    ):
        raise BrainProviderAdmissionDecisionMissing(
            "The frozen provider-admission requirement is malformed."
        )
    return expected


def _matches_provider_admission_receipts(
    candidate: Any,
    *,
    expected_count: int,
    expected_requirement: dict[str, str],
) -> bool:
    """Validate admission parity without inspecting or rewriting prompt text."""

    expected_keys = {*expected_requirement, "status"}
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("provider_admission_decision"), dict)
        and set(item["provider_admission_decision"]) == expected_keys
        and all(
            item["provider_admission_decision"].get(key) == value
            for key, value in expected_requirement.items()
        )
        and item["provider_admission_decision"].get("status") in {"approved", "rewritten"}
        for index, item in enumerate(candidate, start=1)
    )


def _required_reference_led_slot_delta_requirement(request: BrainRunRequest) -> dict[str, str]:
    """Return the exact Doc186 slot-delta contract when required."""

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    decision = context.get("reference_led_slot_delta_decision")
    if not isinstance(decision, dict):
        return {}
    expected = {
        "contract_version": "v3_reference_led_slot_delta_decision_v1",
        "materialization_mode": "reference_led_slot_delta",
        "stable_identity_source": "approved_character_card_reference",
        "prompt_scope": "slot_delta_only",
        "safety_sensitive_repetition_policy": "avoid_repeating_stable_person_biology",
        "slot_delta_type": str(decision.get("slot_delta_type") or "").strip(),
        "owner": "remote_v3_llm_brain",
    }
    if not (
        decision.get("required") is True
        and expected["slot_delta_type"] in {"view_angle", "expression", "body_pose"}
        and all(decision.get(key) == value for key, value in expected.items())
        and isinstance(decision.get("frozen_binding"), dict)
    ):
        raise BrainProviderAdmissionDecisionMissing(
            "The frozen reference-led slot-delta requirement is malformed."
        )
    return expected


def _matches_reference_led_slot_delta_receipts(
    candidate: Any,
    *,
    expected_count: int,
    expected_requirement: dict[str, str],
) -> bool:
    """Validate Doc186 slot-delta parity without inspecting prompt prose."""

    expected_keys = {*expected_requirement, "status"}
    if not isinstance(candidate, list) or len(candidate) != expected_count:
        return False
    return all(
        isinstance(item, dict)
        and int(item.get("output_index") or 0) == index
        and isinstance(item.get("reference_led_slot_delta_decision"), dict)
        and set(item["reference_led_slot_delta_decision"]) == expected_keys
        and all(
            item["reference_led_slot_delta_decision"].get(key) == value
            for key, value in expected_requirement.items()
        )
        and item["reference_led_slot_delta_decision"].get("status") in {"approved", "rewritten"}
        for index, item in enumerate(candidate, start=1)
    )


def _character_card_stage_prompt_scope_violations(
    candidate: Any,
    *,
    request: BrainRunRequest,
) -> list[str]:
    """Reject obvious Character Card stage/slot mismatches without recipes."""

    metadata = request.metadata if isinstance(request.metadata, dict) else {}
    context = metadata.get("canonical_prompt_context")
    context = context if isinstance(context, dict) else {}
    target = context.get("character_card_slot_delta_target")
    if not isinstance(target, dict):
        return []
    stage = str(target.get("stage") or "").strip()
    slot_key = str(target.get("slot_key") or "").strip()
    if stage == "body_silhouette" and slot_key.startswith("body."):
        if not isinstance(candidate, list):
            return []
        violations: list[str] = []
        for index, item in enumerate(candidate, start=1):
            if not isinstance(item, dict):
                continue
            prompt = str(item.get("prompt") or "").strip()
            if prompt and body_silhouette_mcp_materialization_prompt_findings(prompt):
                violations.append(f"output_{index}:character_card_body_mcp_forbidden_channels")
        return violations
    if stage != "expression_set" or not slot_key.startswith("expression."):
        return []
    expression = str(target.get("expression") or slot_key.split(".", 1)[1]).strip()
    expression_terms = {
        "laugh": ("laugh", "laughing", "amused", "delighted", "joyful"),
        "smile": ("smile", "smiling", "happy", "joyful", "cheerful"),
        "anger": ("angry", "anger", "annoyed", "serious", "stern", "upset", "frown"),
        "sad": ("sad", "sadness", "pensive", "downcast", "melancholy", "somber", "unhappy"),
    }.get(expression)
    if not expression_terms:
        return []
    if not isinstance(candidate, list):
        return []
    violations: list[str] = []
    for index, item in enumerate(candidate, start=1):
        if not isinstance(item, dict):
            continue
        prompt = str(item.get("prompt") or "").strip().lower()
        if not prompt or not any(term in prompt for term in expression_terms):
            violations.append(f"output_{index}:character_card_expression_slot_prompt_mismatch")
    return violations


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


def _visual_task_profile_shape_validation_audit(candidate: Any) -> dict[str, Any]:
    if not isinstance(candidate, dict):
        return _section_validation_audit("visual_task_profile", "visual_task_profile", "dict_type")
    if not _has_remote_rendering_intent(candidate):
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.rendering_intent",
            "missing",
        )
    required_profile_fields = (
        "developmental_age_intent",
        "reference_channel_ownership_intent",
        "subject_entities",
        "visual_intent_tags",
        "unknown_requirements",
        "confidence",
        "evidence",
    )
    for field in required_profile_fields:
        if field not in candidate:
            return _section_validation_audit("visual_task_profile", f"visual_task_profile.{field}", "missing")
    for field in ("subject_entities", "evidence", "visual_intent_tags", "unknown_requirements"):
        if not isinstance(candidate.get(field), list):
            return _section_validation_audit("visual_task_profile", f"visual_task_profile.{field}", "list_type")
    confidence = candidate.get("confidence")
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0.0 <= confidence <= 1.0:
        return _section_validation_audit("visual_task_profile", "visual_task_profile.confidence", "float_type")
    if candidate.get("developmental_age_intent") not in {
        "current_request_assigns_stage",
        "preserve_reference_stage",
        "not_applicable",
        "ambiguous",
    }:
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.developmental_age_intent",
            "literal_error",
        )
    reference_ownership = candidate.get("reference_channel_ownership_intent")
    if not isinstance(reference_ownership, dict):
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent",
            "dict_type",
        )
    required = (
        "applicability",
        "decision_owner",
        "reference_owned_channels",
        "current_request_owned_channels",
        "evidence_ids",
        "confidence",
    )
    for field in required:
        if field not in reference_ownership:
            return _section_validation_audit(
                "visual_task_profile",
                f"visual_task_profile.reference_channel_ownership_intent.{field}",
                "missing",
            )
    if reference_ownership.get("decision_owner") != "remote_brain":
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent.decision_owner",
            "literal_error",
        )
    if reference_ownership.get("applicability") not in {"applicable", "not_applicable", "ambiguous"}:
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent.applicability",
            "literal_error",
        )
    for field in ("reference_owned_channels", "current_request_owned_channels", "evidence_ids"):
        if not isinstance(reference_ownership.get(field), list):
            return _section_validation_audit(
                "visual_task_profile",
                f"visual_task_profile.reference_channel_ownership_intent.{field}",
                "list_type",
            )
    channels = [
        *reference_ownership.get("reference_owned_channels", []),
        *reference_ownership.get("current_request_owned_channels", []),
    ]
    if not all(isinstance(item, str) and item.strip() for item in channels):
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent.reference_owned_channels.item",
            "string_type",
        )
    if any(channel not in REFERENCE_CHANNEL_IDS for channel in channels):
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent.reference_owned_channels.item",
            "literal_error",
        )
    if set(reference_ownership.get("reference_owned_channels", [])) & set(
        reference_ownership.get("current_request_owned_channels", [])
    ):
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent.reference_owned_channels",
            "value_error",
        )
    reference_confidence = reference_ownership.get("confidence")
    if (
        not isinstance(reference_confidence, (int, float))
        or isinstance(reference_confidence, bool)
        or not 0.0 <= reference_confidence <= 1.0
    ):
        return _section_validation_audit(
            "visual_task_profile",
            "visual_task_profile.reference_channel_ownership_intent.confidence",
            "float_type",
        )
    for entity in candidate.get("subject_entities", []):
        if not isinstance(entity, dict):
            return _section_validation_audit(
                "visual_task_profile",
                "visual_task_profile.subject_entities.item",
                "dict_type",
            )
        if not isinstance(entity.get("confidence"), (int, float)) or isinstance(entity.get("confidence"), bool):
            return _section_validation_audit(
                "visual_task_profile",
                "visual_task_profile.subject_entities.item.confidence",
                "float_type",
            )
    for item in [*candidate.get("visual_intent_tags", []), *candidate.get("unknown_requirements", [])]:
        if not isinstance(item, str) or not item.strip():
            return _section_validation_audit("visual_task_profile", "visual_task_profile.visual_intent_tags.item", "string_type")
    return _section_validation_audit("visual_task_profile", "visual_task_profile", "value_error")


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

    payload, accepted, _ = _merge_validated_section_with_audit(payload, key, candidate)
    return payload, accepted


def _merge_validated_section_with_audit(
    payload: dict[str, Any],
    key: str,
    candidate: Any,
) -> tuple[dict[str, Any], bool, dict[str, Any]]:
    """Accept one remote section and return public-safe validation metadata on failure."""

    probe = dict(payload)
    probe[key] = candidate
    try:
        validated = BrainRunResult.model_validate(probe).model_dump(mode="json")
    except ValidationError as exc:
        return payload, False, _safe_validation_error_audit(exc, section=key)
    payload[key] = validated[key]
    return payload, True, {}


def _safe_validation_error_audit(exc: ValidationError, *, section: str) -> dict[str, Any]:
    paths: list[str] = []
    types: list[str] = []
    for error in exc.errors():
        path = _safe_validation_path(error.get("loc"), section=section)
        if path:
            paths.append(path)
            types.append(_safe_validation_type(error.get("type")))
    paths = list(dict.fromkeys(paths))[:8]
    types = list(dict.fromkeys(types))[:8]
    return {
        "validation_error_count": len(paths),
        "validation_error_paths": paths,
        "validation_error_types": types,
    }


def _section_validation_audit(section: str, path: str, error_type: str) -> dict[str, Any]:
    safe_path = _safe_validation_path(path.split("."), section=section)
    safe_type = _safe_validation_type(error_type)
    return {
        "validation_error_count": 1 if safe_path else 0,
        "validation_error_paths": [safe_path] if safe_path else [],
        "validation_error_types": [safe_type] if safe_path else [],
    }


def _remote_contract_validation_audit_payload(
    sections: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    safe_sections: dict[str, dict[str, Any]] = {}
    for section, audit in sections.items():
        section_key = str(section or "").strip()
        if section_key not in {"image_set_plan", "visual_task_profile", "capability_activation_intent"}:
            continue
        if not isinstance(audit, dict):
            continue
        paths = audit.get("validation_error_paths")
        types = audit.get("validation_error_types")
        safe_paths = (
            [
                _safe_validation_path(str(item).split("."), section=section_key)
                for item in paths
                if str(item).strip()
            ][:8]
            if isinstance(paths, list)
            else []
        )
        safe_types = (
            [_safe_validation_type(item) for item in types if str(item).strip()][:8]
            if isinstance(types, list)
            else []
        )
        safe_paths = [item for item in safe_paths if item]
        if not safe_paths and not safe_types:
            continue
        count = audit.get("validation_error_count")
        safe_sections[section_key] = {
            "validation_error_count": count if isinstance(count, int) else len(safe_paths),
            "validation_error_paths": list(dict.fromkeys(safe_paths))[:8],
            "validation_error_types": list(dict.fromkeys(safe_types))[:8],
        }
    return {
        "schema_version": "v3_remote_contract_validation_audit_v1",
        "sections": safe_sections,
    }


def _safe_validation_path(loc: Any, *, section: str) -> str:
    if not isinstance(loc, (list, tuple)):
        return ""
    parts = [str(item).strip() for item in loc if str(item).strip()]
    if not parts:
        return ""
    if parts[0] != section:
        parts = [section, *parts]
    if parts[0] not in {"image_set_plan", "visual_task_profile", "capability_activation_intent"}:
        return ""
    safe_parts: list[str] = []
    for part in parts:
        safe_parts.append("item" if part.isdigit() else part)
    path = ".".join(safe_parts)
    allowed_prefixes = (
        "image_set_plan",
        "image_set_plan.image_count",
        "image_set_plan.shot_plan",
        "image_set_plan.evidence_dimensions_by_output",
        "image_set_plan.evidence_dimensions_by_output.item",
        "image_set_plan.evidence_dimensions_by_output.item.output_index",
        "image_set_plan.evidence_dimensions_by_output.item.evidence_dimensions",
        "image_set_plan.evidence_dimensions_by_output.item.evidence_dimensions.item",
        "image_set_plan.evidence_dimensions_by_output.item.professional_body_proportion_requirement",
        "image_set_plan.evidence_dimensions_by_output.item.professional_body_view_kind",
        "image_set_plan.evidence_dimensions_by_output.item.product_truth_selection_role",
        "image_set_plan.evidence_dimensions_by_output.item.selected_product_truth_asset_ids",
        "image_set_plan.evidence_dimensions_by_output.item.selected_product_truth_asset_ids.item",
        "image_set_plan.evidence_dimensions_by_output.item.professional_ecommerce_pose_role",
        "image_set_plan.evidence_dimensions_by_output.item.standing_pose_requirements",
        "image_set_plan.evidence_dimensions_by_output.item.standing_pose_requirements.item",
        "image_set_plan.evidence_dimensions_by_output.item.standing_presentation_requirements",
        "image_set_plan.evidence_dimensions_by_output.item.standing_presentation_requirements.item",
        "image_set_plan.composition_rules",
        "image_set_plan.quality_bar",
        "image_set_plan.size",
        "image_set_plan.set_goal",
        "visual_task_profile",
        "visual_task_profile.rendering_intent",
        "visual_task_profile.rendering_intent.rendering_mode",
        "visual_task_profile.rendering_intent.stylization_scope",
        "visual_task_profile.rendering_intent.decision_owner",
        "visual_task_profile.developmental_age_intent",
        "visual_task_profile.reference_channel_ownership_intent",
        "visual_task_profile.reference_channel_ownership_intent.applicability",
        "visual_task_profile.reference_channel_ownership_intent.decision_owner",
        "visual_task_profile.reference_channel_ownership_intent.reference_owned_channels",
        "visual_task_profile.reference_channel_ownership_intent.reference_owned_channels.item",
        "visual_task_profile.reference_channel_ownership_intent.current_request_owned_channels",
        "visual_task_profile.reference_channel_ownership_intent.current_request_owned_channels.item",
        "visual_task_profile.reference_channel_ownership_intent.evidence_ids",
        "visual_task_profile.reference_channel_ownership_intent.evidence_ids.item",
        "visual_task_profile.reference_channel_ownership_intent.confidence",
        "visual_task_profile.subject_entities",
        "visual_task_profile.subject_entities.item",
        "visual_task_profile.subject_entities.item.entity_id",
        "visual_task_profile.subject_entities.item.entity_type",
        "visual_task_profile.subject_entities.item.role",
        "visual_task_profile.subject_entities.item.source_asset_ids",
        "visual_task_profile.subject_entities.item.source_asset_ids.item",
        "visual_task_profile.subject_entities.item.visible_in_target",
        "visual_task_profile.subject_entities.item.preservation_level",
        "visual_task_profile.subject_entities.item.confidence",
        "visual_task_profile.subject_entities.item.attributes",
        "visual_task_profile.visual_intent_tags",
        "visual_task_profile.visual_intent_tags.item",
        "visual_task_profile.unknown_requirements",
        "visual_task_profile.unknown_requirements.item",
        "visual_task_profile.confidence",
        "visual_task_profile.evidence",
        "visual_task_profile.evidence.item",
        "visual_task_profile.evidence.item.evidence_id",
        "visual_task_profile.evidence.item.evidence_type",
        "visual_task_profile.evidence.item.source",
        "visual_task_profile.evidence.item.confidence",
        "visual_task_profile.evidence.item.metadata",
        "capability_activation_intent",
    )
    if path in allowed_prefixes or any(path.startswith(prefix + ".") for prefix in allowed_prefixes):
        return path
    return parts[0]


def _safe_validation_type(value: Any) -> str:
    token = str(value or "unknown").strip().lower()
    allowed = []
    for char in token[:64]:
        allowed.append(char if char.isalnum() or char in {"_", "-", "."} else "_")
    return "".join(allowed).strip("_") or "unknown"


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
