"""Professional Character Card Body Silhouette source-standard ownership.

This module owns the closed, scene-neutral source-standard vocabulary for
Body Silhouette candidate review.  Shared Vision may project these labels when
the Character Card Body stage asks for them, but the shared layer does not own
or globally apply the contract.
"""

from __future__ import annotations

import math
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
        "doll_like_body_chain",
        "mannequin_body_chain",
        "body_chain_discontinuity",
        "stage_incoherent_body_proportion",
        "over_infantilized_body",
        "accidental_adultification",
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
    }
)


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
    "BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES",
    "BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSION_EVIDENCE_CODES",
    "BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS",
    "BODY_SILHOUETTE_SOURCE_STANDARD_SCORE_FLOOR",
    "body_silhouette_source_standard_contract",
    "validated_body_silhouette_source_standard_contract",
]
