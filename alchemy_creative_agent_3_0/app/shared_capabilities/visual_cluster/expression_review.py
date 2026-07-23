"""Shared affective-expression review receipt projection.

Doc196 keeps expression quality in the V3 foundation layer.  Specialized
modules such as Professional Character Card may ask for an ``expression.laugh``
deliverable, but they must consume this shared receipt instead of defining
private expression scores, issue gates, or framing tolerances.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION = "v3_affective_laugh_intent_v3"

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
EXPRESSION_SCORE_FLOOR_EPSILON = 0.005


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


__all__ = [
    "AffectiveExpressionReviewReceipt",
    "EXPRESSION_FRAMING_DELTA_MAX",
    "EXPRESSION_REVIEW_BLOCKING_ISSUE_CODES",
    "LAUGH_EXPRESSION_INTENT_CONTRACT_VERSION",
    "LAUGH_EXPRESSION_EVIDENCE_CODES",
    "LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES",
    "laugh_expression_intent_contract",
    "laugh_expression_materialization_directive",
    "laugh_expression_receipt_allows_slot",
    "normalize_affective_expression_score_card",
    "project_laugh_expression_review_receipt",
]
