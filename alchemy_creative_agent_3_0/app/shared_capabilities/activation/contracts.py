"""Contracts for evidence-driven V3 capability activation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from ...creative_core.rules import stable_id
from ...schemas.models import V3BaseModel


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class ActivationEvidence(V3BaseModel):
    evidence_id: str
    evidence_type: str
    source: str
    value: Any = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class VisualSubjectEntity(V3BaseModel):
    entity_id: str
    entity_type: str
    role: str = "subject"
    source_asset_ids: list[str] = Field(default_factory=list)
    visible_in_target: bool = True
    preservation_level: str = "none"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attributes: dict[str, Any] = Field(default_factory=dict)


class PreservationTarget(V3BaseModel):
    target_id: str
    target_type: str
    source_entity_id: str | None = None
    source_asset_ids: list[str] = Field(default_factory=list)
    level: str = "balanced"
    allowed_changes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class VisualTaskProfile(V3BaseModel):
    profile_id: str
    project_id: str | None = None
    job_id: str
    template_id: str
    scenario_id: str
    output_medium: str = "image"
    subject_entities: list[VisualSubjectEntity] = Field(default_factory=list)
    preservation_targets: list[PreservationTarget] = Field(default_factory=list)
    allowed_changes: list[str] = Field(default_factory=list)
    visual_intent_tags: list[str] = Field(default_factory=list)
    commercial_goal_tags: list[str] = Field(default_factory=list)
    requested_deliverable_roles: list[str] = Field(default_factory=list)
    explicit_user_controls: dict[str, Any] = Field(default_factory=dict)
    unknown_requirements: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[ActivationEvidence] = Field(default_factory=list)

    @model_validator(mode="after")
    def unique_ids(self) -> "VisualTaskProfile":
        _ensure_unique([item.entity_id for item in self.subject_entities], "entity_id")
        _ensure_unique([item.evidence_id for item in self.evidence], "evidence_id")
        return self


class RequestedCapability(V3BaseModel):
    capability_id: str
    activation_mode: str = "recommended"
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    requested_profile: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("activation_mode")
    @classmethod
    def valid_activation_mode(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if cleaned not in {"required", "recommended", "optional", "forbidden"}:
            raise ValueError("unsupported activation_mode")
        return cleaned


class RejectedCapability(V3BaseModel):
    capability_id: str
    reason_code: str
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class CapabilityActivationIntent(V3BaseModel):
    intent_id: str
    task_profile_id: str
    requested_capabilities: list[RequestedCapability] = Field(default_factory=list)
    rejected_capabilities: list[RejectedCapability] = Field(default_factory=list)
    unresolved_signals: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def unique_capability_requests(self) -> "CapabilityActivationIntent":
        _ensure_unique([item.capability_id for item in self.requested_capabilities], "requested capability_id")
        return self


class CapabilityCost(V3BaseModel):
    latency: int = Field(default=1, ge=0)
    token: int = Field(default=1, ge=0)
    provider_calls: int = Field(default=0, ge=0)


class VisualCapabilityManifest(V3BaseModel):
    capability_id: str
    version: str = "v1"
    display_name: str
    owner_layer: str = "shared_capabilities"
    status: str = "enabled"
    supported_entity_types: list[str] = Field(default_factory=list)
    supported_output_media: list[str] = Field(default_factory=lambda: ["image"])
    activation_evidence_schema: list[str] = Field(default_factory=list)
    minimum_activation_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    dependencies: list[str] = Field(default_factory=list)
    optional_dependencies: list[str] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    compatible_templates: list[str] = Field(default_factory=list)
    forbidden_templates: list[str] = Field(default_factory=list)
    supported_profiles: list[str] = Field(default_factory=lambda: ["balanced"])
    contribution_stages: list[str] = Field(default_factory=list)
    estimated_cost: CapabilityCost = Field(default_factory=CapabilityCost)
    fallback_behavior: str = "skip_optional"
    audit_tags: list[str] = Field(default_factory=list)


class TemplateCapabilityBinding(V3BaseModel):
    capability_id: str
    profile: str | None = None
    minimum_confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    config: dict[str, Any] = Field(default_factory=dict)


class TemplateCapabilityPolicy(V3BaseModel):
    policy_id: str = "compatibility_default"
    policy_version: str = "v1"
    required_capabilities: list[TemplateCapabilityBinding] = Field(default_factory=list)
    recommended_capabilities: list[TemplateCapabilityBinding] = Field(default_factory=list)
    optional_capabilities: list[TemplateCapabilityBinding] = Field(default_factory=list)
    forbidden_capabilities: list[str] = Field(default_factory=list)
    profile_overrides: dict[str, str] = Field(default_factory=dict)
    activation_threshold_overrides: dict[str, float] = Field(default_factory=dict)
    deliverable_role_owner: str = "general_template"
    review_threshold_profile: str = "balanced"
    brain_activation_enabled: bool = True
    requires_remote_creative_brain: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def unique_bindings(self) -> "TemplateCapabilityPolicy":
        ids = [
            item.capability_id
            for group in (self.required_capabilities, self.recommended_capabilities, self.optional_capabilities)
            for item in group
        ]
        _ensure_unique(ids, "template capability binding")
        return self


class ActivatedCapability(V3BaseModel):
    capability_id: str
    version: str
    selected_profile: str = "balanced"
    activation_mode: str = "recommended"
    reason_codes: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    template_configuration: dict[str, Any] = Field(default_factory=dict)
    dependency_source: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class InactiveCapability(V3BaseModel):
    capability_id: str
    reason_code: str
    considered_profile: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)


class CapabilityConflictDecision(V3BaseModel):
    capability_ids: list[str]
    winner: str | None = None
    reason_code: str


class CapabilityBudgetDecision(V3BaseModel):
    capability_id: str
    included: bool
    reason_code: str
    cost: CapabilityCost = Field(default_factory=CapabilityCost)


class CapabilityActivationPlan(V3BaseModel):
    plan_id: str
    fingerprint: str
    project_id: str | None = None
    job_id: str
    task_profile_id: str
    template_id: str
    scenario_id: str
    base_capabilities: list[ActivatedCapability] = Field(default_factory=list)
    active_capabilities: list[ActivatedCapability] = Field(default_factory=list)
    inactive_capabilities: list[InactiveCapability] = Field(default_factory=list)
    dependency_order: list[str] = Field(default_factory=list)
    conflict_decisions: list[CapabilityConflictDecision] = Field(default_factory=list)
    budget_decisions: list[CapabilityBudgetDecision] = Field(default_factory=list)
    fallback_used: bool = False
    plan_version: str = "v1"
    catalog_version: str = "v1"
    activation_mode: str = "shadow"
    created_at: str = Field(default_factory=utc_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def active_ids_are_unique(self) -> "CapabilityActivationPlan":
        active_ids = [item.capability_id for item in self.active_capabilities]
        _ensure_unique(active_ids, "active capability_id")
        if self.dependency_order and set(self.dependency_order) != set(active_ids):
            raise ValueError("dependency_order must contain every active capability exactly once")
        return self

    def is_active(self, capability_id: str) -> bool:
        return any(item.capability_id == capability_id for item in self.active_capabilities)

    def active(self, capability_id: str) -> ActivatedCapability | None:
        return next((item for item in self.active_capabilities if item.capability_id == capability_id), None)

    def summary(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "plan_version": self.plan_version,
            "catalog_version": self.catalog_version,
            "active_capability_ids": list(self.dependency_order),
            "activation_mode": self.activation_mode,
        }


class CapabilityExecutionEnvelope(V3BaseModel):
    """Immutable, auditable execution input for an enforced capability plan.

    This deliberately sits between active capability executors and every
    downstream consumer.  A provider, reviewer, or retry path must never
    rediscover instructions from the legacy visual-cluster metadata once this
    envelope exists.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    envelope_id: str
    execution_fingerprint: str
    job_id: str
    template_id: str
    scenario_id: str
    activation_mode: str
    activation_plan: CapabilityActivationPlan
    normalized_job_intent: "NormalizedV3JobIntent"
    template_deliverable_plan: "TemplateDeliverablePlan"
    active_capability_ids: list[str] = Field(default_factory=list)
    composed_visual_contribution: "ComposedVisualContribution"
    provider_projection: dict[str, Any] = Field(default_factory=dict)
    review_contracts: list[dict[str, Any]] = Field(default_factory=list)
    retry_contracts: list[dict[str, Any]] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def execution_truth_is_frozen(self) -> "CapabilityExecutionEnvelope":
        if self.activation_mode not in {"enforced", "shadow", "legacy"}:
            raise ValueError("unsupported capability execution mode")
        if self.activation_mode != self.activation_plan.activation_mode:
            raise ValueError("capability_execution_mode_mismatch")
        if self.template_id != self.activation_plan.template_id:
            raise ValueError("execution envelope template does not match activation plan")
        if self.scenario_id != self.activation_plan.scenario_id:
            raise ValueError("execution envelope scenario does not match activation plan")
        if self.active_capability_ids != self.activation_plan.dependency_order:
            raise ValueError("execution envelope active capabilities do not match activation plan")
        if self.composed_visual_contribution.activation_plan_id != self.activation_plan.plan_id:
            raise ValueError("execution envelope contribution does not match activation plan")
        if self.composed_visual_contribution.active_capability_ids != self.active_capability_ids:
            raise ValueError("execution envelope contribution active capabilities do not match activation plan")
        if self.template_id != self.normalized_job_intent.template_id:
            raise ValueError("execution envelope template does not match normalized intent")
        if self.scenario_id != self.normalized_job_intent.scenario_id:
            raise ValueError("execution envelope scenario does not match normalized intent")
        if self.template_id != self.template_deliverable_plan.template_id:
            raise ValueError("execution envelope template does not match deliverable plan")
        if self.scenario_id != self.template_deliverable_plan.scenario_id:
            raise ValueError("execution envelope scenario does not match deliverable plan")
        if self.normalized_job_intent.effective_image_count != self.template_deliverable_plan.effective_image_count:
            raise ValueError("execution envelope deliverable count does not match normalized intent")
        return self

    def safe_metadata(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class NormalizedV3JobIntent(V3BaseModel):
    """The one canonical image request shape shared by every V3 entry path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    intent_id: str
    template_id: str
    scenario_id: str
    protected_user_intent: str
    requested_image_count: int = Field(ge=1)
    effective_image_count: int = Field(ge=1)
    declared_image_count_limit: int | None = Field(default=None, ge=1)
    count_limit_source: str = "unspecified"
    requested_image_size: str | None = None
    effective_image_size: str | None = None
    text_policy: str = "provider_native_only"
    provenance: list[dict[str, Any]] = Field(default_factory=list)


class TemplateDeliverable(V3BaseModel):
    """Opaque output binding, never a static camera/scene recipe."""

    deliverable_id: str
    output_index: int = Field(ge=1)
    image_intent: str
    source: str
    factual_acceptance: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemplateDeliverablePlan(V3BaseModel):
    """Template-owned binding of requested outputs to Brain-approved intents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_id: str
    template_id: str
    scenario_id: str
    owner: str
    creative_direction_owner: str
    requested_image_count: int = Field(ge=1)
    effective_image_count: int = Field(ge=1)
    deliverables: list[TemplateDeliverable] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def output_binding_matches_count(self) -> "TemplateDeliverablePlan":
        if self.requested_image_count != self.effective_image_count:
            raise ValueError("template deliverable plan may not silently truncate requested outputs")
        if len(self.deliverables) != self.effective_image_count:
            raise ValueError("template deliverable plan must bind every effective output")
        expected = list(range(1, self.effective_image_count + 1))
        if [item.output_index for item in self.deliverables] != expected:
            raise ValueError("template deliverable outputs must be ordered and contiguous")
        return self


class CapabilityContribution(V3BaseModel):
    capability_id: str
    capability_version: str
    activation_plan_id: str
    contribution_version: str = "v1"
    facts: dict[str, Any] = Field(default_factory=dict)
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    provider_input_requirements: list[dict[str, Any]] = Field(default_factory=list)
    review_contract: dict[str, Any] = Field(default_factory=dict)
    retry_contract: dict[str, Any] = Field(default_factory=dict)
    project_memory_proposal: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] = Field(default_factory=list)
    stages: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComposedVisualContribution(V3BaseModel):
    activation_plan_id: str
    contribution_version: str = "v1"
    prompt_additions: list[str] = Field(default_factory=list)
    negative_additions: list[str] = Field(default_factory=list)
    provider_input_requirements: list[dict[str, Any]] = Field(default_factory=list)
    review_contracts: list[dict[str, Any]] = Field(default_factory=list)
    retry_contracts: list[dict[str, Any]] = Field(default_factory=list)
    memory_proposals: list[dict[str, Any]] = Field(default_factory=list)
    active_capability_ids: list[str] = Field(default_factory=list)
    provenance: list[dict[str, Any]] = Field(default_factory=list)


class CapabilityCatalogEntry(V3BaseModel):
    manifest: VisualCapabilityManifest
    executor_ref: str


class CapabilityCatalogSnapshot(V3BaseModel):
    catalog_version: str
    template_id: str
    scenario_id: str
    entries: list[CapabilityCatalogEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now_iso)

    def manifest(self, capability_id: str) -> VisualCapabilityManifest | None:
        entry = next((item for item in self.entries if item.manifest.capability_id == capability_id), None)
        return entry.manifest if entry else None

    def safe_metadata(self) -> dict[str, Any]:
        return {
            "catalog_version": self.catalog_version,
            "capabilities": [
                {
                    "capability_id": item.manifest.capability_id,
                    "version": item.manifest.version,
                    "supported_entity_types": item.manifest.supported_entity_types,
                    "supported_profiles": item.manifest.supported_profiles,
                    "minimum_activation_confidence": item.manifest.minimum_activation_confidence,
                }
                for item in self.entries
            ],
        }


class CapabilityPlanAmendment(V3BaseModel):
    amendment_id: str
    original_plan_id: str
    amended_plan_id: str
    evidence_ids: list[str] = Field(default_factory=list)
    reason_code: str
    amendment_index: int = Field(default=1, ge=1, le=1)
    created_at: str = Field(default_factory=utc_now_iso)


class CapabilityGraphAudit(V3BaseModel):
    valid: bool = True
    dependency_order: list[str] = Field(default_factory=list)
    missing_dependencies: list[str] = Field(default_factory=list)
    cycles: list[list[str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def activation_fingerprint(*parts: Any) -> str:
    return stable_id("capability_activation", *parts)


def _ensure_unique(values: list[str], field_name: str) -> None:
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    if len(cleaned) != len(set(cleaned)):
        raise ValueError(f"duplicate {field_name}")
