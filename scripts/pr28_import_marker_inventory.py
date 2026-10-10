#!/usr/bin/env python3
"""Read-only inventory of PR #28 legacy import completion evidence.

This command never imports application modules or writes to the inspected DBs.
It reports migration evidence only; it is not a data reconciliation or repair
tool. Use explicit, frozen database copies when inspecting production state.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


_NAMESPACES = frozenset({"v1_history", "v1_favorites", "v2_history", "v2_favorites"})


def _readonly_connect(path: Path) -> sqlite3.Connection:
    resolved = path.expanduser().resolve(strict=True)
    if not resolved.is_file():
        raise FileNotFoundError
    connection = sqlite3.connect(f"{resolved.as_uri()}?mode=ro", uri=True, timeout=1.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only=ON")
    return connection


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _table_count(connection: sqlite3.Connection, table: str) -> int | None:
    if not _table_exists(connection, table):
        return None
    return int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])


def _receipt_row(
    connection: sqlite3.Connection,
    table: str,
    key_column: str,
    key: str,
    expected_importer: str,
) -> dict[str, Any] | None:
    if not _table_exists(connection, table):
        return None
    columns = {str(row[1]) for row in connection.execute(f'PRAGMA table_info("{table}")')}
    expected = {key_column, "importer_id", "importer_version", "record_count", "completed_at"}
    if not expected.issubset(columns):
        return {"valid": False}
    row = connection.execute(
        f'SELECT importer_id, importer_version, record_count, completed_at FROM "{table}" '
        f'WHERE "{key_column}"=?', (key,)
    ).fetchone()
    if row is None:
        return None
    valid = (
        row[0] == expected_importer
        and type(row[1]) is int
        and row[1] == 1
        and type(row[2]) is int
        and row[2] >= 0
        and isinstance(row[3], str)
        and bool(row[3])
    )
    if not valid:
        return {"valid": False}
    return {
        "valid": True,
        "importer_id": expected_importer,
        "importer_version": 1,
        "record_count": row[2],
    }


def inspect_database(namespace: str, path: Path) -> dict[str, Any]:
    if namespace not in _NAMESPACES:
        raise ValueError("unknown_namespace")
    connection = _readonly_connect(path)
    try:
        connection.execute("BEGIN")
        if namespace == "v1_history":
            table, marker_keys, importer, data_table = (
                "v1_history_state",
                ("jsonl_imported", "owner_evidence_backfilled"),
                "v1.history.jsonl",
                "v1_history_records",
            )
            if not _table_exists(connection, table):
                receipt = _receipt_row(connection, "v1_import_receipts", "namespace", "history", importer)
                status = "uninitialized" if receipt is None else (
                    "receipt_invalid" if receipt.get("valid") is False else "receipt_without_completion_marker"
                )
                result = {"namespace": namespace, "status": status, "record_count_now": None}
                if receipt and receipt.get("valid"):
                    result["receipt"] = receipt
                return result
            states = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    f'SELECT state_key, state_value FROM "{table}" '
                    "WHERE state_key IN (?, ?)", marker_keys
                )
            }
            complete_flags = [states.get(key) is not None for key in marker_keys]
            receipt = _receipt_row(connection, "v1_import_receipts", "namespace", "history", importer)
            marker_present = all(complete_flags)
            marker_any = any(complete_flags)
            count = _table_count(connection, data_table)
            marker_detail = {key: flag for key, flag in zip(marker_keys, complete_flags)}
        elif namespace == "v1_favorites":
            table, marker_key, importer, data_table = (
                "v1_favorite_state",
                "legacy_imported",
                "v1.favorites.json",
                "v1_favorites",
            )
            if not _table_exists(connection, table):
                receipt = _receipt_row(connection, "v1_import_receipts", "namespace", "favorites", importer)
                status = "uninitialized" if receipt is None else (
                    "receipt_invalid" if receipt.get("valid") is False else "receipt_without_completion_marker"
                )
                result = {"namespace": namespace, "status": status, "record_count_now": None}
                if receipt and receipt.get("valid"):
                    result["receipt"] = receipt
                return result
            states = {
                str(row[0]): str(row[1])
                for row in connection.execute(
                    f'SELECT state_key, state_value FROM "{table}" WHERE state_key=?',
                    (marker_key,),
                )
            }
            marker_present = states.get(marker_key) is not None
            receipt = _receipt_row(connection, "v1_import_receipts", "namespace", "favorites", importer)
            count = _table_count(connection, data_table)
            marker_detail = {marker_key: marker_present}
        elif namespace == "v2_history":
            marker_table, marker_key, receipt_table, importer, data_table = (
                "v2_image_history_migration",
                "jsonl",
                "v2_image_history_import_receipts",
                "v2.history.jsonl",
                "v2_image_history",
            )
            if not _table_exists(connection, marker_table):
                receipt = _receipt_row(connection, receipt_table, "migration_key", marker_key, importer)
                status = "uninitialized" if receipt is None else (
                    "receipt_invalid" if receipt.get("valid") is False else "receipt_without_completion_marker"
                )
                result = {"namespace": namespace, "status": status, "record_count_now": None}
                if receipt and receipt.get("valid"):
                    result["receipt"] = receipt
                return result
            marker_present = connection.execute(
                f'SELECT 1 FROM "{marker_table}" WHERE migration_key=?', (marker_key,)
            ).fetchone() is not None
            receipt = _receipt_row(connection, receipt_table, "migration_key", marker_key, importer)
            count = _table_count(connection, data_table)
            marker_detail = {marker_key: marker_present}
        else:
            marker_table, marker_key, receipt_table, importer, data_table = (
                "favorite_migrations",
                "legacy_json",
                "favorite_import_receipts",
                "v2.favorites.json",
                "favorites",
            )
            if not _table_exists(connection, marker_table):
                receipt = _receipt_row(connection, receipt_table, "migration_key", marker_key, importer)
                status = "uninitialized" if receipt is None else (
                    "receipt_invalid" if receipt.get("valid") is False else "receipt_without_completion_marker"
                )
                result = {"namespace": namespace, "status": status, "record_count_now": None}
                if receipt and receipt.get("valid"):
                    result["receipt"] = receipt
                return result
            marker_present = connection.execute(
                f'SELECT 1 FROM "{marker_table}" WHERE migration_key=?', (marker_key,)
            ).fetchone() is not None
            receipt = _receipt_row(connection, receipt_table, "migration_key", marker_key, importer)
            count = _table_count(connection, data_table)
            marker_detail = {marker_key: marker_present}

        if isinstance(receipt, dict) and receipt.get("valid") is False:
            status = "receipt_invalid"
        elif namespace == "v1_history" and marker_any and not marker_present:
            status = "incomplete_completion_marker"
        elif marker_present and receipt is None:
            status = "legacy_completion_unverified"
        elif not marker_present and receipt is not None:
            status = "receipt_without_completion_marker"
        elif not marker_present:
            status = "not_imported"
        else:
            status = "strict_import_receipt"
        if marker_present and count is None:
            status = "schema_incomplete"
        result: dict[str, Any] = {
            "namespace": namespace,
            "status": status,
            "markers": marker_detail,
            "record_count_now": count,
        }
        if receipt and receipt.get("valid"):
            result["receipt"] = receipt
        return result
    finally:
        connection.close()


def _parse_mapping(raw: str) -> tuple[str, Path]:
    namespace, separator, path = raw.partition("=")
    if not separator or namespace not in _NAMESPACES or not path:
        raise argparse.ArgumentTypeError("database arguments must be NAMESPACE=PATH")
    return namespace, Path(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", action="append", type=_parse_mapping, required=True, metavar="NAMESPACE=PATH")
    args = parser.parse_args(argv)
    namespaces = [namespace for namespace, _ in args.db]
    if len(set(namespaces)) != len(namespaces):
        parser.error("each namespace may be supplied at most once")
    results: list[dict[str, Any]] = []
    unreadable = False
    for namespace, path in args.db:
        try:
            results.append(inspect_database(namespace, path))
        except (OSError, sqlite3.Error, ValueError):
            unreadable = True
            results.append({"namespace": namespace, "status": "database_unreadable"})
    statuses = {str(item["status"]) for item in results}
    print(json.dumps({"tool": "pr28_import_marker_inventory_v1", "results": results}, sort_keys=True))
    if unreadable:
        return 3
    if statuses & {
        "legacy_completion_unverified",
        "receipt_invalid",
        "receipt_without_completion_marker",
        "incomplete_completion_marker",
        "schema_incomplete",
    }:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
