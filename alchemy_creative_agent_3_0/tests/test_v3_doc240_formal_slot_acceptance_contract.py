"""Doc240 module-neutral formal slot acceptance contract tests."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
    project_formal_slot_public_summary,
    validate_formal_slot_receipt_for_activation,
)


def _shared_review(status: str = "pass") -> FormalSlotSharedReviewSummary:
    return FormalSlotSharedReviewSummary(
        status=status,  # type: ignore[arg-type]
        evidence_codes=["shared_visual_review_verified"],
        issue_codes=[] if status in {"pass", "verified"} else ["shared_visual_review_rejected"],
        score_dimensions={
            "generic_visual_quality": 0.91 if status in {"pass", "verified"} else 0.62,
            "identity_or_subject_consistency": 0.90 if status in {"pass", "verified"} else 0.58,
        },
        framing_delta_dimensions={"frame_delta": 0.02},
    )


def _requirement(status: str = "pass") -> FormalSlotRequirementSummary:
    return FormalSlotRequirementSummary(
        status=status,  # type: ignore[arg-type]
        evidence_codes=[f"{status}_requirement_evidence"],
        dimensions={"summary_score": 0.92 if status == "pass" else 0.2},
    )


def _candidate(
    index: int,
    *,
    status: str = "pass",
    winner: bool = False,
) -> FormalSlotCandidateSummary:
    return FormalSlotCandidateSummary(
        candidate_index=index,
        candidate_id=f"candidate_{index}",
        output_id=f"output_{index}",
        reviewed=True,
        selected_as_winner=winner,
        shared_review=_shared_review(status),
    )


def _standard_receipt(
    *,
    module: str = "expression_set",
    slot_key: str = "expression.anger",
    winner_index: int = 2,
    candidate_count: int = 3,
    reviewed_candidate_count: int | None = None,
    slot_scope: str = "formal_slot",
    parity_status: str = "pass",
) -> FormalSlotReceipt:
    candidates = [
        _candidate(index, status="pass" if index == winner_index else "fail_retryable", winner=index == winner_index)
        for index in range(1, candidate_count + 1)
    ]
    winner = candidates[winner_index - 1]
    return FormalSlotReceipt(
        module=module,
        slot_key=slot_key,
        acceptance_mode="standard_three_candidate",
        slot_scope=slot_scope,  # type: ignore[arg-type]
        reviewed_candidate_count=reviewed_candidate_count if reviewed_candidate_count is not None else len(candidates),
        candidates=candidates,
        winner_candidate_id=winner.candidate_id,
        winner_output_id=winner.output_id,
        winner_shared_review=winner.shared_review,
        framing_summary=_requirement("pass"),
        parity_summary=_requirement(parity_status),
        identity_summary=_requirement("pass"),
        retry_count=0,
        repair_count=0,
        reload_public_projection_verified=True,
    )


def _target_only_receipt() -> FormalSlotReceipt:
    candidate = _candidate(1, winner=True)
    return FormalSlotReceipt(
        module="expression_set",
        slot_key="expression.laugh",
        acceptance_mode="target_only_existing_candidate_collection",
        slot_scope="formal_slot",
        reviewed_candidate_count=1,
        candidates=[candidate],
        winner_candidate_id=candidate.candidate_id,
        winner_output_id=candidate.output_id,
        winner_shared_review=candidate.shared_review,
        framing_summary=_requirement("pass"),
        parity_summary=_requirement("pass"),
        identity_summary=_requirement("pass"),
        reload_public_projection_verified=True,
    )


def _bridge_receipt() -> FormalSlotReceipt:
    candidate = _candidate(1, winner=True)
    return FormalSlotReceipt(
        module="face_identity_auxiliary",
        slot_key="reference_bridge.left_25",
        acceptance_mode="auxiliary_first_pass_reference",
        slot_scope="auxiliary_reference",
        reviewed_candidate_count=1,
        candidates=[candidate],
        winner_candidate_id=candidate.candidate_id,
        winner_output_id=candidate.output_id,
        winner_shared_review=candidate.shared_review,
        framing_summary=_requirement("pass"),
        parity_summary=_requirement("pass"),
        identity_summary=_requirement("pass"),
        reload_public_projection_verified=True,
    )


@pytest.mark.parametrize(
    ("module", "slot_key"),
    [
        ("face_identity", "face.front"),
        ("expression_set", "expression.anger"),
        ("body_silhouette", "body.front_full"),
        ("future_professional_module", "future.slot"),
    ],
)
def test_doc240_standard_three_candidate_is_module_name_agnostic(module: str, slot_key: str) -> None:
    receipt = _standard_receipt(module=module, slot_key=slot_key)

    assert receipt.activation_eligible is True
    assert validate_formal_slot_receipt_for_activation(receipt) == receipt
    assert receipt.public_summary().formal_completion_verified is True
    assert receipt.public_summary().reviewed_candidate_count == 3


def test_doc240_standard_three_candidate_requires_three_real_reviewed_attempts() -> None:
    with pytest.raises(ValidationError, match="exactly three reviewed candidates"):
        _standard_receipt(candidate_count=2)


def test_doc240_reviewed_count_cannot_be_faked_by_constant() -> None:
    with pytest.raises(ValidationError, match="must equal the real candidate summary count"):
        _standard_receipt(candidate_count=1, reviewed_candidate_count=3, winner_index=1)


def test_doc240_standard_three_candidate_rejects_wrong_scope_or_missing_parity() -> None:
    with pytest.raises(ValidationError, match="formal_slot slot scope"):
        _standard_receipt(slot_scope="auxiliary_reference")
    with pytest.raises(ValidationError, match="passing parity summary"):
        _standard_receipt(parity_status="missing")


def test_doc240_target_only_is_collectable_but_not_formal_activation() -> None:
    receipt = _target_only_receipt()
    summary = receipt.public_summary()

    assert receipt.formal_completion_verified is False
    assert summary.acceptance_mode == "target_only_existing_candidate_collection"
    assert summary.reviewed_candidate_count == 1
    assert summary.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        validate_formal_slot_receipt_for_activation(receipt)


def test_doc240_auxiliary_first_pass_reference_is_not_a_formal_slot_receipt() -> None:
    receipt = _bridge_receipt()
    summary = project_formal_slot_public_summary(receipt)

    assert summary["acceptance_mode"] == "auxiliary_first_pass_reference"
    assert summary["slot_scope"] == "auxiliary_reference"
    assert summary["formal_completion_verified"] is False
    assert summary["activation_eligible"] is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        validate_formal_slot_receipt_for_activation(receipt)


def test_doc240_auxiliary_bridge_cannot_use_formal_slot_scope() -> None:
    candidate = _candidate(1, winner=True)
    with pytest.raises(ValidationError, match="auxiliary_reference scope"):
        FormalSlotReceipt(
            module="face_identity",
            slot_key="face.left_front_25",
            acceptance_mode="auxiliary_first_pass_reference",
            slot_scope="formal_slot",
            reviewed_candidate_count=1,
            candidates=[candidate],
            winner_candidate_id=candidate.candidate_id,
            winner_output_id=candidate.output_id,
            winner_shared_review=candidate.shared_review,
            framing_summary=_requirement("pass"),
            parity_summary=_requirement("pass"),
            identity_summary=_requirement("pass"),
            reload_public_projection_verified=True,
        )


def test_doc240_public_summary_is_safe_and_round_trips() -> None:
    receipt = _standard_receipt()
    dumped = receipt.model_dump(mode="json")
    reloaded = FormalSlotReceipt.model_validate(dumped)
    public_summary = project_formal_slot_public_summary(reloaded)

    assert reloaded == receipt
    assert public_summary["winner_output_id"] == "output_2"
    assert public_summary["candidate_output_ids"] == ["output_1", "output_2", "output_3"]
    serialized = json.dumps(public_summary, sort_keys=True)
    for forbidden in ("prompt", "provider_response", "api_key", "file_path", "handoff", "artifact"):
        assert forbidden not in serialized


def test_doc240_public_receipt_rejects_prompt_or_provider_private_fields() -> None:
    payload = _standard_receipt().model_dump(mode="json")
    payload["raw_prompt"] = "not allowed"
    with pytest.raises(ValidationError):
        FormalSlotReceipt.model_validate(payload)

    payload = _standard_receipt().model_dump(mode="json")
    payload["candidates"][0]["shared_review"]["evidence_codes"] = ["raw_provider_response"]
    with pytest.raises(ValidationError, match="public-safe"):
        FormalSlotReceipt.model_validate(payload)
