"""Module-local contracts for the inactive Photography P1 skeleton."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator, model_validator

from ...schemas.models import V3BaseModel
from ...shared_capabilities.activation import CapabilityContribution


GENERAL_PHOTOGRAPHY_PROFILE_ID = "general_photography"


class PhotographyInputMode(StrEnum):
    TEXT_TO_PHOTO = "text_to_photo"
    REFERENCE_TO_PROFESSIONAL_RESHOOT = "reference_to_professional_reshoot"


class PhotographyDeliveryMode(StrEnum):
    SINGLE_HERO = "single_hero"
    PROFESSIONAL_SET = "professional_set"


class PhotographyReshootStrength(StrEnum):
    FAITHFUL = "faithful"
    PROFESSIONAL_RESHOOT = "professional_reshoot"
    CREATIVE_REINTERPRETATION = "creative_reinterpretation"


class PhotographySceneDomain(StrEnum):
    GENERAL = "general"
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    STILL_LIFE = "still_life"
    ANIMAL = "animal"


class PhotographyCommissionIntent(StrEnum):
    SINGLE_HERO = "single_hero"
    PROFESSIONAL_SESSION = "professional_session"
    EDITORIAL_STORY = "editorial_story"
    COMMERCIAL_IMAGE = "commercial_image"
    ENVIRONMENTAL_PORTRAIT = "environmental_portrait"
    DOCUMENTARY_MOMENT = "documentary_moment"
    FINE_ART_STUDY = "fine_art_study"
    REFERENCE_RESHOOT = "reference_reshoot"


class PhotographerProfileSelectionSource(StrEnum):
    USER_EXPLICIT_UI = "user_explicit_ui"


class PhotographerProfileKind(StrEnum):
    GENERAL = "general"
    TECHNIQUE_ARCHETYPE = "technique_archetype"
    NAMED_PHOTOGRAPHER = "named_photographer"


class PhotographerProfileRightsStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    APPROVED = "approved"
    APPROVED_WITH_CONSTRAINTS = "approved_with_constraints"
    PENDING_REVIEW = "pending_review"
    DISABLED = "disabled"


class PhotographerProfileAvailability(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    REGION_RESTRICTED = "region_restricted"
    SUSPENDED = "suspended"


class PhotographyTechniquePackage(V3BaseModel):
    """Structured photographic technique DNA; never a raw prompt patch."""

    composition: list[str] = Field(default_factory=list)
    camera_relation: list[str] = Field(default_factory=list)
    depth_and_focus: list[str] = Field(default_factory=list)
    motion_treatment: list[str] = Field(default_factory=list)
    lighting: list[str] = Field(default_factory=list)
    exposure_and_tone: list[str] = Field(default_factory=list)
    color_response: list[str] = Field(default_factory=list)
    texture_and_grain: list[str] = Field(default_factory=list)
    subject_direction: list[str] = Field(default_factory=list)
    retouch_finish: list[str] = Field(default_factory=list)
    forbidden_techniques: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographerProfile(V3BaseModel):
    profile_id: str
    profile_version: str = "v1"
    profile_kind: PhotographerProfileKind
    public_display_name: str
    public_description: str = ""
    supported_scene_ids: list[str] = Field(default_factory=list)
    supported_commission_ids: list[str] = Field(default_factory=list)
    technique_package: PhotographyTechniquePackage = Field(default_factory=PhotographyTechniquePackage)
    rights_status: PhotographerProfileRightsStatus = PhotographerProfileRightsStatus.PENDING_REVIEW
    availability_status: PhotographerProfileAvailability = PhotographerProfileAvailability.INACTIVE
    allowed_regions: list[str] = Field(default_factory=list)
    effective_from: str | None = None
    effective_until: str | None = None
    source_provenance: list[dict[str, Any]] = Field(default_factory=list)
    review_owner: str | None = None
    reviewed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("profile_id", "profile_version", "public_display_name")
    @classmethod
    def non_empty_profile_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("photographer profile identifiers and display name must not be empty")
        return cleaned

    @model_validator(mode="after")
    def general_profile_has_no_named_rights_claim(self) -> "PhotographerProfile":
        if self.profile_kind == PhotographerProfileKind.GENERAL:
            if self.profile_id != GENERAL_PHOTOGRAPHY_PROFILE_ID:
                raise ValueError("the general profile must use the reserved general_photography ID")
            if self.rights_status != PhotographerProfileRightsStatus.NOT_APPLICABLE:
                raise ValueError("the general profile must use rights_status=not_applicable")
        return self


class PhotographyUserControls(V3BaseModel):
    """Photography-owned controls before a future shared API integration."""

    input_mode: PhotographyInputMode = PhotographyInputMode.TEXT_TO_PHOTO
    delivery_mode: PhotographyDeliveryMode = PhotographyDeliveryMode.SINGLE_HERO
    reshoot_strength: PhotographyReshootStrength | None = None
    explicit_scene_id: str | None = None
    preservation_controls: dict[str, str] = Field(default_factory=dict)
    photographer_profile_id: str | None = None
    photographer_profile_selection_source: PhotographerProfileSelectionSource | None = None
    output_count: int = Field(default=1, ge=1, le=8)
    aspect_ratio: str | None = None
    advanced_controls: dict[str, Any] = Field(default_factory=dict)

    @field_validator("explicit_scene_id", "photographer_profile_id", "aspect_ratio")
    @classmethod
    def clean_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def named_profile_requires_explicit_ui_selection(self) -> "PhotographyUserControls":
        profile_id = self.photographer_profile_id
        if profile_id in {None, GENERAL_PHOTOGRAPHY_PROFILE_ID}:
            if self.photographer_profile_selection_source is not None:
                raise ValueError("General Photography must not carry a named-profile selection source")
            return self
        if self.photographer_profile_selection_source != PhotographerProfileSelectionSource.USER_EXPLICIT_UI:
            raise ValueError("named_profile_requires_explicit_ui_selection")
        return self

    @model_validator(mode="after")
    def reshoot_strength_matches_input_mode(self) -> "PhotographyUserControls":
        if self.input_mode == PhotographyInputMode.TEXT_TO_PHOTO and self.reshoot_strength is not None:
            raise ValueError("reshoot_strength requires a reference-conditioned input mode")
        return self


class PhotographerProfileBinding(V3BaseModel):
    binding_mode: str
    profile_id: str
    profile_version: str
    selection_source: PhotographerProfileSelectionSource | None = None
    catalog_version: str
    availability_decision: str
    technique_package_checksum: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyBrief(V3BaseModel):
    """Module-local interpretation of a Photography request."""

    brief_id: str
    job_key: str
    subject_entities: list[str] = Field(default_factory=list)
    scene_domain: PhotographySceneDomain
    commission_intent: PhotographyCommissionIntent
    audience_and_use: str = "direct professional photographic use"
    story_or_emotional_goal: str | None = None
    location_and_environment: str | None = None
    wardrobe_prop_and_set_needs: list[str] = Field(default_factory=list)
    moment_and_subject_direction: list[str] = Field(default_factory=list)
    delivery_roles: list[str] = Field(default_factory=list)
    reference_policy_summary: dict[str, Any] = Field(default_factory=dict)
    profile_binding_summary: dict[str, Any] = Field(default_factory=dict)
    unknown_requirements: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotoShotSpec(V3BaseModel):
    """Structured specification for one planned Photography output."""

    shot_id: str
    role: str
    sequence_index: int = Field(default=1, ge=1)
    subject_and_decisive_moment: str
    framing_and_crop: str
    camera_position_and_perspective_effect: str
    depth_and_focus_behavior: str
    motion_behavior: str
    lighting_map_and_exposure_key: str
    palette_and_tone_curve: str
    surface_texture_and_grain: str
    subject_direction: str
    retouch_direction: str
    immutable_reference_truth: list[str] = Field(default_factory=list)
    allowed_changes: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)
    review_profile: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyReviewReport(V3BaseModel):
    """Metadata-only review profile for a planned Photography job."""

    review_id: str
    status: str = "ready"
    checks: list[dict[str, Any]] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    retryable_issue_codes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyPackOutput(V3BaseModel):
    """Planning-only Photography output before production registration exists."""

    profile_binding: PhotographerProfileBinding
    brief: PhotographyBrief
    technique_contributions: list[CapabilityContribution] = Field(default_factory=list)
    scene_contributions: list[CapabilityContribution] = Field(default_factory=list)
    shot_specs: list[PhotoShotSpec] = Field(default_factory=list)
    review: PhotographyReviewReport
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographySceneDirectorDescriptor(V3BaseModel):
    scene_id: str
    capability_id: str
    display_name: str
    status: str = "inactive"
    activation_ready: bool = False
    supported_commission_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PhotographyTechniqueModuleDescriptor(V3BaseModel):
    capability_id: str
    display_name: str
    status: str = "inactive"
    activation_ready: bool = False
    dependencies: list[str] = Field(default_factory=list)
    contribution_stages: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
