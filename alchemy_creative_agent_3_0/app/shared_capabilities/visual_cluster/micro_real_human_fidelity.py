"""Doc252 hot-pluggable micro real-human fidelity Enhanced proof.

This module is intentionally small and detached from production routing.  It
validates public-safe candidate evidence for close-inspection portrait realism
without importing Formal Core, Provider/MCP, route handlers, library, or slot
lifecycle code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ...schemas.models import V3BaseModel


MICRO_REAL_HUMAN_FIDELITY_OWNER = "v3_micro_real_human_fidelity_enhanced_module"
MICRO_REAL_HUMAN_FIDELITY_CONTRACT_VERSION = "v3_micro_real_human_fidelity_proof_v1"
MICRO_REAL_HUMAN_FIDELITY_PROFILE_ID = "micro_real_human_fidelity_v1"
MICRO_REAL_HUMAN_FIDELITY_REQUIREMENT_ID = "micro_real_human_visible_evidence_v1"
MICRO_REAL_HUMAN_FIDELITY_METADATA_FLAG = "micro_real_human_fidelity_required"
MICRO_REAL_HUMAN_FIDELITY_METADATA_PROVENANCE = "micro_real_human_fidelity_provenance"
MICRO_REAL_HUMAN_FIDELITY_TRUSTED_PROVENANCE = "server_feature_flag_v1"
APPROVED_MICRO_REAL_HUMAN_FIDELITY_SCOPES = frozenset(
    {
        "character_card_face_identity:standard_front",
    }
)

MicroRealHumanFidelityStatus = Literal["pass", "fail"]
MicroApplicability = Literal["applicable", "not_applicable"]
MicroVisibility = Literal[
    "visible_and_reviewable",
    "occluded",
    "outside_frame",
    "insufficient_resolution",
]
MicroDimensionStatus = Literal["pass", "fail", "not_applicable"]

REQUIRED_STANDARD_FRONT_MINIMUM_GROUP_DIMENSIONS = frozenset(
    {
        "non_mirrored_catchlights",
        "natural_eyelid_asymmetry",
        "gaze_axis_consistency",
        "sclera_micro_texture",
        "non_plastic_iris_detail",
        "strand_width_variation",
        "flyaway_baby_hair_evidence",
        "temple_hair_skin_integration",
        "non_uniform_hair_edge_silhouette",
        "pore_scale_texture",
        "cheek_tonal_variation",
        "nose_wing_shadow_naturalness",
        "non_ceramic_highlight_transition",
        "lip_chin_material_transition",
        "natural_microcontrast",
        "sensor_lens_response_plausibility",
        "highlight_rolloff_believability",
        "commercial_beauty_preserved",
        "clean_model_card_finish",
        "age_appropriate_attractiveness_preserved",
    }
)
OPTIONAL_VISIBLE_DIMENSIONS = frozenset(
    {
        "ear_cartilage_fold_clarity",
        "left_right_ear_nonidentity",
        "ear_hair_boundary_naturalness",
        "fabric_weave_irregularity",
        "collar_tension_plausibility",
        "seam_edge_nonuniformity",
    }
)
MINIMUM_MICRO_DIMENSION_SCORE = 0.78
MINIMUM_MICRO_BEAUTY_SCORE = 0.82

FORBIDDEN_DEGRADATION_ISSUES = frozenset(
    {
        "detector_evasion_requested",
        "random_noise_as_realism",
        "compression_damage_as_realism",
        "blur_as_realism",
        "beauty_degraded_for_realism",
        "identity_asymmetry_injected",
        "dirty_skin_used_as_realism",
    }
)

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


class _StrictMicroModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


def _safe_label(value: str, field_name: str) -> str:
    label = str(value or "").strip()
    if not label:
        raise ValueError(f"{field_name} must be nonempty")
    lowered = label.lower()
    if any(token in lowered for token in _SAFE_FORBIDDEN_TOKENS):
        raise ValueError(f"{field_name} is not public-safe")
    return label


def _safe_code_list(values: Sequence[str], field_name: str) -> list[str]:
    normalized = [_safe_label(value, field_name) for value in values]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must be unique")
    return normalized


def _normalized_scores(values: Mapping[str, float], field_name: str) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_score in values.items():
        key = _safe_label(str(raw_key), f"{field_name} key")
        score = float(raw_score)
        if not math.isfinite(score) or score < 0.0 or score > 1.0:
            raise ValueError(f"{field_name} values must be finite in [0, 1]")
        normalized[key] = score
    return normalized


class MicroDimensionApplicability(_StrictMicroModel):
    applicability: MicroApplicability
    visibility: MicroVisibility
    status: MicroDimensionStatus


class MicroRealHumanFidelityGuidance(_StrictMicroModel):
    enabled: bool
    mode: Literal["additive_guidance"]
    prompt_authority: Literal["existing_trusted_brain_host"]
    generation_channel: None = None
    retry_budget: None = None
    rewrites_user_prompt: Literal[False] = False
    scope: str

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, value: str) -> str:
        return _safe_label(value, "micro-realism scope")


class MicroRealHumanFidelityProof(_StrictMicroModel):
    owner: Literal["v3_micro_real_human_fidelity_enhanced_module"] = (
        MICRO_REAL_HUMAN_FIDELITY_OWNER
    )
    contract_version: Literal["v3_micro_real_human_fidelity_proof_v1"] = (
        MICRO_REAL_HUMAN_FIDELITY_CONTRACT_VERSION
    )
    profile_id: Literal["micro_real_human_fidelity_v1"] = MICRO_REAL_HUMAN_FIDELITY_PROFILE_ID
    requirement_id: Literal["micro_real_human_visible_evidence_v1"] = (
        MICRO_REAL_HUMAN_FIDELITY_REQUIREMENT_ID
    )
    candidate_id: str
    output_id: str
    status: MicroRealHumanFidelityStatus
    eligible: bool
    evidence_codes: list[str]
    issue_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float]
    applicability: dict[str, MicroDimensionApplicability]
    passed_dimensions: list[str]
    not_applicable_dimensions: list[str]

    @field_validator("candidate_id", "output_id")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("candidate/output identity must be nonempty")
        return text

    @field_validator("evidence_codes", "issue_codes", "passed_dimensions", "not_applicable_dimensions")
    @classmethod
    def validate_public_codes(cls, value: list[str]) -> list[str]:
        return _safe_code_list(value, "micro-realism code")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return _normalized_scores(value, "micro-realism dimensions")

    @model_validator(mode="after")
    def validate_proof(self) -> "MicroRealHumanFidelityProof":
        if not self.evidence_codes:
            raise ValueError("micro-realism proof requires evidence codes")
        if self.eligible != (self.status == "pass"):
            raise ValueError("micro-realism eligibility must match pass status")
        if self.status == "pass" and self.issue_codes:
            raise ValueError("passing micro-realism proof cannot contain issues")
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
            "passed_dimensions": list(self.passed_dimensions),
            "not_applicable_dimensions": list(self.not_applicable_dimensions),
        }


def micro_real_human_fidelity_enabled_from_metadata(metadata: Mapping[str, object]) -> bool:
    requested = metadata.get(MICRO_REAL_HUMAN_FIDELITY_METADATA_FLAG)
    if requested is not True:
        return False
    if str(metadata.get(MICRO_REAL_HUMAN_FIDELITY_METADATA_PROVENANCE) or "") != (
        MICRO_REAL_HUMAN_FIDELITY_TRUSTED_PROVENANCE
    ):
        raise ValueError("trusted_host_required")
    return True


def build_micro_real_human_fidelity_guidance(
    *,
    enabled: bool,
    enabled_by: str,
    scope: str,
) -> MicroRealHumanFidelityGuidance:
    if enabled and enabled_by != MICRO_REAL_HUMAN_FIDELITY_TRUSTED_PROVENANCE:
        raise ValueError("trusted_host_required")
    if scope not in APPROVED_MICRO_REAL_HUMAN_FIDELITY_SCOPES:
        raise ValueError("micro_real_human_fidelity_scope_not_approved")
    return MicroRealHumanFidelityGuidance(
        enabled=enabled,
        mode="additive_guidance",
        prompt_authority="existing_trusted_brain_host",
        scope=scope,
    )


def _as_public_string_list(values: object, field_name: str) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ValueError(f"{field_name} must be a list")
    return [_safe_label(str(item), field_name) for item in values]


def append_micro_real_human_fidelity_guidance(
    prompt_contract: Mapping[str, object],
    *,
    metadata: Mapping[str, object],
    scope: str,
) -> dict[str, object]:
    """Return an additive Doc252 prompt contract projection.

    This helper does not authorize Doc252 by itself.  It only appends guidance
    when server-owned metadata explicitly enables the profile.  It preserves the
    existing prompt author and never adds transport, retry, age, identity, or
    reference-ownership changes.
    """

    enabled = micro_real_human_fidelity_enabled_from_metadata(metadata)
    projected = dict(prompt_contract)
    if not enabled:
        return projected

    existing_author = str(
        projected.get("prompt_authority")
        or projected.get("creative_direction_owner")
        or ""
    ).strip()
    if not existing_author:
        raise ValueError("existing_prompt_author_required")
    guidance = build_micro_real_human_fidelity_guidance(
        enabled=True,
        enabled_by=MICRO_REAL_HUMAN_FIDELITY_TRUSTED_PROVENANCE,
        scope=scope,
    )

    positive = _as_public_string_list(projected.get("visual_direction_addons"), "visual direction addon")
    negative = _as_public_string_list(projected.get("negative_prompt_addons"), "negative prompt addon")
    positive.extend(
        [
            "real photographed skin eye hair ear cloth camera micro evidence",
            "subtle human non mechanical texture while preserving polished commercial beauty",
        ]
    )
    negative.extend(
        [
            "no detector evasion noise blur dirt compression damage or beauty degradation",
            "no identity redesign or artificial asymmetry injection",
        ]
    )
    projected["visual_direction_addons"] = list(dict.fromkeys(positive))
    projected["negative_prompt_addons"] = list(dict.fromkeys(negative))
    projected["micro_real_human_fidelity_guidance"] = {
        "profile_id": MICRO_REAL_HUMAN_FIDELITY_PROFILE_ID,
        "requirement_id": MICRO_REAL_HUMAN_FIDELITY_REQUIREMENT_ID,
        "enabled": guidance.enabled,
        "mode": guidance.mode,
        "prompt_authority": existing_author,
        "scope": guidance.scope,
        "provenance": MICRO_REAL_HUMAN_FIDELITY_TRUSTED_PROVENANCE,
    }
    return projected


def evaluate_micro_real_human_fidelity(
    *,
    candidate_id: str,
    output_id: str,
    dimensions: Mapping[str, float],
    applicability: Mapping[str, Mapping[str, str] | MicroDimensionApplicability],
    evidence_codes: Sequence[str],
    issue_codes: Sequence[str] = (),
    enabled_by: str,
    minimum_dimension_score: float = MINIMUM_MICRO_DIMENSION_SCORE,
    minimum_beauty_score: float = MINIMUM_MICRO_BEAUTY_SCORE,
) -> MicroRealHumanFidelityProof:
    if enabled_by != MICRO_REAL_HUMAN_FIDELITY_TRUSTED_PROVENANCE:
        raise ValueError("trusted_host_required")
    dimension_floor = float(minimum_dimension_score)
    beauty_floor = float(minimum_beauty_score)
    if not math.isfinite(dimension_floor):
        raise ValueError("micro_realism_dimension_floor_must_be_finite")
    if not math.isfinite(beauty_floor):
        raise ValueError("micro_realism_beauty_floor_must_be_finite")
    if dimension_floor < MINIMUM_MICRO_DIMENSION_SCORE:
        raise ValueError("micro_realism_dimension_floor_cannot_be_lowered")
    if beauty_floor < MINIMUM_MICRO_BEAUTY_SCORE:
        raise ValueError("micro_realism_beauty_floor_cannot_be_lowered")

    normalized_dimensions = _normalized_scores(dimensions, "micro-realism dimensions")
    normalized_evidence = _safe_code_list(evidence_codes, "micro-realism evidence")
    normalized_issues = _safe_code_list(issue_codes, "micro-realism issue")
    applicability_map = {
        _safe_label(str(name), "micro-realism applicability dimension"): (
            value if isinstance(value, MicroDimensionApplicability) else MicroDimensionApplicability.model_validate(value)
        )
        for name, value in applicability.items()
    }

    failure_issues = list(normalized_issues)
    passed: list[str] = []
    not_applicable: list[str] = []

    required_dimensions = set(REQUIRED_STANDARD_FRONT_MINIMUM_GROUP_DIMENSIONS)
    expected_dimensions = required_dimensions | set(OPTIONAL_VISIBLE_DIMENSIONS)
    for dimension in sorted(expected_dimensions | set(applicability_map)):
        receipt = applicability_map.get(dimension)
        if receipt is None:
            failure_issues.append("micro_real_human_applicability_missing")
            continue
        if receipt.visibility == "visible_and_reviewable" and receipt.applicability == "not_applicable":
            failure_issues.append("visible_region_marked_not_applicable")
            continue
        if receipt.applicability == "applicable" and receipt.status == "not_applicable":
            failure_issues.append("applicable_dimension_marked_not_applicable")
            continue
        if receipt.applicability == "not_applicable" and receipt.status != "not_applicable":
            failure_issues.append("not_applicable_dimension_requires_not_applicable_status")
            continue
        if receipt.applicability == "not_applicable":
            not_applicable.append(dimension)
            continue
        if dimension not in normalized_dimensions:
            failure_issues.append("micro_real_human_visible_evidence_missing")
            continue
        if normalized_dimensions[dimension] < dimension_floor or receipt.status != "pass":
            failure_issues.append("micro_real_human_dimension_below_target")
            continue
        passed.append(dimension)

    beauty_dimensions = (
        "commercial_beauty_preserved",
        "clean_model_card_finish",
        "age_appropriate_attractiveness_preserved",
    )
    if any(normalized_dimensions.get(dimension, 0.0) < beauty_floor for dimension in beauty_dimensions):
        failure_issues.append("commercial_beauty_not_preserved")
    if FORBIDDEN_DEGRADATION_ISSUES.intersection(normalized_issues):
        failure_issues.append("micro_realism_degradation_strategy_rejected")

    unique_issues = sorted(set(failure_issues))
    status: MicroRealHumanFidelityStatus = "fail" if unique_issues else "pass"
    return MicroRealHumanFidelityProof(
        candidate_id=candidate_id,
        output_id=output_id,
        status=status,
        eligible=status == "pass",
        evidence_codes=normalized_evidence,
        issue_codes=unique_issues,
        dimensions=normalized_dimensions,
        applicability=applicability_map,
        passed_dimensions=passed,
        not_applicable_dimensions=not_applicable,
    )
