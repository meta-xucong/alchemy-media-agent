from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


RunStatus = Literal[
    "created",
    "planning",
    "retrieving_cases",
    "composing_prompt",
    "safety_checking",
    "generating",
    "reviewing",
    "completed",
    "failed",
    "cancelled",
    "blocked_by_policy",
    "waiting_for_user",
]
SyncStatus = Literal[
    "queued",
    "fetching",
    "parsing",
    "classifying",
    "indexing",
    "validating",
    "publishing",
    "completed",
    "failed",
    "partially_completed",
    "skipped_no_change",
]
SafetyDecisionValue = Literal["allow", "allow_with_warning", "transform_required", "blocked", "need_user_confirmation"]
AssetRole = Literal[
    "style_reference",
    "subject_reference",
    "logo_reference",
    "face_reference",
    "background_reference",
    "composition_reference",
    "color_reference",
    "negative_reference",
]
ConstraintStrength = Literal["required", "strong", "soft"]


class AssetContentUploadRequest(BaseModel):
    content_base64: str
    mime_type: str | None = None


class CreateUploadedAssetRequest(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    role: AssetRole | None = None
    constraint_strength: ConstraintStrength = "strong"
    intended_use: str | None = None


class CreateUploadedAssetResponse(BaseModel):
    asset_id: str
    upload_url: str
    headers: dict[str, str] = Field(default_factory=dict)


class AssetBrief(BaseModel):
    asset_id: str
    role: AssetRole
    constraint_strength: ConstraintStrength = "strong"
    visual_summary: str = ""
    identity_requirements: list[str] = Field(default_factory=list)
    style_signals: list[str] = Field(default_factory=list)
    detected_text: list[dict[str, Any]] = Field(default_factory=list)
    image: dict[str, Any] = Field(default_factory=dict)
    palette: list[dict[str, Any]] = Field(default_factory=list)
    composition: dict[str, Any] = Field(default_factory=dict)
    usable_as_input_image: bool = True
    provider_input_required: bool = False
    warnings: list[str] = Field(default_factory=list)


class UploadedAsset(BaseModel):
    asset_id: str
    filename: str
    mime_type: str
    size_bytes: int
    veyra_user_id: int | None = None
    status: Literal["upload_requested", "stored", "ready", "rejected", "failed"] = "upload_requested"
    role: AssetRole | None = None
    constraint_strength: ConstraintStrength = "strong"
    intended_use: str | None = None
    upload_url: str | None = None
    source_url: str | None = None
    thumbnail_url: str | None = None
    storage_path: str | None = None
    brief: AssetBrief | None = None
    error: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CreativeRunAssetInput(BaseModel):
    asset_id: str
    role: AssetRole | None = None
    constraint_strength: ConstraintStrength | None = None
    notes: str | None = None


class TemplateLockContract(BaseModel):
    contract_id: str
    locked_case_id: str
    priority: Literal["highest"] = "highest"
    locked_elements: list[str] = Field(default_factory=list)
    replaceable_slots: list[str] = Field(default_factory=list)
    conflict_policy: str = "preserve_template_structure_bind_assets_to_slots"
    summary: str = ""


class AssetBinding(BaseModel):
    asset_id: str
    role: AssetRole
    constraint_strength: ConstraintStrength = "strong"
    binding_slot: str
    fusion_mode: str = "reference"
    placement_intent: dict[str, Any] = Field(default_factory=dict)
    target_surface: str | None = None
    allowed_to_override: list[str] = Field(default_factory=list)
    not_allowed_to_override: list[str] = Field(default_factory=list)
    provider_input_required: bool = False
    prompt_instruction: str = ""
    conflict_resolution: str | None = None
    review_expectations: list[str] = Field(default_factory=list)


class AssetBindingPlan(BaseModel):
    plan_id: str
    template_lock_contract_id: str | None = None
    mode: Literal["template_lock", "free_agent"] = "free_agent"
    bindings: list[AssetBinding] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    provider_input_plan: dict[str, Any] = Field(default_factory=dict)


class ProviderInputImage(BaseModel):
    asset_id: str
    role: AssetRole
    constraint_strength: ConstraintStrength = "strong"
    source_url: str | None = None
    mime_type: str | None = None
    provider_input_required: bool = False
    prompt_instruction: str = ""
    fusion_mode: str = "reference"
    placement_intent: dict[str, Any] = Field(default_factory=dict)
    target_surface: str | None = None
    review_expectations: list[str] = Field(default_factory=list)


class HealthIsolation(BaseModel):
    api_prefix: str
    db_namespace: str
    redis_prefix: str
    storage_prefix: str
    trace_project: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    agent_runtime: str
    agents_sdk_available: bool
    isolation: HealthIsolation


class ResourceProvider(BaseModel):
    provider_id: str
    provider_type: str
    source_uri: str
    display_name: str
    enabled: bool = True
    manifest: dict[str, Any] = Field(default_factory=dict)
    last_sync_at: datetime | None = None
    active_index_version: str | None = None


class ProviderSyncRun(BaseModel):
    sync_run_id: str
    provider_id: str
    status: SyncStatus
    source_version: str | None = None
    stats: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] | None = None
    started_at: datetime
    finished_at: datetime | None = None


class LicensePolicy(BaseModel):
    template_reuse_allowed: bool = True
    raw_image_final_use_allowed: bool = False
    commercial_use_status: str = "requires_case_level_safety_check"


class PromptCaseSummary(BaseModel):
    case_id: str
    index_version: str | None = None
    title: str
    category: str
    summary: str = ""
    preview_url: str | None = None
    style_tags: list[str] = Field(default_factory=list)
    use_case_tags: list[str] = Field(default_factory=list)
    risk_tags: list[str] = Field(default_factory=list)
    profile_tags: list[str] = Field(default_factory=list)
    score: float | None = None
    why_selected: str | None = None


class CaseProfile(BaseModel):
    source: Literal["rules", "claude-code"] = "rules"
    model: str | None = None
    subject_tags: list[str] = Field(default_factory=list)
    style_tags: list[str] = Field(default_factory=list)
    use_case_tags: list[str] = Field(default_factory=list)
    material_tags: list[str] = Field(default_factory=list)
    color_tags: list[str] = Field(default_factory=list)
    lighting_tags: list[str] = Field(default_factory=list)
    composition_tags: list[str] = Field(default_factory=list)
    reusable_principles: list[str] = Field(default_factory=list)
    suitable_for: list[str] = Field(default_factory=list)
    caution_tags: list[str] = Field(default_factory=list)


class PromptCase(PromptCaseSummary):
    provider_id: str
    index_version: str
    source_url: str
    raw_prompt: str
    prompt_atoms: dict[str, Any] = Field(default_factory=dict)
    visual_features: dict[str, Any] = Field(default_factory=dict)
    license_policy: LicensePolicy = Field(default_factory=LicensePolicy)
    quality_score: float = 0.5
    is_active: bool = True


class SearchPromptCasesRequest(BaseModel):
    query_text: str = ""
    category_filters: list[str] = Field(default_factory=list)
    style_filters: list[str] = Field(default_factory=list)
    use_case_filters: list[str] = Field(default_factory=list)
    risk_filters: list[str] = Field(default_factory=list)
    limit: int = Field(default=10, ge=1, le=1000)
    diversity_level: Literal["low", "medium", "high"] = "medium"


class SearchPromptCasesResponse(BaseModel):
    cases: list[PromptCaseSummary]
    ranking_explanation: str
    index_version: str | None


class SafetyDecision(BaseModel):
    decision_id: str
    scope: str
    decision: SafetyDecisionValue
    reasons: list[str] = Field(default_factory=list)
    blocked_terms: list[str] = Field(default_factory=list)
    required_transforms: list[str] = Field(default_factory=list)
    user_confirmation_required: bool = False
    commercial_use_status: str = "allowed_after_generation_review"


class ImagePromptPlan(BaseModel):
    plan_id: str
    mode: Literal["template_customize", "smart_enhance", "revision", "batch"]
    prompt: str
    negative_prompt: str = ""
    style_basis: list[dict[str, Any]] = Field(default_factory=list)
    user_variables: dict[str, Any] = Field(default_factory=dict)
    provider_parameters: dict[str, Any] = Field(default_factory=dict)
    risk_notes: list[str] = Field(default_factory=list)
    explanation: str = ""


class ImageReviewDecision(BaseModel):
    review_id: str
    output_id: str
    decision: Literal["pass", "needs_review", "retry_recommended", "failed"]
    score: float = Field(default=0.5, ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
    detected_risks: list[str] = Field(default_factory=list)
    revision_directives: list[str] = Field(default_factory=list)
    reviewer: str = "rule-reviewer"
    analysis_mode: str = "metadata_rules"
    agent_trace_id: str | None = None
    created_at: datetime


class CaseRetrievalPlan(BaseModel):
    query_text: str
    category_filters: list[str] = Field(default_factory=list)
    use_case_filters: list[str] = Field(default_factory=list)
    style_filters: list[str] = Field(default_factory=list)
    risk_filters: list[str] = Field(default_factory=list)
    limit: int = 6
    diversity_level: Literal["low", "medium", "high"] = "medium"


class StageCommand(BaseModel):
    stage: Literal["retrieve_cases", "compose_prompt", "safety_check", "generate", "review_outputs"]
    action: str = "run"
    priority: int = Field(default=50, ge=0, le=100)
    reason: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)


class PromptDirectives(BaseModel):
    visual_strategy: str = ""
    case_selection_rationale: str = ""
    reusable_prompt_atoms: list[str] = Field(default_factory=list)
    composition: str | None = None
    lighting: str | None = None
    color_palette: str | None = None
    negative_prompt_additions: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)


class OrchestratorTaskIntent(BaseModel):
    primary_relationship: Literal[
        "no_uploaded_assets",
        "replace_template_subject",
        "replace_template_food_subject",
        "extract_composite_content",
        "fill_template_slots",
        "free_reference",
    ] = "free_reference"
    target_surface: str | None = None
    target_label: str | None = None
    uploaded_asset_role: str | None = None
    fusion_mode: str | None = None
    content_extraction: bool | None = None
    template_slot_replacement: bool | None = None
    provider_input_required: bool | None = None
    visible_text_language: str | None = None
    visible_text_policy: str | None = None
    prompt_directive: str | None = None
    negative_prompt_additions: list[str] = Field(default_factory=list)
    review_expectations: list[str] = Field(default_factory=list)
    rationale: str | None = None


class CreativeOrchestratorDecision(BaseModel):
    decision_id: str
    provider: str = "deterministic-fallback"
    mode: Literal["template_customize", "smart_enhance", "revision", "batch"]
    selected_case_ids: list[str] = Field(default_factory=list)
    case_retrieval_plan: CaseRetrievalPlan
    final_prompt: str = ""
    negative_prompt: str = ""
    provider_parameters: dict[str, Any] = Field(default_factory=dict)
    prompt_rationale: str = ""
    prompt_directives: PromptDirectives = Field(default_factory=PromptDirectives)
    task_intent: OrchestratorTaskIntent | None = None
    stage_commands: list[StageCommand] = Field(default_factory=list)
    generation_directives: dict[str, Any] = Field(default_factory=dict)
    quality_gates: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    fallback_reason: str | None = None
    invocation_status: str = "unknown"
    latency_ms: int | None = None
    attempts: int = Field(default=1, ge=0)
    cache_hit: bool = False
    cache_key: str | None = None
    workspace_id: str | None = None
    claude_stage_trace: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime


class OrchestratorInvocationRecord(BaseModel):
    invocation_id: str
    provider: str
    status: str
    fallback_reason: str | None = None
    latency_ms: int | None = None
    attempts: int = 0
    cache_hit: bool = False
    cache_key: str | None = None
    workspace_id: str | None = None
    selected_case_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class OrchestratorStatusResponse(BaseModel):
    enabled: bool
    cli: str
    model: str | None = None
    multimodal_model: str | None = None
    tools: str
    fallback_model: str | None = None
    cache_enabled: bool
    cache_entries: int
    max_attempts: int
    timeout_seconds: float | None = None
    max_output_tokens: int | None = None
    checkpoint_enabled: bool = False
    fallback_models: list[str] = Field(default_factory=list)
    fallback_base_url_configured: bool = False
    fallback_auth_token_configured: bool = False
    recent_invocations: list[OrchestratorInvocationRecord] = Field(default_factory=list)
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    average_latency_ms: int | None = None


class V2RuntimeModelSettingsResponse(BaseModel):
    image_generation_provider: str
    openai_image_model: str
    openai_api_key_configured: bool = False
    openai_base_url_configured: bool = False
    doubao_image_model: str
    doubao_image_api_key_configured: bool = False
    doubao_image_base_url_configured: bool = False
    gemini_image_model: str
    gemini_api_key_configured: bool = False
    gemini_base_url_configured: bool = False
    default_agent_model: str
    output_review_agent_enabled: bool
    output_review_agent_model: str | None = None
    claude_orchestrator_enabled: bool
    claude_orchestrator_cli: str
    claude_orchestrator_model: str | None = None
    claude_orchestrator_multimodal_model: str | None = None
    claude_orchestrator_fallback_model: str | None = None
    claude_orchestrator_effort: str
    claude_orchestrator_tools: str
    claude_orchestrator_timeout_seconds: float
    claude_orchestrator_max_output_tokens: int
    claude_checkpoint_orchestrator_enabled: bool = False
    claude_orchestrator_fallback_models: list[str] = Field(default_factory=list)
    claude_orchestrator_fallback_base_url_configured: bool = False
    claude_orchestrator_fallback_auth_token_configured: bool = False
    case_intelligence_provider: Literal["rules", "claude-code"]
    case_intelligence_model: str | None = None
    persisted: bool = False


class V2RuntimeModelSettingsRequest(BaseModel):
    image_generation_provider: str | None = Field(default=None, max_length=80)
    openai_image_model: str | None = Field(default=None, max_length=120)
    doubao_image_model: str | None = Field(default=None, max_length=120)
    gemini_image_model: str | None = Field(default=None, max_length=120)
    default_agent_model: str | None = Field(default=None, max_length=120)
    output_review_agent_enabled: bool | None = None
    output_review_agent_model: str | None = Field(default=None, max_length=120)
    claude_orchestrator_enabled: bool | None = None
    claude_orchestrator_model: str | None = Field(default=None, max_length=120)
    claude_orchestrator_multimodal_model: str | None = Field(default=None, max_length=120)
    claude_orchestrator_fallback_model: str | None = Field(default=None, max_length=120)
    claude_orchestrator_effort: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    claude_orchestrator_tools: str | None = Field(default=None, max_length=80)
    claude_checkpoint_orchestrator_enabled: bool | None = None
    case_intelligence_provider: Literal["rules", "claude-code"] | None = None
    case_intelligence_model: str | None = Field(default=None, max_length=120)


class VeyraBillingRule(BaseModel):
    key: str
    label: str = ""
    agent: str = "alchemy"
    version: str = ""
    enabled: bool
    charge_amount: float
    source: str = "alchemy"


class VeyraBillingSettingsResponse(BaseModel):
    enabled: bool
    charge_amount: float
    rules: list[VeyraBillingRule] = Field(default_factory=list)
    currency_label: str = "sub2api_balance"
    persisted: bool = False


class VeyraBillingRuleUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=120)
    label: str | None = Field(default=None, max_length=120)
    enabled: bool | None = None
    charge_amount: float | None = Field(default=None, ge=0, le=100000)


class VeyraBillingSettingsRequest(BaseModel):
    enabled: bool | None = None
    charge_amount: float | None = Field(default=None, ge=0, le=100000)
    rule_key: str | None = Field(default=None, max_length=120)
    rules: list[VeyraBillingRuleUpdate] | None = None


class CreateCreativeRunRequest(BaseModel):
    user_prompt: str = ""
    mode_hint: Literal["template_customize", "smart_enhance", "revision", "batch"] | None = None
    template_case_id: str | None = None
    assets: list[str | CreativeRunAssetInput] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    veyra_user_id: int | None = None

    @model_validator(mode="after")
    def normalize_and_validate(self) -> "CreateCreativeRunRequest":
        self.user_prompt = str(self.user_prompt or "").strip()
        self.template_case_id = str(self.template_case_id or "").strip() or None
        has_assets = bool(self.assets)
        if not self.user_prompt and not self.template_case_id and not has_assets:
            raise ValueError("请先填写提示词，或选择模板/上传素材。")
        self.output = _normalize_run_output(self.output)
        return self


class CreateRevisionRunRequest(BaseModel):
    feedback: str = ""
    provider_hint: str | None = None
    output: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_output_defaults(self) -> "CreateRevisionRunRequest":
        self.output = _normalize_run_output(self.output)
        return self


def _normalize_run_output(value: dict[str, Any] | None) -> dict[str, Any]:
    output = dict(value or {})
    try:
        count = int(output.get("count", 1))
    except Exception:
        count = 1
    output["count"] = max(1, min(count, 8))
    return output


class ImageOutput(BaseModel):
    output_id: str
    job_id: str
    url: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    score: dict[str, Any] = Field(default_factory=dict)
    review: ImageReviewDecision | None = None
    selected_by_user: bool = False
    created_at: datetime


class ImageHistoryItem(BaseModel):
    output_id: str
    job_id: str
    run_id: str | None = None
    status: str = "completed"
    provider_id: str
    model: str
    mode: str | None = None
    template_case_id: str | None = None
    prompt: str
    url: str
    thumbnail_url: str | None = None
    preview_url: str | None = None
    score: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    veyra_legacy_public: bool = False
    record_label: str | None = None
    can_delete: bool = False
    favorite: bool = False
    created_at: datetime
    updated_at: datetime


class ImageHistoryResponse(BaseModel):
    items: list[ImageHistoryItem]
    total: int


class FavoriteImageRequest(BaseModel):
    favorite: bool = True


class FavoriteReferenceAssetRequest(BaseModel):
    role: AssetRole = "composition_reference"
    constraint_strength: ConstraintStrength = "required"
    intended_use: str | None = "continue_modifying_selected_favorite_image"
    notes: str | None = None


class ImageJob(BaseModel):
    job_id: str
    run_id: str | None = None
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    provider_id: str
    model: str
    prompt_plan: ImagePromptPlan
    outputs: list[ImageOutput] = Field(default_factory=list)
    error: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class CreativeRun(BaseModel):
    run_id: str
    status: RunStatus
    mode: Literal["template_customize", "smart_enhance", "revision", "batch"]
    intent_summary: str
    case_retrieval_plan: CaseRetrievalPlan | None = None
    selected_cases: list[PromptCaseSummary] = Field(default_factory=list)
    prompt_plan: ImagePromptPlan | None = None
    safety_decision: SafetyDecision | None = None
    orchestrator_decision: CreativeOrchestratorDecision | None = None
    generation_jobs: list[ImageJob] = Field(default_factory=list)
    trace_id: str
    next_actions: list[str] = Field(default_factory=list)
    progress_events: list[dict[str, Any]] = Field(default_factory=list)
    progress_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CreateImageJobRequest(BaseModel):
    run_id: str | None = None
    prompt_plan: ImagePromptPlan
    provider_hint: str | None = None
    input_images: list[ProviderInputImage] = Field(default_factory=list)
    veyra_user_id: int | None = None


class CreateFeedbackRequest(BaseModel):
    feedback_type: Literal["selected", "downloaded", "liked", "disliked", "revise", "report_issue"]
    payload: dict[str, Any] = Field(default_factory=dict)


class FeedbackEvent(BaseModel):
    feedback_id: str
    output_id: str
    feedback_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ErrorResponse(BaseModel):
    error_code: str
    message: str
    retryable: bool = False
    user_visible: bool = True
    safe_fallback: str | None = None
