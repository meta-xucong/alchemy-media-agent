from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from scripts.pr28_import_marker_inventory import inspect_database, main


def _create_v1(path: Path, namespace: str, *, marker: bool, receipt: bool, partial: bool = False):
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE v1_import_receipts(namespace TEXT PRIMARY KEY, importer_id TEXT NOT NULL, "
            "importer_version INTEGER NOT NULL, record_count INTEGER NOT NULL, completed_at TEXT NOT NULL)"
        )
        if namespace == "v1_history":
            connection.execute("CREATE TABLE v1_history_state(state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL)")
            connection.execute("CREATE TABLE v1_history_records(output_id TEXT)")
            if marker:
                connection.execute("INSERT INTO v1_history_state VALUES('jsonl_imported', '1')")
                if not partial:
                    connection.execute("INSERT INTO v1_history_state VALUES('owner_evidence_backfilled', '1')")
            importer = "v1.history.jsonl"
            receipt_namespace = "history"
        else:
            connection.execute("CREATE TABLE v1_favorite_state(state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL)")
            connection.execute("CREATE TABLE v1_favorites(output_id TEXT)")
            if marker:
                connection.execute("INSERT INTO v1_favorite_state VALUES('legacy_imported', 'now')")
            importer = "v1.favorites.json"
            receipt_namespace = "favorites"
        if receipt:
            connection.execute(
                "INSERT INTO v1_import_receipts VALUES(?, ?, 1, 12, 'now')",
                (receipt_namespace, importer),
            )
        connection.execute("INSERT INTO " + ("v1_history_records" if namespace == "v1_history" else "v1_favorites") + " VALUES('private-id')")


def _create_v2(path: Path, namespace: str, *, marker: bool, receipt: bool):
    with sqlite3.connect(path) as connection:
        if namespace == "v2_history":
            marker_table, marker_column, key, data_table, receipt_table, importer = (
                "v2_image_history_migration", "migration_key", "jsonl", "v2_image_history",
                "v2_image_history_import_receipts", "v2.history.jsonl",
            )
        else:
            marker_table, marker_column, key, data_table, receipt_table, importer = (
                "favorite_migrations", "migration_key", "legacy_json", "favorites",
                "favorite_import_receipts", "v2.favorites.json",
            )
        connection.execute(f'CREATE TABLE "{marker_table}"(migration_key TEXT PRIMARY KEY, completed_at TEXT NOT NULL)')
        connection.execute(f'CREATE TABLE "{data_table}"(item_id TEXT)')
        connection.execute(
            f'''CREATE TABLE "{receipt_table}"(
                migration_key TEXT PRIMARY KEY, importer_id TEXT NOT NULL,
                importer_version INTEGER NOT NULL, record_count INTEGER NOT NULL,
                completed_at TEXT NOT NULL)'''
        )
        if marker:
            connection.execute(f'INSERT INTO "{marker_table}" VALUES(?, ?)', (key, "now"))
        if receipt:
            connection.execute(f'INSERT INTO "{receipt_table}" VALUES(?, ?, 1, 12, ?)', (key, importer, "now"))
        connection.execute(f'INSERT INTO "{data_table}" VALUES(?)', ("private-id",))


def test_inventory_distinguishes_legacy_marker_from_strict_receipt_and_allows_native_changes(tmp_path):
    cases = (
        ("v1_history", _create_v1, True, False, "legacy_completion_unverified"),
        ("v1_favorites", _create_v1, True, True, "strict_import_receipt"),
        ("v2_history", _create_v2, True, True, "strict_import_receipt"),
        ("v2_favorites", _create_v2, False, True, "receipt_without_completion_marker"),
    )
    for namespace, create, marker, receipt, expected in cases:
        path = tmp_path / f"{namespace}.sqlite3"
        if create is _create_v1:
            create(path, namespace, marker=marker, receipt=receipt)
        else:
            create(path, namespace, marker=marker, receipt=receipt)
        result = inspect_database(namespace, path)
        assert result["status"] == expected
        if expected == "strict_import_receipt":
            assert result["receipt"]["record_count"] == 12
            assert result["record_count_now"] == 1


def test_v1_history_partial_markers_are_not_misclassified_as_uninitialized(tmp_path):
    path = tmp_path / "partial.sqlite3"
    _create_v1(path, "v1_history", marker=True, receipt=False, partial=True)
    assert inspect_database("v1_history", path)["status"] == "incomplete_completion_marker"


def test_inventory_detects_receipt_without_marker_table_and_marker_without_data_table(tmp_path):
    orphan = tmp_path / "orphan-receipt.sqlite3"
    with sqlite3.connect(orphan) as connection:
        connection.execute(
            "CREATE TABLE v1_import_receipts(namespace TEXT PRIMARY KEY, importer_id TEXT NOT NULL, "
            "importer_version INTEGER NOT NULL, record_count INTEGER NOT NULL, completed_at TEXT NOT NULL)"
        )
        connection.execute("INSERT INTO v1_import_receipts VALUES('favorites', 'v1.favorites.json', 1, 2, 'now')")
    assert inspect_database("v1_favorites", orphan)["status"] == "receipt_without_completion_marker"

    missing_data = tmp_path / "missing-data.sqlite3"
    _create_v2(missing_data, "v2_history", marker=True, receipt=True)
    with sqlite3.connect(missing_data) as connection:
        connection.execute("DROP TABLE v2_image_history")
    assert inspect_database("v2_history", missing_data)["status"] == "schema_incomplete"


def test_inventory_does_not_create_missing_database_or_leak_paths_ids_or_payload(tmp_path, capsys):
    missing = tmp_path / "never-created-private-path.sqlite3"
    assert main(["--db", f"v1_history={missing}"]) == 3
    assert not missing.exists()
    output = capsys.readouterr().out
    assert "never-created-private-path" not in output
    assert "private-id" not in output


def test_inventory_leaves_existing_database_bytes_unchanged(tmp_path):
    path = tmp_path / "read-only.sqlite3"
    _create_v2(path, "v2_history", marker=True, receipt=True)
    before = path.read_bytes()
    result = inspect_database("v2_history", path)
    after = path.read_bytes()
    assert result["status"] == "strict_import_receipt"
    assert after == before


def test_cli_uses_distinct_exit_code_for_legacy_markers(tmp_path, capsys):
    path = tmp_path / "legacy.sqlite3"
    _create_v1(path, "v1_favorites", marker=True, receipt=False)
    assert main(["--db", f"v1_favorites={path}"]) == 2
    result = json.loads(capsys.readouterr().out)
    assert result["results"][0]["status"] == "legacy_completion_unverified"


def test_invalid_receipt_is_redacted_and_classified(tmp_path):
    path = tmp_path / "bad-receipt.sqlite3"
    _create_v1(path, "v1_favorites", marker=True, receipt=False)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO v1_import_receipts VALUES('favorites', 'private-unexpected', 999, -4, 'secret')"
        )
    result = inspect_database("v1_favorites", path)
    assert result["status"] == "receipt_invalid"
    assert "private-unexpected" not in json.dumps(result)
    assert "secret" not in json.dumps(result)


def test_unknown_namespace_is_rejected_without_opening_database(tmp_path):
    missing = tmp_path / "never-created.sqlite3"
    try:
        inspect_database("unknown", missing)
    except ValueError as exc:
        assert str(exc) == "unknown_namespace"
    else:
        raise AssertionError("unknown namespace was accepted")
    assert not missing.exists()
