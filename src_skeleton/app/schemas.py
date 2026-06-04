from __future__ import annotations

from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field


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
    risks: list[str] = Field(default_factory=list)


class CreateAssetUploadRequest(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    consent: dict[str, Any]


class CreateAssetUploadResponse(BaseModel):
    asset_id: str
    upload_url: str
    headers: dict[str, str] = Field(default_factory=dict)


class Asset(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int
    status: Literal["uploaded", "scanning", "extracting", "analyzed", "ready", "failed", "rejected"]
    upload_url: str | None = None
    thumbnail_url: str | None = None
    material_brief: MaterialBrief | None = None
    consent: dict[str, Any] = Field(default_factory=dict)
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
    size: str = "1024x1024"
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
    provider_preference: str | None = None
    idempotency_key: str | None = None
    trace_id: str | None = None
    source_output_id: str | None = None


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
    version_parent_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationJob(BaseModel):
    id: str
    session_id: str | None = None
    job_type: Literal["image", "video"]
    status: JobStatus
    provider: str | None = None
    model: str | None = None
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
    work_intensity: Literal["swift", "balanced", "studio", "atelier"] | None = None
    work_intensity_label: str | None = None
    prompt: str | None = None
    size: str | None = None
    version_parent_id: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    source: Literal["repository", "manifest"] = "repository"


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
    prompt: str
    asset_ids: list[str] = Field(default_factory=list)
    count: int = Field(default=1, ge=1, le=10)
    size: str = "1024x1024"
    quality: Literal["low", "medium", "high", "auto"] = "auto"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    work_intensity: Literal["swift", "balanced", "studio", "atelier"] | None = None
    provider_preference: str | None = None
    idempotency_key: str | None = None


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
