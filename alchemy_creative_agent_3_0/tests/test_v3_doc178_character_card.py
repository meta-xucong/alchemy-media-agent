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
    with pytest.raises(ValueError, match="Expression Set"):
        service.prepare_body_silhouette(
            card,
            face_reference_output_ids=["front", "profile", "rear"],
            source_class="brain_inferred",
        )


def test_doc178_face_update_marks_only_dependents_stale_and_keeps_history() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    updated = card.mark_face_version_stale(new_face_version_id="face_v2")
    assert updated.face_identity_status == "active"
    assert updated.expression_set_status == "stale"
    assert updated.body_silhouette_status == "stale"
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
