"""Shared affective-expression review receipt projection.

Doc196 keeps expression quality in the V3 foundation layer.  Specialized
modules such as Professional Character Card may ask for an ``expression.laugh``
deliverable, but they must consume this shared receipt instead of defining
private expression scores, issue gates, or framing tolerances.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Mapping
from typing import Any, Literal


LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION = "v3_affective_laugh_intent_v3"
GENERIC_SLOT_REVIEW_RECEIPT_CONTRACT_VERSION = "v3_character_card_generic_slot_review_receipt_v1"

LAUGH_EXPRESSION_INTENT_CONTRACT: dict[str, Any] = {
    "contract_version": LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION,
    "owner": "v3_shared_visual_cluster",
    "emotion": "laugh",
    "intensity_band": "medium_to_medium_high",
    "arousal_band": "medium_to_medium_high",
    "phase": "onset_to_peak_static_keyframe",
    "static_keyframe_policy": "single_still_may_hint_motion_but_must_not_claim_time_sequence",
    "style_channel_policy": "inherit_prompt_owned_face_front_channels_without_lighting_or_complexion_override",
    "framing_policy": "inherit_face_front_visual_skeleton",
    "participation_channels": [
        "mouth_eye_coherence",
        "engaged_lively_gaze",
        "visible_eye_cheek_coupling",
        "lower_lid_periocular_participation",
        "upper_cheek_lift",
        "relaxed_jaw_opening",
        "natural_age_appropriate_teeth_visibility",
        "spontaneous_asymmetry",
        "identity_preservation",
        "age_coherence",
    ],
    "collapse_risks": [
        "polite_open_mouth_smile",
        "neutral_portrait_with_parted_lips",
        "mouth_only_expression",
        "detached_gaze",
        "frozen_periocular_region",
        "plastic_expression_symmetry",
    ],
    "video_motion_hint": "positive_laugh_keyframe_without_time_sequence_claim",
}

EXPRESSION_REVIEW_BLOCKING_ISSUE_CODES = frozenset(
    {
        "mouth_only_smile",
        "detached_gaze",
        "frozen_periocular_region",
        "plastic_expression_symmetry",
        "adultized_child_expression",
        "laugh_intensity_mismatch",
        "laugh_phase_unclear",
        "neutral_expression_collapse",
        "positive_expression_neutral_collapse",
    }
)

LAUGH_EXPRESSION_EVIDENCE_CODES = frozenset(
    {
        "laugh_expression_evidence_verified",
        "mouth_eye_coherence_verified",
        "periocular_gaze_affect_verified",
        "cheek_jaw_coupling_verified",
        "laugh_arousal_intensity_coherent",
        "laugh_age_identity_coherent",
    }
)
LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES = frozenset(
    {
        *LAUGH_EXPRESSION_EVIDENCE_CODES,
        "front_card_framing_parity_verified",
        "front_card_framing_delta_receipt_verified",
        "shared_affective_expression_review_receipt_verified",
    }
)
EXPRESSION_FRONT_CARD_FRAMING_EVIDENCE_CODES = frozenset(
    {
        "front_card_framing_parity_verified",
        "front_card_framing_delta_receipt_verified",
    }
)

LAUGH_EXPRESSION_SCORE_FLOORS = {
    "mouth_eye_coherence": 0.82,
    "gaze_engagement": 0.78,
    "periocular_affect": 0.78,
    "cheek_jaw_coupling": 0.78,
    "jaw_relaxation": 0.74,
    "arousal_intensity_coherence": 0.78,
    "spontaneity_asymmetry": 0.70,
    "expression_age_coherence": 0.78,
    "expression_identity_preservation": 0.82,
}

EXPRESSION_FRAMING_PARITY_FLOOR = 0.86
EXPRESSION_FRAMING_DELTA_MAX = {
    "face_area_delta_from_front": 0.10,
    "top_margin_delta_from_front": 0.045,
    "bottom_margin_delta_from_front": 0.055,
    "eye_line_delta_from_front": 0.045,
    "center_x_delta_from_front": 0.045,
    "shoulder_span_delta_from_front": 0.12,
    "head_yaw_delta_from_front": 0.08,
    "head_pitch_delta_from_front": 0.06,
}
BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS = (
    "body_scale_delta",
    "full_body_containment_delta",
    "ground_contact_delta",
    "limb_visibility_delta",
    "centerline_delta",
)
BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS = (
    "body_chain_coherence",
    "stage_aware_proportion",
    "head_neck_shoulder_continuity",
    "torso_limb_joint_plausibility",
    "stance_ground_contact",
    "cross_view_body_parity",
)
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
        "cross_view_body_parity_mismatch",
        "front_side_body_depth_conflict",
        "rear_body_build_conflict",
        "view_specific_age_stage_drift",
    }
)
EXPRESSION_SCORE_FLOOR_EPSILON = 0.005
DOC256_EXPRESSION_CARD_FAMILY_DIMENSIONS = (
    "model_card_crop_closeness",
    "shoulder_collar_context",
    "headroom_commercial_balance",
    "camera_distance_consistency",
)
DOC256_EXPRESSION_AFFECT_DIMENSIONS = (
    "expression_affect_readability",
    "expression_identity_preserved_under_affect",
)
DOC256_EXPRESSION_DELIVERY_SLOTS = frozenset(
    {"expression.anger", "expression.sad", "expression.laugh"}
)


def laugh_expression_intent_contract() -> dict[str, Any]:
    """Return the shared structured laugh intent contract.

    The contract is the source of truth for Professional Character Card's
    default positive expression.  Renderer prompt text is only a projection of
    these typed fields, so Provider and MCP can share the same intent without
    each module inventing its own wording.
    """

    return {
        key: list(value) if isinstance(value, list) else value
        for key, value in LAUGH_EXPRESSION_INTENT_CONTRACT.items()
    }


def laugh_expression_materialization_directive(contract: Any | None = None) -> str:
    """Project the shared laugh intent into concise renderer language."""

    data = contract if isinstance(contract, dict) else laugh_expression_intent_contract()
    if data.get("emotion") != "laugh":
        raise ValueError("laugh expression materialization requires a laugh intent contract")
    intensity = str(data.get("intensity_band") or "medium_to_medium_high").replace("_", "-")
    phase = str(data.get("phase") or "onset_to_peak_static_keyframe").replace("_", " ")
    return (
        "Render a clearly readable joyful laugh keyframe, not merely a polite open-mouth smile. "
        f"Use {intensity} expression energy in a {phase}: engaged, lively gaze as expression evidence "
        "only, clearly visible eye-cheek coupling where the upper cheeks lift into the lower eyelids, "
        "eyes stay open but become slightly narrower joyful crescent arcs, relaxed jaw opening, "
        "natural age-appropriate teeth visibility, and slight spontaneous asymmetry. The mouth opening "
        "must synchronize with cheek lift and periocular affect instead of reading as mouth-only. "
        "The still image should feel like a captured laugh keyframe, not a neutral portrait with parted lips."
    )


def expression_front_card_framing_materialization_directive() -> str:
    """Project the expression-slot front-card framing contract into renderer language."""

    return (
        "Use the approved face.front full-frame Character Card image as the framing authority: keep the same "
        "vertical 2:3 white-background card skeleton, camera distance, subject scale, head-top margin, eye-line "
        "height, centered head position, neck and upper-shoulder crop, shoulder span, white padding, lighting and "
        "white balance. Identity/detail crops are only feature evidence; they must not enlarge the face, lower the "
        "eye line, add extra torso, tighten into a big-head crop, or turn the card into a different portrait crop."
    )


@dataclass(frozen=True)
class AffectiveExpressionReviewReceipt:
    """Foundation-owned expression receipt consumed by Provider and MCP paths."""

    status: Literal["pass", "fail"]
    evidence_codes: tuple[str, ...]
    issue_codes: tuple[str, ...]
    score_dimensions: tuple[str, ...]
    framing_delta_dimensions: tuple[str, ...]
    owner: Literal["v3_shared_visual_cluster"] = "v3_shared_visual_cluster"
    contract_version: Literal["v3_affective_expression_review_receipt_v1"] = (
        "v3_affective_expression_review_receipt_v1"
    )
    expression: Literal["laugh"] = "laugh"
    framing_baseline: Literal["face.front"] = "face.front"

    @property
    def allows_slot_write(self) -> bool:
        return self.status == "pass"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "contract_version": self.contract_version,
            "expression": self.expression,
            "framing_baseline": self.framing_baseline,
            "status": self.status,
            "evidence_codes": list(self.evidence_codes),
            "issue_codes": list(self.issue_codes),
            "score_dimensions": list(self.score_dimensions),
            "framing_delta_dimensions": list(self.framing_delta_dimensions),
        }


@dataclass(frozen=True)
class GenericVisualReviewReceipt:
    """Foundation-owned generic visual review receipt for Character Card slots.

    This receipt projects an already-completed shared Vision inspection into a
    small durable proof that a candidate passed the shared visual review path.
    It deliberately does not add slot-specific expression thresholds; those
    remain explicit Enhanced quality policies such as the laugh receipt below.
    """

    status: Literal["pass", "fail"]
    evidence_codes: tuple[str, ...]
    issue_codes: tuple[str, ...]
    score_dimensions: tuple[str, ...]
    framing_delta_dimensions: tuple[str, ...]
    owner: Literal["v3_shared_visual_cluster"] = "v3_shared_visual_cluster"
    contract_version: Literal["v3_character_card_generic_slot_review_receipt_v1"] = (
        GENERIC_SLOT_REVIEW_RECEIPT_CONTRACT_VERSION
    )

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "owner": self.owner,
            "contract_version": self.contract_version,
            "status": self.status,
            "evidence_codes": list(self.evidence_codes),
            "issue_codes": list(self.issue_codes),
            "score_dimensions": list(self.score_dimensions),
            "framing_delta_dimensions": list(self.framing_delta_dimensions),
        }


def normalize_affective_expression_score_card(raw_score_card: Any) -> dict[str, float]:
    """Normalize shared Vision expression dimensions and aliases.

    This function only reshapes already-observed review evidence.  It does not
    inspect pixels, infer local scores, or add specialized-module policy.
    """

    if not isinstance(raw_score_card, dict):
        return {}
    score_card: dict[str, float] = {}
    for key, value in raw_score_card.items():
        try:
            score_card[str(key)] = float(value)
        except (TypeError, ValueError):
            continue

    def copy_first(target: str, aliases: tuple[str, ...]) -> None:
        if target in score_card:
            return
        for alias in aliases:
            if alias in score_card:
                score_card[target] = score_card[alias]
                return

    copy_first("mouth_eye_coherence", ("mouth-eye_coherence", "mouth_and_eye_coherence"))
    copy_first("gaze_engagement", ("engaged_gaze", "eye_contact_engagement"))
    copy_first("periocular_affect", ("periocular_expression", "lower_lid_affect"))
    copy_first("cheek_jaw_coupling", ("lower_lid_cheek_coupling", "cheek_lift_jaw_relaxation"))
    copy_first("jaw_relaxation", ("relaxed_jaw", "jaw_state"))
    copy_first("arousal_intensity_coherence", ("laugh_arousal_intensity_coherence", "expression_intensity_coherence"))
    copy_first("spontaneity_asymmetry", ("spontaneous_asymmetry", "natural_asymmetry"))
    copy_first("expression_age_coherence", ("age_coherence", "developmental_age_coherence"))
    copy_first("expression_identity_preservation", ("identity_preservation", "expression_identity"))
    copy_first("expression_framing_parity", ("front_card_framing_parity", "framing_parity"))
    copy_first("face_area_delta_from_front", ("face_area_delta", "normalized_face_area_delta"))
    copy_first("top_margin_delta_from_front", ("top_margin_delta", "normalized_top_margin_delta"))
    copy_first("bottom_margin_delta_from_front", ("bottom_margin_delta", "normalized_bottom_margin_delta"))
    copy_first("eye_line_delta_from_front", ("eye_line_delta", "normalized_eye_line_delta"))
    copy_first("center_x_delta_from_front", ("center_x_delta", "normalized_center_x_delta"))
    copy_first("shoulder_span_delta_from_front", ("shoulder_span_delta", "normalized_shoulder_span_delta"))
    copy_first("head_yaw_delta_from_front", ("head_yaw_delta", "normalized_head_yaw_delta"))
    copy_first("head_pitch_delta_from_front", ("head_pitch_delta", "normalized_head_pitch_delta"))
    return score_card


def project_generic_visual_review_receipt(
    *,
    score_card: Any,
    issue_codes: list[str] | tuple[str, ...] | set[str],
    verified: bool,
    raw_status: str,
    require_front_card_framing: bool = False,
    framing_dimension_allowlist: list[str] | tuple[str, ...] | set[str] | None = None,
) -> GenericVisualReviewReceipt:
    """Project shared Vision's generic pass/fail facts into a safe receipt.

    The function only preserves facts already produced by the shared review
    package: verification status, issue codes and score dimension names.  It
    does not create an anger/sad/body private reviewer and does not introduce
    new thresholds.
    """

    normalized_scores = normalize_affective_expression_score_card(score_card)
    normalized_issues = tuple(
        dict.fromkeys(str(item or "").strip() for item in issue_codes if str(item or "").strip())
    )
    framing_issues = _front_card_framing_gate_issues(normalized_scores) if require_front_card_framing else []
    status = (
        "pass"
        if verified
        and str(raw_status or "").strip().lower() in {"pass", "warning"}
        and not framing_issues
        else "fail"
    )
    evidence_codes = ["shared_visual_review_verified" if verified else "shared_visual_review_unverified"]
    if status == "pass":
        evidence_codes.append("shared_visual_review_status_pass")
        if require_front_card_framing:
            evidence_codes.extend(sorted(EXPRESSION_FRONT_CARD_FRAMING_EVIDENCE_CODES))
    allowed_framing_dimensions = (
        tuple(EXPRESSION_FRAMING_DELTA_MAX)
        if framing_dimension_allowlist is None
        else tuple(
            dict.fromkeys(
                str(dimension or "").strip()
                for dimension in framing_dimension_allowlist
                if str(dimension or "").strip()
            )
        )
    )
    framing_dimensions = tuple(
        sorted(dimension for dimension in allowed_framing_dimensions if dimension in normalized_scores)
    )
    return GenericVisualReviewReceipt(
        status=status,
        evidence_codes=tuple(dict.fromkeys(evidence_codes)),
        issue_codes=tuple(dict.fromkeys([*normalized_issues, *framing_issues])),
        score_dimensions=tuple(sorted(normalized_scores)),
        framing_delta_dimensions=framing_dimensions,
    )


def project_laugh_expression_review_receipt(
    *,
    score_card: Any,
    issue_codes: list[str] | tuple[str, ...] | set[str],
) -> AffectiveExpressionReviewReceipt:
    """Project shared Vision laugh evidence into a foundation receipt."""

    normalized_scores = normalize_affective_expression_score_card(score_card)
    normalized_issues = {str(item or "").strip() for item in issue_codes if str(item or "").strip()}
    gate_issues: list[str] = []
    if normalized_issues.intersection(EXPRESSION_REVIEW_BLOCKING_ISSUE_CODES):
        gate_issues.append("shared_affective_laugh_expression_blocked")

    missing_or_low = [
        dimension
        for dimension, floor in LAUGH_EXPRESSION_SCORE_FLOORS.items()
        if _score_below_floor(normalized_scores, dimension, floor)
    ]
    if missing_or_low:
        gate_issues.append("shared_affective_laugh_evidence_below_bar")

    if _score_below_floor(
        normalized_scores,
        "expression_framing_parity",
        EXPRESSION_FRAMING_PARITY_FLOOR,
    ):
        gate_issues.append("shared_affective_expression_framing_drift")
    gate_issues.extend(_expression_framing_delta_issues(normalized_scores))

    evidence_codes = (
        tuple(
            sorted(
                [
                    *LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
                ]
            )
        )
        if not gate_issues
        else ()
    )
    return AffectiveExpressionReviewReceipt(
        status="pass" if not gate_issues else "fail",
        evidence_codes=evidence_codes,
        issue_codes=tuple(dict.fromkeys(gate_issues)),
        score_dimensions=tuple(sorted(normalized_scores)),
        framing_delta_dimensions=tuple(sorted(EXPRESSION_FRAMING_DELTA_MAX)),
    )


def laugh_expression_receipt_allows_slot(
    *,
    evidence_codes: list[str] | tuple[str, ...] | set[str],
    issue_codes: list[str] | tuple[str, ...] | set[str],
) -> bool:
    """Return whether a shared laugh receipt is sufficient for slot write."""

    normalized_issues = {str(item or "").strip() for item in issue_codes if str(item or "").strip()}
    if normalized_issues.intersection(EXPRESSION_REVIEW_BLOCKING_ISSUE_CODES):
        return False
    normalized_evidence = {str(item or "").strip() for item in evidence_codes if str(item or "").strip()}
    return LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES.issubset(normalized_evidence)


def expression_front_card_framing_receipt_allows_slot(
    shared_review_receipts: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> bool:
    """Return whether a shared expression receipt preserves face.front framing."""

    for receipt in shared_review_receipts or []:
        if not isinstance(receipt, dict):
            continue
        if receipt.get("owner") != "v3_shared_visual_cluster":
            continue
        if receipt.get("contract_version") != GENERIC_SLOT_REVIEW_RECEIPT_CONTRACT_VERSION:
            continue
        if receipt.get("status") != "pass":
            continue
        issues = {str(item or "").strip() for item in receipt.get("issue_codes", [])}
        if {
            "shared_affective_expression_framing_receipt_missing",
            "shared_affective_expression_framing_drift",
        }.intersection(issues):
            continue
        evidence = {str(item or "").strip() for item in receipt.get("evidence_codes", [])}
        if not EXPRESSION_FRONT_CARD_FRAMING_EVIDENCE_CODES.issubset(evidence):
            continue
        if not receipt.get("framing_delta_dimensions"):
            continue
        return True
    return False


def project_expression_model_card_proofs(
    *,
    slot_key: str,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
    review_binding: Mapping[str, Any],
    score_card: Any,
    issue_codes: list[str] | tuple[str, ...] | set[str],
    verified: bool,
    raw_status: str,
    acceptance_mode: str,
) -> dict[str, dict[str, Any]]:
    """Project canonical Expression review facts into Doc256 consumer proofs.

    The projector only packages already-reviewed shared Vision facts.  It does
    not select a winner, write a receipt, infer missing framing/affect proof,
    or upgrade target-only/legacy collection into Doc256 completion.
    """

    normalized_scores = normalize_affective_expression_score_card(score_card)
    binding = _doc256_expression_review_binding(
        review_binding,
        candidate_id=candidate_id,
        output_id=output_id,
        operation_id=operation_id,
        round_id=round_id,
    )
    normalized_issues = [
        str(item or "").strip()
        for item in issue_codes
        if str(item or "").strip()
    ]
    status_allowed = bool(verified) and str(raw_status or "").strip().lower() == "pass"
    standard_mode = str(acceptance_mode or "").strip() == "standard_three_candidate"
    valid_slot = slot_key in DOC256_EXPRESSION_DELIVERY_SLOTS

    shared_issues: list[str] = []
    if not valid_slot:
        shared_issues.append("expression_model_card_scope_invalid")
    if not standard_mode:
        shared_issues.append("legacy_target_only_not_doc256_completion")
    if not status_allowed:
        shared_issues.append("expression_model_card_shared_review_not_pass")
    if _doc256_binding_has_missing_or_mismatch(
        binding,
        candidate_id=candidate_id,
        output_id=output_id,
        operation_id=operation_id,
        round_id=round_id,
    ):
        shared_issues.append("expression_model_card_review_binding_mismatch")
    shared_issues.extend(normalized_issues)

    framing_dimensions = _doc256_finite_dimensions(
        normalized_scores,
        DOC256_EXPRESSION_CARD_FAMILY_DIMENSIONS,
    )
    affect_dimensions = _doc256_finite_dimensions(
        normalized_scores,
        DOC256_EXPRESSION_AFFECT_DIMENSIONS,
    )

    framing_issues = list(shared_issues)
    if set(framing_dimensions) != set(DOC256_EXPRESSION_CARD_FAMILY_DIMENSIONS):
        framing_issues.append("card_family_framing_evidence_missing")
    affect_issues = list(shared_issues)
    if set(affect_dimensions) != set(DOC256_EXPRESSION_AFFECT_DIMENSIONS):
        affect_issues.append("expression_affect_evidence_missing")

    return {
        "card_family_framing": {
            "owner": "shared_card_family_framing",
            "contract_version": "v3_card_family_framing_contract_v1",
            "profile_id": "card_family_framing_v1",
            "requirement_id": "close_photographic_model_card_framing_v1",
            "status": "fail" if framing_issues else "pass",
            "module": "expression_set",
            "slot": slot_key,
            "view_role": slot_key,
            "slot_scope": "formal_slot",
            **binding,
            "evidence_codes": ["close_model_card_crop_verified"] if not framing_issues else [],
            "issue_codes": list(dict.fromkeys(framing_issues)),
            "dimensions": framing_dimensions,
        },
        "affect_proof": {
            "owner": "expression_affect_profile",
            "profile_id": f"{slot_key}_affect_v1",
            "status": "fail" if affect_issues else "pass",
            "module": "expression_set",
            "slot": slot_key,
            **binding,
            "evidence_codes": ["expression_affect_delta_verified"] if not affect_issues else [],
            "issue_codes": list(dict.fromkeys(affect_issues)),
            "dimensions": {
                "affect_readability": affect_dimensions.get("expression_affect_readability", 0.0),
                "identity_preserved_under_affect": affect_dimensions.get(
                    "expression_identity_preserved_under_affect",
                    0.0,
                ),
            },
        },
    }


def _front_card_framing_gate_issues(score_card: dict[str, float]) -> list[str]:
    issues: list[str] = []
    if _score_below_floor(
        score_card,
        "expression_framing_parity",
        EXPRESSION_FRAMING_PARITY_FLOOR,
    ):
        issues.append("shared_affective_expression_framing_drift")
    issues.extend(_expression_framing_delta_issues(score_card))
    return list(dict.fromkeys(issues))


def _expression_framing_delta_issues(score_card: dict[str, float]) -> list[str]:
    missing: list[str] = []
    drifting: list[str] = []
    for dimension, maximum_delta in EXPRESSION_FRAMING_DELTA_MAX.items():
        raw_value = score_card.get(dimension)
        if raw_value is None:
            missing.append(dimension)
            continue
        try:
            value = abs(float(raw_value))
        except (TypeError, ValueError):
            missing.append(dimension)
            continue
        if value > maximum_delta + EXPRESSION_SCORE_FLOOR_EPSILON:
            drifting.append(dimension)
    issues: list[str] = []
    if missing:
        issues.append("shared_affective_expression_framing_receipt_missing")
    if drifting:
        issues.append("shared_affective_expression_framing_drift")
    return issues


def _score_below_floor(score_card: dict[str, float], dimension: str, floor: float) -> bool:
    value = score_card.get(dimension)
    if value is None:
        return True
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return True
    return numeric + EXPRESSION_SCORE_FLOOR_EPSILON < floor


def _doc256_expression_review_binding(
    review_binding: Mapping[str, Any],
    *,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
) -> dict[str, str]:
    if isinstance(review_binding, Mapping):
        return {
            "candidate_id": str(review_binding.get("candidate_id") or ""),
            "output_id": str(review_binding.get("output_id") or ""),
            "operation_id": str(review_binding.get("operation_id") or ""),
            "round_id": str(review_binding.get("round_id") or ""),
        }
    return {
        "candidate_id": "",
        "output_id": "",
        "operation_id": "",
        "round_id": "",
    }


def _doc256_binding_has_missing_or_mismatch(
    binding: Mapping[str, str],
    *,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
) -> bool:
    expected_values = (candidate_id, output_id, operation_id, round_id)
    if any(not str(value or "").strip() for value in expected_values):
        return True
    for key, expected in (
        ("candidate_id", candidate_id),
        ("output_id", output_id),
        ("operation_id", operation_id),
        ("round_id", round_id),
    ):
        if str(binding.get(key) or "") != str(expected or ""):
            return True
    return False


def _doc256_finite_dimensions(
    score_card: Mapping[str, float],
    dimensions: tuple[str, ...],
) -> dict[str, float]:
    values: dict[str, float] = {}
    for dimension in dimensions:
        raw_value = score_card.get(dimension)
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(value) and 0.0 <= value <= 1.0:
            values[dimension] = value
    return values


__all__ = [
    "AffectiveExpressionReviewReceipt",
    "BODY_SILHOUETTE_FRAMING_DELTA_DIMENSIONS",
    "BODY_SILHOUETTE_SOURCE_STANDARD_BLOCKING_ISSUE_CODES",
    "BODY_SILHOUETTE_SOURCE_STANDARD_DIMENSIONS",
    "EXPRESSION_FRAMING_DELTA_MAX",
    "EXPRESSION_FRONT_CARD_FRAMING_EVIDENCE_CODES",
    "EXPRESSION_REVIEW_BLOCKING_ISSUE_CODES",
    "GENERIC_SLOT_REVIEW_RECEIPT_CONTRACT_VERSION",
    "GenericVisualReviewReceipt",
    "LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION",
    "LAUGH_EXPRESSION_EVIDENCE_CODES",
    "LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES",
    "expression_front_card_framing_materialization_directive",
    "expression_front_card_framing_receipt_allows_slot",
    "laugh_expression_intent_contract",
    "laugh_expression_materialization_directive",
    "laugh_expression_receipt_allows_slot",
    "normalize_affective_expression_score_card",
    "project_expression_model_card_proofs",
    "project_generic_visual_review_receipt",
    "project_laugh_expression_review_receipt",
]
