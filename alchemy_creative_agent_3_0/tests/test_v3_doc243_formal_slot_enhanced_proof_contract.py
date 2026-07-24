"""Doc243 / Task6-A pure candidate-level Enhanced proof contracts."""

from __future__ import annotations

import inspect

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotAcceptanceCore,
    FormalSlotCandidateEnhancedProofSummary,
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
)


def _shared_review() -> FormalSlotSharedReviewSummary:
    return FormalSlotSharedReviewSummary(
        status="pass",
        evidence_codes=["shared_visual_review_verified"],
        score_dimensions=["generic_visual_quality"],
        framing_delta_dimensions=["generic_frame_delta"],
    )


def _requirement() -> FormalSlotRequirementSummary:
    return FormalSlotRequirementSummary(
        status="pass",
        evidence_codes=["formal_requirement_verified"],
        dimensions={"summary_score": 0.91},
    )


def _enhanced_proof(
    *,
    candidate_id: str = "candidate_1",
    output_id: str = "output_1",
    eligible: bool = True,
    status: str = "pass",
) -> FormalSlotCandidateEnhancedProofSummary:
    return FormalSlotCandidateEnhancedProofSummary(
        profile_id="profile_contract_v1",
        requirement_id="profile_requirement_v1",
        candidate_id=candidate_id,
        output_id=output_id,
        eligible=eligible,
        status=status,  # type: ignore[arg-type]
        evidence_codes=["profile_requirement_verified"] if eligible else ["profile_requirement_rejected"],
        issue_codes=[] if eligible else ["profile_requirement_not_met"],
        dimensions={"profile_score": 0.93 if eligible else 0.22},
    )


def _candidate(
    index: int = 1,
    *,
    enhanced_proof: FormalSlotCandidateEnhancedProofSummary | None = None,
    shared_status: str = "pass",
) -> FormalSlotCandidateSummary:
    return FormalSlotCandidateSummary(
        candidate_index=index,
        candidate_id=f"candidate_{index}",
        output_id=f"output_{index}",
        reviewed=True,
        shared_review=_shared_review()
        if shared_status == "pass"
        else FormalSlotSharedReviewSummary(
            status=shared_status,  # type: ignore[arg-type]
            issue_codes=["shared_visual_review_rejected"],
        ),
        enhanced_proof=enhanced_proof,
    )


def test_doc243_enhanced_proof_requires_explicit_profile_status_and_eligibility() -> None:
    base = {
        "profile_id": "profile_contract_v1",
        "requirement_id": "profile_requirement_v1",
        "candidate_id": "candidate_1",
        "output_id": "output_1",
        "evidence_codes": ["profile_requirement_verified"],
        "dimensions": {"profile_score": 0.93},
    }
    for missing in ("profile_id", "requirement_id", "status", "eligible"):
        payload = dict(base)
        payload.pop(missing, None)
        with pytest.raises(ValidationError):
            FormalSlotCandidateEnhancedProofSummary.model_validate(payload)

    with pytest.raises(ValidationError):
        FormalSlotCandidateEnhancedProofSummary.model_validate({**base, "status": "pass", "eligible": False})
    with pytest.raises(ValidationError):
        FormalSlotCandidateEnhancedProofSummary.model_validate({**base, "status": "fail", "eligible": True})


def test_doc243_enhanced_proof_rejects_malformed_evidence_dimensions_and_private_fields() -> None:
    with pytest.raises(ValidationError):
        FormalSlotCandidateEnhancedProofSummary.model_validate(
            {**_enhanced_proof().model_dump(mode="json"), "evidence_codes": []}
        )
    with pytest.raises(ValidationError):
        FormalSlotCandidateEnhancedProofSummary(
            profile_id="profile_contract_v1",
            requirement_id="profile_requirement_v1",
            candidate_id="candidate_1",
            output_id="output_1",
            eligible=True,
            status="pass",
            evidence_codes=["profile_requirement_verified"],
            dimensions={"profile_score": 1.5},
        )
    with pytest.raises(ValidationError):
        FormalSlotCandidateEnhancedProofSummary(
            profile_id="profile_contract_v1",
            requirement_id="profile_requirement_v1",
            candidate_id="candidate_1",
            output_id="output_1",
            eligible=True,
            status="pass",
            evidence_codes=["profile_requirement_verified"],
            dimensions={"profile_score": 0.92},
            prompt="private renderer text",  # type: ignore[call-arg]
        )


def test_doc243_candidate_rejects_enhanced_proof_for_different_candidate_or_output() -> None:
    with pytest.raises(ValidationError):
        _candidate(enhanced_proof=_enhanced_proof(candidate_id="candidate_other"))
    with pytest.raises(ValidationError):
        _candidate(enhanced_proof=_enhanced_proof(output_id="output_other"))


def test_doc243_enhanced_proof_coexists_with_generic_shared_review_without_overriding_it() -> None:
    candidate = _candidate(enhanced_proof=_enhanced_proof())

    assert candidate.shared_review.owner == "v3_shared_visual_cluster"
    assert candidate.shared_review.passed is True
    assert candidate.enhanced_proof is not None
    assert candidate.enhanced_proof.owner == "v3_professional_enhanced_profile_contract"
    assert candidate.enhanced_proof.eligible is True

    rejected_generic = candidate.model_copy(
        update={"shared_review": FormalSlotSharedReviewSummary(status="fail", issue_codes=["generic_failed"])}
    )
    assert rejected_generic.enhanced_proof is not None
    assert rejected_generic.enhanced_proof.eligible is True
    assert rejected_generic.shared_review.passed is False


def test_doc243_core_preserves_enhanced_proof_without_understanding_profile_semantics() -> None:
    candidates = [
        _candidate(1, enhanced_proof=_enhanced_proof()),
        _candidate(2, enhanced_proof=_enhanced_proof(candidate_id="candidate_2", output_id="output_2")),
        _candidate(3, enhanced_proof=_enhanced_proof(candidate_id="candidate_3", output_id="output_3")),
    ]
    receipt = FormalSlotAcceptanceCore().accept(
        module="future_professional_module",
        slot_key="future.slot",
        acceptance_mode="standard_three_candidate",
        candidates=candidates,
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        reload_public_projection_verified=True,
    )
    reloaded = FormalSlotReceipt.model_validate(receipt.model_dump(mode="json"))

    assert reloaded.candidates[2].selected_as_winner is True
    assert reloaded.candidates[2].enhanced_proof is not None
    assert reloaded.candidates[2].enhanced_proof.profile_id == "profile_contract_v1"
    assert reloaded.winner_shared_review == reloaded.candidates[2].shared_review


def test_doc243_core_filters_winner_by_injected_enhanced_eligibility_before_ranking() -> None:
    candidates = [
        _candidate(
            1,
            enhanced_proof=_enhanced_proof(candidate_id="candidate_1", output_id="output_1", eligible=False, status="fail"),
        ),
        _candidate(
            2,
            enhanced_proof=_enhanced_proof(candidate_id="candidate_2", output_id="output_2"),
        ),
        _candidate(
            3,
            enhanced_proof=_enhanced_proof(candidate_id="candidate_3", output_id="output_3", eligible=False, status="fail"),
        ),
    ]

    receipt = FormalSlotAcceptanceCore().accept(
        module="expression_set",
        slot_key="expression.profiled_slot",
        acceptance_mode="standard_three_candidate",
        candidates=candidates,
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        candidate_eligibility=lambda candidate: candidate.enhanced_proof is not None
        and candidate.enhanced_proof.eligible,
        reload_public_projection_verified=True,
    )

    assert receipt.winner_candidate_id == "candidate_2"
    assert [candidate.selected_as_winner for candidate in receipt.candidates] == [False, True, False]


def test_doc243_core_rejects_all_enhanced_ineligible_candidates_when_policy_requires_proof() -> None:
    candidates = [
        _candidate(
            1,
            enhanced_proof=_enhanced_proof(candidate_id="candidate_1", output_id="output_1", eligible=False, status="fail"),
        ),
        _candidate(
            2,
            enhanced_proof=_enhanced_proof(candidate_id="candidate_2", output_id="output_2", eligible=False, status="fail"),
        ),
        _candidate(
            3,
            enhanced_proof=_enhanced_proof(candidate_id="candidate_3", output_id="output_3", eligible=False, status="fail"),
        ),
    ]

    with pytest.raises(ValueError, match="external eligibility"):
        FormalSlotAcceptanceCore().accept(
            module="expression_set",
            slot_key="expression.profiled_slot",
            acceptance_mode="standard_three_candidate",
            candidates=candidates,
            framing_summary=_requirement(),
            parity_summary=_requirement(),
            identity_summary=_requirement(),
            ranking_key=lambda candidate: candidate.candidate_index,
            candidate_eligibility=lambda candidate: candidate.enhanced_proof is not None
            and candidate.enhanced_proof.eligible,
            reload_public_projection_verified=True,
        )


def test_doc243_core_does_not_treat_missing_enhanced_proof_as_eligible_when_policy_requires_it() -> None:
    candidates = [_candidate(1), _candidate(2), _candidate(3)]

    with pytest.raises(ValueError, match="external eligibility"):
        FormalSlotAcceptanceCore().accept(
            module="expression_set",
            slot_key="expression.profiled_slot",
            acceptance_mode="standard_three_candidate",
            candidates=candidates,
            framing_summary=_requirement(),
            parity_summary=_requirement(),
            identity_summary=_requirement(),
            ranking_key=lambda candidate: candidate.candidate_index,
            candidate_eligibility=lambda candidate: candidate.enhanced_proof is not None
            and candidate.enhanced_proof.eligible,
            reload_public_projection_verified=True,
        )


def test_doc243_core_keeps_existing_unprofiled_policy_available_for_face_task4() -> None:
    receipt = FormalSlotAcceptanceCore().accept(
        module="face_identity",
        slot_key="face.front",
        acceptance_mode="standard_three_candidate",
        candidates=[_candidate(1), _candidate(2), _candidate(3)],
        framing_summary=_requirement(),
        parity_summary=_requirement(),
        identity_summary=_requirement(),
        ranking_key=lambda candidate: candidate.candidate_index,
        reload_public_projection_verified=True,
    )

    assert receipt.winner_candidate_id == "candidate_3"


def test_doc243_enhanced_public_summary_is_safe_and_stable() -> None:
    proof = _enhanced_proof()
    summary = proof.public_summary()
    reloaded = FormalSlotCandidateEnhancedProofSummary.model_validate(proof.model_dump(mode="json"))

    assert reloaded == proof
    assert summary["eligible"] is True
    assert summary["profile_id"] == "profile_contract_v1"
    serialized = str(summary).lower()
    for forbidden in ("prompt", "provider", "mcp", "handoff", "artifact", "path", "raw"):
        assert forbidden not in serialized


def test_doc243_shared_core_rejects_slot_specific_extra_fields_in_enhanced_input() -> None:
    payload = _enhanced_proof().model_dump(mode="json")
    payload["emotion"] = "laugh"
    with pytest.raises(ValidationError):
        FormalSlotCandidateEnhancedProofSummary.model_validate(payload)


def test_doc243_core_source_does_not_gain_profile_specific_or_adapter_branches() -> None:
    source = inspect.getsource(FormalSlotAcceptanceCore).lower()
    enhanced_source = inspect.getsource(FormalSlotCandidateEnhancedProofSummary).lower()
    combined = source + enhanced_source

    for forbidden in ("laugh", "anger", "sad", "smile", "age", "eye", "cheek", "jaw", "mcp", "provider"):
        assert forbidden not in combined
