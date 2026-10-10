"""Synthetic, streaming legacy-history import safety checks. No providers run."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
from threading import Event, Lock

import pytest

from app.storage import local as local_module
from app.storage.local import LocalMediaStore


def _record(output_id="out_import", **fields):
    return {"id": output_id, "job_id": "job_import", "format": "png", **fields}


def _source(store, *lines):
    store.history_file.parent.mkdir(parents=True, exist_ok=True)
    store.history_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _snapshot(store):
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        return {
            table: connection.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()
            for table in ("v1_history_records", "v1_history_owner_evidence", "v1_history_state")
        }


def _clear_markers(store, *, owner_only=False):
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        if owner_only:
            connection.execute("DELETE FROM v1_history_state WHERE state_key='owner_evidence_backfilled'")
            connection.execute("DELETE FROM v1_history_owner_evidence")
            connection.execute("DELETE FROM v1_import_receipts WHERE namespace='history'")
        else:
            connection.execute("DELETE FROM v1_history_state")
            connection.execute("DELETE FROM v1_import_receipts WHERE namespace='history'")


def _assert_import_error(store, *, line=2):
    with pytest.raises(ValueError, match=rf"line {line}\b") as captured:
        store._ensure_history_index()
    error = captured.value
    assert type(error).__name__ == "LegacyHistoryImportError"
    assert error.line_number == line
    assert error.reason in {"invalid_json", "invalid_record"}
    assert "PRIVATE-PAYLOAD" not in str(error)
    assert error.__cause__ is None
    assert error.__suppress_context__


@pytest.mark.parametrize(
    "bad_line",
    [
        '{"prompt":"PRIVATE-PAYLOAD",',
        '{"id":"out_bad","veyra_user_id":NaN}',
        '{"id":"out_bad","veyra_user_id":Infinity}',
        '{"id":"out_bad","veyra_user_id":1e400}',
        '{"id":"out_bad","veyra_user_id":41,"veyra_user_id":null}',
    ],
)
def test_malformed_json_rolls_back_rows_evidence_and_markers(tmp_path, bad_line):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record(veyra_user_id=41)), bad_line)

    _assert_import_error(store)

    assert all(not rows for rows in _snapshot(store).values())


@pytest.mark.parametrize(
    "invalid",
    [
        None, [], "PRIVATE-PAYLOAD", 42, True, {},
        {"id": None}, {"id": " "}, {"id": 7}, {"id": ["PRIVATE-PAYLOAD"]},
        _record(job_id=[]), _record(job_id=None), _record(session_id={}),
        _record(format=[]), _record(created_at={}), _record(updated_at=17),
        _record(prompt=[]), _record(width="512"), _record(height=True),
        _record(provider_fallback=[]), _record(asset_intents={}),
        _record(asset_vision_profiles=["PRIVATE-PAYLOAD"]),
        _record(veyra_user_id="PRIVATE-PAYLOAD"), _record(veyra_user_id=[]),
        _record(veyra_user_id=True), _record(veyra_user_id=41.5),
        _record(veyra_user_id=41.0), _record(veyra_user_id=0.0),
        _record(veyra_user_id=-1), _record(veyra_user_id=2**63),
        _record(prompt="PRIVATE-PAYLOAD\ud800"), _record(metadata=["\ud800"]),
        _record("out\x00broken"), _record(job_id="job\x00broken"),
    ],
)
def test_valid_json_invalid_record_is_rejected_without_partial_import(tmp_path, invalid):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record(veyra_user_id=41)), json.dumps(invalid))

    _assert_import_error(store)

    assert all(not rows for rows in _snapshot(store).values())


def test_repaired_source_retries_entire_import_and_keeps_existing_durable_rows(tmp_path):
    store = LocalMediaStore(tmp_path)
    durable = _record("out_durable", veyra_user_id=41, created_at="2025-01-01T00:00:00Z")
    store.save_history_record(durable)
    _clear_markers(store)
    before = _snapshot(store)
    conflicting = _record("out_durable", veyra_user_id=77, created_at="2026-01-01T00:00:00Z")
    first = _record("out_new", veyra_user_id=41)
    _source(store, json.dumps(conflicting), json.dumps(first), '{"prompt":"PRIVATE-PAYLOAD"')

    _assert_import_error(store, line=3)
    assert _snapshot(store) == before

    _source(store, json.dumps(conflicting), json.dumps(first), json.dumps(_record("out_repaired")))
    store._ensure_history_index()
    after = _snapshot(store)
    assert {row[1] for row in after["v1_history_records"]} == {"out_durable", "out_new", "out_repaired"}
    assert ("out_durable", 41, 1) in after["v1_history_owner_evidence"]
    assert dict(after["v1_history_state"]) == {"jsonl_imported": "1", "owner_evidence_backfilled": "1"}
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        receipt = connection.execute(
            "SELECT importer_id, importer_version, record_count FROM v1_import_receipts WHERE namespace='history'"
        ).fetchone()
    assert receipt == ("v1.history.jsonl", 1, 3)
    assert store.get_history_record("out_durable", include_missing=True)["_veyra_owner_conflict"] is True


def test_owner_backfill_is_atomic_retryable_and_does_not_reimport_history(tmp_path):
    store = LocalMediaStore(tmp_path)
    durable = _record("out_durable", veyra_user_id=41)
    store.save_history_record(durable)
    store._ensure_history_index()
    _clear_markers(store, owner_only=True)
    before = _snapshot(store)
    duplicate = _record("out_durable", veyra_user_id="77")
    deleted = _record("out_previously_deleted", veyra_user_id=77)
    _source(store, json.dumps(durable), json.dumps(duplicate), json.dumps(deleted), '{}')

    _assert_import_error(store, line=4)
    assert _snapshot(store) == before

    _source(store, json.dumps(durable), json.dumps(duplicate), json.dumps(deleted))
    store._ensure_history_index()
    after = _snapshot(store)
    assert after["v1_history_records"] == before["v1_history_records"]
    assert ("out_durable", 41, 1) in after["v1_history_owner_evidence"]
    assert dict(after["v1_history_state"])["owner_evidence_backfilled"] == "1"
    assert store.get_history_record("out_previously_deleted", include_missing=True) is None
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        receipt = connection.execute(
            "SELECT importer_id, importer_version, record_count FROM v1_import_receipts WHERE namespace='history'"
        ).fetchone()
    assert receipt is None


def test_v1_orphan_receipt_blocks_legacy_history_replay(tmp_path):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record("out_once")))
    store._ensure_history_index()
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        connection.execute("DELETE FROM v1_history_state WHERE state_key='jsonl_imported'")
        connection.execute("DELETE FROM v1_history_state WHERE state_key='owner_evidence_backfilled'")
        connection.commit()
    with pytest.raises(ValueError, match="import_state_inconsistent"):
        store._ensure_history_index()
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM v1_history_records WHERE output_id='out_once'"
        ).fetchone()[0] == 1


def test_v1_owner_evidence_marker_without_history_marker_blocks_stale_source_replay(tmp_path):
    store = LocalMediaStore(tmp_path)
    store._ensure_history_index()
    _source(store, json.dumps(_record("out_stale_source")))
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        connection.execute(
            "INSERT INTO v1_history_state(state_key, state_value) VALUES('owner_evidence_backfilled', '1')"
        )
        connection.commit()

    with pytest.raises(ValueError, match="import_state_inconsistent"):
        store._ensure_history_index()

    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM v1_history_records").fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM v1_history_state WHERE state_key='owner_evidence_backfilled'"
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT COUNT(*) FROM v1_history_state WHERE state_key='jsonl_imported'"
        ).fetchone()[0] == 0
        assert connection.execute(
            "SELECT COUNT(*) FROM v1_import_receipts WHERE namespace='history'"
        ).fetchone()[0] == 0


def test_v1_strict_receipt_with_missing_owner_marker_blocks_evidence_replay(tmp_path):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record("out_original", veyra_user_id=41)))
    store._ensure_history_index()
    before = _snapshot(store)
    _source(store, json.dumps(_record("out_new_stale", veyra_user_id=77)))
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        connection.execute("DELETE FROM v1_history_state WHERE state_key='owner_evidence_backfilled'")
        connection.commit()

    with pytest.raises(ValueError, match="import_state_inconsistent"):
        store._ensure_history_index()

    assert _snapshot(store)["v1_history_records"] == before["v1_history_records"]
    assert _snapshot(store)["v1_history_owner_evidence"] == before["v1_history_owner_evidence"]
    assert dict(_snapshot(store)["v1_history_state"]) == {"jsonl_imported": "1"}
    with sqlite3.connect(store.root / "repository.sqlite3") as connection:
        assert connection.execute(
            "SELECT importer_id, importer_version, record_count FROM v1_import_receipts WHERE namespace='history'"
        ).fetchone() == ("v1.history.jsonl", 1, 1)


@pytest.mark.parametrize("owner", [None, 0, "0", "", "  ", 41, "41", "+41", "  +41  "])
def test_legacy_ownerless_and_integer_string_owners_remain_supported(tmp_path, owner):
    store = LocalMediaStore(tmp_path)
    minimal = {"id": "out_minimal"}
    legacy = _record("out_legacy", veyra_user_id=owner, session_id=None, created_at=None)
    _source(store, "", json.dumps(minimal), "  ", json.dumps(legacy))

    store._ensure_history_index()

    assert {item["id"] for item in store.iter_history_records(include_missing=True)} == {"out_minimal", "out_legacy"}
    expected = [("out_legacy", 41, 0)] if owner in (41, "41", "+41", "  +41  ") else []
    assert _snapshot(store)["v1_history_owner_evidence"] == expected


def test_ownerless_duplicate_cannot_replace_canonical_owned_record(tmp_path):
    store = LocalMediaStore(tmp_path)
    owned = _record(veyra_user_id=41, created_at="2025-01-01T00:00:00Z")
    ownerless = _record(created_at="2026-01-01T00:00:00Z")
    _source(store, json.dumps(owned), json.dumps(ownerless))

    store._ensure_history_index()

    record = store.get_history_record(owned["id"], include_missing=True)
    assert record["veyra_user_id"] == 41
    assert record["created_at"] == owned["created_at"]


def test_completed_markers_do_not_replay_repaired_or_deleted_source_rows(tmp_path):
    store = LocalMediaStore(tmp_path)
    store.save_history_record(_record())
    store.delete_history_record("out_import")
    before = _snapshot(store)
    _source(store, json.dumps(_record()), '{"prompt":"PRIVATE-PAYLOAD"')

    LocalMediaStore(tmp_path)._ensure_history_index()

    assert _snapshot(store) == before
    assert store.get_history_record("out_import", include_missing=True) is None


def test_absent_source_stays_pending_and_later_source_is_imported(tmp_path):
    store = LocalMediaStore(tmp_path)
    store._ensure_history_index()
    before = _snapshot(store)
    assert before["v1_history_state"] == []
    _source(store, json.dumps(_record()))

    store._ensure_history_index()

    assert store.get_history_record("out_import", include_missing=True) is not None
    assert dict(_snapshot(store)["v1_history_state"]) == {"jsonl_imported": "1", "owner_evidence_backfilled": "1"}


def test_import_streams_source_without_read_or_readlines(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    _source(store, *(json.dumps(_record(f"out_{index}")) for index in range(300)))
    original_open = Path.open

    class StreamingOnly:
        def __init__(self, handle):
            self.handle = handle

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.handle.close()

        def __iter__(self):
            return iter(self.handle)

        def read(self, *_args):
            raise AssertionError("Do not materialize the source")

        readlines = read

    def stream_open(path, *args, **kwargs):
        handle = original_open(path, *args, **kwargs)
        return StreamingOnly(handle) if path == store.history_file else handle

    monkeypatch.setattr(Path, "open", stream_open)
    store._ensure_history_index()
    assert len(_snapshot(store)["v1_history_records"]) == 300


def test_concurrent_initializers_recheck_markers_after_writer_serialization(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    store._ensure_history_index()
    _clear_markers(store)
    _source(store, json.dumps(_record(veyra_user_id=41)))
    first_in_import = Event()
    release_first = Event()
    second_at_transaction = Event()
    calls = []
    calls_lock = Lock()
    original_upsert = LocalMediaStore._upsert_history_index
    original_connect = local_module.connect

    def counted_upsert(connection, record):
        with calls_lock:
            calls.append(record["id"])
            first = len(calls) == 1
        if first:
            first_in_import.set()
            assert release_first.wait(5)
        return original_upsert(connection, record)

    def second_connect(path):
        connection = original_connect(path)
        connection.set_trace_callback(
            lambda statement: second_at_transaction.set()
            if statement == "BEGIN IMMEDIATE" else None
        )
        return connection

    monkeypatch.setattr(LocalMediaStore, "_upsert_history_index", staticmethod(counted_upsert))
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(store._ensure_history_index)
        assert first_in_import.wait(5)
        monkeypatch.setattr(local_module, "connect", second_connect)
        second = pool.submit(LocalMediaStore(tmp_path)._ensure_history_index)
        try:
            assert second_at_transaction.wait(2), "Initializer must lock before rechecking import markers"
        finally:
            release_first.set()
        first.result(timeout=5)
        second.result(timeout=5)
    assert calls == ["out_import"]
    assert _snapshot(store)["v1_history_owner_evidence"] == [("out_import", 41, 0)]


def test_invalid_utf8_has_safe_line_error_and_repaired_bytes_retry(tmp_path):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record(veyra_user_id=41)))
    with store.history_file.open("ab") as handle:
        handle.write(b'{"id":"PRIVATE-PAYLOAD-\xff"}\n')

    _assert_import_error(store)
    assert all(not rows for rows in _snapshot(store).values())

    _source(store, json.dumps(_record(veyra_user_id=41)))
    store._ensure_history_index()
    assert _snapshot(store)["v1_history_owner_evidence"] == [("out_import", 41, 0)]


@pytest.mark.parametrize("content", ["", "\n  \n\t\n"])
def test_present_empty_source_is_a_valid_completed_import(tmp_path, content):
    store = LocalMediaStore(tmp_path)
    store.history_file.parent.mkdir(parents=True)
    store.history_file.write_text(content, encoding="utf-8")

    store._ensure_history_index()

    assert dict(_snapshot(store)["v1_history_state"]) == {"jsonl_imported": "1", "owner_evidence_backfilled": "1"}


def test_unreadable_source_is_not_treated_as_absent(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record()))
    original_open = Path.open

    def denied_open(path, *args, **kwargs):
        if path == store.history_file:
            raise PermissionError("PRIVATE-PAYLOAD source path")
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", denied_open)
    with pytest.raises(local_module.LegacyHistoryImportError, match="source_access_error") as captured:
        store._ensure_history_index()
    assert captured.value.line_number == 0
    assert "PRIVATE-PAYLOAD" not in str(captured.value)
    assert captured.value.__suppress_context__
    assert all(not rows for rows in _snapshot(store).values())


def test_read_failure_midstream_rolls_back_all_import_writes(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record(veyra_user_id=41)))
    original_open = Path.open

    class BrokenStream:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def __iter__(self):
            yield json.dumps(_record(veyra_user_id=41)).encode("utf-8")
            raise OSError("PRIVATE-PAYLOAD source read failure")

    monkeypatch.setattr(
        Path, "open", lambda path, *args, **kwargs: BrokenStream()
        if path == store.history_file else original_open(path, *args, **kwargs)
    )
    with pytest.raises(local_module.LegacyHistoryImportError, match="source_read_error") as captured:
        store._ensure_history_index()
    assert captured.value.line_number == 2
    assert "PRIVATE-PAYLOAD" not in str(captured.value)
    assert captured.value.__suppress_context__
    assert all(not rows for rows in _snapshot(store).values())


def test_explicit_transaction_rolls_back_on_autocommit_connection(tmp_path, monkeypatch):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record(veyra_user_id=41)), '{}')
    original_connect = local_module.connect

    def autocommit_connect(path):
        connection = original_connect(path)
        connection.isolation_level = None
        return connection

    monkeypatch.setattr(local_module, "connect", autocommit_connect)
    _assert_import_error(store)
    assert all(not rows for rows in _snapshot(store).values())


def test_absent_source_during_owner_backfill_keeps_existing_completion_only(tmp_path):
    store = LocalMediaStore(tmp_path)
    store.save_history_record(_record(veyra_user_id=41))
    store._ensure_history_index()
    _clear_markers(store, owner_only=True)
    store.history_file.unlink()
    before = _snapshot(store)

    store._ensure_history_index()
    assert _snapshot(store) == before

    _source(store, json.dumps(_record(veyra_user_id=41)), json.dumps(_record(veyra_user_id=77)))
    store._ensure_history_index()
    after = _snapshot(store)
    assert after["v1_history_records"] == before["v1_history_records"]
    assert after["v1_history_owner_evidence"] == [("out_import", 41, 1)]


@pytest.mark.parametrize("owner_token", ["9007199254740993.0", "41.00000000000000001", "1e-999"])
def test_float_owner_tokens_cannot_round_into_another_owner_or_ownerless(tmp_path, owner_token):
    store = LocalMediaStore(tmp_path)
    _source(store, json.dumps(_record(veyra_user_id=41)), '{"id":"out_rounded","veyra_user_id":' + owner_token + '}')

    _assert_import_error(store)

    assert all(not rows for rows in _snapshot(store).values())
