"""Historical decode contracts for retired deterministic text delivery.

They exist solely so archived records can be read and receive a
``provider_native_required`` result.  New work must pass approved literal copy
to the remote Brain/provider and must not create these plans.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from ...creative_core.rules import stable_id
from ...schemas.models import V3BaseModel


TextPolicy = Literal["forbidden", "optional", "required"]
ClaimReviewState = Literal["approved", "requires_review", "blocked"]


class NormalizedSafeArea(V3BaseModel):
    """Archived geometry only; it must never drive new-image composition."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)
    anchor: Literal["top_left", "top_center", "center", "bottom_left", "bottom_center"] = "top_center"

    @model_validator(mode="after")
    def remains_inside_canvas(self) -> "NormalizedSafeArea":
        if self.x + self.w > 1.000001 or self.y + self.h > 1.000001:
            raise ValueError("normalized safe area must remain inside the canvas")
        return self

    def as_pixel_box(self, width: int, height: int) -> dict[str, int]:
        return {
            "x": round(self.x * width),
            "y": round(self.y * height),
            "w": max(1, round(self.w * width)),
            "h": max(1, round(self.h * height)),
        }


class CopyRenderSourceLineage(V3BaseModel):
    """The immutable source chain that binds copy work to a frozen V3 plan."""

    capability_activation_plan_id: str | None = None
    source_job_id: str | None = None
    source_asset_id: str | None = None
    source_output_id: str | None = None
    source_reference: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("capability_activation_plan_id")
    @classmethod
    def clean_activation_plan_id(cls, value: str | None) -> str | None:
        cleaned = value.strip() if isinstance(value, str) else ""
        return cleaned or None


class CopyRenderPlan(V3BaseModel):
    """Archived deterministic-plan shape, accepted only for read compatibility."""

    schema_version: str = "v3_copy_render_plan_v1"
    plan_id: str = ""
    expected_copy: str | None = None
    locale: str | None = None
    text_policy: TextPolicy = "optional"
    normalized_safe_area: NormalizedSafeArea
    layout_priority: str = "supporting"
    claim_review_state: ClaimReviewState = "approved"
    source_lineage: CopyRenderSourceLineage
    foreground_color: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("expected_copy")
    @classmethod
    def clean_copy(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) and value.strip() else None

    @field_validator("locale")
    @classmethod
    def clean_locale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or " " in cleaned:
            raise ValueError("locale must be a BCP-47-style tag")
        return cleaned

    @field_validator("layout_priority")
    @classmethod
    def clean_priority(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("layout_priority is required")
        return cleaned

    @model_validator(mode="after")
    def assign_stable_plan_id(self) -> "CopyRenderPlan":
        if not self.plan_id:
            self.plan_id = stable_id(
                "copy_render_plan",
                self.expected_copy or "",
                self.locale or "",
                self.text_policy,
                self.normalized_safe_area.model_dump_json(),
                self.layout_priority,
                self.claim_review_state,
                self.source_lineage.capability_activation_plan_id or "unbound",
                self.source_lineage.source_asset_id or "",
                self.source_lineage.source_output_id or "",
            )
        return self

    def bind_to_frozen_plan(self, activation_plan_id: str) -> "CopyRenderPlan":
        """Preserve historical binding data; this does not activate delivery.

        Templates may supply internal copy intent before the activation planner
        creates an ID.  The Product API binds it once, before generation; the
        runtime subsequently accepts only this exact ID.
        """

        cleaned = str(activation_plan_id or "").strip()
        if not cleaned:
            raise ValueError("activation_plan_id is required to bind CopyRenderPlan")
        if self.source_lineage.capability_activation_plan_id and self.source_lineage.capability_activation_plan_id != cleaned:
            raise ValueError("CopyRenderPlan is already bound to another frozen plan")
        payload = self.model_dump(mode="json")
        payload["source_lineage"] = {
            **dict(payload.get("source_lineage") or {}),
            "capability_activation_plan_id": cleaned,
        }
        payload["plan_id"] = ""
        return CopyRenderPlan.model_validate(payload)


class CopyRenderPlanBatch(V3BaseModel):
    """An ordered, independently bound set of scenario-neutral copy plans.

    This contract deliberately uses only source asset/output lineage.  It has
    no template, role, platform, or marketplace vocabulary, so a template
    cannot turn its own deliverable map into shared-runtime semantics.
    """

    schema_version: str = "v3_copy_render_plan_batch_v1"
    batch_id: str = ""
    plans: list[CopyRenderPlan] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_independent_lineage(self) -> "CopyRenderPlanBatch":
        plan_ids = [plan.plan_id for plan in self.plans]
        if len(set(plan_ids)) != len(plan_ids):
            raise ValueError("CopyRenderPlanBatch plans must have unique plan_id values")
        lineage_keys: list[str] = []
        for plan in self.plans:
            lineage = plan.source_lineage
            if lineage.source_output_id:
                lineage_key = f"output:{lineage.source_output_id}"
            elif lineage.source_asset_id:
                lineage_key = f"asset:{lineage.source_asset_id}"
            else:
                raise ValueError("CopyRenderPlanBatch plans require source_asset_id or source_output_id lineage")
            lineage_keys.append(lineage_key)
        if len(set(lineage_keys)) != len(lineage_keys):
            raise ValueError("CopyRenderPlanBatch plans must have unique source asset/output lineage")
        if not self.batch_id:
            self.batch_id = stable_id("copy_render_plan_batch", *plan_ids)
        return self

    def bind_to_frozen_plan(self, activation_plan_id: str) -> "CopyRenderPlanBatch":
        payload = self.model_dump(mode="json")
        payload["plans"] = [plan.bind_to_frozen_plan(activation_plan_id).model_dump(mode="json") for plan in self.plans]
        payload["batch_id"] = ""
        return CopyRenderPlanBatch.model_validate(payload)


class TextPixelDeliveryAttempt(V3BaseModel):
    """One append-only composition, review, or recovery record."""

    attempt_id: str
    attempt_index: int = Field(ge=0)
    stage: Literal["eligibility", "composition", "review", "deterministic_repair", "generation_retry_signal"]
    status: str
    source_output_id: str | None = None
    derived_output_id: str | None = None
    issue_codes: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class TextPixelDelivery(V3BaseModel):
    """Auditable result exposed to a template without exposing renderer knobs."""

    schema_version: str = "v3_text_pixel_delivery_v1"
    delivery_id: str
    copy_render_plan_id: str | None = None
    status: Literal[
        "not_requested",
        "planned_only",
        "composed_pending_review",
        "passed",
        "requires_copy_correction",
        "repair_exhausted",
        "provider_native_required",
        "blocked",
    ] = "not_requested"
    rendered: bool = False
    review_passed: bool = False
    text_policy: TextPolicy | None = None
    locale: str | None = None
    source_output_id: str | None = None
    current_output_id: str | None = None
    artifact_lineage: dict[str, Any] = Field(default_factory=dict)
    recovery: dict[str, Any] = Field(default_factory=dict)
    attempts: list[TextPixelDeliveryAttempt] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    user_visible_summary: list[str] = Field(default_factory=list)
    gate_c_eligible: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class TextPixelDeliveryBatch(V3BaseModel):
    """Append-only delivery results for an independently bound plan batch."""

    schema_version: str = "v3_text_pixel_delivery_batch_v1"
    batch_id: str
    deliveries: list[TextPixelDelivery] = Field(default_factory=list)
    source_asset_ids_by_plan: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_deliveries(self) -> "TextPixelDeliveryBatch":
        plan_ids = [delivery.copy_render_plan_id for delivery in self.deliveries if delivery.copy_render_plan_id]
        if len(set(plan_ids)) != len(plan_ids):
            raise ValueError("TextPixelDeliveryBatch deliveries must have unique copy_render_plan_id values")
        if set(self.source_asset_ids_by_plan).difference(plan_ids):
            raise ValueError("TextPixelDeliveryBatch source asset mapping must reference included plans")
        return self

    def delivery_for_source_asset(self, asset_id: str) -> TextPixelDelivery | None:
        for plan_id, mapped_asset_id in self.source_asset_ids_by_plan.items():
            if mapped_asset_id != asset_id:
                continue
            return next((item for item in self.deliveries if item.copy_render_plan_id == plan_id), None)
        return None
