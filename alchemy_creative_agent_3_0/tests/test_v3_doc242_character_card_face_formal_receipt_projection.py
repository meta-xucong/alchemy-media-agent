from __future__ import annotations

from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    CharacterCardSlot,
    CharacterCardState,
    apply_face_identity_pack_to_card,
    character_card_formal_slot_receipt_public_summary,
)
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    AnchorAuxiliaryReference,
    AnchorView,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
)


FORMAL_ROLE_TO_CARD_SLOT = {
    "standard_front": "face.front",
    "three_quarter": "face.front_three_quarter",
    "profile": "face.profile",
    "reverse_three_quarter": "face.reverse_three_quarter",
    "rear_head": "face.rear_head",
}


def _shared_review() -> FormalSlotSharedReviewSummary:
    return FormalSlotSharedReviewSummary(
        status="pass",
        evidence_codes=["shared_visual_review_verified"],
        score_dimensions=["identity_or_subject_consistency", "generic_visual_quality"],
        framing_delta_dimensions=["face_identity_view_framing_delta"],
    )


def _requirement(code: str) -> FormalSlotRequirementSummary:
    return FormalSlotRequirementSummary(
        status="pass",
        evidence_codes=[code],
        dimensions={"summary_score": 0.93},
    )


def _formal_receipt(
    role: str,
    *,
    module: str = "face_identity",
    slot_key: str | None = None,
    winner_output_id: str | None = None,
    winner_candidate_id: str | None = None,
    acceptance_mode: str = "standard_three_candidate",
) -> FormalSlotReceipt:
    slot_key = slot_key or f"face_identity.{role}"
    output_id = winner_output_id or f"output_{role}_3"
    candidate_id = winner_candidate_id or f"candidate_{role}_3"
    candidates = [
        FormalSlotCandidateSummary(
            candidate_index=index,
            candidate_id=f"candidate_{role}_{index}" if index != 3 else candidate_id,
            output_id=f"output_{role}_{index}" if index != 3 else output_id,
            reviewed=True,
            selected_as_winner=index == 3,
            shared_review=_shared_review(),
        )
        for index in (1, 2, 3)
    ]
    return FormalSlotReceipt(
        module=module,
        slot_key=slot_key,
        acceptance_mode=acceptance_mode,  # type: ignore[arg-type]
        reviewed_candidate_count=3,
        candidates=candidates,
        winner_candidate_id=candidate_id,
        winner_output_id=output_id,
        winner_shared_review=_shared_review(),
        framing_summary=_requirement("face_identity_view_profile_reviewed"),
        parity_summary=_requirement("face_identity_reference_parity_verified"),
        identity_summary=_requirement("face_identity_shared_identity_review_verified"),
        reload_public_projection_verified=True,
    )


def _target_only_receipt(role: str) -> FormalSlotReceipt:
    candidate = FormalSlotCandidateSummary(
        candidate_index=1,
        candidate_id=f"candidate_{role}_1",
        output_id=f"output_{role}_1",
        reviewed=True,
        selected_as_winner=True,
        shared_review=_shared_review(),
    )
    return FormalSlotReceipt(
        module="face_identity",
        slot_key=f"face_identity.{role}",
        acceptance_mode="target_only_existing_candidate_collection",
        reviewed_candidate_count=1,
        candidates=[candidate],
        winner_candidate_id=candidate.candidate_id,
        winner_output_id=candidate.output_id,
        winner_shared_review=candidate.shared_review,
        framing_summary=_requirement("face_identity_view_profile_reviewed"),
        parity_summary=_requirement("face_identity_reference_parity_verified"),
        identity_summary=_requirement("face_identity_shared_identity_review_verified"),
        reload_public_projection_verified=True,
    )


def _bridge_receipt(role: str = "left_front_25") -> FormalSlotReceipt:
    candidate = FormalSlotCandidateSummary(
        candidate_index=1,
        candidate_id=f"candidate_bridge_{role}_1",
        output_id=f"output_bridge_{role}_1",
        reviewed=True,
        selected_as_winner=True,
        shared_review=_shared_review(),
    )
    return FormalSlotReceipt(
        module="face_identity",
        slot_key=f"face_identity_bridge.{role}",
        acceptance_mode="auxiliary_first_pass_reference",
        slot_scope="auxiliary_reference",
        reviewed_candidate_count=1,
        candidates=[candidate],
        winner_candidate_id=candidate.candidate_id,
        winner_output_id=candidate.output_id,
        winner_shared_review=candidate.shared_review,
        framing_summary=_requirement("face_identity_view_profile_reviewed"),
        parity_summary=_requirement("face_identity_reference_parity_verified"),
        identity_summary=_requirement("face_identity_shared_identity_review_verified"),
        reload_public_projection_verified=True,
    )


def _identity_scores() -> IdentityScoreSummary:
    return IdentityScoreSummary(
        same_face_score=0.94,
        visual_quality_score=0.91,
        evidence_codes=["face_geometry_match"],
    )


def _view(role: str, *, receipt: FormalSlotReceipt | None = None) -> AnchorView:
    receipt = receipt or _formal_receipt(role)
    return AnchorView(
        view_id=f"view_{role}",
        view_role=role,  # type: ignore[arg-type]
        output_id=str(receipt.winner_output_id),
        source_candidate_ids=[candidate.candidate_id for candidate in receipt.candidates],
        identity_scores=_identity_scores(),
        formal_slot_receipt=receipt,
    )


def _pack(*, views: list[AnchorView], status: str = "active") -> IdentityAnchorPackVersion:
    return IdentityAnchorPackVersion(
        pack_version_id="pack_formal_1",
        people_asset_id="person_1",
        status=status,  # type: ignore[arg-type]
        anchor_views=views,
        auxiliary_references=[
            AnchorAuxiliaryReference(
                reference_id="bridge_left_25",
                reference_role="left_front_25",
                output_id="output_bridge_left_front_25_1",
                source_candidate_ids=["candidate_bridge_left_front_25_1"],
                identity_scores=_identity_scores(),
                formal_slot_receipt=_bridge_receipt("left_front_25"),
            )
        ],
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="asset_root_1",
            project_id="project_1",
        ),
        user_activation_confirmed=status == "active",
    )


def test_task5_projects_all_formal_face_receipts_into_character_card_slots() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    pack = _pack(views=[_view(role) for role in FORMAL_ROLE_TO_CARD_SLOT])

    projected = apply_face_identity_pack_to_card(card, pack)

    for role, slot_key in FORMAL_ROLE_TO_CARD_SLOT.items():
        slot = projected.face_slots[slot_key]
        assert slot.state == "active"
        assert slot.output_id == f"output_{role}_3"
        assert slot.formal_slot_receipt is not None
        assert slot.formal_slot_receipt.slot_key == f"face_identity.{role}"
        assert slot.formal_slot_receipt.acceptance_mode == "standard_three_candidate"
        assert slot.formal_slot_receipt.reviewed_candidate_count == 3
        assert slot.shared_runtime_receipt is None

    assert projected.face_slots["face.left_front_25"].state == "empty"
    assert projected.face_slots["face.right_front_25"].state == "empty"


@pytest.mark.parametrize(
    "receipt",
    [
        None,
        _formal_receipt("standard_front", module="expression_set"),
        _formal_receipt("standard_front", slot_key="face_identity.profile"),
        _formal_receipt("standard_front", winner_output_id="output_other"),
        _formal_receipt("standard_front", winner_candidate_id="candidate_other"),
        _target_only_receipt("standard_front"),
        _bridge_receipt("left_front_25"),
    ],
)
def test_task5_face_projection_requires_matching_standard_formal_receipt(
    receipt: FormalSlotReceipt | None,
) -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    view = SimpleNamespace(
        view_id="view_standard_front",
        view_role="standard_front",
        output_id="output_standard_front_3",
        source_candidate_ids=["candidate_standard_front_1", "candidate_standard_front_2", "candidate_standard_front_3"],
        active=True,
        formal_slot_receipt=receipt,
    )
    pack = SimpleNamespace(
        pack_version_id="pack_1",
        status="active",
        anchor_views=[view],
    )

    with pytest.raises((ValueError, ValidationError)):
        apply_face_identity_pack_to_card(card, pack)


def test_task5_old_boolean_face_slot_without_formal_receipt_fails_closed() -> None:
    with pytest.raises(ValidationError):
        CharacterCardSlot(
            slot_key="face.front",
            module="face_identity",
            state="active",
            output_id="output_legacy",
            source_candidate_ids=["candidate_1", "candidate_2", "candidate_3"],
            review_verified=True,
            prompt_reference_parity_verified=True,
            candidate_attempt_count=3,
        )


def test_task5_catalog_style_reload_preserves_face_formal_receipt_and_public_summary_is_safe() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    pack = _pack(views=[_view(role) for role in FORMAL_ROLE_TO_CARD_SLOT])

    projected = apply_face_identity_pack_to_card(card, pack)
    reloaded = CharacterCardState.model_validate(projected.model_dump(mode="json"))
    slot = reloaded.face_slots["face.front"]
    summary = character_card_formal_slot_receipt_public_summary(slot)

    assert slot.formal_slot_receipt is not None
    assert summary is not None
    assert summary["activation_eligible"] is True
    assert summary["acceptance_mode"] == "standard_three_candidate"
    serialized = str(summary).lower()
    for forbidden in ("prompt", "provider", "mcp", "handoff", "artifact", "path"):
        assert forbidden not in serialized


def test_task5_route_public_projection_exposes_face_formal_summary_only() -> None:
    card = CharacterCardState.initial(card_version_id="card_1")
    pack = _pack(views=[_view(role) for role in FORMAL_ROLE_TO_CARD_SLOT])
    projected = apply_face_identity_pack_to_card(card, pack)

    class Asset:
        visual_asset_id = "asset_1"
        display_name = "Character"
        asset_type = "people"
        lifecycle_status = "active"
        active_version_id = None
        character_card = projected
        versions: list[object] = []

        def active_version(self) -> object | None:
            return None

    public = V3ProductRouteHandlers._visual_asset_public_record(Asset())
    front = public["character_card"]["slots"]["face.front"]

    assert front["formal_slot_receipt_verified"] is True
    assert front["formal_slot_receipt"]["acceptance_mode"] == "standard_three_candidate"
    assert "shared_runtime_receipt" not in front
    serialized = str(front).lower()
    for forbidden in ("prompt", "provider", "mcp", "handoff", "artifact", "path"):
        assert forbidden not in serialized


def test_task5_bridge_receipt_cannot_be_used_as_formal_face_slot() -> None:
    with pytest.raises(ValidationError):
        CharacterCardSlot(
            slot_key="face.left_front_25",
            module="face_identity",
            state="active",
            output_id="output_bridge_left_front_25_1",
            source_candidate_ids=["candidate_bridge_left_front_25_1"],
            formal_slot_receipt=_bridge_receipt("left_front_25"),
        )
