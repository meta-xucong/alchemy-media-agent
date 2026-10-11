from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from app.repositories import history_index as index
from app.repositories.memory import MemoryRepository
from app.repositories.sqlite_json import connect
from app.schemas import GenerationJob, GenerationOutput
from app.services import favorites
from app.storage.local import LocalMediaStore


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    repo = MemoryRepository(database_path=tmp_path / "repository.sqlite3")
    monkeypatch.setattr(favorites, "media_store", store)
    connection = connect(repo.database_path)
    with connection:
        for number in range(120):
            job_id, output_id = f"job_{number:012d}", f"out_{number:012d}"
            owner = (None, 41, 77)[number % 3]
            job = GenerationJob(
                id=job_id, session_id="a" if number % 2 else "b", job_type="image",
                status="ready", trace_id="synthetic", created_at="2026-01-01T00:00:00Z",
                updated_at="2026-01-01T00:00:00Z", outputs=[GenerationOutput(
                    id=output_id, job_id=job_id, url="/synthetic",
                    metadata={"veyra_user_id": owner} if owner else {},
                )],
            )
            repo.jobs.put_on(connection, job.id, job)
    connection.close()
    index.prepare_history_index(store)
    favorites.prepare_favorites_index()
    connection = connect(repo.database_path)
    with connection:
        for number in range(120):
            for divisor, owner in ((2, 41), (5, None), (7, 77)):
                if number % divisor == 0:
                    connection.execute("INSERT INTO v1_favorites VALUES(?,?,?,?,?)",
                                       (f"out_{number:012d}", "" if owner is None else str(owner), owner, "", ""))
    connection.close()
    return store, repo


def test_favorite_pages_filter_both_authorities_before_decoding(fixture, monkeypatch):
    store, _ = fixture
    expected = [f"out_{n:012d}" for n in reversed(range(120))
                if n % 3 != 2 and (n % 2 == 0 or n % 5 == 0)]
    monkeypatch.setattr(index, "_decode", lambda *_: pytest.fail("No full authority decoding on warm page"))
    seen = []
    for offset in range(0, len(expected), 7):
        metrics = index.HistoryReadMetrics()
        rows, total = index.read_history_page(store, surface="v1", owner_id=41,
                                             favorite=True, limit=7, offset=offset, metrics=metrics)
        assert total == len(expected)
        assert metrics.page_decodes == len(rows) <= 7
        assert metrics.authority_decodes == 0
        seen.extend(row["id"] for row in rows)
    assert seen == expected
    assert index.read_history_page(store, surface="v1", owner_id=41, favorite=True,
                                   limit=7, offset=999) == ([], len(expected))


def test_admin_history_does_not_expand_v1_favorite_owner_scope(fixture):
    store, _ = fixture
    rows, total = index.read_history_page(store, surface="v1", owner_id=41,
                                        all_owners=True, favorite=True, limit=200)
    expected = [f"out_{n:012d}" for n in reversed(range(120)) if n % 2 == 0 or n % 5 == 0]
    assert [row["id"] for row in rows] == expected and total == len(expected)


def test_session_favorites_and_toggles_are_not_cached(fixture):
    store, _ = fixture
    rows, total = index.read_history_page(store, surface="v1", owner_id=41,
                                        session_id="a", favorite=True, limit=200)
    expected = [f"out_{n:012d}" for n in reversed(range(120)) if n % 2 and n % 3 != 2 and n % 5 == 0]
    assert [row["id"] for row in rows] == expected and total == len(expected)
    favorites.set_favorite("out_000000000001", True, veyra_user_id=41)
    assert index.read_history_page(store, surface="v1", owner_id=41, session_id="a",
                                   favorite=True, limit=200)[1] == total + 1
    favorites.set_favorite("out_000000000001", False, veyra_user_id=41)
    assert index.read_history_page(store, surface="v1", owner_id=41, session_id="a",
                                   favorite=True, limit=200)[1] == total


def test_pending_legacy_favorites_never_import_during_read(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    MemoryRepository(database_path=tmp_path / "repository.sqlite3")
    monkeypatch.setattr(favorites, "media_store", store)
    index.prepare_history_index(store)
    source = tmp_path / "favorites" / "image_favorites.json"
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({"items": [{"output_id": "legacy", "veyra_user_id": 41}]}))
    original_open = Path.open
    def forbidden(path, *args, **kwargs):
        if path == source:
            pytest.fail("Readiness must not open/import legacy favorites")
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(index.HistoryIndexUnavailable, match="Favorites"):
        index.read_history_page(store, surface="v1", owner_id=41, favorite=True)
    with pytest.raises(index.HistoryIndexUnavailable, match="Favorites"):
        favorites.list_favorite_ids(veyra_user_id=41, output_ids=["legacy"], prepared_only=True)
    monkeypatch.setattr(Path, "open", original_open)
    favorites.prepare_favorites_index()
    assert favorites.list_favorite_ids(veyra_user_id=41, output_ids=["legacy"], prepared_only=True) == {"legacy"}


def test_empty_favorites_without_legacy_source_are_read_only(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    MemoryRepository(database_path=tmp_path / "repository.sqlite3")
    monkeypatch.setattr(favorites, "media_store", store)
    index.prepare_history_index(store)
    assert index.read_history_page(store, surface="v1", favorite=True, all_owners=True) == ([], 0)
    connection = connect(tmp_path / "repository.sqlite3")
    try:
        assert not connection.execute("SELECT 1 FROM sqlite_master WHERE name='v1_favorites'").fetchone()
    finally:
        connection.close()


def test_filtered_response_keeps_snapshot_membership_after_toggle(fixture, monkeypatch):
    import app.main as main

    store, _ = fixture
    monkeypatch.setattr(main, "media_store", store)
    read = index.read_history_page
    def selected_then_unfavorite(*args, **kwargs):
        rows, total = read(*args, **kwargs)
        connection = connect(store.root / "repository.sqlite3")
        with connection:
            connection.execute("DELETE FROM v1_favorites")
        connection.close()
        return rows, total
    monkeypatch.setattr(index, "read_history_page", selected_then_unfavorite)
    monkeypatch.setattr(main, "list_favorite_ids", lambda **_: pytest.fail("Filtered snapshot must not be overlaid later"))
    response = main._list_image_history_sync(
        {"authenticated": True, "user_id": 41, "is_admin": False}, limit=5, favorite=True,
    )
    assert response.total > 5 and len(response.items) == 5
    assert all(item.favorite for item in response.items)


def test_unprepared_favorite_route_returns_typed_503(fixture, monkeypatch):
    import app.main as main
    from fastapi import HTTPException
    from starlette.requests import Request

    store, _ = fixture
    monkeypatch.setattr(main, "media_store", store)
    async def context(*args):
        return {"authenticated": True, "user_id": 41, "is_admin": False}
    monkeypatch.setattr(main, "_veyra_history_context", context)
    source = store.root / "favorites" / "image_favorites.json"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("{broken legacy source")
    with pytest.raises(HTTPException) as error:
        asyncio.run(main.list_image_history(Request({"type": "http", "headers": []}), limit=24,
                                           offset=0, favorite=True, authorization=""))
    assert error.value.status_code == 503
    assert error.value.detail["code"] == "history_index_unavailable"
    assert "broken legacy" not in str(error.value.detail)


def test_missing_favorites_with_retained_receipt_is_not_empty(fixture):
    store, _ = fixture
    connection = connect(store.root / "repository.sqlite3")
    with connection:
        connection.execute("INSERT INTO v1_import_receipts VALUES('favorites','v1.favorites.json',1,1,'synthetic')")
        connection.execute("DROP TABLE v1_favorites")
        connection.execute("DROP TABLE v1_favorite_state")
    try:
        with pytest.raises(index.HistoryIndexUnavailable, match="Favorites"):
            favorites.favorite_reads_ready(connection, storage_root=store.root)
    finally:
        connection.close()


def test_favorite_query_drives_from_candidates_not_all_history(fixture):
    store, _ = fixture
    connection = connect(store.root / "repository.sqlite3")
    plans = []
    class Traced:
        def execute(self, sql, args=()):
            if " CROSS JOIN v1_read_winners " in sql:
                plans.extend(str(row[3]) for row in connection.execute("EXPLAIN QUERY PLAN " + sql, args))
            return connection.execute(sql, args)
    try:
        connection.execute("BEGIN")
        rows, total = index._favorite_page_rows(Traced(), store=store, surface="v1", scope="global",
                                               owner_id=41, all_owners=False, include_mock=False,
                                               limit=3, offset=0)
        assert total > 3 and len(rows) == 3
        assert any("SCAN f" in detail for detail in plans)
        assert any("SEARCH w USING INDEX sqlite_autoindex_v1_read_winners_1" in detail and "output_id=?" in detail
                   for detail in plans)
        assert not any("SCAN w" in detail for detail in plans)
    finally:
        connection.close()
