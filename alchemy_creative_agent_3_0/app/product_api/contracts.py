"""Product-level request and response contracts for the V3 API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StrictStr,
    field_validator,
    model_validator,
)

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
    GENERATING = "generating"
    FINALIZING = "finalizing"
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


class ImageOutputOptions(ProductApiBase):
    """Official image output controls exposed as a typed V3 surface."""

    size: str | None = None
    quality: Literal["low", "medium", "high", "auto"] | None = None
    background: Literal["transparent", "opaque", "auto"] | None = None
    output_format: Literal["png", "jpeg", "webp"] | None = None
    output_compression: int | None = Field(default=None, ge=0, le=100)
    moderation: Literal["auto", "low"] | None = None

    @field_validator("size", mode="before")
    @classmethod
    def normalize_size(cls, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_format_options(self) -> "ImageOutputOptions":
        if self.output_compression is not None and self.output_format not in {"jpeg", "webp"}:
            raise ValueError("output_compression requires jpeg or webp output_format")
        if self.background == "transparent" and self.output_format == "jpeg":
            raise ValueError("transparent background requires png or webp output_format")
        return self


class CreateCreativeJobRequest(ProductApiBase):
    user_input: str
    brand_id: str | None = None
    continue_style_from_brand_id: str | None = None
    campaign: CampaignRequest | None = None
    scenario_selection: ScenarioSelection | None = None
    photographer_profile_id: str | None = None
    photographer_profile_selection_source: Literal["user_explicit_ui"] | None = None
    # Professional Mode is an explicit outer choice. It contributes only a
    # project-scoped People Asset binding; all creative direction remains in
    # the existing Remote Brain/shared runtime.
    professional_mode: Literal["standard", "professional"] = "standard"
    people_asset_id: str | None = None
    professional_identity_view_ids: list[str] = Field(default_factory=list)
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    product_profile: dict[str, Any] = Field(default_factory=dict)
    image_options: ImageOutputOptions | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_input")
    @classmethod
    def user_input_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("user_input is required")
        return value

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

    @field_validator("people_asset_id")
    @classmethod
    def clean_people_asset_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("professional_identity_view_ids")
    @classmethod
    def clean_professional_identity_view_ids(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value]
        if any(not item for item in cleaned):
            raise ValueError("professional_identity_view_ids must not contain empty strings")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("professional_identity_view_ids must be unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_explicit_professional_choice(self) -> "CreateCreativeJobRequest":
        if self.professional_mode == "standard" and (
            self.people_asset_id is not None or self.professional_identity_view_ids
        ):
            raise ValueError("People Asset selection requires explicit Professional Mode")
        if self.professional_mode == "professional" and self.people_asset_id is None:
            raise ValueError("Professional Mode requires a selected People Asset")
        return self

    @property
    def effective_brand_id(self) -> str | None:
        return self.brand_id or self.continue_style_from_brand_id


_VISUAL_RETRY_PATCH_FIELDS = (
    "prompt_additions",
    "negative_additions",
    "negative_prompt_additions",
    "reference_requirements",
    "identity_reinforcement",
    "product_reinforcement",
    "brand_asset_reinforcement",
    "composition_repair",
    "artifact_repair",
    "object_removal_instruction",
)


class VisualRetryPatch(BaseModel):
    """The narrow legacy-compatible retry material accepted by a continuation.

    This is intentionally limited to the existing compatibility patch fields.
    Provider routing, complete prompts, reasoning traces, and storage details
    remain server-owned and cannot cross the continuation boundary here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)

    prompt_additions: tuple[StrictStr, ...] = ()
    negative_additions: tuple[StrictStr, ...] = ()
    negative_prompt_additions: tuple[StrictStr, ...] = ()
    reference_requirements: tuple[StrictStr, ...] = ()
    identity_reinforcement: tuple[StrictStr, ...] = ()
    product_reinforcement: tuple[StrictStr, ...] = ()
    brand_asset_reinforcement: tuple[StrictStr, ...] = ()
    composition_repair: tuple[StrictStr, ...] = ()
    artifact_repair: tuple[StrictStr, ...] = ()
    object_removal_instruction: tuple[StrictStr, ...] = ()

    @field_validator(*_VISUAL_RETRY_PATCH_FIELDS, mode="before")
    @classmethod
    def normalize_legacy_patch_strings(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        values = (value,) if isinstance(value, str) else value
        if not isinstance(values, (list, tuple)):
            raise ValueError("visual retry patch fields must be strings or string sequences")
        if any(not isinstance(item, str) for item in values):
            raise ValueError("visual retry patch fields must contain only strings")
        cleaned = tuple(item.strip() for item in values)
        if any(not item for item in cleaned):
            raise ValueError("visual retry patch fields must not contain empty strings")
        return cleaned

    def legacy_payload(self) -> dict[str, list[str]]:
        """Return the established metadata shape consumed by legacy retry code."""

        return {
            field_name: list(values)
            for field_name in _VISUAL_RETRY_PATCH_FIELDS
            if (values := getattr(self, field_name))
        }


class GenerateContinuation(BaseModel):
    """Typed, server-only controls for continuing an existing V3 Job.

    This model is deliberately not accepted by the HTTP Generate contract.
    Public Generate requests carry product-level options only; worker claims,
    resume predicates, review switches, and retry controls enter through the
    explicit internal continuation seam on ``V3ProductApiService``.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        validate_default=True,
    )

    job_id: StrictStr
    background_worker_claim: StrictBool = False
    background_generation_attempt_id: StrictStr | None = None
    resume_interrupted_mcp_materialization: StrictBool = False
    resume_finalizing_review: StrictBool = False
    disable_visual_auto_retry: StrictBool | None = None
    max_visual_retry_attempts: StrictInt | None = Field(default=None, ge=0, le=2)
    enable_visual_auto_retry_in_explore: StrictBool | None = None
    force_empty_visual_retry_patch: StrictBool | None = None

    vision_inspection_mode: StrictStr | None = None
    post_generation_inspection_mode: StrictStr | None = None
    vision_inspection_timeout_seconds: StrictFloat | StrictInt | None = Field(
        default=None,
        ge=0.05,
        le=300.0,
    )
    vision_inspection_max_attempts: StrictInt | None = Field(default=None, ge=1, le=5)
    enable_real_vision_inspection: StrictBool | None = None
    disable_real_vision_inspection: StrictBool | None = None
    enable_local_aesthetic_heuristics: StrictBool | None = None
    post_generation_fake_issue_codes: tuple[StrictStr, ...] | None = None
    post_generation_fake_confidence: StrictFloat | StrictInt | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    force_visual_retry_issue_codes: tuple[StrictStr, ...] | None = None
    visual_retry_issue_codes: tuple[StrictStr, ...] | None = None
    visual_auto_retry_issue_codes: tuple[StrictStr, ...] | None = None
    force_anti_ai_face_issue_codes: tuple[StrictStr, ...] | None = None
    anti_ai_face_issue_codes: tuple[StrictStr, ...] | None = None
    force_beautiful_realism_issue_codes: tuple[StrictStr, ...] | None = None
    beautiful_realism_issue_codes: tuple[StrictStr, ...] | None = None
    facial_feature_issue_codes: tuple[StrictStr, ...] | None = None
    identity_card_issue_codes: tuple[StrictStr, ...] | None = None
    force_visual_retry_issue: StrictStr | None = None
    visual_retry_issue_code: StrictStr | None = None
    visual_retry_patch: VisualRetryPatch | None = None

    @field_validator("job_id", "background_generation_attempt_id", mode="after")
    @classmethod
    def non_empty_identifiers(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("continuation identifiers must not be empty")
        return cleaned

    @field_validator(
        "post_generation_fake_issue_codes",
        "force_visual_retry_issue_codes",
        "visual_retry_issue_codes",
        "visual_auto_retry_issue_codes",
        "force_anti_ai_face_issue_codes",
        "anti_ai_face_issue_codes",
        "force_beautiful_realism_issue_codes",
        "beautiful_realism_issue_codes",
        "facial_feature_issue_codes",
        "identity_card_issue_codes",
        mode="after",
    )
    @classmethod
    def issue_codes_are_non_empty(cls, value: tuple[str, ...] | None) -> tuple[str, ...] | None:
        if value is None:
            return None
        cleaned = tuple(item.strip() for item in value)
        if any(not item for item in cleaned):
            raise ValueError("continuation issue codes must not be empty")
        return cleaned

    @field_validator(
        "vision_inspection_mode",
        "post_generation_inspection_mode",
        "force_visual_retry_issue",
        "visual_retry_issue_code",
        mode="after",
    )
    @classmethod
    def continuation_strings_are_non_empty(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("continuation string controls must not be empty")
        return cleaned

    @model_validator(mode="after")
    def validate_continuation(self) -> "GenerateContinuation":
        if self.background_worker_claim and not self.background_generation_attempt_id:
            raise ValueError("background_worker_claim requires background_generation_attempt_id")
        if self.enable_real_vision_inspection and self.disable_real_vision_inspection:
            raise ValueError("vision enable and disable controls are mutually exclusive")
        return self

    def runtime_metadata(self) -> dict[str, Any]:
        """Return only the typed runtime controls for a trusted local copy."""

        metadata: dict[str, Any] = {}
        scalar_fields = (
            "disable_visual_auto_retry",
            "max_visual_retry_attempts",
            "enable_visual_auto_retry_in_explore",
            "force_empty_visual_retry_patch",
            "vision_inspection_mode",
            "post_generation_inspection_mode",
            "vision_inspection_timeout_seconds",
            "vision_inspection_max_attempts",
            "enable_real_vision_inspection",
            "disable_real_vision_inspection",
            "enable_local_aesthetic_heuristics",
            "post_generation_fake_confidence",
            "force_visual_retry_issue",
            "visual_retry_issue_code",
        )
        for field_name in scalar_fields:
            value = getattr(self, field_name)
            if value is not None:
                metadata[field_name] = value
        sequence_fields = (
            "post_generation_fake_issue_codes",
            "force_visual_retry_issue_codes",
            "visual_retry_issue_codes",
            "visual_auto_retry_issue_codes",
            "force_anti_ai_face_issue_codes",
            "anti_ai_face_issue_codes",
            "force_beautiful_realism_issue_codes",
            "beautiful_realism_issue_codes",
            "facial_feature_issue_codes",
            "identity_card_issue_codes",
        )
        for field_name in sequence_fields:
            value = getattr(self, field_name)
            if value is not None:
                metadata[field_name] = list(value)
        if self.visual_retry_patch is not None:
            metadata["visual_retry_patch"] = self.visual_retry_patch.legacy_payload()
        return metadata

    def legacy_metadata(self) -> dict[str, Any]:
        """Build the old metadata shape for test doubles without the seam.

        Production V3 services use ``runtime_metadata`` through the typed
        method.  This compatibility adapter is kept so historical host fakes
        can continue to assert the old call shape while they are migrated.
        """

        metadata = self.runtime_metadata()
        if self.background_worker_claim:
            metadata["_v3_background_worker_claim"] = True
        if self.background_generation_attempt_id:
            metadata["_v3_background_generation_attempt_id"] = self.background_generation_attempt_id
        if self.resume_interrupted_mcp_materialization:
            metadata["_v3_resume_interrupted_mcp_materialization"] = True
        if self.resume_finalizing_review:
            metadata["_v3_resume_finalizing_review"] = True
        return metadata


class GenerateJobRequest(ProductApiBase):
    quality_mode: str = "standard"
    image_options: ImageOutputOptions | None = None
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
    selected_candidate_ids: list[str] = Field(default_factory=list)
    selected_asset_ids: list[str] = Field(default_factory=list)
    apply_memory_update: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_selection_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        payload = dict(value)
        for singular_key, plural_key in (
            ("selected_candidate_id", "selected_candidate_ids"),
            ("selected_asset_id", "selected_asset_ids"),
        ):
            plural = payload.get(plural_key)
            if plural is None:
                plural = []
            if isinstance(plural, list):
                values = list(plural)
            else:
                values = plural
            singular = payload.get(singular_key)
            if singular is not None and isinstance(values, list):
                values.insert(0, singular)
            payload[plural_key] = values
        return payload

    @field_validator("selected_candidate_ids", "selected_asset_ids")
    @classmethod
    def clean_selection_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if str(item).strip()))


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
    veyra_user_id: int | None = None
    filename: str
    mime_type: str
    size_bytes: int = 0
    role: str | None = None
    status: V3AssetUploadStatusValue
    upload_url: str | None = None
    content_url: str | None = None
    file_path: str | None = None
    content_sha256: str | None = None
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
    creative_context: dict[str, Any] = Field(default_factory=dict)
    remote_brain_output_intents: list[dict[str, Any]] = Field(default_factory=list)
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
