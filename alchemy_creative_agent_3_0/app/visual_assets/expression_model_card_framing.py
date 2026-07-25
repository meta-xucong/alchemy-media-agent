"""Doc256 Expression model-card framing adapter.

Expression delivery slots consume neutral card-family framing evidence and
Expression-owned affect proof.  They do not import Face-local photographic
front code and do not create winner, receipt, activation, or target-only
authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from ..shared_capabilities.visual_cluster import card_family_framing as card_family_framing_contract


EXPRESSION_MODEL_CARD_OWNER = "expression_model_card_delivery_profile"
EXPRESSION_MODEL_CARD_CONTRACT_VERSION = "v3_expression_model_card_delivery_v1"
EXPRESSION_MODEL_CARD_PROFILE_ID = "expression_model_card_delivery_v1"
EXPRESSION_MODEL_CARD_REQUIREMENT_ID = "expression_model_card_framing_and_affect_v1"

ExpressionModelCardStatus = Literal["pass", "fail"]

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
_EXPRESSION_DELIVERY_SLOTS = frozenset(
    {"expression.anger", "expression.sad", "expression.laugh"}
)


class _StrictExpressionModelCardModel(V3BaseModel):
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
    normalized: list[str] = []
    for value in values:
        label = str(value or "").strip()
        if not label:
            raise ValueError(f"{field_name} must be nonempty")
        normalized.append(label)
    return list(dict.fromkeys(normalized))


def _safe_dimensions(value: Mapping[str, object]) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_score in value.items():
        try:
            key = _safe_label(raw_key, "expression model-card dimension")
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


class ExpressionModelCardEnhancedSummary(_StrictExpressionModelCardModel):
    owner: Literal["expression_model_card_delivery_profile"] = EXPRESSION_MODEL_CARD_OWNER
    contract_version: Literal["v3_expression_model_card_delivery_v1"] = (
        EXPRESSION_MODEL_CARD_CONTRACT_VERSION
    )
    profile_id: Literal["expression_model_card_delivery_v1"] = EXPRESSION_MODEL_CARD_PROFILE_ID
    requirement_id: Literal["expression_model_card_framing_and_affect_v1"] = (
        EXPRESSION_MODEL_CARD_REQUIREMENT_ID
    )
    summary_kind: Literal["module_neutral_enhanced_eligibility"] = (
        "module_neutral_enhanced_eligibility"
    )
    status: ExpressionModelCardStatus
    eligible: bool
    module: Literal["expression_set"] = "expression_set"
    slot: str | None = None
    candidate_id: str | None = None
    output_id: str | None = None
    operation_id: str | None = None
    round_id: str | None = None
    compatibility_read_only: bool = False
    evidence_codes: list[str] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)

    @field_validator("slot", "candidate_id", "output_id", "operation_id", "round_id")
    @classmethod
    def validate_optional_labels(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _safe_label(value, "expression model-card identity")

    @field_validator("evidence_codes", "issue_codes")
    @classmethod
    def validate_codes(cls, value: list[str]) -> list[str]:
        return _safe_codes(value, "expression model-card code")

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return _safe_dimensions(value)

    @model_validator(mode="after")
    def validate_status(self) -> "ExpressionModelCardEnhancedSummary":
        if self.eligible != (self.status == "pass"):
            raise ValueError("expression model-card eligibility must match pass status")
        if self.status == "pass" and not self.evidence_codes:
            raise ValueError("passing expression model-card proof requires evidence")
        return self

    def public_summary(self) -> dict[str, object]:
        return {
            "owner": self.owner,
            "contract_version": self.contract_version,
            "profile_id": self.profile_id,
            "requirement_id": self.requirement_id,
            "summary_kind": self.summary_kind,
            "eligible": self.eligible,
            "status": self.status,
            "compatibility_read_only": self.compatibility_read_only,
            "evidence_codes": _public_safe_codes(self.evidence_codes),
            "issue_codes": _public_safe_codes(self.issue_codes),
            "dimensions": dict(self.dimensions),
        }


def _status(payload: Mapping[str, object] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    return str(payload.get("status") or "").strip()


def _codes(payload: Mapping[str, object] | None, key: str) -> list[str]:
    if not isinstance(payload, Mapping):
        return []
    values = payload.get(key)
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        return []
    return [str(value) for value in values]


def _dimensions(payload: Mapping[str, object] | None) -> dict[str, float]:
    if not isinstance(payload, Mapping):
        return {}
    values = payload.get("dimensions")
    if not isinstance(values, Mapping):
        return {}
    return _safe_dimensions(values)


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


def compose_expression_model_card_enhanced_summary(
    *,
    module: str,
    slot: str,
    candidate_id: str,
    output_id: str,
    operation_id: str,
    round_id: str,
    card_family_framing: Mapping[str, object] | None,
    affect_proof: Mapping[str, object] | None,
) -> ExpressionModelCardEnhancedSummary:
    issue_codes: list[str] = []
    evidence_codes: list[str] = []
    dimensions: dict[str, float] = {}

    if module != "expression_set" or slot not in _EXPRESSION_DELIVERY_SLOTS:
        issue_codes.append("expression_model_card_scope_invalid")
    if not isinstance(card_family_framing, Mapping):
        issue_codes.append("card_family_framing_proof_missing")
    else:
        if card_family_framing.get("owner") != card_family_framing_contract.CARD_FAMILY_FRAMING_OWNER:
            issue_codes.append("card_family_framing_owner_invalid")
        if (
            card_family_framing.get("contract_version")
            != card_family_framing_contract.CARD_FAMILY_FRAMING_CONTRACT_VERSION
        ):
            issue_codes.append("card_family_framing_contract_invalid")
        if card_family_framing.get("profile_id") != card_family_framing_contract.CARD_FAMILY_FRAMING_PROFILE_ID:
            issue_codes.append("card_family_framing_profile_invalid")
        if (
            card_family_framing.get("requirement_id")
            != card_family_framing_contract.CARD_FAMILY_FRAMING_REQUIREMENT_ID
        ):
            issue_codes.append("card_family_framing_requirement_invalid")
        if not card_family_framing_contract.card_family_framing_applies(
            module=str(card_family_framing.get("module") or ""),
            view_role=str(card_family_framing.get("view_role") or ""),
            slot_scope=str(card_family_framing.get("slot_scope") or ""),
            slot=str(card_family_framing.get("slot") or ""),
        ):
            issue_codes.append("card_family_framing_scope_invalid")
        if _binding_missing_or_mismatch(
            card_family_framing,
            candidate_id=candidate_id,
            output_id=output_id,
            operation_id=operation_id,
            round_id=round_id,
        ):
            issue_codes.append("expression_card_family_binding_mismatch")
        if _status(card_family_framing) != "pass":
            issue_codes.append("card_family_framing_failed")
            if _status(affect_proof) == "pass":
                issue_codes.append("affect_pass_cannot_compensate_framing_fail")
        else:
            evidence_codes.append("card_family_framing_profile_passed")
            dimensions.update(_dimensions(card_family_framing))

    if not isinstance(affect_proof, Mapping):
        issue_codes.append("expression_affect_profile_missing")
    else:
        if affect_proof.get("owner") != "expression_affect_profile":
            issue_codes.append("expression_affect_owner_invalid")
        if affect_proof.get("profile_id") != f"{slot}_affect_v1":
            issue_codes.append("expression_affect_profile_invalid")
        if _binding_missing_or_mismatch(
            affect_proof,
            candidate_id=candidate_id,
            output_id=output_id,
            operation_id=operation_id,
            round_id=round_id,
        ):
            issue_codes.append("expression_affect_binding_mismatch")
        if _status(affect_proof) != "pass":
            issue_codes.append("expression_affect_profile_failed")
            if _status(card_family_framing) == "pass":
                issue_codes.append("framing_pass_cannot_compensate_affect_fail")
        else:
            evidence_codes.append("expression_affect_profile_passed")
            dimensions.update(_dimensions(affect_proof))

    status: ExpressionModelCardStatus = "fail" if issue_codes else "pass"
    return ExpressionModelCardEnhancedSummary(
        status=status,
        eligible=status == "pass",
        slot=slot,
        candidate_id=candidate_id,
        output_id=output_id,
        operation_id=operation_id,
        round_id=round_id,
        evidence_codes=list(dict.fromkeys(evidence_codes)),
        issue_codes=sorted(set(issue_codes)),
        dimensions=dimensions,
    )


def project_legacy_expression_receipt_for_doc256_compatibility(
    payload: Mapping[str, object],
) -> ExpressionModelCardEnhancedSummary:
    issue_codes = ["legacy_target_only_not_doc256_completion"]
    if str(payload.get("acceptance_mode") or "") != "target_only_existing_candidate_collection":
        issue_codes.append("legacy_expression_receipt_not_doc256_profile")
    return ExpressionModelCardEnhancedSummary(
        status="fail",
        eligible=False,
        slot=str(payload.get("slot") or "") or None,
        output_id=str(payload.get("winner_output_id") or "") or None,
        compatibility_read_only=True,
        evidence_codes=[],
        issue_codes=issue_codes,
        dimensions={},
    )
