"""Doc246 / Task8 cross-module formal authority closure contracts."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BODY_SLOT_KEYS,
    EXPRESSION_SLOT_KEYS,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardStageResult,
    CharacterCardSlot,
    CharacterCardState,
    character_card_formal_slot_receipt_public_summary,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotAcceptanceCore,
    FormalSlotCandidateEnhancedProofSummary,
    FormalSlotCandidateSummary,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
    mark_formal_slot_receipt_reload_public_projection_verified,
    validate_formal_slot_receipt_for_activation,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import VisualAssetLibraryLifecycleService


def _generic_shared_receipt(*, status: str = "pass", framing: bool = True) -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": status,
        "evidence_codes": [
            "shared_visual_review_verified",
            "shared_visual_review_status_pass",
            "front_card_framing_parity_verified",
            "front_card_framing_delta_receipt_verified",
        ]
        if status == "pass"
        else ["shared_visual_review_rejected"],
        "issue_codes": [] if status == "pass" else ["shared_visual_review_rejected"],
        "score_dimensions": ["generic_visual_quality", "identity_or_subject_consistency"],
        "framing_delta_dimensions": ["front_card_framing_delta"] if framing else [],
    }


def _requirement(*, status: str = "pass", code: str = "requirement_verified") -> FormalSlotRequirementSummary:
    return FormalSlotRequirementSummary(
        status=status,  # type: ignore[arg-type]
        evidence_codes=[code],
        dimensions={"summary_score": 1.0 if status == "pass" else 0.0},
    )


def _proof(index: int, *, eligible: bool = True) -> FormalSlotCandidateEnhancedProofSummary:
    return FormalSlotCandidateEnhancedProofSummary(
        profile_id="generic_profile_v1",
        requirement_id="generic_profile.required",
        candidate_id=f"candidate_{index}",
        output_id=f"output_{index}",
        eligible=eligible,
        status="pass" if eligible else "fail",
        evidence_codes=["profile_eligible"] if eligible else ["profile_rejected"],
        issue_codes=[] if eligible else ["profile_rejected"],
        dimensions={"profile_score": 1.0 if eligible else 0.0},
    )


def _candidate(index: int, *, enhanced: bool = True, eligible: bool = True) -> FormalSlotCandidateSummary:
    return FormalSlotCandidateSummary(
        candidate_index=index,
        candidate_id=f"candidate_{index}",
        output_id=f"output_{index}",
        reviewed=True,
        shared_review=FormalSlotSharedReviewSummary.model_validate(_generic_shared_receipt()),
        enhanced_proof=_proof(index, eligible=eligible) if enhanced else None,
    )


def _scores(index: int, *, body_eligible: bool = True) -> IdentityScoreSummary:
    evidence_codes = ["body_candidate_reviewed"]
    if body_eligible:
        evidence_codes.append("body_silhouette_profile_eligible")
    return IdentityScoreSummary(
        same_face_score=0.80 + index / 100,
        visual_quality_score=0.70 + index / 100,
        evidence_codes=evidence_codes,
    )


def _review(index: int, *, framing: bool = True, body_eligible: bool = True) -> AnchorReviewDecision:
    return AnchorReviewDecision(
        status="pass",
        identity_scores=_scores(index, body_eligible=body_eligible),
        issue_codes=[] if body_eligible else ["body_silhouette_profile_rejected"],
        shared_review_receipts=[_generic_shared_receipt(framing=framing)],
    )


def _body_candidate(slot_key: str, index: int) -> CharacterCardCandidateResult:
    refs = ["face_front_output", "face_profile_output", "face_rear_output"]
    return CharacterCardCandidateResult(
        candidate_id=f"candidate_{slot_key}_{index}",
        output_id=f"output_{slot_key}_{index}",
        module="body_silhouette",
        slot_key=slot_key,
        candidate_index=index,
        source_candidate_ids=[f"source_{slot_key}_{index}"],
        source_output_ids=refs,
        canonical_prompt_hash=f"prompt_hash_{slot_key}_{index}",
        prompt_compilation_id=f"prompt_compilation_{slot_key}_{index}",
        prompt_reference_parity_verified=True,
    )


def _body_attempts(slot_key: str, *, framing: bool = True) -> list[object]:
    return [
        SimpleNamespace(
            request=CharacterCardCandidateRequest(
                project_id="visual_asset_body",
                people_asset_id="people_body",
                card_version_id="card_doc246_body",
                module="body_silhouette",
                slot_key=slot_key,  # type: ignore[arg-type]
                candidate_index=index,
                reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
                user_intent="neutral body silhouette profile",
                source_class="brain_inferred",
            ),
            candidate=_body_candidate(slot_key, index),
            review=_review(index, framing=framing),
        )
        for index in (1, 2, 3)
    ]


class _BodyGenerator:
    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{request.slot_key}_{request.candidate_index}",
            output_id=f"output_{request.slot_key}_{request.candidate_index}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"source_{request.slot_key}_{request.candidate_index}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"prompt_hash_{request.slot_key}_{request.candidate_index}",
            prompt_compilation_id=f"prompt_compilation_{request.slot_key}_{request.candidate_index}",
            prompt_reference_parity_verified=True,
        )


class _BodyReviewer:
    def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        return _review(candidate.candidate_index)


def _card_ready_for_body() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_doc246_body")
    face_slots = dict(card.face_slots)
    for slot_key, output_id in {
        "face.front": "face_front_output",
        "face.profile": "face_profile_output",
        "face.rear_head": "face_rear_output",
    }.items():
        face_slots[slot_key] = CharacterCardSlot.model_construct(
            slot_key=slot_key,
            module="face_identity",
            state="active",
            output_id=output_id,
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
    expression_slots = dict(card.expression_slots)
    for slot_key in ("expression.laugh", "expression.anger", "expression.sad"):
        expression_slots[slot_key] = CharacterCardSlot.model_construct(
            slot_key=slot_key,
            module="expression_set",
            state="active",
            output_id=f"{slot_key}_output",
            review_verified=True,
            prompt_reference_parity_verified=True,
        )
    expression_slots["expression.neutral"] = CharacterCardSlot.model_construct(
        slot_key="expression.neutral",
        module="expression_set",
        state="active",
        is_alias=True,
        alias_of="face.front",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    return card.model_copy(
        update={
            "face_identity_status": "active",
            "expression_set_status": "active",
            "face_slots": face_slots,
            "expression_slots": expression_slots,
        }
    )


def test_doc246_candidate_eligibility_required_is_persisted_and_rechecked_on_activation() -> None:
    receipt = FormalSlotAcceptanceCore().accept(
        module="generic_module",
        slot_key="generic.slot",
        acceptance_mode="standard_three_candidate",
        candidates=[_candidate(1), _candidate(2), _candidate(3)],
        framing_summary=_requirement(code="generic_framing_verified"),
        parity_summary=_requirement(code="generic_parity_verified"),
        identity_summary=_requirement(code="generic_identity_verified"),
        ranking_key=lambda candidate: candidate.candidate_index,
        candidate_eligibility=lambda candidate: candidate.enhanced_proof is not None
        and candidate.enhanced_proof.eligible,
    )

    assert receipt.candidate_eligibility_required is True
    verified = mark_formal_slot_receipt_reload_public_projection_verified(receipt)
    assert validate_formal_slot_receipt_for_activation(verified).activation_eligible is True

    payload = verified.model_dump(mode="json")
    for candidate in payload["candidates"]:
        if candidate["candidate_id"] == payload["winner_candidate_id"]:
            candidate.pop("enhanced_proof")
    with pytest.raises(ValueError, match="enhanced"):
        validate_formal_slot_receipt_for_activation(payload)


def test_doc246_non_required_legacy_compatible_formal_receipt_does_not_require_enhanced_proof() -> None:
    receipt = FormalSlotAcceptanceCore().accept(
        module="face_identity",
        slot_key="face.front",
        acceptance_mode="standard_three_candidate",
        candidates=[_candidate(1, enhanced=False), _candidate(2, enhanced=False), _candidate(3, enhanced=False)],
        framing_summary=_requirement(code="face_framing_verified"),
        parity_summary=_requirement(code="face_parity_verified"),
        identity_summary=_requirement(code="face_identity_verified"),
        ranking_key=lambda candidate: candidate.candidate_index,
    )

    verified = mark_formal_slot_receipt_reload_public_projection_verified(receipt)
    assert verified.candidate_eligibility_required is False
    assert validate_formal_slot_receipt_for_activation(verified).activation_eligible is True


def test_doc246_body_framing_summary_must_come_from_generic_shared_review_not_enhanced_profile() -> None:
    with pytest.raises(ValueError, match="framing"):
        CharacterCardPreparationService._formal_body_slot_receipt(
            slot_key="body.front_full",
            attempts=_body_attempts("body.front_full", framing=False),  # type: ignore[arg-type]
        )


def test_doc246_formal_receipts_are_authority_when_stage_shared_runtime_receipt_is_missing() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    assert result.shared_runtime_receipt is None

    persisted = VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
        result,
        stage="body_silhouette",
    )

    slot = persisted.body_slots["body.front_full"]
    assert slot.formal_slot_receipt is not None
    assert slot.formal_slot_receipt.winner_output_id == slot.output_id
    assert slot.shared_runtime_receipt is None


def test_doc246_conflicting_stage_shared_runtime_receipt_cannot_shadow_formal_receipt() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    conflicting = CharacterCardSharedRuntimeReceipt(
        reviewed_candidate_count=1,
        acceptance_mode="target_only_existing_candidate_collection",
        final_winner_selection_verified=True,
        prompt_reference_parity_verified=True,
        shared_review_receipts=[_generic_shared_receipt()],
    )

    with pytest.raises(Exception, match="conflict|mismatch|standard"):
        VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
            result.model_copy(update={"shared_runtime_receipt": conflicting}),
            stage="body_silhouette",
        )


def test_doc246_explicit_smile_is_formal_extension_but_not_default_expression_activation_slot() -> None:
    assert "expression.smile" not in EXPRESSION_SLOT_KEYS
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    card = CharacterCardState.initial(card_version_id="card_doc246_smile").model_copy(
        update={
            "face_identity_status": "active",
            "face_slots": {
                **CharacterCardState.initial(card_version_id="unused").face_slots,
                "face.front": CharacterCardSlot.model_construct(
                    slot_key="face.front",
                    module="face_identity",
                    state="active",
                    output_id="face_front_output",
                    review_verified=True,
                    prompt_reference_parity_verified=True,
                ),
            },
        }
    )

    result = service.prepare_expression_slot(
        card,
        expression="smile",
        front_output_id="face_front_output",
        user_intent="explicit lower-intensity smile expression",
    )

    assert set(result.formal_slot_receipts) == {"expression.smile"}
    persisted = VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
        result,
        stage="expression_set",
    )
    slot = persisted.expression_slots["expression.smile"]
    assert slot.formal_slot_receipt is not None
    assert slot.formal_slot_receipt.acceptance_mode == "standard_three_candidate"
    assert slot.state == "winner_selected"
    assert persisted.expression_set_status == "partial"
