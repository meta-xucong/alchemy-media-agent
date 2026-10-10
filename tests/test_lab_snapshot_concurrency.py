from __future__ import annotations

from app.services import alchemy_lab
from app.services.alchemy_lab import (
    AlchemyLabStore,
    ExplorationRequest,
    ExplorationSession,
    FavoriteSelection,
    GenerationVariant,
)


def test_generation_progress_save_preserves_favorite_updated_during_run(tmp_path, monkeypatch):
    store = AlchemyLabStore(database_path=tmp_path / "lab.sqlite3")
    monkeypatch.setattr(alchemy_lab, "lab_store", store)
    session = ExplorationSession(
        id="lab-session-1",
        status="running",
        created_at="2026-10-09T00:00:00+00:00",
        updated_at="2026-10-09T00:00:00+00:00",
        request=ExplorationRequest(idea="test idea"),
        variants=[
            GenerationVariant(
                id="variant-1",
                session_id="lab-session-1",
                prompt_id="prompt-1",
                style_preset_id="style-1",
                index_within_style=1,
                status="queued",
                created_at="2026-10-09T00:00:00+00:00",
            )
        ],
    )
    store.save(session)
    stale_runner_snapshot = store.get(session.id)
    assert stale_runner_snapshot is not None

    updated = alchemy_lab.update_favorites(
        session.id,
        FavoriteSelection(variant_ids=["variant-1"]),
    )
    assert updated is not None
    assert updated.favorites == ["variant-1"]

    stale_runner_snapshot.progress = {"status": "running", "current": 1}
    store.save_runner_state(stale_runner_snapshot)

    persisted = store.get(session.id)
    assert persisted is not None
    assert persisted.progress["current"] == 1
    assert persisted.favorites == ["variant-1"]
