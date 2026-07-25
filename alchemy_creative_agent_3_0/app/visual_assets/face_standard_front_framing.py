"""Doc253 Face standard-front framing Enhanced contract.

This module is deliberately detached from Formal Core and transport routing. It
describes and validates the Face-owned standard-front framing proof using an
explicit calibration artifact supplied by the caller.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel


STANDARD_FRONT_FRAMING_OWNER = "face_standard_front_framing_profile"
STANDARD_FRONT_FRAMING_CONTRACT_VERSION = "v3_face_standard_front_framing_envelope_v1"
STANDARD_FRONT_FRAMING_PROFILE_ID = "standard_front_framing_envelope_v1"
STANDARD_FRONT_FRAMING_REQUIREMENT_ID = "standard_front_numeric_framing_envelope_v1"

FramingStatus = Literal["pass", "fail"]

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


class _StrictFramingModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


def _safe_label(value: str, field_name: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field_name} must be nonempty")
    lowered = label.lower()
    if any(token in lowered for token in _SAFE_FORBIDDEN_TOKENS):
        raise ValueError(f"{field_name} is not public-safe")
    return label


def _finite_unit(value: object, field_name: str) -> float:
    score = float(value)
    if not math.isfinite(score) or score < 0.0 or score > 1.0:
        raise ValueError(f"{field_name} must be finite in [0, 1]")
    return score


def _band(value: Sequence[float], field_name: str) -> tuple[float, float]:
    if len(value) != 2:
        raise ValueError(f"{field_name} requires two values")
    low = _finite_unit(value[0], field_name)
    high = _finite_unit(value[1], field_name)
    if low > high:
        raise ValueError(f"{field_name} lower bound must not exceed upper bound")
    return (low, high)


class StandardFrontFramingCalibrationArtifact(_StrictFramingModel):
    artifact_id: str
    provenance: Literal["server_owned_calibration_v1"]
    approval_status: Literal["approved"]
    source_fixture_set: str
    measurement_method: str
    face_box_width_band: tuple[float, float]
    face_box_height_band: tuple[float, float]
    face_center_x_band: tuple[float, float]
    face_center_y_band: tuple[float, float]
    round_variance_limits: dict[str, float]
    applies_to: Literal["face.standard_front.formal_slot"]
    version: str

    @field_validator("artifact_id", "source_fixture_set", "measurement_method", "version")
    @classmethod
    def validate_labels(cls, value: str) -> str:
        return _safe_label(value, "framing calibration label")

    @model_validator(mode="after")
    def validate_server_owned_approved_artifact(self) -> "StandardFrontFramingCalibrationArtifact":
        if self.artifact_id != "standard_front_framing_envelope_calibration_v1":
            raise ValueError("standard_front_framing_calibration_artifact_not_approved")
        return self

    @field_validator(
        "face_box_width_band",
        "face_box_height_band",
        "face_center_x_band",
        "face_center_y_band",
        mode="before",
    )
    @classmethod
    def validate_band(cls, value: Sequence[float]) -> tuple[float, float]:
        return _band(value, "framing calibration band")

    @field_validator("round_variance_limits")
    @classmethod
    def validate_variance_limits(cls, value: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for key, raw_limit in value.items():
            label = _safe_label(str(key), "framing variance dimension")
            limit = _finite_unit(raw_limit, "framing variance limit")
            normalized[label] = limit
        return normalized


class StandardFrontFramingProof(_StrictFramingModel):
    owner: Literal["face_standard_front_framing_profile"] = STANDARD_FRONT_FRAMING_OWNER
    contract_version: Literal["v3_face_standard_front_framing_envelope_v1"] = (
        STANDARD_FRONT_FRAMING_CONTRACT_VERSION
    )
    profile_id: Literal["standard_front_framing_envelope_v1"] = STANDARD_FRONT_FRAMING_PROFILE_ID
    requirement_id: Literal["standard_front_numeric_framing_envelope_v1"] = (
        STANDARD_FRONT_FRAMING_REQUIREMENT_ID
    )
    candidate_id: str | None = None
    output_id: str | None = None
    status: FramingStatus
    eligible: bool
    evidence_codes: list[str] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)

    @field_validator("candidate_id", "output_id")
    @classmethod
    def validate_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _safe_label(value, "framing candidate identity")

    @field_validator("evidence_codes", "issue_codes")
    @classmethod
    def validate_codes(cls, value: list[str]) -> list[str]:
        normalized = [_safe_label(item, "framing code") for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("framing codes must be unique")
        return normalized

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return {_safe_label(key, "framing dimension"): _finite_unit(score, "framing dimension") for key, score in value.items()}

    @model_validator(mode="after")
    def validate_status(self) -> "StandardFrontFramingProof":
        if self.eligible != (self.status == "pass"):
            raise ValueError("framing eligibility must match pass status")
        if self.status == "pass" and not self.evidence_codes:
            raise ValueError("passing framing proof requires evidence codes")
        return self

    def public_summary(self) -> dict[str, object]:
        return {
            "owner": self.owner,
            "contract_version": self.contract_version,
            "profile_id": self.profile_id,
            "requirement_id": self.requirement_id,
            "eligible": self.eligible,
            "status": self.status,
            "evidence_codes": list(self.evidence_codes),
            "issue_codes": list(self.issue_codes),
            "dimensions": dict(self.dimensions),
        }


def standard_front_framing_envelope_applies(*, module: str, view_role: str, slot_scope: str) -> bool:
    return module == "face_identity" and view_role == "standard_front" and slot_scope == "formal_slot"


def _value_in_band(value: float, band: tuple[float, float]) -> bool:
    return band[0] <= value <= band[1]


def evaluate_standard_front_framing_envelope(
    metrics: Mapping[str, object],
    *,
    calibration: StandardFrontFramingCalibrationArtifact | None,
) -> StandardFrontFramingProof:
    if calibration is None:
        raise ValueError("standard_front_framing_calibration_required")

    candidate_id = str(metrics.get("candidate_id") or "").strip() or None
    output_id = str(metrics.get("output_id") or "").strip() or None
    issue_codes: list[str] = []
    evidence_codes: list[str] = []

    if not standard_front_framing_envelope_applies(
        module=str(metrics.get("module") or "face_identity"),
        view_role=str(metrics.get("view_role") or ""),
        slot_scope=str(metrics.get("slot_scope") or ""),
    ):
        issue_codes.append("standard_front_framing_scope_invalid")
    if str(metrics.get("shared_review_status") or "") != "pass":
        issue_codes.append("standard_front_shared_review_not_pass")
    if not candidate_id:
        issue_codes.append("standard_front_candidate_identity_missing")
    if not output_id:
        issue_codes.append("standard_front_output_identity_missing")

    required = {
        "face_box_width_ratio": calibration.face_box_width_band,
        "face_box_height_ratio": calibration.face_box_height_band,
        "face_center_x": calibration.face_center_x_band,
        "face_center_y": calibration.face_center_y_band,
    }
    dimensions: dict[str, float] = {}

    if metrics.get("transport_canvas_size") and not any(key in metrics for key in required):
        issue_codes.append("transport_canvas_is_not_framing_evidence")

    missing = [key for key in required if key not in metrics]
    if missing:
        issue_codes.append("standard_front_numeric_framing_missing")
    else:
        for key, band in required.items():
            dimensions[key] = _finite_unit(metrics[key], key)
            if not _value_in_band(dimensions[key], band):
                issue_codes.append("standard_front_numeric_framing_out_of_band")

    for optional_key in ("eye_line_y", "head_top_margin", "shoulder_visibility_ratio"):
        if optional_key in metrics:
            dimensions[optional_key] = _finite_unit(metrics[optional_key], optional_key)

    if not issue_codes:
        evidence_codes.append("standard_front_numeric_framing_envelope_verified")
    status: FramingStatus = "fail" if issue_codes else "pass"
    return StandardFrontFramingProof(
        candidate_id=candidate_id,
        output_id=output_id,
        status=status,
        eligible=status == "pass",
        evidence_codes=evidence_codes,
        issue_codes=sorted(set(issue_codes)),
        dimensions=dimensions,
    )


def evaluate_standard_front_round_framing_consistency(
    candidates: Sequence[Mapping[str, object]],
    *,
    calibration: StandardFrontFramingCalibrationArtifact | None,
) -> StandardFrontFramingProof:
    if calibration is None:
        raise ValueError("standard_front_framing_calibration_required")

    per_candidate = [
        evaluate_standard_front_framing_envelope(candidate, calibration=calibration)
        for candidate in candidates
    ]
    issue_codes: list[str] = []
    dimensions: dict[str, float] = {}
    for proof in per_candidate:
        issue_codes.extend(proof.issue_codes)

    for key, limit in calibration.round_variance_limits.items():
        values = [
            _finite_unit(candidate[key], key)
            for candidate in candidates
            if key in candidate
        ]
        if len(values) != len(candidates):
            issue_codes.append("round_framing_dimension_missing")
            continue
        spread = max(values) - min(values)
        dimensions[f"{key}_spread"] = spread
        if spread > limit:
            issue_codes.append("round_face_box_variance_exceeds_calibration")

    status: FramingStatus = "fail" if issue_codes else "pass"
    return StandardFrontFramingProof(
        status=status,
        eligible=status == "pass",
        evidence_codes=["standard_front_round_framing_consistency_verified"] if status == "pass" else [],
        issue_codes=sorted(set(issue_codes)),
        dimensions=dimensions,
    )
