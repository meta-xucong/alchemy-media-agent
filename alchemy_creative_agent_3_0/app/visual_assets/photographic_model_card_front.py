"""Doc256 Face-local photographic model-card front Enhanced contract.

This module binds neutral card-family framing evidence and shared Human Realism
foundation evidence into one Face ``standard_front`` candidate eligibility
summary.  It does not own generic realism evaluation and does not import Formal
Core, Provider/MCP, route handlers, or slot lifecycle code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from ..shared_capabilities.visual_cluster.card_family_framing import (
    CARD_FAMILY_FRAMING_CONTRACT_VERSION,
    CARD_FAMILY_FRAMING_OWNER,
    CARD_FAMILY_FRAMING_PROFILE_ID,
    CARD_FAMILY_FRAMING_REQUIREMENT_ID,
)


PHOTOGRAPHIC_MODEL_CARD_FRONT_OWNER = "face_photographic_model_card_front_profile"
PHOTOGRAPHIC_MODEL_CARD_FRONT_CONTRACT_VERSION = (
    "v3_face_photographic_model_card_front_profile_v1"
)
PHOTOGRAPHIC_MODEL_CARD_FRONT_PROFILE_ID = "photographic_model_card_front_v1"
PHOTOGRAPHIC_MODEL_CARD_FRONT_REQUIREMENT_ID = (
    "photographic_model_card_front_enhanced_eligibility_v1"
)

PhotographicModelCardFrontStatus = Literal["pass", "fail"]

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
_LEGACY_PROFILE_IDS = frozenset(
    {
        "absolute_portrait_realism_v1",
        "micro_real_human_fidelity_v1",
    }
)
_SHARED_HUMAN_REALISM_OWNER = "shared_human_realism_foundation"
_SHARED_HUMAN_REALISM_PROFILE_ID = "human_realism_v3_shared"
_SHARED_HUMAN_VISIBILITY_OWNER = "shared_human_realism_visibility"
_REQUIRED_VISIBILITY_DIMENSIONS = frozenset(
    {
        "eyes",
        "skin",
        "hair",
        "ear_or_temple",
        "garment_neckline",
        "light_camera",
    }
)


class _StrictPhotographicFrontModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


def _safe_label(value: object, field_name: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field_name} must be nonempty")
    lowered = label.lower()
    if any(token in lowered for token in _SAFE_FORBIDDEN_TOKENS):
        raise ValueError(f"{field_name} is not public-safe")
    return label


def _safe_code_list(values: Sequence[str], field_name: str) -> list[str]:
    normalized: list[str] = []
    for value in values:
        label = str(value or "").strip()
        if not label:
            raise ValueError(f"{field_name} must be nonempty")
        normalized.append(label)
    return list(dict.fromkeys(normalized))


def _safe_dimensions(values: Mapping[str, object]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_score in values.items():
        try:
            key = _safe_label(raw_key, "photographic front dimension")
            score = float(raw_score)
        except (TypeError, ValueError):
            continue
        if 0.0 <= score <= 1.0:
            normalized[key] = score
    return normalized


def _public_safe_codes(values: Sequence[str]) -> list[str]:
    safe: list[str] = []
    for value in values:
        lowered = value.lower()
        if any(token in lowered for token in _SAFE_FORBIDDEN_TOKENS):
            continue
        safe.append(value)
    return safe


class PhotographicModelCardFrontProof(_StrictPhotographicFrontModel):
    owner: Literal["face_photographic_model_card_front_profile"] = (
        PHOTOGRAPHIC_MODEL_CARD_FRONT_OWNER
    )
    contract_version: Literal["v3_face_photographic_model_card_front_profile_v1"] = (
        PHOTOGRAPHIC_MODEL_CARD_FRONT_CONTRACT_VERSION
    )
    profile_id: Literal["photographic_model_card_front_v1"] = (
        PHOTOGRAPHIC_MODEL_CARD_FRONT_PROFILE_ID
    )
    requirement_id: Literal["photographic_model_card_front_enhanced_eligibility_v1"] = (
        PHOTOGRAPHIC_MODEL_CARD_FRONT_REQUIREMENT_ID
    )
    status: PhotographicModelCardFrontStatus
    eligible: bool
    candidate_id: str | None = None
    output_id: str | None = None
    operation_id: str | None = None
    round_id: str | None = None
    compatibility_read_only: bool = False
    evidence_codes: list[str] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)

    @field_validator("candidate_id", "output_id", "operation_id", "round_id")
    @classmethod
    def validate_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _safe_label(value, "photographic front identity")

    @field_validator("evidence_codes", "issue_codes")
    @classmethod
    def validate_codes(cls, value: list[str]) -> list[str]:
        return _safe_code_list(value, "photographic front code")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return _safe_dimensions(value)

    @model_validator(mode="after")
    def validate_status(self) -> "PhotographicModelCardFrontProof":
        if self.eligible != (self.status == "pass"):
            raise ValueError("photographic front eligibility must match pass status")
        if self.status == "pass" and not self.evidence_codes:
            raise ValueError("passing photographic front proof requires evidence")
        return self

    def public_summary(self) -> dict[str, object]:
        return {
            "owner": self.owner,
            "contract_version": self.contract_version,
            "profile_id": self.profile_id,
            "requirement_id": self.requirement_id,
            "eligible": self.eligible,
            "status": self.status,
            "compatibility_read_only": self.compatibility_read_only,
            "evidence_codes": _public_safe_codes(self.evidence_codes),
            "issue_codes": _public_safe_codes(self.issue_codes),
            "dimensions": dict(self.dimensions),
        }


def _payload_status(payload: Mapping[str, object] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("status") or "").strip()


def _payload_codes(payload: Mapping[str, object] | None, key: str) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    value = payload.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [str(item) for item in value]


def _payload_dimensions(payload: Mapping[str, object] | None) -> dict[str, float]:
    if not isinstance(payload, Mapping):
        return {}
    value = payload.get("dimensions")
    if not isinstance(value, Mapping):
        return {}
    return _safe_dimensions(value)


def _binding_mismatch(
    payload: Mapping[str, object] | None,
    *,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
) -> bool:
    if not isinstance(payload, Mapping):
        return False
    for key, expected in (
        ("candidate_id", candidate_id),
        ("output_id", output_id),
        ("operation_id", operation_id),
        ("round_id", round_id),
    ):
        actual = payload.get(key)
        if actual is not None and str(actual) != expected:
            return True
    return False


def _binding_missing_or_mismatch(
    payload: Mapping[str, object] | None,
    *,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
) -> bool:
    if not isinstance(payload, Mapping):
        return True
    for key, expected in (
        ("candidate_id", candidate_id),
        ("output_id", output_id),
        ("operation_id", operation_id),
        ("round_id", round_id),
    ):
        if str(payload.get(key) or "") != expected:
            return True
    return False


def _visibility_complete(shared_human_visibility: Mapping[str, object] | None) -> bool:
    if not isinstance(shared_human_visibility, Mapping):
        return False
    applicability = shared_human_visibility.get("applicability_receipts")
    if not isinstance(applicability, Mapping):
        return False
    return all(str(applicability.get(key) or "") == "visible_reviewed" for key in _REQUIRED_VISIBILITY_DIMENSIONS)


def evaluate_photographic_model_card_front_candidate(
    *,
    module: str,
    view_role: str,
    slot_scope: str,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
    card_family_framing: Mapping[str, object] | None,
    shared_human_realism: Mapping[str, object] | None,
    shared_human_visibility: Mapping[str, object] | None,
) -> PhotographicModelCardFrontProof:
    issue_codes: list[str] = []
    evidence_codes: list[str] = []
    dimensions: dict[str, float] = {}

    if module != "face_identity" or view_role != "standard_front" or slot_scope != "formal_slot":
        issue_codes.append("photographic_model_card_front_scope_invalid")

    if not isinstance(card_family_framing, Mapping):
        issue_codes.append("card_family_framing_proof_missing")
    else:
        if card_family_framing.get("owner") != CARD_FAMILY_FRAMING_OWNER:
            issue_codes.append("card_family_framing_owner_invalid")
        if card_family_framing.get("contract_version") != CARD_FAMILY_FRAMING_CONTRACT_VERSION:
            issue_codes.append("card_family_framing_contract_invalid")
        if card_family_framing.get("profile_id") != CARD_FAMILY_FRAMING_PROFILE_ID:
            issue_codes.append("card_family_framing_profile_invalid")
        if card_family_framing.get("requirement_id") != CARD_FAMILY_FRAMING_REQUIREMENT_ID:
            issue_codes.append("card_family_framing_requirement_invalid")
        if _binding_missing_or_mismatch(
            card_family_framing,
            candidate_id=candidate_id,
            output_id=output_id,
            operation_id=operation_id,
            round_id=round_id,
        ):
            issue_codes.append("candidate_binding_mismatch")
        if _payload_status(card_family_framing) != "pass":
            issue_codes.append("card_family_framing_failed")
            codes = set(_payload_codes(card_family_framing, "evidence_codes"))
            if "identity_document_headshot_crop_detected" in codes:
                issue_codes.append("identity_document_headshot_crop_rejected")
                issue_codes.append("human_realism_pass_cannot_compensate_wrong_framing")
            if "half_body_portrait_crop_detected" in codes:
                issue_codes.append("half_body_crop_rejected_for_close_model_card_front")
        else:
            evidence_codes.append("card_family_framing_profile_passed")
            dimensions.update(_payload_dimensions(card_family_framing))

    if not isinstance(shared_human_realism, Mapping):
        issue_codes.append("shared_human_realism_proof_missing")
    else:
        if shared_human_realism.get("owner") != _SHARED_HUMAN_REALISM_OWNER:
            issue_codes.append("shared_human_realism_owner_invalid")
        if shared_human_realism.get("profile_id") != _SHARED_HUMAN_REALISM_PROFILE_ID:
            issue_codes.append("shared_human_realism_profile_invalid")
        if _binding_missing_or_mismatch(
            shared_human_realism,
            candidate_id=candidate_id,
            output_id=output_id,
            operation_id=operation_id,
            round_id=round_id,
        ):
            issue_codes.append("shared_human_realism_binding_mismatch")
        profile_id = str(shared_human_realism.get("profile_id") or "")
        realism_codes = set(_payload_codes(shared_human_realism, "evidence_codes"))
        if (
            profile_id in {PHOTOGRAPHIC_MODEL_CARD_FRONT_PROFILE_ID, *_LEGACY_PROFILE_IDS}
            or realism_codes
            & {
            "absolute_portrait_realism_profile_passed",
            "micro_real_human_fidelity_profile_passed",
            }
        ):
            issue_codes.append("legacy_profile_mixed_with_doc256_profile")
        if _payload_status(shared_human_realism) != "pass":
            issue_codes.append("shared_human_realism_failed")
        if "commercial_beauty_degraded_by_realism_treatment" in realism_codes:
            issue_codes.append("commercial_beauty_degraded")
        realism_dimensions = _payload_dimensions(shared_human_realism)
        if realism_dimensions.get("commercial_beauty", 1.0) < 0.82:
            issue_codes.append("commercial_beauty_degraded")
        if not issue_codes or "shared_human_realism_failed" not in issue_codes:
            evidence_codes.append("shared_human_realism_profile_passed")
        dimensions.update(realism_dimensions)

    if not isinstance(shared_human_visibility, Mapping):
        issue_codes.append("shared_human_visibility_evidence_missing")
        issue_codes.append("face_adapter_must_not_synthesize_shared_visibility")
    elif shared_human_visibility.get("owner") != _SHARED_HUMAN_VISIBILITY_OWNER:
        issue_codes.append("shared_human_visibility_owner_invalid")
    elif _binding_missing_or_mismatch(
        shared_human_visibility,
        candidate_id=candidate_id,
        output_id=output_id,
        operation_id=operation_id,
        round_id=round_id,
    ):
        issue_codes.append("shared_human_visibility_binding_mismatch")
    elif not _visibility_complete(shared_human_visibility):
        issue_codes.append("shared_human_visibility_evidence_missing")
    else:
        evidence_codes.append("shared_human_visibility_profile_passed")

    status: PhotographicModelCardFrontStatus = "fail" if issue_codes else "pass"
    if status == "pass":
        evidence_codes.append("photographic_model_card_front_profile_passed")

    return PhotographicModelCardFrontProof(
        status=status,
        eligible=status == "pass",
        candidate_id=candidate_id,
        output_id=output_id,
        operation_id=operation_id,
        round_id=round_id,
        evidence_codes=list(dict.fromkeys(evidence_codes)),
        issue_codes=sorted(set(issue_codes)),
        dimensions=dimensions,
    )


def project_legacy_profile_for_doc256_compatibility(
    payload: Mapping[str, object],
) -> PhotographicModelCardFrontProof:
    profile_id = str(payload.get("profile_id") or "")
    issue_codes = ["legacy_profile_not_doc256_completion"]
    if profile_id not in _LEGACY_PROFILE_IDS:
        issue_codes.append("legacy_profile_unknown")
    return PhotographicModelCardFrontProof(
        status="fail",
        eligible=False,
        candidate_id=str(payload.get("candidate_id") or "") or None,
        output_id=str(payload.get("output_id") or "") or None,
        compatibility_read_only=True,
        evidence_codes=[],
        issue_codes=issue_codes,
        dimensions={},
    )
