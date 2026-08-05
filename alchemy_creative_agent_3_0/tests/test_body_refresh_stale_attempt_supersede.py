"""Red tests for closing an unrecoverable interrupted Body refresh attempt."""

from __future__ import annotations

from pathlib import Path

from test_body_analysis_profile_lifecycle_freeze import (
    BodySilhouettePublicRequest,
    _library_refresh_fixture,
    _profile_context,
)

from alchemy_creative_agent_3_0.app.visual_assets.body_refresh_attempt_state import (
    BodyRefreshAttemptStateStore,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import (
    BodyRefreshAttemptIdentity,
    BodySourceAdmission,
)


def _admission() -> BodySourceAdmission:
    return BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=[f"body-source-{index}" for index in range(5)],
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=["face.front", "face.profile", "face.rear"],
    )


def test_unrecoverable_interrupted_attempt_can_be_superseded_without_rewriting_history(
    tmp_path: Path,
) -> None:
    attempt, context = _profile_context()
    store = BodyRefreshAttemptStateStore(tmp_path / "state")
    original = store.begin(
        visual_asset_id="visual_asset_1",
        attempt_identity=attempt,
        analysis_context=context,
        body_source_admission=_admission(),
    )

    superseded = store.supersede(
        original,
        reason_code="mcp_materialization_reference_mismatch",
    )

    assert superseded.status == "superseded"
    assert superseded.next_slot_key is None
    assert superseded.next_candidate_index is None
    assert superseded.supersession_code == "mcp_materialization_reference_mismatch"
    assert superseded.candidate_checkpoints == original.candidate_checkpoints
    assert store.load_current(visual_asset_id="visual_asset_1").status == "superseded"


def test_fresh_entry_is_allowed_after_superseding_stale_attempt(
    tmp_path: Path,
) -> None:
    lifecycle, host, _service, body_asset_ids, analyzer = _library_refresh_fixture(
        tmp_path=tmp_path,
    )
    asset = next(iter(lifecycle.catalog._assets.values()))
    state_store = BodyRefreshAttemptStateStore(tmp_path / "lifecycle-state")
    lifecycle.body_refresh_attempt_state_store = state_store
    request = BodySilhouettePublicRequest(
        source_class="observed",
        target_age_scope="age_6_child_only",
        body_reference_asset_id=body_asset_ids[0],
        body_reference_asset_ids=body_asset_ids,
    )
    stale_attempt = BodyRefreshAttemptIdentity.create(
        append_only_revision=asset.character_card.append_only_revision + 1,
    )
    admission, context = host.prepare_body_refresh_analysis_context_for_refresh(
        asset=asset,
        card=asset.character_card,
        request=request,
        attempt_identity=stale_attempt,
    )
    original = state_store.begin(
        visual_asset_id=asset.visual_asset_id,
        attempt_identity=stale_attempt,
        analysis_context=context,
        body_source_admission=admission,
    )
    active_before = {
        slot_key: slot.output_id
        for slot_key, slot in asset.character_card.body_slots.items()
    }
    superseded_asset = lifecycle.supersede_current_body_refresh_attempt(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        reason_code="mcp_materialization_reference_mismatch",
    )

    assert {
        slot_key: slot.output_id
        for slot_key, slot in superseded_asset.character_card.body_slots.items()
    } == active_before
    assert superseded_asset.character_card.pending_mcp_handoff_ids == []
    assert superseded_asset.character_card.body_silhouette_refresh_slots == {}
    assert state_store.load_current(visual_asset_id=asset.visual_asset_id).status == "superseded"

    refreshed = lifecycle.refresh_character_card_body_silhouette(
        owner_scope="owner",
        visual_asset_id=asset.visual_asset_id,
        body_request=request,
        generation_channel="mcp",
    )

    assert refreshed.character_card.body_silhouette_refresh_status == "reviewing"
    current = state_store.load_current(visual_asset_id=asset.visual_asset_id)
    assert current.status == "pending_refresh"
    assert current.attempt_identity.attempt_id != stale_attempt.attempt_id
    assert current.analyzer_call_count == 1
    assert len(analyzer.calls) == 2
    assert len(host.generator.requests) == 9
    assert refreshed.character_card.body_slots["body.front_full"].output_id is not None
