from __future__ import annotations

from pathlib import Path

from services.alchemy_codex_local_adapter.provenance import renderer_parity_receipt
from services.alchemy_codex_local_adapter.professional_binding import (
    persistent_professional_binding_resolver,
)
from alchemy_creative_agent_3_0.app.visual_assets import PersistentVisualAssetCatalog
from alchemy_creative_agent_3_0.app.visual_assets import (
    CharacterCardSlot,
    CharacterCardState,
    LibraryVisualAssetCreateRequest,
    PersistentVisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.app.visual_assets.formal_slot_acceptance import (
    FormalSlotCandidateSummary,
    FormalSlotReceipt,
    FormalSlotRequirementSummary,
    FormalSlotSharedReviewSummary,
)
from alchemy_creative_agent_3_0.tests.professional_mode_test_support import (
    catalog_with_active_face_identity_pack,
)


def test_renderer_parity_requires_exact_host_contract() -> None:
    expected = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1024",
        "quality": "medium",
        "output_format": "png",
    }
    verified = renderer_parity_receipt(expected_contract=expected, actual_contract=dict(expected))
    assert verified["state"] == "verified"
    assert verified["reason_code"] is None
    assert verified["conversation_only"] is True

    blocked = renderer_parity_receipt(
        expected_contract=expected,
        actual_contract={**expected, "size": "1086x1448"},
    )
    assert blocked["state"] == "blocked"
    assert blocked["mismatch_fields"] == ["size"]
    assert blocked["reason_code"] == "renderer_contract_mismatch"


def test_renderer_parity_does_not_infer_missing_model_or_quality() -> None:
    receipt = renderer_parity_receipt(
        expected_contract={"model": "gpt-image-2", "size": "1024x1024"},
        actual_contract={"renderer": "codex_builtin_imagegen", "size": "1024x1024"},
    )
    assert receipt["state"] == "blocked"
    assert set(receipt["missing_fields"]) == {"model", "quality", "output_format"}


def test_persistent_professional_resolver_uses_only_catalog_metadata(tmp_path: Path) -> None:
    source = catalog_with_active_face_identity_pack()
    catalog = PersistentVisualAssetCatalog(tmp_path)
    asset = source.get("project_professional", "person_1")
    assert asset is not None
    pack = source.get_pack("project_professional", "person_1", "pack_1")
    assert pack is not None
    catalog.save_pack(pack, project_id="project_professional", event_type="activate")
    catalog.save(asset, project_id="project_professional", event_type="activate")

    resolver = persistent_professional_binding_resolver(tmp_path)
    binding = resolver(
        project_id="project_professional",
        people_asset_id="person_1",
        job_id="job_1",
        reference_view_ids=["front_1", "three_quarter_1", "profile_1"],
    )
    assert binding is not None
    assert binding.mode == "professional"
    assert binding.pack_version_id == "pack_1"
    assert binding.identity_view_ids == ["front_1", "three_quarter_1", "profile_1"]


def _library_formal_receipt(*, slot_role: str, output_id: str) -> FormalSlotReceipt:
    shared = FormalSlotSharedReviewSummary(
        status="pass",
        evidence_codes=["shared_real_pixel_review_verified"],
        score_dimensions=["identity_or_subject_consistency", "generic_visual_quality"],
        framing_delta_dimensions=["face_identity_view_framing_delta"],
    )
    candidates = [
        FormalSlotCandidateSummary(
            candidate_index=index,
            candidate_id=f"candidate_{slot_role}_{index}",
            output_id=output_id if index == 3 else f"{output_id}_{index}",
            reviewed=True,
            selected_as_winner=index == 3,
            shared_review=shared,
        )
        for index in (1, 2, 3)
    ]
    requirement = FormalSlotRequirementSummary(
        status="pass",
        evidence_codes=["face_identity_reference_parity_verified"],
        dimensions={"summary_score": 0.95},
    )
    return FormalSlotReceipt(
        module="face_identity",
        slot_key=f"face_identity.{slot_role}",
        acceptance_mode="standard_three_candidate",
        reviewed_candidate_count=3,
        candidates=candidates,
        winner_candidate_id=f"candidate_{slot_role}_3",
        winner_output_id=output_id,
        winner_shared_review=shared,
        framing_summary=requirement,
        parity_summary=requirement,
        identity_summary=requirement,
        reload_public_projection_verified=True,
    )


def test_persistent_professional_resolver_reads_active_character_card_library_slot(tmp_path: Path) -> None:
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path / "visual-asset-library")
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="Fresh Professional Character Card Rebuild",
            asset_type="people",
            root_source_asset_id="v3_asset_root",
            consent_reference="user_confirmed_visual_asset_use",
            preparation_intent="Use the reviewed Character Card as the Professional identity source.",
        ),
    )
    asset = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        version_id="version_character_card_active",
        approved_evidence_ids=["formal_character_card_evidence"],
    )
    card = CharacterCardState.initial(card_version_id="card_character_active")
    card = card.model_copy(
        update={
            "face_identity_status": "active",
            "face_identity_version_id": "face_identity_character_active",
            "face_slots": {
                **card.face_slots,
                "face.front": CharacterCardSlot(
                    slot_key="face.front",
                    module="face_identity",
                    state="active",
                    output_id="v3_output_front_active",
                    source_candidate_ids=[
                        "candidate_standard_front_1",
                        "candidate_standard_front_2",
                        "candidate_standard_front_3",
                    ],
                    review_verified=True,
                    prompt_reference_parity_verified=True,
                    formal_slot_receipt=_library_formal_receipt(
                        slot_role="standard_front",
                        output_id="v3_output_front_active",
                    ),
                ),
            },
        }
    )
    catalog.save(asset.model_copy(update={"character_card": card}))

    resolver = persistent_professional_binding_resolver(tmp_path / "visual-asset-library")
    binding = resolver(
        project_id="local_default",
        people_asset_id=asset.visual_asset_id,
        job_id="job_character_card",
        reference_view_ids=["v3_output_front_active"],
    )

    assert binding is not None
    assert binding.mode == "professional"
    assert binding.project_id == "local_default"
    assert binding.people_asset_id == asset.visual_asset_id
    assert binding.pack_version_id == "face_identity_character_active"
    assert binding.identity_view_ids == ["v3_output_front_active"]
