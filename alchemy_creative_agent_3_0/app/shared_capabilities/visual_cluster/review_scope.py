"""DOC316 shared review-scope and evidence-separation helpers.

The visual inspector's status remains the canonical safety decision.  This
module provides an additive, mode-agnostic explanation of that decision so a
missing certificate is not presented as proof that the pixels are poor.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Iterable


UNIVERSAL_REVIEW_SCHEMA_VERSION = "v3_universal_visual_quality_review_v1"
UNIVERSAL_REVIEW_AUTHORITY = "shared_visual_inspection"
UNIVERSAL_REVIEW_MODES = (
    "selection_candidates",
    "delivery_suite",
    "creative_exploration",
    "format_layout_adaptation",
)

UNIVERSAL_REVIEW_DIMENSIONS = (
    "technical_integrity",
    "core_subject_and_user_intent",
    "composition_and_readability",
    "aesthetic_finish",
    "artifact_cleanliness",
    "human_naturalness_when_visible",
    "reference_fidelity_when_provided",
)

# Keep this list intentionally small and orthogonal.  Mode role/format codes
# are owned by ModeAwareRoleDirector and must not enter this shared list.
UNIVERSAL_REVIEW_ISSUE_CODES = (
    "visible_text_artifact",
    "watermark_or_signature",
    "faint_corner_watermark",
    "ai_generated_badge_trace",
    "signature_like_artifact",
    "lower_right_mark_artifact",
    "collage_or_split_panel",
    "lighting_mismatch",
    "composition_mismatch",
    "weak_aesthetic_finish",
    "overexposed_washout",
    "underexposed_muddy_frame",
    "low_resolution_output",
    "low_confidence_review",
)

# These codes say that the system cannot certify a conclusion.  They are not
# visual defects.  Prefixes cover output-scoped evidence contracts introduced
# after DOC316 without making every future evidence code a quality recipe.
EVIDENCE_ONLY_REVIEW_ISSUE_CODES = frozenset(
    {
        "file_missing",
        "file_unreadable",
        "vision_provider_unavailable",
        "low_confidence_review",
        "provider_error",
        "provider_timeout",
        "face_integrity_unverified",
        "face_reference_comparison_unverified",
        "metadata_only_non_certifying",
        "hard_semantic_contract_unverified",
        "reference_evidence_unavailable",
        "feedback_or_similarity_not_verifiable",
        "human_naturalness_unverified",
    }
)
EVIDENCE_ONLY_REVIEW_ISSUE_PREFIXES = (
    "review_evidence_",
    "legacy_reference_",
    "public_review_",
)

REAL_PIXEL_REVIEW_MODES = frozenset({"vision_model", "hybrid"})
QUALITY_FAILURE_STATUSES = frozenset({"fail_retryable", "fail_final"})


def universal_review_scope() -> dict[str, Any]:
    """Return the public-safe shared contract descriptor."""

    return {
        "schema_version": UNIVERSAL_REVIEW_SCHEMA_VERSION,
        "authority": UNIVERSAL_REVIEW_AUTHORITY,
        "mode_agnostic": True,
        "applies_to_modes": list(UNIVERSAL_REVIEW_MODES),
        "mode_semantics_separate": True,
        "mode_semantics_owner": "ModeAwareRoleDirector",
        "dimensions": list(UNIVERSAL_REVIEW_DIMENSIONS),
        "issue_codes": list(UNIVERSAL_REVIEW_ISSUE_CODES),
        "evidence_only_issue_codes": sorted(EVIDENCE_ONLY_REVIEW_ISSUE_CODES),
    }


def classify_review_outcome(
    inspection: Any,
    *,
    provider_pixel_certified: bool | None = None,
) -> dict[str, Any]:
    """Separate pixel quality, evidence, and delivery explanation.

    ``VisualInspectionReport.status`` is deliberately not rewritten.  A
    ``manual_review`` report with only evidence/uncertainty codes means that
    no quality failure was established; a manual report with a substantive
    issue remains unresolved and needs a person. Only a verified pixel review
    with a substantive visual issue and a fail status sets ``quality_failure``.
    Metadata preflight and missing certificates never establish poor pixels.
    """

    status = _text(_value(inspection, "status"), default="not_assessed").lower()
    mode = _text(_value(inspection, "mode"), default="metadata_only").lower()
    verification_state = _text(
        _value(inspection, "verification_state"),
        default="unverified",
    ).lower()
    evidence = _mapping(_value(inspection, "evidence"))
    issue_codes = _issue_codes(_value(inspection, "detected_issues"))
    evidence_issue_codes = [code for code in issue_codes if _is_evidence_only(code)]
    quality_issue_codes = [code for code in issue_codes if code not in set(evidence_issue_codes)]
    certification_denied = provider_pixel_certified is False or evidence.get("provider_pixel_result_certified") is False
    if provider_pixel_certified is None:
        provider_pixel_certified = bool(evidence.get("provider_pixel_result_certified"))

    evidence_state = _evidence_state(
        mode=mode,
        verification_state=verification_state,
        provider_pixel_certified=bool(provider_pixel_certified),
        issue_codes=issue_codes,
    )
    has_verified_pixels = (
        mode in REAL_PIXEL_REVIEW_MODES
        and verification_state == "verified"
        and not certification_denied
    )
    if not has_verified_pixels or (status in QUALITY_FAILURE_STATUSES and not quality_issue_codes):
        quality_assessment = "not_assessed"
        quality_failure = False
        review_reason = "evidence_incomplete"
    elif status in QUALITY_FAILURE_STATUSES:
        quality_assessment = status
        quality_failure = True
        review_reason = "quality_issue"
    elif status in {"pass", "warning"}:
        quality_assessment = status
        quality_failure = False
        review_reason = (
            "quality_issue"
            if quality_issue_codes
            else "evidence_incomplete"
            if evidence_state == "incomplete"
            else "not_evaluated"
            if evidence_state == "unavailable"
            else "not_evaluated"
        )
    elif status == "manual_review":
        quality_assessment = "needs_manual_review" if quality_issue_codes else "not_assessed"
        quality_failure = False
        review_reason = (
            "quality_issue"
            if quality_issue_codes
            else "evidence_incomplete"
            if evidence_state in {"incomplete", "unavailable"}
            or evidence_issue_codes
            else "review_uncertain"
        )
    else:
        quality_assessment = "not_assessed"
        quality_failure = False
        review_reason = (
            "evidence_incomplete"
            if evidence_state in {"incomplete", "unavailable"} and (evidence_issue_codes or mode in REAL_PIXEL_REVIEW_MODES)
            else "review_uncertain"
        )

    return {
        "schema_version": UNIVERSAL_REVIEW_SCHEMA_VERSION,
        "quality_assessment": quality_assessment,
        "quality_failure": quality_failure,
        "evidence_state": evidence_state,
        "review_reason": review_reason,
        "mode": mode,
        "verification_state": verification_state,
        "quality_issue_codes": quality_issue_codes,
        "evidence_issue_codes": evidence_issue_codes,
    }


def aggregate_review_outcomes(outcomes: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate output-level classifications without erasing their detail."""

    normalized = [dict(item) for item in outcomes if isinstance(item, Mapping)]
    if not normalized:
        return {
            "schema_version": UNIVERSAL_REVIEW_SCHEMA_VERSION,
            "quality_assessment": "not_assessed",
            "quality_failure": False,
            "evidence_state": "unavailable",
            "review_reason": "not_evaluated",
        }

    statuses = {_text(item.get("quality_assessment"), default="not_assessed") for item in normalized}
    has_quality_findings = any(bool(item.get("quality_issue_codes")) for item in normalized)
    if any(bool(item.get("quality_failure")) for item in normalized):
        quality_assessment = (
            "fail_final" if "fail_final" in statuses else "fail_retryable"
        )
        quality_failure = True
        review_reason = "quality_issue"
    elif "needs_manual_review" in statuses:
        quality_assessment = "needs_manual_review"
        quality_failure = False
        review_reason = "quality_issue"
    elif "not_assessed" in statuses:
        quality_assessment = "not_assessed"
        quality_failure = False
        review_reason = "evidence_incomplete"
    elif "warning" in statuses:
        quality_assessment = "warning"
        quality_failure = False
        review_reason = "quality_issue" if has_quality_findings else "not_evaluated"
    elif "pass" in statuses:
        quality_assessment = "pass"
        quality_failure = False
        review_reason = "quality_issue" if has_quality_findings else "not_evaluated"
    else:
        quality_assessment = "not_assessed"
        quality_failure = False
        review_reason = "review_uncertain"

    evidence_states = {_text(item.get("evidence_state"), default="unavailable") for item in normalized}
    if evidence_states == {"certified"}:
        evidence_state = "certified"
    elif "incomplete" in evidence_states:
        evidence_state = "incomplete"
    else:
        evidence_state = "unavailable"
    if not quality_failure and evidence_state in {"incomplete", "unavailable"}:
        review_reason = "evidence_incomplete" if evidence_state == "incomplete" else review_reason
    return {
        "schema_version": UNIVERSAL_REVIEW_SCHEMA_VERSION,
        "quality_assessment": quality_assessment,
        "quality_failure": quality_failure,
        "evidence_state": evidence_state,
        "review_reason": review_reason,
    }


def _evidence_state(
    *,
    mode: str,
    verification_state: str,
    provider_pixel_certified: bool,
    issue_codes: list[str],
) -> str:
    if mode not in REAL_PIXEL_REVIEW_MODES:
        return "unavailable"
    if (
        verification_state == "verified"
        and provider_pixel_certified
        and not any(_is_evidence_only(code) for code in issue_codes)
    ):
        return "certified"
    if verification_state in {"verified", "unverified", "locally_checked"} or issue_codes:
        return "incomplete"
    return "unavailable"


def _is_evidence_only(code: str) -> bool:
    return code in EVIDENCE_ONLY_REVIEW_ISSUE_CODES or code.startswith(EVIDENCE_ONLY_REVIEW_ISSUE_PREFIXES)


def _issue_codes(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    result: list[str] = []
    seen: set[str] = set()
    for issue in value:
        raw = _value(issue, "code") if not isinstance(issue, str) else issue
        code = _text(raw)
        if code and code not in seen:
            seen.add(code)
            result.append(code)
    return result


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _value(value: Any, key: str) -> Any:
    if isinstance(value, Mapping):
        return value.get(key)
    return getattr(value, key, None)


def _text(value: Any, *, default: str = "") -> str:
    text = str(value or "").strip()
    return text or default
