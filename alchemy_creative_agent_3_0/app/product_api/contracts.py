"""Product-level request and response contracts for the V3 API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..public_api_guardrails import reject_low_level_controls
from ..scenario_packs import ScenarioSelection
from ..schemas import BrandProfile, IndustryCategory, Platform
from ..schemas.models import V3BaseModel


class ProductApiBase(V3BaseModel):
    """Strict public API model that keeps low-level generation controls hidden."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def low_level_generation_controls_are_not_public_api(cls, data: Any) -> Any:
        reject_low_level_controls(data)
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
    scenario_selection: ScenarioSelection | None = None
    photographer_profile_id: str | None = None
    photographer_profile_selection_source: Literal["user_explicit_ui"] | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    product_profile: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

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

    @field_validator("photographer_profile_id")
    @classmethod
    def clean_photographer_profile_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

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


class V3AssetUploadStatusValue(StrEnum):
    UPLOAD_REQUESTED = "upload_requested"
    STORED = "stored"
    READY = "ready"
    FAILED = "failed"


class V3AssetUploadCreateRequest(ProductApiBase):
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    role: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("filename is required")
        return cleaned

    @field_validator("mime_type")
    @classmethod
    def mime_type_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not cleaned:
            raise ValueError("mime_type is required")
        return cleaned


class V3AssetContentUploadRequest(ProductApiBase):
    content_base64: str
    mime_type: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content_base64")
    @classmethod
    def content_base64_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("content_base64 is required")
        return cleaned


class V3UploadedAssetRecord(V3BaseModel):
    asset_id: str
    filename: str
    mime_type: str
    size_bytes: int = 0
    role: str | None = None
    status: V3AssetUploadStatusValue
    upload_url: str | None = None
    content_url: str | None = None
    file_path: str | None = None
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str
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
    output_id: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    thumbnail_url: str | None = None
    editable_text_layer_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateSummary(V3BaseModel):
    candidate_id: str
    asset_id: str
    platform: Platform
    preview_uri: str | None = None
    output_id: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    thumbnail_url: str | None = None
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


class ScenarioSummary(V3BaseModel):
    scenario_id: str
    display_name: str
    status: str
    can_create_jobs: bool
    selected_mode_id: str | None = None
    selected_preset_id: str | None = None
    route_hint: str | None = None
    ui_card: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StyleContinuationSummary(V3BaseModel):
    enabled: bool = False
    source_brand_id: str | None = None
    visual_tone: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    reference_asset_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeneralCreativeCapabilitySummary(V3BaseModel):
    enabled: bool = False
    scenario_id: str = "general_creative"
    selected_mode_id: str | None = None
    selected_preset_id: str | None = None
    user_controls: list[str] = Field(default_factory=list)
    reference_understanding: list[str] = Field(default_factory=list)
    reference_bindings: list[str] = Field(default_factory=list)
    visual_grammar: list[str] = Field(default_factory=list)
    information_integrity: list[str] = Field(default_factory=list)
    review_hints: list[str] = Field(default_factory=list)
    history_continuation: list[str] = Field(default_factory=list)
    closure_checks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceCapabilitySummary(V3BaseModel):
    enabled: bool = False
    scenario_id: str = "ecommerce"
    selected_mode_id: str | None = None
    selected_preset_id: str | None = None
    platform: str = "generic"
    market: str = "global"
    product_truth: dict[str, Any] = Field(default_factory=dict)
    target_audience: list[str] = Field(default_factory=list)
    buying_motivations: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    trust_drivers: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    keyword_intent_map: list[dict[str, str]] = Field(default_factory=list)
    competitor_patterns: list[str] = Field(default_factory=list)
    visual_strategy: list[str] = Field(default_factory=list)
    image_recipes: list[dict[str, Any]] = Field(default_factory=list)
    critic_checks: list[dict[str, Any]] = Field(default_factory=list)
    export_package: dict[str, Any] = Field(default_factory=dict)
    closure_checks: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
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
    scenario: ScenarioSummary | None = None
    campaign: CampaignSummary | None = None
    asset_series: list[AssetSeriesItem] = Field(default_factory=list)
    candidates: list[CandidateSummary] = Field(default_factory=list)
    style_continuation: StyleContinuationSummary | None = None
    general_creative: GeneralCreativeCapabilitySummary | None = None
    ecommerce: EcommerceCapabilitySummary | None = None
    selected_result: SelectedResult | None = None
    balance_estimate: dict[str, Any] = Field(default_factory=dict)
    routes: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class V3JobHistoryItem(V3BaseModel):
    job_id: str
    status: ProductJobStatusValue
    scenario_id: str | None = None
    scenario_label: str | None = None
    selected_preset_id: str | None = None
    user_input: str
    asset_count: int = 0
    candidate_count: int = 0
    selected_asset_count: int = 0
    created_at: str
    updated_at: str
    route: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class V3JobHistoryResponse(V3BaseModel):
    api_namespace: str
    route: str
    total: int
    limit: int
    items: list[V3JobHistoryItem] = Field(default_factory=list)
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


class V3ExportPackageResponse(V3BaseModel):
    job_id: str
    status: ProductJobStatusValue
    api_namespace: str
    scenario_id: str | None = None
    package_id: str | None = None
    export_package: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    download_route: str | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class V3ExportDownloadPayload(V3BaseModel):
    filename: str
    content_type: str = "application/json"
    content: str
    response: V3ExportPackageResponse
