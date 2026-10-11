"""Explicit read-only verifier for prepared V2 history/favorites projections."""
from __future__ import annotations

import sqlite3
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from app.schemas import ImageHistoryItem
from app.services.image_history import (
    _finite_json_float,
    _legacy_history_owner_id,
    _timestamp,
    _unique_json_object,
)
from app.services.history_counts import verify_history_counts

MAX_HISTORY_SOURCE_LINE_BYTES = 4 * 1024 * 1024


class HistoryReadVerificationError(RuntimeError):
    """The read projections are absent or inconsistent; preparation is required."""


def verify_history_reads(data_root: Path, history_path: Path) -> dict[str, Any]:
    """Check readiness without creating databases, importing sources, or repairing state."""
    data_root = data_root.resolve()
    history_path = history_path.resolve()
    history_database = history_path.with_name("image_history_index.sqlite3")
    favorites_database = data_root / "image_favorites.sqlite3"
    if not history_database.is_file() or not favorites_database.is_file():
        raise HistoryReadVerificationError("V2 history and favorites indexes require explicit preparation.")

    history = sqlite3.connect(history_database.as_uri() + "?mode=ro", uri=True)
    try:
        history.execute("PRAGMA query_only=ON")
        history.execute("PRAGMA cache_size=-2048")
        history.execute("BEGIN")
        objects = {row[0] for row in history.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index') AND name IN "
            "('v2_image_history','v2_image_history_page_idx','v2_image_history_global_page_idx', "
            "'v2_image_history_migration','v2_image_history_import_receipts', "
            "'v2_history_counts','v2_history_count_state')"
        )}
        required = {
            "v2_image_history", "v2_image_history_page_idx", "v2_image_history_global_page_idx",
            "v2_image_history_migration", "v2_image_history_import_receipts",
            "v2_history_counts", "v2_history_count_state",
        }
        if not required.issubset(objects):
            raise HistoryReadVerificationError("V2 history index schema is incomplete.")
        verify_history_counts(history)
        migration = history.execute(
            "SELECT 1 FROM v2_image_history_migration WHERE migration_key='jsonl'"
        ).fetchone()
        receipt = history.execute(
            "SELECT 1 FROM v2_image_history_import_receipts WHERE migration_key='jsonl'"
        ).fetchone()
        if receipt and not migration:
            raise HistoryReadVerificationError("V2 image history import state is inconsistent.")
        try:
            source_has_data = history_path.stat().st_size > 0
        except FileNotFoundError:
            source_has_data = False
        except OSError:
            raise HistoryReadVerificationError("V2 image history source requires operator verification.") from None
        if source_has_data and not migration:
            raise HistoryReadVerificationError("V2 image history source has not been imported.")
        history_source_count = _verify_history_source_parity(history, history_path)
    finally:
        history.close()

    favorites = sqlite3.connect(favorites_database.as_uri() + "?mode=ro", uri=True)
    try:
        favorites.execute("PRAGMA query_only=ON")
        check = favorites.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise HistoryReadVerificationError("V2 favorites database integrity check failed.")
        favorite_objects = {row[0] for row in favorites.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','index') AND name IN "
            "('favorites','favorites_owner_idx','favorite_migrations','favorite_import_receipts')"
        )}
        required_favorites = {"favorites", "favorites_owner_idx", "favorite_migrations", "favorite_import_receipts"}
        if favorite_objects != required_favorites:
            raise HistoryReadVerificationError("V2 favorites index schema is incomplete.")
        migration = favorites.execute(
            "SELECT 1 FROM favorite_migrations WHERE migration_key='legacy_json'"
        ).fetchone()
        receipt = favorites.execute(
            "SELECT 1 FROM favorite_import_receipts WHERE migration_key='legacy_json'"
        ).fetchone()
        if receipt and not migration:
            raise HistoryReadVerificationError("V2 favorites import state is inconsistent.")
        source_path = data_root / "image_favorites.json"
        try:
            source_exists = source_path.is_file()
        except OSError:
            raise HistoryReadVerificationError("V2 favorites source requires operator verification.") from None
        if source_exists and not migration:
            raise HistoryReadVerificationError("V2 favorites source has not been imported.")
    finally:
        favorites.close()

    return {
        "status": "verified",
        "scope": "v2_history_favorites_readiness",
        "history_source_parity": "verified",
        "history_records_reconciled": history_source_count,
        "favorites_authority": "sqlite_after_migration",
    }


def _verify_history_source_parity(history: sqlite3.Connection, history_path: Path) -> int:
    """Reconcile current JSONL and index with bounded memory and disk scratch only."""
    try:
        before = history_path.stat()
    except FileNotFoundError:
        before = None
    except OSError:
        raise HistoryReadVerificationError("V2 image history source requires operator verification.") from None
    scratch_bytes = max(16 * 1024 * 1024, (before.st_size if before else 0) * 2)
    if shutil.disk_usage(history_path.parent).free < scratch_bytes:
        raise HistoryReadVerificationError("V2 image history reconciliation scratch space is insufficient.")
    try:
        with tempfile.TemporaryDirectory(prefix="v2-history-verify-", dir=history_path.parent) as temporary:
            scratch = sqlite3.connect(str(Path(temporary) / "source.sqlite3"))
            try:
                scratch.execute("PRAGMA journal_mode=OFF")
                scratch.execute("PRAGMA synchronous=OFF")
                scratch.execute("PRAGMA cache_size=-2048")
                scratch.execute(
                    "CREATE TABLE source(output_id TEXT PRIMARY KEY, owner_id INTEGER, updated_epoch REAL NOT NULL, payload_hash TEXT NOT NULL)"
                )
                if before is not None:
                    with history_path.open("rb") as source:
                        line_number = 0
                        while True:
                            raw_line = source.readline(MAX_HISTORY_SOURCE_LINE_BYTES + 1)
                            if not raw_line:
                                break
                            line_number += 1
                            if len(raw_line) > MAX_HISTORY_SOURCE_LINE_BYTES:
                                raise HistoryReadVerificationError(
                                    f"V2 image history source record exceeds the verification limit at line {line_number}."
                                )
                            if not raw_line.strip():
                                continue
                            try:
                                line = raw_line.decode("utf-8")
                                payload = json.loads(
                                    line,
                                    parse_float=_finite_json_float,
                                    parse_constant=_finite_json_float,
                                    object_pairs_hook=_unique_json_object,
                                )
                                item = ImageHistoryItem.model_validate(payload)
                                if any(not value.strip() or "\x00" in value for value in (item.output_id, item.job_id)):
                                    raise ValueError("invalid identity")
                                owner_id = _legacy_history_owner_id(item.metadata)
                                previous = scratch.execute(
                                    "SELECT owner_id,updated_epoch FROM source WHERE output_id=?", (item.output_id,),
                                ).fetchone()
                                if previous and previous[0] != owner_id:
                                    raise ValueError("conflicting owner")
                                updated_epoch = _timestamp(item.updated_at)
                                payload_hash = hashlib.sha256(item.model_dump_json().encode("utf-8")).hexdigest()
                                scratch.execute(
                                    "INSERT INTO source VALUES(?,?,?,?) ON CONFLICT(output_id) DO UPDATE SET "
                                    "owner_id=excluded.owner_id,updated_epoch=excluded.updated_epoch,payload_hash=excluded.payload_hash "
                                    "WHERE excluded.updated_epoch>=source.updated_epoch",
                                    (item.output_id, owner_id, updated_epoch, payload_hash),
                                )
                            except (ValueError, OverflowError, RecursionError, UnicodeError, json.JSONDecodeError):
                                raise HistoryReadVerificationError(
                                    f"V2 image history source is invalid at line {line_number}."
                                ) from None
                scratch.commit()
                count = int(scratch.execute("SELECT COUNT(*) FROM source").fetchone()[0])
                index_count = int(history.execute("SELECT COUNT(*) FROM v2_image_history").fetchone()[0])
                if count != index_count:
                    raise HistoryReadVerificationError("V2 image history source and index record counts disagree.")
                rows = scratch.execute("SELECT output_id,owner_id,updated_epoch,payload_hash FROM source ORDER BY output_id")
                for output_id, owner_id, updated_epoch, payload_hash in rows:
                    indexed = history.execute(
                        "SELECT job_id,owner_id,created_epoch,updated_epoch,payload FROM v2_image_history WHERE output_id=?",
                        (output_id,),
                    ).fetchone()
                    if not indexed:
                        raise HistoryReadVerificationError("V2 image history source contains an unindexed record.")
                    try:
                        item = ImageHistoryItem.model_validate_json(indexed[4])
                    except (ValueError, TypeError):
                        raise HistoryReadVerificationError("V2 image history index payload is invalid.") from None
                    indexed_hash = hashlib.sha256(item.model_dump_json().encode("utf-8")).hexdigest()
                    if (
                        indexed_hash != payload_hash
                        or indexed[1] != owner_id
                        or indexed[0] != item.job_id
                        or indexed[2] != _timestamp(item.created_at)
                        or indexed[3] != updated_epoch
                    ):
                        raise HistoryReadVerificationError("V2 image history source and index records disagree.")
                return count
            finally:
                scratch.close()
    except HistoryReadVerificationError:
        raise
    except (OSError, sqlite3.Error, UnicodeError):
        raise HistoryReadVerificationError("V2 image history source reconciliation failed.") from None
    finally:
        try:
            after = history_path.stat()
        except FileNotFoundError:
            after = None
        except OSError:
            raise HistoryReadVerificationError("V2 image history source changed during verification.") from None
        if before is None:
            if after is not None:
                raise HistoryReadVerificationError("V2 image history source changed during verification.")
        elif after is None or (before.st_ino, before.st_size, before.st_mtime_ns) != (
            after.st_ino, after.st_size, after.st_mtime_ns,
        ):
            raise HistoryReadVerificationError("V2 image history source changed during verification.")
