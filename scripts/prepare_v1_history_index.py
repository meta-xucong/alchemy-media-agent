#!/usr/bin/env python3
"""Explicit offline V1/Lab projection maintenance; no app/worker bootstrap."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src_skeleton"))


def verify_derived_index(database: Path) -> tuple[dict, int]:
    """Read-only internal coherence check, not full authority/payload parity."""
    try:
        connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("BEGIN")
            state = dict(connection.execute("SELECT state_key,value FROM v1_read_state"))
            pending = int(connection.execute("SELECT COUNT(*) FROM v1_read_dirty").fetchone()[0])
            if (state.get("version") != "1" or "blocked" in state or pending
                    or Path(state.get("storage_root", "")) != database.parent.resolve()):
                return {"status": "not_ready", "pending_keys": pending}, 2
            dangling = int(connection.execute(
                "SELECT COUNT(*) FROM v1_read_winners w LEFT JOIN v1_read_sources s "
                "ON w.kind=s.kind AND w.source_key=s.source_key "
                "WHERE s.source_key IS NULL OR w.output_id!=s.output_id"
            ).fetchone()[0])
            expected = """WITH expected AS (
                SELECT surface,scope,-1 AS owner_id,0 AS non_mock,COUNT(*) AS total
                  FROM v1_read_winners GROUP BY surface,scope
                UNION ALL
                SELECT surface,scope,owner_id,0,COUNT(*) FROM v1_read_winners GROUP BY surface,scope,owner_id
                UNION ALL
                SELECT surface,scope,-1,1,COUNT(*) FROM v1_read_winners
                  WHERE surface='lab' AND is_mock=0 GROUP BY surface,scope
                UNION ALL
                SELECT surface,scope,owner_id,1,COUNT(*) FROM v1_read_winners
                  WHERE surface='lab' AND is_mock=0 GROUP BY surface,scope,owner_id
            ) """
            missing = connection.execute(expected +
                "SELECT * FROM expected EXCEPT SELECT * FROM v1_read_counts WHERE total>0 LIMIT 1"
            ).fetchone() is not None
            excess = connection.execute(expected +
                "SELECT * FROM v1_read_counts WHERE total>0 EXCEPT SELECT * FROM expected LIMIT 1"
            ).fetchone() is not None
            triggers = {row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'v1_read_%'"
            )}
            required = {"v1_read_records_" + event for event in ("insert", "update", "delete")}
            required.update("v1_read_" + table + "_" + event for table in
                            ("v1_history_records", "v1_history_owner_evidence")
                            for event in ("insert", "update", "delete"))
            coherent = not (dangling or missing or excess or not required.issubset(triggers))
            return {"status": "verified" if coherent else "inconsistent",
                    "scope": "derived_internal_coherence", "dangling_winners": dangling,
                    "count_buckets_match": not (missing or excess),
                    "tracking_triggers_present": required.issubset(triggers)}, 0 if coherent else 2
        finally:
            connection.close()
    except sqlite3.Error as exc:
        return {"status": "blocked", "error_type": type(exc).__name__}, 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true", help="Build once or catch up committed source changes.")
    modes.add_argument("--rebuild", action="store_true", help="Rebuild only derived tables from current authorities.")
    modes.add_argument("--reconcile", action="store_true", help="Observe unmanaged file changes and refresh the inventory.")
    modes.add_argument("--verify", action="store_true", help="Read-only derived coherence/count checks; no authority-parity claim.")
    args = parser.parse_args(argv)
    if not args.storage_root.is_dir():
        parser.error("--storage-root must name an existing directory")
    root = args.storage_root.resolve()
    if args.verify:
        result, code = verify_derived_index(root / "repository.sqlite3")
        print(json.dumps(result))
        return code
    # Set the singleton's root before importing any application package. Never
    # allow the caller's default storage path to become an implicit destination.
    os.environ["MEDIA_STORAGE_ROOT"] = str(root)
    os.environ["MEDIA_AGENT_PERSIST_RUNTIME_SETTINGS"] = "false"
    source = root / "history" / "outputs.jsonl"
    if source.exists():
        database = root / "repository.sqlite3"
        try:
            connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
            try:
                markers = {row[0] for row in connection.execute("SELECT state_key FROM v1_history_state")}
            finally:
                connection.close()
        except sqlite3.Error:
            markers = set()
        if not {"jsonl_imported", "owner_evidence_backfilled"}.issubset(markers):
            print(json.dumps({"status": "blocked", "error_type": "legacy_import_pending"}))
            return 2
    from app.repositories.history_index import prepare_history_index, reconcile_history_files
    from app.repositories.sqlite_json import connect
    from app.storage.local import LocalMediaStore

    store = LocalMediaStore(args.storage_root.resolve())
    try:
        if args.reconcile:
            reconcile_history_files(store)
        else:
            prepare_history_index(store, rebuild=args.rebuild)
        connection = connect(store.root / "repository.sqlite3")
        try:
            connection.execute("BEGIN")
            pending = int(connection.execute("SELECT COUNT(*) FROM v1_read_dirty").fetchone()[0])
            counts = {surface: int(connection.execute(
                "SELECT COALESCE(SUM(total),0) FROM v1_read_counts WHERE surface=? AND scope='global' AND owner_id=-1 AND non_mock=0",
                (surface,),
            ).fetchone()[0]) for surface in ("v1", "lab")}
            connection.commit()
        finally:
            connection.close()
        print(json.dumps({"status": "ready" if pending == 0 else "catch_up_pending", "pending_keys": pending, "counts": counts}))
        return 0 if pending == 0 else 2
    except Exception as exc:
        # SQLite/import exceptions can include private paths or source material.
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
