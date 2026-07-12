"""V3-owned schema contracts for the planning foundation."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class V3BaseModel(BaseModel):
    """Base model configured for JSON-friendly V3 contracts."""

    model_config = ConfigDict(validate_assignment=True, extra="allow")


class Locale(StrEnum):
    ZH_CN = "zh-CN"
    EN_US = "en-US"
    UNKNOWN = "unknown"


class Platform(StrEnum):
    XIAOHONGSHU = "xiaohongshu"
    WECHAT_MOMENTS = "wechat_moments"
    DELIVERY_APP = "delivery_app"
    MEITUAN = "meituan"
    ELEME = "eleme"
    TAOBAO = "taobao"
    JD = "jd"
    DOUYIN = "douyin"
    ECOMMERCE_GENERIC = "ecommerce_generic"
    STORE_SCREEN = "store_screen"
    PRINT_POSTER = "print_poster"
    GENERIC_SOCIAL = "generic_social"
    GENERIC = "generic"


class IndustryCategory(StrEnum):
    BEVERAGE = "beverage"
    RESTAURANT_BARBECUE = "restaurant_barbecue"
    RESTAURANT_HOTPOT = "restaurant_hotpot"
    RESTAURANT_GENERAL = "restaurant_general"
    ECOMMERCE_PRODUCT = "ecommerce_product"
    LOCAL_SERVICE_BEAUTY = "local_service_beauty"
    LOCAL_SERVICE_GENERAL = "local_service_general"
    PERSONAL_BRAND = "personal_brand"
    EDUCATION = "education"
    HOSPITALITY = "hospitality"
    UNKNOWN = "unknown"


class AssetType(StrEnum):
    MAIN_POSTER = "main_poster"
    SOCIAL_COVER = "social_cover"
    WECHAT_MOMENTS_POSTER = "wechat_moments_poster"
    DELIVERY_COVER = "delivery_cover"
    ECOMMERCE_MAIN_IMAGE = "ecommerce_main_image"
    PRODUCT_DETAIL_BANNER = "product_detail_banner"
    GROUP_BUYING_IMAGE = "group_buying_image"
    STORE_SCREEN_IMAGE = "store_screen_image"
    CAMPAIGN_BANNER = "campaign_banner"
    BRAND_STYLE_SAMPLE = "brand_style_sample"
    SINGLE_IMAGE = "single_image"


class TextRenderingMode(StrEnum):
    HTML_OVERLAY = "html_overlay"
    SVG_OVERLAY = "svg_overlay"
    CANVAS_OVERLAY = "canvas_overlay"
    MODEL_TEXT_ALLOWED = "model_text_allowed"
    NO_TEXT = "no_text"
    UNKNOWN = "unknown"


class ProviderStrategy(StrEnum):
    AUTO = "auto"
    PLANNING_ONLY = "planning_only"
    MOCK_GENERATION = "mock_generation"
    DEFAULT_IMAGE_PROVIDER = "default_image_provider"
    REFERENCE_CONDITIONED_PROVIDER = "reference_conditioned_provider"
    LAYOUT_CONDITIONED_PROVIDER = "layout_conditioned_provider"
    EXTERNAL_RENDERER_ONLY = "external_renderer_only"


class Recommendation(StrEnum):
    ACCEPT = "accept"
    RETRY = "retry"
    REJECT = "reject"
    MANUAL_REVIEW = "manual_review"
    PLANNING_ONLY = "planning_only"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    HARD_FAILURE = "hard_failure"


class CreativeJob(V3BaseModel):
    job_id: str
    raw_user_input: str
    locale: Locale = Locale.ZH_CN
    optional_brand_id: str | None = None
    optional_template_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    requested_output: str = "commercial_image_series"
    explicit_constraints: list[str] = Field(default_factory=list)
    implicit_constraints: list[str] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommercialBrief(V3BaseModel):
    brief_id: str
    job_id: str
    industry: IndustryCategory
    scenario: str
    business_goal: str
    target_platforms: list[Platform]
    target_audience: str | None = None
    commercial_hooks: list[str] = Field(default_factory=list)
    selling_points: list[str] = Field(default_factory=list)
    visual_tone: list[str] = Field(default_factory=list)
    copy_strategy: str | None = None
    platform_notes: dict[str, Any] = Field(default_factory=dict)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReferenceAsset(V3BaseModel):
    asset_id: str
    asset_type: str
    source: str
    purpose: str | None = None
    style_tags: list[str] = Field(default_factory=list)
    file_path: str | None = None
    uri: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BrandProfile(V3BaseModel):
    brand_id: str
    brand_name: str | None = None
    industry: IndustryCategory | None = None
    is_temporary: bool = True
    visual_tone: list[str] = Field(default_factory=list)
    color_palette: list[str] = Field(default_factory=list)
    layout_preference: str | None = None
    typography_preference: str | None = None
    copywriting_tone: str | None = None
    reference_assets: list[ReferenceAsset] = Field(default_factory=list)
    successful_asset_ids: list[str] = Field(default_factory=list)
    rejected_style_tags: list[str] = Field(default_factory=list)
    platform_history: list[Platform] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreativePlan(V3BaseModel):
    creative_plan_id: str
    job_id: str
    brief_id: str
    brand_id: str | None = None
    concept: str
    visual_direction: str
    composition_strategy: str
    lighting_strategy: str | None = None
    color_strategy: list[str] = Field(default_factory=list)
    materials_and_props: list[str] = Field(default_factory=list)
    copy_strategy: str | None = None
    consistency_strategy: str | None = None
    negative_direction: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AssetSpec(V3BaseModel):
    asset_id: str
    asset_type: AssetType
    platform: Platform
    aspect_ratio: str
    purpose: str
    priority: int = 1
    # New V3 assets are complete provider-generated images.  This legacy field
    # remains readable for historical manifests but must never default a new
    # job into an external HTML/SVG/canvas composition path.
    requires_text_overlay: bool = False
    requires_brand_consistency: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class SeriesPlan(V3BaseModel):
    series_plan_id: str
    job_id: str
    assets: list[AssetSpec]
    series_strategy: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutRegion(V3BaseModel):
    name: str
    position: str
    priority: int = 1
    relative_box: dict[str, float] | None = None
    notes: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LayoutPlan(V3BaseModel):
    layout_plan_id: str
    asset_id: str
    platform: Platform
    aspect_ratio: str
    # Provider-native text, when a user explicitly requests it, is part of the
    # image-generation brief.  Layout regions are not a local post-render
    # typography instruction.
    text_rendering: TextRenderingMode = TextRenderingMode.MODEL_TEXT_ALLOWED
    visual_hierarchy: list[str] = Field(default_factory=list)
    product_area: LayoutRegion
    headline_area: LayoutRegion | None = None
    subtitle_area: LayoutRegion | None = None
    cta_area: LayoutRegion | None = None
    logo_area: LayoutRegion | None = None
    reserved_text_regions: list[LayoutRegion] = Field(default_factory=list)
    typography_strategy: str | None = None
    background_strategy: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PromptCompilationResult(V3BaseModel):
    prompt_compilation_id: str
    asset_id: str
    visual_prompt: str
    negative_prompt: str | None = None
    hard_constraints: list[str] = Field(default_factory=list)
    text_policy: str
    style_notes: list[str] = Field(default_factory=list)
    layout_notes: list[str] = Field(default_factory=list)
    provider_notes: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConditionSpec(V3BaseModel):
    enabled: bool
    provider: str
    reference_asset_ids: list[str] = Field(default_factory=list)
    strength: float | None = Field(default=None, ge=0.0, le=1.0)
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConditionPlan(V3BaseModel):
    condition_plan_id: str
    asset_id: str
    style_condition: ConditionSpec | None = None
    layout_condition: ConditionSpec | None = None
    identity_condition: ConditionSpec | None = None
    product_condition: ConditionSpec | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationPlan(V3BaseModel):
    generation_plan_id: str
    asset_id: str
    provider_strategy: ProviderStrategy = ProviderStrategy.PLANNING_ONLY
    candidate_count: int = 4
    quality_threshold: float = Field(default=0.78, ge=0.0, le=1.0)
    max_refine_rounds: int = 2
    scorers: list[str] = Field(default_factory=list)
    rendering_required: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateResult(V3BaseModel):
    candidate_id: str
    asset_id: str
    file_path: str | None = None
    uri: str | None = None
    provider: str | None = None
    prompt_compilation_id: str | None = None
    condition_plan_id: str | None = None
    is_mock: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationProblem(V3BaseModel):
    code: str
    message: str
    severity: Severity
    repair_hint: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationReport(V3BaseModel):
    evaluation_id: str
    candidate_id: str | None = None
    asset_id: str
    aesthetic_score: float = Field(ge=0.0, le=1.0)
    commercial_score: float = Field(ge=0.0, le=1.0)
    brand_consistency_score: float = Field(ge=0.0, le=1.0)
    layout_score: float = Field(ge=0.0, le=1.0)
    text_region_score: float = Field(ge=0.0, le=1.0)
    platform_fit_score: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    recommendation: Recommendation
    problems: list[EvaluationProblem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("overall_score")
    @classmethod
    def round_overall(cls, value: float) -> float:
        return round(value, 4)


class RefinementPlan(V3BaseModel):
    refinement_plan_id: str
    asset_id: str
    source_evaluation_id: str
    action: Recommendation
    prompt_modifications: list[str] = Field(default_factory=list)
    layout_modifications: list[str] = Field(default_factory=list)
    condition_modifications: list[str] = Field(default_factory=list)
    provider_modifications: list[str] = Field(default_factory=list)
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryUpdate(V3BaseModel):
    memory_update_id: str
    brand_id: str
    action: str
    accepted_asset_ids: list[str] = Field(default_factory=list)
    new_reference_assets: list[ReferenceAsset] = Field(default_factory=list)
    new_style_tags: list[str] = Field(default_factory=list)
    new_rejected_style_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PackagedAsset(V3BaseModel):
    asset_id: str
    asset_type: AssetType
    platform: Platform
    aspect_ratio: str
    purpose: str
    file_path: str | None = None
    uri: str | None = None
    layout_plan_id: str | None = None
    prompt_compilation_id: str | None = None
    evaluation_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommercialAssetPack(V3BaseModel):
    asset_pack_id: str
    job_id: str
    brand_id: str | None = None
    assets: list[PackagedAsset] = Field(default_factory=list)
    manifest: dict[str, Any] = Field(default_factory=dict)
    brand_memory_update: MemoryUpdate | None = None
    planning_only: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanningResult(V3BaseModel):
    planning_result_id: str
    creative_job: CreativeJob
    commercial_brief: CommercialBrief
    brand_profile: BrandProfile
    creative_plan: CreativePlan
    series_plan: SeriesPlan
    layout_plans: list[LayoutPlan]
    prompt_compilations: list[PromptCompilationResult]
    condition_plans: list[ConditionPlan]
    generation_plans: list[GenerationPlan]
    evaluation_reports: list[EvaluationReport]
    asset_pack: CommercialAssetPack
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "AssetSpec",
    "AssetType",
    "BrandProfile",
    "CandidateResult",
    "CommercialAssetPack",
    "CommercialBrief",
    "ConditionPlan",
    "ConditionSpec",
    "CreativeJob",
    "CreativePlan",
    "EvaluationProblem",
    "EvaluationReport",
    "GenerationPlan",
    "IndustryCategory",
    "LayoutPlan",
    "LayoutRegion",
    "Locale",
    "MemoryUpdate",
    "PackagedAsset",
    "PlanningResult",
    "Platform",
    "PromptCompilationResult",
    "ProviderStrategy",
    "Recommendation",
    "ReferenceAsset",
    "RefinementPlan",
    "SeriesPlan",
    "Severity",
    "TextRenderingMode",
]
