"""Doc256 neutral card-family framing contract.

This module owns only versioned, reviewable framing evidence for the close
photographic model-card family.  It is deliberately neutral between Face
``standard_front`` and Expression delivery slots and does not import Formal
Core, Provider/MCP routing, route handlers, Body, or slot lifecycle code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ...schemas.models import V3BaseModel


CARD_FAMILY_FRAMING_OWNER = "shared_card_family_framing"
CARD_FAMILY_FRAMING_CONTRACT_VERSION = "v3_card_family_framing_contract_v1"
CARD_FAMILY_FRAMING_PROFILE_ID = "card_family_framing_v1"
CARD_FAMILY_FRAMING_REQUIREMENT_ID = "close_photographic_model_card_framing_v1"
CARD_FAMILY_CALIBRATION_ARTIFACT_ID = "close_model_card_framing_family_calibration_v1"

CardFamilyFramingStatus = Literal["pass", "fail"]

_SAFE_FORBIDDEN_TOKENS = (
    "prompt",
    "provider",
    "mcp",
    "handoff",
    "artifact",
    "path",
    "file",
    "api",
    "secret",
    "token",
    "raw",
)
_FORMAL_FACE_SCOPE = ("face_identity", "standard_front", "formal_slot")
_EXPRESSION_DELIVERY_SLOTS = frozenset(
    {"expression.anger", "expression.sad", "expression.laugh"}
)
_REQUIRED_VISIBLE_EVIDENCE = frozenset(
    {"hair", "face", "neck", "collar", "upper_shoulder"}
)
_REQUIRED_DIMENSIONS = (
    "model_card_crop_closeness",
    "shoulder_collar_context",
    "headroom_commercial_balance",
    "camera_distance_consistency",
)


class _StrictCardFamilyModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


def _safe_label(value: object, field_name: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field_name} must be nonempty")
    lowered = label.lower()
    if any(token in lowered for token in _SAFE_FORBIDDEN_TOKENS):
        raise ValueError(f"{field_name} is not public-safe")
    return label


def _safe_codes(values: Sequence[str], field_name: str) -> list[str]:
    normalized = [str(value or "").strip() for value in values]
    if any(not value for value in normalized):
        raise ValueError(f"{field_name} must be nonempty")
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must be unique")
    return normalized


def _public_safe_codes(values: Sequence[str]) -> list[str]:
    safe: list[str] = []
    for value in values:
        lowered = value.lower()
        if any(token in lowered for token in _SAFE_FORBIDDEN_TOKENS):
            continue
        safe.append(value)
    return safe


def _finite_unit(value: object, field_name: str) -> float:
    score = float(value)
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        raise ValueError(f"{field_name} must be finite in [0, 1]")
    return score


def _finite_unit_or_issue(value: object, field_name: str, issue_codes: list[str]) -> float | None:
    try:
        return _finite_unit(value, field_name)
    except (TypeError, ValueError):
        issue_codes.append("card_family_framing_dimension_not_finite")
        return None


def _band(value: Sequence[float], field_name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{field_name} requires two values")
    low = _finite_unit(value[0], field_name)
    high = _finite_unit(value[1], field_name)
    if low > high:
        raise ValueError(f"{field_name} lower bound must not exceed upper bound")
    return (low, high)


class CardFamilyFramingCalibrationArtifact(_StrictCardFamilyModel):
    artifact_id: str
    profile_id: Literal["card_family_framing_v1"] = CARD_FAMILY_FRAMING_PROFILE_ID
    version: str
    provenance: Literal["server_owned_calibration_v1"]
    approval_status: Literal["approved"]
    source_fixture_set: str
    measurement_method: str
    applies_to: list[str]
    dimension_bands: dict[str, tuple[float, float]]
    round_variance_limits: dict[str, float]

    @field_validator("artifact_id", "version", "source_fixture_set", "measurement_method")
    @classmethod
    def validate_labels(cls, value: str) -> str:
        return _safe_label(value, "card-family calibration label")

    @field_validator("applies_to")
    @classmethod
    def validate_applies_to(cls, value: list[str]) -> list[str]:
        normalized = _safe_codes(value, "card-family applies_to")
        allowed = {"face_identity:standard_front", "expression_set:delivery_slots"}
        if not set(normalized).issubset(allowed):
            raise ValueError("card-family calibration applies_to unsupported scope")
        return normalized

    @field_validator("dimension_bands", mode="before")
    @classmethod
    def validate_dimension_bands(cls, value: Mapping[str, Sequence[float]]) -> dict[str, tuple[float, float]]:
        normalized: dict[str, tuple[float, float]] = {}
        for key, band in value.items():
            normalized[_safe_label(key, "card-family calibration dimension")] = _band(
                band, "card-family calibration band"
            )
        return normalized

    @field_validator("round_variance_limits")
    @classmethod
    def validate_round_variance_limits(cls, value: dict[str, float]) -> dict[str, float]:
        return {
            _safe_label(key, "card-family variance dimension"): _finite_unit(
                limit, "card-family variance limit"
            )
            for key, limit in value.items()
        }

    @model_validator(mode="after")
    def validate_artifact(self) -> "CardFamilyFramingCalibrationArtifact":
        if self.artifact_id != CARD_FAMILY_CALIBRATION_ARTIFACT_ID:
            raise ValueError("card_family_framing_calibration_artifact_invalid")
        missing = [key for key in _REQUIRED_DIMENSIONS if key not in self.dimension_bands]
        if missing:
            raise ValueError("card_family_framing_calibration_dimension_missing")
        return self


class CardFamilyFramingProof(_StrictCardFamilyModel):
    owner: Literal["shared_card_family_framing"] = CARD_FAMILY_FRAMING_OWNER
    contract_version: Literal["v3_card_family_framing_contract_v1"] = (
        CARD_FAMILY_FRAMING_CONTRACT_VERSION
    )
    profile_id: Literal["card_family_framing_v1"] = CARD_FAMILY_FRAMING_PROFILE_ID
    requirement_id: Literal["close_photographic_model_card_framing_v1"] = (
        CARD_FAMILY_FRAMING_REQUIREMENT_ID
    )
    status: CardFamilyFramingStatus
    eligible: bool
    module: str | None = None
    slot: str | None = None
    view_role: str | None = None
    slot_scope: str | None = None
    candidate_id: str | None = None
    output_id: str | None = None
    operation_id: str | None = None
    round_id: str | None = None
    evidence_codes: list[str] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)

    @field_validator(
        "module",
        "slot",
        "view_role",
        "slot_scope",
        "candidate_id",
        "output_id",
        "operation_id",
        "round_id",
    )
    @classmethod
    def validate_optional_labels(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _safe_label(value, "card-family identity")

    @field_validator("evidence_codes", "issue_codes")
    @classmethod
    def validate_codes(cls, value: list[str]) -> list[str]:
        return _safe_codes(value, "card-family code")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return {
            _safe_label(key, "card-family dimension"): _finite_unit(
                score, "card-family dimension"
            )
            for key, score in value.items()
        }

    @model_validator(mode="after")
    def validate_status(self) -> "CardFamilyFramingProof":
        if self.eligible != (self.status == "pass"):
            raise ValueError("card-family framing eligibility must match pass status")
        if self.status == "pass" and not self.evidence_codes:
            raise ValueError("passing card-family framing proof requires evidence")
        return self

    def public_summary(self) -> dict[str, object]:
        return {
            "owner": self.owner,
            "contract_version": self.contract_version,
            "profile_id": self.profile_id,
            "requirement_id": self.requirement_id,
            "eligible": self.eligible,
            "status": self.status,
            "evidence_codes": _public_safe_codes(self.evidence_codes),
            "issue_codes": _public_safe_codes(self.issue_codes),
            "dimensions": dict(self.dimensions),
        }


def card_family_framing_applies(
    *,
    module: str,
    view_role: str,
    slot_scope: str,
    slot: str | None = None,
) -> bool:
    if (module, view_role, slot_scope) == _FORMAL_FACE_SCOPE:
        return True
    if module == "expression_set" and slot_scope == "formal_slot":
        return (slot or view_role) in _EXPRESSION_DELIVERY_SLOTS
    return False


def _calibration_or_fail(
    calibration: Mapping[str, object] | CardFamilyFramingCalibrationArtifact | None,
) -> tuple[CardFamilyFramingCalibrationArtifact | None, list[str]]:
    if calibration is None:
        return None, ["card_family_framing_calibration_required"]
    try:
        if isinstance(calibration, CardFamilyFramingCalibrationArtifact):
            return calibration, []
        return CardFamilyFramingCalibrationArtifact.model_validate(calibration), []
    except ValueError as exc:
        message = str(exc)
        if "approval_status" in message:
            return None, ["card_family_framing_calibration_not_approved"]
        if "artifact" in message:
            return None, ["card_family_framing_calibration_artifact_invalid"]
        return None, ["card_family_framing_calibration_invalid"]


def _binding_issue(
    payload: Mapping[str, object],
    expected_binding: Mapping[str, object] | None,
) -> bool:
    if not expected_binding:
        return False
    for key in ("candidate_id", "output_id", "operation_id", "round_id"):
        if str(payload.get(key) or "") != str(expected_binding.get(key) or ""):
            return True
    return False


def _scope_key(module: str, view_role: str, slot: str | None) -> str:
    if module == "face_identity" and view_role == "standard_front":
        return "face_identity:standard_front"
    if module == "expression_set" and (slot or view_role) in _EXPRESSION_DELIVERY_SLOTS:
        return "expression_set:delivery_slots"
    return ""


def evaluate_card_family_framing(
    metrics: Mapping[str, object],
    *,
    calibration: Mapping[str, object] | CardFamilyFramingCalibrationArtifact | None,
    expected_binding: Mapping[str, object] | None = None,
) -> CardFamilyFramingProof:
    calibration_model, issue_codes = _calibration_or_fail(calibration)
    evidence_codes: list[str] = []
    dimensions: dict[str, float] = {}
    module = str(metrics.get("module") or "")
    slot = str(metrics.get("slot") or "") or None
    view_role = str(metrics.get("view_role") or "")
    slot_scope = str(metrics.get("slot_scope") or "")
    candidate_id = str(metrics.get("candidate_id") or "") or None
    output_id = str(metrics.get("output_id") or "") or None
    operation_id = str(metrics.get("operation_id") or "") or None
    round_id = str(metrics.get("round_id") or "") or None

    if not card_family_framing_applies(
        module=module, view_role=view_role, slot_scope=slot_scope, slot=slot
    ):
        issue_codes.append("card_family_framing_scope_invalid")
    elif calibration_model is not None:
        scope_key = _scope_key(module, view_role, slot)
        if scope_key not in calibration_model.applies_to:
            issue_codes.append("card_family_calibration_scope_not_applicable")
    if str(metrics.get("shared_review_status") or "") != "pass":
        issue_codes.append("card_family_shared_review_not_pass")
    if not all((candidate_id, output_id, operation_id, round_id)):
        issue_codes.append("card_family_binding_missing")
    if _binding_issue(metrics, expected_binding):
        issue_codes.append("card_family_binding_mismatch")

    if calibration_model is not None:
        raw_dimensions = metrics.get("dimensions")
        if not isinstance(raw_dimensions, Mapping) or not raw_dimensions:
            issue_codes.append("prompt_canvas_or_boolean_is_not_framing_proof")
            issue_codes.append("card_family_numeric_framing_missing")
        else:
            missing = [key for key in _REQUIRED_DIMENSIONS if key not in raw_dimensions]
            if missing:
                issue_codes.append("card_family_numeric_framing_missing")
            for key in _REQUIRED_DIMENSIONS:
                if key not in raw_dimensions:
                    continue
                value = _finite_unit_or_issue(raw_dimensions[key], key, issue_codes)
                if value is None:
                    continue
                dimensions[key] = value
                low, high = calibration_model.dimension_bands[key]
                if value < low or value > high:
                    issue_codes.append("card_family_numeric_framing_out_of_band")

    visible_evidence = metrics.get("visible_evidence")
    if not isinstance(visible_evidence, Mapping):
        issue_codes.append("card_family_visible_evidence_missing")
    else:
        for key in _REQUIRED_VISIBLE_EVIDENCE:
            if str(visible_evidence.get(key) or "") != "visible_reviewed":
                issue_codes.append("card_family_visible_evidence_missing")
                break

    if not issue_codes:
        evidence_codes = [
            "close_model_card_crop_verified",
            "shoulder_collar_context_visible",
            "not_identity_document_headshot",
            "not_half_body_portrait",
        ]

    status: CardFamilyFramingStatus = "fail" if issue_codes else "pass"
    return CardFamilyFramingProof(
        status=status,
        eligible=status == "pass",
        module=module or None,
        slot=slot,
        view_role=view_role or None,
        slot_scope=slot_scope or None,
        candidate_id=candidate_id,
        output_id=output_id,
        operation_id=operation_id,
        round_id=round_id,
        evidence_codes=evidence_codes,
        issue_codes=sorted(set(issue_codes)),
        dimensions=dimensions,
    )


def evaluate_card_family_round_consistency(
    candidates: Sequence[Mapping[str, object]],
    *,
    calibration: Mapping[str, object] | CardFamilyFramingCalibrationArtifact | None,
    operation_id: str,
    round_id: str,
) -> CardFamilyFramingProof:
    calibration_model, calibration_issues = _calibration_or_fail(calibration)
    issue_codes: list[str] = list(calibration_issues)
    dimensions: dict[str, float] = {}
    if len(candidates) != 3:
        issue_codes.append("card_family_round_requires_three_candidates")
    if not str(operation_id or "").strip() or not str(round_id or "").strip():
        issue_codes.append("card_family_round_binding_missing")
    proofs = [
        evaluate_card_family_framing(
            candidate,
            calibration=calibration,
            expected_binding={
                "candidate_id": candidate.get("candidate_id"),
                "output_id": candidate.get("output_id"),
                "operation_id": operation_id,
                "round_id": round_id,
            },
        )
        for candidate in candidates
    ]
    for proof in proofs:
        issue_codes.extend(proof.issue_codes)

    if calibration_model is not None:
        for key, limit in calibration_model.round_variance_limits.items():
            values: list[float] = []
            for candidate in candidates:
                raw_dimensions = candidate.get("dimensions")
                if not isinstance(raw_dimensions, Mapping) or key not in raw_dimensions:
                    issue_codes.append("card_family_round_dimension_missing")
                    continue
                value = _finite_unit_or_issue(raw_dimensions[key], key, issue_codes)
                if value is not None:
                    values.append(value)
            if len(values) != len(candidates):
                continue
            if not values:
                continue
            spread = max(values) - min(values)
            dimensions[f"{key}_spread"] = spread
            if spread > limit:
                issue_codes.append("card_family_round_scale_variance_exceeds_calibration")

    status: CardFamilyFramingStatus = "fail" if issue_codes else "pass"
    return CardFamilyFramingProof(
        status=status,
        eligible=status == "pass",
        evidence_codes=["card_family_round_consistency_verified"] if status == "pass" else [],
        issue_codes=sorted(set(issue_codes)),
        dimensions=dimensions,
    )
