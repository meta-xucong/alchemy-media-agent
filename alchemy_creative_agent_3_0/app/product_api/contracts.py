"""Product-level request and response contracts for the V3 API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas import BrandProfile, IndustryCategory, Platform
from ..schemas.models import V3BaseModel


LOW_LEVEL_GENERATION_CONTROL_KEYS = {
    "seed",
    "sampler",
    "lora",
    "lora_weight",
    "controlnet",
    "controlnet_type",
    "control_net",
    "control_net_type",
    "adapter_scale",
    "ip_adapter_scale",
    "node_graph",
}


def _normalise_public_key(key: str) -> str:
    return key.strip().lower().replace("-", "_").replace(" ", "_")


def _low_level_control_paths(value: Any, prefix: str = "") -> list[str]:
    if isinstance(value, dict):
        paths: list[str] = []
        for raw_key, raw_value in value.items():
            key = str(raw_key)
            path = f"{prefix}.{key}" if prefix else key
            if _normalise_public_key(key) in LOW_LEVEL_GENERATION_CONTROL_KEYS:
                paths.append(path)
            paths.extend(_low_level_control_paths(raw_value, path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            path = f"{prefix}[{index}]" if prefix else f"[{index}]"
            paths.extend(_low_level_control_paths(item, path))
        return paths
    return []


class ProductApiBase(V3BaseModel):
    """Strict public API model that keeps low-level generation controls hidden."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def low_level_generation_controls_are_not_public_api(cls, data: Any) -> Any:
        blocked_paths = _low_level_control_paths(data)
        if blocked_paths:
            raise ValueError(
                "low-level generation controls are not part of the V3 product API: "
                + ", ".join(sorted(blocked_paths))
            )
        return data


class ProductJobStatusValue(StrEnum):
    PLANNED = "planned"
    GENERATED = "generated"
    SELECTED = "selected"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    FAILED = "failed"


class CampaignRequest(ProductApiBase):
    campaign_id: str | None = None
    campaign_name: str | None = None
    business_goal: str | None = None
    platforms: list[Platform] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateCreativeJobRequest(ProductApiBase):
    user_input: str
    brand_id: str | None = None
    continue_style_from_brand_id: str | None = None
    campaign: CampaignRequest | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_input")
    @classmethod
    def user_input_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_input is required")
        return cleaned

    @property
    def effective_brand_id(self) -> str | None:
        return self.brand_id or self.continue_style_from_brand_id


class GenerateJobRequest(ProductApiBase):
    quality_mode: str = "standard"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("quality_mode")
    @classmethod
    def quality_mode_is_product_level(cls, value: str) -> str:
        allowed = {"standard", "explore", "strict"}
        if value not in allowed:
            raise ValueError(f"quality_mode must be one of {sorted(allowed)}")
        return value


class SelectResultRequest(ProductApiBase):
    selected_candidate_id: str | None = None
    selected_asset_id: str | None = None
    apply_memory_update: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateBrandRequest(ProductApiBase):
    brand_id: str | None = None
    brand_name: str | None = None
    industry: IndustryCategory = IndustryCategory.UNKNOWN
    visual_tone: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    layout_preference: str | None = None
    typography_preference: str | None = None
    copywriting_tone: str | None = None
    platform_history: list[Platform] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetSeriesItem(V3BaseModel):
    asset_id: str
    asset_type: str
    platform: Platform
    aspect_ratio: str
    purpose: str
    status: str
    selected_candidate_id: str | None = None
    preview_uri: str | None = None
    editable_text_layer_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateSummary(V3BaseModel):
    candidate_id: str
    asset_id: str
    platform: Platform
    preview_uri: str | None = None
    overall_score: float | None = None
    recommendation: str | None = None
    selected: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CampaignSummary(V3BaseModel):
    campaign_id: str
    campaign_name: str | None = None
    scenario: str
    business_goal: str
    target_platforms: list[Platform] = Field(default_factory=list)
    commercial_hooks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StyleContinuationSummary(V3BaseModel):
    enabled: bool = False
    source_brand_id: str | None = None
    visual_tone: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    reference_asset_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelectedResult(V3BaseModel):
    selected_candidate_ids: list[str] = Field(default_factory=list)
    selected_asset_ids: list[str] = Field(default_factory=list)
    asset_pack_id: str | None = None
    memory_update_id: str | None = None
    memory_update_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProductJobStatus(V3BaseModel):
    job_id: str
    status: ProductJobStatusValue
    api_namespace: str
    ui_entry_route: str
    brand_id: str | None = None
    planning_result_id: str | None = None
    generation_result_id: str | None = None
    asset_pack_id: str | None = None
    campaign: CampaignSummary | None = None
    asset_series: list[AssetSeriesItem] = Field(default_factory=list)
    candidates: list[CandidateSummary] = Field(default_factory=list)
    style_continuation: StyleContinuationSummary | None = None
    selected_result: SelectedResult | None = None
    balance_estimate: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrandApiResponse(V3BaseModel):
    status: str
    brand: BrandProfile | None = None
    api_namespace: str
    route: str
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SelectionResponse(V3BaseModel):
    job_id: str
    status: ProductJobStatusValue
    selected_result: SelectedResult
    job_status: ProductJobStatus
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
