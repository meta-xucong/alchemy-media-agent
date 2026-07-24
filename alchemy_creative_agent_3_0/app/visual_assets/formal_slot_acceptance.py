"""Module-neutral formal slot acceptance contracts for Professional assets.

Doc240 separates the official slot-completion contract from profile-specific
quality rules and auxiliary MCP/recovery mechanics.  This module intentionally
does not import Face Identity, Expression Set, Body, Provider, MCP, or route
code.  It only validates safe, durable facts that any formal Professional slot
must prove before it can be treated as standard completion.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any, Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel


FORMAL_SLOT_RECEIPT_VERSION = "v3_formal_slot_acceptance_receipt_v1"
FORMAL_SLOT_RECEIPT_OWNER = "v3_professional_formal_slot_acceptance_core"
FORMAL_SLOT_SHARED_REVIEW_OWNER = "v3_shared_visual_cluster"
FORMAL_SLOT_SHARED_REVIEW_CONTRACT_VERSION = "v3_character_card_generic_slot_review_receipt_v1"

FormalSlotAcceptanceMode = Literal[
    "standard_three_candidate",
    "target_only_existing_candidate_collection",
    "auxiliary_first_pass_reference",
]
FormalSlotArtifactScope = Literal["formal_slot", "auxiliary_reference"]
FormalSlotReviewStatus = Literal[
    "pass",
    "verified",
    "fail",
    "fail_retryable",
    "manual_review",
    "blocked",
    "unverified",
]
FormalSlotRequirementStatus = Literal["pass", "fail", "missing", "not_applicable"]

STANDARD_THREE_CANDIDATE_COUNT = 3
SAFE_PUBLIC_FORBIDDEN_TOKENS = (
    "prompt",
    "raw",
    "provider_response",
    "api_key",
    "secret",
    "token",
    "file_path",
    "path",
    "artifact",
    "handoff",
)
_PASSING_REVIEW_STATUSES = frozenset({"pass", "verified"})
_PASSING_REQUIREMENT_STATUSES = frozenset({"pass"})


class _StrictFormalSlotModel(V3BaseModel):
    """Shared strict base for public-safe formal-slot contract objects."""

    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
    )


def _require_nonempty_text(value: str, field_name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} must be nonempty")
    return normalized


def _require_safe_public_label(value: str, field_name: str) -> str:
    normalized = _require_nonempty_text(value, field_name)
    lowered = normalized.lower()
    if any(token in lowered for token in SAFE_PUBLIC_FORBIDDEN_TOKENS):
        raise ValueError(f"{field_name} is not public-safe")
    return normalized


def _validate_public_score_dimensions(value: dict[str, float], field_name: str) -> dict[str, float]:
    normalized: dict[str, float] = {}
    for raw_key, raw_score in value.items():
        key = _require_safe_public_label(str(raw_key), f"{field_name} key")
        score = float(raw_score)
        if score < 0.0 or score > 1.0:
            raise ValueError(f"{field_name} values must be in [0, 1]")
        normalized[key] = score
    return normalized


def _validate_public_dimension_names(value: list[str], field_name: str) -> list[str]:
    normalized = [_require_safe_public_label(item, field_name) for item in value]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must be unique")
    return normalized


class FormalSlotSharedReviewSummary(_StrictFormalSlotModel):
    """Public-safe summary of a shared Vision/review decision.

    This summary can represent passing or rejected candidate reviews.  Formal
    completion only requires the winner to have a passing summary; rejected
    candidates still count as reviewed attempts when their summary is present.
    """

    owner: Literal["v3_shared_visual_cluster"] = FORMAL_SLOT_SHARED_REVIEW_OWNER
    contract_version: Literal["v3_character_card_generic_slot_review_receipt_v1"] = (
        FORMAL_SLOT_SHARED_REVIEW_CONTRACT_VERSION
    )
    status: FormalSlotReviewStatus
    evidence_codes: list[str] = Field(default_factory=list)
    issue_codes: list[str] = Field(default_factory=list)
    score_dimensions: list[str] = Field(default_factory=list)
    framing_delta_dimensions: list[str] = Field(default_factory=list)

    @field_validator("evidence_codes", "issue_codes")
    @classmethod
    def validate_public_codes(cls, value: list[str]) -> list[str]:
        normalized = [_require_safe_public_label(item, "review code") for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("review codes must be unique")
        return normalized

    @field_validator("score_dimensions", "framing_delta_dimensions")
    @classmethod
    def validate_dimensions(cls, value: list[str]) -> list[str]:
        return _validate_public_dimension_names(value, "review dimensions")

    @model_validator(mode="after")
    def require_passing_evidence(self) -> "FormalSlotSharedReviewSummary":
        if self.passed:
            if not self.evidence_codes:
                raise ValueError("passing shared review requires evidence codes")
            if not self.score_dimensions:
                raise ValueError("passing shared review requires score dimensions")
        return self

    @property
    def passed(self) -> bool:
        return self.status in _PASSING_REVIEW_STATUSES


class FormalSlotRequirementSummary(_StrictFormalSlotModel):
    """Public-safe winner requirement summary supplied by a profile/reviewer."""

    status: FormalSlotRequirementStatus
    evidence_codes: list[str] = Field(default_factory=list)
    dimensions: dict[str, float] = Field(default_factory=dict)

    @field_validator("evidence_codes")
    @classmethod
    def validate_public_codes(cls, value: list[str]) -> list[str]:
        normalized = [_require_safe_public_label(item, "requirement evidence code") for item in value]
        if len(normalized) != len(set(normalized)):
            raise ValueError("requirement evidence codes must be unique")
        return normalized

    @field_validator("dimensions")
    @classmethod
    def validate_dimensions(cls, value: dict[str, float]) -> dict[str, float]:
        return _validate_public_score_dimensions(value, "requirement dimensions")

    @model_validator(mode="after")
    def require_passing_evidence(self) -> "FormalSlotRequirementSummary":
        if self.passed:
            if not self.evidence_codes:
                raise ValueError("passing requirement summary requires evidence codes")
            if not self.dimensions:
                raise ValueError("passing requirement summary requires dimensions")
        return self

    @property
    def passed(self) -> bool:
        return self.status in _PASSING_REQUIREMENT_STATUSES


class FormalSlotCandidateSummary(_StrictFormalSlotModel):
    """A reviewed candidate attempt for a formal slot or auxiliary collection."""

    candidate_index: int = Field(ge=1)
    candidate_id: str
    output_id: str
    reviewed: bool = True
    selected_as_winner: bool = False
    shared_review: FormalSlotSharedReviewSummary

    @field_validator("candidate_id", "output_id")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        return _require_nonempty_text(value, "candidate/output identity")

    @model_validator(mode="after")
    def require_reviewed_attempt(self) -> "FormalSlotCandidateSummary":
        if not self.reviewed:
            raise ValueError("candidate summary must represent a real reviewed attempt")
        return self


FormalSlotRankingKey = Callable[[FormalSlotCandidateSummary], Any]


class FormalSlotReceipt(_StrictFormalSlotModel):
    """Durable, public-safe receipt for Professional slot acceptance modes."""

    owner: Literal["v3_professional_formal_slot_acceptance_core"] = FORMAL_SLOT_RECEIPT_OWNER
    receipt_version: Literal["v3_formal_slot_acceptance_receipt_v1"] = FORMAL_SLOT_RECEIPT_VERSION
    module: str
    slot_key: str
    acceptance_mode: FormalSlotAcceptanceMode
    slot_scope: FormalSlotArtifactScope = "formal_slot"
    reviewed_candidate_count: int = Field(ge=1)
    candidates: list[FormalSlotCandidateSummary] = Field(min_length=1)
    winner_candidate_id: str | None = None
    winner_output_id: str | None = None
    winner_shared_review: FormalSlotSharedReviewSummary | None = None
    framing_summary: FormalSlotRequirementSummary
    parity_summary: FormalSlotRequirementSummary
    identity_summary: FormalSlotRequirementSummary
    retry_count: int = Field(default=0, ge=0)
    repair_count: int = Field(default=0, ge=0)
    reload_public_projection_verified: bool = False

    @field_validator("module", "slot_key")
    @classmethod
    def validate_scope_text(cls, value: str) -> str:
        return _require_nonempty_text(value, "formal slot scope")

    @field_validator("winner_candidate_id", "winner_output_id")
    @classmethod
    def validate_optional_winner_identity(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _require_nonempty_text(value, "winner identity")

    @model_validator(mode="after")
    def validate_receipt_contract(self) -> "FormalSlotReceipt":
        if self.reviewed_candidate_count != len(self.candidates):
            raise ValueError("reviewed_candidate_count must equal the real candidate summary count")
        candidate_ids = [candidate.candidate_id for candidate in self.candidates]
        output_ids = [candidate.output_id for candidate in self.candidates]
        indexes = [candidate.candidate_index for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("candidate IDs must be unique")
        if len(output_ids) != len(set(output_ids)):
            raise ValueError("candidate output IDs must be unique")
        if len(indexes) != len(set(indexes)):
            raise ValueError("candidate indexes must be unique")

        selected = [candidate for candidate in self.candidates if candidate.selected_as_winner]
        if self.acceptance_mode == "standard_three_candidate":
            self._validate_standard_three_candidate(selected)
        elif self.acceptance_mode == "target_only_existing_candidate_collection":
            self._validate_target_only_collection(selected)
        elif self.acceptance_mode == "auxiliary_first_pass_reference":
            self._validate_auxiliary_bridge(selected)
        else:  # pragma: no cover - exhaustive guard for future literals
            raise ValueError(f"unsupported acceptance mode: {self.acceptance_mode}")
        return self

    def _validate_winner(self, selected: list[FormalSlotCandidateSummary]) -> FormalSlotCandidateSummary:
        if len(selected) != 1:
            raise ValueError("receipt requires exactly one selected winner/target candidate")
        winner = selected[0]
        if self.winner_candidate_id != winner.candidate_id or self.winner_output_id != winner.output_id:
            raise ValueError("winner fields must match the selected candidate")
        if self.winner_shared_review is None:
            raise ValueError("winner shared review summary is required")
        if self.winner_shared_review.model_dump(mode="json") != winner.shared_review.model_dump(mode="json"):
            raise ValueError("winner shared review summary must match the selected candidate review")
        return winner

    def _validate_standard_three_candidate(self, selected: list[FormalSlotCandidateSummary]) -> None:
        if self.slot_scope != "formal_slot":
            raise ValueError("standard_three_candidate requires formal_slot slot scope")
        if self.reviewed_candidate_count != STANDARD_THREE_CANDIDATE_COUNT:
            raise ValueError("standard_three_candidate requires exactly three reviewed candidates")
        if [candidate.candidate_index for candidate in sorted(self.candidates, key=lambda item: item.candidate_index)] != [
            1,
            2,
            3,
        ]:
            raise ValueError("standard_three_candidate requires candidate indexes 1, 2, and 3")
        winner = self._validate_winner(selected)
        self._validate_success_proof("standard_three_candidate", winner)

    def _validate_target_only_collection(self, selected: list[FormalSlotCandidateSummary]) -> None:
        if self.slot_scope != "formal_slot":
            raise ValueError("target-only collection references a formal slot target")
        if self.reviewed_candidate_count != 1 or len(self.candidates) != 1:
            raise ValueError("target-only collection requires exactly one reviewed target")
        if self.candidates[0].candidate_index != 1:
            raise ValueError("target-only collection requires candidate index 1")
        winner = self._validate_winner(selected)
        self._validate_success_proof("target-only collection", winner)

    def _validate_auxiliary_bridge(self, selected: list[FormalSlotCandidateSummary]) -> None:
        if self.slot_scope != "auxiliary_reference":
            raise ValueError("auxiliary_first_pass_reference must use auxiliary_reference scope")
        if self.reviewed_candidate_count != 1 or len(self.candidates) != 1:
            raise ValueError("auxiliary_first_pass_reference requires exactly one reviewed bridge target")
        if self.candidates[0].candidate_index != 1:
            raise ValueError("auxiliary_first_pass_reference requires candidate index 1")
        winner = self._validate_winner(selected)
        self._validate_success_proof("auxiliary_first_pass_reference", winner)

    def _validate_success_proof(self, mode_label: str, winner: FormalSlotCandidateSummary) -> None:
        if not winner.shared_review.passed:
            raise ValueError(f"{mode_label} winner requires passing shared review")
        if not self.framing_summary.passed:
            raise ValueError(f"{mode_label} requires passing framing summary")
        if not self.parity_summary.passed:
            raise ValueError(f"{mode_label} requires passing parity summary")
        if not self.identity_summary.passed:
            raise ValueError(f"{mode_label} requires passing identity summary")
        if not self.reload_public_projection_verified:
            raise ValueError(f"{mode_label} requires reload/public projection verification")

    @property
    def formal_completion_verified(self) -> bool:
        return (
            self.acceptance_mode == "standard_three_candidate"
            and self.slot_scope == "formal_slot"
            and self.reviewed_candidate_count == STANDARD_THREE_CANDIDATE_COUNT
            and self.winner_shared_review is not None
            and self.winner_shared_review.passed
            and self.framing_summary.passed
            and self.parity_summary.passed
            and self.identity_summary.passed
            and self.reload_public_projection_verified
        )

    @property
    def activation_eligible(self) -> bool:
        """Only standard three-candidate receipts can activate formal slots."""

        return self.formal_completion_verified

    def public_summary(self) -> "FormalSlotPublicSummary":
        return FormalSlotPublicSummary.from_receipt(self)


class FormalSlotPublicSummary(_StrictFormalSlotModel):
    """Safe UI/public projection for a formal slot receipt."""

    owner: Literal["v3_professional_formal_slot_acceptance_core"]
    receipt_version: Literal["v3_formal_slot_acceptance_receipt_v1"]
    module: str
    slot_key: str
    acceptance_mode: FormalSlotAcceptanceMode
    slot_scope: FormalSlotArtifactScope
    formal_completion_verified: bool
    activation_eligible: bool
    reviewed_candidate_count: int
    winner_output_id: str | None
    candidate_output_ids: list[str]
    generic_vision_status: FormalSlotReviewStatus | None
    framing_status: FormalSlotRequirementStatus
    parity_status: FormalSlotRequirementStatus
    identity_status: FormalSlotRequirementStatus
    retry_count: int
    repair_count: int

    @classmethod
    def from_receipt(cls, receipt: FormalSlotReceipt) -> "FormalSlotPublicSummary":
        return cls(
            owner=receipt.owner,
            receipt_version=receipt.receipt_version,
            module=receipt.module,
            slot_key=receipt.slot_key,
            acceptance_mode=receipt.acceptance_mode,
            slot_scope=receipt.slot_scope,
            formal_completion_verified=receipt.formal_completion_verified,
            activation_eligible=receipt.activation_eligible,
            reviewed_candidate_count=receipt.reviewed_candidate_count,
            winner_output_id=receipt.winner_output_id,
            candidate_output_ids=[candidate.output_id for candidate in receipt.candidates],
            generic_vision_status=receipt.winner_shared_review.status
            if receipt.winner_shared_review is not None
            else None,
            framing_status=receipt.framing_summary.status,
            parity_status=receipt.parity_summary.status,
            identity_status=receipt.identity_summary.status,
            retry_count=receipt.retry_count,
            repair_count=receipt.repair_count,
        )


class FormalSlotAcceptanceCore:
    """Module-neutral candidate-to-winner formal slot acceptance core.

    The core accepts already-reviewed candidate summaries plus externally
    supplied requirement summaries.  It has no knowledge of module names,
    view roles, emotion profiles, execution adapters, or recovery mechanics.
    """

    def accept(
        self,
        *,
        module: str,
        slot_key: str,
        acceptance_mode: FormalSlotAcceptanceMode,
        candidates: Iterable[FormalSlotCandidateSummary | dict[str, object]],
        framing_summary: FormalSlotRequirementSummary | dict[str, object],
        parity_summary: FormalSlotRequirementSummary | dict[str, object],
        identity_summary: FormalSlotRequirementSummary | dict[str, object],
        ranking_key: FormalSlotRankingKey | None = None,
        retry_count: int = 0,
        repair_count: int = 0,
        reload_public_projection_verified: bool = True,
    ) -> FormalSlotReceipt:
        """Build and validate a formal-slot receipt without module branches."""

        reviewed_candidates = self._coerce_candidates(candidates)
        selected = self._select_winner(
            acceptance_mode=acceptance_mode,
            candidates=reviewed_candidates,
            ranking_key=ranking_key,
        )
        candidate_receipts = [
            candidate.model_copy(update={"selected_as_winner": candidate.candidate_id == selected.candidate_id})
            for candidate in reviewed_candidates
        ]
        return FormalSlotReceipt(
            module=module,
            slot_key=slot_key,
            acceptance_mode=acceptance_mode,
            slot_scope=self._slot_scope_for_mode(acceptance_mode),
            reviewed_candidate_count=len(candidate_receipts),
            candidates=candidate_receipts,
            winner_candidate_id=selected.candidate_id,
            winner_output_id=selected.output_id,
            winner_shared_review=selected.shared_review,
            framing_summary=self._coerce_requirement_summary(framing_summary),
            parity_summary=self._coerce_requirement_summary(parity_summary),
            identity_summary=self._coerce_requirement_summary(identity_summary),
            retry_count=retry_count,
            repair_count=repair_count,
            reload_public_projection_verified=reload_public_projection_verified,
        )

    def _coerce_candidates(
        self,
        candidates: Iterable[FormalSlotCandidateSummary | dict[str, object]],
    ) -> list[FormalSlotCandidateSummary]:
        reviewed_candidates = [
            candidate
            if isinstance(candidate, FormalSlotCandidateSummary)
            else FormalSlotCandidateSummary.model_validate(candidate)
            for candidate in candidates
        ]
        if not reviewed_candidates:
            raise ValueError("formal slot acceptance requires reviewed candidates")
        return reviewed_candidates

    def _coerce_requirement_summary(
        self,
        summary: FormalSlotRequirementSummary | dict[str, object],
    ) -> FormalSlotRequirementSummary:
        return summary if isinstance(summary, FormalSlotRequirementSummary) else FormalSlotRequirementSummary.model_validate(summary)

    def _select_winner(
        self,
        *,
        acceptance_mode: FormalSlotAcceptanceMode,
        candidates: list[FormalSlotCandidateSummary],
        ranking_key: FormalSlotRankingKey | None,
    ) -> FormalSlotCandidateSummary:
        if acceptance_mode == "standard_three_candidate":
            return self._select_standard_winner(candidates=candidates, ranking_key=ranking_key)
        if acceptance_mode in {
            "target_only_existing_candidate_collection",
            "auxiliary_first_pass_reference",
        }:
            if len(candidates) != 1:
                raise ValueError(f"{acceptance_mode} requires exactly one reviewed target")
            return candidates[0]
        raise ValueError(f"unsupported acceptance mode: {acceptance_mode}")

    def _select_standard_winner(
        self,
        *,
        candidates: list[FormalSlotCandidateSummary],
        ranking_key: FormalSlotRankingKey | None,
    ) -> FormalSlotCandidateSummary:
        if len(candidates) != STANDARD_THREE_CANDIDATE_COUNT:
            raise ValueError("standard_three_candidate requires exactly three reviewed candidates")
        eligible = [candidate for candidate in candidates if candidate.shared_review.passed]
        if not eligible:
            raise ValueError("standard_three_candidate requires at least one passing reviewed candidate")
        if ranking_key is None:
            return min(eligible, key=lambda candidate: candidate.candidate_index)
        return max(eligible, key=lambda candidate: (ranking_key(candidate), -candidate.candidate_index))

    def _slot_scope_for_mode(self, acceptance_mode: FormalSlotAcceptanceMode) -> FormalSlotArtifactScope:
        if acceptance_mode == "auxiliary_first_pass_reference":
            return "auxiliary_reference"
        return "formal_slot"


def project_formal_slot_public_summary(receipt: FormalSlotReceipt | dict[str, object]) -> dict[str, object]:
    """Return the safe public summary for a formal slot receipt-like payload."""

    validated = receipt if isinstance(receipt, FormalSlotReceipt) else FormalSlotReceipt.model_validate(receipt)
    return validated.public_summary().model_dump(mode="json")


def validate_formal_slot_receipt_for_activation(
    receipt: FormalSlotReceipt | dict[str, object],
) -> FormalSlotReceipt:
    """Fail closed unless a receipt proves standard three-candidate completion."""

    validated = receipt if isinstance(receipt, FormalSlotReceipt) else FormalSlotReceipt.model_validate(receipt)
    if not validated.activation_eligible:
        raise ValueError("formal slot activation requires standard_three_candidate receipt")
    return validated
