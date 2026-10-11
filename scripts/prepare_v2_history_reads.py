#!/usr/bin/env python3
"""Explicit V2 history/favorites preparation; no app lifespan or providers."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys


def disk_preflight(data_root: Path, history_path: Path, minimum_free_bytes: int | None) -> dict:
    locations = []
    for scope, database in (
        ("history", history_path.with_name("image_history_index.sqlite3")),
        ("favorites", data_root / "image_favorites.sqlite3"),
    ):
        footprint = {}
        for field, suffix in (("database_bytes", ""), ("wal_bytes", "-wal"), ("shm_bytes", "-shm")):
            try:
                footprint[field] = Path(str(database) + suffix).stat().st_size
            except FileNotFoundError:
                footprint[field] = 0
        locations.append({"scope": scope, "free_bytes": shutil.disk_usage(database.parent).free, **footprint})
    return {
        "minimum_free_bytes": minimum_free_bytes,
        "locations": locations,
        "within_budget": None if minimum_free_bytes is None else all(
            item["free_bytes"] >= minimum_free_bytes for item in locations
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-root", required=True, type=Path,
                        help="Existing V2 data directory containing image_favorites.json / SQLite.")
    parser.add_argument("--history-path", required=True, type=Path,
                        help="Explicit V2 image_history.jsonl source; its parent must already exist.")
    parser.add_argument("--minimum-free-bytes", type=int,
                        help="Required positive operator capacity budget for mutating preparation.")
    parser.add_argument("--preflight", action="store_true", help="Report disk capacity only; no database writes.")
    args = parser.parse_args(argv)
    if not args.data_root.is_dir() or not args.history_path.parent.is_dir():
        parser.error("--data-root and --history-path parent must be existing directories")
    if args.minimum_free_bytes is not None and args.minimum_free_bytes <= 0:
        parser.error("--minimum-free-bytes must be positive")
    if not args.preflight and args.minimum_free_bytes is None:
        parser.error("mutating preparation requires --minimum-free-bytes")
    try:
        preflight = disk_preflight(args.data_root, args.history_path, args.minimum_free_bytes)
    except OSError as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__}))
        return 2
    if args.preflight:
        print(json.dumps({"status": "preflight", "disk": preflight}))
        return 0
    if not preflight["within_budget"]:
        print(json.dumps({"status": "blocked", "error_type": "insufficient_free_space", "disk": preflight}))
        return 2
    os.environ["V2_DATA_DIR"] = str(args.data_root.resolve())
    os.environ["V2_IMAGE_HISTORY_PATH"] = str(args.history_path.resolve())
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_media_agent_2_0"))
    from app.services.image_history import prepare_history_reads

    try:
        prepare_history_reads()
    except Exception as exc:
        # Import/SQLite failures may embed source data or private paths.
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__, "disk": preflight}))
        return 2
    print(json.dumps({"status": "ready", "scope": "v2_history_and_favorites", "disk": preflight}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
