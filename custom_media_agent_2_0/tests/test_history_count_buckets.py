from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace

import pytest

from app.schemas import ImageHistoryItem
import app.services.history_counts as counts
import app.services.image_history as history


@pytest.fixture
def configured(tmp_path, monkeypatch):
    path = tmp_path / "history.jsonl"
    monkeypatch.setattr(history, "settings", SimpleNamespace(image_history_path=path, veyra_auth_enabled=True))
    monkeypatch.setattr(history, "list_favorite_ids", lambda **_: set())
    return path


def _item(output_id="one", owner=1, updated=0):
    created = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return ImageHistoryItem(output_id=output_id, job_id="job-" + output_id,
                            provider_id="fixture", model="fixture", prompt="fixture", url="/fixture",
                            metadata={} if owner is None else {"veyra_user_id": owner},
                            created_at=created, updated_at=created + timedelta(seconds=updated))


def _total(connection, owner=None, public=False):
    return counts.read_history_count(connection, owner_id=owner, include_public=public, include_all=owner is None)


def _assert_counts(connection, all_count, owner1, public_owner1):
    counts.verify_history_counts(connection)
    assert _total(connection) == all_count
    assert _total(connection, 1) == owner1
    assert _total(connection, 1, True) == public_owner1


def test_native_upsert_owner_move_stale_write_delete_and_replace(configured):
    connection = history._history_connect()
    try:
        assert connection.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
        with connection:
            for item in (_item("one", 1, 5), _item("two", 2), _item("public", None)):
                history._upsert_history_item(connection, item)
        _assert_counts(connection, 3, 1, 2)
        with connection:
            history._upsert_history_item(connection, _item("one", 2, 4))
        _assert_counts(connection, 3, 1, 2)  # Rejected stale upsert.
        with connection:
            history._upsert_history_item(connection, _item("one", 2, 6))
            history._upsert_history_item(connection, _item("one", 2, 7))
        _assert_counts(connection, 3, 0, 1)
        assert connection.execute("SELECT 1 FROM v2_history_counts WHERE bucket='1'").fetchone() is None
        with connection:
            old = connection.execute("SELECT * FROM v2_image_history WHERE output_id='one'").fetchone()
            replacement = list(old)
            replacement[2] = 1
            replacement[5] = _item("one", 1, 8).model_dump_json()
            connection.execute("INSERT OR REPLACE INTO v2_image_history VALUES(?,?,?,?,?,?)", replacement)
        _assert_counts(connection, 3, 1, 2)
        with connection:
            connection.execute("DELETE FROM v2_image_history WHERE output_id='public'")
        _assert_counts(connection, 2, 1, 1)
        assert connection.execute("SELECT 1 FROM v2_history_counts WHERE bucket='public'").fetchone() is None
        with pytest.raises(RuntimeError), connection:
            history._upsert_history_item(connection, _item("rolled-back", 1))
            raise RuntimeError("fixture rollback")
        _assert_counts(connection, 2, 1, 1)
    finally:
        connection.close()


def test_strict_import_rolls_back_counts_and_retries_atomically(configured):
    configured.write_text(_item().model_dump_json() + '\n{"broken":', encoding="utf-8")
    with pytest.raises(history.LegacyHistoryImportError):
        history._ensure_history_index()
    connection = history._history_connect()
    _assert_counts(connection, 0, 0, 0)
    assert connection.execute("SELECT COUNT(*) FROM v2_image_history_migration").fetchone()[0] == 0
    connection.close()
    configured.write_text(_item().model_dump_json() + "\n" + _item("public", None).model_dump_json(), encoding="utf-8")
    history._ensure_history_index()
    result = history.list_image_history(include_all=True)
    assert result.total == len(result.items) == 2
    connection = history._history_connect()
    _assert_counts(connection, 2, 1, 2)
    connection.close()


def test_removed_owner_buckets_do_not_accumulate_after_many_distinct_owners(configured):
    connection = history._history_connect()
    try:
        with connection:
            for owner in range(1000):
                history._upsert_history_item(connection, _item("moving", owner, owner))
            connection.execute("DELETE FROM v2_image_history")
        counts.verify_history_counts(connection)
        assert list(map(tuple, connection.execute("SELECT * FROM v2_history_counts"))) == [("all", 0)]
    finally:
        connection.close()


def test_existing_pre_count_database_backfills_once_and_reopens(configured):
    raw = sqlite3.connect(configured.with_name("image_history_index.sqlite3"))
    raw.execute("""CREATE TABLE v2_image_history(output_id TEXT PRIMARY KEY, job_id TEXT NOT NULL,
        owner_id INTEGER, created_epoch REAL NOT NULL, updated_epoch REAL NOT NULL, payload TEXT NOT NULL)""")
    with raw:
        for item in (_item(), _item("public", None)):
            raw.execute("INSERT INTO v2_image_history VALUES(?,?,?,?,?,?)", (
                item.output_id, item.job_id, item.metadata.get("veyra_user_id"), 0, 0, item.model_dump_json(),
            ))
    raw.close()
    for _ in range(2):
        connection = history._history_connect()
        _assert_counts(connection, 2, 1, 2)
        assert connection.execute("SELECT version FROM v2_history_count_state").fetchone()[0] == 1
        connection.close()


def test_concurrent_first_connections_and_writes_are_counted_once(configured):
    def write(worker):
        connection = history._history_connect()
        try:
            with connection:
                for index in range(20):
                    history._upsert_history_item(connection, _item(f"{worker}-{index}", 1))
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(write, range(4)))
    connection = history._history_connect()
    _assert_counts(connection, 80, 80, 80)
    connection.close()


@pytest.mark.parametrize("damage", [
    "DROP TABLE v2_history_counts",
    "DROP TRIGGER v2_history_count_insert",
    "UPDATE v2_history_count_state SET version=99",
    "DELETE FROM v2_history_counts WHERE bucket='all'",
])
def test_incomplete_derived_state_fails_closed_and_rebuild_preserves_authority(configured, damage):
    configured.write_text(_item().model_dump_json(), encoding="utf-8")
    history._ensure_history_index()
    history.list_image_history(include_all=True)
    connection = history._history_connect()
    source = tuple(connection.execute("SELECT * FROM v2_image_history").fetchone())
    receipt = tuple(connection.execute("SELECT * FROM v2_image_history_import_receipts").fetchone())
    with connection:
        connection.execute(damage)
    connection.close()
    with pytest.raises(counts.HistoryCountIndexError):
        history.list_image_history(include_all=True)
    raw = sqlite3.connect(configured.with_name("image_history_index.sqlite3"))
    counts.rebuild_history_counts(raw)
    assert tuple(raw.execute("SELECT * FROM v2_image_history").fetchone()) == source
    assert tuple(raw.execute("SELECT * FROM v2_image_history_import_receipts").fetchone()) == receipt
    raw.close()
    assert history.list_image_history(include_all=True).total == 1


def test_missing_populated_owner_bucket_fails_but_absent_owner_is_zero(configured):
    connection = history._history_connect()
    with connection:
        history._upsert_history_item(connection, _item())
        connection.execute("DELETE FROM v2_history_counts WHERE bucket='1'")
    assert _total(connection, 999, True) == 0
    with pytest.raises(counts.HistoryCountIndexError):
        _total(connection, 1)
    with pytest.raises(counts.HistoryCountIndexError):
        counts.verify_history_counts(connection)
    connection.close()


def test_unmanaged_replace_without_recursive_triggers_requires_maintenance(configured):
    managed = history._history_connect()
    with managed:
        history._upsert_history_item(managed, _item())
    managed.close()
    raw = sqlite3.connect(configured.with_name("image_history_index.sqlite3"))
    raw.execute("PRAGMA recursive_triggers=OFF")
    with raw:
        row = raw.execute("SELECT * FROM v2_image_history").fetchone()
        raw.execute("INSERT OR REPLACE INTO v2_image_history VALUES(?,?,?,?,?,?)", row)
    with pytest.raises(counts.HistoryCountIndexError):
        counts.verify_history_counts(raw)
    counts.rebuild_history_counts(raw)
    _assert_counts(raw, 1, 1, 1)
    raw.close()


def test_positive_counter_corruption_and_failed_rebuild_are_not_silent(configured, monkeypatch):
    connection = history._history_connect()
    with connection:
        history._upsert_history_item(connection, _item())
        connection.execute("UPDATE v2_history_counts SET row_count=99 WHERE bucket='1'")
    with pytest.raises(counts.HistoryCountIndexError):
        counts.verify_history_counts(connection)
    build = counts._build

    def fail_after_build(conn):
        build(conn)
        raise RuntimeError("fixture rebuild interruption")

    monkeypatch.setattr(counts, "_build", fail_after_build)
    with pytest.raises(RuntimeError):
        counts.rebuild_history_counts(connection)
    assert connection.execute("SELECT row_count FROM v2_history_counts WHERE bucket='1'").fetchone()[0] == 99
    assert connection.execute("SELECT COUNT(*) FROM v2_image_history").fetchone()[0] == 1
    monkeypatch.setattr(counts, "_build", build)
    counts.rebuild_history_counts(connection)
    _assert_counts(connection, 1, 1, 1)
    connection.close()


@pytest.mark.parametrize("value", [0, 99])
def test_hot_page_detects_impossible_derived_total(configured, value):
    connection = history._history_connect()
    with connection:
        history._upsert_history_item(connection, _item())
        connection.execute("UPDATE v2_history_counts SET row_count=? WHERE bucket='all'", (value,))
    connection.close()
    with pytest.raises(counts.HistoryCountIndexError):
        history.list_image_history(limit=24, include_all=True)


def test_maintenance_verification_is_read_only_and_owns_a_snapshot(configured):
    connection = history._history_connect()
    with connection:
        history._upsert_history_item(connection, _item())
    connection.close()
    path = configured.with_name("image_history_index.sqlite3")
    readonly = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    trace = []
    readonly.set_trace_callback(trace.append)
    before = readonly.total_changes
    counts.verify_history_counts(readonly)
    assert readonly.total_changes == before == 0
    assert not readonly.in_transaction
    assert trace[0] == "BEGIN"
    assert trace[-1] == "ROLLBACK"
    assert not any(sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE", "DROP", "CREATE")) for sql in trace)
    readonly.close()


def test_verification_keeps_snapshot_when_writer_commits_during_metadata_read(configured):
    connection = history._history_connect()
    with connection:
        history._upsert_history_item(connection, _item())
    fired = False

    def trace(sql):
        nonlocal fired
        if "SELECT row_count FROM v2_history_counts WHERE bucket='all'" in sql and not fired:
            fired = True
            writer = history._history_connect()
            with writer:
                history._upsert_history_item(writer, _item("later", 2))
            writer.close()

    connection.set_trace_callback(trace)
    counts.verify_history_counts(connection)
    assert fired
    assert not connection.in_transaction
    assert _total(connection) == 2
    connection.close()
