"""V3-owned Scenario Pack contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..public_api_guardrails import reject_low_level_controls
from ..schemas.models import V3BaseModel


class ScenarioPackStatus(StrEnum):
    ACTIVE = "active"
    PLACEHOLDER = "placeholder"
    INACTIVE = "inactive"


class ScenarioSelection(V3BaseModel):
    """Product-level scenario choice from the user-facing API or Scenario Hub."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    scenario_id: str = "general_creative"
    mode_id: str | None = None
    preset_id: str | None = None
    platform_profile: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def scenario_selection_is_product_level(cls, data: Any) -> Any:
        reject_low_level_controls(data)
        return data

    @field_validator("scenario_id", "mode_id", "preset_id", "platform_profile")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("scenario selection text fields must not be empty")
        return cleaned


class ScenarioPackManifest(V3BaseModel):
    """UI and runtime manifest for one Scenario Pack."""

    scenario_id: str
    display_name: str
    category: str
    status: ScenarioPackStatus = ScenarioPackStatus.PLACEHOLDER
    description: str
    default_mode_id: str | None = None
    supported_mode_ids: list[str] = Field(default_factory=list)
    preset_ids: list[str] = Field(default_factory=list)
    enabled_capabilities: list[str] = Field(default_factory=list)
    route_hint: str | None = None
    ui_card: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def can_create_jobs(self) -> bool:
        return self.status == ScenarioPackStatus.ACTIVE


class ScenarioPackResolution(V3BaseModel):
    """Resolved Scenario Pack choice for runtime and product responses."""

    selection: ScenarioSelection
    manifest: ScenarioPackManifest
    status: ScenarioPackStatus
    can_create_jobs: bool
    selected_mode_id: str | None = None
    selected_preset_id: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
