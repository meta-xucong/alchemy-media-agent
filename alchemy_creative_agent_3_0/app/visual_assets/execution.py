"""Framework-agnostic Professional Mode execution preparation seam.

This adapter is deliberately pre-runtime: it accepts only an explicit
Professional consumer request and typed Brain/shared-evidence reference plans,
then returns a safe evidence packet and planning metadata for a future
ScenarioRuntime integration. It never calls the Brain, Provider, Reviewer,
filesystem, or a Standard Mode fallback.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .authority import (
    ReferenceAdmissionDecision,
    ReferenceAdmissionResult,
    ReferenceChannelPlan,
    ReferenceEvidencePacket,
)
from .consumers import (
    ProfessionalConsumerContext,
    ProfessionalConsumerRequest,
    ProfessionalModeConsumerAdapter,
)
from .runtime_bridge import ProfessionalModeRuntimeBridge


class ProfessionalModeExecutionRequest(V3BaseModel):
    """Internal pre-freeze request; no raw prompt or uploaded file is allowed."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    consumer_request: ProfessionalConsumerRequest
    canonical_prompt_hash: str
    reference_plans: list[ReferenceChannelPlan] = Field(default_factory=list)

    @field_validator("canonical_prompt_hash")
    @classmethod
    def require_prompt_receipt_hash(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Professional Mode requires a canonical Brain prompt hash")
        return value

    @model_validator(mode="after")
    def keep_standard_mode_pristine(self) -> "ProfessionalModeExecutionRequest":
        if self.consumer_request.mode == "standard" and self.reference_plans:
            raise ValueError("Standard Mode cannot receive Professional reference plans")
        return self


class ProfessionalModeExecutionContext(V3BaseModel):
    """Safe context a future runtime may attach before capability-plan freeze."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    template_id: Literal["general_template", "ecommerce_template", "photographer_template"]
    mode: Literal["professional"] = "professional"
    project_id: str
    job_id: str
    consumer_context: ProfessionalConsumerContext
    admission: ReferenceAdmissionResult
    evidence_packet: ReferenceEvidencePacket
    planning_metadata: dict[str, object]


class ProfessionalModePreparationResult(V3BaseModel):
    """Structured result for a caller before it invokes shared runtime code."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    status: Literal["ready", "blocked"]
    context: ProfessionalModeExecutionContext | None = None
    blocked_decisions: list[ReferenceAdmissionDecision] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_result_shape(self) -> "ProfessionalModePreparationResult":
        if self.status == "ready":
            if self.context is None or self.blocked_decisions or self.reason_codes:
                raise ValueError("a ready Professional Mode result must contain only a valid context")
        elif self.context is not None or not (self.blocked_decisions or self.reason_codes):
            raise ValueError("a blocked Professional Mode result must contain safe failure evidence")
        return self


class ProfessionalModeExecutionAdapter:
    """Prepare Professional Mode evidence without owning runtime orchestration."""

    def __init__(self, *, bridge: ProfessionalModeRuntimeBridge | None = None) -> None:
        self.bridge = bridge or ProfessionalModeRuntimeBridge()
        self.consumer_adapter = ProfessionalModeConsumerAdapter()

    def prepare(
        self,
        request: ProfessionalModeExecutionRequest,
    ) -> ProfessionalModePreparationResult | None:
        """Return ``None`` for pristine Standard Mode, otherwise prepare safely."""

        consumer_context = self.consumer_adapter.prepare(request.consumer_request)
        if consumer_context is None:
            return None

        binding = request.consumer_request.binding
        if binding is None:  # defensive guard; the request model already rejects this
            raise ValueError("Professional Mode requires a selected People Asset binding")

        admission = self.bridge.resolve_reference_admissions(binding, request.reference_plans)
        if admission.status != "admitted":
            blocked = [item for item in admission.decisions if item.status == "blocked"]
            reason_codes = list(
                dict.fromkeys(code for decision in blocked for code in decision.reason_codes)
            )
            return ProfessionalModePreparationResult(
                status="blocked",
                blocked_decisions=blocked,
                reason_codes=reason_codes,
            )

        packet = admission.to_evidence_packet()
        self.bridge.validate_reference_evidence_parity(packet)
        metadata = self.bridge.planning_metadata(
            binding,
            canonical_prompt_hash=request.canonical_prompt_hash,
            reference_admissions=admission,
        )
        context = ProfessionalModeExecutionContext(
            template_id=consumer_context.template_id,
            project_id=binding.project_id,
            job_id=binding.job_id,
            consumer_context=consumer_context,
            admission=admission,
            evidence_packet=packet,
            planning_metadata=metadata,
        )
        return ProfessionalModePreparationResult(status="ready", context=context)
