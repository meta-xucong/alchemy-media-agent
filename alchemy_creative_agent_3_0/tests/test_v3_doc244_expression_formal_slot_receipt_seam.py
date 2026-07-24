"""Doc244 / Task6-B Expression formal-slot receipt seam contracts."""

from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardSlot,
    CharacterCardState,
    character_card_formal_slot_receipt_public_summary,
    project_character_card_slot_success_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import VisualAssetLibraryLifecycleService
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.expression_review import (
    LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES,
)


def _generic_expression_shared_receipt(*, status: str = "pass", framing: bool = True) -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": status,
        "evidence_codes": [
            "shared_visual_review_verified",
            "shared_visual_review_status_pass",
            *(
                [
                    "front_card_framing_parity_verified",
                    "front_card_framing_delta_receipt_verified",
                ]
                if framing
                else []
            ),
        ]
        if status == "pass"
        else ["shared_visual_review_unverified"],
        "issue_codes": [] if status == "pass" else ["shared_visual_review_rejected"],
        "score_dimensions": ["generic_visual_quality", "identity_or_subject_consistency"],
        "framing_delta_dimensions": ["eye_line_delta_from_front", "face_area_delta_from_front"]
        if framing
        else [],
    }


def _laugh_expression_shared_receipt() -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_affective_expression_review_receipt_v1",
        "expression": "laugh",
        "framing_baseline": "face.front",
        "status": "pass",
        "evidence_codes": sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES),
        "issue_codes": [],
        "score_dimensions": ["mouth_eye_coherence", "periocular_affect"],
        "framing_delta_dimensions": ["eye_line_delta_from_front"],
    }


def _legacy_slot_success_receipt(slot_key: str, output_id: str) -> dict[str, object]:
    shared_reviews = [_generic_expression_shared_receipt()]
    if slot_key == "expression.laugh":
        shared_reviews.append(_laugh_expression_shared_receipt())
    return project_character_card_slot_success_receipt(
        CharacterCardSharedRuntimeReceipt(
            reviewed_candidate_count=3,
            acceptance_mode="standard_three_candidate",
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
            shared_review_receipts=shared_reviews,
        ),
        module="expression_set",
        slot_key=slot_key,
        output_id=output_id,
        shared_review_receipts=shared_reviews,
    )


def _scores(index: int) -> IdentityScoreSummary:
    return IdentityScoreSummary(
        same_face_score=0.80 + index / 100,
        visual_quality_score=0.70 + index / 100,
        evidence_codes=["expression_candidate_reviewed"],
    )


def _review(index: int, *, status: str = "pass", framing: bool = True) -> AnchorReviewDecision:
    return AnchorReviewDecision(
        status=status,  # type: ignore[arg-type]
        identity_scores=_scores(index),
        issue_codes=[] if status == "pass" else ["candidate_failed"],
        shared_review_receipts=[_generic_expression_shared_receipt(status=status, framing=framing)],
    )


class _ExpressionGenerator:
    def __init__(self) -> None:
        self.requests: list[CharacterCardCandidateRequest] = []

    def generate(self, request: CharacterCardCandidateRequest) -> CharacterCardCandidateResult:
        self.requests.append(request)
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


class _ExpressionReviewer:
    def __init__(
        self,
        *,
        failing_indexes: set[int] | None = None,
        no_framing_indexes: set[int] | None = None,
        missing_laugh_evidence_indexes: set[int] | None = None,
    ) -> None:
        self.failing_indexes = set(failing_indexes or set())
        self.no_framing_indexes = set(no_framing_indexes or set())
        self.missing_laugh_evidence_indexes = set(missing_laugh_evidence_indexes or set())

    def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        status = "fail" if candidate.candidate_index in self.failing_indexes else "pass"
        framing = candidate.candidate_index not in self.no_framing_indexes
        review = _review(candidate.candidate_index, status=status, framing=framing)
        if (
            candidate.slot_key == "expression.laugh"
            and status == "pass"
            and candidate.candidate_index not in self.missing_laugh_evidence_indexes
        ):
            scores = review.identity_scores.model_copy(
                update={
                    "evidence_codes": [
                        *review.identity_scores.evidence_codes,
                        *sorted(LAUGH_EXPRESSION_SLOT_REQUIRED_EVIDENCE_CODES),
                    ]
                }
            )
            return review.model_copy(
                update={
                    "identity_scores": scores,
                    "shared_review_receipts": [
                        *review.shared_review_receipts,
                        _laugh_expression_shared_receipt(),
                    ],
                }
            )
        return review


def _card_with_active_front() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_expression_formal")
    face_slots = dict(card.face_slots)
    face_slots["face.front"] = CharacterCardSlot.model_construct(
        slot_key="face.front",
        module="face_identity",
        state="active",
        output_id="front_output",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    return card.model_copy(update={"face_identity_status": "active", "face_slots": face_slots})


def test_doc244_expression_slot_result_carries_per_slot_formal_receipt_after_three_reviewed_candidates() -> None:
    generator = _ExpressionGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_ExpressionReviewer())

    result = service.prepare_expression_slot(
        _card_with_active_front(),
        expression="anger",
        front_output_id="front_output",
        user_intent="explicit anger profile",
    )

    assert [request.candidate_index for request in generator.requests] == [1, 2, 3]
    assert result.winner_output_ids == {"expression.anger": "output_expression.anger_3"}
    formal_receipts = getattr(result, "formal_slot_receipts", {})
    assert set(formal_receipts) == {"expression.anger"}
    receipt = formal_receipts["expression.anger"]
    assert receipt.module == "expression_set"
    assert receipt.slot_key == "expression.anger"
    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_output_id == "output_expression.anger_3"
    assert receipt.activation_eligible is False


def test_doc244_expression_set_carries_existing_formal_receipts_during_partial_resume() -> None:
    generator = _ExpressionGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_ExpressionReviewer())
    base_card = _card_with_active_front()
    existing_result = service.prepare_expression_slot(
        base_card,
        expression="anger",
        front_output_id="front_output",
        user_intent="explicit anger profile",
    )
    existing_anger = existing_result.card.expression_slots["expression.anger"]
    assert existing_anger.formal_slot_receipt is not None
    card_with_existing_anger = base_card.model_copy(
        update={
            "expression_set_status": "reviewing",
            "expression_slots": {
                **base_card.expression_slots,
                "expression.anger": existing_anger,
            },
        }
    )

    generator.requests.clear()
    result = service.prepare_expression_set(
        card_with_existing_anger,
        front_output_id="front_output",
        user_intents={
            "laugh": "default laugh profile",
            "anger": "existing anger profile",
            "sad": "default sad profile",
        },
    )

    assert result.status == "review"
    assert result.winner_output_ids["expression.anger"] == existing_anger.output_id
    assert "expression.anger" in result.formal_slot_receipts
    assert result.formal_slot_receipts["expression.anger"].winner_output_id == existing_anger.output_id
    assert [request.slot_key for request in generator.requests] == [
        "expression.laugh",
        "expression.laugh",
        "expression.laugh",
        "expression.sad",
        "expression.sad",
        "expression.sad",
    ]


def test_doc244_expression_formal_core_filters_enhanced_ineligible_candidate_before_ranking() -> None:
    generator = _ExpressionGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_ExpressionReviewer(missing_laugh_evidence_indexes={3}),
    )

    result = service.prepare_expression_slot(
        _card_with_active_front(),
        expression="laugh",
        front_output_id="front_output",
        user_intent="explicit laugh profile",
    )

    assert [request.candidate_index for request in generator.requests] == [1, 2, 3]
    assert result.winner_output_ids == {"expression.laugh": "output_expression.laugh_2"}
    receipt = result.formal_slot_receipts["expression.laugh"]
    assert receipt.winner_candidate_id == "candidate_expression.laugh_2"
    assert receipt.candidates[2].shared_review.passed is True
    assert receipt.candidates[2].enhanced_proof is not None
    assert receipt.candidates[2].enhanced_proof.eligible is False
    assert [candidate.selected_as_winner for candidate in receipt.candidates] == [False, True, False]


def test_doc244_expression_formal_core_blocks_when_all_enhanced_profiles_fail() -> None:
    service = CharacterCardPreparationService(
        generator=_ExpressionGenerator(),
        reviewer=_ExpressionReviewer(missing_laugh_evidence_indexes={1, 2, 3}),
    )

    result = service.prepare_expression_slot(
        _card_with_active_front(),
        expression="laugh",
        front_output_id="front_output",
        user_intent="explicit laugh profile",
    )

    assert result.status == "blocked"
    assert result.winner_output_ids == {}
    assert result.formal_slot_receipts == {}
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"


def test_doc244_expression_stage_level_runtime_receipt_cannot_replace_per_slot_formal_receipts() -> None:
    card = CharacterCardState.initial(card_version_id="card_expression_legacy_runtime")
    expression_slots = {
        "expression.neutral": CharacterCardSlot(
            slot_key="expression.neutral",
            module="expression_set",
            state="active",
            is_alias=True,
            alias_of="face.front",
            review_verified=True,
            prompt_reference_parity_verified=True,
        ),
        "expression.laugh": CharacterCardSlot(
            slot_key="expression.laugh",
            module="expression_set",
            state="winner_selected",
            output_id="output_laugh_3",
            source_candidate_ids=["candidate_laugh_3"],
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
            shared_runtime_receipt=_legacy_slot_success_receipt("expression.laugh", "output_laugh_3"),
        ),
        "expression.anger": CharacterCardSlot(
            slot_key="expression.anger",
            module="expression_set",
            state="winner_selected",
            output_id="output_anger_3",
            source_candidate_ids=["candidate_anger_3"],
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
            shared_runtime_receipt=_legacy_slot_success_receipt("expression.anger", "output_anger_3"),
        ),
        "expression.sad": CharacterCardSlot(
            slot_key="expression.sad",
            module="expression_set",
            state="winner_selected",
            output_id="output_sad_3",
            source_candidate_ids=["candidate_sad_3"],
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
            shared_runtime_receipt=_legacy_slot_success_receipt("expression.sad", "output_sad_3"),
        ),
    }
    card = card.model_copy(
        update={
            "expression_set_status": "reviewing",
            "expression_slots": expression_slots,
        }
    )

    with pytest.raises(ValueError, match="formal"):
        CharacterCardPreparationService.activate_module(card, module="expression_set", confirmed=True)


def test_doc244_expression_formal_receipt_becomes_public_safe_only_after_projection_verification() -> None:
    service = CharacterCardPreparationService(generator=_ExpressionGenerator(), reviewer=_ExpressionReviewer())
    result = service.prepare_expression_slot(
        _card_with_active_front(),
        expression="anger",
        front_output_id="front_output",
        user_intent="explicit anger profile",
    )
    shared_runtime = CharacterCardSharedRuntimeReceipt(
        reviewed_candidate_count=3,
        acceptance_mode="standard_three_candidate",
        final_winner_selection_verified=True,
        prompt_reference_parity_verified=True,
        shared_review_receipts=[_generic_expression_shared_receipt()],
    )
    attached = result.model_copy(update={"shared_runtime_receipt": shared_runtime})

    persisted = VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
        attached,
        stage="expression_set",
    )
    slot = persisted.expression_slots["expression.anger"]

    assert slot.formal_slot_receipt is not None
    assert slot.formal_slot_receipt.reload_public_projection_verified is False
    assert slot.formal_slot_receipt.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        character_card_formal_slot_receipt_public_summary(slot)

    verified = VisualAssetLibraryLifecycleService._mark_expression_formal_receipts_after_projection(persisted)
    verified_slot = verified.expression_slots["expression.anger"]
    summary = character_card_formal_slot_receipt_public_summary(verified_slot)
    assert summary is not None
    assert summary["activation_eligible"] is True
    assert summary["acceptance_mode"] == "standard_three_candidate"
    assert summary["reviewed_candidate_count"] == 3
