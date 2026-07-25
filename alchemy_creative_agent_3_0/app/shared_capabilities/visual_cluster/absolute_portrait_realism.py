"""Hot-pluggable absolute portrait realism Enhanced proof.

Doc248 keeps this module outside Formal Core and outside Provider/MCP routing.
It evaluates structured, public-safe portrait realism evidence and can project
that evidence into the existing candidate-level Enhanced proof contract when a
professional portrait slot explicitly opts in.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ...schemas.models import V3BaseModel


ABSOLUTE_PORTRAIT_REALISM_OWNER = "v3_absolute_portrait_realism_enhanced_module"
ABSOLUTE_PORTRAIT_REALISM_CONTRACT_VERSION = "v3_absolute_portrait_realism_proof_v1"
ABSOLUTE_PORTRAIT_REALISM_PROFILE_ID = "absolute_portrait_realism_v1"
ABSOLUTE_PORTRAIT_REALISM_REQUIREMENT_ID = "absolute_portrait_realism_visible_evidence_v1"

AbsolutePortraitRealismStatus = Literal["pass", "fail"]

REQUIRED_REALISM_DIMENSIONS = (
    "eye_gaze_alignment",
    "facial_micro_asymmetry",
    "skin_micro_texture",
    "hair_strand_randomness",
    "ear_anatomy_clarity",
    "natural_light_transition",
    "camera_texture_response",
    "commercial_beauty_preserved",
)

FORBIDDEN_DEGRADATION_ISSUES = frozenset(
    {
        "resolution_degraded_for_realism",
        "compression_noise_used_as_realism",
        "random_grain_used_as_realism",
        "blur_used_as_realism",
        "dirty_skin_used_as_realism",
        "muddy_color_cast",
        "tired_or_unflattering_expression",
        "beauty_degraded_for_realism",
        "identity_geometry_redesigned",
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


class _StrictRealismModel(V3BaseModel):
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
        if score < 0.0 or score > 1.0:
            raise ValueError(f"{field_name} values must be in [0, 1]")
        normalized[key] = score
    return normalized


class AbsolutePortraitRealismProof(_StrictRealismModel):
    """Public-safe result of an explicit absolute portrait realism profile."""

    owner: Literal["v3_absolute_portrait_realism_enhanced_module"] = (
        ABSOLUTE_PORTRAIT_REALISM_OWNER
    )
    contract_version: Literal["v3_absolute_portrait_realism_proof_v1"] = (
        ABSOLUTE_PORTRAIT_REALISM_CONTRACT_VERSION
    )
    profile_id: Literal["absolute_portrait_realism_v1"] = ABSOLUTE_PORTRAIT_REALISM_PROFILE_ID
    requirement_id: Literal["absolute_portrait_realism_visible_evidence_v1"] = (
        ABSOLUTE_PORTRAIT_REALISM_REQUIREMENT_ID
    )
    candidate_id: str
    output_id: str
    status: AbsolutePortraitRealismStatus
    eligible: bool
    evidence_codes: list[str]
    issue_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float]
    required_dimensions: list[str] = Field(default_factory=lambda: list(REQUIRED_REALISM_DIMENSIONS))
    minimum_dimension_score: float = Field(default=0.72, ge=0.0, le=1.0)
    minimum_beauty_score: float = Field(default=0.78, ge=0.0, le=1.0)

    @field_validator("candidate_id", "output_id")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("candidate/output identity must be nonempty")
        return text

    @field_validator("evidence_codes", "issue_codes", "required_dimensions")
    @classmethod
    def validate_public_codes(cls, value: list[str]) -> list[str]:
        return _safe_code_list(value, "absolute portrait realism code")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return _normalized_scores(value, "absolute portrait realism dimensions")

    @model_validator(mode="after")
    def validate_proof(self) -> "AbsolutePortraitRealismProof":
        if not self.evidence_codes:
            raise ValueError("absolute portrait realism proof requires evidence codes")
        if not self.dimensions:
            raise ValueError("absolute portrait realism proof requires dimensions")
        if self.eligible != (self.status == "pass"):
            raise ValueError("absolute portrait realism eligibility must match pass status")
        missing = [name for name in self.required_dimensions if name not in self.dimensions]
        if self.status == "pass" and missing:
            raise ValueError("passing absolute portrait realism proof requires all dimensions")
        if self.status == "pass":
            low = [
                name
                for name in self.required_dimensions
                if self.dimensions.get(name, 0.0) < self.minimum_dimension_score
            ]
            if low:
                raise ValueError("passing absolute portrait realism proof has low dimensions")
            if self.dimensions.get("commercial_beauty_preserved", 0.0) < self.minimum_beauty_score:
                raise ValueError("passing absolute portrait realism proof must preserve beauty")
            if FORBIDDEN_DEGRADATION_ISSUES.intersection(self.issue_codes):
                raise ValueError("passing proof cannot contain realism degradation issue codes")
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


def evaluate_absolute_portrait_realism(
    *,
    candidate_id: str,
    output_id: str,
    dimensions: Mapping[str, float],
    evidence_codes: Sequence[str],
    issue_codes: Sequence[str] = (),
    minimum_dimension_score: float = 0.72,
    minimum_beauty_score: float = 0.78,
    required_dimensions: Sequence[str] = REQUIRED_REALISM_DIMENSIONS,
) -> AbsolutePortraitRealismProof:
    """Evaluate a structured absolute-realism evidence packet.

    Missing or weak evidence returns a fail proof instead of defaulting to pass.
    The caller can still keep the candidate as an append-only reviewed attempt.
    """

    normalized_dimensions = _normalized_scores(dimensions, "absolute portrait realism dimensions")
    normalized_issues = _safe_code_list(issue_codes, "absolute portrait realism issue")
    normalized_required = _safe_code_list(required_dimensions, "absolute portrait realism required dimension")
    normalized_evidence = _safe_code_list(evidence_codes, "absolute portrait realism evidence")
    missing = [name for name in normalized_required if name not in normalized_dimensions]
    low = [
        name
        for name in normalized_required
        if normalized_dimensions.get(name, 0.0) < float(minimum_dimension_score)
    ]
    beauty_low = normalized_dimensions.get("commercial_beauty_preserved", 0.0) < float(minimum_beauty_score)
    degradation = sorted(FORBIDDEN_DEGRADATION_ISSUES.intersection(normalized_issues))
    failure_issues = list(normalized_issues)
    if missing:
        failure_issues.append("absolute_portrait_realism_evidence_missing")
    if low:
        failure_issues.append("absolute_portrait_realism_dimension_below_target")
    if beauty_low:
        failure_issues.append("commercial_beauty_not_preserved")
    if degradation:
        failure_issues.append("realism_degradation_strategy_rejected")

    status: AbsolutePortraitRealismStatus = "fail" if failure_issues else "pass"
    return AbsolutePortraitRealismProof(
        candidate_id=candidate_id,
        output_id=output_id,
        status=status,
        eligible=status == "pass",
        evidence_codes=normalized_evidence or ["absolute_portrait_realism_reviewed"],
        issue_codes=sorted(set(failure_issues)),
        dimensions=normalized_dimensions,
        required_dimensions=list(normalized_required),
        minimum_dimension_score=minimum_dimension_score,
        minimum_beauty_score=minimum_beauty_score,
    )


def project_absolute_portrait_realism_enhanced_proof(
    proof: AbsolutePortraitRealismProof,
):
    """Project Doc248 proof into the module-neutral candidate Enhanced proof.

    The import is intentionally local so the Enhanced module can be inspected
    without pulling Formal Core or slot lifecycle code into its evaluation path.
    """

    from ...visual_assets.formal_slot_acceptance import FormalSlotCandidateEnhancedProofSummary

    return FormalSlotCandidateEnhancedProofSummary(
        profile_id=proof.profile_id,
        requirement_id=proof.requirement_id,
        candidate_id=proof.candidate_id,
        output_id=proof.output_id,
        eligible=proof.eligible,
        status=proof.status,
        evidence_codes=list(proof.evidence_codes),
        issue_codes=list(proof.issue_codes),
        dimensions=dict(proof.dimensions),
    )
