from __future__ import annotations

import io
import json
import sqlite3
import threading
import traceback
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.schemas import ImageHistoryItem
from app.services import image_history


@pytest.fixture(params=[False, True], ids=["implicit-transactions", "autocommit"])
def history_path(tmp_path, monkeypatch, request):
    path = tmp_path / "image_history.jsonl"
    monkeypatch.setattr(
        image_history,
        "settings",
        SimpleNamespace(image_history_path=path, veyra_auth_enabled=True),
    )
    monkeypatch.setattr(image_history, "_HISTORY_DATABASES", OrderedDict())
    monkeypatch.setattr(image_history, "list_favorite_ids", lambda **_kwargs: set())
    if request.param:
        original_connect = image_history._history_connect

        def connect():
            connection = original_connect()
            connection.isolation_level = None
            return connection

        monkeypatch.setattr(image_history, "_history_connect", connect)
    return path


def _item(output_id="out-a", *, day=1, owner=41, prompt="private prompt"):
    timestamp = datetime(2026, 1, day, tzinfo=timezone.utc)
    return ImageHistoryItem(
        output_id=output_id,
        job_id=f"job-{output_id}",
        provider_id="provider",
        model="model",
        prompt=prompt,
        url=f"/outputs/{output_id}",
        metadata={"veyra_user_id": owner} if owner is not None else {},
        created_at=timestamp,
        updated_at=timestamp,
    )


def _write(path, *items):
    path.write_text("\n".join(item.model_dump_json() for item in items) + "\n", encoding="utf-8")


def _state():
    connection = image_history._history_connect()
    try:
        rows = [tuple(row) for row in connection.execute("SELECT * FROM v2_image_history ORDER BY output_id")]
        markers = [tuple(row) for row in connection.execute("SELECT * FROM v2_image_history_migration")]
        return rows, markers
    finally:
        connection.close()


@pytest.mark.parametrize(
    "invalid_line",
    [
        '{"prompt":"do-not-expose-this-record",',
        '{"output_id":"do-not-expose-this-record"}',
        '["do-not-expose-this-record"]',
        '"do-not-expose-this-record"',
        "null",
    ],
    ids=["malformed-json", "invalid-schema", "array", "string", "null"],
)
def test_invalid_history_record_rolls_back_and_can_be_repaired(history_path, invalid_line):
    first = _item()
    second = _item("out-b")
    history_path.write_text("\n" + first.model_dump_json() + "\n" + invalid_line + "\n", encoding="utf-8")

    with pytest.raises(image_history.LegacyHistoryImportError, match=r"line 3") as raised:
        image_history.list_image_history(include_all=True)

    assert "do-not-expose-this-record" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])
    _write(history_path, first, second)
    response = image_history.list_image_history(include_all=True)
    assert response.total == 2
    assert {item.output_id for item in response.items} == {first.output_id, second.output_id}
    assert len(_state()[1]) == 1
    connection = image_history._history_connect()
    try:
        receipt = connection.execute(
            "SELECT importer_id, importer_version, record_count FROM v2_image_history_import_receipts "
            "WHERE migration_key='jsonl'"
        ).fetchone()
    finally:
        connection.close()
    assert tuple(receipt) == ("v2.history.jsonl", 1, 2)


def test_failed_history_import_restores_preexisting_rows_and_updates(history_path):
    original = _item(prompt="original durable value")
    connection = image_history._history_connect()
    try:
        image_history._upsert_history_item(connection, original)
        connection.commit()
    finally:
        connection.close()
    before = _state()
    replacement = _item(day=2, owner=41, prompt="attempted replacement")
    new = _item("out-new")
    history_path.write_text(
        replacement.model_dump_json() + "\n" + new.model_dump_json() + '\n{"prompt":"private broken row"}\n',
        encoding="utf-8",
    )

    with pytest.raises(image_history.LegacyHistoryImportError, match=r"line 3"):
        image_history._ensure_history_index()

    assert _state() == before
    _write(history_path, replacement, new)
    assert image_history.get_image_history_item(original.output_id) == replacement
    assert image_history.get_image_history_item(new.output_id) == new


def test_invalid_utf8_is_sanitized_and_retryable(history_path):
    history_path.write_bytes(_item().model_dump_json().encode("utf-8") + b'\n{"prompt":"secret-utf8-\xff"}\n')

    with pytest.raises(image_history.LegacyHistoryImportError, match="UTF-8") as raised:
        image_history._ensure_history_index()

    assert "secret-utf8" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])
    _write(history_path, _item())
    assert image_history.get_image_history_item("out-a") == _item()


def test_v2_orphan_history_receipt_blocks_legacy_replay(history_path):
    _write(history_path, _item())
    image_history._ensure_history_index()
    connection = image_history._history_connect()
    try:
        connection.execute("DELETE FROM v2_image_history_migration WHERE migration_key='jsonl'")
        connection.commit()
    finally:
        connection.close()
    with pytest.raises(image_history.LegacyHistoryImportError, match="inconsistent"):
        image_history._ensure_history_index()
    connection = image_history._history_connect()
    try:
        assert connection.execute(
            "SELECT COUNT(*) FROM v2_image_history WHERE output_id='out-a'"
        ).fetchone()[0] == 1
    finally:
        connection.close()


@pytest.mark.parametrize("number", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
def test_nonfinite_json_numbers_fail_closed_without_losing_values(history_path, number):
    invalid = _item("out-invalid").model_dump_json().replace('"score":{}', f'"score":{{"private-number":{number}}}')
    history_path.write_text(_item().model_dump_json() + "\n" + invalid + "\n", encoding="utf-8")

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2") as raised:
        image_history._ensure_history_index()

    assert "private-number" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])


@pytest.mark.parametrize("field", ["output_id", "job_id"])
@pytest.mark.parametrize("value", ["", " \t ", "out\x00invalid"])
def test_invalid_required_history_identity_fails_closed(history_path, field, value):
    invalid = _item("out-invalid").model_dump(mode="json")
    invalid[field] = value
    history_path.write_text(_item().model_dump_json() + "\n" + json.dumps(invalid) + "\n", encoding="utf-8")

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2"):
        image_history._ensure_history_index()

    assert _state() == ([], [])


@pytest.mark.parametrize(
    "invalid_fields",
    [
        '"output_id":"out-invalid","output_id":"out-other"',
        '"metadata":{"veyra_user_id":41,"veyra_user_id":99}',
        '"prompt":"private-surrogate-\\ud800"',
        '"metadata":{"private-surrogate":"\\udfff"}',
        '"future_extra_field":"private-surrogate-\\ud800"',
    ],
    ids=["duplicate-identity-key", "duplicate-owner-key", "surrogate-prompt", "surrogate-metadata", "surrogate-unknown-field"],
)
def test_ambiguous_json_or_invalid_unicode_is_sanitized(history_path, invalid_fields):
    record = _item("out-invalid").model_dump(mode="json")
    record.pop(invalid_fields.split('"')[1], None)
    invalid = json.dumps(record)[:-1] + "," + invalid_fields + "}"
    history_path.write_text(_item().model_dump_json() + "\n" + invalid + "\n", encoding="utf-8")

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2") as raised:
        image_history._ensure_history_index()

    assert "private-surrogate" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])


@pytest.mark.parametrize("owners", [(41, None), (None, 41), (41, 99)])
@pytest.mark.parametrize("second_day", [1, 3], ids=["older-conflict", "newer-conflict"])
def test_duplicate_output_with_ambiguous_owners_rolls_back(history_path, owners, second_day):
    first_owner, second_owner = owners
    _write(history_path, _item(day=2, owner=first_owner), _item(day=second_day, owner=second_owner))

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2"):
        image_history._ensure_history_index()

    assert _state() == ([], [])
    _write(history_path, _item(day=2, owner=first_owner))
    assert image_history.get_image_history_item("out-a").metadata == _item(owner=first_owner).metadata


@pytest.mark.parametrize("owners", [(41, None), (None, 41), (41, 99)])
def test_import_cannot_change_a_preexisting_outputs_owner(history_path, owners):
    old_owner, new_owner = owners
    old_item = _item(owner=old_owner)
    connection = image_history._history_connect()
    try:
        image_history._upsert_history_item(connection, old_item)
        connection.commit()
    finally:
        connection.close()
    before = _state()
    _write(history_path, _item("out-new"), _item(day=2, owner=new_owner))

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2"):
        image_history._ensure_history_index()

    assert _state() == before


def test_ownerless_duplicates_keep_the_newest_payload(history_path):
    newest = _item(owner=None, day=3)
    _write(history_path, newest, _item(owner=None, day=1))

    assert image_history.get_image_history_item("out-a") == newest


@pytest.mark.parametrize("owner", ["bad-owner", [], {}, -7, True, False, 41.5, 41.0, 0.0, 2**63, str(2**63), "-1", "4_1", "\u0664\u0661", "+"])
@pytest.mark.parametrize("has_prefix", [False, True], ids=["first-record", "after-valid-record"])
def test_malformed_explicit_owner_never_becomes_public_and_can_be_repaired(history_path, owner, has_prefix):
    invalid = _item("out-invalid").model_copy(update={"metadata": {"veyra_user_id": owner}})
    prefix = [_item()] if has_prefix else []
    _write(history_path, *prefix, invalid)

    with pytest.raises(image_history.LegacyHistoryImportError, match=f"line {len(prefix) + 1}") as raised:
        image_history._ensure_history_index()

    assert "bad-owner" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])
    _write(history_path, *prefix, _item("out-invalid"))
    response = image_history.list_image_history(veyra_user_id=41, include_legacy_public=False)
    assert {item.output_id for item in response.items} == {item.output_id for item in [*prefix, invalid]}


@pytest.mark.parametrize(
    ("owner", "expected"),
    [(None, None), ("", None), (" \t ", None), (0, None), ("0", None), (1, 1), ("41", 41), (" +41 ", 41), ("00041", 41), (2**63 - 1, 2**63 - 1)],
)
def test_valid_legacy_owner_forms_keep_original_payload(history_path, owner, expected):
    item = _item().model_copy(update={"metadata": {"veyra_user_id": owner}})
    _write(history_path, item)

    assert image_history.get_image_history_item(item.output_id) == item
    rows, markers = _state()
    assert rows[0][2] == expected
    assert len(markers) == 1


@pytest.mark.parametrize("raw_owner", ["9007199254740993.0", "41.0000000000000001"])
def test_float_owner_precision_loss_never_changes_identity(history_path, raw_owner):
    invalid = _item("out-invalid").model_dump_json().replace('"veyra_user_id":41', f'"veyra_user_id":{raw_owner}')
    history_path.write_text(_item().model_dump_json() + "\n" + invalid + "\n", encoding="utf-8")

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2"):
        image_history._ensure_history_index()

    assert _state() == ([], [])


def test_excessive_metadata_nesting_is_a_safe_retryable_import_error(history_path):
    nested = "[" * 2000 + "0" + "]" * 2000
    invalid = _item("out-invalid").model_dump_json().replace(
        '"metadata":{"veyra_user_id":41}', '"metadata":{"private-deep":' + nested + "}"
    )
    history_path.write_text(_item().model_dump_json() + "\n" + invalid + "\n", encoding="utf-8")

    with pytest.raises(image_history.LegacyHistoryImportError, match="line 2") as raised:
        image_history._ensure_history_index()

    assert "private-deep" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])
    _write(history_path, _item())
    assert image_history.get_image_history_item("out-a") == _item()


@pytest.mark.parametrize("fail_during_read", [False, True], ids=["open", "midstream"])
def test_source_io_error_is_sanitized_and_retryable(history_path, monkeypatch, fail_during_read):
    first = _item()
    _write(history_path, first)
    original_open = Path.open

    class FailedRead(io.StringIO):
        def __next__(self):
            if self.tell():
                raise OSError("private source contents must not escape")
            return super().__next__()

    def failing_open(path, *args, **kwargs):
        if path == history_path:
            if fail_during_read:
                return FailedRead(first.model_dump_json() + "\n")
            raise PermissionError("private source contents must not escape")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", failing_open)
        with pytest.raises(image_history.LegacyHistoryImportError, match="read") as raised:
            image_history._ensure_history_index()

    assert "private source contents" not in "".join(traceback.format_exception(raised.value))
    assert _state() == ([], [])
    assert image_history.get_image_history_item("out-a") == first


def test_present_source_disappearing_before_open_is_not_a_completed_import(history_path, monkeypatch):
    _write(history_path, _item())
    original_open = Path.open

    def disappearing_open(path, *args, **kwargs):
        if path == history_path:
            raise FileNotFoundError("private source path")
        return original_open(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "open", disappearing_open)
        with pytest.raises(image_history.LegacyHistoryImportError, match="read"):
            image_history._ensure_history_index()

    assert _state() == ([], [])
    assert image_history.get_image_history_item("out-a") == _item()


def test_missing_source_does_not_prevent_later_import(history_path):
    assert image_history.list_image_history(include_all=True).total == 0
    assert _state() == ([], [])
    _write(history_path, _item())
    assert image_history.get_image_history_item("out-a") == _item()


@pytest.mark.parametrize("contents", ["", "\n \t\n"])
def test_empty_or_blank_source_is_a_complete_empty_import(history_path, contents):
    history_path.write_text(contents, encoding="utf-8")

    image_history._ensure_history_index()

    rows, markers = _state()
    assert rows == []
    assert len(markers) == 1


def test_migration_preserves_schema_compatibility_deduplication_and_owner_privacy(history_path):
    latest = _item(day=3, owner=41).model_copy(update={"score": {"finite": 1e308}})
    older = _item(day=1, owner=41)
    public = _item("out-public", owner=None)
    other = _item("out-other", owner=99)
    compatible = latest.model_dump(mode="json")
    compatible.update({"can_delete": "false", "future_extra_field": "ignored"})
    history_path.write_text(
        "\n".join([json.dumps(compatible), older.model_dump_json(), public.model_dump_json(), other.model_dump_json()]) + "\n",
        encoding="utf-8",
    )

    assert image_history.get_image_history_item("out-a") == latest
    assert image_history.list_image_history().total == 0
    private = image_history.list_image_history(veyra_user_id=41, include_legacy_public=False)
    assert [item.output_id for item in private.items] == [latest.output_id]
    including_public = image_history.list_image_history(veyra_user_id=41)
    assert {item.output_id for item in including_public.items} == {latest.output_id, public.output_id}


def test_completed_marker_never_reimports_deleted_rows_or_reopens_bad_source(history_path, monkeypatch):
    _write(history_path, _item())
    image_history._ensure_history_index()
    connection = image_history._history_connect()
    try:
        connection.execute("DELETE FROM v2_image_history")
        connection.commit()
    finally:
        connection.close()
    original_marker = _state()[1]
    history_path.write_text(_item().model_dump_json() + "\ninvalid-private-source\n", encoding="utf-8")

    def forbidden_open(*_args, **_kwargs):
        raise AssertionError("completed migration must not reopen its legacy source")

    monkeypatch.setattr(Path, "open", forbidden_open)
    assert image_history.list_image_history(include_all=True).total == 0
    assert _state() == ([], original_marker)


def test_database_write_failure_rolls_back_partial_history_import(history_path, monkeypatch):
    _write(history_path, _item(), _item("out-b"))
    original_upsert = image_history._upsert_history_item

    def failing_upsert(connection, item):
        original_upsert(connection, item)
        if item.output_id == "out-b":
            raise sqlite3.OperationalError("simulated database write failure")

    with monkeypatch.context() as patch:
        patch.setattr(image_history, "_upsert_history_item", failing_upsert)
        with pytest.raises(sqlite3.OperationalError, match="simulated"):
            image_history._ensure_history_index()

    assert _state() == ([], [])
    assert image_history.list_image_history(include_all=True).total == 2


def test_marker_write_failure_rolls_back_rows_and_marker(history_path):
    _write(history_path, _item())
    connection = image_history._history_connect()
    try:
        connection.execute(
            "CREATE TRIGGER fail_migration_marker AFTER INSERT ON v2_image_history_migration "
            "BEGIN SELECT RAISE(ABORT, 'simulated marker failure'); END"
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(sqlite3.IntegrityError, match="simulated marker failure"):
        image_history._ensure_history_index()

    assert _state() == ([], [])
    connection = image_history._history_connect()
    try:
        connection.execute("DROP TRIGGER fail_migration_marker")
        connection.commit()
    finally:
        connection.close()
    assert image_history.get_image_history_item("out-a") == _item()


def test_completed_import_does_not_need_a_writer_lock(history_path):
    _write(history_path, _item())
    image_history._ensure_history_index()
    writer = image_history._history_connect()
    try:
        writer.execute("BEGIN IMMEDIATE")
        assert image_history.get_image_history_item("out-a") == _item()
    finally:
        writer.rollback()
        writer.close()


def test_concurrent_initializers_serialize_marker_check_and_import_once(history_path, monkeypatch):
    items = [_item(f"out-{index}") for index in range(40)]
    _write(history_path, *items)
    original_connect = image_history._history_connect
    original_upsert = image_history._upsert_history_item
    statements: dict[int, list[str]] = {}
    imported: list[str] = []
    barrier = threading.Barrier(4)

    def traced_connect():
        connection = original_connect()
        connection.set_trace_callback(statements.setdefault(threading.get_ident(), []).append)
        return connection

    def counted_upsert(connection, item):
        imported.append(item.output_id)
        original_upsert(connection, item)

    def initialize():
        barrier.wait(timeout=5)
        image_history._ensure_history_index()

    with monkeypatch.context() as patch:
        patch.setattr(image_history, "_history_connect", traced_connect)
        patch.setattr(image_history, "_upsert_history_item", counted_upsert)
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(initialize) for _ in range(4)]
            for future in futures:
                future.result(timeout=10)

    assert sorted(imported) == sorted(item.output_id for item in items)
    assert len(statements) == 4
    for queries in statements.values():
        assert "SELECT 1 FROM v2_image_history_migration" in queries[0]
        if "BEGIN IMMEDIATE" in queries:
            begin_index = queries.index("BEGIN IMMEDIATE")
            assert "SELECT 1 FROM v2_image_history_migration" in queries[begin_index + 1]
            assert queries[-1] == "COMMIT"
        else:
            assert len(queries) == 1
    rows, markers = _state()
    assert len(rows) == len(items)
    assert len(markers) == 1
