"""Doc178 contract-first tests for the Professional Character Card modules.

This file intentionally lands before the runtime implementation.  It fixes the
public contract that the implementation must satisfy without creating a second
provider, reviewer, retry, or storage path.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BODY_SOURCE_CLASSES,
    BODY_SLOT_KEYS,
    EXPRESSION_SLOT_KEYS,
    FACE_SLOT_KEYS,
    CharacterCardPreparationService,
    CharacterCardSlot,
    CharacterCardState,
    ExpressionPreparationRequest,
    BodyPreparationRequest,
    CharacterCardCandidateResult,
)
from alchemy_creative_agent_3_0.app.visual_assets.anchor_pack import (
    AnchorCandidateResult,
    AnchorGenerationRequest,
    AnchorPackPreparationRequest,
    AnchorPackPreparationService,
    AnchorReviewDecision,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    IdentityScoreSummary,
    PeopleAsset,
    RootSourceProvenance,
)


def test_doc178_exposes_all_slots_as_visible_empty_slots() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")

    assert set(card.face_slots) == set(FACE_SLOT_KEYS)
    assert set(card.expression_slots) == set(EXPRESSION_SLOT_KEYS)
    assert set(card.body_slots) == set(BODY_SLOT_KEYS)
    assert all(slot.state == "empty" for slot in card.all_slots())
    assert all(slot.output_id is None for slot in card.all_slots())


def test_doc178_empty_slot_requires_explicit_user_decision_when_left_empty() -> None:
    visible_empty = CharacterCardSlot(
        slot_key="face.rear_head",
        module="face_identity",
        state="empty",
        explicitly_left_empty=False,
    )
    assert visible_empty.state == "empty"

    left_empty = CharacterCardSlot(
        slot_key="face.rear_head",
        module="face_identity",
        state="empty",
        explicitly_left_empty=True,
    )
    assert left_empty.state == "empty"


def test_doc178_neutral_is_an_alias_and_never_a_generation_slot() -> None:
    neutral = CharacterCardSlot(
        slot_key="expression.neutral",
        module="expression_set",
        state="active",
        is_alias=True,
        alias_of="face.front",
        review_verified=True,
        prompt_reference_parity_verified=True,
    )
    assert neutral.output_id is None
    assert neutral.candidate_attempt_count == 0
    with pytest.raises(ValidationError, match="neutral"):
        CharacterCardSlot(
            slot_key="expression.neutral",
            module="expression_set",
            state="active",
            output_id="output_should_not_exist",
            is_alias=True,
            alias_of="face.front",
            review_verified=True,
            prompt_reference_parity_verified=True,
        )


def test_doc178_rejects_unreviewed_winner_and_wrong_module_slot() -> None:
    with pytest.raises(ValidationError, match="review"):
        CharacterCardSlot(
            slot_key="expression.smile",
            module="expression_set",
            state="winner_selected",
            output_id="output_1",
            prompt_reference_parity_verified=True,
        )
    with pytest.raises(ValidationError, match="module"):
        CharacterCardSlot(slot_key="body.front_full", module="expression_set")


def test_doc178_body_source_is_a_typed_truth_class() -> None:
    assert BODY_SOURCE_CLASSES == ("observed", "user_described", "brain_inferred")
    with pytest.raises(ValidationError):
        BodyPreparationRequest(
            source_class="measured",
            face_reference_output_ids=["front", "profile", "rear"],
        )
    inferred = BodyPreparationRequest(
        source_class="brain_inferred",
        face_reference_output_ids=["front", "profile", "rear"],
    )
    assert inferred.source_class == "brain_inferred"
    assert inferred.observed_truth is False
    with pytest.raises(ValidationError, match="consent"):
        BodyPreparationRequest(
            source_class="observed",
            face_reference_output_ids=["front", "profile", "rear"],
            body_evidence_ids=["full_body_upload"],
        )


def test_doc178_expression_requests_all_use_front_and_never_previous_expression() -> None:
    requests = [
        ExpressionPreparationRequest(
            expression=expression,
            front_output_id="front_winner",
            user_intent=f"user intent for {expression}",
        )
        for expression in ("smile", "anger", "sad")
    ]
    assert all(request.reference_output_ids == ["front_winner"] for request in requests)
    assert all(request.candidate_count == 3 for request in requests)
    with pytest.raises(ValidationError, match="front"):
        ExpressionPreparationRequest(
            expression="anger",
            front_output_id="front_winner",
            reference_output_ids=["smile_winner"],
            user_intent="anger",
        )


def test_doc178_body_requests_are_separate_from_expression_and_keep_face_as_continuity_only() -> None:
    request = BodyPreparationRequest(
        source_class="user_described",
        face_reference_output_ids=["front_winner", "profile_winner", "rear_winner"],
        body_evidence_ids=["height_note_1"],
    )
    assert request.reference_output_ids == ["front_winner", "profile_winner", "rear_winner"]
    assert request.candidate_count == 3
    assert request.wardrobe_lock is False
    with pytest.raises(ValidationError, match="Face Identity"):
        BodyPreparationRequest(source_class="observed", face_reference_output_ids=[])


def test_doc178_ordered_stage_gate_blocks_expression_and_body_before_face() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    service = CharacterCardPreparationService(generator=None, reviewer=None)
    with pytest.raises(ValueError, match="Face Identity"):
        service.prepare_expression_set(card, front_output_id="front_winner")
    with pytest.raises(ValueError, match="Face Identity"):
        service.prepare_body_silhouette(
            card,
            face_reference_output_ids=["front", "profile", "rear"],
            source_class="brain_inferred",
        )
    face_ready = card.model_copy(update={"face_identity_status": "active"})
    with pytest.raises(ValueError, match="Expression Set"):
        service.prepare_body_silhouette(
            face_ready,
            face_reference_output_ids=["front", "profile", "rear"],
            source_class="brain_inferred",
        )


def test_doc178_face_update_marks_only_dependents_stale_and_keeps_history() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    updated = card.mark_face_version_stale(new_face_version_id="face_v2")
    assert updated.face_identity_status == card.face_identity_status
    assert updated.expression_set_status == "empty"
    assert updated.body_silhouette_status == "empty"
    assert updated.append_only_revision > card.append_only_revision
    assert card.card_version_id != updated.card_version_id


def test_doc178_has_no_local_prompt_or_private_runtime_fields() -> None:
    fields = set(CharacterCardState.model_fields) | set(CharacterCardSlot.model_fields)
    forbidden = {"prompt", "negative_prompt", "provider", "reviewer", "retry", "storage_path"}
    assert not fields.intersection(forbidden)


def test_doc178_standard_mode_does_not_acquire_character_card_metadata() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    assert card.mode == "professional"
    assert CharacterCardState.model_validate(card.model_dump()).mode == "professional"


class _Doc178FaceGenerator:
    def __init__(self) -> None:
        self.requests: list[AnchorGenerationRequest] = []

    def generate(self, request: AnchorGenerationRequest) -> AnchorCandidateResult:
        self.requests.append(request)
        token = f"{request.view_role}_{request.candidate_index}"
        return AnchorCandidateResult(
            candidate_id=f"candidate_{token}",
            view_id=f"view_{token}",
            output_id=f"output_{token}",
            view_role=request.view_role,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"candidate_{token}"],
            source_asset_ids=["root_1"],
            brain_plan_id=f"brain_{token}",
            canonical_prompt_hash=f"sha256:{token}",
            prompt_compilation_id=f"prompt_{token}",
            prompt_reference_parity_verified=True,
        )


class _Doc178FaceReviewer:
    def review(self, candidate: AnchorCandidateResult) -> AnchorReviewDecision:
        return AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=0.9,
                distinctive_feature_score=0.9,
                human_realism_score=0.9,
                visual_quality_score=0.9,
            ),
        )


def _doc178_face_request() -> AnchorPackPreparationRequest:
    intent = "one person, neutral identity evidence capture"
    asset = PeopleAsset(
        people_asset_id="people_1",
        project_id="project_1",
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(module_id="face_1", people_asset_id="people_1"),
        preparation_intent=intent,
    )
    return AnchorPackPreparationRequest(
        project_id="project_1",
        asset=asset,
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="root_1",
            project_id="project_1",
        ),
        preparation_intent=intent,
        brain_plan_id="brain_1",
        canonical_prompt_hash="sha256:prompt",
    )


def test_doc178_face_extension_reuses_existing_serial_host_for_two_new_slots() -> None:
    generator = _Doc178FaceGenerator()
    service = AnchorPackPreparationService(generator=generator, reviewer=_Doc178FaceReviewer())
    result = CharacterCardPreparationService.prepare_face_identity_extension(service, _doc178_face_request())

    assert result.status == "review"
    assert len(result.attempts) == 21
    assert [view.view_role for view in result.pack.anchor_views] == [
        "standard_front",
        "left_front_25",
        "three_quarter",
        "profile",
        "right_front_25",
        "reverse_three_quarter",
        "rear_head",
    ]
    reverse_request = next(
        request for request in generator.requests if request.view_role == "reverse_three_quarter"
    )
    assert reverse_request.reference_evidence_ids == [
        "root_1",
        "output_standard_front_3",
        "output_profile_3",
        "output_right_front_25_3",
    ]
    assert generator.requests[-1].reference_evidence_ids == [
        "root_1",
        "output_standard_front_3",
        "output_profile_3",
        "output_reverse_three_quarter_3",
    ]


def _doc178_face_ready_card() -> CharacterCardState:
    card = CharacterCardState.initial(card_version_id="card_1")
    front = CharacterCardSlot(
        slot_key="face.front",
        module="face_identity",
        state="active",
        output_id="front_winner",
        source_candidate_ids=["front_candidate_1"],
        lineage_id="lineage_front",
        review_verified=True,
        prompt_reference_parity_verified=True,
        candidate_attempt_count=3,
    )
    return card.model_copy(update={"face_identity_status": "active", "face_slots": {**card.face_slots, "face.front": front}})


class _Doc178ExpressionBodyGenerator:
    def __init__(self) -> None:
        self.requests = []

    def generate(self, request):
        self.requests.append(request)
        token = f"{request.slot_key}_{request.candidate_index}"
        return CharacterCardCandidateResult(
            candidate_id=f"candidate_{token}",
            output_id=f"output_{token}",
            module=request.module,
            slot_key=request.slot_key,
            candidate_index=request.candidate_index,
            source_candidate_ids=[f"candidate_{token}"],
            source_output_ids=list(request.reference_output_ids),
            canonical_prompt_hash=f"sha256:{token}",
            prompt_compilation_id=f"compile_{token}",
            prompt_reference_parity_verified=True,
        )


class _Doc178ExpressionBodyReviewer:
    def review(self, candidate):
        return AnchorReviewDecision(
            status="pass",
            identity_scores=IdentityScoreSummary(
                same_face_score=0.9,
                distinctive_feature_score=0.9,
                human_realism_score=0.9,
                visual_quality_score=0.9,
            ),
        )


def test_doc178_expression_and_body_are_independent_three_candidate_stages() -> None:
    generator = _Doc178ExpressionBodyGenerator()
    service = CharacterCardPreparationService(
        generator=generator,
        reviewer=_Doc178ExpressionBodyReviewer(),
    )
    expression = service.prepare_expression_set(
        _doc178_face_ready_card(),
        front_output_id="front_winner",
        user_intents={"smile": "smile intent", "anger": "anger intent", "sad": "sad intent"},
    )
    assert expression.status == "review"
    assert expression.card.expression_slots["expression.neutral"].is_alias is True
    assert expression.card.expression_set_status == "reviewing"
    assert len(generator.requests) == 9
    assert all(request.reference_output_ids == ["front_winner"] for request in generator.requests)

    activated_expression = service.activate_module(
        expression.card,
        module="expression_set",
        confirmed=True,
    )
    body = service.prepare_body_silhouette(
        activated_expression,
        face_reference_output_ids=["front_winner", "profile_winner", "rear_winner"],
        source_class="brain_inferred",
        user_intent="Brain-owned neutral body continuity direction",
    )
    assert body.status == "review"
    body_requests = generator.requests[9:]
    assert len(body_requests) == 9
    assert all(request.reference_output_ids == ["front_winner", "profile_winner", "rear_winner"] for request in body_requests)
    assert all(request.source_class == "brain_inferred" for request in body_requests)
    assert body.card.body_slots["body.front_full"].source_class == "brain_inferred"
    assert body.card.body_slots["body.front_full"].state == "winner_selected"


def test_doc178_generation_does_not_invent_expression_or_body_intent_locally() -> None:
    service = CharacterCardPreparationService(
        generator=_Doc178ExpressionBodyGenerator(),
        reviewer=_Doc178ExpressionBodyReviewer(),
    )
    with pytest.raises(ValueError, match="Brain/user-owned expression intent"):
        service.prepare_expression_set(_doc178_face_ready_card(), front_output_id="front_winner")
    face_and_expression = _doc178_face_ready_card().model_copy(update={"expression_set_status": "active"})
    with pytest.raises(ValueError, match="Brain/user-owned body preparation intent"):
        service.prepare_body_silhouette(
            face_and_expression,
            face_reference_output_ids=["front", "profile", "rear"],
            source_class="brain_inferred",
        )
