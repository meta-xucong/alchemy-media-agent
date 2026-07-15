"""Contracts for V3 Project Mode."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator

from ..public_api_guardrails import reject_low_level_controls
from ..schemas.models import V3BaseModel


PROJECT_API_SOURCE = "V3ProjectModeService"
GENERAL_TEMPLATE_ID = "general_template"
GENERAL_SCENARIO_ID = "general_creative"
ECOMMERCE_TEMPLATE_ID = "ecommerce_template"
PHOTOGRAPHER_TEMPLATE_ID = "photographer_template"


class ProjectModeBase(V3BaseModel):
    """Project Mode public contracts keep low-level controls out."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any):  # type: ignore[override]
        reject_low_level_controls(obj)
        return super().model_validate(obj, *args, **kwargs)


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class TemplateStatus(StrEnum):
    ACTIVE = "active"
    LOCKED = "locked"
    PLACEHOLDER = "placeholder"
    DISABLED = "disabled"
    INACTIVE = "inactive"


class TimelineItemType(StrEnum):
    PROJECT_CREATED = "project_created"
    PROJECT_ARCHIVED = "project_archived"
    REFERENCE_UPLOADED = "reference_uploaded"
    REFERENCE_UPDATED = "reference_updated"
    REFERENCE_REMOVED = "reference_removed"
    JOB_CREATED = "job_created"
    JOB_GENERATED = "job_generated"
    PROVIDER_RETRY = "provider_retry"
    JOB_BLOCKED = "job_blocked"
    VISUAL_REVIEW = "visual_review"
    VISUAL_RETRY = "visual_retry"
    CANDIDATE_SELECTED = "candidate_selected"
    CANDIDATE_UNSELECTED = "candidate_unselected"
    DIRECTION_REJECTED = "direction_rejected"
    BRAND_MEMORY_CONFIRMED = "brand_memory_confirmed"
    STYLE_CONTINUED = "style_continued"
    EXPORT_CREATED = "export_created"
    NOTE_ADDED = "note_added"


class ProjectReferenceSourceType(StrEnum):
    UPLOADED = "uploaded"
    GENERATED_SELECTED = "generated_selected"


class ProjectReferenceStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class ProjectReferenceUsePolicy(StrEnum):
    STYLE = "style"
    COMPOSITION = "composition"
    PRODUCT = "product"
    IDENTITY = "identity"
    PRODUCT_IDENTITY = "product_identity"
    BRAND_ASSET = "brand_asset"
    LIGHTING = "lighting"
    MOOD = "mood"
    GENERAL = "general"


class ProjectFeedbackTargetType(StrEnum):
    PROJECT = "project"
    JOB = "job"
    OUTPUT = "output"
    REFERENCE = "reference"


class ProjectFeedbackType(StrEnum):
    AVOID_DIRECTION = "avoid_direction"
    REMOVE_REFERENCE = "remove_reference"
    PREFER_DIRECTION = "prefer_direction"
    NOTE = "note"


class ProjectFeedbackStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ARCHIVED = "archived"


class ProjectOutputSelectionStateValue(StrEnum):
    SELECTED = "selected"
    UNSELECTED = "unselected"
    REJECTED = "rejected"


class ProjectBrandMemoryProposalMode(StrEnum):
    CREATE = "create"
    APPEND = "append"


class ProjectBrandMemoryProposalStatus(StrEnum):
    DRAFT = "draft"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class OutputRef(V3BaseModel):
    output_ref_id: str
    source_type: str
    project_id: str
    job_id: str | None = None
    asset_id: str | None = None
    candidate_id: str | None = None
    output_id: str | None = None
    preview_url: str | None = None
    thumbnail_url: str | None = None
    download_url: str | None = None
    selection_reason: str | None = None
    selected_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectReferenceAsset(V3BaseModel):
    reference_id: str
    project_id: str
    source_type: ProjectReferenceSourceType
    asset_ref_id: str
    preview_url: str | None = None
    created_at: str
    created_from_job_id: str | None = None
    created_from_output_id: str | None = None
    label: str | None = None
    user_note: str | None = None
    status: ProjectReferenceStatus = ProjectReferenceStatus.ACTIVE
    use_policy: ProjectReferenceUsePolicy = ProjectReferenceUsePolicy.GENERAL
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectFeedbackRecord(V3BaseModel):
    feedback_id: str
    project_id: str
    target_type: ProjectFeedbackTargetType = ProjectFeedbackTargetType.PROJECT
    target_id: str | None = None
    feedback_type: ProjectFeedbackType = ProjectFeedbackType.NOTE
    plain_text: str
    reason_tags: list[str] = Field(default_factory=list)
    created_at: str
    status: ProjectFeedbackStatus = ProjectFeedbackStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectSelectedOutputState(V3BaseModel):
    project_id: str
    job_id: str
    output_id: str
    selection_state: ProjectOutputSelectionStateValue
    selected_at: str | None = None
    unselected_at: str | None = None
    rejected_at: str | None = None
    selection_note: str | None = None
    rejection_note: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectBrandMemoryProposal(V3BaseModel):
    proposal_id: str
    project_id: str
    target_brand_id: str | None = None
    mode: ProjectBrandMemoryProposalMode = ProjectBrandMemoryProposalMode.CREATE
    status: ProjectBrandMemoryProposalStatus = ProjectBrandMemoryProposalStatus.DRAFT
    brand_name_suggestion: str | None = None
    style_summary: str
    keep_notes: list[str] = Field(default_factory=list)
    avoid_notes: list[str] = Field(default_factory=list)
    usage_scenes: list[str] = Field(default_factory=list)
    reference_output_ids: list[str] = Field(default_factory=list)
    reference_asset_ids: list[str] = Field(default_factory=list)
    created_at: str
    confirmed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectCommerceProfile(V3BaseModel):
    project_id: str | None = None
    product_name: str | None = None
    product_category: str | None = None
    target_platform: str | None = None
    target_market: str | None = None
    price_positioning: str | None = None
    target_audience: str | None = None
    core_selling_points: list[str] = Field(default_factory=list)
    must_keep_facts: list[str] = Field(default_factory=list)
    avoid_claims: list[str] = Field(default_factory=list)
    keyword_roots: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    competitor_notes: list[str] = Field(default_factory=list)
    # Explicit garment truth is a product fact, not an E-Commerce recipe.  It
    # must survive the public Project Mode request boundary so the shared
    # constraint ledger, Provider, and pixel reviewer see the same frozen
    # evidence.  An empty value intentionally means that no construction
    # truth was supplied; the runtime must never infer it from a small garment.
    apparel_construction: dict[str, Any] = Field(default_factory=dict)
    # Historical payload-read field. New E-Commerce requests reject it because
    # the remote Brain decides the output set.
    suite_slots_requested: list[str] = Field(default_factory=list)
    updated_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "project_id",
        "product_name",
        "product_category",
        "target_platform",
        "target_market",
        "price_positioning",
        "target_audience",
        "updated_at",
    )
    @classmethod
    def clean_optional_profile_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator(
        "core_selling_points",
        "must_keep_facts",
        "avoid_claims",
        "keyword_roots",
        "keywords",
        "competitor_notes",
        "suite_slots_requested",
    )
    @classmethod
    def clean_profile_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if str(item).strip()]

    @field_validator("apparel_construction")
    @classmethod
    def clean_apparel_construction(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("apparel_construction must be an object when supplied")
        return {str(key).strip(): item for key, item in value.items() if str(key).strip() and item not in (None, "", [], {})}


class ProjectTimelineItem(V3BaseModel):
    timeline_item_id: str
    project_id: str
    item_type: TimelineItemType
    title: str
    summary: str
    job_id: str | None = None
    asset_ids: list[str] = Field(default_factory=list)
    candidate_ids: list[str] = Field(default_factory=list)
    selected_output_refs: list[OutputRef] = Field(default_factory=list)
    created_at: str
    related_job_id: str | None = None
    related_output_ids: list[str] = Field(default_factory=list)
    related_reference_ids: list[str] = Field(default_factory=list)
    visible_to_user: bool = True
    debug_payload: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectContextPackage(V3BaseModel):
    project_id: str
    context_version: str
    goal_summary: str
    template_id: str = GENERAL_TEMPLATE_ID
    linked_brand_id: str | None = None
    confirmed_visual_tone: list[str] = Field(default_factory=list)
    confirmed_color_logic: list[str] = Field(default_factory=list)
    confirmed_layout_logic: list[str] = Field(default_factory=list)
    selected_reference_assets: list[dict[str, Any]] = Field(default_factory=list)
    selected_output_assets: list[OutputRef] = Field(default_factory=list)
    uploaded_reference_assets: list[dict[str, Any]] = Field(default_factory=list)
    selected_visual_references: list[dict[str, Any]] = Field(default_factory=list)
    visual_grammar_snapshot: dict[str, Any] = Field(default_factory=dict)
    strong_reference_bindings: list[dict[str, Any]] = Field(default_factory=list)
    identity_lock_profiles: list[dict[str, Any]] = Field(default_factory=list)
    project_identity_anchors: list[dict[str, Any]] = Field(default_factory=list)
    strong_reference_continuation_plan: dict[str, Any] = Field(default_factory=dict)
    resolved_reference_policy_package: dict[str, Any] = Field(default_factory=dict)
    general_suite_role_plan: dict[str, Any] = Field(default_factory=dict)
    batch_identity_diversity_review: dict[str, Any] = Field(default_factory=dict)
    negative_visual_memory: list[dict[str, Any]] = Field(default_factory=list)
    latest_quality_reviews: list[dict[str, Any]] = Field(default_factory=list)
    latest_auto_retry_decisions: list[dict[str, Any]] = Field(default_factory=list)
    commercial_output_selection: dict[str, Any] = Field(default_factory=dict)
    template_consistency_policy: dict[str, Any] = Field(default_factory=dict)
    confirmed_visual_profile_summary: str | None = None
    visual_continuity_strength: str = "weak"
    required_text_or_facts: list[str] = Field(default_factory=list)
    rejected_style_tags: list[str] = Field(default_factory=list)
    negative_direction_notes: list[str] = Field(default_factory=list)
    negative_visual_directions: list[str] = Field(default_factory=list)
    continuation_instruction: str | None = None
    source_timeline_item_ids: list[str] = Field(default_factory=list)
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectMemorySummary(V3BaseModel):
    project_id: str
    title: str
    goal: str
    # A visible label is not an ownership contract.  Recent-project surfaces
    # need the immutable template identity so a refresh cannot reinterpret a
    # Photography or E-Commerce project as General.
    primary_template_id: str | None = None
    scenario_id: str | None = None
    active_template_label: str = "通用模板"
    latest_thumbnail_urls: list[str] = Field(default_factory=list)
    confirmed_style_chips: list[str] = Field(default_factory=list)
    selected_asset_count: int = 0
    job_count: int = 0
    # This is intentionally only the terminal/active lifecycle state. Recent
    # project cards need to distinguish an in-progress request from a safely
    # blocked one without exposing a prompt, provider payload, or diagnostics.
    latest_job_status: str | None = None
    last_action_label: str = "项目已创建"
    updated_at: str
    next_suggested_actions: list[str] = Field(default_factory=list)


class ProjectRecord(V3BaseModel):
    project_id: str
    title: str
    status: ProjectStatus = ProjectStatus.ACTIVE
    primary_template_id: str = GENERAL_TEMPLATE_ID
    allowed_template_ids: list[str] = Field(default_factory=lambda: [GENERAL_TEMPLATE_ID])
    linked_brand_id: str | None = None
    user_goal: str
    short_summary: str
    confirmed_style_summary: str | None = None
    selected_output_refs: list[OutputRef] = Field(default_factory=list)
    uploaded_asset_refs: list[dict[str, Any]] = Field(default_factory=list)
    rejected_direction_notes: list[str] = Field(default_factory=list)
    timeline_refs: list[str] = Field(default_factory=list)
    job_ids: list[str] = Field(default_factory=list)
    photographer_profile_bindings: dict[str, dict[str, Any]] = Field(default_factory=dict)
    latest_context: ProjectContextPackage | None = None
    reference_assets: list[ProjectReferenceAsset] = Field(default_factory=list)
    feedback_records: list[ProjectFeedbackRecord] = Field(default_factory=list)
    selected_output_states: list[ProjectSelectedOutputState] = Field(default_factory=list)
    brand_memory_proposals: list[ProjectBrandMemoryProposal] = Field(default_factory=list)
    commerce_profile: ProjectCommerceProfile | None = None
    memory_summary: ProjectMemorySummary | None = None
    last_context_built_at: str | None = None
    schema_version: str = "project_mode_v2_context_assets_feedback"
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TemplateCard(V3BaseModel):
    template_id: str
    scenario_id: str
    display_name: str
    status: TemplateStatus
    project_can_create_jobs: bool
    description: str
    primary_action: str
    ui_card: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CreateProjectRequest(ProjectModeBase):
    user_goal: str
    title: str | None = None
    primary_template_id: str = GENERAL_TEMPLATE_ID
    linked_brand_id: str | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_goal")
    @classmethod
    def user_goal_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("user_goal is required")
        return cleaned

    @field_validator("title", "linked_brand_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CreateProjectJobRequest(ProjectModeBase):
    user_input: str | None = None
    template_id: str = GENERAL_TEMPLATE_ID
    photographer_profile_id: str | None = None
    photographer_profile_selection_source: Literal["user_explicit_ui"] | None = None
    uploaded_asset_ids: list[str] = Field(default_factory=list)
    use_project_context: bool = True
    commerce_profile_patch: ProjectCommerceProfile | None = None
    # Historical payload-read field. New E-Commerce requests reject it.
    suite_slot_request: list[str] = Field(default_factory=list)
    advanced_reference_controls: dict[str, bool] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("user_input", "template_id")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        if not cleaned and value is not None:
            raise ValueError("text fields must not be empty")
        return cleaned

    @field_validator("uploaded_asset_ids", "suite_slot_request")
    @classmethod
    def clean_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if str(item).strip()]

    @field_validator("advanced_reference_controls")
    @classmethod
    def clean_advanced_reference_controls(cls, value: dict[str, bool]) -> dict[str, bool]:
        allowed = {
            "preserve_person_identity",
            "preserve_product_appearance",
            "preserve_scene_consistency",
        }
        return {key: bool(value[key]) for key in allowed if key in value}


class EcommerceSlotContinuationRequest(ProjectModeBase):
    """User-directed continuation of one opaque E-Commerce output identity."""

    correction_note: str | None = Field(default=None, max_length=1200)
    new_evidence_asset_ids: list[str] = Field(default_factory=list, max_length=12)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("correction_note")
    @classmethod
    def clean_correction_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("new_evidence_asset_ids")
    @classmethod
    def clean_new_evidence_asset_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if str(item).strip()))


class PhotographyRoleContinuationRequest(ProjectModeBase):
    """User-confirmed continuation of one frozen Photography set role."""

    correction_note: str | None = Field(default=None, max_length=1200)
    new_reference_asset_ids: list[str] = Field(default_factory=list, max_length=12)
    reconfirmed_profile_id: str | None = None
    reconfirmed_profile_version: str | None = None
    reconfirmed_technique_package_checksum: str | None = None
    profile_selection_source: Literal["user_explicit_ui"] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "correction_note",
        "reconfirmed_profile_id",
        "reconfirmed_profile_version",
        "reconfirmed_technique_package_checksum",
    )
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("new_reference_asset_ids")
    @classmethod
    def clean_new_reference_asset_ids(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if str(item).strip()))


class ProjectReferenceRequest(ProjectModeBase):
    asset_ref_id: str
    source_type: ProjectReferenceSourceType = ProjectReferenceSourceType.UPLOADED
    label: str | None = None
    user_note: str | None = None
    use_policy: ProjectReferenceUsePolicy = ProjectReferenceUsePolicy.GENERAL
    created_from_job_id: str | None = None
    created_from_output_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("asset_ref_id")
    @classmethod
    def asset_ref_id_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("asset_ref_id is required")
        return cleaned

    @field_validator("label", "user_note", "created_from_job_id", "created_from_output_id")
    @classmethod
    def clean_optional_reference_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectReferenceUpdateRequest(ProjectModeBase):
    label: str | None = None
    user_note: str | None = None
    status: ProjectReferenceStatus | None = None
    use_policy: ProjectReferenceUsePolicy | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("label", "user_note")
    @classmethod
    def clean_optional_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectFeedbackRequest(ProjectModeBase):
    target_type: ProjectFeedbackTargetType = ProjectFeedbackTargetType.PROJECT
    target_id: str | None = None
    feedback_type: ProjectFeedbackType = ProjectFeedbackType.NOTE
    plain_text: str
    reason_tags: list[str] = Field(default_factory=list)
    status: ProjectFeedbackStatus = ProjectFeedbackStatus.ACTIVE
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("plain_text")
    @classmethod
    def plain_text_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("plain_text is required")
        return cleaned

    @field_validator("target_id")
    @classmethod
    def clean_optional_target_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectOutputStateRequest(ProjectModeBase):
    plain_text: str | None = None
    reason_tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("plain_text")
    @classmethod
    def clean_optional_plain_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectBrandMemoryProposalRequest(ProjectModeBase):
    target_brand_id: str | None = None
    mode: ProjectBrandMemoryProposalMode = ProjectBrandMemoryProposalMode.CREATE
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_brand_id")
    @classmethod
    def clean_optional_target_brand_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class ProjectBrandMemoryConfirmRequest(ProjectModeBase):
    proposal_id: str
    edited_brand_name: str | None = None
    edited_style_summary: str
    edited_keep_notes: list[str] = Field(default_factory=list)
    edited_avoid_notes: list[str] = Field(default_factory=list)
    edited_usage_scenes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("proposal_id", "edited_style_summary")
    @classmethod
    def required_text_must_not_be_empty(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("required text fields must not be empty")
        return cleaned

    @field_validator("edited_brand_name")
    @classmethod
    def clean_optional_brand_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("edited_keep_notes", "edited_avoid_notes", "edited_usage_scenes")
    @classmethod
    def clean_text_list(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class ProjectResponse(V3BaseModel):
    api_namespace: str
    route: str
    project: ProjectRecord | None = None
    templates: list[TemplateCard] = Field(default_factory=list)
    context: ProjectContextPackage | None = None
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectListResponse(V3BaseModel):
    api_namespace: str
    route: str
    total: int
    limit: int
    projects: list[ProjectMemorySummary] = Field(default_factory=list)
    templates: list[TemplateCard] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectTimelineResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    total: int
    items: list[ProjectTimelineItem] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectReferenceResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    reference: ProjectReferenceAsset
    project: ProjectRecord
    context: ProjectContextPackage | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectFeedbackResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    feedback: ProjectFeedbackRecord
    project: ProjectRecord
    context: ProjectContextPackage | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectBrandMemoryProposalResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    proposal: ProjectBrandMemoryProposal
    project: ProjectRecord
    context: ProjectContextPackage | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ProjectBrandMemoryConfirmResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    brand_id: str
    memory_update_applied: bool = True
    updated_at: str
    plain_summary: str
    proposal: ProjectBrandMemoryProposal
    project: ProjectRecord
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceSlotLineage(V3BaseModel):
    schema_version: str = "ecommerce_slot_lineage_v1"
    root_job_id: str
    parent_job_id: str | None = None
    parent_slot_id: str | None = None
    continuation_kind: str
    continuation_correction_note: str | None = None
    new_evidence_asset_ids: list[str] = Field(default_factory=list)
    capability_activation_plan_id: str
    plan_amendment_id: str | None = None
    created_at: str


class EcommerceSlotAttemptSummary(V3BaseModel):
    job_id: str
    parent_job_id: str | None = None
    status: str
    candidate_ids: list[str] = Field(default_factory=list)
    output_ids: list[str] = Field(default_factory=list)
    created_at: str | None = None
    is_current_delivery: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceSlotCurrentDelivery(V3BaseModel):
    root_job_id: str
    slot_id: str
    job_id: str
    candidate_id: str
    asset_id: str | None = None
    output_id: str | None = None
    preview_url: str | None = None
    download_url: str | None = None
    resolved_at: str


class EcommerceSlotDeliveryResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    root_job_id: str
    slot_id: str
    current_delivery: EcommerceSlotCurrentDelivery | None = None
    attempts: list[EcommerceSlotAttemptSummary] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EcommerceSlotContinuationResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    parent_job_id: str
    slot_id: str
    child_job_id: str
    child_status: str
    lineage: EcommerceSlotLineage
    delivery: EcommerceSlotDeliveryResponse
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyRoleLineage(V3BaseModel):
    schema_version: str = "photography_role_lineage_v1"
    root_job_id: str
    parent_job_id: str | None = None
    parent_role_id: str | None = None
    root_set_id: str
    continuation_kind: str
    continuation_correction_note: str | None = None
    new_reference_asset_ids: list[str] = Field(default_factory=list)
    capability_activation_plan_id: str
    plan_amendment_id: str | None = None
    created_at: str


class PhotographyRoleAttemptSummary(V3BaseModel):
    job_id: str
    parent_job_id: str | None = None
    status: str
    candidate_ids: list[str] = Field(default_factory=list)
    output_ids: list[str] = Field(default_factory=list)
    created_at: str | None = None
    is_current_delivery: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyRoleCurrentDelivery(V3BaseModel):
    root_job_id: str
    root_set_id: str
    role_id: str
    job_id: str
    candidate_id: str
    asset_id: str | None = None
    output_id: str | None = None
    preview_url: str | None = None
    download_url: str | None = None
    resolved_at: str


class PhotographyRoleDeliveryResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    root_job_id: str
    root_set_id: str
    role_id: str
    current_delivery: PhotographyRoleCurrentDelivery | None = None
    attempts: list[PhotographyRoleAttemptSummary] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyRoleContinuationResponse(V3BaseModel):
    api_namespace: str
    route: str
    project_id: str
    parent_job_id: str
    role_id: str
    child_job_id: str
    child_status: str
    lineage: PhotographyRoleLineage
    delivery: PhotographyRoleDeliveryResponse
    metadata: dict[str, Any] = Field(default_factory=dict)
