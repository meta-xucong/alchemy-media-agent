"""Bounded V2 favorite pages and explicit cold preparation, synthetic only."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.schemas import ImageHistoryItem, ImageJob, ImageOutput, ImagePromptPlan
from app.services import favorites, history_counts, image_history as history


@pytest.fixture
def configured(tmp_path, monkeypatch):
    settings = SimpleNamespace(
        image_history_path=tmp_path / "image_history.jsonl", data_dir=tmp_path,
        veyra_auth_enabled=True,
    )
    monkeypatch.setattr(history, "settings", settings)
    monkeypatch.setattr(favorites, "settings", settings)
    return settings


def _item(output_id, owner, *, job_id="same-job"):
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ImageHistoryItem(
        output_id=output_id, job_id=job_id, provider_id="fixture", model="fixture",
        prompt="synthetic payload", url="/fixture", created_at=timestamp, updated_at=timestamp,
        metadata={} if owner is None else {"veyra_user_id": owner},
    )


def _seed_history(rows):
    history.prepare_history_reads()
    connection = history._history_connect()
    try:
        with connection:
            for item in rows:
                history._upsert_history_item(connection, item)
    finally:
        connection.close()


@pytest.mark.parametrize("scope", ["all", "own_public", "own", "missing", "auth_disabled"])
def test_favorite_pages_preserve_visibility_dedup_ties_and_access(configured, scope):
    # Public inserted before own deliberately opposes owner-first merged ties.
    rows = [_item("public-first", None), _item("own-z", 7), _item("own-a", 7),
            _item("other", 8), _item("public-second", None), _item("own-unstarred", 7)]
    _seed_history(rows)
    for output_id, owner in [("public-first", None), ("public-first", 7), ("own-z", 7),
                             ("own-a", 8), ("other", 7), ("other", 8),
                             ("public-second", 8), ("missing-output", 7)]:
        favorites.set_favorite(output_id, True, veyra_user_id=owner)
    if scope == "auth_disabled":
        configured.veyra_auth_enabled = False
    kwargs = {"include_all": True} if scope == "all" else (
        {} if scope in {"missing", "auth_disabled"} else {
            "veyra_user_id": 7, "include_legacy_public": scope == "own_public",
        }
    )
    baseline = history.list_image_history(limit=100, **kwargs)
    expected = [item for item in baseline.items if item.favorite]
    for offset in (0, 1, 2, 5, 20):
        page = history.list_image_history(limit=2, offset=offset, favorite=True, **kwargs)
        assert page.total == len(expected)
        assert page.items == expected[offset:offset + 2]
        assert all(item.favorite for item in page.items)
    if scope == "own_public":
        assert [item.output_id for item in expected] == ["own-z", "public-first"]


@pytest.mark.parametrize("count", [1000, 10000])
def test_filtered_reads_decode_only_the_page_and_never_enumerate_favorites(configured, monkeypatch, count):
    _seed_history(_item(f"out-{index:06d}", 7) for index in range(count))
    connection = favorites._connect()
    with connection:
        connection.executemany(
            "INSERT INTO favorites VALUES(?, '7', 7, '', '')",
            ((f"out-{index:06d}",) for index in range(count)),
        )
    connection.close()
    original = ImageHistoryItem.model_validate_json
    decoded = []

    def validate(payload):
        decoded.append(1)
        return original(payload)

    def forbidden(*args, **kwargs):
        raise AssertionError("filtered pages must not enumerate favorite IDs in Python")

    monkeypatch.setattr(ImageHistoryItem, "model_validate_json", validate)
    monkeypatch.setattr(history, "list_favorite_ids", forbidden)
    monkeypatch.setattr(favorites, "_ensure_imported", forbidden)
    monkeypatch.setattr(history, "_ensure_history_index", forbidden)
    result = history.list_image_history(limit=24, offset=count - 25, favorite=True, veyra_user_id=7)
    assert result.total == count
    assert len(result.items) == len(decoded) == 24


@pytest.mark.parametrize("count", [1000, 10000])
def test_favorite_query_drives_from_owner_index_and_sorts_only_scalar_keys(configured, monkeypatch, count):
    _seed_history(_item(f"out-{index:06d}", 7) for index in range(count))
    favorites.set_favorite(f"out-{count - 1:06d}", True, veyra_user_id=7)
    statements = []
    original_connect = history._history_connect
    steps = 0

    def count_step():
        nonlocal steps
        steps += 1
        return 0

    def traced_connect(**kwargs):
        connection = original_connect(**kwargs)
        connection.set_trace_callback(statements.append)
        connection.set_progress_handler(count_step, 1)
        return connection

    monkeypatch.setattr(history, "_history_connect", traced_connect)
    page = history.list_image_history(limit=24, favorite=True, veyra_user_id=7)
    assert page.total == len(page.items) == 1
    assert steps < 1200  # A full 10k-row history walk cannot fit this budget.
    assert "PRAGMA temp_store=FILE" in statements
    query = next(sql for sql in statements if sql.startswith("SELECT h.output_id"))
    assert "payload" not in query
    connection = original_connect(prepare=False)
    favorites.attach_ready_favorites(connection)
    try:
        plan = [row[3] for row in connection.execute("EXPLAIN QUERY PLAN " + query)]
        assert any("favorites_owner_idx" in step for step in plan), plan
        assert any("SEARCH h USING INDEX" in step and "output_id=?" in step for step in plan), plan
        assert not any(step.startswith("SCAN h") for step in plan), plan
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            connection.execute("DELETE FROM history_favorites.favorites")
    finally:
        connection.close()


def test_count_page_payloads_and_true_flags_share_attached_snapshot(configured, monkeypatch):
    _seed_history([_item("one", 7), _item("two", 7)])
    favorites.set_favorite("one", True, veyra_user_id=7)
    favorites.set_favorite("two", True, veyra_user_id=7)
    original_connect = history._history_connect
    changed = False

    def mutate_after_count(sql):
        nonlocal changed
        if sql.startswith("SELECT h.output_id") and not changed:
            changed = True
            favorite_writer = favorites._connect()
            with favorite_writer:
                favorite_writer.execute("DELETE FROM favorites")
            favorite_writer.close()
            writer = original_connect()
            with writer:
                writer.execute("DELETE FROM v2_image_history")
            writer.close()

    def traced_connect(**kwargs):
        connection = original_connect(**kwargs)
        connection.set_trace_callback(mutate_after_count)
        return connection

    monkeypatch.setattr(history, "_history_connect", traced_connect)
    page = history.list_image_history(limit=24, favorite=True, veyra_user_id=7)
    assert changed and page.total == len(page.items) == 2
    assert all(item.favorite for item in page.items)
    assert history.list_image_history(favorite=True, veyra_user_id=7).total == 0


@pytest.mark.parametrize("favorite", [False, True])
def test_pending_history_never_opens_legacy_source_in_request(configured, monkeypatch, favorite):
    configured.image_history_path.write_text(_item("one", 7).model_dump_json(), encoding="utf-8")
    original_open = Path.open

    def forbidden_open(path, *args, **kwargs):
        if path == configured.image_history_path:
            raise AssertionError("request must not open pending JSONL")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", forbidden_open)
        with pytest.raises(history.HistoryIndexNotReadyError):
            history.list_image_history(veyra_user_id=7, favorite=favorite)
    assert not configured.image_history_path.with_name("image_history_index.sqlite3").exists()
    history.prepare_history_reads()
    result = history.list_image_history(veyra_user_id=7, favorite=favorite)
    assert result.total == (0 if favorite else 1)


@pytest.mark.parametrize("favorite", [False, True])
def test_pending_favorites_never_import_during_history_read(configured, monkeypatch, favorite):
    _seed_history([_item("one", 7)])
    source = favorites.favorites_path()
    source.write_text(json.dumps({"items": [{"output_id": "one", "veyra_user_id": 7}]}), encoding="utf-8")
    original_import = favorites._ensure_imported

    def forbidden_import(*args, **kwargs):
        raise AssertionError("request must not import pending favorite JSON")

    with monkeypatch.context() as patch:
        patch.setattr(favorites, "_ensure_imported", forbidden_import)
        with pytest.raises(favorites.FavoritesIndexNotReadyError):
            history.list_image_history(veyra_user_id=7, favorite=favorite)
    assert original_import is favorites._ensure_imported
    history.prepare_history_reads()
    page = history.list_image_history(veyra_user_id=7, favorite=favorite)
    assert page.total == 1 and page.items[0].favorite


def test_old_countless_database_is_not_backfilled_by_request(configured):
    connection = sqlite3.connect(configured.image_history_path.with_name("image_history_index.sqlite3"))
    connection.execute("""CREATE TABLE v2_image_history(output_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
        owner_id INTEGER, created_epoch REAL NOT NULL, updated_epoch REAL NOT NULL, payload TEXT NOT NULL)""")
    with connection:
        item = _item("old", 7)
        connection.execute("INSERT INTO v2_image_history VALUES(?,?,?,?,?,?)", (
            item.output_id, item.job_id, 7, 0, 0, item.model_dump_json(),
        ))
    connection.close()
    with pytest.raises(history.HistoryIndexNotReadyError):
        history.list_image_history(veyra_user_id=7)
    connection = sqlite3.connect(configured.image_history_path.with_name("image_history_index.sqlite3"))
    assert connection.execute("SELECT name FROM sqlite_master WHERE name='v2_history_counts'").fetchone() is None
    connection.close()
    history.prepare_history_reads()
    assert history.list_image_history(veyra_user_id=7).total == 1


def test_missing_count_objects_are_never_backfilled_by_read(configured):
    _seed_history([_item("one", 7)])
    connection = history._history_connect()
    with connection:
        for name in ("insert", "delete", "owner_update"):
            connection.execute("DROP TRIGGER v2_history_count_" + name)
        connection.execute("DROP TABLE v2_history_counts")
        connection.execute("DROP TABLE v2_history_count_state")
    connection.close()
    with pytest.raises(history_counts.HistoryCountIndexError):
        history.list_image_history(veyra_user_id=7)
    raw = sqlite3.connect(configured.image_history_path.with_name("image_history_index.sqlite3"))
    try:
        assert raw.execute("SELECT name FROM sqlite_master WHERE name='v2_history_counts'").fetchone() is None
        assert raw.execute("SELECT COUNT(*) FROM v2_image_history").fetchone()[0] == 1
    finally:
        raw.close()
    history.prepare_history_reads()
    assert history.list_image_history(veyra_user_id=7).total == 1


@pytest.mark.parametrize("endpoint", ["/api/v2/image/history", "/api/v2/veyra/history"])
@pytest.mark.parametrize("error,code", [
    (history.HistoryIndexNotReadyError, "history_index_unavailable"),
    (favorites.FavoritesIndexNotReadyError, "favorites_index_unavailable"),
])
def test_readiness_api_failure_is_sanitized_not_empty(monkeypatch, endpoint, error, code):
    from app import main

    def fail(*args, **kwargs):
        raise error("private-path-and-source")

    monkeypatch.setattr(main, "list_image_history", fail)
    monkeypatch.setattr(main, "settings", SimpleNamespace(veyra_auth_enabled=False))
    response = TestClient(main.app).get(endpoint + "?favorite=true")
    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == code
    assert response.json()["detail"]["retryable"] is False
    assert "private-path-and-source" not in response.text
    assert "items" not in response.json()


def test_empty_store_read_bootstrap_is_bounded_and_later_source_requires_preparation(configured):
    assert history.list_image_history(veyra_user_id=7).total == 0
    assert history.list_image_history(veyra_user_id=7, favorite=True).total == 0
    configured.image_history_path.write_text(_item("later", 7).model_dump_json(), encoding="utf-8")
    with pytest.raises(history.HistoryIndexNotReadyError):
        history.list_image_history(veyra_user_id=7)
    history.prepare_history_reads()
    assert history.list_image_history(veyra_user_id=7).total == 1


def _native_job():
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ImageJob(
        job_id="native-job", status="completed", provider_id="fixture", model="fixture",
        prompt_plan=ImagePromptPlan(plan_id="fixture-plan", mode="smart_enhance", prompt="synthetic"),
        outputs=[ImageOutput(output_id="native-output", job_id="native-job", url="/fixture",
                             created_at=timestamp, metadata={"veyra_user_id": 7})],
        created_at=timestamp, updated_at=timestamp,
    )


def test_first_native_write_establishes_ready_index_before_jsonl_mirror(configured, monkeypatch):
    configured.persist_image_history = True
    history.persist_image_job_history(_native_job())
    assert configured.image_history_path.stat().st_size > 0

    def forbidden_import():
        raise AssertionError("native mirror must not need a read-time import")

    monkeypatch.setattr(history, "_ensure_history_index", forbidden_import)
    result = history.list_image_history(veyra_user_id=7)
    assert result.total == 1 and result.items[0].output_id == "native-output"
    connection = history._history_connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM v2_image_history_migration").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM v2_image_history_import_receipts").fetchone()[0] == 0
    finally:
        connection.close()


@pytest.mark.parametrize("blocked_state", ["corrupt_source", "orphan_receipt"])
def test_native_write_never_bypasses_pending_legacy_failure(configured, blocked_state):
    configured.persist_image_history = True
    connection = history._history_connect()
    if blocked_state == "corrupt_source":
        configured.image_history_path.write_text('{"invalid":', encoding="utf-8")
    else:
        with connection:
            connection.execute(
                "INSERT INTO v2_image_history_import_receipts VALUES('jsonl', 'fixture', 1, 1, '')"
            )
    connection.close()
    with pytest.raises(history.LegacyHistoryImportError):
        history.persist_image_job_history(_native_job())
    connection = history._history_connect()
    try:
        assert connection.execute("SELECT COUNT(*) FROM v2_image_history").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM v2_image_history_migration").fetchone()[0] == 0
    finally:
        connection.close()
