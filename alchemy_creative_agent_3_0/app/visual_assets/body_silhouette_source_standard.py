"""Professional Character Card Body Silhouette source-standard ownership.

This module owns the closed, scene-neutral source-standard vocabulary for
Body Silhouette candidate review.  Shared Vision may project these labels when
the Character Card Body stage asks for them, but the shared layer does not own
or globally apply the contract.
"""

from __future__ import annotations

import math
import re
from typing import Any


# Gate C review eligibility floor for source-standard evidence only.  This is
# not a runtime grade, commercial certification, migration rule, or downstream
# delivery score.  The value is intentionally owned by the Body Silhouette
# source-standard contract and only gates new Body candidate/winner formation.
BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR = 0.80

BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS = (
    "body_chain_coherence",
    "stage_aware_proportion",
    "head_neck_shoulder_continuity",
    "torso_limb_joint_plausibility",
    "stance_ground_contact",
)

BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES = {
    dimension: f"body_silhouette_{dimension}_verified"
    for dimension in BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS
}

BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES = frozenset(
    {
        "head_body_scale_mismatch",
        "pasted_head_body_boundary",
        "head_body_integration_artifact",
        "face_reference_transplant_artifact",
        "face_body_texture_lighting_mismatch",
        "doll_like_body_chain",
        "mannequin_body_chain",
        "body_chain_discontinuity",
        "stage_incoherent_body_proportion",
        "target_age_body_proportion_drift",
        "over_infantilized_body",
        "accidental_adultification",
        "model_like_limb_elongation",
        "generic_model_body_override",
        "compressed_neck_shoulders",
        "floating_head",
        "neck_support_missing",
        "shoulder_width_incoherent",
        "head_neck_shoulder_discontinuity",
        "torso_compression",
        "limb_length_incoherence",
        "joint_placement_error",
        "rubbery_limb_structure",
        "left_right_body_asymmetry",
        "floating_body",
        "implausible_ground_contact",
        "collapsed_weight_bearing",
        "cardboard_stance",
        "stance_centerline_error",
        "body_silhouette_integrated_review_evidence_missing",
        "body_silhouette_multi_view_sheet_in_single_slot",
        "body_silhouette_cross_view_camera_distance_drift",
        "body_silhouette_subject_scale_drift",
        "body_silhouette_headroom_footroom_mismatch",
        "body_silhouette_view_specific_zoom_drift",
    }
)

BODY_SILHOUETTE_CROSS_VIEW_PARITY_DIMENSION = "cross_view_body_parity"
BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE = "body_silhouette_cross_view_parity_verified"
BODY_SILHOUETTE_CROSS_VIEW_PARITY_BLOCKING_ISSUE_CODES = frozenset(
    {
        "cross_view_body_parity_mismatch",
        "front_side_body_depth_conflict",
        "rear_body_build_conflict",
        "view_specific_age_stage_drift",
        "view_specific_limb_length_drift",
        "view_specific_body_maturity_drift",
        "front_side_rear_stature_ratio_conflict",
    }
)

BODY_SILHOUETTE_MCP_MATERIALIZATION_CHANNEL_CONTRACT_VERSION = (
    "professional_body_silhouette_mcp_materialization_channel_v1"
)

BODY_SILHOUETTE_MCP_ALLOWED_BODY_CHANNELS = (
    "body_proportion",
    "body_scale",
    "neck_shoulder_continuity",
    "torso_limb_relationship",
    "developmental_stage_body_context",
    "stance_ground_contact",
    "cross_view_body_parity",
)

BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS = (
    "wardrobe_or_attire_channel_present",
    "formal_business_styling_present",
    "expression_or_professional_pose_language_present",
    "scene_or_studio_styling_present",
)
BODY_SILHOUETTE_MCP_CLOTHING_ABSENCE_FINDING = "clothing_absence_positive_semantics_present"
BODY_SILHOUETTE_BLOCKING_ISSUE_EVALUATION_EVIDENCE_CODE = (
    "body_silhouette_blocking_issue_evaluation_complete"
)

BODY_SILHOUETTE_INTEGRATED_WHOLE_PERSON_CONTRACT_VERSION = (
    "professional_body_silhouette_integrated_whole_person_synthesis_v1"
)

BODY_SILHOUETTE_INTEGRATED_REVIEW_DIMENSIONS = (
    "head_neck_shoulder_continuity",
    "single_person_synthesis",
    "natural_body_chain",
    "natural_weight_bearing",
    "shoulder_head_proportion",
    "head_body_blend_naturalism",
    "target_age_body_proportion",
)

BODY_SILHOUETTE_AGE6_CROSS_VIEW_NATURALNESS_CONTRACT_VERSION = (
    "professional_body_silhouette_age6_cross_view_naturalness_v1"
)

BODY_SILHOUETTE_FIXED_FULL_BODY_FRAMING_CONTRACT_VERSION = (
    "professional_body_silhouette_fixed_full_body_framing_v1"
)

_BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_TERMS = {
    "wardrobe_or_attire_channel_present": (
        "wardrobe",
        "attire",
        "outfit",
        "dress",
        "skirt",
        "shirt",
        "shorts",
        "shoes",
        "socks",
        "barefoot",
        "bare feet",
    ),
    "formal_business_styling_present": (
        "formal",
        "business",
        "suit",
        "blazer",
        "tie",
        "commercial photography",
        "professional model-card",
        "professional model card",
    ),
    "expression_or_professional_pose_language_present": (
        "expression",
        "smile",
        "smiling",
        "professional pose",
        "model pose",
        "headshot",
        "portrait pose",
    ),
    "scene_or_studio_styling_present": (
        "scene",
        "studio",
        "background",
        "backdrop",
        "lighting",
        "camera",
        "lens",
        "white field",
    ),
    "clothing_absence_positive_semantics_present": (
        "nude",
        "naked",
        "unclothed",
        "undressed",
        "no clothing",
        "no clothes",
        "no garments",
        "clothing free",
        "without clothing",
        "without clothes",
        "without garments",
        "clothing absent",
        "absence of clothing",
        "bare body",
        "unclothed silhouette",
    ),
}


def body_silhouette_mcp_materialization_channel_contract() -> dict[str, Any]:
    """Return the closed Body-owned channel contract for MCP materialization.

    The contract narrows only Professional Character Card Body Silhouette
    MCP handoffs.  It does not define a new quality grade, activation state,
    downstream reference projection, scene recipe, or provider capability.
    """

    return {
        "contract_version": BODY_SILHOUETTE_MCP_MATERIALIZATION_CHANNEL_CONTRACT_VERSION,
        "applies": True,
        "scope": "professional_character_card_body_silhouette_mcp_materialization_only",
        "allowed_body_owned_channels": list(BODY_SILHOUETTE_MCP_ALLOWED_BODY_CHANNELS),
        "face_identity_reference_scope": "identity_continuity_only",
        "body_reference_scope": "body_only_when_server_resolved_reference_assisted",
        "non_body_owned_channels": "unspecified_not_authored_by_body_silhouette",
        "forbidden_channel_findings": list(BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS),
        "source_mode_scope": ["inference_first", "reference_assisted"],
    }


def body_silhouette_integrated_whole_person_synthesis_contract() -> dict[str, Any]:
    """Return the closed whole-person execution authority for Body MCP."""

    return {
        "contract_version": BODY_SILHOUETTE_INTEGRATED_WHOLE_PERSON_CONTRACT_VERSION,
        "synthesis_mode": "one_coherent_whole_person",
        "required_integrated_channels": [
            "face",
            "head",
            "neck",
            "shoulders",
            "torso",
            "limbs",
        ],
        "forbidden_composition_modes": [
            "pasted_head_body_boundary",
            "head_swap_or_composite",
            "mannequin_body_chain",
            "cardboard_stance",
        ],
        "authority": "professional_body_silhouette_renderer_execution_directive",
    }


def body_silhouette_age6_cross_view_naturalness_contract() -> dict[str, Any]:
    """Return the Body-only age-6 renderer and review guard.

    The five admitted Body sources are analysis evidence for this one
    reference-assisted Body refresh.  This contract must not become a global
    child, teen, adult, Face, Expression, or ordinary image-generation rule.
    """

    return {
        "contract_version": BODY_SILHOUETTE_AGE6_CROSS_VIEW_NATURALNESS_CONTRACT_VERSION,
        "applies": True,
        "scope": "reference_assisted_body_refresh_only",
        "target_age_scope": "age_6_child_only",
        "same_body_model_across_views": True,
        "front_head_body_integration_required": True,
        "forbid_teen_or_adult_model_elongation": True,
        "face_identity_integration_mode": "whole_person_regeneration_not_face_transplant",
        "same_body_envelope_across_views": True,
        "required_renderer_obligations": [
            "approximately_six_year_school_age_body_proportions",
            "single_natural_head_neck_shoulder_torso_limb_synthesis",
            "face_identity_guidance_without_face_transplant",
            "no_visible_head_body_join_or_composite_boundary",
            "no_teen_adolescent_or_adult_fashion_model_elongation",
            "same_compact_stature_body_depth_shoulder_width_and_limb_scale_across_views",
            "same_body_envelope_across_front_side_rear",
        ],
        "review_dimensions": [
            "head_body_blend_naturalism",
            "target_age_body_proportion",
            "age_stage_consistency",
            "head_body_scale_consistency",
            "front_side_rear_volume_consistency",
        ],
        "blocking_issue_codes": sorted(
            {
                "pasted_head_body_boundary",
                "head_body_integration_artifact",
                "face_reference_transplant_artifact",
                "face_body_texture_lighting_mismatch",
                "target_age_body_proportion_drift",
                "accidental_adultification",
                "model_like_limb_elongation",
                "cross_view_body_parity_mismatch",
                "same_body_envelope_conflict_between_views",
                "front_face_body_integration_artifact",
                "front_side_body_depth_conflict",
                "rear_body_build_conflict",
                "view_specific_age_stage_drift",
                "view_specific_limb_length_drift",
                "view_specific_body_maturity_drift",
                "front_side_rear_stature_ratio_conflict",
            }
        ),
        "forbidden_runtime_authority": [
            "global_child_prompt_rule",
            "teen_or_adult_age_override",
            "body_reference_physical_renderer_input",
            "biometric_vector_or_measurement_storage",
        ],
    }


def body_silhouette_fixed_full_body_framing_contract() -> dict[str, Any]:
    """Return the Body-only full-body framing parity contract.

    This contract owns camera-distance and canvas-scale consistency for
    Professional Character Card Body slots. It is composition authority only:
    it does not infer age, identity, body measurements, or scenario styling.
    """

    return {
        "contract_version": BODY_SILHOUETTE_FIXED_FULL_BODY_FRAMING_CONTRACT_VERSION,
        "applies": True,
        "scope": "professional_character_card_body_silhouette_slot_triplet",
        "target_canvas_size": "1024x1536",
        "single_full_body_subject_centered": True,
        "same_camera_distance_across_slots": True,
        "same_subject_scale_across_slots": True,
        "matched_headroom_and_footroom": True,
        "target_subject_height_fraction": {"min": 0.84, "max": 0.90},
        "target_headroom_fraction": {"min": 0.04, "max": 0.08},
        "target_footroom_fraction": {"min": 0.04, "max": 0.08},
        "required_renderer_obligations": [
            "full_body_head_to_feet_visible_in_each_slot",
            "same_camera_distance_and_subject_scale_across_front_side_rear",
            "matched_headroom_and_footroom_across_views",
            "subject_centerline_consistent_across_views",
            "no_view_specific_zoom_or_scale_drift",
        ],
        "blocking_issue_codes": [
            "body_silhouette_cross_view_camera_distance_drift",
            "body_silhouette_subject_scale_drift",
            "body_silhouette_headroom_footroom_mismatch",
            "body_silhouette_view_specific_zoom_drift",
        ],
    }


def evaluate_body_silhouette_visual_review(payload: Any) -> dict[str, Any]:
    """Fail closed unless typed pixel evidence covers the Body blockers."""

    if not isinstance(payload, dict):
        return {"status": "blocked", "formal_eligible": False}
    evidence_codes = payload.get("evidence_codes")
    issue_codes = payload.get("issue_codes")
    if not isinstance(evidence_codes, list) or not isinstance(issue_codes, list):
        return {"status": "blocked", "formal_eligible": False}
    if BODY_SILHOUETTE_BLOCKING_ISSUE_EVALUATION_EVIDENCE_CODE not in evidence_codes:
        return {"status": "blocked", "formal_eligible": False}
    if payload.get("verified") is not True or payload.get("status") != "pass":
        return {"status": "blocked", "formal_eligible": False}
    if set(str(code) for code in issue_codes) & BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES:
        return {"status": "blocked", "formal_eligible": False}
    integrated = payload.get("integrated_whole_person_review_evidence")
    if not validate_integrated_whole_person_review_evidence(integrated):
        return {"status": "blocked", "formal_eligible": False}
    return {"status": "pass", "formal_eligible": True}


def validate_integrated_whole_person_review_evidence(payload: Any) -> bool:
    """Validate the typed, pixel-backed shared review evidence envelope."""

    if not isinstance(payload, dict) or set(payload) != set(BODY_SILHOUETTE_INTEGRATED_REVIEW_DIMENSIONS):
        return False
    for dimension in BODY_SILHOUETTE_INTEGRATED_REVIEW_DIMENSIONS:
        item = payload.get(dimension)
        if not isinstance(item, dict) or set(item) != {"status", "pixel_evidence_present"}:
            return False
        if item.get("status") not in {"pass", "fail", "unknown"}:
            return False
        if type(item.get("pixel_evidence_present")) is not bool:
            return False
        if item["status"] != "pass" or item["pixel_evidence_present"] is not True:
            return False
    return True


def body_silhouette_mcp_materialization_prompt_findings(prompt: Any) -> tuple[str, ...]:
    """Return closed findings for non-Body-owned MCP renderer prompt channels.

    This is a defensive handoff check.  The owning fix remains the Body
    Silhouette source contract and Brain/recovery prompt contract; this helper
    prevents stale contracts from reaching MCP materialization.
    """

    raw_prompt = str(prompt or "").lower().replace("_", " ").replace("-", " ")
    normalized = " ".join(raw_prompt.split())
    if not normalized:
        return ()

    def term_present(term: str) -> bool:
        normalized_term = " ".join(str(term or "").lower().replace("_", " ").replace("-", " ").split())
        if not normalized_term:
            return False
        if " " in normalized_term:
            pattern = re.compile(rf"\b{re.escape(normalized_term)}\b")
        else:
            pattern = re.compile(rf"\b{re.escape(normalized_term)}\b")

        term_pattern = re.escape(normalized_term).replace(r"\ ", r"\s+")

        def negative_or_unspecified_context() -> bool:
            return bool(
                re.search(
                    r"\b(?:do\s+not\s+(?:author|assign|include|emit|carry|preserve|inherit|lock)|"
                    r"avoid|without|no|not|never)\b"
                    rf"[^.?!;:]{{0,160}}\b{term_pattern}\b",
                    raw_prompt,
                )
                or re.search(
                    rf"\b{term_pattern}\b[^.?!;:]{{0,80}}"
                    r"\b(?:unspecified|unassigned|not\s+authored|neutral)\b",
                    raw_prompt,
                )
            )

        if negative_or_unspecified_context():
            return False

        for match in pattern.finditer(normalized):
            before = normalized[max(0, match.start() - 42):match.start()].strip()
            after = normalized[match.end():match.end() + 42].strip()
            local = f"{before} {normalized_term} {after}"
            if (
                re.search(
                    r"\b(no|not|never|without|avoid)\s+"
                    rf"(?:\w+\s+){{0,4}}{re.escape(normalized_term)}\b",
                    local,
                )
                or re.search(
                    r"\bdo\s+not\s+(?:author|assign|include|emit|carry|preserve|inherit|lock)\s+"
                    rf"(?:\w+\s+){{0,4}}{re.escape(normalized_term)}\b",
                    local,
                )
                or re.search(
                    rf"\b{re.escape(normalized_term)}\s+(?:channel\s+)?(?:unspecified|unassigned|not\s+authored|neutral)\b",
                    local,
                )
            ):
                continue
            if normalized_term == "scene" and re.search(r"\bscene\s+neutral\b", local):
                continue
            return True
        return False

    def clothing_absence_term_present(term: str) -> bool:
        """Detect positive absence language without treating negation as positive."""

        normalized_term = " ".join(
            str(term or "").lower().replace("_", " ").replace("-", " ").split()
        )
        if not normalized_term:
            return False
        term_pattern = re.escape(normalized_term).replace(r"\ ", r"\s+")
        for match in re.finditer(rf"\b{term_pattern}\b", normalized):
            before = normalized[max(0, match.start() - 48):match.start()].strip()
            if re.search(
                r"\b(?:not|never|avoid|without being|no nudity|fully clothed|wearing)\b[^.?!;:]{0,32}$",
                before,
            ):
                continue
            return True
        return False

    findings: list[str] = []
    for finding in (
        *BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS,
        BODY_SILHOUETTE_MCP_CLOTHING_ABSENCE_FINDING,
    ):
        terms = _BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_TERMS[finding]
        if finding == "clothing_absence_positive_semantics_present":
            matched = any(clothing_absence_term_present(term) for term in terms)
        else:
            matched = any(term_present(term) for term in terms)
        if matched:
            findings.append(finding)
    return tuple(findings)


def body_silhouette_source_standard_contract() -> dict[str, Any]:
    """Return the closed Body-owner source-standard contract.

    The contract is review eligibility evidence for new Body Silhouette
    candidates only.  It is not a grade, commercial certification, runtime
    delivery field, or historical migration instruction.
    """

    return {
        "contract_version": "professional_body_silhouette_source_standard_v1",
        "applies": True,
        "scope": "body_silhouette_only",
        "required_dimensions": list(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS),
        "dimension_evidence_codes": dict(BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES),
        "dimension_score_floor": BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
        "blocking_issue_codes": sorted(BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES),
        "cross_view_parity_owner": "character_card_body_three_slot_formal_acceptance",
        "cross_view_parity_dimension": BODY_SILHOUETTE_CROSS_VIEW_PARITY_DIMENSION,
        "cross_view_parity_evidence_code": BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE,
        "cross_view_parity_score_floor": BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR,
        "cross_view_parity_blocking_issue_codes": sorted(
            BODY_SILHOUETTE_CROSS_VIEW_PARITY_BLOCKING_ISSUE_CODES
        ),
        "source_class_policy": "provenance_only_no_quality_grade",
        "forbidden_runtime_authority": [
            "commercial_certification",
            "body_silhouette_grade",
            "fixed_age_ratio",
            "scene_or_vertical_recipe",
        ],
    }


def validated_body_silhouette_source_standard_contract(raw: Any) -> dict[str, Any]:
    """Return a public-safe closed Body contract or `{}` for invalid input."""

    if not isinstance(raw, dict):
        return {}
    expected = body_silhouette_source_standard_contract()
    if set(raw) != set(expected):
        return {}

    def exact_list(value: Any, expected_items: list[str]) -> bool:
        if not isinstance(value, list):
            return False
        normalized = [str(item).strip() for item in value if str(item).strip()]
        return (
            len(normalized) == len(value)
            and len(normalized) == len(set(normalized))
            and normalized == expected_items
        )

    def exact_number(value: Any, expected_value: float) -> bool:
        if isinstance(value, bool) or type(value) not in {int, float}:
            return False
        numeric = float(value)
        return math.isfinite(numeric) and numeric == expected_value

    if raw.get("contract_version") != expected["contract_version"]:
        return {}
    if raw.get("applies") is not True or raw.get("scope") != expected["scope"]:
        return {}
    if not exact_list(raw.get("required_dimensions"), expected["required_dimensions"]):
        return {}
    if raw.get("dimension_evidence_codes") != expected["dimension_evidence_codes"]:
        return {}
    if not exact_number(raw.get("dimension_score_floor"), expected["dimension_score_floor"]):
        return {}
    if not exact_list(raw.get("blocking_issue_codes"), expected["blocking_issue_codes"]):
        return {}
    if raw.get("cross_view_parity_owner") != expected["cross_view_parity_owner"]:
        return {}
    if raw.get("cross_view_parity_dimension") != expected["cross_view_parity_dimension"]:
        return {}
    if raw.get("cross_view_parity_evidence_code") != expected["cross_view_parity_evidence_code"]:
        return {}
    if not exact_number(raw.get("cross_view_parity_score_floor"), expected["cross_view_parity_score_floor"]):
        return {}
    if not exact_list(
        raw.get("cross_view_parity_blocking_issue_codes"),
        expected["cross_view_parity_blocking_issue_codes"],
    ):
        return {}
    if raw.get("source_class_policy") != expected["source_class_policy"]:
        return {}
    if not exact_list(raw.get("forbidden_runtime_authority"), expected["forbidden_runtime_authority"]):
        return {}
    return dict(expected)


__all__ = [
    "BODY_SILHOUETTE_CROSS_VIEW_PARITY_BLOCKING_ISSUE_CODES",
    "BODY_SILHOUETTE_CROSS_VIEW_PARITY_DIMENSION",
    "BODY_SILHOUETTE_CROSS_VIEW_PARITY_EVIDENCE_CODE",
    "BODY_SILHOUETTE_MCP_ALLOWED_BODY_CHANNELS",
    "BODY_SILHOUETTE_MCP_CLOTHING_ABSENCE_FINDING",
    "BODY_SILHOUETTE_BLOCKING_ISSUE_EVALUATION_EVIDENCE_CODE",
    "BODY_SILHOUETTE_INTEGRATED_REVIEW_DIMENSIONS",
    "BODY_SILHOUETTE_AGE6_CROSS_VIEW_NATURALNESS_CONTRACT_VERSION",
    "BODY_SILHOUETTE_INTEGRATED_WHOLE_PERSON_CONTRACT_VERSION",
    "BODY_SILHOUETTE_MCP_FORBIDDEN_CHANNEL_FINDINGS",
    "BODY_SILHOUETTE_MCP_MATERIALIZATION_CHANNEL_CONTRACT_VERSION",
    "BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES",
    "BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES",
    "BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS",
    "BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR",
    "body_silhouette_mcp_materialization_channel_contract",
    "body_silhouette_mcp_materialization_prompt_findings",
    "body_silhouette_age6_cross_view_naturalness_contract",
    "body_silhouette_integrated_whole_person_synthesis_contract",
    "body_silhouette_source_standard_contract",
    "evaluate_body_silhouette_visual_review",
    "validate_integrated_whole_person_review_evidence",
    "validated_body_silhouette_source_standard_contract",
]
