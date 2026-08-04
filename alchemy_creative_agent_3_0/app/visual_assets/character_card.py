"""Professional Character Card contracts and shared-stage orchestration.

Doc178 deliberately keeps Character Card as an additive state machine.  This
module owns slot/state/dependency contracts and calls injected candidate
generator/reviewer seams; it never authors prompt prose or implements a second
provider, review, retry, selector, or image store.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import hashlib
import json
from typing import Any, Callable, Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator, model_validator

from ..schemas.models import V3BaseModel
from ..shared_capabilities.visual_cluster.expression_review import laugh_expression_receipt_allows_slot
from ..shared_capabilities.visual_cluster.review_repair import (
    shared_review_repair_context_from_decision,
)
from .formal_slot_acceptance import (
    FormalSlotAcceptanceCore,
    FormalSlotCandidateEnhancedProofSummary,
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
    HISTORICAL_IDENTITY_CONTEXT_ONLY,
    project_formal_slot_public_summary,
    validate_formal_slot_receipt_for_activation,
)
from .body_silhouette_source_standard import (
    BODY_SILHOUETTE_CROSS_VIEW_PARITY_BLOCKING_ISSUE_CODES,
    BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE,
    BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES,
    BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES,
    BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS,
)
from .body_proportion_evidence_profile import (
    BODY_REFRESH_REFERENCE_AGE_SCOPE,
    BodyRefreshAnalysisContext,
)
from .expression_model_card_framing import compose_expression_model_card_enhanced_summary


FACE_SLOT_KEYS = (
    "face.front",
    "face.left_front_25",
    "face.front_three_quarter",
    "face.profile",
    "face.right_front_25",
    # Historical key kept for persisted cards.  User-facing meaning is the
    # opposite front-side 45-degree face view, not a rear/back-of-head view.
    "face.reverse_three_quarter",
    "face.rear_head",
)
_FACE_SLOT_TO_FORMAL_VIEW_ROLE = {
    "face.front": "standard_front",
    "face.front_three_quarter": "three_quarter",
    "face.profile": "profile",
    "face.reverse_three_quarter": "reverse_three_quarter",
    "face.rear_head": "rear_head",
}
_FORMAL_VIEW_ROLE_TO_FACE_SLOT = {
    view_role: slot_key for slot_key, view_role in _FACE_SLOT_TO_FORMAL_VIEW_ROLE.items()
}
EXPRESSION_SLOT_KEYS = ("expression.neutral", "expression.laugh", "expression.anger", "expression.sad")
LEGACY_EXPRESSION_SLOT_KEYS = ("expression.smile",)
ALL_EXPRESSION_SLOT_KEYS = (*EXPRESSION_SLOT_KEYS, *LEGACY_EXPRESSION_SLOT_KEYS)
POSITIVE_EXPRESSION_SLOT_KEY = "expression.laugh"
DEFAULT_EXPRESSION_KEYS = ("laugh", "anger", "sad")
BODY_SLOT_KEYS = ("body.front_full", "body.side_full", "body.rear_full")
BODY_SOURCE_CLASSES = ("observed", "user_described", "brain_inferred")
BODY_ENHANCED_PROFILE_EVIDENCE_CODE = "body_silhouette_profile_eligible"
BODY_ENHANCED_PROFILE_ISSUE_CODE = "body_silhouette_profile_rejected"
BODY_SOURCE_STANDARD_EVIDENCE_CODE = "body_silhouette_source_standard_verified"
BODY_SOURCE_STANDARD_MISSING_ISSUE_CODE = "body_silhouette_source_standard_evidence_missing"
BODY_FORMAL_SLOT_FAILURE_GENERIC_CODE = "body_formal_slot_receipt_invalid"
BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE = "body_formal_slot_no_passing_shared_review_candidate"
BODY_FORMAL_SLOT_NO_EXTERNAL_ELIGIBILITY_CODE = "body_formal_slot_no_external_eligibility_passing_candidate"
BODY_FORMAL_SLOT_SOURCE_STANDARD_MISSING_CODE = "body_formal_slot_source_standard_evidence_missing"
BODY_FORMAL_SLOT_SOURCE_STANDARD_BLOCKED_CODE = "body_formal_slot_source_standard_blocking_issue"
BODY_FORMAL_SLOT_SHARED_REVIEW_RECEIPT_MISSING_CODE = "body_formal_slot_shared_review_receipt_missing"
BODY_FORMAL_SLOT_CANDIDATE_CONTRACT_MISMATCH_CODE = "body_formal_slot_candidate_contract_mismatch"
BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE = "body_formal_slot_reviewed_candidate_count_invalid"
CHARACTER_CARD_FORMAL_CANDIDATE_COUNT = 3
BodyFormalSlotFailureCode = Literal[
    "body_formal_slot_receipt_invalid",
    "body_formal_slot_no_passing_shared_review_candidate",
    "body_formal_slot_no_external_eligibility_passing_candidate",
    "body_formal_slot_source_standard_evidence_missing",
    "body_formal_slot_source_standard_blocking_issue",
    "body_formal_slot_shared_review_receipt_missing",
    "body_formal_slot_candidate_contract_mismatch",
    "body_formal_slot_reviewed_candidate_count_invalid",
]
BodyFormalSlotFailureCategory = Literal[
    "shared_review_not_pass",
    "source_standard_evidence_missing",
    "source_standard_blocking_issue",
    "candidate_contract_mismatch",
    "enhanced_proof_unavailable",
]
BodyFormalSlotSharedReviewStatus = Literal["pass", "fail", "borderline", "missing"]
BodyCandidateGenerationFailureFamily = Literal[
    "provider_no_pixel",
    "remote_brain",
    "mcp_materialization",
    "candidate_generation",
    "candidate_planning",
    "candidate_review",
]
BodyCandidateGenerationFailureCode = Literal[
    "image_edit_invalid_request_unattributed",
    "remote_brain_unavailable",
    "remote_brain_unauthorized",
    "remote_creative_brain_prompt_signoff_unavailable",
    "mcp_materialization_pending",
    "mcp_materialization_failed",
    "mcp_review_pending",
    "character_card_candidate_generation_failed",
    "candidate_pre_durable_planning_blocked",
    "candidate_generation_blocked",
    "candidate_review_blocked",
    "unknown_candidate_generation_failure",
]
CharacterCardCandidateLifecyclePhase = Literal["planning", "generation", "review", "formal_receipt"]
CharacterCardCandidateLifecycleCheckpointPhase = Literal[
    "planning",
    "generation",
    "review_extraction",
    "review",
    "formal_receipt",
]
CharacterCardCandidateLifecycleStatus = Literal["blocked"]
CharacterCardCandidateLifecycleCheckpointStatus = Literal["started", "completed", "blocked"]
CharacterCardCandidateLifecycleFailureFamily = Literal[
    "candidate_planning",
    "candidate_generation",
    "candidate_review",
    "formal_receipt",
    "provider_no_pixel",
    "remote_brain",
    "mcp_materialization",
]
CharacterCardCandidateLifecycleFailureCode = Literal[
    "candidate_pre_durable_planning_blocked",
    "candidate_generation_blocked",
    "candidate_review_blocked",
    "candidate_review_generation_result_missing",
    "candidate_review_extraction_unbound",
    "candidate_review_output_binding_missing",
    "candidate_formal_receipt_blocked",
    "image_edit_invalid_request_unattributed",
    "remote_brain_unavailable",
    "remote_brain_unauthorized",
    "remote_creative_brain_prompt_signoff_unavailable",
    "mcp_materialization_pending",
    "mcp_materialization_failed",
    "mcp_review_pending",
    "character_card_candidate_generation_failed",
    "unknown_candidate_generation_failure",
]
EXPRESSION_LABELS = {
    "expression.neutral": "中性",
    "expression.laugh": "开心笑",
    "expression.anger": "愤怒",
    "expression.sad": "悲伤",
    "expression.smile": "微笑（旧版）",
}


def _is_expression_delivery_slot(slot_key: str) -> bool:
    return slot_key in ALL_EXPRESSION_SLOT_KEYS and slot_key != "expression.neutral"


def _is_body_delivery_slot(slot_key: str) -> bool:
    return slot_key in BODY_SLOT_KEYS


CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION = "v3_character_card_slot_success_receipt_v1"
_CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_OWNER = "v3_character_card_shared_runtime"
CharacterCardAcceptanceMode = Literal[
    "standard_three_candidate",
    "target_only_existing_candidate_collection",
]
_CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE = "legacy_unclassified"
_SAFE_SHARED_REVIEW_RECEIPT_KEYS = (
    "owner",
    "contract_version",
    "status",
    "expression",
    "framing_baseline",
    "evidence_codes",
    "issue_codes",
    "score_dimensions",
    "framing_delta_dimensions",
)
_CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_KEYS = {
    "owner",
    "receipt_version",
    "module",
    "slot_key",
    "output_id",
    "review_owner",
    "retry_owner",
    "candidate_count",
    "reviewed_candidate_count",
    "acceptance_mode",
    "max_bounded_repair_count",
    "bounded_repair_count",
    "final_winner_selection_verified",
    "prompt_reference_parity_verified",
    "shared_review_receipts",
}

CharacterCardSlotKey = Literal[
    "face.front",
    "face.left_front_25",
    "face.front_three_quarter",
    "face.profile",
    "face.right_front_25",
    "face.reverse_three_quarter",
    "face.rear_head",
    "expression.neutral",
    "expression.laugh",
    "expression.smile",
    "expression.anger",
    "expression.sad",
    "body.front_full",
    "body.side_full",
    "body.rear_full",
]
CharacterCardModule = Literal["face_identity", "expression_set", "body_silhouette"]
CharacterCardSlotState = Literal[
    "empty",
    "preparing",
    "reviewing",
    "winner_selected",
    "active",
    "stale",
    "blocked",
]
CharacterCardModuleStatus = Literal[
    "empty",
    "preparing",
    "reviewing",
    "partial",
    "active",
    "stale",
    "blocked",
]
BodySourceClass = Literal["observed", "user_described", "brain_inferred"]
BodyRefreshSourceMode = Literal["reference_assisted", "inference_first"]
BodyRefreshTargetAgeScope = Literal["age_6_child_only", "current_request_age_owned"]
BodyRefreshBodyModelContext = Literal[
    "similar_person_body_reference_assisted_v1",
    "system_inferred_body_model_scene_neutral_v1",
]
BODY_REFRESH_PRESENTATION_INTENT_CONTRACT_VERSION = "professional_body_refresh_presentation_intent_v2"
BODY_REFRESH_PRESENTATION_INTENT_OWNER = "professional_character_card_body_silhouette_refresh_request"
BODY_REFRESH_PRESENTATION_INTENT_SCOPE = "modeling_card_presentation_only"
BODY_SILHOUETTE_HAIR_CONTINUITY_CONTRACT_VERSION = (
    "professional_body_silhouette_hair_continuity_v1"
)
BODY_SILHOUETTE_GARMENT_CONTINUITY_CONTRACT_VERSION = (
    "professional_body_silhouette_garment_continuity_v2"
)
BODY_SILHOUETTE_GARMENT_CONTINUITY_LEGACY_CONTRACT_VERSION = (
    "professional_body_silhouette_garment_continuity_v1"
)
BODY_SILHOUETTE_BACKDROP_PRESENTATION_CONTRACT_VERSION = (
    "professional_body_silhouette_backdrop_presentation_v1"
)
ExpressionKey = Literal["laugh", "smile", "anger", "sad"]
BodySlotKey = Literal["body.front_full", "body.side_full", "body.rear_full"]
BODY_SOURCE_ADMISSION_CONTRACT_VERSION = "professional_body_source_admission_v1"
BODY_SOURCE_ADMISSION_ALLOWED_CHANNELS = (
    "body_proportion",
    "body_scale",
    "neck_shoulder_transition",
    "torso_limb_proportion",
    "developmental_stage_coherence",
    "stance_ground_contact",
    "cross_view_body_parity",
)


class _CharacterCardModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


class CharacterCardRuntimeUnavailable(RuntimeError):
    """A safe, non-provider error for an unconfigured shared stage host."""

    code = "character_card_shared_runtime_unavailable"


class BodyRefreshPresentationIntent(_CharacterCardModel):
    """Request-scoped modeling-card presentation intent for Body refresh.

    This is not Body source truth, Face Identity truth, age truth, review proof,
    or activation authority.  It only lets the owning Body refresh request
    constrain the neutral modeling-card clothing/footwear presentation without
    reviving the superseded global wardrobe contract.
    """

    contract_version: Literal["professional_body_refresh_presentation_intent_v2"] = (
        BODY_REFRESH_PRESENTATION_INTENT_CONTRACT_VERSION
    )
    owner: Literal["professional_character_card_body_silhouette_refresh_request"] = (
        BODY_REFRESH_PRESENTATION_INTENT_OWNER
    )
    scope: Literal["modeling_card_presentation_only"] = BODY_REFRESH_PRESENTATION_INTENT_SCOPE
    top_presentation: Literal["short_sleeve_top"] = "short_sleeve_top"
    bottom_presentation: Literal["shorts"] = "shorts"
    footwear_presentation: Literal["plain_white_ankle_socks"] = "plain_white_ankle_socks"
    not_body_proportion_truth: Literal[True] = True
    not_identity_truth: Literal[True] = True
    not_age_truth: Literal[True] = True


class BodySilhouetteHairContinuityContract(_CharacterCardModel):
    """Closed, executable hair continuity evidence for Body materialization."""

    contract_version: Literal["professional_body_silhouette_hair_continuity_v1"] = (
        BODY_SILHOUETTE_HAIR_CONTINUITY_CONTRACT_VERSION
    )
    applies: Literal[True] = True
    source: Literal["current_project_confirmed_face_identity_references"] = (
        "current_project_confirmed_face_identity_references"
    )
    required_continuity: list[
        Literal[
            "same_hairstyle_category",
            "same_hair_length_tier",
            "same_bangs_or_parting_pattern",
            "same_overall_hair_outline",
        ]
    ] = Field(
        default_factory=lambda: [
            "same_hairstyle_category",
            "same_hair_length_tier",
            "same_bangs_or_parting_pattern",
            "same_overall_hair_outline",
        ]
    )
    allowed_variation: list[
        Literal["view_angle", "pose", "lighting", "natural_body_view_movement"]
    ] = Field(
        default_factory=lambda: [
            "view_angle",
            "pose",
            "lighting",
            "natural_body_view_movement",
        ]
    )
    forbidden: list[
        Literal[
            "unsupported_hairstyle_category_change",
            "obvious_hair_length_tier_change",
            "unsupported_bangs_or_parting_change",
            "unsupported_hair_outline_change",
        ]
    ] = Field(
        default_factory=lambda: [
            "unsupported_hairstyle_category_change",
            "obvious_hair_length_tier_change",
            "unsupported_bangs_or_parting_change",
            "unsupported_hair_outline_change",
        ]
    )
    fixed_hairstyle_text: None = None
    scope: Literal["body_silhouette_only"] = "body_silhouette_only"

    @model_validator(mode="after")
    def require_closed_lists(self) -> "BodySilhouetteHairContinuityContract":
        if self.required_continuity != [
            "same_hairstyle_category",
            "same_hair_length_tier",
            "same_bangs_or_parting_pattern",
            "same_overall_hair_outline",
        ]:
            raise ValueError("Body hair continuity required fields are not closed")
        if self.allowed_variation != ["view_angle", "pose", "lighting", "natural_body_view_movement"]:
            raise ValueError("Body hair continuity variation fields are not closed")
        if self.forbidden != [
            "unsupported_hairstyle_category_change",
            "obvious_hair_length_tier_change",
            "unsupported_bangs_or_parting_change",
            "unsupported_hair_outline_change",
        ]:
            raise ValueError("Body hair continuity forbidden fields are not closed")
        return self


class BodySilhouetteGarmentContinuityContractV1(_CharacterCardModel):
    """Historical category-only garment contract kept readable for old handoffs."""

    contract_version: Literal["professional_body_silhouette_garment_continuity_v1"] = (
        BODY_SILHOUETTE_GARMENT_CONTINUITY_LEGACY_CONTRACT_VERSION
    )
    applies: Literal[True] = True
    owner: Literal["professional_character_card_body_silhouette_refresh_request"] = (
        BODY_REFRESH_PRESENTATION_INTENT_OWNER
    )
    scope: Literal["professional_character_card_body_silhouette_mcp_materialization_only"] = (
        "professional_character_card_body_silhouette_mcp_materialization_only"
    )
    top_presentation: Literal["short_sleeve_top"] = "short_sleeve_top"
    bottom_presentation: Literal["shorts"] = "shorts"
    footwear_presentation: Literal["plain_white_ankle_socks"] = "plain_white_ankle_socks"
    exact_same_garments_across_views: Literal[True] = True
    required_continuity: list[
        Literal[
            "same_top_garment_identity",
            "same_bottom_garment_identity",
            "same_footwear_identity",
            "same_colorway_between_views",
            "same_material_and_cut_between_views",
            "same_graphic_free_surface_between_views",
        ]
    ] = Field(
        default_factory=lambda: [
            "same_top_garment_identity",
            "same_bottom_garment_identity",
            "same_footwear_identity",
            "same_colorway_between_views",
            "same_material_and_cut_between_views",
            "same_graphic_free_surface_between_views",
        ]
    )
    allowed_variation: list[
        Literal["view_angle", "pose", "lighting", "natural_fabric_fold", "natural_occlusion"]
    ] = Field(
        default_factory=lambda: [
            "view_angle",
            "pose",
            "lighting",
            "natural_fabric_fold",
            "natural_occlusion",
        ]
    )
    forbidden: list[
        Literal[
            "top_garment_swap_between_views",
            "bottom_garment_swap_between_views",
            "footwear_swap_between_views",
            "colorway_change_between_views",
            "material_or_cut_change_between_views",
            "graphic_logo_or_pattern_appears",
            "extra_layer_added_or_removed_between_views",
        ]
    ] = Field(
        default_factory=lambda: [
            "top_garment_swap_between_views",
            "bottom_garment_swap_between_views",
            "footwear_swap_between_views",
            "colorway_change_between_views",
            "material_or_cut_change_between_views",
            "graphic_logo_or_pattern_appears",
            "extra_layer_added_or_removed_between_views",
        ]
    )
    not_body_proportion_truth: Literal[True] = True
    not_identity_truth: Literal[True] = True
    not_age_truth: Literal[True] = True

    @model_validator(mode="after")
    def require_closed_lists(self) -> "BodySilhouetteGarmentContinuityContractV1":
        if self.required_continuity != [
            "same_top_garment_identity",
            "same_bottom_garment_identity",
            "same_footwear_identity",
            "same_colorway_between_views",
            "same_material_and_cut_between_views",
            "same_graphic_free_surface_between_views",
        ]:
            raise ValueError("Body garment continuity required fields are not closed")
        if self.allowed_variation != [
            "view_angle",
            "pose",
            "lighting",
            "natural_fabric_fold",
            "natural_occlusion",
        ]:
            raise ValueError("Body garment continuity variation fields are not closed")
        if self.forbidden != [
            "top_garment_swap_between_views",
            "bottom_garment_swap_between_views",
            "footwear_swap_between_views",
            "colorway_change_between_views",
            "material_or_cut_change_between_views",
            "graphic_logo_or_pattern_appears",
            "extra_layer_added_or_removed_between_views",
        ]:
            raise ValueError("Body garment continuity forbidden fields are not closed")
        return self


class BodySilhouetteGarmentContinuityContractV2(_CharacterCardModel):
    """Closed, exact same-garment identity for new Body materializations."""

    contract_version: Literal["professional_body_silhouette_garment_continuity_v2"] = (
        BODY_SILHOUETTE_GARMENT_CONTINUITY_CONTRACT_VERSION
    )
    applies: Literal[True] = True
    owner: Literal["professional_character_card_body_silhouette_refresh_request"] = (
        BODY_REFRESH_PRESENTATION_INTENT_OWNER
    )
    scope: Literal["professional_character_card_body_silhouette_mcp_materialization_only"] = (
        "professional_character_card_body_silhouette_mcp_materialization_only"
    )
    top_presentation: Literal["short_sleeve_top"] = "short_sleeve_top"
    top_garment_identity: Literal["plain_white_short_sleeve_top"] = (
        "plain_white_short_sleeve_top"
    )
    top_material: Literal["plain_cotton_jersey"] = "plain_cotton_jersey"
    top_cut: Literal["crew_neck_short_sleeve"] = "crew_neck_short_sleeve"
    bottom_presentation: Literal["shorts"] = "shorts"
    bottom_garment_identity: Literal["light_blue_denim_shorts"] = (
        "light_blue_denim_shorts"
    )
    bottom_material: Literal["lightweight_light_blue_denim"] = (
        "lightweight_light_blue_denim"
    )
    bottom_cut: Literal["straight_mid_thigh_shorts"] = "straight_mid_thigh_shorts"
    footwear_presentation: Literal["plain_white_ankle_socks"] = (
        "plain_white_ankle_socks"
    )
    footwear_identity: Literal["plain_white_ankle_socks"] = "plain_white_ankle_socks"
    surface_treatment: Literal["graphic_free"] = "graphic_free"
    exact_same_garments_across_views: Literal[True] = True
    required_continuity: list[
        Literal[
            "same_top_garment_identity",
            "same_top_material_and_cut",
            "same_bottom_garment_identity",
            "same_bottom_material_and_cut",
            "same_footwear_identity",
            "same_colorway_between_views",
            "same_graphic_free_surface_between_views",
        ]
    ] = Field(
        default_factory=lambda: [
            "same_top_garment_identity",
            "same_top_material_and_cut",
            "same_bottom_garment_identity",
            "same_bottom_material_and_cut",
            "same_footwear_identity",
            "same_colorway_between_views",
            "same_graphic_free_surface_between_views",
        ]
    )
    allowed_variation: list[
        Literal["view_angle", "pose", "lighting", "natural_fabric_fold", "natural_occlusion"]
    ] = Field(
        default_factory=lambda: [
            "view_angle",
            "pose",
            "lighting",
            "natural_fabric_fold",
            "natural_occlusion",
        ]
    )
    forbidden: list[
        Literal[
            "top_garment_swap_between_views",
            "top_material_or_cut_change_between_views",
            "bottom_garment_swap_between_views",
            "bottom_material_or_cut_change_between_views",
            "footwear_swap_between_views",
            "colorway_change_between_views",
            "graphic_logo_or_pattern_appears",
            "extra_layer_added_or_removed_between_views",
        ]
    ] = Field(
        default_factory=lambda: [
            "top_garment_swap_between_views",
            "top_material_or_cut_change_between_views",
            "bottom_garment_swap_between_views",
            "bottom_material_or_cut_change_between_views",
            "footwear_swap_between_views",
            "colorway_change_between_views",
            "graphic_logo_or_pattern_appears",
            "extra_layer_added_or_removed_between_views",
        ]
    )
    not_body_proportion_truth: Literal[True] = True
    not_identity_truth: Literal[True] = True
    not_age_truth: Literal[True] = True

    @model_validator(mode="after")
    def require_closed_lists(self) -> "BodySilhouetteGarmentContinuityContractV2":
        if self.required_continuity != [
            "same_top_garment_identity",
            "same_top_material_and_cut",
            "same_bottom_garment_identity",
            "same_bottom_material_and_cut",
            "same_footwear_identity",
            "same_colorway_between_views",
            "same_graphic_free_surface_between_views",
        ]:
            raise ValueError("Body garment continuity required fields are not closed")
        if self.allowed_variation != [
            "view_angle",
            "pose",
            "lighting",
            "natural_fabric_fold",
            "natural_occlusion",
        ]:
            raise ValueError("Body garment continuity variation fields are not closed")
        if self.forbidden != [
            "top_garment_swap_between_views",
            "top_material_or_cut_change_between_views",
            "bottom_garment_swap_between_views",
            "bottom_material_or_cut_change_between_views",
            "footwear_swap_between_views",
            "colorway_change_between_views",
            "graphic_logo_or_pattern_appears",
            "extra_layer_added_or_removed_between_views",
        ]:
            raise ValueError("Body garment continuity forbidden fields are not closed")
        return self


# Keep the established import name pointed at the new contract.
BodySilhouetteGarmentContinuityContract = BodySilhouetteGarmentContinuityContractV2


def validate_body_silhouette_garment_continuity_contract(
    raw: Any,
    *,
    require_identity: bool = False,
) -> dict[str, Any]:
    """Validate a new contract or read a historical category-only handoff."""

    if not isinstance(raw, dict):
        raise ValueError("Body garment continuity contract must be an object")
    version = raw.get("contract_version")
    if version == BODY_SILHOUETTE_GARMENT_CONTINUITY_CONTRACT_VERSION:
        return BodySilhouetteGarmentContinuityContractV2.model_validate(raw).model_dump(mode="json")
    if version == BODY_SILHOUETTE_GARMENT_CONTINUITY_LEGACY_CONTRACT_VERSION and not require_identity:
        return BodySilhouetteGarmentContinuityContractV1.model_validate(raw).model_dump(mode="json")
    if version == BODY_SILHOUETTE_GARMENT_CONTINUITY_LEGACY_CONTRACT_VERSION:
        raise ValueError("Body garment continuity identity contract required")
    raise ValueError("Body garment continuity contract version invalid")


class BodySilhouetteBackdropPresentationContract(_CharacterCardModel):
    """Closed presentation backdrop intent, never Body or identity truth."""

    contract_version: Literal["professional_body_silhouette_backdrop_presentation_v1"] = (
        BODY_SILHOUETTE_BACKDROP_PRESENTATION_CONTRACT_VERSION
    )
    applies: Literal[True] = True
    owner: Literal["professional_character_card_body_silhouette_refresh_request"] = (
        BODY_REFRESH_PRESENTATION_INTENT_OWNER
    )
    scope: Literal["professional_character_card_body_silhouette_mcp_materialization_only"] = (
        "professional_character_card_body_silhouette_mcp_materialization_only"
    )
    backdrop: Literal["solid_white"] = "solid_white"
    not_body_proportion_truth: Literal[True] = True
    not_identity_truth: Literal[True] = True
    not_age_truth: Literal[True] = True


def default_body_silhouette_hair_continuity_contract() -> dict[str, Any]:
    return BodySilhouetteHairContinuityContract().model_dump(mode="json")


def default_body_silhouette_garment_continuity_contract() -> dict[str, Any]:
    return BodySilhouetteGarmentContinuityContractV2().model_dump(mode="json")


def default_body_silhouette_backdrop_presentation_contract() -> dict[str, Any]:
    return BodySilhouetteBackdropPresentationContract().model_dump(mode="json")


def default_body_refresh_presentation_intent() -> BodyRefreshPresentationIntent:
    return BodyRefreshPresentationIntent()


def unspecified_body_refresh_presentation_intent() -> dict[str, str]:
    return {
        "contract_version": BODY_REFRESH_PRESENTATION_INTENT_CONTRACT_VERSION,
        "owner": BODY_REFRESH_PRESENTATION_INTENT_OWNER,
        "scope": BODY_REFRESH_PRESENTATION_INTENT_SCOPE,
        "status": "unspecified",
    }


class BodySilhouettePublicRequest(_CharacterCardModel):
    """The only body facts a browser may submit for a Character Card stage.

    Asset IDs are resolved server-side.  Natural-language facts remain user
    authored; callers cannot submit paths, prompt fragments, or a structured
    body recipe.
    """

    source_class: BodySourceClass
    # The existing five-source observed Body contract is the user-approved
    # six-year proportion evidence. Other ages must explicitly remain owned by
    # the current request and therefore cannot consume that profile.
    target_age_scope: BodyRefreshTargetAgeScope = "current_request_age_owned"
    body_reference_asset_id: str | None = None
    body_reference_asset_ids: list[StrictStr] = Field(default_factory=list)
    body_facts: str | None = Field(default=None, max_length=2000)

    @field_validator("body_reference_asset_id")
    @classmethod
    def validate_reference_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned or "/" in cleaned or "\\" in cleaned or ":" in cleaned:
            raise ValueError("body reference must be an asset identifier")
        return cleaned

    @field_validator("body_reference_asset_ids", mode="before")
    @classmethod
    def validate_reference_ids(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("body_reference_asset_ids must be a list")
        cleaned = [item.strip() if isinstance(item, str) else item for item in value]
        if any(not isinstance(item, str) or not item for item in cleaned):
            raise ValueError("body_reference_asset_ids must contain asset identifiers")
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("body_reference_asset_ids must be unique")
        if any("/" in item or "\\" in item or ":" in item for item in cleaned):
            raise ValueError("body_reference_asset_ids must not contain paths")
        return cleaned

    @field_validator("body_facts")
    @classmethod
    def validate_user_facts(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("body facts must be natural-language text")
        return cleaned

    @model_validator(mode="after")
    def enforce_source_truth(self) -> "BodySilhouettePublicRequest":
        if self.target_age_scope not in {
            BODY_REFRESH_REFERENCE_AGE_SCOPE,
            "current_request_age_owned",
        }:
            raise ValueError("body_refresh_target_age_scope_invalid")
        if self.source_class == "observed":
            if self.body_facts is not None or (
                not self.body_reference_asset_id and not self.body_reference_asset_ids
            ):
                raise ValueError("observed Body Silhouette requires an authorized full-body asset")
            if self.body_reference_asset_ids:
                if len(self.body_reference_asset_ids) != 5:
                    raise ValueError("body_reference_asset_ids_exactly_five_required")
                if (
                    self.body_reference_asset_id is not None
                    and self.body_reference_asset_id not in self.body_reference_asset_ids
                ):
                    raise ValueError("body_reference_asset_primary_mismatch")
            if self.target_age_scope == BODY_REFRESH_REFERENCE_AGE_SCOPE and len(
                self.body_reference_asset_ids
            ) != 5:
                raise ValueError("body_refresh_target_age_scope_requires_five_sources")
        elif self.source_class == "user_described":
            if self.target_age_scope == BODY_REFRESH_REFERENCE_AGE_SCOPE:
                raise ValueError("body_refresh_target_age_scope_requires_observed_reference")
            if self.body_reference_asset_id is not None or self.body_reference_asset_ids or not self.body_facts:
                raise ValueError("user_described Body Silhouette requires natural-language facts")
        elif self.target_age_scope == BODY_REFRESH_REFERENCE_AGE_SCOPE:
            raise ValueError("body_refresh_target_age_scope_requires_observed_reference")
        elif self.body_reference_asset_id is not None or self.body_reference_asset_ids or self.body_facts is not None:
            raise ValueError("brain_inferred Body Silhouette accepts no observed body facts")
        return self


class BodySourceAdmission(_CharacterCardModel):
    """Server-owned source admission for strict Body Silhouette repair.

    It separates Body-owner evidence/provenance from Face Identity references.
    The payload is public-safe: it contains no prompt prose, local paths,
    provider response, biometric vectors, or raw user-described body facts.
    """

    contract_version: Literal["professional_body_source_admission_v1"] = BODY_SOURCE_ADMISSION_CONTRACT_VERSION
    source_class: Literal["observed", "user_described"]
    body_evidence_ids: list[str] = Field(default_factory=list)
    body_reference_role: Literal["body_proportion_reference"] | None = None
    body_reference_truth_layer: Literal["body_proportion_truth"] | None = None
    face_reference_output_ids: list[str] = Field(default_factory=list)
    body_owned_channels: list[str] = Field(default_factory=lambda: list(BODY_SOURCE_ADMISSION_ALLOWED_CHANNELS))

    @field_validator("body_evidence_ids", "face_reference_output_ids")
    @classmethod
    def clean_source_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("body source admission IDs must be unique")
        for item in cleaned:
            if "/" in item or "\\" in item or ":" in item:
                raise ValueError("body source admission IDs must not contain paths")
        return cleaned

    @field_validator("body_owned_channels")
    @classmethod
    def body_owned_channels_are_closed(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        allowed = set(BODY_SOURCE_ADMISSION_ALLOWED_CHANNELS)
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("body_stage_channel_duplicate")
        if set(cleaned) != allowed:
            raise ValueError("body_stage_channel_not_owned")
        return cleaned

    @model_validator(mode="after")
    def enforce_source_channel_contract(self) -> "BodySourceAdmission":
        if len(self.face_reference_output_ids) != 3:
            raise ValueError("body_source_admission_face_chain_invalid")
        if self.source_class == "observed":
            if not self.body_evidence_ids:
                raise ValueError("body_source_admission_observed_evidence_missing")
            if self.body_reference_role != "body_proportion_reference":
                raise ValueError("body_source_admission_role_invalid")
            if self.body_reference_truth_layer != "body_proportion_truth":
                raise ValueError("body_source_admission_truth_layer_invalid")
        else:
            if self.body_evidence_ids:
                raise ValueError("user_described_body_source_admission_has_reference")
            if self.body_reference_role is not None or self.body_reference_truth_layer is not None:
                raise ValueError("user_described_body_source_admission_has_reference_role")
        return self

    def source_evidence_id_digest(self) -> str:
        """Return a stable digest for this exact ordered Body evidence set."""

        return hashlib.sha256(
            json.dumps(
                list(self.body_evidence_ids),
                ensure_ascii=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()


class CharacterCardSlot(_CharacterCardModel):
    """One independent slot and its reviewed-materialization state."""

    slot_key: CharacterCardSlotKey
    module: CharacterCardModule
    state: CharacterCardSlotState = "empty"
    output_id: str | None = None
    source_candidate_ids: list[str] = Field(default_factory=list)
    source_class: BodySourceClass | None = None
    consent_provenance_id: str | None = None
    lineage_id: str | None = None
    dependency_version_ids: list[str] = Field(default_factory=list)
    review_verified: bool = False
    prompt_reference_parity_verified: bool = False
    # Doc223-D: sanitized success proof for this exact slot/output.  It is
    # projected from the shared runtime receipt and contains no prompts, raw
    # provider/MCP response, local path, image bytes or artifact identifiers.
    shared_runtime_receipt: dict[str, Any] | None = None
    # Module-neutral formal-slot proof for Face Identity slots.  It is the
    # only Task5 authority for Face slot completion; legacy booleans are kept
    # for compatibility/display but cannot activate Face slots without it.
    formal_slot_receipt: FormalSlotReceipt | None = None
    candidate_attempt_count: int = Field(default=0, ge=0, le=4)
    bounded_repair_count: int = Field(default=0, ge=0, le=1)
    explicitly_left_empty: bool = False
    is_alias: bool = False
    alias_of: str | None = None

    @model_validator(mode="before")
    @classmethod
    def tolerate_legacy_slot_readback_noise(cls, data: Any) -> Any:
        """Keep older persisted slots readable without upgrading their proof.

        Pre-formal Character Card records may contain fields that were never
        slot authority.  Dropping those fields lets downstream stages reference
        an already-slotted winner image, while the formal receipt validators
        below still fail closed for activation/completion proof.
        """

        if not isinstance(data, dict):
            return data
        cleaned = dict(data)
        if cleaned.get("failure_reason") is None:
            cleaned.pop("failure_reason", None)
        return cleaned

    @field_validator("source_candidate_ids", "dependency_version_ids")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Character Card provenance IDs must be unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_slot_contract(self) -> "CharacterCardSlot":
        expected_module = self.slot_key.split(".", 1)[0]
        expected_module = {
            "face": "face_identity",
            "expression": "expression_set",
            "body": "body_silhouette",
        }[expected_module]
        if self.module != expected_module:
            raise ValueError("Character Card slot module does not match slot key")
        if self.state == "empty":
            if any(
                (
                    self.output_id,
                    self.source_candidate_ids,
                    self.lineage_id,
                    self.review_verified,
                    self.prompt_reference_parity_verified,
                    self.shared_runtime_receipt,
                    self.formal_slot_receipt,
                    self.is_alias,
                )
            ):
                raise ValueError("empty Character Card slots cannot contain materialized evidence")
            if self.candidate_attempt_count or self.bounded_repair_count:
                raise ValueError("empty Character Card slots cannot contain generation attempts")
        elif self.state in {"winner_selected", "active"}:
            if not self.is_alias and not self.output_id:
                raise ValueError("reviewed Character Card winners require an output")
            if self.module == "face_identity":
                if self.formal_slot_receipt is not None:
                    self._validate_face_identity_formal_slot_receipt()
                elif not self.historical_identity_context_only():
                    raise ValueError("Face Identity Character Card slots require a formal slot receipt")
            elif self.module == "expression_set" and _is_expression_delivery_slot(self.slot_key):
                if self.formal_slot_receipt is not None:
                    self._validate_expression_formal_slot_receipt(require_activation=self.state == "active")
            elif self.module == "body_silhouette" and _is_body_delivery_slot(self.slot_key):
                if self.formal_slot_receipt is not None:
                    self._validate_body_formal_slot_receipt(require_activation=self.state == "active")
            elif self.formal_slot_receipt is not None:
                raise ValueError("formal slot receipts are not yet wired for this Character Card module")
            if self.module != "face_identity" and (
                not self.review_verified or not self.prompt_reference_parity_verified
            ):
                raise ValueError("Character Card winners require shared review and prompt/reference parity")
            if self.shared_runtime_receipt is not None:
                validate_character_card_slot_success_receipt(
                    self.shared_runtime_receipt,
                    module=self.module,
                    slot_key=self.slot_key,
                    output_id=str(self.output_id or ""),
                    allow_legacy_unclassified=True,
                )
        if self.is_alias:
            if self.slot_key != "expression.neutral" or self.alias_of != "face.front":
                raise ValueError("only expression.neutral may alias face.front")
            if self.output_id or self.candidate_attempt_count or self.bounded_repair_count:
                raise ValueError("expression.neutral alias cannot create a generation job")
            if self.shared_runtime_receipt is not None:
                raise ValueError("expression.neutral alias cannot contain a generated-slot receipt")
            if self.formal_slot_receipt is not None:
                raise ValueError("expression.neutral alias cannot contain a formal slot receipt")
        elif self.slot_key == "expression.neutral" and self.state != "empty":
            raise ValueError("expression.neutral must alias face.front")
        if self.module == "body_silhouette" and self.state != "empty" and self.source_class is None:
            raise ValueError("body Character Card slots require an explicit source class")
        if self.module == "body_silhouette" and self.state != "empty" and self.source_class == "observed":
            if not str(self.consent_provenance_id or "").strip():
                raise ValueError("observed Body Silhouette winners require consent provenance")
        if self.module != "body_silhouette" and self.source_class is not None:
            raise ValueError("body source class is only valid for Body Silhouette slots")
        if self.module != "body_silhouette" and self.consent_provenance_id is not None:
            raise ValueError("body consent provenance is only valid for Body Silhouette slots")
        if self.bounded_repair_count > self.candidate_attempt_count:
            raise ValueError("bounded repair cannot exceed candidate attempts")
        return self

    def historical_identity_context_only(self) -> bool:
        """Return True only for old Face winners usable as read-only identity context.

        This compatibility mode is deliberately not formal slot proof: it does
        not create a receipt, does not prove Face activation, and must not be
        copied into downstream Expression/Body receipts or winners.
        """

        return (
            self.module == "face_identity"
            and self.output_id is not None
            and self.review_verified is True
            and self.prompt_reference_parity_verified is True
            and self.candidate_attempt_count >= 1
        )

    def reference_context_mode(self) -> str | None:
        if self.historical_identity_context_only() and self.formal_slot_receipt is None:
            return HISTORICAL_IDENTITY_CONTEXT_ONLY
        return None

    def _validate_face_identity_formal_slot_receipt(self) -> None:
        if self.formal_slot_receipt is None:
            raise ValueError("Face Identity Character Card slots require a formal slot receipt")
        view_role = _FACE_SLOT_TO_FORMAL_VIEW_ROLE.get(self.slot_key)
        if view_role is None:
            raise ValueError("25-35 degree bridge references cannot be formal Character Card Face slots")
        receipt = validate_formal_slot_receipt_for_activation(self.formal_slot_receipt)
        if receipt.module != "face_identity":
            raise ValueError("Face Identity Character Card receipt module mismatch")
        if receipt.slot_key != f"face_identity.{view_role}":
            raise ValueError("Face Identity Character Card receipt slot mismatch")
        if receipt.winner_output_id != self.output_id:
            raise ValueError("Face Identity Character Card receipt output mismatch")
        if self.source_candidate_ids and receipt.winner_candidate_id not in self.source_candidate_ids:
            raise ValueError("Face Identity Character Card receipt winner is not in source candidates")

    def _validate_expression_formal_slot_receipt(self, *, require_activation: bool = False) -> None:
        receipt = (
            validate_formal_slot_receipt_for_activation(self.formal_slot_receipt)
            if require_activation
            else FormalSlotReceipt.model_validate(self.formal_slot_receipt)
        )
        if receipt.module != "expression_set":
            raise ValueError("Expression Character Card formal receipt module mismatch")
        if receipt.slot_key != self.slot_key:
            raise ValueError("Expression Character Card formal receipt slot mismatch")
        if receipt.winner_output_id != self.output_id:
            raise ValueError("Expression Character Card formal receipt output mismatch")

    def _validate_body_formal_slot_receipt(self, *, require_activation: bool = False) -> None:
        receipt = (
            validate_formal_slot_receipt_for_activation(self.formal_slot_receipt)
            if require_activation
            else FormalSlotReceipt.model_validate(self.formal_slot_receipt)
        )
        if receipt.module != "body_silhouette":
            raise ValueError("Body Character Card formal receipt module mismatch")
        if receipt.slot_key != self.slot_key:
            raise ValueError("Body Character Card formal receipt slot mismatch")
        if receipt.winner_output_id != self.output_id:
            raise ValueError("Body Character Card formal receipt output mismatch")


class CharacterCardState(_CharacterCardModel):
    """The visible, resumable state of all three sibling modules."""

    mode: Literal["professional"] = "professional"
    card_version_id: str
    face_identity_status: CharacterCardModuleStatus = "empty"
    expression_set_status: CharacterCardModuleStatus = "empty"
    body_silhouette_status: CharacterCardModuleStatus = "empty"
    face_identity_version_id: str | None = None
    expression_set_version_id: str | None = None
    body_silhouette_version_id: str | None = None
    face_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    expression_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    body_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    body_silhouette_refresh_status: CharacterCardModuleStatus = "empty"
    body_silhouette_refresh_version_id: str | None = None
    body_silhouette_refresh_slots: dict[str, CharacterCardSlot] = Field(default_factory=dict)
    active_version_id: str | None = None
    user_activation_confirmed: bool = False
    expression_activation_confirmed: bool = False
    body_activation_confirmed: bool = False
    append_only_revision: int = Field(default=0, ge=0)
    last_failed_module: CharacterCardModule | None = None
    last_failed_slot_key: CharacterCardSlotKey | None = None
    last_failure_code: str | None = None
    last_failure_details: BodyFormalSlotFailureDetails | None = None
    last_failure_attempt_count: int = Field(default=0, ge=0, le=3)
    resume_available: bool = False
    # Sanitized proof from the shared runtime when a stage pauses after one or
    # more reviewed candidates.  It never contains prompts, provider paths,
    # raw responses, or local artifacts; it only preserves review ownership,
    # parity and public receipt dimensions so a later resume cannot erase
    # already-reviewed pixels.
    last_shared_runtime_failure: dict[str, Any] | None = None
    # Sanitized repair evidence from the latest reviewed-but-failed candidate.
    # This is produced by the shared visual-cluster repair projection and is
    # used only to inform the next candidate in the same slot/round.
    last_review_repair_context: dict[str, Any] | None = None
    # Opaque local-MCP receipts for a blocked stage.  They are cleared by a
    # successful stage and never carry prompt, path, provider or artifact data.
    pending_mcp_handoff_ids: list[str] = Field(default_factory=list)
    # Per-slot retry round for user-confirmed continuations after the current
    # three-candidate budget is exhausted.  Round one is the implicit default;
    # later rounds only isolate durable operation ids and never increase the
    # per-round candidate budget.
    slot_retry_rounds: dict[str, int] = Field(default_factory=dict)

    @field_validator("pending_mcp_handoff_ids")
    @classmethod
    def unique_mcp_handoffs(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Character Card MCP handoff IDs must be unique")
        return cleaned

    @field_validator("slot_retry_rounds")
    @classmethod
    def validate_slot_retry_rounds(cls, value: dict[str, int]) -> dict[str, int]:
        cleaned: dict[str, int] = {}
        allowed = {*ALL_EXPRESSION_SLOT_KEYS, *BODY_SLOT_KEYS}
        for key, round_value in dict(value or {}).items():
            slot_key = str(key).strip()
            if slot_key not in allowed:
                raise ValueError("Character Card retry round slot is invalid")
            parsed = int(round_value)
            if parsed < 1:
                raise ValueError("Character Card retry round must be positive")
            cleaned[slot_key] = parsed
        return cleaned

    @classmethod
    def initial(cls, *, card_version_id: str) -> "CharacterCardState":
        return cls(
            card_version_id=card_version_id,
            face_slots={
                key: CharacterCardSlot(slot_key=key, module="face_identity") for key in FACE_SLOT_KEYS
            },
            expression_slots={
                key: CharacterCardSlot(slot_key=key, module="expression_set") for key in EXPRESSION_SLOT_KEYS
            },
            body_slots={
                key: CharacterCardSlot(slot_key=key, module="body_silhouette") for key in BODY_SLOT_KEYS
            },
        )

    @model_validator(mode="before")
    @classmethod
    def hydrate_new_slots_and_legacy_expression_slots(cls, data: Any) -> Any:
        """Keep historical cards readable after slot-map migrations."""

        if not isinstance(data, dict):
            return data
        face_slots = data.get("face_slots")
        if isinstance(face_slots, dict):
            hydrated = dict(face_slots)
            for slot_key in FACE_SLOT_KEYS:
                hydrated.setdefault(
                    slot_key,
                    CharacterCardSlot(slot_key=slot_key, module="face_identity").model_dump(
                        mode="python"
                    ),
                )
            data = {**data, "face_slots": hydrated}
        expression_slots = data.get("expression_slots")
        if isinstance(expression_slots, dict):
            hydrated = dict(expression_slots)
            for slot_key in EXPRESSION_SLOT_KEYS:
                hydrated.setdefault(
                    slot_key,
                    CharacterCardSlot(slot_key=slot_key, module="expression_set").model_dump(
                        mode="python"
                    ),
                )
            legacy = hydrated.get("expression.smile")
            if legacy is not None:
                if isinstance(legacy, CharacterCardSlot):
                    if legacy.state != "empty":
                        hydrated["expression.smile"] = legacy.model_copy(update={"state": "stale"})
                elif isinstance(legacy, dict) and str(legacy.get("state") or "empty") != "empty":
                    hydrated["expression.smile"] = {**legacy, "state": "stale"}
            data = {**data, "expression_slots": hydrated}
        return data

    @model_validator(mode="after")
    def validate_slots_and_order(self) -> "CharacterCardState":
        if set(self.face_slots) != set(FACE_SLOT_KEYS):
            raise ValueError("Character Card must expose all five Face Identity slots")
        expression_keys = set(self.expression_slots)
        if not set(EXPRESSION_SLOT_KEYS).issubset(expression_keys) or not expression_keys.issubset(
            set(ALL_EXPRESSION_SLOT_KEYS)
        ):
            raise ValueError("Character Card must expose all Expression Set slots")
        if set(self.body_slots) != set(BODY_SLOT_KEYS):
            raise ValueError("Character Card must expose all Body Silhouette slots")
        if self.body_silhouette_refresh_slots:
            if not set(self.body_silhouette_refresh_slots).issubset(set(BODY_SLOT_KEYS)):
                raise ValueError("Body Silhouette refresh slots must use Body Silhouette slot keys")
            if self.body_silhouette_refresh_status == "reviewing" and set(self.body_silhouette_refresh_slots) != set(BODY_SLOT_KEYS):
                raise ValueError("Body Silhouette refresh review requires all three Body slots")
            for slot_key, slot in self.body_silhouette_refresh_slots.items():
                if slot_key != slot.slot_key:
                    raise ValueError("Body Silhouette refresh slot key mismatch")
                if slot.module != "body_silhouette":
                    raise ValueError("Body Silhouette refresh module mismatch")
                if slot.state == "active":
                    raise ValueError("Body Silhouette refresh cannot activate slots")
                if slot.state not in {"winner_selected", "blocked"}:
                    raise ValueError("Body Silhouette refresh slots must be pending winners or blocked")
        elif self.body_silhouette_refresh_status not in {"empty", "blocked"}:
            raise ValueError("Body Silhouette refresh status requires refresh slots")
        if self.expression_set_status in {"preparing", "reviewing", "partial", "active"} and self.face_identity_status != "active":
            raise ValueError("Expression Set requires an active Face Identity module")
        if self.body_silhouette_status in {"preparing", "reviewing", "partial", "active"}:
            if self.face_identity_status != "active":
                raise ValueError("Body Silhouette requires an active Face Identity module")
        if self.active_version_id and not self.user_activation_confirmed:
            raise ValueError("active Character Card versions require explicit user activation")
        if self.resume_available:
            if (
                self.last_failed_module is None
                or self.last_failed_slot_key is None
                or not str(self.last_failure_code or "").strip()
                or self.last_failure_attempt_count < 1
            ):
                raise ValueError("resumable Character Card state requires a safe failure checkpoint")
        return self

    def all_slots(self) -> list[CharacterCardSlot]:
        return [*self.face_slots.values(), *self.expression_slots.values(), *self.body_slots.values()]

    @property
    def face_identity_base_active(self) -> bool:
        """The historical three-view activation state."""

        return self.face_identity_status == "active"

    @property
    def face_identity_complete(self) -> bool:
        """Five-view completeness, independent from the historical base pack."""

        return all(
            slot.state in {"active", "winner_selected"} or slot.explicitly_left_empty
            for slot in self.face_slots.values()
        )

    def slot(self, slot_key: str) -> CharacterCardSlot:
        for slot in self.all_slots():
            if slot.slot_key == slot_key:
                return slot
        raise KeyError("character_card_slot_not_found")

    def begin_failed_slot_retry(
        self,
        *,
        module: Literal["expression_set", "body_silhouette"],
        confirmed: bool,
    ) -> "CharacterCardState":
        """Start a new user-confirmed retry round for the failed slot.

        This is deliberately not an automatic retry.  It only advances the
        durable slot round after the previous three-candidate budget has been
        exhausted and no MCP handoff is still waiting for materialization.
        """

        if not confirmed:
            raise ValueError("explicit Character Card failed-slot retry confirmation is required")
        if not self.resume_available or self.last_failed_module != module or self.last_failed_slot_key is None:
            raise ValueError("Character Card failed-slot retry requires the matching failed checkpoint")
        if self.pending_mcp_handoff_ids:
            raise ValueError("Character Card failed-slot retry cannot supersede a pending MCP handoff")
        transport_ambiguity = self.last_failure_code == "mcp_materialization_operation_ambiguous"
        if transport_ambiguity:
            failure_receipt = self.last_shared_runtime_failure
            if not isinstance(failure_receipt, dict) or not failure_receipt.get("resume_available"):
                raise ValueError("Character Card ambiguous MCP retry requires shared runtime failure receipt")
            reviewed_attempt_count = int(failure_receipt.get("reviewed_attempt_count") or 0)
            if reviewed_attempt_count > 0 and not failure_receipt.get("shared_review_receipts"):
                raise ValueError("Character Card ambiguous MCP retry requires reviewed candidate receipt")
        if self.last_failure_attempt_count < 3 and not transport_ambiguity:
            raise ValueError("Character Card failed-slot retry requires exhausted candidate budget")

        slot_key = str(self.last_failed_slot_key)
        if module == "expression_set":
            slots = dict(self.expression_slots)
            status_field = "expression_set_status"
            slots_field = "expression_slots"
        else:
            slots = dict(self.body_slots)
            status_field = "body_silhouette_status"
            slots_field = "body_slots"
        if slot_key not in slots:
            raise ValueError("Character Card failed-slot retry slot is missing")
        slot = slots[slot_key]
        if slot.state in {"winner_selected", "active"}:
            raise ValueError("Character Card failed-slot retry cannot replace a reviewed winner")
        slots[slot_key] = CharacterCardSlot(slot_key=slot.slot_key, module=slot.module)
        retry_rounds = dict(self.slot_retry_rounds)
        retry_rounds[slot_key] = int(retry_rounds.get(slot_key, 1)) + 1
        return self.model_copy(
            update={
                status_field: "partial",
                slots_field: slots,
                "slot_retry_rounds": retry_rounds,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
                "append_only_revision": self.append_only_revision + 1,
            }
        )

    def mark_face_version_stale(self, *, new_face_version_id: str) -> "CharacterCardState":
        """Create an append-only state revision without deleting old evidence."""

        stale_expression = {
            key: slot.model_copy(update={"state": "stale"})
            if slot.state != "empty"
            else slot
            for key, slot in self.expression_slots.items()
        }
        stale_body = {
            key: slot.model_copy(update={"state": "stale"})
            if slot.state != "empty"
            else slot
            for key, slot in self.body_slots.items()
        }
        return self.model_copy(
            update={
                "card_version_id": f"card_{uuid4().hex}",
                "face_identity_version_id": new_face_version_id,
                "expression_set_status": "stale" if self.expression_set_status != "empty" else "empty",
                "body_silhouette_status": "stale" if self.body_silhouette_status != "empty" else "empty",
                "expression_slots": stale_expression,
                "body_slots": stale_body,
                "active_version_id": None,
                "user_activation_confirmed": False,
                "expression_activation_confirmed": False,
                "body_activation_confirmed": False,
                "append_only_revision": self.append_only_revision + 1,
            }
        )


class BodyRefreshAttemptIdentity(_CharacterCardModel):
    """Server-owned identity for one Body Silhouette refresh lifecycle."""

    contract_version: Literal["professional_body_refresh_attempt_identity_v1"] = (
        "professional_body_refresh_attempt_identity_v1"
    )
    authority: Literal["character_card_refresh_lifecycle_service"] = (
        "character_card_refresh_lifecycle_service"
    )
    attempt_id: StrictStr
    append_only_revision: StrictInt = Field(ge=1)

    @classmethod
    def create(cls, *, append_only_revision: int) -> "BodyRefreshAttemptIdentity":
        return cls(
            attempt_id=f"body_refresh_attempt_{uuid4().hex}",
            append_only_revision=append_only_revision,
        )

    @field_validator("attempt_id")
    @classmethod
    def safe_attempt_id(cls, value: str) -> str:
        cleaned = value.strip()
        prefix = "body_refresh_attempt_"
        if not cleaned.startswith(prefix):
            raise ValueError("Body refresh attempt id must be server-owned")
        suffix = cleaned[len(prefix):]
        if len(suffix) != 32 or any(char not in "0123456789abcdef" for char in suffix):
            raise ValueError("Body refresh attempt id must be generated by the refresh lifecycle")
        return cleaned


class CharacterCardCandidateRequest(_CharacterCardModel):
    """Opaque shared-runtime request; prompt prose is intentionally absent."""

    project_id: str
    people_asset_id: str
    card_version_id: str
    module: Literal["expression_set", "body_silhouette"]
    slot_key: Literal[
        "expression.laugh",
        "expression.smile",
        "expression.anger",
        "expression.sad",
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    ]
    candidate_index: int = Field(ge=1, le=3)
    attempt_round: int = Field(default=1, ge=1)
    reference_output_ids: list[str] = Field(min_length=1)
    user_intent: str
    source_class: BodySourceClass | None = None
    consent_provenance_id: str | None = None
    body_source_admission: BodySourceAdmission | None = None
    body_refresh_source_mode: BodyRefreshSourceMode | None = None
    body_refresh_target_age_scope: Literal["age_6_child_only"] | None = None
    body_model_context: BodyRefreshBodyModelContext | None = None
    body_refresh_contract_required: StrictBool = False
    body_refresh_presentation_intent: BodyRefreshPresentationIntent | None = None
    generation_channel: Literal["provider", "mcp"] = "provider"
    body_refresh_attempt_identity: BodyRefreshAttemptIdentity | None = None
    body_refresh_analysis_context: BodyRefreshAnalysisContext | None = None
    mcp_handoff_id: str | None = None
    prior_review_repair: dict[str, Any] | None = None
    review_only_resume: bool = False
    candidate_count: Literal[3] = 3

    @field_validator("body_refresh_analysis_context", mode="before")
    @classmethod
    def reject_untrusted_analysis_context(cls, value: Any) -> Any:
        if value is None or isinstance(value, BodyRefreshAnalysisContext):
            return value
        raise ValueError("body_refresh_analysis_context_untrusted")

    @field_validator("project_id", "people_asset_id", "card_version_id", "user_intent")
    @classmethod
    def require_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Character Card request text is required")
        return value

    @field_validator("reference_output_ids")
    @classmethod
    def unique_references(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Character Card references must be unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_module_slot(self) -> "CharacterCardCandidateRequest":
        if self.module == "expression_set":
            if self.slot_key not in {"expression.laugh", "expression.smile", "expression.anger", "expression.sad"}:
                raise ValueError("Expression Set request has an invalid slot")
            if len(self.reference_output_ids) != 1:
                raise ValueError("Expression Set requests must use only face.front winner")
            if self.source_class is not None:
                raise ValueError("Expression Set does not accept a body source class")
            if self.body_source_admission is not None:
                raise ValueError("Expression Set does not accept body source admission")
            if self.body_refresh_attempt_identity is not None:
                raise ValueError("Expression Set does not accept body refresh attempt identity")
            if self.body_refresh_analysis_context is not None:
                raise ValueError("Expression Set does not accept Body analysis context")
            if self.body_refresh_presentation_intent is not None:
                raise ValueError("Expression Set does not accept body refresh presentation intent")
            if self.body_refresh_target_age_scope is not None:
                raise ValueError("Expression Set does not accept Body target age scope")
        else:
            if not self.slot_key.startswith("body."):
                raise ValueError("Body Silhouette request has an invalid slot")
            if len(self.reference_output_ids) != 3:
                raise ValueError("Body Silhouette requests require three face continuity references")
            if self.source_class is None:
                raise ValueError("Body Silhouette request requires a source class")
            if self.source_class == "observed" and not str(self.consent_provenance_id or "").strip():
                raise ValueError("observed Body Silhouette request requires consent provenance")
            if self.body_refresh_target_age_scope is not None and self.body_refresh_source_mode != "reference_assisted":
                raise ValueError("body_refresh_target_age_scope_source_mode_invalid")
            source_mode_present = self.body_refresh_source_mode is not None or self.body_model_context is not None
            strict_refresh_contract = self.body_refresh_contract_required or source_mode_present
            if self.body_refresh_presentation_intent is not None and not strict_refresh_contract:
                raise ValueError("Body Silhouette presentation intent requires strict refresh source mode")
            if self.source_class == "observed":
                if strict_refresh_contract:
                    if self.body_refresh_source_mode != "reference_assisted":
                        raise ValueError("Body Silhouette reference-assisted source mode required")
                    if self.body_model_context != "similar_person_body_reference_assisted_v1":
                        raise ValueError("Body Silhouette reference-assisted context required")
                if self.body_source_admission is None:
                    raise ValueError("Body Silhouette strict source admission is required")
                if self.body_source_admission.source_class != self.source_class:
                    raise ValueError("Body Silhouette source admission class mismatch")
                if self.body_source_admission.face_reference_output_ids != self.reference_output_ids:
                    raise ValueError("Body Silhouette source admission face chain mismatch")
            elif self.source_class == "brain_inferred":
                if self.body_source_admission is not None:
                    raise ValueError("brain_inferred Body Silhouette cannot carry body source admission")
                if strict_refresh_contract:
                    if self.body_refresh_source_mode != "inference_first":
                        raise ValueError("Body Silhouette inference-first source mode required")
                    if self.body_model_context != "system_inferred_body_model_scene_neutral_v1":
                        raise ValueError("Body Silhouette inference-first context required")
            elif self.source_class == "user_described":
                if self.body_refresh_contract_required or source_mode_present:
                    raise ValueError("user_described Body Silhouette cannot carry strict refresh source mode")
                if self.body_source_admission is None:
                    raise ValueError("Body Silhouette strict source admission is required")
                if self.body_source_admission.source_class != self.source_class:
                    raise ValueError("Body Silhouette source admission class mismatch")
                if self.body_source_admission.face_reference_output_ids != self.reference_output_ids:
                    raise ValueError("Body Silhouette source admission face chain mismatch")
            if (
                self.body_refresh_source_mode == "reference_assisted"
                and self.generation_channel == "mcp"
            ):
                if self.body_refresh_analysis_context is None:
                    raise ValueError("body_proportion_analysis_context_missing")
                if self.body_refresh_attempt_identity is None:
                    raise ValueError("body_proportion_analysis_attempt_missing")
                if (
                    self.body_refresh_analysis_context.attempt_id
                    != self.body_refresh_attempt_identity.attempt_id
                    or self.body_refresh_analysis_context.append_only_revision
                    != self.body_refresh_attempt_identity.append_only_revision
                ):
                    raise ValueError("body_proportion_analysis_context_attempt_mismatch")
                if len(self.body_source_admission.body_evidence_ids) != 5:
                    raise ValueError("body_refresh_source_admission_five_sources_required")
                if (
                    self.body_refresh_analysis_context.source_evidence_id_digest
                    != self.body_source_admission.source_evidence_id_digest()
                ):
                    raise ValueError("body_refresh_source_admission_digest_mismatch")
                if self.body_refresh_analysis_context.target_age_scope != BODY_REFRESH_REFERENCE_AGE_SCOPE:
                    raise ValueError("body_refresh_target_age_scope_mismatch")
                if self.body_refresh_target_age_scope != self.body_refresh_analysis_context.target_age_scope:
                    raise ValueError("body_refresh_target_age_scope_mismatch")
            elif self.body_refresh_analysis_context is not None:
                raise ValueError("body_proportion_analysis_context_source_mode_invalid")
        return self

class CharacterCardCandidateResult(_CharacterCardModel):
    candidate_id: str
    output_id: str
    module: Literal["expression_set", "body_silhouette"]
    slot_key: str
    candidate_index: int = Field(ge=1, le=3)
    operation_id: str | None = None
    round_id: str | None = None
    source_candidate_ids: list[str] = Field(min_length=1)
    source_output_ids: list[str] = Field(min_length=1)
    canonical_prompt_hash: str
    prompt_compilation_id: str
    prompt_reference_parity_verified: bool

    @field_validator("operation_id", "round_id")
    @classmethod
    def validate_optional_binding_label(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = str(value).strip()
        if not normalized:
            raise ValueError("Character Card candidate binding label must be nonempty")
        return normalized

    @model_validator(mode="after")
    def require_parity(self) -> "CharacterCardCandidateResult":
        if not self.prompt_reference_parity_verified:
            raise ValueError("Character Card candidate prompt/reference parity is required")
        return self


class CharacterCardCandidateAttempt(_CharacterCardModel):
    request: CharacterCardCandidateRequest
    candidate: CharacterCardCandidateResult
    review: Any


class SlotAcceptanceCore:
    """Pure Character Card slot acceptance.

    This core owns only the canonical decision that turns reviewed candidates
    into one winner.  It deliberately has no knowledge of MCP handoffs,
    operation indexes, retry rounds, quality specializations, card failure
    state, storage, or whole module activation; those remain adapter/lifecycle
    responsibilities.
    """

    def __init__(self, *, quality_gate: Callable[[Any], bool] | None = None) -> None:
        self.quality_gate = quality_gate

    def accepts_review(self, review: Any) -> bool:
        if getattr(review, "status", None) != "pass":
            return False
        if self.quality_gate is None:
            return True
        return bool(self.quality_gate(review))

    def select_winner(
        self,
        reviewed_candidates: Iterable[tuple[CharacterCardCandidateResult, Any]],
    ) -> CharacterCardCandidateResult | None:
        passing = list(reviewed_candidates)
        if not passing:
            return None
        return max(passing, key=lambda item: self.selection_key(item[1]))[0]

    @staticmethod
    def selection_key(review: Any) -> tuple[Any, ...]:
        scores = getattr(review, "identity_scores", None)
        if scores is not None and hasattr(scores, "selection_key"):
            return tuple(scores.selection_key())
        return (0,)


class BodyFormalSlotCandidateFailureSummary(_CharacterCardModel):
    """Closed public-safe per-candidate Body formal failure summary."""

    model_config = ConfigDict(extra="forbid")

    candidate_index: StrictInt = Field(ge=1, le=3)
    shared_review_status: BodyFormalSlotSharedReviewStatus
    shared_review_passed: bool
    enhanced_proof_eligible: bool
    issue_categories: list[BodyFormalSlotFailureCategory] = Field(default_factory=list)

    @field_validator("issue_categories")
    @classmethod
    def unique_categories(cls, value: list[BodyFormalSlotFailureCategory]) -> list[BodyFormalSlotFailureCategory]:
        if len(value) != len(set(value)):
            raise ValueError("Body formal failure categories must be unique")
        return value


class BodyFormalSlotCandidateGenerationFailureSummary(_CharacterCardModel):
    """Closed public-safe summary for a candidate that never reached review."""

    model_config = ConfigDict(extra="forbid")

    candidate_index: StrictInt = Field(ge=1, le=3)
    failure_family: BodyCandidateGenerationFailureFamily
    failure_code: BodyCandidateGenerationFailureCode


class CharacterCardCandidateLifecycleProjection(_CharacterCardModel):
    """Closed public-safe per-candidate lifecycle terminal projection.

    This model is intentionally enum/strict-int only.  It never accepts raw
    exception text, prompts, paths, URLs, provider payloads, asset IDs, output
    IDs, job IDs, or candidate IDs.
    """

    model_config = ConfigDict(extra="forbid")

    contract: Literal["character_card_candidate_lifecycle_projection_v1"] = (
        "character_card_candidate_lifecycle_projection_v1"
    )
    stage: Literal["expression_set", "body_silhouette"]
    slot_key: CharacterCardSlotKey
    candidate_index: StrictInt = Field(ge=1, le=3)
    candidate_count: StrictInt = Field(ge=1, le=3)
    lifecycle_phase: CharacterCardCandidateLifecyclePhase
    status: CharacterCardCandidateLifecycleStatus
    failure_family: CharacterCardCandidateLifecycleFailureFamily
    failure_code: CharacterCardCandidateLifecycleFailureCode


class CharacterCardCandidateLifecycleCheckpoint(_CharacterCardModel):
    """Closed public-safe per-candidate lifecycle progress checkpoint.

    This is a progress/readback contract, not acceptance.  It intentionally
    carries no job id, output id, candidate id, provider payload, prompt, URL or
    filesystem path; those remain internal to their owning stores.
    """

    model_config = ConfigDict(extra="forbid")

    contract: Literal["character_card_candidate_lifecycle_checkpoint_v1"] = (
        "character_card_candidate_lifecycle_checkpoint_v1"
    )
    stage: Literal["expression_set", "body_silhouette"]
    slot_key: CharacterCardSlotKey
    candidate_index: StrictInt = Field(ge=1, le=3)
    candidate_count: StrictInt = Field(ge=1, le=3)
    lifecycle_phase: CharacterCardCandidateLifecycleCheckpointPhase
    status: CharacterCardCandidateLifecycleCheckpointStatus
    failure_family: CharacterCardCandidateLifecycleFailureFamily | None = None
    failure_code: CharacterCardCandidateLifecycleFailureCode | None = None

    @model_validator(mode="after")
    def validate_checkpoint_contract(self) -> "CharacterCardCandidateLifecycleCheckpoint":
        if type(self.candidate_count) is not int or self.candidate_count != CHARACTER_CARD_FORMAL_CANDIDATE_COUNT:
            raise ValueError("Candidate lifecycle checkpoint candidate_count must equal formal count")
        if self.status == "blocked":
            if self.failure_family is None or self.failure_code is None:
                raise ValueError("Candidate lifecycle blocked checkpoint requires closed failure")
        elif self.failure_family is not None or self.failure_code is not None:
            raise ValueError("Candidate lifecycle non-blocked checkpoint cannot carry failure")
        return self


class CharacterCardCandidateLifecycleBoundaryError(RuntimeError):
    """Internal adapter signal for closed candidate lifecycle terminal states."""

    def __init__(
        self,
        *,
        lifecycle_phase: CharacterCardCandidateLifecyclePhase,
        failure_family: CharacterCardCandidateLifecycleFailureFamily,
        failure_code: CharacterCardCandidateLifecycleFailureCode,
    ) -> None:
        super().__init__("character_card_candidate_lifecycle_boundary")
        self.candidate_lifecycle_phase = lifecycle_phase
        self.candidate_lifecycle_failure_family = failure_family
        self.candidate_lifecycle_failure_code = failure_code


class BodyFormalSlotFailureDetails(_CharacterCardModel):
    """Closed public-safe diagnostic for Body formal receipt rejection."""

    model_config = ConfigDict(extra="forbid")

    contract: Literal["body_formal_slot_failure_projection_v1"] = "body_formal_slot_failure_projection_v1"
    failure_code: BodyFormalSlotFailureCode
    module: Literal["body_silhouette"] = "body_silhouette"
    slot_key: Literal["body.front_full", "body.side_full", "body.rear_full"]
    candidate_count: StrictInt = Field(ge=0, le=3)
    candidate_indexes: list[StrictInt] = Field(default_factory=list)
    passed_shared_review_count: StrictInt = Field(ge=0, le=3)
    enhanced_eligible_count: StrictInt = Field(ge=0, le=3)
    shared_review_receipt_missing_count: StrictInt = Field(ge=0, le=3)
    source_standard_evidence_missing_count: StrictInt = Field(ge=0, le=3)
    source_standard_blocking_issue_count: StrictInt = Field(ge=0, le=3)
    candidate_contract_mismatch_count: StrictInt = Field(ge=0, le=3)
    candidate_generation_blocked_count: StrictInt = Field(default=0, ge=0, le=3)
    candidate_generation_blocked_indexes: list[StrictInt] = Field(default_factory=list)
    candidate_generation_failures: list[BodyFormalSlotCandidateGenerationFailureSummary] = Field(default_factory=list)
    candidate_lifecycle_blocked_count: StrictInt = Field(default=0, ge=0, le=3)
    candidate_lifecycle_blocked_indexes: list[StrictInt] = Field(default_factory=list)
    candidate_lifecycle_failures: list[CharacterCardCandidateLifecycleProjection] = Field(default_factory=list)
    candidate_summaries: list[BodyFormalSlotCandidateFailureSummary] = Field(default_factory=list)

    @field_validator("candidate_indexes")
    @classmethod
    def validate_candidate_indexes(cls, value: list[StrictInt]) -> list[StrictInt]:
        if any(index not in {1, 2, 3} for index in value):
            raise ValueError("Body formal failure candidate indexes must be closed to 1..3")
        if len(value) != len(set(value)):
            raise ValueError("Body formal failure candidate indexes must be unique")
        return value

    @field_validator("candidate_generation_blocked_indexes")
    @classmethod
    def validate_candidate_generation_indexes(cls, value: list[StrictInt]) -> list[StrictInt]:
        if any(index not in {1, 2, 3} for index in value):
            raise ValueError("Body candidate generation indexes must be closed to 1..3")
        if len(value) != len(set(value)):
            raise ValueError("Body candidate generation indexes must be unique")
        return value

    @field_validator("candidate_lifecycle_blocked_indexes")
    @classmethod
    def validate_candidate_lifecycle_indexes(cls, value: list[StrictInt]) -> list[StrictInt]:
        if any(index not in {1, 2, 3} for index in value):
            raise ValueError("Body candidate lifecycle indexes must be closed to 1..3")
        if len(value) != len(set(value)):
            raise ValueError("Body candidate lifecycle indexes must be unique")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> "BodyFormalSlotFailureDetails":
        if self.candidate_count != len(self.candidate_indexes):
            raise ValueError("Body formal failure candidate_count must equal candidate_indexes")
        if self.candidate_count != len(self.candidate_summaries):
            raise ValueError("Body formal failure candidate_count must equal candidate_summaries")
        if self.candidate_generation_blocked_count != len(self.candidate_generation_blocked_indexes):
            raise ValueError("Body candidate generation blocked count must equal indexes")
        if self.candidate_generation_blocked_count != len(self.candidate_generation_failures):
            raise ValueError("Body candidate generation blocked count must equal summaries")
        if self.candidate_lifecycle_blocked_count != len(self.candidate_lifecycle_blocked_indexes):
            raise ValueError("Body candidate lifecycle blocked count must equal indexes")
        if self.candidate_lifecycle_blocked_count != len(self.candidate_lifecycle_failures):
            raise ValueError("Body candidate lifecycle blocked count must equal summaries")
        if self.candidate_count + self.candidate_generation_blocked_count > 3:
            raise ValueError("Body reviewed and blocked candidate counts must not exceed three")
        for count in (
            self.passed_shared_review_count,
            self.enhanced_eligible_count,
            self.shared_review_receipt_missing_count,
            self.source_standard_evidence_missing_count,
            self.source_standard_blocking_issue_count,
            self.candidate_contract_mismatch_count,
        ):
            if count > self.candidate_count:
                raise ValueError("Body formal failure counts must not exceed candidate_count")
        if set(self.candidate_indexes).intersection(self.candidate_generation_blocked_indexes):
            raise ValueError("Body candidate cannot be both reviewed and generation-blocked")
        if set(self.candidate_indexes).intersection(self.candidate_lifecycle_blocked_indexes):
            raise ValueError("Body candidate cannot be both reviewed and lifecycle-blocked")
        return self


class CharacterCardFailureEvent(_CharacterCardModel):
    """Safe per-candidate failure evidence retained for manual continuation."""

    module: CharacterCardModule
    slot_key: CharacterCardSlotKey
    candidate_index: int = Field(ge=1, le=3)
    attempt_round: int = Field(default=1, ge=1)
    failure_code: str
    mcp_handoff_id: str | None = None
    review_repair_context: dict[str, Any] | None = None
    failure_details: BodyFormalSlotFailureDetails | None = None
    candidate_lifecycle: CharacterCardCandidateLifecycleProjection | None = None


class CharacterCardStageResult(_CharacterCardModel):
    status: Literal["review", "blocked"]
    card: CharacterCardState
    attempts: list[CharacterCardCandidateAttempt] = Field(default_factory=list)
    winner_output_ids: dict[str, str] = Field(default_factory=dict)
    failure_codes: list[str] = Field(default_factory=list)
    failures: list[CharacterCardFailureEvent] = Field(default_factory=list)
    candidate_lifecycle_checkpoints: list[CharacterCardCandidateLifecycleCheckpoint] = Field(default_factory=list)
    # Production hosts must return a receipt proving that the existing shared
    # review/retry/final-winner path handled this stage.  The offline contract
    # service below intentionally leaves it empty and is never a route host.
    shared_runtime_receipt: "CharacterCardSharedRuntimeReceipt | None" = None
    shared_runtime_failure: "CharacterCardSharedRuntimeFailureReceipt | None" = None
    mcp_handoff_ids: list[str] = Field(default_factory=list)
    formal_slot_receipts: dict[str, FormalSlotReceipt] = Field(default_factory=dict)
    acceptance_mode: CharacterCardAcceptanceMode = "standard_three_candidate"


class CharacterCardSharedRuntimeReceipt(_CharacterCardModel):
    """Opaque proof that a stage used the shared V3 execution chain."""

    review_owner: Literal["v3_shared_vision"] = "v3_shared_vision"
    retry_owner: Literal["v3_shared_visual_retry"] = "v3_shared_visual_retry"
    candidate_count: Literal[3] = 3
    reviewed_candidate_count: int = Field(default=3, ge=1, le=3)
    acceptance_mode: CharacterCardAcceptanceMode = "standard_three_candidate"
    max_bounded_repair_count: Literal[1] = 1
    retry_count: int = Field(default=0, ge=0, le=1)
    final_winner_selection_verified: bool = False
    prompt_reference_parity_verified: bool = False
    shared_review_receipts: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_shared_acceptance(self) -> "CharacterCardSharedRuntimeReceipt":
        if not self.final_winner_selection_verified or not self.prompt_reference_parity_verified:
            raise ValueError("shared Character Card runtime receipt is incomplete")
        for receipt in self.shared_review_receipts:
            if not isinstance(receipt, dict) or str(receipt.get("owner") or "") != "v3_shared_visual_cluster":
                raise ValueError("shared Character Card runtime receipt contains an invalid review receipt")
        return self


class CharacterCardSharedRuntimeFailureReceipt(_CharacterCardModel):
    """Proof that a blocked stage used shared generation/review before pausing."""

    review_owner: Literal["v3_shared_vision"] = "v3_shared_vision"
    retry_owner: Literal["v3_shared_visual_retry"] = "v3_shared_visual_retry"
    candidate_count: Literal[3] = 3
    failure_count: int = Field(ge=1, le=3)
    resume_available: Literal[True] = True
    reviewed_attempt_count: int = Field(default=0, ge=0, le=3)
    prompt_reference_parity_verified: bool = False
    shared_review_receipts: list[dict[str, Any]] = Field(default_factory=list)

    @model_validator(mode="after")
    def require_public_review_receipts(self) -> "CharacterCardSharedRuntimeFailureReceipt":
        for receipt in self.shared_review_receipts:
            if not isinstance(receipt, dict) or str(receipt.get("owner") or "") != "v3_shared_visual_cluster":
                raise ValueError("shared Character Card failure receipt contains an invalid review receipt")
        return self


def _safe_receipt_token(value: Any) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    return token[:160]


def _safe_receipt_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    cleaned = [_safe_receipt_token(item) for item in value]
    return list(dict.fromkeys(item for item in cleaned if item))


def _sanitize_shared_review_receipt(receipt: Any) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("Character Card shared review receipt must be a public dictionary")
    public: dict[str, Any] = {}
    for key in _SAFE_SHARED_REVIEW_RECEIPT_KEYS:
        if key not in receipt:
            continue
        value = receipt.get(key)
        if key in {
            "evidence_codes",
            "issue_codes",
            "score_dimensions",
            "framing_delta_dimensions",
        }:
            public[key] = _safe_receipt_list(value)
        else:
            public[key] = _safe_receipt_token(value)
    if public.get("owner") != "v3_shared_visual_cluster":
        raise ValueError("Character Card shared review receipt owner is invalid")
    if public.get("status") != "pass":
        raise ValueError("Character Card success receipt requires a passing shared review")
    if not public.get("contract_version"):
        raise ValueError("Character Card shared review receipt contract version is required")
    if not public.get("score_dimensions"):
        raise ValueError("Character Card shared review receipt dimensions are required")
    public.setdefault("evidence_codes", [])
    public.setdefault("issue_codes", [])
    public.setdefault("framing_delta_dimensions", [])
    return public


def project_character_card_slot_success_receipt(
    receipt: CharacterCardSharedRuntimeReceipt | dict[str, Any],
    *,
    module: CharacterCardModule,
    slot_key: str,
    output_id: str,
    shared_review_receipts: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> dict[str, Any]:
    """Build the persisted, per-slot success receipt from a shared stage receipt.

    The stage host owns review/retry/final-winner evidence.  This function only
    projects that proof onto the exact winner slot/output and strips everything
    that is not safe for durable catalog/public status readback.
    """

    output_id = _safe_receipt_token(output_id)
    if not output_id:
        raise ValueError("Character Card slot success receipt requires an output")
    stage_receipt = (
        receipt
        if isinstance(receipt, CharacterCardSharedRuntimeReceipt)
        else CharacterCardSharedRuntimeReceipt.model_validate(receipt)
    )
    if not stage_receipt.final_winner_selection_verified:
        raise ValueError("Character Card slot success receipt requires winner selection")
    if not stage_receipt.prompt_reference_parity_verified:
        raise ValueError("Character Card slot success receipt requires prompt/reference parity")
    slot_reviews = [_sanitize_shared_review_receipt(item) for item in shared_review_receipts]
    if not slot_reviews:
        raise ValueError("Character Card slot success receipt requires shared review dimensions")
    if slot_key == POSITIVE_EXPRESSION_SLOT_KEY:
        laugh_receipts = [
            item
            for item in slot_reviews
            if item.get("expression") == "laugh"
            and item.get("contract_version") == "v3_affective_expression_review_receipt_v1"
        ]
        if not laugh_receipts:
            raise ValueError("Character Card laugh slot requires shared affective expression receipt")
        if not any(
            laugh_expression_receipt_allows_slot(
                evidence_codes=item.get("evidence_codes", []),
                issue_codes=item.get("issue_codes", []),
            )
            and bool(item.get("framing_delta_dimensions"))
            for item in laugh_receipts
        ):
            raise ValueError("Character Card laugh slot receipt lacks affect/framing evidence")
    projected = {
        "owner": _CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_OWNER,
        "receipt_version": CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION,
        "module": module,
        "slot_key": slot_key,
        "output_id": output_id,
        "review_owner": stage_receipt.review_owner,
        "retry_owner": stage_receipt.retry_owner,
        "candidate_count": int(stage_receipt.candidate_count),
        "reviewed_candidate_count": int(stage_receipt.reviewed_candidate_count),
        "acceptance_mode": stage_receipt.acceptance_mode,
        "max_bounded_repair_count": int(stage_receipt.max_bounded_repair_count),
        "bounded_repair_count": int(stage_receipt.retry_count),
        "final_winner_selection_verified": bool(stage_receipt.final_winner_selection_verified),
        "prompt_reference_parity_verified": bool(stage_receipt.prompt_reference_parity_verified),
        "shared_review_receipts": slot_reviews,
    }
    return validate_character_card_slot_success_receipt(
        projected,
        module=module,
        slot_key=slot_key,
        output_id=output_id,
    )


def validate_character_card_slot_success_receipt(
    receipt: Any,
    *,
    module: CharacterCardModule,
    slot_key: str,
    output_id: str,
    allow_legacy_unclassified: bool = False,
) -> dict[str, Any]:
    if not isinstance(receipt, dict):
        raise ValueError("Character Card slot shared runtime receipt is required")
    if set(receipt) - _CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_KEYS:
        raise ValueError("Character Card slot shared runtime receipt contains unsafe fields")
    if receipt.get("owner") != _CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_OWNER:
        raise ValueError("Character Card slot shared runtime receipt owner is invalid")
    if receipt.get("receipt_version") != CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION:
        raise ValueError("Character Card slot shared runtime receipt version is invalid")
    if receipt.get("module") != module or receipt.get("slot_key") != slot_key:
        raise ValueError("Character Card slot shared runtime receipt ownership mismatch")
    if receipt.get("output_id") != output_id:
        raise ValueError("Character Card slot shared runtime receipt output mismatch")
    if receipt.get("review_owner") != "v3_shared_vision":
        raise ValueError("Character Card slot shared runtime receipt review owner is invalid")
    if receipt.get("retry_owner") != "v3_shared_visual_retry":
        raise ValueError("Character Card slot shared runtime receipt retry owner is invalid")
    if int(receipt.get("candidate_count") or 0) != 3:
        raise ValueError("Character Card slot shared runtime receipt candidate budget is invalid")
    has_explicit_acceptance_mode = "acceptance_mode" in receipt
    has_explicit_reviewed_count = "reviewed_candidate_count" in receipt
    if not has_explicit_acceptance_mode or not has_explicit_reviewed_count:
        if not allow_legacy_unclassified:
            raise ValueError("Character Card slot shared runtime receipt acceptance mode is missing")
        reviewed_candidate_count = 0
        acceptance_mode = _CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE
    else:
        reviewed_candidate_count = int(receipt.get("reviewed_candidate_count") or 0)
        acceptance_mode = str(receipt.get("acceptance_mode") or "").strip()
    if reviewed_candidate_count < 1 or reviewed_candidate_count > 3:
        if acceptance_mode != _CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE:
            raise ValueError("Character Card slot shared runtime receipt reviewed candidate count is invalid")
    if acceptance_mode not in {
        "standard_three_candidate",
        "target_only_existing_candidate_collection",
        _CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE,
    }:
        raise ValueError("Character Card slot shared runtime receipt acceptance mode is invalid")
    if acceptance_mode == _CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE:
        if not allow_legacy_unclassified:
            raise ValueError("Character Card slot shared runtime receipt acceptance mode is missing")
        if receipt.get("final_winner_selection_verified") is not True:
            raise ValueError("Character Card slot shared runtime receipt winner selection is missing")
        if receipt.get("prompt_reference_parity_verified") is not True:
            raise ValueError("Character Card slot shared runtime receipt prompt/reference parity is missing")
        sanitized_reviews = [
            _sanitize_shared_review_receipt(item)
            for item in receipt.get("shared_review_receipts", [])
        ]
        if not sanitized_reviews:
            raise ValueError("Character Card slot shared runtime receipt review dimensions are missing")
        return {
            **receipt,
            "reviewed_candidate_count": 0,
            "acceptance_mode": _CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE,
            "shared_review_receipts": sanitized_reviews,
        }
    if acceptance_mode == "standard_three_candidate" and reviewed_candidate_count != 3:
        raise ValueError("Character Card standard slot receipt requires three reviewed candidates")
    if int(receipt.get("max_bounded_repair_count") or -1) != 1:
        raise ValueError("Character Card slot shared runtime receipt repair budget is invalid")
    if int(receipt.get("bounded_repair_count") or 0) < 0 or int(receipt.get("bounded_repair_count") or 0) > 1:
        raise ValueError("Character Card slot shared runtime receipt repair count is invalid")
    if receipt.get("final_winner_selection_verified") is not True:
        raise ValueError("Character Card slot shared runtime receipt winner selection is missing")
    if receipt.get("prompt_reference_parity_verified") is not True:
        raise ValueError("Character Card slot shared runtime receipt prompt/reference parity is missing")
    sanitized_reviews = [
        _sanitize_shared_review_receipt(item)
        for item in receipt.get("shared_review_receipts", [])
    ]
    if not sanitized_reviews:
        raise ValueError("Character Card slot shared runtime receipt review dimensions are missing")
    if slot_key == POSITIVE_EXPRESSION_SLOT_KEY:
        if not any(
            item.get("expression") == "laugh"
            and item.get("contract_version") == "v3_affective_expression_review_receipt_v1"
            and bool(item.get("framing_delta_dimensions"))
            and laugh_expression_receipt_allows_slot(
                evidence_codes=item.get("evidence_codes", []),
                issue_codes=item.get("issue_codes", []),
            )
            for item in sanitized_reviews
        ):
            raise ValueError("Character Card laugh slot shared runtime receipt is incomplete")
    return {
        **receipt,
        "reviewed_candidate_count": reviewed_candidate_count,
        "acceptance_mode": acceptance_mode,
        "shared_review_receipts": sanitized_reviews,
    }


def character_card_formal_slot_receipt_public_summary(
    slot: CharacterCardSlot,
) -> dict[str, Any] | None:
    """Safe public projection for activation-eligible formal-slot receipts."""

    if slot.formal_slot_receipt is None:
        return None
    receipt = validate_formal_slot_receipt_for_activation(slot.formal_slot_receipt)
    if slot.output_id and receipt.winner_output_id != slot.output_id:
        raise ValueError("formal receipt output does not match slot output")
    return project_formal_slot_public_summary(receipt)


def character_card_slot_success_receipt_public_summary(
    slot: CharacterCardSlot,
) -> dict[str, Any] | None:
    if slot.shared_runtime_receipt is None or not slot.output_id:
        return None
    receipt = validate_character_card_slot_success_receipt(
        slot.shared_runtime_receipt,
        module=slot.module,
        slot_key=slot.slot_key,
        output_id=slot.output_id,
        allow_legacy_unclassified=True,
    )
    if receipt["acceptance_mode"] == _CHARACTER_CARD_LEGACY_UNCLASSIFIED_ACCEPTANCE_MODE:
        return {
            "verified": False,
            "status": "legacy_unclassified",
            "reason": "missing_acceptance_mode",
            "owner": receipt["owner"],
            "receipt_version": receipt["receipt_version"],
            "module": receipt["module"],
            "slot_key": receipt["slot_key"],
            "output_id": receipt["output_id"],
            "review_owner": receipt["review_owner"],
            "retry_owner": receipt["retry_owner"],
            "candidate_count": receipt["candidate_count"],
            "reviewed_candidate_count": receipt["reviewed_candidate_count"],
            "acceptance_mode": receipt["acceptance_mode"],
        }
    return {
        "verified": True,
        "owner": receipt["owner"],
        "receipt_version": receipt["receipt_version"],
        "module": receipt["module"],
        "slot_key": receipt["slot_key"],
        "output_id": receipt["output_id"],
        "review_owner": receipt["review_owner"],
        "retry_owner": receipt["retry_owner"],
        "candidate_count": receipt["candidate_count"],
        "reviewed_candidate_count": receipt["reviewed_candidate_count"],
        "acceptance_mode": receipt["acceptance_mode"],
        "max_bounded_repair_count": receipt["max_bounded_repair_count"],
        "bounded_repair_count": receipt["bounded_repair_count"],
        "final_winner_selection_verified": receipt["final_winner_selection_verified"],
        "prompt_reference_parity_verified": receipt["prompt_reference_parity_verified"],
        "shared_review_receipts": receipt["shared_review_receipts"],
    }


class ExpressionPreparationRequest(_CharacterCardModel):
    expression: ExpressionKey
    front_output_id: str
    reference_output_ids: list[str] = Field(default_factory=list)
    user_intent: str
    candidate_count: Literal[3] = 3

    @field_validator("front_output_id", "user_intent")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Expression Set requires front winner and user intent")
        return value

    @model_validator(mode="after")
    def enforce_front_only_reference(self) -> "ExpressionPreparationRequest":
        if not self.reference_output_ids:
            self.reference_output_ids = [self.front_output_id]
        if self.reference_output_ids != [self.front_output_id]:
            raise ValueError("Expression Set references must use only the face.front winner")
        return self


class BodyPreparationRequest(_CharacterCardModel):
    source_class: BodySourceClass
    face_reference_output_ids: list[str] = Field(default_factory=list)
    body_evidence_ids: list[str] = Field(default_factory=list)
    consent_provenance_id: str | None = None
    candidate_count: Literal[3] = 3
    wardrobe_lock: Literal[False] = False
    strict_body_source_repair: bool = False

    @field_validator("face_reference_output_ids", "body_evidence_ids")
    @classmethod
    def clean_ids(cls, value: list[str]) -> list[str]:
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("Body Silhouette evidence IDs must be unique")
        return cleaned

    @model_validator(mode="after")
    def require_face_continuity_references(self) -> "BodyPreparationRequest":
        if len(self.face_reference_output_ids) != 3:
            raise ValueError("Body Silhouette requires Face Identity front, profile, and rear references")
        if self.source_class == "observed":
            if not self.body_evidence_ids:
                raise ValueError("observed Body Silhouette requires an authorized full-body reference")
            if not str(self.consent_provenance_id or "").strip():
                raise ValueError("observed Body Silhouette requires consent provenance")
        if self.strict_body_source_repair and self.source_class == "user_described":
            raise ValueError("body_silhouette_refresh_body_source_unavailable")
        return self

    @property
    def reference_output_ids(self) -> list[str]:
        return list(self.face_reference_output_ids)

    @property
    def observed_truth(self) -> bool:
        return self.source_class == "observed"

    @property
    def body_refresh_source_mode(self) -> BodyRefreshSourceMode | None:
        if self.source_class == "observed":
            return "reference_assisted"
        if self.source_class == "brain_inferred":
            return "inference_first"
        return None

    @property
    def body_model_context(self) -> BodyRefreshBodyModelContext | None:
        if self.source_class == "observed":
            return "similar_person_body_reference_assisted_v1"
        if self.source_class == "brain_inferred":
            return "system_inferred_body_model_scene_neutral_v1"
        return None

    def source_admission(self) -> BodySourceAdmission | None:
        if self.source_class == "brain_inferred":
            return None
        return BodySourceAdmission(
            source_class=self.source_class,  # type: ignore[arg-type]
            body_evidence_ids=list(self.body_evidence_ids),
            body_reference_role="body_proportion_reference" if self.source_class == "observed" else None,
            body_reference_truth_layer="body_proportion_truth" if self.source_class == "observed" else None,
            face_reference_output_ids=list(self.face_reference_output_ids),
        )


class CharacterCardCandidateGenerator(Protocol):
    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        ...


class CharacterCardCandidateReviewer(Protocol):
    def review(self, candidate: CharacterCardCandidateResult) -> Any:
        ...


class CharacterCardStageHost(Protocol):
    """Host contract for the existing shared runtime, never a local fallback."""

    production_shared_runtime: bool

    def prepare_expression_set(
        self, *, asset: Any, card: CharacterCardState, generation_channel: str = "provider"
    ) -> CharacterCardStageResult:
        ...

    def prepare_expression_slot(
        self, *, asset: Any, card: CharacterCardState, expression: ExpressionKey, generation_channel: str = "provider"
    ) -> CharacterCardStageResult:
        ...

    def prepare_body_silhouette(
        self, *, asset: Any, card: CharacterCardState,
        request: BodySilhouettePublicRequest | None = None,
        generation_channel: str = "provider",
    ) -> CharacterCardStageResult:
        ...

    def refresh_body_silhouette(
        self, *, asset: Any, card: CharacterCardState,
        request: BodySilhouettePublicRequest | None = None,
        generation_channel: str = "provider",
        body_refresh_presentation_intent: BodyRefreshPresentationIntent | None = None,
        body_refresh_analysis_context: BodyRefreshAnalysisContext | None = None,
        body_source_admission: BodySourceAdmission | None = None,
        body_refresh_attempt_identity: BodyRefreshAttemptIdentity | None = None,
    ) -> CharacterCardStageResult:
        ...


class CharacterCardPreparationService:
    """Offline contract helper; never a production stage host.

    Its injected generator/reviewer seams are useful for deterministic contract
    tests only.  Production HTTP routes require a host advertising
    ``production_shared_runtime`` and a shared-runtime receipt, so this class
    cannot become a second provider/review/retry path.
    """

    production_shared_runtime = False
    execution_mode = "offline_contract"

    CANDIDATE_COUNT = CHARACTER_CARD_FORMAL_CANDIDATE_COUNT
    MAX_BOUNDED_REPAIR_COUNT = 1

    def __init__(
        self,
        *,
        generator: CharacterCardCandidateGenerator | None,
        reviewer: CharacterCardCandidateReviewer | None,
        candidate_checkpoint_callback: Callable[[CharacterCardCandidateRequest, CharacterCardCandidateResult, Any, str], None] | None = None,
        formal_receipt_callback: Callable[[FormalSlotReceipt], None] | None = None,
    ) -> None:
        self.generator = generator
        self.reviewer = reviewer
        self.candidate_checkpoint_callback = candidate_checkpoint_callback
        self.formal_receipt_callback = formal_receipt_callback

    @classmethod
    def _candidate_lifecycle_projection(
        cls,
        *,
        module: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        candidate_index: int,
        lifecycle_phase: CharacterCardCandidateLifecyclePhase,
        failure_family: CharacterCardCandidateLifecycleFailureFamily,
        failure_code: CharacterCardCandidateLifecycleFailureCode,
    ) -> CharacterCardCandidateLifecycleProjection:
        return CharacterCardCandidateLifecycleProjection(
            stage=module,
            slot_key=slot_key,  # type: ignore[arg-type]
            candidate_index=min(cls.CANDIDATE_COUNT, max(1, int(candidate_index or 1))),
            candidate_count=cls.CANDIDATE_COUNT,
            lifecycle_phase=lifecycle_phase,
            status="blocked",
            failure_family=failure_family,
            failure_code=failure_code,
        )

    @classmethod
    def _candidate_lifecycle_checkpoint(
        cls,
        *,
        module: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        candidate_index: int,
        lifecycle_phase: CharacterCardCandidateLifecycleCheckpointPhase,
        status: CharacterCardCandidateLifecycleCheckpointStatus,
        failure_family: CharacterCardCandidateLifecycleFailureFamily | None = None,
        failure_code: CharacterCardCandidateLifecycleFailureCode | None = None,
    ) -> CharacterCardCandidateLifecycleCheckpoint:
        return CharacterCardCandidateLifecycleCheckpoint(
            stage=module,
            slot_key=slot_key,  # type: ignore[arg-type]
            candidate_index=candidate_index,
            candidate_count=cls.CANDIDATE_COUNT,
            lifecycle_phase=lifecycle_phase,
            status=status,
            failure_family=failure_family,
            failure_code=failure_code,
        )

    @classmethod
    def _candidate_lifecycle_projection_from_exception(
        cls,
        exc: BaseException,
        *,
        module: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        candidate_index: int,
        default_phase: CharacterCardCandidateLifecyclePhase,
        default_family: CharacterCardCandidateLifecycleFailureFamily,
        default_code: CharacterCardCandidateLifecycleFailureCode,
    ) -> CharacterCardCandidateLifecycleProjection:
        """Convert an adapter seam exception into a closed public projection.

        Only explicit closed attributes are honored.  Raw exception text is not
        copied and cannot influence public codes.
        """

        phase = getattr(exc, "candidate_lifecycle_phase", None)
        if phase not in {"planning", "generation", "review", "formal_receipt"}:
            phase = default_phase
        family = getattr(exc, "candidate_lifecycle_failure_family", None)
        if family not in {
            "candidate_planning",
            "candidate_generation",
            "candidate_review",
            "formal_receipt",
            "provider_no_pixel",
            "remote_brain",
            "mcp_materialization",
        }:
            family = default_family
        code = getattr(exc, "candidate_lifecycle_failure_code", None)
        if code not in {
            "candidate_pre_durable_planning_blocked",
            "candidate_generation_blocked",
            "candidate_review_blocked",
            "candidate_review_generation_result_missing",
            "candidate_review_extraction_unbound",
            "candidate_review_output_binding_missing",
            "candidate_formal_receipt_blocked",
            "image_edit_invalid_request_unattributed",
            "remote_brain_unavailable",
            "remote_brain_unauthorized",
            "remote_creative_brain_prompt_signoff_unavailable",
            "mcp_materialization_pending",
            "mcp_materialization_failed",
            "mcp_review_pending",
            "character_card_candidate_generation_failed",
            "unknown_candidate_generation_failure",
        }:
            code = default_code
        return cls._candidate_lifecycle_projection(
            module=module,
            slot_key=slot_key,
            candidate_index=candidate_index,
            lifecycle_phase=phase,  # type: ignore[arg-type]
            failure_family=family,  # type: ignore[arg-type]
            failure_code=code,  # type: ignore[arg-type]
        )

    @classmethod
    def _anchor_candidate_lifecycle_projection(
        cls,
        *,
        module: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        candidate_index: int,
        failure_code: str,
    ) -> CharacterCardCandidateLifecycleProjection:
        raw_code = str(failure_code or "").strip()
        if raw_code == "image_edit_invalid_request_unattributed":
            return cls._candidate_lifecycle_projection(
                module=module,
                slot_key=slot_key,
                candidate_index=candidate_index,
                lifecycle_phase="generation",
                failure_family="provider_no_pixel",
                failure_code="image_edit_invalid_request_unattributed",
            )
        if raw_code in {"character_card_candidate_planning_blocked", "professional_anchor_candidate_planning_blocked"}:
            return cls._candidate_lifecycle_projection(
                module=module,
                slot_key=slot_key,
                candidate_index=candidate_index,
                lifecycle_phase="planning",
                failure_family="candidate_planning",
                failure_code="candidate_pre_durable_planning_blocked",
            )
        if raw_code in {
            "remote_brain_unavailable",
            "remote_brain_unauthorized",
            "remote_creative_brain_prompt_signoff_unavailable",
        }:
            return cls._candidate_lifecycle_projection(
                module=module,
                slot_key=slot_key,
                candidate_index=candidate_index,
                lifecycle_phase="planning",
                failure_family="remote_brain",
                failure_code=raw_code,  # type: ignore[arg-type]
            )
        if raw_code in {
            "mcp_materialization_pending",
            "mcp_materialization_failed",
            "mcp_review_pending",
        }:
            return cls._candidate_lifecycle_projection(
                module=module,
                slot_key=slot_key,
                candidate_index=candidate_index,
                lifecycle_phase="generation",
                failure_family="mcp_materialization",
                failure_code=raw_code,  # type: ignore[arg-type]
            )
        return cls._candidate_lifecycle_projection(
            module=module,
            slot_key=slot_key,
            candidate_index=candidate_index,
            lifecycle_phase="generation",
            failure_family="candidate_generation",
            failure_code=(
                "character_card_candidate_generation_failed"
                if raw_code == "character_card_candidate_generation_failed"
                else "unknown_candidate_generation_failure"
            ),
        )

    @staticmethod
    def prepare_face_identity_extension(
        anchor_pack_service: Any,
        request: Any,
    ) -> Any:
        """Run the existing Face Identity host with the two Doc178 slots.

        The import is deliberately runtime-only: the established
        ``AnchorPackPreparationService`` remains the sole face generator and
        reviewer coordinator.  No local prompt or alternate Provider is
        introduced here.
        """

        from .anchor_pack import AnchorPackPreparationRequest

        if not isinstance(request, AnchorPackPreparationRequest):
            raise TypeError("face identity extension requires AnchorPackPreparationRequest")
        extended = request.model_copy(update={"face_view_scope": "character_card"})
        return anchor_pack_service.prepare(extended)

    def prepare_expression_set(
        self,
        card: CharacterCardState,
        *,
        front_output_id: str,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        user_intents: Mapping[ExpressionKey, str] | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
    ) -> CharacterCardStageResult:
        self._require_face_active(card, front_output_id)
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        if not user_intents or any(not str(user_intents.get(key) or "").strip() for key in DEFAULT_EXPRESSION_KEYS):
            raise ValueError("Expression Set requires Brain/user-owned expression intent for every slot")
        intents = user_intents
        attempts: list[CharacterCardCandidateAttempt] = []
        winners: dict[str, str] = {}
        formal_slot_receipts: dict[str, FormalSlotReceipt] = {}
        failures: list[CharacterCardFailureEvent] = []
        slots = dict(card.expression_slots)
        neutral = CharacterCardSlot(
            slot_key="expression.neutral",
            module="expression_set",
            state="active",
            is_alias=True,
            alias_of="face.front",
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
        slots["expression.neutral"] = neutral
        for expression in DEFAULT_EXPRESSION_KEYS:
            slot_key = f"expression.{expression}"
            existing = slots[slot_key]
            if existing.state in {"winner_selected", "active"} and existing.output_id:
                winners[slot_key] = existing.output_id
                if existing.formal_slot_receipt is not None:
                    receipt = FormalSlotReceipt.model_validate(existing.formal_slot_receipt)
                    if receipt.module != "expression_set":
                        raise ValueError("Expression formal receipt module mismatch")
                    if receipt.slot_key != slot_key:
                        raise ValueError("Expression formal receipt slot mismatch")
                    if receipt.winner_output_id != existing.output_id:
                        raise ValueError("Expression formal receipt output mismatch")
                    formal_slot_receipts[slot_key] = receipt
                continue
            request = ExpressionPreparationRequest(
                expression=expression,
                front_output_id=front_output_id,
                user_intent=str(intents.get(expression) or expression),
            )
            winner, expression_attempts, slot_failures, formal_receipt = self._prepare_slot(
                card=card,
                module="expression_set",
                slot_key=slot_key,
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=request.user_intent,
                source_class=None,
                generation_channel=generation_channel,
                attempts=attempts,
            )
            attempts.extend(expression_attempts)
            failures.extend(slot_failures)
            if winner is None:
                failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
                failed_card = self._blocked_card(
                    card,
                    module="expression_set",
                    slot_key=slot_key,
                    failure_code=failure_code,
                    failure_attempt_count=self._failure_attempt_count(slot_failures),
                    slots=slots,
                    status_field="expression_set_status",
                )
                blocked_updates: dict[str, Any] = {
                    "pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures)
                }
                if failure_code == "character_card_shared_review_failed":
                    blocked_updates["last_review_repair_context"] = self._failure_review_repair_context(
                        slot_failures
                    )
                return CharacterCardStageResult(
                    status="blocked",
                    card=failed_card.model_copy(update=blocked_updates),
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                    failures=failures,
                    mcp_handoff_ids=self._mcp_handoff_ids(failures),
                )
            slots[slot_key] = self._winner_slot(
                module="expression_set",
                slot_key=slot_key,
                winner=winner,
                formal_slot_receipt=formal_receipt,
            )
            if formal_receipt is not None:
                formal_slot_receipts[slot_key] = formal_receipt
            winners[slot_key] = winner.output_id
        updated = card.model_copy(
            update={
                "expression_slots": slots,
                "expression_set_status": "reviewing",
                "expression_set_version_id": f"expression_{uuid4().hex}",
                "expression_activation_confirmed": False,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(
            status="review",
            card=updated,
            attempts=attempts,
            winner_output_ids=winners,
            failures=failures,
            formal_slot_receipts=formal_slot_receipts,
        )

    @staticmethod
    def _body_silhouette_cross_view_parity_failure(
        formal_slot_receipts: dict[str, FormalSlotReceipt],
        *,
        stage_cross_view_evidence: bool = False,
    ) -> str | None:
        if set(formal_slot_receipts) != set(BODY_SLOT_KEYS):
            return "body_silhouette_cross_view_parity_receipts_missing"
        for receipt in formal_slot_receipts.values():
            selected = [candidate for candidate in receipt.candidates if candidate.selected_as_winner]
            if len(selected) != 1:
                return "body_silhouette_cross_view_parity_winner_missing"
            issue_codes = set(selected[0].shared_review.issue_codes)
            if issue_codes.intersection(BODY_SILHOUETTE_CROSS_VIEW_PARITY_BLOCKING_ISSUE_CODES):
                return "body_silhouette_cross_view_parity_mismatch"
            if BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE not in set(
                selected[0].shared_review.evidence_codes
            ) and not stage_cross_view_evidence:
                return "body_silhouette_cross_view_parity_evidence_missing"
        return None

    @staticmethod
    def _body_silhouette_reference_assisted_stage_cross_view_evidence(
        formal_slot_receipts: dict[str, FormalSlotReceipt],
        *,
        body_refresh_analysis_context: BodyRefreshAnalysisContext | None,
        body_refresh_attempt_identity: BodyRefreshAttemptIdentity | None,
        body_source_admission: BodySourceAdmission | None,
    ) -> bool:
        """Return true when the completed refresh owns stage-level parity proof.

        Real candidate review is single-image: it can verify source-standard
        body structure but cannot honestly carry cross-view evidence before
        all three views exist.  For strict reference-assisted refreshes, the
        three formal receipts plus one frozen five-source morphology context
        provide the stage-level boundary.  Ordinary Body preparation and any
        missing/forged context still require per-review cross-view evidence.
        """

        if set(formal_slot_receipts) != set(BODY_SLOT_KEYS):
            return False
        if not isinstance(body_refresh_analysis_context, BodyRefreshAnalysisContext):
            return False
        if not isinstance(body_refresh_attempt_identity, BodyRefreshAttemptIdentity):
            return False
        if not isinstance(body_source_admission, BodySourceAdmission):
            return False
        if body_refresh_analysis_context.source_mode != "reference_assisted":
            return False
        if (
            body_refresh_analysis_context.attempt_id != body_refresh_attempt_identity.attempt_id
            or body_refresh_analysis_context.append_only_revision
            != body_refresh_attempt_identity.append_only_revision
        ):
            return False
        if len(body_source_admission.body_evidence_ids) != 5:
            return False
        if (
            body_refresh_analysis_context.source_evidence_id_digest
            != body_source_admission.source_evidence_id_digest()
        ):
            return False
        required_single_view_evidence = {
            BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES[dimension]
            for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS
        }
        for receipt in formal_slot_receipts.values():
            selected = [candidate for candidate in receipt.candidates if candidate.selected_as_winner]
            if len(selected) != 1:
                return False
            shared_review = selected[0].shared_review
            if not shared_review.passed:
                return False
            evidence_codes = set(shared_review.evidence_codes)
            issue_codes = set(shared_review.issue_codes)
            if not required_single_view_evidence.issubset(evidence_codes):
                return False
            if issue_codes.intersection(BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES):
                return False
            if issue_codes.intersection(BODY_SILHOUETTE_CROSS_VIEW_PARITY_BLOCKING_ISSUE_CODES):
                return False
        return True

    def prepare_expression_slot(
        self,
        card: CharacterCardState,
        *,
        expression: ExpressionKey,
        front_output_id: str,
        user_intent: str,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        generation_channel: Literal["provider", "mcp"] = "provider",
        review_only_resume: bool = False,
    ) -> CharacterCardStageResult:
        """Prepare one explicit expression slot outside the default set.

        This preserves Doc196 compatibility: a user may explicitly request a
        lower-intensity ``expression.smile`` card, but the default Professional
        positive deliverable remains ``expression.laugh`` and activation still
        depends on the current required slots only.
        """

        self._require_face_active(card, front_output_id)
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        request = ExpressionPreparationRequest(
            expression=expression,
            front_output_id=front_output_id,
            user_intent=user_intent,
        )
        slot_key = f"expression.{expression}"
        slots = dict(card.expression_slots)
        slots.setdefault(slot_key, CharacterCardSlot(slot_key=slot_key, module="expression_set"))  # type: ignore[arg-type]
        attempts: list[CharacterCardCandidateAttempt] = []
        winner, expression_attempts, slot_failures, formal_receipt = self._prepare_slot(
            card=card,
            module="expression_set",
            slot_key=slot_key,
            project_id=project_id,
            people_asset_id=people_asset_id,
            reference_output_ids=request.reference_output_ids,
            user_intent=request.user_intent,
            source_class=None,
            generation_channel=generation_channel,
            review_only_resume=review_only_resume,
            attempts=attempts,
        )
        attempts.extend(expression_attempts)
        if winner is None:
            failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
            if slot_key not in EXPRESSION_SLOT_KEYS:
                slots[slot_key] = CharacterCardSlot(slot_key=slot_key, module="expression_set", state="blocked")  # type: ignore[arg-type]
                failed_card = card.model_copy(
                    update={
                        "expression_slots": slots,
                        "expression_set_status": card.expression_set_status if card.expression_set_status == "active" else "partial",
                        "last_failed_module": "expression_set",
                        "last_failed_slot_key": slot_key,
                        "last_failure_code": failure_code,
                        "last_failure_details": None,
                        "last_failure_attempt_count": self._failure_attempt_count(slot_failures),
                        "resume_available": True,
                        "append_only_revision": card.append_only_revision + 1,
                    }
                )
            else:
                failed_card = self._blocked_card(
                    card,
                    module="expression_set",
                    slot_key=slot_key,
                    failure_code=failure_code,
                    failure_attempt_count=self._failure_attempt_count(slot_failures),
                    slots=slots,
                    status_field="expression_set_status",
                )
            blocked_updates = {"pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures)}
            if failure_code == "character_card_shared_review_failed":
                blocked_updates["last_review_repair_context"] = self._failure_review_repair_context(slot_failures)
            return CharacterCardStageResult(
                status="blocked",
                card=failed_card.model_copy(update=blocked_updates),
                attempts=attempts,
                winner_output_ids={},
                failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                failures=slot_failures,
                mcp_handoff_ids=self._mcp_handoff_ids(slot_failures),
            )
        slots[slot_key] = self._winner_slot(
            module="expression_set",
            slot_key=slot_key,
            winner=winner,
            formal_slot_receipt=formal_receipt,
        )
        next_status = card.expression_set_status if card.expression_set_status == "active" else "partial"
        updated = card.model_copy(
            update={
                "expression_slots": slots,
                "expression_set_status": next_status,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(
            status="review",
            card=updated,
            attempts=attempts,
            winner_output_ids={slot_key: winner.output_id},
            failures=slot_failures,
            formal_slot_receipts={slot_key: formal_receipt} if formal_receipt is not None else {},
        )

    def prepare_body_silhouette(
        self,
        card: CharacterCardState,
        *,
        face_reference_output_ids: list[str],
        source_class: BodySourceClass,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        body_evidence_ids: list[str] | None = None,
        consent_provenance_id: str | None = None,
        user_intent: str | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
        body_refresh_presentation_intent: BodyRefreshPresentationIntent | None = None,
    ) -> CharacterCardStageResult:
        if card.face_identity_status != "active":
            raise ValueError("Body Silhouette requires an active Face Identity module")
        request = BodyPreparationRequest(
            source_class=source_class,
            face_reference_output_ids=face_reference_output_ids,
            body_evidence_ids=list(body_evidence_ids or []),
            consent_provenance_id=consent_provenance_id,
        )
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        if not str(user_intent or "").strip():
            raise ValueError("Body Silhouette requires Brain/user-owned body preparation intent")
        attempts: list[CharacterCardCandidateAttempt] = []
        winners: dict[str, str] = {}
        formal_slot_receipts: dict[str, FormalSlotReceipt] = {}
        failures: list[CharacterCardFailureEvent] = []
        slots = dict(card.body_slots)
        for slot_key in BODY_SLOT_KEYS:
            existing = slots[slot_key]
            if existing.state in {"winner_selected", "active"} and existing.output_id:
                winners[slot_key] = existing.output_id
                if existing.formal_slot_receipt is not None:
                    receipt = FormalSlotReceipt.model_validate(existing.formal_slot_receipt)
                    if receipt.module != "body_silhouette":
                        raise ValueError("Body formal receipt module mismatch")
                    if receipt.slot_key != slot_key:
                        raise ValueError("Body formal receipt slot mismatch")
                    if receipt.winner_output_id != existing.output_id:
                        raise ValueError("Body formal receipt output mismatch")
                    formal_slot_receipts[slot_key] = receipt
                continue
            winner, slot_attempts, slot_failures, formal_receipt = self._prepare_slot(
                card=card,
                module="body_silhouette",
                slot_key=slot_key,
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=user_intent,
                source_class=source_class,
                body_source_admission=request.source_admission(),
                body_refresh_source_mode=None,
                body_model_context=None,
                body_refresh_contract_required=False,
                consent_provenance_id=consent_provenance_id,
                generation_channel=generation_channel,
                attempts=attempts,
            )
            attempts.extend(slot_attempts)
            failures.extend(slot_failures)
            if formal_receipt is not None and self.formal_receipt_callback is not None:
                self.formal_receipt_callback(formal_receipt)
            if winner is None:
                failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
                failure_details = self._latest_failure_details(slot_failures)
                return CharacterCardStageResult(
                    status="blocked",
                    card=self._blocked_card(
                        card,
                        module="body_silhouette",
                        slot_key=slot_key,
                        failure_code=failure_code,
                        failure_details=failure_details,
                        failure_attempt_count=self._failure_attempt_count(slot_failures),
                        slots=slots,
                        status_field="body_silhouette_status",
                    ).model_copy(
                        update={"pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures)}
                    ),
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                    failures=failures,
                    mcp_handoff_ids=self._mcp_handoff_ids(failures),
                )
            slots[slot_key] = self._winner_slot(
                module="body_silhouette",
                slot_key=slot_key,
                winner=winner,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
                formal_slot_receipt=formal_receipt,
            )
            if formal_receipt is not None:
                formal_slot_receipts[slot_key] = formal_receipt
            winners[slot_key] = winner.output_id
        parity_failure_code = self._body_silhouette_cross_view_parity_failure(formal_slot_receipts)
        if parity_failure_code:
            failure = CharacterCardFailureEvent(
                module="body_silhouette",
                slot_key="body.front_full",
                candidate_index=self.CANDIDATE_COUNT,
                failure_code=parity_failure_code,
            )
            failures.append(failure)
            return CharacterCardStageResult(
                status="blocked",
                card=self._blocked_card(
                    card,
                    module="body_silhouette",
                    slot_key="body.front_full",
                    failure_code=parity_failure_code,
                    failure_attempt_count=self.CANDIDATE_COUNT,
                    slots=slots,
                    status_field="body_silhouette_status",
                ),
                attempts=attempts,
                winner_output_ids=winners,
                failure_codes=[parity_failure_code],
                failures=failures,
            )
        updated = card.model_copy(
            update={
                "body_slots": slots,
                "body_silhouette_status": "reviewing",
                "body_silhouette_version_id": f"body_{uuid4().hex}",
                "body_activation_confirmed": False,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(
            status="review",
            card=updated,
            attempts=attempts,
            winner_output_ids=winners,
            failures=failures,
            formal_slot_receipts=formal_slot_receipts,
        )

    def refresh_body_silhouette(
        self,
        card: CharacterCardState,
        *,
        face_reference_output_ids: list[str],
        source_class: BodySourceClass,
        project_id: str = "project",
        people_asset_id: str = "people_asset",
        body_evidence_ids: list[str] | None = None,
        consent_provenance_id: str | None = None,
        user_intent: str | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
        body_refresh_presentation_intent: BodyRefreshPresentationIntent | None = None,
        body_refresh_analysis_context: BodyRefreshAnalysisContext | None = None,
        body_refresh_attempt_identity: BodyRefreshAttemptIdentity | None = None,
        resume_slot_key: str | None = None,
        resume_candidate_index: int | None = None,
        prior_reviewed_candidates: dict[tuple[str, int], CharacterCardCandidateAttempt] | None = None,
    ) -> CharacterCardStageResult:
        """Append a pending Body Silhouette refresh without replacing active slots."""

        if card.face_identity_status != "active":
            raise ValueError("Body Silhouette refresh requires an active Face Identity module")
        if card.body_silhouette_status != "active":
            raise ValueError("Body Silhouette refresh requires active Body Silhouette slots")
        if card.body_silhouette_refresh_status == "reviewing" or (
            card.body_silhouette_refresh_status != "blocked" and card.body_silhouette_refresh_slots
        ):
            raise ValueError("body_silhouette_refresh_pending")
        if self.generator is None or self.reviewer is None:
            raise RuntimeError("shared Character Card candidate/review seam is unavailable")
        if not str(user_intent or "").strip():
            raise ValueError("Body Silhouette refresh requires Brain/user-owned body preparation intent")
        request = BodyPreparationRequest(
            source_class=source_class,
            face_reference_output_ids=face_reference_output_ids,
            body_evidence_ids=list(body_evidence_ids or []),
            consent_provenance_id=consent_provenance_id,
            strict_body_source_repair=True,
        )
        body_source_admission = request.source_admission()
        if source_class == "brain_inferred" and body_refresh_analysis_context is not None:
            raise ValueError("body_proportion_analysis_context_source_mode_invalid")
        if source_class == "observed" and generation_channel == "mcp":
            if body_refresh_analysis_context is None:
                raise ValueError("body_proportion_analysis_context_missing")
            if body_refresh_attempt_identity is None:
                raise ValueError("body_proportion_analysis_attempt_missing")
            if (
                body_refresh_analysis_context.attempt_id
                != body_refresh_attempt_identity.attempt_id
                or body_refresh_analysis_context.append_only_revision
                != body_refresh_attempt_identity.append_only_revision
            ):
                raise ValueError("body_proportion_analysis_context_attempt_mismatch")
            if len(body_source_admission.body_evidence_ids) != 5:
                raise ValueError("body_refresh_source_admission_five_sources_required")
            if body_refresh_analysis_context.source_evidence_id_digest != body_source_admission.source_evidence_id_digest():
                raise ValueError("body_refresh_source_admission_digest_mismatch")
        attempts: list[CharacterCardCandidateAttempt] = []
        winners: dict[str, str] = {}
        formal_slot_receipts: dict[str, FormalSlotReceipt] = {}
        failures: list[CharacterCardFailureEvent] = []
        candidate_lifecycle_checkpoints: list[CharacterCardCandidateLifecycleCheckpoint] = []
        generation_card = card.model_copy(
            update={
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_review_repair_context": None,
                "pending_mcp_handoff_ids": [],
                "resume_available": False,
            }
        )
        body_refresh_attempt_identity = body_refresh_attempt_identity or BodyRefreshAttemptIdentity.create(
            append_only_revision=card.append_only_revision + 1
        )
        refresh_slots = self._validated_refresh_slots_for_resume(
            card,
            attempt_id=body_refresh_attempt_identity.attempt_id,
            resume_slot_key=resume_slot_key,
        )
        for preserved_slot_key, preserved_slot in refresh_slots.items():
            if preserved_slot.formal_slot_receipt is None or not preserved_slot.output_id:
                raise ValueError("body_refresh_resume_formal_receipt_missing")
            formal_slot_receipts[preserved_slot_key] = FormalSlotReceipt.model_validate(
                preserved_slot.formal_slot_receipt
            )
            winners[preserved_slot_key] = preserved_slot.output_id
        resume_started = resume_slot_key is None
        for slot_key in BODY_SLOT_KEYS:
            if not resume_started:
                if slot_key != resume_slot_key:
                    continue
                resume_started = True
            winner, slot_attempts, slot_failures, formal_receipt = self._prepare_slot(
                card=generation_card,
                module="body_silhouette",
                slot_key=slot_key,
                project_id=project_id,
                people_asset_id=people_asset_id,
                reference_output_ids=request.reference_output_ids,
                user_intent=user_intent,
                source_class=source_class,
                body_source_admission=body_source_admission,
                body_refresh_source_mode=request.body_refresh_source_mode,
                body_model_context=request.body_model_context,
                body_refresh_contract_required=True,
                body_refresh_presentation_intent=body_refresh_presentation_intent,
                consent_provenance_id=consent_provenance_id,
                generation_channel=generation_channel,
                body_refresh_attempt_identity=body_refresh_attempt_identity,
                body_refresh_analysis_context=body_refresh_analysis_context,
                start_candidate_index_override=(
                    resume_candidate_index if slot_key == resume_slot_key else None
                ),
                prior_reviewed_attempts={
                    index: attempt
                    for (prior_slot, index), attempt in (prior_reviewed_candidates or {}).items()
                    if prior_slot == slot_key
                },
                attempts=attempts,
                candidate_lifecycle_checkpoints=candidate_lifecycle_checkpoints,
            )
            attempts.extend(slot_attempts)
            failures.extend(slot_failures)
            if formal_receipt is not None and self.formal_receipt_callback is not None:
                self.formal_receipt_callback(formal_receipt)
            if winner is None:
                failure_code = slot_failures[-1].failure_code if slot_failures else f"{slot_key}_review_failed"
                failure_details = self._latest_failure_details(slot_failures)
                blocked = card.model_copy(
                    update={
                        "body_silhouette_refresh_status": "blocked",
                        "body_silhouette_refresh_version_id": body_refresh_attempt_identity.attempt_id,
                        "body_silhouette_refresh_slots": refresh_slots,
                        "last_failed_module": "body_silhouette",
                        "last_failed_slot_key": slot_key,
                        "last_failure_code": failure_code,
                        "last_failure_details": failure_details,
                        "last_failure_attempt_count": self._failure_attempt_count(slot_failures),
                        "resume_available": False,
                        "append_only_revision": card.append_only_revision + 1,
                        "pending_mcp_handoff_ids": self._mcp_handoff_ids(slot_failures),
                    }
                )
                return CharacterCardStageResult(
                    status="blocked",
                    card=blocked,
                    attempts=attempts,
                    winner_output_ids=winners,
                    failure_codes=list(dict.fromkeys([f"{slot_key}_no_reviewed_winner", *[item.failure_code for item in slot_failures]])),
                    failures=failures,
                    candidate_lifecycle_checkpoints=candidate_lifecycle_checkpoints,
                    mcp_handoff_ids=self._mcp_handoff_ids(failures),
                )
            refresh_slots[slot_key] = self._winner_slot(
                module="body_silhouette",
                slot_key=slot_key,
                winner=winner,
                source_class=source_class,
                consent_provenance_id=consent_provenance_id,
                formal_slot_receipt=formal_receipt,
            )
            if formal_receipt is not None:
                formal_slot_receipts[slot_key] = formal_receipt
            winners[slot_key] = winner.output_id
        stage_cross_view_evidence = self._body_silhouette_reference_assisted_stage_cross_view_evidence(
            formal_slot_receipts,
            body_refresh_analysis_context=body_refresh_analysis_context,
            body_refresh_attempt_identity=body_refresh_attempt_identity,
            body_source_admission=body_source_admission,
        )
        parity_failure_code = self._body_silhouette_cross_view_parity_failure(
            formal_slot_receipts,
            stage_cross_view_evidence=stage_cross_view_evidence,
        )
        if parity_failure_code:
            failure = CharacterCardFailureEvent(
                module="body_silhouette",
                slot_key="body.front_full",
                candidate_index=self.CANDIDATE_COUNT,
                failure_code=parity_failure_code,
            )
            failures.append(failure)
            blocked = card.model_copy(
                update={
                    "body_silhouette_refresh_status": "blocked",
                    "body_silhouette_refresh_version_id": body_refresh_attempt_identity.attempt_id,
                    "body_silhouette_refresh_slots": refresh_slots,
                    "last_failed_module": "body_silhouette",
                    "last_failed_slot_key": "body.front_full",
                    "last_failure_code": parity_failure_code,
                    "last_failure_details": None,
                    "last_failure_attempt_count": self.CANDIDATE_COUNT,
                    "resume_available": False,
                    "append_only_revision": card.append_only_revision + 1,
                }
            )
            return CharacterCardStageResult(
                status="blocked",
                card=blocked,
                attempts=attempts,
                winner_output_ids=winners,
                failure_codes=[parity_failure_code],
                failures=failures,
                candidate_lifecycle_checkpoints=candidate_lifecycle_checkpoints,
            )
        updated = card.model_copy(
            update={
                "body_silhouette_refresh_status": "reviewing",
                "body_silhouette_refresh_version_id": body_refresh_attempt_identity.attempt_id,
                "body_silhouette_refresh_slots": refresh_slots,
                "append_only_revision": card.append_only_revision + 1,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
            }
        )
        return CharacterCardStageResult(
            status="review",
            card=updated,
            attempts=attempts,
            winner_output_ids=winners,
            failures=failures,
            formal_slot_receipts=formal_slot_receipts,
            candidate_lifecycle_checkpoints=candidate_lifecycle_checkpoints,
        )

    @staticmethod
    def _validated_refresh_slots_for_resume(
        card: CharacterCardState,
        *,
        attempt_id: str,
        resume_slot_key: str | None,
    ) -> dict[str, CharacterCardSlot]:
        """Keep only formally verified slots from this exact refresh attempt.

        A resume may continue at side/rear after an earlier slot was formally
        accepted.  Refresh slots are visible card state, so they must be
        validated against the attempt/version before being carried forward;
        stale blocked slots are never treated as winners.
        """

        if resume_slot_key is None:
            return {}
        if resume_slot_key not in BODY_SLOT_KEYS:
            raise ValueError("body_refresh_resume_slot_invalid")
        if card.body_silhouette_refresh_slots and card.body_silhouette_refresh_version_id != attempt_id:
            raise ValueError("body_refresh_resume_attempt_binding_mismatch")
        target_index = BODY_SLOT_KEYS.index(resume_slot_key)
        preserved: dict[str, CharacterCardSlot] = {}
        for slot_key, slot in card.body_silhouette_refresh_slots.items():
            if slot_key not in BODY_SLOT_KEYS:
                raise ValueError("body_refresh_resume_slot_invalid")
            slot_index = BODY_SLOT_KEYS.index(slot_key)
            if slot_index >= target_index:
                raise ValueError("body_refresh_resume_stale_slot_projection")
            if slot.state != "winner_selected" or slot.formal_slot_receipt is None:
                raise ValueError("body_refresh_resume_formal_receipt_missing")
            receipt = validate_formal_slot_receipt_for_activation(
                FormalSlotReceipt.model_validate(slot.formal_slot_receipt)
            )
            if (
                receipt.module != "body_silhouette"
                or receipt.slot_key != slot_key
                or receipt.acceptance_mode != "standard_three_candidate"
                or receipt.reviewed_candidate_count != CharacterCardPreparationService.CANDIDATE_COUNT
                or receipt.winner_output_id != slot.output_id
            ):
                raise ValueError("body_refresh_resume_formal_receipt_invalid")
            preserved[slot_key] = slot.model_copy(update={"formal_slot_receipt": receipt})
        return preserved

    def resume_body_silhouette_formal_only(
        self,
        card: CharacterCardState,
        *,
        slot_key: str,
        body_refresh_attempt_identity: BodyRefreshAttemptIdentity,
        prior_reviewed_candidates: dict[tuple[str, int], CharacterCardCandidateAttempt],
        consent_provenance_id: str | None = None,
    ) -> CharacterCardStageResult:
        """Reconstitute formal acceptance without generating another candidate."""

        if slot_key not in BODY_SLOT_KEYS:
            raise ValueError("body_refresh_formal_only_slot_invalid")
        if card.body_silhouette_refresh_version_id != body_refresh_attempt_identity.attempt_id:
            raise ValueError("body_refresh_formal_only_attempt_binding_mismatch")
        attempts = [
            prior_reviewed_candidates[(slot_key, index)]
            for index in range(1, self.CANDIDATE_COUNT + 1)
            if (slot_key, index) in prior_reviewed_candidates
        ]
        if len(attempts) != self.CANDIDATE_COUNT:
            raise ValueError("body_refresh_formal_only_reviewed_candidates_missing")
        receipt = self._formal_body_slot_receipt(slot_key=slot_key, attempts=attempts)
        winner_attempt = next(
            attempt
            for attempt in attempts
            if attempt.candidate.output_id == receipt.winner_output_id
        )
        preserved = self._validated_refresh_slots_for_resume(
            card,
            attempt_id=body_refresh_attempt_identity.attempt_id,
            resume_slot_key=slot_key,
        )
        if slot_key in preserved:
            raise ValueError("body_refresh_formal_only_receipt_already_projected")
        preserved[slot_key] = self._winner_slot(
            module="body_silhouette",
            slot_key=slot_key,
            winner=winner_attempt.candidate,
            source_class="observed",
            consent_provenance_id=consent_provenance_id
            or winner_attempt.request.consent_provenance_id,
            formal_slot_receipt=receipt,
        )
        if self.formal_receipt_callback is not None:
            self.formal_receipt_callback(receipt)
        updated = card.model_copy(
            update={
                "body_silhouette_refresh_status": "blocked",
                "body_silhouette_refresh_version_id": body_refresh_attempt_identity.attempt_id,
                "body_silhouette_refresh_slots": preserved,
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "resume_available": False,
            }
        )
        return CharacterCardStageResult(
            status="blocked",
            card=updated,
            attempts=attempts,
            winner_output_ids={slot_key: winner_attempt.candidate.output_id},
            formal_slot_receipts={slot_key: receipt},
        )

    def _prepare_slot(
        self,
        *,
        card: CharacterCardState,
        module: Literal["expression_set", "body_silhouette"],
        slot_key: str,
        project_id: str,
        people_asset_id: str,
        reference_output_ids: list[str],
        user_intent: str,
        source_class: BodySourceClass | None,
        body_source_admission: BodySourceAdmission | None = None,
        body_refresh_source_mode: BodyRefreshSourceMode | None = None,
        body_model_context: BodyRefreshBodyModelContext | None = None,
        body_refresh_contract_required: bool = False,
        body_refresh_presentation_intent: BodyRefreshPresentationIntent | None = None,
        consent_provenance_id: str | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
        body_refresh_attempt_identity: BodyRefreshAttemptIdentity | None = None,
        body_refresh_analysis_context: BodyRefreshAnalysisContext | None = None,
        review_only_resume: bool = False,
        start_candidate_index_override: int | None = None,
        prior_reviewed_attempts: dict[int, CharacterCardCandidateAttempt] | None = None,
        attempts: list[CharacterCardCandidateAttempt],
        candidate_lifecycle_checkpoints: list[CharacterCardCandidateLifecycleCheckpoint] | None = None,
    ) -> tuple[
        CharacterCardCandidateResult | None,
        list[CharacterCardCandidateAttempt],
        list[CharacterCardFailureEvent],
        FormalSlotReceipt | None,
    ]:
        from .anchor_pack import AnchorCandidateUnavailable

        slot_attempts: list[CharacterCardCandidateAttempt] = []
        slot_failures: list[CharacterCardFailureEvent] = []
        lifecycle_checkpoints = (
            candidate_lifecycle_checkpoints
            if candidate_lifecycle_checkpoints is not None
            else []
        )
        passing: list[tuple[CharacterCardCandidateResult, Any]] = []
        acceptance_core = SlotAcceptanceCore(quality_gate=self._quality_gate_for_slot(slot_key))
        attempt_round = int(card.slot_retry_rounds.get(slot_key, 1))
        start_candidate_index = self._candidate_start_index(
            card,
            module=module,
            slot_key=slot_key,
            generation_channel=generation_channel,
            review_only_resume=review_only_resume,
        )
        if start_candidate_index_override is not None:
            if type(start_candidate_index_override) is not int or not 1 <= start_candidate_index_override <= self.CANDIDATE_COUNT:
                raise ValueError("body_refresh_resume_candidate_index_invalid")
            start_candidate_index = start_candidate_index_override
        prior_review_repair: dict[str, Any] | None = self._resumable_review_repair_context(
            card,
            module=module,
            slot_key=slot_key,
            generation_channel=generation_channel,
            start_candidate_index=start_candidate_index,
        )
        if start_candidate_index > self.CANDIDATE_COUNT:
            return (
                None,
                slot_attempts,
                [
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=self.CANDIDATE_COUNT,
                        attempt_round=attempt_round,
                        failure_code=str(card.last_failure_code or "character_card_shared_review_failed"),
                    )
                ],
                None,
            )
        # A durable resume cursor starts generation at the next candidate, but
        # formal acceptance still needs the already reviewed candidates from
        # this slot.  Reconstitute those prior attempts before the new loop;
        # they are evidence from the authoritative job/review chain, not new
        # generator work and not a second acceptance implementation.
        for prior_index in sorted(prior_reviewed_attempts or {}):
            if prior_index >= start_candidate_index:
                continue
            prior_attempt = (prior_reviewed_attempts or {}).get(prior_index)
            if prior_attempt is None:
                continue
            if (
                prior_attempt.request.slot_key != slot_key
                or prior_attempt.candidate.candidate_index != prior_index
            ):
                raise ValueError("body_refresh_prior_candidate_binding_mismatch")
            lifecycle_checkpoints.append(
                self._candidate_lifecycle_checkpoint(
                    module=module,
                    slot_key=slot_key,
                    candidate_index=prior_index,
                    lifecycle_phase="review",
                    status="completed",
                )
            )
            slot_attempts.append(prior_attempt)
            if acceptance_core.accepts_review(prior_attempt.review):
                passing.append((prior_attempt.candidate, prior_attempt.review))
            else:
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=prior_index,
                        attempt_round=attempt_round,
                        failure_code="character_card_shared_review_failed",
                    )
                )
        for candidate_index in range(start_candidate_index, self.CANDIDATE_COUNT + 1):
            request = CharacterCardCandidateRequest(
                project_id=project_id,
                people_asset_id=people_asset_id,
                card_version_id=card.card_version_id,
                module=module,
                slot_key=slot_key,  # type: ignore[arg-type]
                candidate_index=candidate_index,
                attempt_round=attempt_round,
                reference_output_ids=list(reference_output_ids),
                user_intent=user_intent,
                source_class=source_class,
                body_source_admission=body_source_admission,
                body_refresh_source_mode=body_refresh_source_mode,
                body_model_context=body_model_context,
                body_refresh_contract_required=body_refresh_contract_required,
                body_refresh_presentation_intent=body_refresh_presentation_intent,
                consent_provenance_id=consent_provenance_id,
                generation_channel=generation_channel,
                body_refresh_attempt_identity=body_refresh_attempt_identity,
                body_refresh_analysis_context=body_refresh_analysis_context,
                body_refresh_target_age_scope=(
                    body_refresh_analysis_context.target_age_scope
                    if body_refresh_analysis_context is not None
                    else None
                ),
                mcp_handoff_id=self._resumable_mcp_handoff_id(
                    card,
                    module=module,
                    slot_key=slot_key,
                    candidate_index=candidate_index,
                    review_only_resume=review_only_resume,
                ),
                prior_review_repair=prior_review_repair,
                review_only_resume=review_only_resume,
            )
            prior_attempt = (prior_reviewed_attempts or {}).get(candidate_index)
            if prior_attempt is not None:
                if prior_attempt.request.slot_key != slot_key or prior_attempt.candidate.candidate_index != candidate_index:
                    raise ValueError("body_refresh_prior_candidate_binding_mismatch")
                lifecycle_checkpoints.append(
                    self._candidate_lifecycle_checkpoint(
                        module=module,
                        slot_key=slot_key,
                        candidate_index=candidate_index,
                        lifecycle_phase="review",
                        status="completed",
                    )
                )
                slot_attempts.append(prior_attempt)
                if acceptance_core.accepts_review(prior_attempt.review):
                    passing.append((prior_attempt.candidate, prior_attempt.review))
                else:
                    slot_failures.append(
                        CharacterCardFailureEvent(
                            module=module,
                            slot_key=slot_key,  # type: ignore[arg-type]
                            candidate_index=candidate_index,
                            attempt_round=attempt_round,
                            failure_code="character_card_shared_review_failed",
                        )
                    )
                continue
            try:
                candidate = self.generator.generate(request)
            except AnchorCandidateUnavailable as exc:
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=candidate_index,
                        attempt_round=attempt_round,
                        failure_code=exc.failure_code,
                        mcp_handoff_id=exc.mcp_handoff_id,
                        candidate_lifecycle=self._anchor_candidate_lifecycle_projection(
                            module=module,
                            slot_key=slot_key,
                            candidate_index=candidate_index,
                            failure_code=exc.failure_code,
                        ),
                    )
                )
                if generation_channel == "mcp" and exc.failure_code in {
                    "mcp_materialization_pending",
                    "mcp_review_pending",
                    "mcp_materialization_operation_ambiguous",
                    "mcp_materialization_checkpoint_mismatch",
                    "mcp_materialization_projection_unavailable",
                }:
                    return None, slot_attempts, slot_failures, None
                continue
            except CharacterCardCandidateLifecycleBoundaryError as exc:
                lifecycle = self._candidate_lifecycle_projection_from_exception(
                    exc,
                    module=module,
                    slot_key=slot_key,
                    candidate_index=candidate_index,
                    default_phase="generation",
                    default_family="candidate_generation",
                    default_code="unknown_candidate_generation_failure",
                )
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=candidate_index,
                        attempt_round=attempt_round,
                        failure_code="character_card_candidate_generation_failed",
                        candidate_lifecycle=lifecycle,
                    )
                )
                if module == "body_silhouette" and _is_body_delivery_slot(slot_key):
                    slot_failures.append(
                        CharacterCardFailureEvent(
                            module=module,
                            slot_key=slot_key,  # type: ignore[arg-type]
                            candidate_index=candidate_index,
                            attempt_round=attempt_round,
                            failure_code="character_card_formal_slot_receipt_invalid",
                            failure_details=self._formal_body_slot_failure_projection(
                                slot_key=slot_key,
                                attempts=slot_attempts,
                                candidate_generation_failures=slot_failures,
                            ),
                        )
                )
                return None, slot_attempts, slot_failures, None
            lifecycle_checkpoints.append(
                self._candidate_lifecycle_checkpoint(
                    module=module,
                    slot_key=slot_key,
                    candidate_index=candidate_index,
                    lifecycle_phase="review",
                    status="started",
                )
            )
            try:
                review = self.reviewer.review(candidate)
            except CharacterCardCandidateLifecycleBoundaryError as exc:
                lifecycle = self._candidate_lifecycle_projection_from_exception(
                    exc,
                    module=module,
                    slot_key=slot_key,
                    candidate_index=candidate_index,
                    default_phase="review",
                    default_family="candidate_review",
                    default_code="candidate_review_blocked",
                )
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=candidate_index,
                        attempt_round=attempt_round,
                        failure_code="character_card_shared_review_failed",
                        candidate_lifecycle=lifecycle,
                    )
                )
                lifecycle_checkpoints.append(
                    self._candidate_lifecycle_checkpoint(
                        module=module,
                        slot_key=slot_key,
                        candidate_index=candidate_index,
                        lifecycle_phase="review",
                        status="blocked",
                        failure_family=lifecycle.failure_family,
                        failure_code=lifecycle.failure_code,
                    )
                )
                if module == "body_silhouette" and _is_body_delivery_slot(slot_key):
                    slot_failures.append(
                        CharacterCardFailureEvent(
                            module=module,
                            slot_key=slot_key,  # type: ignore[arg-type]
                            candidate_index=candidate_index,
                            attempt_round=attempt_round,
                            failure_code="character_card_formal_slot_receipt_invalid",
                            failure_details=self._formal_body_slot_failure_projection(
                                slot_key=slot_key,
                                attempts=slot_attempts,
                                candidate_generation_failures=slot_failures,
                            ),
                        )
                    )
                return None, slot_attempts, slot_failures, None
            lifecycle_checkpoints.append(
                self._candidate_lifecycle_checkpoint(
                    module=module,
                    slot_key=slot_key,
                    candidate_index=candidate_index,
                    lifecycle_phase="review",
                    status="completed",
                )
            )
            attempt = CharacterCardCandidateAttempt(request=request, candidate=candidate, review=review)
            slot_attempts.append(attempt)
            review_passed = acceptance_core.accepts_review(review)
            if self.candidate_checkpoint_callback is not None:
                self.candidate_checkpoint_callback(request, candidate, review, "pass" if review_passed else "fail")
            if review_passed:
                passing.append((candidate, review))
            else:
                repair_context = shared_review_repair_context_from_decision(
                    candidate_id=candidate.candidate_id,
                    output_id=candidate.output_id,
                    issue_codes=getattr(review, "issue_codes", []) or [],
                    shared_review_receipts=getattr(review, "shared_review_receipts", []) or [],
                )
                if repair_context:
                    prior_review_repair = repair_context
                if generation_channel == "mcp":
                    slot_failures.append(
                        CharacterCardFailureEvent(
                            module=module,
                            slot_key=slot_key,  # type: ignore[arg-type]
                            candidate_index=candidate_index,
                            attempt_round=attempt_round,
                            failure_code="character_card_shared_review_failed",
                            review_repair_context=repair_context,
                        )
                    )
                    return None, slot_attempts, slot_failures, None
        formal_slot_ready = (
            (
                module == "expression_set"
                and _is_expression_delivery_slot(slot_key)
            )
            or (
                module == "body_silhouette"
                and _is_body_delivery_slot(slot_key)
            )
        ) and len(slot_attempts) == self.CANDIDATE_COUNT
        if not passing and not formal_slot_ready:
            if not slot_failures:
                slot_failures = [
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=index,
                        attempt_round=attempt_round,
                        failure_code="character_card_shared_review_failed",
                    )
                    for index in range(1, self.CANDIDATE_COUNT + 1)
                ]
            return None, slot_attempts, slot_failures, None
        if (
            module == "expression_set"
            and _is_expression_delivery_slot(slot_key)
        ) or (
            module == "body_silhouette"
            and _is_body_delivery_slot(slot_key)
        ):
            if module == "body_silhouette":
                lifecycle_checkpoints.append(
                    self._candidate_lifecycle_checkpoint(
                        module=module,
                        slot_key=slot_key,
                        candidate_index=self.CANDIDATE_COUNT,
                        lifecycle_phase="formal_receipt",
                        status="started",
                    )
                )
            try:
                if module == "expression_set":
                    formal_receipt = self._formal_expression_slot_receipt(
                        slot_key=slot_key,
                        attempts=slot_attempts,
                    )
                else:
                    formal_receipt = self._formal_body_slot_receipt(
                        slot_key=slot_key,
                        attempts=slot_attempts,
                    )
            except ValueError:
                if module == "body_silhouette":
                    lifecycle_checkpoints.append(
                        self._candidate_lifecycle_checkpoint(
                            module=module,
                            slot_key=slot_key,
                            candidate_index=min(self.CANDIDATE_COUNT, max(1, len(slot_attempts) or 1)),
                            lifecycle_phase="formal_receipt",
                            status="blocked",
                            failure_family="formal_receipt",
                            failure_code="candidate_formal_receipt_blocked",
                        )
                    )
                failure_details = (
                    self._formal_body_slot_failure_projection(
                        slot_key=slot_key,
                        attempts=slot_attempts,
                        candidate_generation_failures=slot_failures,
                    )
                    if module == "body_silhouette"
                    else None
                )
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=min(self.CANDIDATE_COUNT, max(1, len(slot_attempts) or 1)),
                        attempt_round=attempt_round,
                        failure_code="character_card_formal_slot_receipt_invalid",
                        failure_details=failure_details,
                        candidate_lifecycle=(
                            self._candidate_lifecycle_projection(
                                module=module,
                                slot_key=slot_key,
                                candidate_index=min(self.CANDIDATE_COUNT, max(1, len(slot_attempts) or 1)),
                                lifecycle_phase="formal_receipt",
                                failure_family="formal_receipt",
                                failure_code="candidate_formal_receipt_blocked",
                            )
                            if module == "body_silhouette"
                            else None
                        ),
                    )
                )
                return None, slot_attempts, slot_failures, None
            if module == "body_silhouette":
                lifecycle_checkpoints.append(
                    self._candidate_lifecycle_checkpoint(
                        module=module,
                        slot_key=slot_key,
                        candidate_index=self.CANDIDATE_COUNT,
                        lifecycle_phase="formal_receipt",
                        status="completed",
                    )
                )
            selected = next(
                (
                    attempt.candidate
                    for attempt in slot_attempts
                    if attempt.candidate.candidate_id == formal_receipt.winner_candidate_id
                ),
                None,
            )
            if selected is None:
                slot_failures.append(
                    CharacterCardFailureEvent(
                        module=module,
                        slot_key=slot_key,  # type: ignore[arg-type]
                        candidate_index=min(self.CANDIDATE_COUNT, max(1, len(slot_attempts) or 1)),
                        attempt_round=attempt_round,
                        failure_code="character_card_formal_slot_winner_missing",
                    )
                )
                return None, slot_attempts, slot_failures, None
            return selected, slot_attempts, slot_failures, formal_receipt
        selected = acceptance_core.select_winner(passing)
        return selected, slot_attempts, slot_failures, None

    @staticmethod
    def _failure_review_repair_context(
        failures: list[CharacterCardFailureEvent],
    ) -> dict[str, Any] | None:
        for failure in reversed(failures):
            repair = failure.review_repair_context
            if isinstance(repair, dict) and repair.get("owner") == "v3_shared_visual_cluster":
                return dict(repair)
        return None

    @staticmethod
    def _resumable_review_repair_context(
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        generation_channel: Literal["provider", "mcp"],
        start_candidate_index: int,
    ) -> dict[str, Any] | None:
        if generation_channel != "mcp":
            return None
        if card.last_failed_module != module or card.last_failed_slot_key != slot_key:
            return None
        if card.last_failure_code != "character_card_shared_review_failed":
            return None
        if int(card.last_failure_attempt_count or 0) != start_candidate_index - 1:
            return None
        repair = card.last_review_repair_context
        if not isinstance(repair, dict) or repair.get("owner") != "v3_shared_visual_cluster":
            return None
        return dict(repair)

    @classmethod
    def _candidate_start_index(
        cls,
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        generation_channel: Literal["provider", "mcp"],
        review_only_resume: bool = False,
    ) -> int:
        if generation_channel != "mcp":
            return 1
        if card.last_failed_module != module or card.last_failed_slot_key != slot_key:
            return 1
        failure_count = int(card.last_failure_attempt_count or 0)
        if failure_count < 1:
            return 1
        if review_only_resume and card.last_failure_code in {
            "mcp_review_pending",
            "mcp_materialization_checkpoint_mismatch",
            "mcp_materialization_projection_unavailable",
        }:
            return min(cls.CANDIDATE_COUNT, max(1, failure_count))
        if card.last_failure_code in {"mcp_materialization_pending", "mcp_review_pending"}:
            return min(cls.CANDIDATE_COUNT, max(1, failure_count))
        if card.last_failure_code == "character_card_shared_review_failed":
            return failure_count + 1
        return 1

    @staticmethod
    def _mcp_handoff_ids(failures: list[CharacterCardFailureEvent]) -> list[str]:
        return list(
            dict.fromkeys(
                str(item.mcp_handoff_id).strip()
                for item in failures
                if str(item.mcp_handoff_id or "").strip()
            )
        )

    @staticmethod
    def _failure_attempt_count(failures: list[CharacterCardFailureEvent]) -> int:
        if not failures:
            return 1
        return min(3, max(1, max(int(item.candidate_index or 1) for item in failures)))

    @staticmethod
    def _latest_failure_details(failures: list[CharacterCardFailureEvent]) -> BodyFormalSlotFailureDetails | None:
        for failure in reversed(failures):
            if failure.failure_details is not None:
                return BodyFormalSlotFailureDetails.model_validate(failure.failure_details)
        return None

    @staticmethod
    def _resumable_mcp_handoff_id(
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        candidate_index: int,
        review_only_resume: bool = False,
    ) -> str | None:
        if card.last_failed_module != module or card.last_failed_slot_key != slot_key:
            return None
        if review_only_resume and card.last_failure_code != "mcp_review_pending":
            return None
        if not review_only_resume and card.last_failure_code not in {"mcp_materialization_pending", "mcp_review_pending"}:
            return None
        if int(card.last_failure_attempt_count or 0) != int(candidate_index):
            return None
        handoff_ids = [str(item).strip() for item in card.pending_mcp_handoff_ids if str(item).strip()]
        if len(handoff_ids) != 1:
            return None
        return handoff_ids[0]

    @staticmethod
    def _blocked_card(
        card: CharacterCardState,
        *,
        module: CharacterCardModule,
        slot_key: str,
        failure_code: str,
        failure_details: BodyFormalSlotFailureDetails | None = None,
        failure_attempt_count: int,
        slots: dict[str, CharacterCardSlot],
        status_field: Literal["expression_set_status", "body_silhouette_status"],
    ) -> CharacterCardState:
        return card.model_copy(
            update={
                status_field: "blocked",
                "expression_slots" if module == "expression_set" else "body_slots": slots,
                "last_failed_module": module,
                "last_failed_slot_key": slot_key,
                "last_failure_code": failure_code,
                "last_failure_details": failure_details,
                "last_failure_attempt_count": min(3, max(1, failure_attempt_count)),
                "resume_available": True,
                "append_only_revision": card.append_only_revision + 1,
            }
        )

    @staticmethod
    def _selection_key(review: Any) -> tuple[Any, ...]:
        return SlotAcceptanceCore.selection_key(review)

    @staticmethod
    def _quality_gate_for_slot(slot_key: str) -> Callable[[Any], bool] | None:
        if slot_key == POSITIVE_EXPRESSION_SLOT_KEY:
            return lambda review: CharacterCardPreparationService._review_allows_slot(slot_key, review)
        return None

    @staticmethod
    def _review_allows_slot(slot_key: str, review: Any) -> bool:
        if slot_key != POSITIVE_EXPRESSION_SLOT_KEY:
            return True
        scores = getattr(review, "identity_scores", None)
        return laugh_expression_receipt_allows_slot(
            evidence_codes=getattr(scores, "evidence_codes", []) or [],
            issue_codes=getattr(review, "issue_codes", []) or [],
        )

    @staticmethod
    def _formal_shared_review_summary(review: Any) -> FormalSlotSharedReviewSummary:
        receipts = [
            item
            for item in getattr(review, "shared_review_receipts", []) or []
            if isinstance(item, dict)
            and item.get("owner") == "v3_shared_visual_cluster"
            and item.get("contract_version") == "v3_character_card_generic_slot_review_receipt_v1"
        ]
        if len(receipts) != 1:
            raise ValueError("Expression formal slot requires one canonical generic shared review receipt")
        summary = FormalSlotSharedReviewSummary.model_validate(receipts[0])
        review_passed = getattr(review, "status", None) == "pass"
        if summary.passed != review_passed:
            raise ValueError("Expression formal shared review status does not match candidate review")
        return summary

    @staticmethod
    def body_refresh_review_receipt_digest(
        candidate: CharacterCardCandidateResult,
        review: Any,
    ) -> str:
        """Return the one safe digest used by durable Body checkpoints.

        The digest is derived only from the typed candidate identity and the
        canonical shared-review receipt.  It never includes provider payload,
        pixels, paths, prompts, or raw Vision response data.
        """

        try:
            shared_review = CharacterCardPreparationService._formal_shared_review_summary(review)
        except ValueError as exc:
            raise ValueError("body_refresh_shared_review_receipt_missing") from exc
        payload = {
            "candidate_id": candidate.candidate_id,
            "candidate_index": candidate.candidate_index,
            "module": candidate.module,
            "output_id": candidate.output_id,
            "slot_key": candidate.slot_key,
            "review_status": str(getattr(review, "status", "")).strip(),
            "shared_review": shared_review.model_dump(mode="json"),
        }
        return hashlib.sha256(
            json.dumps(
                payload,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _formal_requirement_summary(
        *,
        passed: bool,
        evidence_code: str,
        issue_code: str,
    ) -> FormalSlotRequirementSummary:
        return FormalSlotRequirementSummary(
            status="pass" if passed else "fail",
            evidence_codes=[evidence_code if passed else issue_code],
            dimensions={"summary_score": 1.0 if passed else 0.0},
        )

    @staticmethod
    def _formal_generic_framing_passed(candidates: list[FormalSlotCandidateSummary]) -> bool:
        """Use only canonical generic shared review framing evidence."""

        return any(
            candidate.shared_review.passed
            and bool(candidate.shared_review.framing_delta_dimensions)
            for candidate in candidates
        )

    @staticmethod
    def _formal_expression_enhanced_proof(
        *,
        slot_key: str,
        candidate: CharacterCardCandidateResult,
        review: Any,
    ) -> FormalSlotCandidateEnhancedProofSummary:
        expression_model_card_proofs = (
            review.get("expression_model_card_proofs")
            if isinstance(review, Mapping)
            else getattr(review, "expression_model_card_proofs", None)
        )
        if isinstance(expression_model_card_proofs, Mapping):
            operation_id = str(getattr(candidate, "operation_id", "") or "").strip()
            round_id = str(getattr(candidate, "round_id", "") or "").strip()
            if not operation_id or not round_id:
                return FormalSlotCandidateEnhancedProofSummary(
                    profile_id="expression_model_card_delivery_v1",
                    requirement_id="expression_model_card_framing_and_affect_v1",
                    candidate_id=candidate.candidate_id,
                    output_id=candidate.output_id,
                    eligible=False,
                    status="fail",
                    evidence_codes=["expression_model_card_profile_rejected"],
                    issue_codes=["expression_model_card_binding_missing"],
                    dimensions={"profile_score": 0.0},
                )
            model_card_summary = compose_expression_model_card_enhanced_summary(
                module=candidate.module,
                slot=slot_key,
                candidate_id=candidate.candidate_id,
                output_id=candidate.output_id,
                operation_id=operation_id,
                round_id=round_id,
                card_family_framing=expression_model_card_proofs.get("card_family_framing"),
                affect_proof=expression_model_card_proofs.get("affect_proof"),
            )
            evidence_codes = ["expression_model_card_profile_passed"] if model_card_summary.eligible else [
                "expression_model_card_profile_rejected"
            ]
            evidence_codes.extend(model_card_summary.evidence_codes)
            dimensions = dict(model_card_summary.dimensions)
            dimensions["profile_score"] = 1.0 if model_card_summary.eligible else 0.0
            return FormalSlotCandidateEnhancedProofSummary(
                profile_id=model_card_summary.profile_id,
                requirement_id=model_card_summary.requirement_id,
                candidate_id=candidate.candidate_id,
                output_id=candidate.output_id,
                eligible=model_card_summary.eligible,
                status=model_card_summary.status,
                evidence_codes=list(dict.fromkeys(evidence_codes)),
                issue_codes=list(model_card_summary.issue_codes),
                dimensions=dimensions,
            )

        eligible = CharacterCardPreparationService._review_allows_slot(slot_key, review)
        return FormalSlotCandidateEnhancedProofSummary(
            profile_id="expression_slot_profile_v1",
            requirement_id=f"{slot_key}.enhanced_profile",
            candidate_id=candidate.candidate_id,
            output_id=candidate.output_id,
            eligible=eligible,
            status="pass" if eligible else "fail",
            evidence_codes=["expression_slot_profile_eligible"]
            if eligible
            else ["expression_slot_profile_rejected"],
            issue_codes=[] if eligible else ["expression_slot_profile_not_met"],
            dimensions={"profile_score": 1.0 if eligible else 0.0},
        )

    @classmethod
    def _formal_expression_slot_receipt(
        cls,
        *,
        slot_key: str,
        attempts: list[CharacterCardCandidateAttempt],
    ) -> FormalSlotReceipt:
        slot_attempts = [
            attempt
            for attempt in attempts
            if attempt.candidate.module == "expression_set" and attempt.candidate.slot_key == slot_key
        ]
        if len(slot_attempts) != cls.CANDIDATE_COUNT:
            raise ValueError("Expression formal slot requires exactly three reviewed candidates")
        selection_keys: dict[str, tuple[Any, ...]] = {}
        candidates: list[FormalSlotCandidateSummary] = []
        for attempt in slot_attempts:
            candidate = attempt.candidate
            shared_review = cls._formal_shared_review_summary(attempt.review)
            enhanced_proof = cls._formal_expression_enhanced_proof(
                slot_key=slot_key,
                candidate=candidate,
                review=attempt.review,
            )
            selection_keys[candidate.candidate_id] = cls._selection_key(attempt.review)
            candidates.append(
                FormalSlotCandidateSummary(
                    candidate_index=candidate.candidate_index,
                    candidate_id=candidate.candidate_id,
                    output_id=candidate.output_id,
                    reviewed=True,
                    shared_review=shared_review,
                    enhanced_proof=enhanced_proof,
                )
            )
        framing_ok = cls._formal_generic_framing_passed(candidates)
        parity_ok = all(attempt.candidate.prompt_reference_parity_verified for attempt in slot_attempts)
        identity_ok = any(candidate.shared_review.passed for candidate in candidates)
        return FormalSlotAcceptanceCore().accept(
            module="expression_set",
            slot_key=slot_key,
            acceptance_mode="standard_three_candidate",
            candidates=candidates,
            framing_summary=cls._formal_requirement_summary(
                passed=framing_ok,
                evidence_code="expression_front_card_framing_verified",
                issue_code="expression_front_card_framing_missing",
            ),
            parity_summary=cls._formal_requirement_summary(
                passed=parity_ok,
                evidence_code="expression_reference_parity_verified",
                issue_code="expression_reference_parity_missing",
            ),
            identity_summary=cls._formal_requirement_summary(
                passed=identity_ok,
                evidence_code="expression_shared_identity_review_verified",
                issue_code="expression_shared_identity_review_missing",
            ),
            ranking_key=lambda candidate: selection_keys[candidate.candidate_id],
            candidate_eligibility=lambda candidate: candidate.enhanced_proof is not None
            and candidate.enhanced_proof.eligible,
        )

    @staticmethod
    def _review_allows_body_slot(review: Any) -> bool:
        if getattr(review, "status", None) != "pass":
            return False
        scores = getattr(review, "identity_scores", None)
        evidence_codes = set(getattr(scores, "evidence_codes", []) or [])
        issue_codes = set(getattr(review, "issue_codes", []) or [])
        return (
            BODY_ENHANCED_PROFILE_EVIDENCE_CODE in evidence_codes
            and BODY_ENHANCED_PROFILE_ISSUE_CODE not in issue_codes
        )

    @classmethod
    def _formal_body_slot_failure_projection(
        cls,
        *,
        slot_key: str,
        attempts: list[CharacterCardCandidateAttempt],
        candidate_generation_failures: list[CharacterCardFailureEvent] | None = None,
    ) -> BodyFormalSlotFailureDetails:
        """Closed, public-safe reason for a failed Body formal-slot receipt.

        The projection deliberately exposes counts, slot and candidate indexes
        only.  It never copies exception text, prompts, paths, URLs, output IDs,
        provider payloads, or candidate IDs.
        """

        reviewed_count = len(attempts)
        passed_shared_review_count = 0
        enhanced_eligible_count = 0
        shared_review_receipt_missing_count = 0
        source_standard_missing_count = 0
        source_standard_blocking_count = 0
        candidate_contract_mismatch_count = 0
        candidate_summaries: list[dict[str, Any]] = []
        generation_failure_summaries = cls._formal_body_candidate_generation_failures(
            slot_key=slot_key,
            failures=candidate_generation_failures or [],
        )
        lifecycle_failure_summaries = cls._formal_body_candidate_lifecycle_failures(
            slot_key=slot_key,
            failures=candidate_generation_failures or [],
        )
        fatal_issue_codes = {
            "body_candidate_module_mismatch",
            "body_candidate_slot_mismatch",
            "body_candidate_index_mismatch",
            "body_face_reference_scope_mismatch",
            "body_candidate_reference_scope_mismatch",
            "body_source_class_missing",
            "body_observed_consent_missing",
        }
        source_standard_blocking_codes = set(BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES)
        for attempt in attempts:
            candidate_index = int(getattr(attempt.request, "candidate_index", 1) or 1)
            shared_review_passed = False
            shared_review_status = "missing"
            shared_review_issue_codes: set[str] = set()
            try:
                shared_review = cls._formal_shared_review_summary(attempt.review)
                shared_review_status = shared_review.status
                shared_review_passed = shared_review.passed
                shared_review_issue_codes = set(shared_review.issue_codes)
            except ValueError:
                shared_review_receipt_missing_count += 1
            if shared_review_passed:
                passed_shared_review_count += 1

            try:
                proof = cls._formal_body_enhanced_proof(slot_key=slot_key, attempt=attempt)
            except ValueError:
                proof = None
                candidate_contract_mismatch_count += 1
            enhanced_eligible = bool(proof is not None and proof.eligible)
            if enhanced_eligible:
                enhanced_eligible_count += 1
            proof_issue_codes = set(proof.issue_codes if proof is not None else [])
            if BODY_SOURCE_STANDARD_MISSING_ISSUE_CODE in proof_issue_codes:
                source_standard_missing_count += 1
            if source_standard_blocking_codes.intersection(proof_issue_codes.union(shared_review_issue_codes)):
                source_standard_blocking_count += 1
            if fatal_issue_codes.intersection(proof_issue_codes):
                candidate_contract_mismatch_count += 1
            safe_issue_categories: list[str] = []
            if not shared_review_passed:
                safe_issue_categories.append("shared_review_not_pass")
            if BODY_SOURCE_STANDARD_MISSING_ISSUE_CODE in proof_issue_codes:
                safe_issue_categories.append("source_standard_evidence_missing")
            if source_standard_blocking_codes.intersection(proof_issue_codes.union(shared_review_issue_codes)):
                safe_issue_categories.append("source_standard_blocking_issue")
            if fatal_issue_codes.intersection(proof_issue_codes):
                safe_issue_categories.append("candidate_contract_mismatch")
            if proof is None:
                safe_issue_categories.append("enhanced_proof_unavailable")
            candidate_summaries.append(
                BodyFormalSlotCandidateFailureSummary(
                    candidate_index=min(3, max(1, candidate_index)),
                    shared_review_status=shared_review_status,  # type: ignore[arg-type]
                    shared_review_passed=shared_review_passed,
                    enhanced_proof_eligible=enhanced_eligible,
                    issue_categories=list(dict.fromkeys(safe_issue_categories)),  # type: ignore[arg-type]
                )
            )

        if reviewed_count != cls.CANDIDATE_COUNT:
            failure_code = BODY_FORMAL_SLOT_REVIEWED_COUNT_INVALID_CODE
        elif candidate_contract_mismatch_count:
            failure_code = BODY_FORMAL_SLOT_CANDIDATE_CONTRACT_MISMATCH_CODE
        elif shared_review_receipt_missing_count:
            failure_code = BODY_FORMAL_SLOT_SHARED_REVIEW_RECEIPT_MISSING_CODE
        elif passed_shared_review_count == 0:
            failure_code = BODY_FORMAL_SLOT_NO_PASSING_SHARED_REVIEW_CODE
        elif enhanced_eligible_count == 0 and source_standard_missing_count:
            failure_code = BODY_FORMAL_SLOT_SOURCE_STANDARD_MISSING_CODE
        elif enhanced_eligible_count == 0 and source_standard_blocking_count:
            failure_code = BODY_FORMAL_SLOT_SOURCE_STANDARD_BLOCKED_CODE
        elif enhanced_eligible_count == 0:
            failure_code = BODY_FORMAL_SLOT_NO_EXTERNAL_ELIGIBILITY_CODE
        else:
            failure_code = BODY_FORMAL_SLOT_FAILURE_GENERIC_CODE
        return BodyFormalSlotFailureDetails(
            contract="body_formal_slot_failure_projection_v1",
            failure_code=failure_code,  # type: ignore[arg-type]
            module="body_silhouette",
            slot_key=slot_key,  # type: ignore[arg-type]
            candidate_count=reviewed_count,
            candidate_indexes=[
                min(3, max(1, int(getattr(attempt.request, "candidate_index", 1) or 1)))
                for attempt in attempts
            ],
            passed_shared_review_count=passed_shared_review_count,
            enhanced_eligible_count=enhanced_eligible_count,
            shared_review_receipt_missing_count=shared_review_receipt_missing_count,
            source_standard_evidence_missing_count=source_standard_missing_count,
            source_standard_blocking_issue_count=source_standard_blocking_count,
            candidate_contract_mismatch_count=candidate_contract_mismatch_count,
            candidate_generation_blocked_count=len(generation_failure_summaries),
            candidate_generation_blocked_indexes=[
                summary.candidate_index for summary in generation_failure_summaries
            ],
            candidate_generation_failures=generation_failure_summaries,
            candidate_lifecycle_blocked_count=len(lifecycle_failure_summaries),
            candidate_lifecycle_blocked_indexes=[
                summary.candidate_index for summary in lifecycle_failure_summaries
            ],
            candidate_lifecycle_failures=lifecycle_failure_summaries,
            candidate_summaries=candidate_summaries,
        )

    @staticmethod
    def _formal_body_candidate_generation_failures(
        *,
        slot_key: str,
        failures: list[CharacterCardFailureEvent],
    ) -> list[BodyFormalSlotCandidateGenerationFailureSummary]:
        summaries: list[BodyFormalSlotCandidateGenerationFailureSummary] = []
        reviewed_failure_codes = {
            "character_card_formal_slot_receipt_invalid",
            "character_card_shared_review_failed",
        }
        for failure in failures:
            if failure.module != "body_silhouette" or failure.slot_key != slot_key:
                continue
            raw_code = str(failure.failure_code or "").strip()
            if not raw_code or raw_code in reviewed_failure_codes:
                continue
            if raw_code == "image_edit_invalid_request_unattributed":
                family: BodyCandidateGenerationFailureFamily = "provider_no_pixel"
                code: BodyCandidateGenerationFailureCode = "image_edit_invalid_request_unattributed"
            elif raw_code in {
                "remote_brain_unavailable",
                "remote_brain_unauthorized",
                "remote_creative_brain_prompt_signoff_unavailable",
            }:
                family = "remote_brain"
                code = raw_code  # type: ignore[assignment]
            elif raw_code in {
                "mcp_materialization_pending",
                "mcp_materialization_failed",
                "mcp_review_pending",
            }:
                family = "mcp_materialization"
                code = raw_code  # type: ignore[assignment]
            elif raw_code == "character_card_candidate_generation_failed":
                family = "candidate_generation"
                code = "character_card_candidate_generation_failed"
            else:
                family = "candidate_generation"
                code = "unknown_candidate_generation_failure"
            summaries.append(
                BodyFormalSlotCandidateGenerationFailureSummary(
                    candidate_index=min(3, max(1, int(failure.candidate_index or 1))),
                    failure_family=family,
                    failure_code=code,
                )
            )
        deduped: dict[int, BodyFormalSlotCandidateGenerationFailureSummary] = {}
        for summary in summaries:
            deduped.setdefault(summary.candidate_index, summary)
        return [deduped[index] for index in sorted(deduped)]

    @staticmethod
    def _formal_body_candidate_lifecycle_failures(
        *,
        slot_key: str,
        failures: list[CharacterCardFailureEvent],
    ) -> list[CharacterCardCandidateLifecycleProjection]:
        deduped: dict[int, CharacterCardCandidateLifecycleProjection] = {}
        for failure in failures:
            lifecycle = failure.candidate_lifecycle
            if lifecycle is None:
                continue
            if lifecycle.stage != "body_silhouette" or lifecycle.slot_key != slot_key:
                continue
            if lifecycle.status != "blocked":
                continue
            deduped.setdefault(lifecycle.candidate_index, lifecycle)
        return [deduped[index] for index in sorted(deduped)]

    @staticmethod
    def _formal_body_enhanced_proof(
        *,
        slot_key: str,
        attempt: CharacterCardCandidateAttempt,
    ) -> FormalSlotCandidateEnhancedProofSummary:
        request = attempt.request
        candidate = attempt.candidate
        review = attempt.review
        issue_codes: list[str] = []
        evidence_codes: list[str] = []
        reference_output_ids = [str(item).strip() for item in request.reference_output_ids if str(item).strip()]
        candidate_source_output_ids = [
            str(item).strip() for item in candidate.source_output_ids if str(item).strip()
        ]
        if request.module != "body_silhouette" or candidate.module != "body_silhouette":
            issue_codes.append("body_candidate_module_mismatch")
        if request.slot_key != slot_key or candidate.slot_key != slot_key:
            issue_codes.append("body_candidate_slot_mismatch")
        if request.candidate_index != candidate.candidate_index:
            issue_codes.append("body_candidate_index_mismatch")
        if len(reference_output_ids) != 3 or len(set(reference_output_ids)) != 3:
            issue_codes.append("body_face_reference_scope_mismatch")
        elif candidate_source_output_ids != reference_output_ids:
            issue_codes.append("body_candidate_reference_scope_mismatch")
        source_class = str(request.source_class or "").strip()
        if source_class not in {"brain_inferred", "user_described", "observed"}:
            issue_codes.append("body_source_class_missing")
        elif source_class == "observed" and not str(request.consent_provenance_id or "").strip():
            issue_codes.append("body_observed_consent_missing")
        review_issue_codes = {
            str(item.get("code") if isinstance(item, dict) else item).strip()
            for item in (getattr(review, "issue_codes", []) or [])
            if str(item.get("code") if isinstance(item, dict) else item).strip()
        }
        shared_review_summary: FormalSlotSharedReviewSummary | None = None
        try:
            shared_review_summary = CharacterCardPreparationService._formal_shared_review_summary(review)
        except ValueError:
            issue_codes.append("body_shared_review_receipt_missing")
        shared_score_dimensions = (
            set(shared_review_summary.score_dimensions) if shared_review_summary is not None else set()
        )
        shared_issue_codes = (
            set(shared_review_summary.issue_codes) if shared_review_summary is not None else set()
        )
        missing_source_standard_dimensions = [
            dimension
            for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS
            if (
                dimension not in shared_score_dimensions
                or BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES[dimension]
                not in set(shared_review_summary.evidence_codes if shared_review_summary is not None else [])
            )
        ]
        if missing_source_standard_dimensions:
            issue_codes.append(BODY_SOURCE_STANDARD_MISSING_ISSUE_CODE)
        blocking_source_standard_issues = sorted(
            review_issue_codes.union(shared_issue_codes).intersection(
                BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES
            )
        )
        issue_codes.extend(blocking_source_standard_issues)
        if BODY_ENHANCED_PROFILE_ISSUE_CODE in review_issue_codes:
            issue_codes.append(BODY_ENHANCED_PROFILE_ISSUE_CODE)
        if getattr(review, "status", None) != "pass":
            issue_codes.append("body_shared_review_not_pass")
        eligible = not issue_codes
        if eligible:
            evidence_codes.extend(
                [
                    BODY_ENHANCED_PROFILE_EVIDENCE_CODE,
                    f"body_source_class_{source_class}",
                    "body_face_reference_scope_verified",
                    "body_candidate_contract_verified",
                    "body_shared_review_pass_verified",
                    BODY_SOURCE_STANDARD_EVIDENCE_CODE,
                ]
            )
            if source_class == "observed":
                evidence_codes.append("body_observed_consent_verified")
            else:
                evidence_codes.append("body_consent_not_required")
        else:
            evidence_codes.append(BODY_ENHANCED_PROFILE_ISSUE_CODE)
        source_standard_verified = not missing_source_standard_dimensions and not blocking_source_standard_issues
        issue_codes = list(dict.fromkeys(issue_codes))
        dimensions: dict[str, float] = {
            "profile_score": 1.0 if eligible else 0.0,
            "face_reference_scope_score": 1.0
            if len(reference_output_ids) == 3 and len(set(reference_output_ids)) == 3
            else 0.0,
            "source_standard_score": 1.0 if source_standard_verified else 0.0,
        }
        dimensions.update(
            {
                f"source_standard_{dimension}": 1.0
                if (
                    dimension in shared_score_dimensions
                    and BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES[dimension]
                    in set(shared_review_summary.evidence_codes if shared_review_summary is not None else [])
                )
                else 0.0
                for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS
            }
        )
        return FormalSlotCandidateEnhancedProofSummary(
            profile_id="body_silhouette_slot_profile_v1",
            requirement_id=f"{slot_key}.enhanced_profile",
            candidate_id=candidate.candidate_id,
            output_id=candidate.output_id,
            eligible=eligible,
            status="pass" if eligible else "fail",
            evidence_codes=evidence_codes,
            issue_codes=issue_codes,
            dimensions=dimensions,
        )

    @classmethod
    def _formal_body_slot_receipt(
        cls,
        *,
        slot_key: str,
        attempts: list[CharacterCardCandidateAttempt],
    ) -> FormalSlotReceipt:
        slot_attempts = [
            attempt
            for attempt in attempts
            if attempt.candidate.module == "body_silhouette" and attempt.candidate.slot_key == slot_key
        ]
        if len(slot_attempts) != cls.CANDIDATE_COUNT:
            raise ValueError("Body formal slot requires exactly three reviewed candidates")
        selection_keys: dict[str, tuple[Any, ...]] = {}
        candidates: list[FormalSlotCandidateSummary] = []
        for attempt in slot_attempts:
            candidate = attempt.candidate
            shared_review = cls._formal_shared_review_summary(attempt.review)
            enhanced_proof = cls._formal_body_enhanced_proof(slot_key=slot_key, attempt=attempt)
            selection_keys[candidate.candidate_id] = cls._selection_key(attempt.review)
            candidates.append(
                FormalSlotCandidateSummary(
                    candidate_index=candidate.candidate_index,
                    candidate_id=candidate.candidate_id,
                    output_id=candidate.output_id,
                    reviewed=True,
                    shared_review=shared_review,
                    enhanced_proof=enhanced_proof,
                )
            )
        fatal_enhanced_issue_codes = {
            "body_candidate_module_mismatch",
            "body_candidate_slot_mismatch",
            "body_candidate_index_mismatch",
            "body_face_reference_scope_mismatch",
            "body_candidate_reference_scope_mismatch",
            "body_source_class_missing",
            "body_observed_consent_missing",
        }
        if any(
            candidate.enhanced_proof is not None
            and fatal_enhanced_issue_codes.intersection(candidate.enhanced_proof.issue_codes)
            for candidate in candidates
        ):
            raise ValueError("Body formal slot enhanced proof contract mismatch")
        framing_ok = cls._formal_generic_framing_passed(candidates)
        parity_ok = all(attempt.candidate.prompt_reference_parity_verified for attempt in slot_attempts)
        identity_ok = any(candidate.shared_review.passed for candidate in candidates)
        return FormalSlotAcceptanceCore().accept(
            module="body_silhouette",
            slot_key=slot_key,
            acceptance_mode="standard_three_candidate",
            candidates=candidates,
            framing_summary=cls._formal_requirement_summary(
                passed=framing_ok,
                evidence_code="body_silhouette_framing_verified",
                issue_code="body_silhouette_framing_missing",
            ),
            parity_summary=cls._formal_requirement_summary(
                passed=parity_ok,
                evidence_code="body_reference_parity_verified",
                issue_code="body_reference_parity_missing",
            ),
            identity_summary=cls._formal_requirement_summary(
                passed=identity_ok,
                evidence_code="body_shared_identity_review_verified",
                issue_code="body_shared_identity_review_missing",
            ),
            ranking_key=lambda candidate: selection_keys[candidate.candidate_id],
            candidate_eligibility=lambda candidate: candidate.enhanced_proof is not None
            and candidate.enhanced_proof.eligible,
        )

    @staticmethod
    def _winner_slot(
        *,
        module: CharacterCardModule,
        slot_key: str,
        winner: CharacterCardCandidateResult,
        source_class: BodySourceClass | None = None,
        consent_provenance_id: str | None = None,
        formal_slot_receipt: FormalSlotReceipt | None = None,
    ) -> CharacterCardSlot:
        review_verified = True
        return CharacterCardSlot(
            slot_key=slot_key,  # type: ignore[arg-type]
            module=module,
            state="winner_selected",
            output_id=winner.output_id,
            source_candidate_ids=list(winner.source_candidate_ids),
            source_class=source_class,
            consent_provenance_id=consent_provenance_id,
            lineage_id=f"lineage_{winner.candidate_id}",
            review_verified=review_verified,
            prompt_reference_parity_verified=winner.prompt_reference_parity_verified,
            candidate_attempt_count=3,
            formal_slot_receipt=formal_slot_receipt,
        )

    @staticmethod
    def _require_face_active(card: CharacterCardState, front_output_id: str) -> None:
        if card.face_identity_status != "active":
            raise ValueError("Expression Set requires an active Face Identity module")
        front = card.face_slots.get("face.front")
        if front is None or front.output_id != front_output_id or front.state != "active":
            raise ValueError("Expression Set requires the active face.front winner")

    @staticmethod
    def _require_slot_success_receipt(
        slot: CharacterCardSlot,
        *,
        require_standard_three_candidate: bool = False,
    ) -> None:
        if slot.is_alias:
            return
        if slot.state not in {"winner_selected", "active"} or not slot.output_id:
            raise ValueError("Character Card contains an unreviewed slot")
        if slot.module == "expression_set" and _is_expression_delivery_slot(slot.slot_key):
            if slot.formal_slot_receipt is None:
                raise ValueError("Character Card expression activation requires a formal slot receipt")
            receipt = validate_formal_slot_receipt_for_activation(slot.formal_slot_receipt)
            if receipt.module != "expression_set":
                raise ValueError("Character Card expression formal receipt module mismatch")
            if receipt.slot_key != slot.slot_key:
                raise ValueError("Character Card expression formal receipt slot mismatch")
            if receipt.winner_output_id != slot.output_id:
                raise ValueError("Character Card expression formal receipt output mismatch")
            return
        if slot.module == "body_silhouette" and _is_body_delivery_slot(slot.slot_key):
            if slot.formal_slot_receipt is None:
                raise ValueError("Character Card body activation requires a formal slot receipt")
            receipt = validate_formal_slot_receipt_for_activation(slot.formal_slot_receipt)
            if receipt.module != "body_silhouette":
                raise ValueError("Character Card body formal receipt module mismatch")
            if receipt.slot_key != slot.slot_key:
                raise ValueError("Character Card body formal receipt slot mismatch")
            if receipt.winner_output_id != slot.output_id:
                raise ValueError("Character Card body formal receipt output mismatch")
            return
        if slot.shared_runtime_receipt is None:
            raise ValueError("Character Card slot activation requires persisted shared runtime receipt")
        receipt = validate_character_card_slot_success_receipt(
            slot.shared_runtime_receipt,
            module=slot.module,
            slot_key=slot.slot_key,
            output_id=slot.output_id,
        )
        if require_standard_three_candidate and receipt.get("acceptance_mode") != "standard_three_candidate":
            raise ValueError("Character Card module activation requires standard three-candidate slot receipts")

    @staticmethod
    def activate_body_silhouette_refresh(
        card: CharacterCardState,
        *,
        confirmed: bool,
    ) -> CharacterCardState:
        """Promote a reviewed Body refresh into the active Body slots."""

        if not confirmed:
            raise ValueError("explicit Body Silhouette refresh activation confirmation is required")
        # Historical active cards can predate persistence of the explicit
        # body_activation_confirmed flag.  The authoritative readback here is
        # the active module status plus all three active Body slots; the flag
        # is repaired as part of this explicit refresh activation.
        if card.body_silhouette_status != "active":
            raise ValueError("Body Silhouette refresh activation requires an active Body module")
        if any(slot.state != "active" for slot in card.body_slots.values()):
            raise ValueError("Body Silhouette refresh activation requires active Body slots")
        if card.body_silhouette_refresh_status != "reviewing":
            raise ValueError("Body Silhouette refresh is not ready for activation")
        if not card.body_silhouette_refresh_version_id:
            raise ValueError("Body Silhouette refresh activation requires a refresh version")
        if set(card.body_silhouette_refresh_slots) != set(BODY_SLOT_KEYS):
            raise ValueError("Body Silhouette refresh activation requires all Body slots")

        activated_slots: dict[str, CharacterCardSlot] = {}
        for slot_key in BODY_SLOT_KEYS:
            slot = card.body_silhouette_refresh_slots[slot_key]
            if slot.state != "winner_selected":
                raise ValueError("Body Silhouette refresh activation requires pending winners")
            if slot.module != "body_silhouette" or slot.slot_key != slot_key:
                raise ValueError("Body Silhouette refresh activation slot mismatch")
            if slot.formal_slot_receipt is None:
                raise ValueError("Body Silhouette refresh activation requires formal slot receipts")
            receipt = validate_formal_slot_receipt_for_activation(slot.formal_slot_receipt)
            if receipt.module != "body_silhouette":
                raise ValueError("Body Silhouette refresh formal receipt module mismatch")
            if receipt.slot_key != slot_key:
                raise ValueError("Body Silhouette refresh formal receipt slot mismatch")
            if receipt.winner_output_id != slot.output_id:
                raise ValueError("Body Silhouette refresh formal receipt output mismatch")
            activated_slots[slot_key] = CharacterCardSlot.model_validate(
                slot.model_copy(
                    update={
                        "state": "active",
                        "formal_slot_receipt": receipt,
                    }
                ).model_dump(mode="python")
            )

        refresh_version_id = card.body_silhouette_refresh_version_id
        return card.model_copy(
            update={
                "body_slots": activated_slots,
                "body_silhouette_status": "active",
                "body_silhouette_version_id": refresh_version_id,
                "body_activation_confirmed": True,
                "user_activation_confirmed": True,
                "active_version_id": refresh_version_id,
                "body_silhouette_refresh_status": "empty",
                "body_silhouette_refresh_version_id": None,
                "body_silhouette_refresh_slots": {},
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "last_shared_runtime_failure": None,
                "last_review_repair_context": None,
                "resume_available": False,
                "pending_mcp_handoff_ids": [],
                "append_only_revision": card.append_only_revision + 1,
            }
        )

    @staticmethod
    def activate_module(
        card: CharacterCardState,
        *,
        module: Literal["expression_set", "body_silhouette"],
        confirmed: bool,
    ) -> CharacterCardState:
        """Explicitly activate a reviewed module; preparation never auto-activates."""

        if not confirmed:
            raise ValueError("explicit Character Card module activation confirmation is required")
        if module == "expression_set":
            if card.expression_set_status not in {"reviewing", "partial"}:
                raise ValueError("Expression Set is not ready for activation")
            slots = dict(card.expression_slots)
            if any(
                slot.state not in {"winner_selected", "active"}
                for key, slot in slots.items()
                if key in EXPRESSION_SLOT_KEYS and key != "expression.neutral"
            ):
                raise ValueError("Expression Set contains an unreviewed slot")
            for key, slot in slots.items():
                if key in EXPRESSION_SLOT_KEYS and key != "expression.neutral":
                    CharacterCardPreparationService._require_slot_success_receipt(
                        slot,
                        require_standard_three_candidate=True,
                    )
            slots = {
                key: slot.model_copy(update={"state": "active"})
                if slot.state == "winner_selected"
                else slot
                for key, slot in slots.items()
            }
            return card.model_copy(
                update={
                    "expression_slots": slots,
                    "expression_set_status": "active",
                    "expression_activation_confirmed": True,
                    "user_activation_confirmed": True,
                    "active_version_id": card.expression_set_version_id,
                    "append_only_revision": card.append_only_revision + 1,
                }
            )
        if card.body_silhouette_status not in {"reviewing", "partial"}:
            raise ValueError("Body Silhouette is not ready for activation")
        if any(slot.state not in {"winner_selected", "active"} for slot in card.body_slots.values()):
            raise ValueError("Body Silhouette contains an unreviewed slot")
        for slot in card.body_slots.values():
            CharacterCardPreparationService._require_slot_success_receipt(slot)
        slots = {
            key: slot.model_copy(update={"state": "active"})
            if slot.state == "winner_selected"
            else slot
            for key, slot in card.body_slots.items()
        }
        return card.model_copy(
            update={
                "body_slots": slots,
                "body_silhouette_status": "active",
                "body_activation_confirmed": True,
                "user_activation_confirmed": True,
                "active_version_id": card.body_silhouette_version_id,
                "append_only_revision": card.append_only_revision + 1,
            }
        )


def apply_face_identity_pack_to_card(card: CharacterCardState, pack: Any) -> CharacterCardState:
    """Project an explicitly activated shared Face Identity pack into slots."""

    pack_version_id = str(pack.pack_version_id)
    if card.face_identity_version_id and card.face_identity_version_id != pack_version_id:
        card = card.mark_face_version_stale(new_face_version_id=pack_version_id)

    role_to_slot = {
        "standard_front": "face.front",
        "three_quarter": "face.front_three_quarter",
        "profile": "face.profile",
        "reverse_three_quarter": "face.reverse_three_quarter",
        "rear_head": "face.rear_head",
    }
    pack_status = str(getattr(pack, "status", "") or "")
    slot_state: Literal["winner_selected", "active"] = (
        "active" if pack_status == "active" else "winner_selected"
    )
    face_slots = {
        slot_key: CharacterCardSlot(slot_key=slot_key, module="face_identity")
        for slot_key in FACE_SLOT_KEYS
    }
    for view in getattr(pack, "anchor_views", []):
        view_role = str(getattr(view, "view_role", ""))
        slot_key = role_to_slot.get(view_role)
        if not getattr(view, "active", False):
            continue
        if slot_key is None:
            continue
        receipt_payload = getattr(view, "formal_slot_receipt", None)
        if receipt_payload is None:
            raise ValueError("Character Card Face projection requires a formal slot receipt")
        receipt = validate_formal_slot_receipt_for_activation(receipt_payload)
        if receipt.module != "face_identity":
            raise ValueError("Character Card Face projection receipt module mismatch")
        if receipt.slot_key != f"face_identity.{view_role}":
            raise ValueError("Character Card Face projection receipt slot mismatch")
        if receipt.winner_output_id != str(getattr(view, "output_id", "")):
            raise ValueError("Character Card Face projection receipt output mismatch")
        source_candidate_ids = list(getattr(view, "source_candidate_ids", []) or [])
        if source_candidate_ids and receipt.winner_candidate_id not in source_candidate_ids:
            raise ValueError("Character Card Face projection receipt winner candidate mismatch")
        face_slots[slot_key] = CharacterCardSlot(
            slot_key=slot_key,
            module="face_identity",
            state=slot_state,
            output_id=str(view.output_id),
            source_candidate_ids=source_candidate_ids,
            lineage_id=f"lineage_{view.view_id}",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=receipt.reviewed_candidate_count,
            formal_slot_receipt=receipt,
        )
    active_view_count = sum(1 for view in getattr(pack, "anchor_views", []) if getattr(view, "active", False))
    missing_slot = next(
        (
            slot_key
            for role, slot_key in role_to_slot.items()
            if not any(
                getattr(view, "active", False) and str(getattr(view, "view_role", "")) == role
                for view in getattr(pack, "anchor_views", [])
            )
        ),
        "face.front",
    )
    update = {
        "face_identity_status": "active" if pack_status == "active" else (
            "reviewing" if pack_status == "review" else ("partial" if active_view_count else "blocked")
        ),
        "face_identity_version_id": pack_version_id,
        "face_slots": face_slots,
        "card_version_id": f"card_{pack_version_id}",
        "active_version_id": None,
        "user_activation_confirmed": False,
        "append_only_revision": card.append_only_revision + 1,
    }
    if pack_status == "failed":
        update.update(
            {
                "last_failed_module": "face_identity",
                "last_failed_slot_key": missing_slot,
                "last_failure_code": "character_card_face_prepare_paused",
                "last_failure_details": None,
                "last_failure_attempt_count": 3,
                "resume_available": True,
            }
        )
    else:
        update.update(
            {
                "last_failed_module": None,
                "last_failed_slot_key": None,
                "last_failure_code": None,
                "last_failure_details": None,
                "last_failure_attempt_count": 0,
                "resume_available": False,
            }
        )
    return card.model_copy(
        update=update
    )


__all__ = [
    "BODY_SOURCE_CLASSES",
    "BODY_SLOT_KEYS",
    "EXPRESSION_SLOT_KEYS",
    "EXPRESSION_LABELS",
    "FACE_SLOT_KEYS",
    "CHARACTER_CARD_SLOT_SUCCESS_RECEIPT_VERSION",
    "BodyPreparationRequest",
    "BodyRefreshAttemptIdentity",
    "CharacterCardCandidateAttempt",
    "CharacterCardCandidateRequest",
    "CharacterCardCandidateResult",
    "CharacterCardPreparationService",
    "CharacterCardFailureEvent",
    "CharacterCardStageHost",
    "CharacterCardSharedRuntimeFailureReceipt",
    "CharacterCardSharedRuntimeReceipt",
    "CharacterCardSlot",
    "CharacterCardState",
    "CharacterCardStageResult",
    "ExpressionPreparationRequest",
    "apply_face_identity_pack_to_card",
    "character_card_formal_slot_receipt_public_summary",
    "character_card_slot_success_receipt_public_summary",
    "project_character_card_slot_success_receipt",
    "validate_character_card_slot_success_receipt",
]
