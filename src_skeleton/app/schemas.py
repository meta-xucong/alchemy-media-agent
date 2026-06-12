from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    created = "created"
    queued = "queued"
    planning = "planning"
    safety_check = "safety_check"
    generating = "generating"
    postprocessing = "postprocessing"
    evaluating = "evaluating"
    processing = "processing"
    submitted = "submitted"
    provider_not_configured = "provider_not_configured"
    ready = "ready"
    failed = "failed"
    canceled = "canceled"
    rejected = "rejected"


class MaterialBrief(BaseModel):
    asset_id: str
    asset_type: str
    summary: str
    visual_style: dict[str, Any] = Field(default_factory=dict)
    text_constraints: list[str] = Field(default_factory=list)
    reference_usage: str | None = None
    detected_roles: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


class AssetVisionProfile(BaseModel):
    asset_id: str
    status: Literal["pending", "ready", "failed", "skipped"] = "pending"
    analyzer_provider: str = "local_asset_vision"
    analyzer_model: str = "pillow-statistical-v1"
    summary: str | None = None
    image: dict[str, Any] = Field(default_factory=dict)
    style: dict[str, Any] = Field(default_factory=dict)
    composition: dict[str, Any] = Field(default_factory=dict)
    subjects: list[dict[str, Any]] = Field(default_factory=list)
    detected_text: list[dict[str, Any]] = Field(default_factory=list)
    logo_candidates: list[dict[str, Any]] = Field(default_factory=list)
    faces: list[dict[str, Any]] = Field(default_factory=list)
    risks: list[dict[str, Any]] = Field(default_factory=list)
    recommended_roles: list[str] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    created_at: str | None = None


class VisualReviewResult(BaseModel):
    review_status: Literal["ready", "failed", "skipped"] = "skipped"
    review_provider: str = "local_visual_review_fallback"
    overall_score: float | None = Field(default=None, ge=0, le=1)
    checks: dict[str, Any] = Field(default_factory=dict)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    retry_recommendation: str | None = None
    created_at: str | None = None


class AssetConsent(BaseModel):
    user_confirmed_rights: bool = False
    rights_confirmed: bool | None = None
    portrait_identity_allowed: bool = False
    logo_or_trademark_allowed: bool = False
    commercial_use_allowed: bool = False
    source_note: str | None = None

    def has_basic_rights(self) -> bool:
        return self.user_confirmed_rights or bool(self.rights_confirmed)


class AssetPlacement(BaseModel):
    anchor: Literal[
        "top_left",
        "top_center",
        "top_right",
        "center_left",
        "center",
        "center_right",
        "bottom_left",
        "bottom_center",
        "bottom_right",
        "custom",
    ] = "bottom_right"
    margin_ratio: float = Field(default=0.06, ge=0, le=0.5)
    width_ratio: float = Field(default=0.18, ge=0.01, le=1)
    height_ratio: float | None = Field(default=None, ge=0.01, le=1)
    opacity: float = Field(default=1.0, ge=0, le=1)
    safe_area: bool = True
    x_ratio: float | None = Field(default=None, ge=0, le=1)
    y_ratio: float | None = Field(default=None, ge=0, le=1)


class AssetIntent(BaseModel):
    asset_id: str
    role: Literal[
        "style_reference",
        "subject_reference",
        "logo_overlay",
        "portrait_identity",
        "background_reference",
        "composition_reference",
        "local_edit",
        "negative_reference",
    ]
    priority: int = Field(default=50, ge=1, le=100)
    preservation: Literal["loose", "medium", "strict", "exact"] = "loose"
    strength: float = Field(default=0.5, ge=0, le=1)
    notes: str | None = None
    placement: AssetPlacement | None = None
    mask_id: str | None = None
    consent: AssetConsent = Field(default_factory=AssetConsent)


class CreateAssetUploadRequest(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    declared_role: Literal[
        "style_reference",
        "subject_reference",
        "logo_overlay",
        "portrait_identity",
        "background_reference",
        "composition_reference",
        "local_edit",
        "negative_reference",
    ] | None = None
    intended_use: str | None = None
    consent: AssetConsent | dict[str, Any]


class CreateAssetUploadResponse(BaseModel):
    asset_id: str
    upload_url: str
    headers: dict[str, str] = Field(default_factory=dict)


class AssetContentUploadRequest(BaseModel):
    content_base64: str
    mime_type: str | None = None


class CreateAssetMaskRequest(BaseModel):
    mask_type: Literal["polygon", "brush", "rectangle"]
    points: list[dict[str, float]] = Field(default_factory=list)
    label: str | None = None


class CreateAssetMaskResponse(BaseModel):
    mask_id: str
    mask_url: str


class Asset(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: Literal[
        "created",
        "upload_requested",
        "uploaded",
        "scanning",
        "stored",
        "normalized",
        "derivatives_ready",
        "extracting",
        "analyzed",
        "ready",
        "scan_failed",
        "normalize_failed",
        "analysis_failed",
        "unsupported_type",
        "policy_blocked",
        "failed",
        "rejected",
    ]
    upload_url: str | None = None
    thumbnail_url: str | None = None
    normalized_url: str | None = None
    material_brief: MaterialBrief | None = None
    vision_profile: AssetVisionProfile | None = None
    declared_role: str | None = None
    intended_use: str | None = None
    consent: AssetConsent | dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ImagePromptPlan(BaseModel):
    main_subject: str
    scene: str | None = None
    style: str | None = None
    composition: str | None = None
    brand_constraints: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    text: dict[str, Any] = Field(default_factory=dict)
    count: int = Field(default=1, ge=1, le=10)
    size: str | None = None
    quality: Literal["low", "medium", "high", "auto"] = "auto"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    transparent_background: bool = False
    variables: dict[str, Any] = Field(default_factory=dict)


class PromptPatch(BaseModel):
    base_output_id: str
    preserve: list[str] = Field(default_factory=list)
    change: list[str] = Field(default_factory=list)
    remove: list[str] = Field(default_factory=list)
    add: list[str] = Field(default_factory=list)
    edit_mode: Literal["image_edit", "regenerate"] = "image_edit"
    new_prompt_delta: str


class ImageGenerationRequest(BaseModel):
    prompt_plan: ImagePromptPlan
    asset_ids: list[str] = Field(default_factory=list)
    asset_mode: Literal["basic", "advanced"] = "basic"
    asset_intents: list[AssetIntent] = Field(default_factory=list)
    asset_plan: dict[str, Any] | None = None
    provider_preference: str | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    source_output_id: str | None = None
    veyra_user_id: int | None = None


class ImageGenerationResult(BaseModel):
    provider: str
    model: str
    outputs: list[dict[str, Any]]
    raw_response_summary: dict[str, Any] = Field(default_factory=dict)


class CostEstimate(BaseModel):
    provider: str
    model: str
    estimated_cost: float = 0.0
    currency: str = "USD"
    detail: dict[str, Any] = Field(default_factory=dict)


class ProviderError(BaseModel):
    code: str
    message: str
    provider: str | None = None
    retryable: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)


class ScoreReport(BaseModel):
    prompt_adherence: float = 0.8
    asset_consistency: float = 0.8
    text_quality: float = 0.8
    composition: float = 0.8
    subject_integrity: float = 0.8
    safety: float = 1.0
    technical: float = 1.0
    notes: list[str] = Field(default_factory=list)


class GenerationOutput(BaseModel):
    id: str
    job_id: str
    url: str
    thumbnail_url: str | None = None
    format: Literal["png", "jpeg", "webp", "mp4"] = "png"
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None
    score: ScoreReport | None = None
    visual_review: VisualReviewResult | None = None
    version_parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationJob(BaseModel):
    id: str
    session_id: str | None = None
    job_type: Literal["image", "video"]
    status: JobStatus
    provider: str | None = None
    model: str | None = None
    asset_mode: Literal["basic", "advanced"] = "basic"
    asset_plan: dict[str, Any] | None = None
    postprocess_steps: list[dict[str, Any]] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    prompt_plan: ImagePromptPlan | None = None
    video_request: "VideoGenerationRequest | None" = None
    outputs: list[GenerationOutput] = Field(default_factory=list)
    error: ProviderError | None = None
    cost_estimate: CostEstimate | None = None
    idempotency_key: str | None = None
    trace_id: str
    version_parent_id: str | None = None
    raw_response_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ImageHistoryItem(BaseModel):
    id: str
    job_id: str
    session_id: str | None = None
    url: str
    thumbnail_url: str | None = None
    format: Literal["png", "jpeg", "webp"] = "png"
    width: int | None = None
    height: int | None = None
    provider: str | None = None
    model: str | None = None
    requested_provider: str | None = None
    requested_model: str | None = None
    provider_fallback: dict[str, Any] | None = None
    asset_mode: Literal["basic", "advanced"] = "basic"
    asset_intents: list[dict[str, Any]] = Field(default_factory=list)
    asset_plan: dict[str, Any] | None = None
    asset_vision_profiles: list[dict[str, Any]] = Field(default_factory=list)
    provider_input_plan: dict[str, Any] | None = None
    visual_review: dict[str, Any] | None = None
    prompt_plan: dict[str, Any] | None = None
    original_prompt: str | None = None
    final_prompt: str | None = None
    work_intensity: Literal["swift", "balanced", "studio", "atelier"] | None = None
    work_intensity_label: str | None = None
    prompt: str | None = None
    size: str | None = None
    version_parent_id: str | None = None
    veyra_user_id: int | None = None
    veyra_legacy_public: bool = False
    record_label: str | None = None
    can_delete: bool = False
    created_at: str | None = None
    updated_at: str | None = None
    source: Literal["repository", "manifest", "filesystem"] = "repository"


class ImageHistoryResponse(BaseModel):
    items: list[ImageHistoryItem] = Field(default_factory=list)
    total: int = 0


class CreateSessionRequest(BaseModel):
    project_id: str
    title: str | None = None
    orchestration_mode: Literal["runtime_first", "claude_first"] = "runtime_first"


class Session(BaseModel):
    id: str
    project_id: str
    title: str | None = None
    orchestration_mode: Literal["runtime_first", "claude_first"] = "runtime_first"
    created_at: str


class MessageRequest(BaseModel):
    text: str
    asset_ids: list[str] = Field(default_factory=list)
    target: Literal["auto", "image", "video", "revise", "batch"] = "auto"
    preferences: dict[str, Any] = Field(default_factory=dict)


class MessageResponse(BaseModel):
    message_id: str
    assistant_text: str
    job_ids: list[str] = Field(default_factory=list)


class CreateImageJobRequest(BaseModel):
    session_id: str
    prompt: str = Field(min_length=1)
    asset_mode: Literal["basic", "advanced"] = "basic"
    asset_ids: list[str] = Field(default_factory=list)
    asset_intents: list[AssetIntent] = Field(default_factory=list)
    count: int = Field(default=1, ge=1, le=10)
    size: str | None = None
    quality: Literal["low", "medium", "high", "auto"] = "auto"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    work_intensity: Literal["swift", "balanced", "studio", "atelier"] | None = None
    provider_preference: str | None = None
    idempotency_key: str | None = None

    @field_validator("prompt")
    @classmethod
    def prompt_must_not_be_blank(cls, value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("请先填写生图提示词。")
        return clean


class ReviseImageRequest(BaseModel):
    output_id: str
    feedback: str
    preserve: list[str] = Field(default_factory=list)
    provider_preference: str | None = None


class VideoGenerationRequest(BaseModel):
    task_type: Literal["text_to_video", "image_to_video", "reference_to_video", "extend_video", "first_last_frame_video"]
    prompt: str
    asset_ids: list[str] = Field(default_factory=list)
    duration_seconds: int = 6
    aspect_ratio: str = "9:16"
    resolution: str = "1080p"
    provider_preference: str | None = None
    session_id: str | None = None
    experimental: bool = True


class CreateVideoJobRequest(VideoGenerationRequest):
    session_id: str


class ProviderCapabilitiesResponse(BaseModel):
    provider: str
    configured: bool
    models: list[str] = Field(default_factory=list)
    operations: list[str] = Field(default_factory=list)
    model_capabilities: list[dict[str, Any]] = Field(default_factory=list)
    advanced_asset_roles: list[str] = Field(default_factory=list)
    limits: dict[str, Any] = Field(default_factory=dict)
    is_mock: bool = False
    reason: str | None = None


class RuntimeProviderSettingsRequest(BaseModel):
    default_image_provider: Literal["openai_gpt_image", "gemini_image"] | None = None
    default_image_model: str | None = Field(default=None, min_length=1, max_length=120)
    openai_image_model: str | None = Field(default=None, min_length=1, max_length=120)
    gemini_image_model: str | None = Field(default=None, min_length=1, max_length=120)
    default_llm_provider: Literal["openai", "anthropic"] | None = None
    default_llm_model: str | None = Field(default=None, min_length=1, max_length=120)
    backup_llm_model: str | None = Field(default=None, min_length=1, max_length=120)
    openai_llm_model: str | None = Field(default=None, min_length=1, max_length=120)
    kimi_llm_model: str | None = Field(default=None, min_length=1, max_length=120)
    image_work_intensity: Literal["swift", "balanced", "studio", "atelier"] | None = None
    openai_api_key: str | None = Field(default=None, max_length=4096)
    openai_base_url: str | None = Field(default=None, max_length=512)
    anthropic_api_key: str | None = Field(default=None, max_length=4096)
    anthropic_base_url: str | None = Field(default=None, max_length=512)
    gemini_image_api_key: str | None = Field(default=None, max_length=4096)
    gemini_image_base_url: str | None = Field(default=None, max_length=512)


class RuntimeProviderSettingsResponse(BaseModel):
    default_image_provider: str
    default_image_model: str
    openai_image_model: str
    gemini_image_model: str
    default_llm_provider: str
    default_llm_model: str
    backup_llm_provider: str
    backup_llm_model: str
    openai_llm_model: str
    kimi_llm_model: str
    image_work_intensity: str
    openai_base_url: str | None = None
    openai_api_key_configured: bool
    anthropic_base_url: str | None = None
    anthropic_api_key_configured: bool
    gemini_image_base_url: str | None = None
    gemini_image_api_key_configured: bool
    provider_notes: dict[str, str] = Field(default_factory=dict)


GenerationJob.model_rebuild()
