"""Contracts for the V3 Scenario Runtime."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..public_api_guardrails import reject_low_level_controls
from ..scenario_packs import ScenarioPackResolution, ScenarioSelection
from ..shared_capabilities import CapabilityRunResult, UploadedAssetInfo
from ..shared_capabilities.activation import CapabilityActivationPlan, CapabilityContribution
from ..llm_brain import BrainRunResult
from ..schemas import PlanningResult
from ..schemas.models import V3BaseModel


class ScenarioRuntimeStatus(StrEnum):
    PLANNED = "planned"
    GENERATED = "generated"
    BLOCKED = "blocked"


class ScenarioRuntimeRequest(V3BaseModel):
    """Product-level request consumed by ScenarioRuntime."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    user_input: str
    optional_brand_id: str | None = None
    scenario_selection: ScenarioSelection | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    uploaded_assets: list[UploadedAssetInfo] = Field(default_factory=list)
    product_profile: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def runtime_request_is_product_level(cls, data: Any) -> Any:
        reject_low_level_controls(data)
        return data

    @field_validator("user_input")
    @classmethod
    def user_input_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_input is required")
        return cleaned

    @field_validator("uploaded_asset_ids")
    @classmethod
    def uploaded_asset_ids_must_not_be_empty_strings(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("uploaded_asset_ids must not contain empty strings")
        return cleaned


class SpecializedScenarioPlanningContext(V3BaseModel):
    """Mainline-owned input passed to an active specialized scenario planner.

    The context contains a server-pinned profile binding but never permits the
    specialized module to choose, replace, or mutate that binding.
    """

    job_key: str
    user_input: str
    scenario_resolution: ScenarioPackResolution
    selected_mode_id: str | None = None
    uploaded_assets: list[UploadedAssetInfo] = Field(default_factory=list)
    project_context_snapshot: dict[str, Any] = Field(default_factory=dict)
    photographer_profile_binding: dict[str, Any] | None = None
    frozen_capability_activation_plan: CapabilityActivationPlan | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SpecializedScenarioPlanningResult(V3BaseModel):
    """Frozen planning facts before shared capability composition and execution."""

    planning_id: str
    scenario_id: str
    template_id: str
    planner_id: str
    capability_contribution_draft: CapabilityContribution
    required_capability_ids: list[str] = Field(default_factory=list)
    requested_image_count: int | None = Field(default=None, ge=1, le=4)
    # An active specialized Scenario Pack may freeze an execution-neutral
    # per-output role contract.  Central Brain never receives this raw
    # payload; the shared execution runtime materializes it only after the
    # capability plan is frozen.  This keeps the seam reusable for future
    # specialized templates without putting their deliverable maps in General.
    execution_plan: dict[str, Any] = Field(default_factory=dict)
    safe_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

class ScenarioRuntimeResult(V3BaseModel):
    """ScenarioRuntime output before product API response shaping."""

    status: ScenarioRuntimeStatus
    scenario_resolution: ScenarioPackResolution
    capability_run: CapabilityRunResult | None = None
    planning_result: PlanningResult | None = None
    generation_result: PlanningResult | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CapabilityPreparationResult(V3BaseModel):
    """One immutable capability preparation result shared by plan and generate."""

    pre_activation_run: CapabilityRunResult | None = None
    brain_result: BrainRunResult
    activation_plan: CapabilityActivationPlan | None = None
    active_capability_run: CapabilityRunResult | None = None
    combined_capability_run: CapabilityRunResult | None = None
    activation_mode: str = "legacy"
    specialized_scenario_plan: SpecializedScenarioPlanningResult | None = None
