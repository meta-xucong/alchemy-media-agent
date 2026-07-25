"""Doc245 / Task7 Body Silhouette formal-slot receipt seam contracts."""

from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import AnchorReviewDecision
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BODY_SLOT_KEYS,
    CharacterCardCandidateRequest,
    CharacterCardCandidateResult,
    CharacterCardPreparationService,
    CharacterCardSharedRuntimeReceipt,
    CharacterCardSlot,
    CharacterCardState,
    character_card_formal_slot_receipt_public_summary,
    project_character_card_slot_success_receipt,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import IdentityScoreSummary
from alchemy_creative_agent_3_0.app.visual_assets.library import VisualAssetLibraryLifecycleService


def _generic_body_shared_receipt(*, status: str = "pass") -> dict[str, object]:
    return {
        "owner": "v3_shared_visual_cluster",
        "contract_version": "v3_character_card_generic_slot_review_receipt_v1",
        "status": status,
        "evidence_codes": [
            "shared_visual_review_verified",
            "shared_visual_review_status_pass",
            "body_silhouette_framing_reviewed",
        ]
        if status == "pass"
        else ["shared_visual_review_unverified"],
        "issue_codes": [] if status == "pass" else ["shared_visual_review_rejected"],
        "score_dimensions": ["generic_visual_quality", "identity_or_subject_consistency"],
        "framing_delta_dimensions": ["body_scale_delta", "ground_contact_delta"],
    }


def _legacy_body_slot_success_receipt(slot_key: str, output_id: str) -> dict[str, object]:
    shared_reviews = [_generic_body_shared_receipt()]
    return project_character_card_slot_success_receipt(
        CharacterCardSharedRuntimeReceipt(
            reviewed_candidate_count=3,
            acceptance_mode="standard_three_candidate",
            final_winner_selection_verified=True,
            prompt_reference_parity_verified=True,
            shared_review_receipts=shared_reviews,
        ),
        module="body_silhouette",
        slot_key=slot_key,
        output_id=output_id,
        shared_review_receipts=shared_reviews,
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


def _review(index: int, *, status: str = "pass", body_eligible: bool = True) -> AnchorReviewDecision:
    issue_codes = [] if status == "pass" else ["candidate_failed"]
    if not body_eligible:
        issue_codes.append("body_silhouette_profile_rejected")
    return AnchorReviewDecision(
        status=status,  # type: ignore[arg-type]
        identity_scores=_scores(index, body_eligible=body_eligible),
        issue_codes=issue_codes,
        shared_review_receipts=[_generic_body_shared_receipt(status=status)],
    )


class _BodyGenerator:
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


class _BodyReviewer:
    def __init__(
        self,
        *,
        failing_indexes: set[int] | None = None,
        enhanced_failing_indexes: set[int] | None = None,
    ) -> None:
        self.failing_indexes = set(failing_indexes or set())
        self.enhanced_failing_indexes = set(enhanced_failing_indexes or set())

    def review(self, candidate: CharacterCardCandidateResult) -> AnchorReviewDecision:
        return _review(
            candidate.candidate_index,
            status="fail" if candidate.candidate_index in self.failing_indexes else "pass",
            body_eligible=candidate.candidate_index not in self.enhanced_failing_indexes,
        )


def _card_ready_for_body() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_body_formal")
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


def test_doc245_body_slot_result_carries_per_slot_formal_receipt_after_three_reviewed_candidates() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert [request.slot_key for request in generator.requests] == [
        "body.front_full",
        "body.front_full",
        "body.front_full",
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
    assert set(result.winner_output_ids) == set(BODY_SLOT_KEYS)
    assert set(result.formal_slot_receipts) == set(BODY_SLOT_KEYS)
    receipt = result.formal_slot_receipts["body.front_full"]
    assert receipt.module == "body_silhouette"
    assert receipt.slot_key == "body.front_full"
    assert receipt.acceptance_mode == "standard_three_candidate"
    assert receipt.reviewed_candidate_count == 3
    assert receipt.winner_output_id == "output_body.front_full_3"
    assert receipt.activation_eligible is False


def test_doc245_body_preparation_does_not_require_whole_expression_set_activation() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    card = _card_ready_for_body().model_copy(update={"expression_set_status": "partial"})

    result = service.prepare_body_silhouette(
        card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert result.winner_output_ids["body.front_full"] == "output_body.front_full_3"
    assert result.formal_slot_receipts["body.front_full"].acceptance_mode == "standard_three_candidate"


def test_doc245_body_formal_core_filters_enhanced_ineligible_candidate_before_ranking() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_BodyReviewer(enhanced_failing_indexes={3}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    receipt = result.formal_slot_receipts["body.front_full"]
    assert receipt.winner_candidate_id == "candidate_body.front_full_2"
    assert receipt.candidates[2].shared_review.passed is True
    assert receipt.candidates[2].enhanced_proof is not None
    assert receipt.candidates[2].enhanced_proof.eligible is False


def test_doc245_body_formal_core_blocks_when_all_enhanced_profiles_fail() -> None:
    service = CharacterCardPreparationService(
        generator=_BodyGenerator(),
        reviewer=_BodyReviewer(enhanced_failing_indexes={1, 2, 3}),
    )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "blocked"
    assert result.winner_output_ids == {}
    assert result.formal_slot_receipts == {}
    assert result.failures[-1].failure_code == "character_card_formal_slot_receipt_invalid"


def test_doc245_body_stage_level_runtime_receipt_cannot_replace_per_slot_formal_receipts() -> None:
    card = _card_ready_for_body()
    body_slots = {}
    for slot_key in BODY_SLOT_KEYS:
        body_slots[slot_key] = CharacterCardSlot(
            slot_key=slot_key,
            module="body_silhouette",
            state="winner_selected",
            output_id=f"output_{slot_key}_3",
            source_candidate_ids=[f"candidate_{slot_key}_3"],
            source_class="brain_inferred",
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
            shared_runtime_receipt=_legacy_body_slot_success_receipt(slot_key, f"output_{slot_key}_3"),
        )
    card = card.model_copy(update={"body_silhouette_status": "reviewing", "body_slots": body_slots})

    with pytest.raises(ValueError, match="formal"):
        CharacterCardPreparationService.activate_module(card, module="body_silhouette", confirmed=True)


def test_doc245_body_source_class_and_consent_contract_still_apply() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())

    with pytest.raises(ValueError, match="consent"):
        service.prepare_body_silhouette(
            _card_ready_for_body(),
            face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
            source_class="observed",
            body_evidence_ids=["body_reference_asset"],
            user_intent="observed body silhouette profile",
        )

    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="observed",
        body_evidence_ids=["body_reference_asset"],
        consent_provenance_id="consent_123",
        user_intent="observed body silhouette profile",
    )
    assert result.card.body_slots["body.front_full"].source_class == "observed"
    assert result.card.body_slots["body.front_full"].consent_provenance_id == "consent_123"


def test_doc245_body_formal_receipt_becomes_public_safe_only_after_projection_verification() -> None:
    service = CharacterCardPreparationService(generator=_BodyGenerator(), reviewer=_BodyReviewer())
    result = service.prepare_body_silhouette(
        _card_ready_for_body(),
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    shared_runtime = CharacterCardSharedRuntimeReceipt(
        reviewed_candidate_count=3,
        acceptance_mode="standard_three_candidate",
        final_winner_selection_verified=True,
        prompt_reference_parity_verified=True,
        shared_review_receipts=[_generic_body_shared_receipt()],
    )
    attached = result.model_copy(update={"shared_runtime_receipt": shared_runtime})

    persisted = VisualAssetLibraryLifecycleService._persist_character_card_success_receipts(
        attached,
        stage="body_silhouette",
    )
    slot = persisted.body_slots["body.front_full"]

    assert slot.formal_slot_receipt is not None
    assert slot.formal_slot_receipt.reload_public_projection_verified is False
    assert slot.formal_slot_receipt.activation_eligible is False
    with pytest.raises(ValueError, match="standard_three_candidate"):
        character_card_formal_slot_receipt_public_summary(slot)

    verified = VisualAssetLibraryLifecycleService._mark_formal_receipts_after_projection(
        persisted,
        stage="body_silhouette",
    )
    verified_slot = verified.body_slots["body.front_full"]
    summary = character_card_formal_slot_receipt_public_summary(verified_slot)
    assert summary is not None
    assert summary["activation_eligible"] is True
    assert summary["acceptance_mode"] == "standard_three_candidate"
    assert summary["reviewed_candidate_count"] == 3


def test_doc245_body_set_carries_existing_formal_receipts_during_partial_resume() -> None:
    generator = _BodyGenerator()
    service = CharacterCardPreparationService(generator=generator, reviewer=_BodyReviewer())
    base_card = _card_ready_for_body()
    existing_result = service.prepare_body_silhouette(
        base_card,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )
    existing_front = existing_result.card.body_slots["body.front_full"]
    assert existing_front.formal_slot_receipt is not None
    card_with_existing_front = base_card.model_copy(
        update={
            "body_silhouette_status": "reviewing",
            "body_slots": {
                **base_card.body_slots,
                "body.front_full": existing_front,
            },
        }
    )

    generator.requests.clear()
    result = service.prepare_body_silhouette(
        card_with_existing_front,
        face_reference_output_ids=["face_front_output", "face_profile_output", "face_rear_output"],
        source_class="brain_inferred",
        user_intent="neutral body silhouette profile",
    )

    assert result.status == "review"
    assert result.winner_output_ids["body.front_full"] == existing_front.output_id
    assert "body.front_full" in result.formal_slot_receipts
    assert result.formal_slot_receipts["body.front_full"].winner_output_id == existing_front.output_id
    assert [request.slot_key for request in generator.requests] == [
        "body.side_full",
        "body.side_full",
        "body.side_full",
        "body.rear_full",
        "body.rear_full",
        "body.rear_full",
    ]
