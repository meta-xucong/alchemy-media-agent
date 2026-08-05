"""Closed three-view Body Silhouette review receipt.

This module owns the final joint review proof for a reference-assisted Body
refresh.  Single-image candidate review can prove one view is acceptable; it
cannot prove that front, side, and rear belong to one coherent person.  The
receipt here is deliberately public-safe: it binds output ids and source
digests, but never stores paths, image bytes, raw provider responses, prompts,
or biometric vectors.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Literal

from pydantic import ConfigDict, Field, StrictBool, StrictStr, field_validator, model_validator

from ..schemas.models import V3BaseModel


BODY_CROSS_VIEW_REVIEW_CONTRACT_VERSION = "professional_body_cross_view_review_receipt_v1"
BODY_CROSS_VIEW_REVIEW_OWNER = "v3_shared_vision_body_cross_view"
BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE = "body_cross_view_real_pixel_review_verified"

BODY_CROSS_VIEW_SLOT_KEYS = ("body.front_full", "body.side_full", "body.rear_full")
BODY_CROSS_VIEW_DIMENSIONS = (
    "age_stage_consistency",
    "head_body_scale_consistency",
    "body_chain_consistency",
    "front_side_rear_volume_consistency",
    "garment_consistency",
    "backdrop_consistency",
    "hair_continuity",
    "single_person_synthesis",
)

BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES = {
    "age_stage_consistency": "body_cross_view_age_stage_consistent",
    "head_body_scale_consistency": "body_cross_view_head_body_scale_consistent",
    "body_chain_consistency": "body_cross_view_body_chain_consistent",
    "front_side_rear_volume_consistency": "body_cross_view_volume_consistent",
    "garment_consistency": "body_cross_view_garment_consistent",
    "backdrop_consistency": "body_cross_view_backdrop_consistent",
    "hair_continuity": "body_cross_view_hair_continuity_verified",
    "single_person_synthesis": "body_cross_view_single_person_synthesis_verified",
}

BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES = (
    "body_cross_view_review_unavailable",
    "body_cross_view_review_not_pixel_backed",
    "age_stage_drift_between_views",
    "head_body_scale_conflict_between_views",
    "body_chain_conflict_between_views",
    "front_side_rear_body_volume_conflict",
    "front_side_rear_stature_ratio_conflict",
    "view_specific_limb_length_drift",
    "view_specific_body_maturity_drift",
    "same_body_envelope_conflict_between_views",
    "front_face_body_integration_artifact",
    "garment_drift_between_views",
    "backdrop_not_consistent_pure_white",
    "hair_continuity_conflict_between_views",
    "multi_person_or_head_body_composite_detected",
)

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_ATTEMPT_RE = re.compile(r"^body_refresh_attempt_[0-9a-f]{32}$")


class BodyCrossViewReviewReceipt(V3BaseModel):
    """Typed proof that the three selected Body views were jointly inspected."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["professional_body_cross_view_review_receipt_v1"] = (
        BODY_CROSS_VIEW_REVIEW_CONTRACT_VERSION
    )
    owner: Literal["v3_shared_vision_body_cross_view"] = BODY_CROSS_VIEW_REVIEW_OWNER
    attempt_id: StrictStr
    source_evidence_id_digest: StrictStr
    view_output_ids: dict[
        Literal["body.front_full", "body.side_full", "body.rear_full"],
        StrictStr,
    ]
    status: Literal["pass", "fail"]
    dimensions: dict[
        Literal[
            "age_stage_consistency",
            "head_body_scale_consistency",
            "body_chain_consistency",
            "front_side_rear_volume_consistency",
            "garment_consistency",
            "backdrop_consistency",
            "hair_continuity",
            "single_person_synthesis",
        ],
        Literal["pass", "fail", "unknown"],
    ]
    evidence_codes: tuple[StrictStr, ...] = ()
    issue_codes: tuple[StrictStr, ...] = ()
    real_pixel_review_verified: StrictBool = False
    activation_eligible: StrictBool = False
    receipt_digest: StrictStr

    @field_validator("attempt_id")
    @classmethod
    def validate_attempt_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not _ATTEMPT_RE.fullmatch(cleaned):
            raise ValueError("body_cross_view_attempt_id_invalid")
        return cleaned

    @field_validator("source_evidence_id_digest", "receipt_digest")
    @classmethod
    def validate_digest(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if not _DIGEST_RE.fullmatch(cleaned):
            raise ValueError("body_cross_view_digest_invalid")
        return cleaned

    @field_validator("evidence_codes", "issue_codes", mode="before")
    @classmethod
    def normalize_codes(cls, value: Any) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, (list, tuple)):
            raise ValueError("body_cross_view_codes_must_be_list")
        cleaned = tuple(str(item).strip() for item in value if str(item).strip())
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("body_cross_view_codes_must_be_unique")
        for item in cleaned:
            if not re.fullmatch(r"[a-z0-9_]{3,96}", item):
                raise ValueError("body_cross_view_code_invalid")
        return cleaned

    @model_validator(mode="after")
    def validate_receipt(self) -> "BodyCrossViewReviewReceipt":
        if set(self.view_output_ids) != set(BODY_CROSS_VIEW_SLOT_KEYS):
            raise ValueError("body_cross_view_outputs_incomplete")
        if len(set(self.view_output_ids.values())) != len(BODY_CROSS_VIEW_SLOT_KEYS):
            raise ValueError("body_cross_view_outputs_must_be_unique")
        for output_id in self.view_output_ids.values():
            if not output_id.strip() or "/" in output_id or "\\" in output_id:
                raise ValueError("body_cross_view_output_id_invalid")
        if set(self.dimensions) != set(BODY_CROSS_VIEW_DIMENSIONS):
            raise ValueError("body_cross_view_dimensions_incomplete")
        evidence = set(self.evidence_codes)
        required_evidence = {
            BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
            *BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES.values(),
        }
        all_dimensions_pass = all(
            self.dimensions[dimension] == "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS
        )
        expected_eligible = (
            self.status == "pass"
            and self.real_pixel_review_verified is True
            and all_dimensions_pass
            and not self.issue_codes
            and required_evidence.issubset(evidence)
        )
        if self.activation_eligible is not expected_eligible:
            raise ValueError("body_cross_view_activation_eligibility_invalid")
        if self.status == "pass" and not expected_eligible:
            raise ValueError("body_cross_view_pass_receipt_incomplete")
        if self.status == "fail" and not self.issue_codes:
            raise ValueError("body_cross_view_failed_receipt_requires_issue")
        if any(code not in BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES for code in self.issue_codes):
            raise ValueError("body_cross_view_issue_code_invalid")
        expected_digest = _receipt_digest(self.canonical_payload(include_digest=False))
        if self.receipt_digest != expected_digest:
            raise ValueError("body_cross_view_receipt_digest_mismatch")
        return self

    def canonical_payload(self, *, include_digest: bool = True) -> dict[str, Any]:
        payload = {
            "contract_version": self.contract_version,
            "owner": self.owner,
            "attempt_id": self.attempt_id,
            "source_evidence_id_digest": self.source_evidence_id_digest,
            "view_output_ids": {
                slot_key: self.view_output_ids[slot_key] for slot_key in BODY_CROSS_VIEW_SLOT_KEYS
            },
            "status": self.status,
            "dimensions": {
                dimension: self.dimensions[dimension] for dimension in BODY_CROSS_VIEW_DIMENSIONS
            },
            "evidence_codes": list(self.evidence_codes),
            "issue_codes": list(self.issue_codes),
            "real_pixel_review_verified": self.real_pixel_review_verified,
            "activation_eligible": self.activation_eligible,
        }
        if include_digest:
            payload["receipt_digest"] = self.receipt_digest
        return payload

    def require_binding(
        self,
        *,
        attempt_id: str,
        source_evidence_id_digest: str,
        view_output_ids: dict[str, str],
    ) -> "BodyCrossViewReviewReceipt":
        expected_outputs = {slot_key: view_output_ids.get(slot_key, "") for slot_key in BODY_CROSS_VIEW_SLOT_KEYS}
        if (
            self.attempt_id != attempt_id
            or self.source_evidence_id_digest != source_evidence_id_digest.lower()
            or dict(self.view_output_ids) != expected_outputs
        ):
            raise ValueError("body_cross_view_receipt_binding_mismatch")
        return self


def build_body_cross_view_review_receipt(
    *,
    attempt_id: str,
    source_evidence_id_digest: str,
    view_output_ids: dict[str, str],
    status: Literal["pass", "fail"],
    dimensions: dict[str, str],
    evidence_codes: list[str] | tuple[str, ...] | None = None,
    issue_codes: list[str] | tuple[str, ...] | None = None,
    real_pixel_review_verified: bool | None = None,
) -> BodyCrossViewReviewReceipt:
    """Build a closed receipt and compute its deterministic digest."""

    cleaned_dimensions = {
        dimension: str(dimensions.get(dimension, "unknown") or "unknown")
        for dimension in BODY_CROSS_VIEW_DIMENSIONS
    }
    cleaned_evidence = tuple(str(code).strip() for code in (evidence_codes or []) if str(code).strip())
    cleaned_issues = tuple(str(code).strip() for code in (issue_codes or []) if str(code).strip())
    pixel_verified = (
        BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE in cleaned_evidence
        if real_pixel_review_verified is None
        else bool(real_pixel_review_verified)
    )
    activation_eligible = (
        status == "pass"
        and pixel_verified
        and not cleaned_issues
        and all(cleaned_dimensions[dimension] == "pass" for dimension in BODY_CROSS_VIEW_DIMENSIONS)
        and {
            BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE,
            *BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES.values(),
        }.issubset(set(cleaned_evidence))
    )
    payload = {
        "contract_version": BODY_CROSS_VIEW_REVIEW_CONTRACT_VERSION,
        "owner": BODY_CROSS_VIEW_REVIEW_OWNER,
        "attempt_id": attempt_id,
        "source_evidence_id_digest": str(source_evidence_id_digest).strip().lower(),
        "view_output_ids": {
            slot_key: str(view_output_ids.get(slot_key, "") or "").strip()
            for slot_key in BODY_CROSS_VIEW_SLOT_KEYS
        },
        "status": status,
        "dimensions": cleaned_dimensions,
        "evidence_codes": list(cleaned_evidence),
        "issue_codes": list(cleaned_issues),
        "real_pixel_review_verified": pixel_verified,
        "activation_eligible": activation_eligible,
    }
    payload["receipt_digest"] = _receipt_digest(payload)
    return BodyCrossViewReviewReceipt.model_validate(payload)


def build_body_cross_view_unavailable_receipt(
    *,
    attempt_id: str,
    source_evidence_id_digest: str,
    view_output_ids: dict[str, str],
) -> BodyCrossViewReviewReceipt:
    return build_body_cross_view_review_receipt(
        attempt_id=attempt_id,
        source_evidence_id_digest=source_evidence_id_digest,
        view_output_ids=view_output_ids,
        status="fail",
        dimensions={dimension: "unknown" for dimension in BODY_CROSS_VIEW_DIMENSIONS},
        evidence_codes=(),
        issue_codes=("body_cross_view_review_unavailable",),
        real_pixel_review_verified=False,
    )


def _receipt_digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "BODY_CROSS_VIEW_BLOCKING_ISSUE_CODES",
    "BODY_CROSS_VIEW_DIMENSION_EVIDENCE_CODES",
    "BODY_CROSS_VIEW_DIMENSIONS",
    "BODY_CROSS_VIEW_PIXEL_EVIDENCE_CODE",
    "BODY_CROSS_VIEW_REVIEW_CONTRACT_VERSION",
    "BODY_CROSS_VIEW_REVIEW_OWNER",
    "BODY_CROSS_VIEW_SLOT_KEYS",
    "BodyCrossViewReviewReceipt",
    "build_body_cross_view_review_receipt",
    "build_body_cross_view_unavailable_receipt",
]
