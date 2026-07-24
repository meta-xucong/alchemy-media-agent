"""Doc241 pure FormalSlotAcceptanceCore contracts."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotAcceptanceCore,
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
    validate_formal_slot_receipt_for_activation,
)


def _shared_review(status: str = "pass") -> FormalSlotSharedReviewSummary:
    return FormalSlotSharedReviewSummary(
        status=status,  # type: ignore[arg-type]
        evidence_codes=["shared_visual_review_verified"],
        issue_codes=[] if status == "pass" else ["shared_visual_review_rejected"],
        score_dimensions=["generic_visual_quality", "identity_or_subject_consistency"],
        framing_delta_dimensions=["frame_delta"],
    )


def _requirement(status: str = "pass") -> FormalSlotRequirementSummary:
    return FormalSlotRequirementSummary(
        status=status,  # type: ignore[arg-type]
        evidence_codes=[f"{status}_requirement_evidence"],
        dimensions={"summary_score": 0.91 if status == "pass" else 0.25},
    )


def _candidate(index: int, *, status: str = "pass") -> FormalSlotCandidateSummary:
    return FormalSlotCandidateSummary(
        candidate_index=index,
        candidate_id=f"candidate_{index}",
        output_id=f"output_{index}",
        reviewed=True,
        selected_as_winner=False,
        shared_review=_shared_review(status),
    )


def _core() -> FormalSlotAcceptanceCore:
    return FormalSlotAcceptanceCore()


@pytest.mark.parametrize(
    ("module", "slot_key"),
    [
        ("face_identity", "face.front"),
        ("expression_set", "expression.anger"),
        ("body_silhouette", "body.front_full"),
        ("future_professional_module", "future.slot"),
    ],
)
def test_doc241_core_builds_standard_receipt_for_any_module_name(module: str, slot_key: str) -> None:
    receipt = _core().accept(
        module=module,
        slot_key=slot_key,
        acceptance_mode="standard_three_candidate",
        candidates=[_candidate(1), _candidate(2), _candidate(3)],
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        reload_public_projection_verified=True,
    )

    assert receipt.module == module
    assert receipt.slot_key == slot_key
    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_candidate_id == "candidate_3"
    assert receipt.winner_output_id == "output_3"
    assert receipt.activation_eligible is True
    assert validate_formal_slot_receipt_for_activation(receipt) == receipt


def test_doc241_core_keeps_rejected_candidates_append_only_and_selects_passing_winner() -> None:
    receipt = _core().accept(
        module="expression_set",
        slot_key="expression.anger",
        acceptance_mode="standard_three_candidate",
        candidates=[
            _candidate(1, status="fail_retryable"),
            _candidate(2, status="pass"),
            _candidate(3, status="fail_retryable"),
        ],
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        reload_public_projection_verified=True,
    )

    assert [candidate.candidate_id for candidate in receipt.candidates] == [
        "candidate_1",
        "candidate_2",
        "candidate_3",
    ]
    assert receipt.winner_candidate_id == "candidate_2"
    assert [candidate.selected_as_winner for candidate in receipt.candidates] == [False, True, False]
    assert receipt.public_summary().candidate_output_ids == ["output_1", "output_2", "output_3"]


def test_doc241_core_uses_injected_ranking_without_changing_implementation() -> None:
    candidates = [_candidate(1), _candidate(2), _candidate(3)]
    choose_highest_index = _core().accept(
        module="face_identity",
        slot_key="face.front",
        acceptance_mode="standard_three_candidate",
        candidates=candidates,
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        reload_public_projection_verified=True,
    )
    choose_lowest_index = _core().accept(
        module="face_identity",
        slot_key="face.front",
        acceptance_mode="standard_three_candidate",
        candidates=candidates,
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: -candidate.candidate_index,
        reload_public_projection_verified=True,
    )

    assert choose_highest_index.winner_candidate_id == "candidate_3"
    assert choose_lowest_index.winner_candidate_id == "candidate_1"
    assert all(candidate.selected_as_winner is False for candidate in candidates)


def test_doc241_standard_mode_requires_explicit_ranking_key() -> None:
    with pytest.raises(ValueError, match="explicit ranking key"):
        _core().accept(
            module="face_identity",
            slot_key="face.front",
            acceptance_mode="standard_three_candidate",
            candidates=[_candidate(1), _candidate(2), _candidate(3)],
            framing_summary=_requirement(),
            parity_summary=_requirement(),
            identity_summary=_requirement(),
            reload_public_projection_verified=True,
        )


def test_doc241_core_does_not_default_reload_public_projection_to_true() -> None:
    receipt = _core().accept(
        module="expression_set",
        slot_key="expression.anger",
        acceptance_mode="standard_three_candidate",
        candidates=[_candidate(1), _candidate(2), _candidate(3)],
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
    )

    assert receipt.reload_public_projection_verified is False
    assert receipt.formal_completion_verified is False
    assert receipt.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        validate_formal_slot_receipt_for_activation(receipt)


def test_doc241_candidate_reviewed_must_be_explicit_true() -> None:
    missing_reviewed = {
        "candidate_index": 1,
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "shared_review": _shared_review().model_dump(mode="json"),
    }
    with pytest.raises(ValidationError):
        FormalSlotCandidateSummary.model_validate(missing_reviewed)
    with pytest.raises(ValidationError):
        _core().accept(
            module="expression_set",
            slot_key="expression.anger",
            acceptance_mode="target_only_existing_candidate_collection",
            candidates=[missing_reviewed],
            framing_summary=_requirement(),
            parity_summary=_requirement(),
            identity_summary=_requirement(),
            reload_public_projection_verified=True,
        )

    explicit_false = {**missing_reviewed, "reviewed": False}
    with pytest.raises(ValidationError, match="real reviewed attempt"):
        FormalSlotCandidateSummary.model_validate(explicit_false)
    explicit_true = FormalSlotCandidateSummary.model_validate({**missing_reviewed, "reviewed": True})
    assert explicit_true.reviewed is True


@pytest.mark.parametrize(
    ("acceptance_mode", "slot_scope"),
    [
        ("target_only_existing_candidate_collection", "formal_slot"),
        ("auxiliary_first_pass_reference", "auxiliary_reference"),
    ],
)
def test_doc241_core_builds_single_target_auxiliary_modes_without_activation(
    acceptance_mode: str,
    slot_scope: str,
) -> None:
    receipt = _core().accept(
        module="any_module",
        slot_key="any.slot",
        acceptance_mode=acceptance_mode,  # type: ignore[arg-type]
        candidates=[_candidate(1)],
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        reload_public_projection_verified=True,
    )

    assert receipt.slot_scope == slot_scope
    assert receipt.reviewed_candidate_count == 1
    assert receipt.winner_candidate_id == "candidate_1"
    assert receipt.formal_completion_verified is False
    assert receipt.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        validate_formal_slot_receipt_for_activation(receipt)


@pytest.mark.parametrize(
    ("acceptance_mode", "candidates", "expected_error"),
    [
        ("standard_three_candidate", [_candidate(1), _candidate(2)], "exactly three"),
        ("target_only_existing_candidate_collection", [_candidate(1), _candidate(2)], "exactly one"),
        ("auxiliary_first_pass_reference", [_candidate(1), _candidate(2)], "exactly one"),
        (
            "standard_three_candidate",
            [_candidate(1, status="fail_retryable"), _candidate(2, status="fail_retryable"), _candidate(3, status="fail_retryable")],
            "at least one passing",
        ),
    ],
)
def test_doc241_core_rejects_invalid_candidate_sets(
    acceptance_mode: str,
    candidates: list[FormalSlotCandidateSummary],
    expected_error: str,
) -> None:
    with pytest.raises(ValueError, match=expected_error):
        _core().accept(
            module="expression_set",
            slot_key="expression.anger",
            acceptance_mode=acceptance_mode,  # type: ignore[arg-type]
            candidates=candidates,
            framing_summary=_requirement(),
            parity_summary=_requirement(),
            identity_summary=_requirement(),
            ranking_key=lambda candidate: candidate.candidate_index,
            reload_public_projection_verified=True,
        )


def test_doc241_core_delegates_requirement_failures_to_receipt_validation() -> None:
    with pytest.raises(ValidationError, match="passing framing summary"):
        _core().accept(
            module="body_silhouette",
            slot_key="body.front_full",
            acceptance_mode="standard_three_candidate",
            candidates=[_candidate(1), _candidate(2), _candidate(3)],
            framing_summary=_requirement("fail"),
            parity_summary=_requirement(),
            identity_summary=_requirement(),
            ranking_key=lambda candidate: candidate.candidate_index,
            reload_public_projection_verified=True,
        )


def test_doc241_core_receipt_roundtrip_and_public_summary_are_consistent() -> None:
    receipt = _core().accept(
        module="future_professional_module",
        slot_key="future.slot",
        acceptance_mode="standard_three_candidate",
        candidates=[_candidate(1), _candidate(2), _candidate(3)],
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        retry_count=1,
        repair_count=1,
        reload_public_projection_verified=True,
    )
    reloaded = FormalSlotReceipt.model_validate(receipt.model_dump(mode="json"))
    summary = reloaded.public_summary()

    assert reloaded == receipt
    assert summary.formal_completion_verified is True
    assert summary.winner_output_id == "output_3"
    assert summary.candidate_output_ids == ["output_1", "output_2", "output_3"]
    assert summary.retry_count == 1
    assert summary.repair_count == 1


def test_doc241_core_source_has_no_slot_specific_or_adapter_branches() -> None:
    source = inspect.getsource(FormalSlotAcceptanceCore).lower()

    for forbidden in ("face.", "expression.", "body.", "laugh", "anger", "sad", "mcp", "provider", "route"):
        assert forbidden not in source
