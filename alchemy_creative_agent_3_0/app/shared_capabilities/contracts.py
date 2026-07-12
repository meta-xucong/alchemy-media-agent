"""Contracts for V3 shared capabilities."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from ..schemas.models import V3BaseModel


class AssetRole(StrEnum):
    UNKNOWN_REFERENCE = "unknown_reference"
    PRODUCT_REFERENCE = "product_reference"
    STYLE_REFERENCE = "style_reference"
    LOGO_REFERENCE = "logo_reference"
    FACE_REFERENCE = "face_reference"
    NONHUMAN_IDENTITY_REFERENCE = "nonhuman_identity_reference"
    BACKGROUND_REFERENCE = "background_reference"
    COMPOSITION_REFERENCE = "composition_reference"
    COLOR_REFERENCE = "color_reference"
    NEGATIVE_REFERENCE = "negative_reference"


class CapabilityStatus(StrEnum):
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    SKIPPED = "skipped"


class CapabilityRunStatus(StrEnum):
    COMPLETE = "complete"
    DEGRADED = "degraded"
    FAILED = "failed"


class CapabilityTargetStage(StrEnum):
    INTENT = "intent"
    COMMERCIAL_BRIEF = "commercial_brief"
    CREATIVE_DIRECTION = "creative_direction"
    SERIES_PLAN = "series_plan"
    LAYOUT_PLAN = "layout_plan"
    PROMPT_COMPILATION = "prompt_compilation"
    EVALUATION = "evaluation"
    EXPORT = "export"


class UploadedAssetInfo(V3BaseModel):
    asset_id: str
    role: AssetRole | None = None
    file_path: str | None = None
    uri: str | None = None
    filename: str | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("asset_id")
    @classmethod
    def asset_id_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("asset_id is required")
        return cleaned


class CapabilityWarning(V3BaseModel):
    code: str
    message: str
    severity: str = "warning"
    asset_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityConstraint(V3BaseModel):
    target_stage: CapabilityTargetStage
    constraint_type: str
    strength: str = "soft"
    value: Any
    source: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityInput(V3BaseModel):
    job_id: str
    scenario_id: str
    user_input: str
    campaign: dict[str, Any] = Field(default_factory=dict)
    brand_context: dict[str, Any] = Field(default_factory=dict)
    uploaded_assets: list[UploadedAssetInfo] = Field(default_factory=list)
    product_profile: dict[str, Any] = Field(default_factory=dict)
    prior_results: list["CapabilityResult"] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityResult(V3BaseModel):
    module_id: str
    version: str
    status: CapabilityStatus
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    facts: dict[str, Any] = Field(default_factory=dict)
    constraints: list[CapabilityConstraint] = Field(default_factory=list)
    warnings: list[CapabilityWarning] = Field(default_factory=list)
    audit_trail: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status in {CapabilityStatus.SUCCESS, CapabilityStatus.WARNING}


class CapabilityRunResult(V3BaseModel):
    status: CapabilityRunStatus
    results: list[CapabilityResult] = Field(default_factory=list)
    warnings: list[CapabilityWarning] = Field(default_factory=list)
    required_failures: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def has_required_failure(self) -> bool:
        return bool(self.required_failures)
