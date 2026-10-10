from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime, timezone
from json import JSONDecoder
from pathlib import Path
from typing import Any, Iterable

from app.repositories.sqlite_json import connect
from app.storage import media_store


class LegacyFavoritesImportError(ValueError):
    """A repairable legacy-source failure with no source payload in its message."""


_STRICT_IMPORTER_ID = "v1.favorites.json"
_STRICT_IMPORTER_VERSION = 1


def favorites_path() -> Path:
    """Legacy JSON path, kept intact as the one-time import source."""
    return media_store.root / "favorites" / "image_favorites.json"


def _reject_json_constant(_value: str):
    raise LegacyFavoritesImportError("Legacy V1 favorites contain a non-finite JSON number.")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise LegacyFavoritesImportError("Legacy V1 favorites contain a non-finite JSON number.")
    return parsed


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise LegacyFavoritesImportError("Legacy V1 favorites contain duplicate object keys.")
        result[key] = value
    return result


def _validate_json_strings(value: Any) -> None:
    # Validate only the current decoded value, never collect the source's items.
    if isinstance(value, str):
        value.encode("utf-8")
    elif isinstance(value, dict):
        for key, item in value.items():
            key.encode("utf-8")
            _validate_json_strings(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json_strings(item)


class _StreamingJSONReader:
    def __init__(self, handle) -> None:
        self.handle = handle
        self.decoder = JSONDecoder(
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
            object_pairs_hook=_unique_json_object,
        )
        self.buffer = ""
        self.position = 0
        self.eof = False

    def _fill(self) -> bool:
        if self.position:
            self.buffer = self.buffer[self.position :]
            self.position = 0
        chunk = self.handle.read(64 * 1024)
        if not chunk:
            self.eof = True
            return False
        self.buffer += chunk
        return True

    def peek(self) -> str | None:
        while self.position >= len(self.buffer) and not self.eof:
            self._fill()
        return self.buffer[self.position] if self.position < len(self.buffer) else None

    def consume(self, expected: str) -> None:
        self.skip_whitespace()
        if self.peek() != expected:
            raise ValueError("Legacy V1 favorites file is not a complete JSON object.")
        self.position += 1

    def skip_whitespace(self) -> None:
        while (char := self.peek()) is not None and char in " \t\r\n":
            self.position += 1

    def value(self):
        self.skip_whitespace()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError:
                if not self._fill():
                    raise ValueError("Legacy V1 favorites file ended before its JSON value was complete.") from None
            else:
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    token_may_continue = end >= len(self.buffer) or self.buffer[end] in "0123456789.eE"
                    if token_may_continue and not self.eof:
                        self._fill()
                        continue
                _validate_json_strings(value)
                self.position = end
                return value

    def array_items(self):
        self.consume("[")
        self.skip_whitespace()
        if self.peek() == "]":
            self.position += 1
            return
        while True:
            yield self.value()
            self.skip_whitespace()
            separator = self.peek()
            if separator == "]":
                self.position += 1
                return
            if separator != ",":
                raise ValueError("Legacy V1 favorites items array is malformed.")
            self.position += 1
            self.skip_whitespace()
            if self.peek() == "]":
                raise ValueError("Legacy V1 favorites items array has a trailing comma.")

    def finish(self) -> None:
        self.skip_whitespace()
        if self.peek() is not None:
            raise ValueError("Legacy V1 favorites file has trailing data after its JSON object.")


def _iter_items(handle):
    reader = _StreamingJSONReader(handle)
    if reader.peek() == "\ufeff":
        reader.position += 1
    reader.consume("{")
    found_items = False
    seen_keys: set[str] = set()
    root_key_chars = 0
    reader.skip_whitespace()
    if reader.peek() != "}":
        while True:
            key = reader.value()
            if not isinstance(key, str):
                raise ValueError("Legacy V1 favorites object contains a non-string key.")
            if key in seen_keys:
                raise LegacyFavoritesImportError("Legacy V1 favorites contain duplicate object keys.")
            # Legacy writers emit only "items". Permit bounded extra metadata
            # without retaining an arbitrary number or size of root key names.
            if len(seen_keys) >= 64 or root_key_chars + len(key) > 64 * 1024:
                raise LegacyFavoritesImportError("Legacy V1 favorites have excessive root metadata.")
            seen_keys.add(key)
            root_key_chars += len(key)
            reader.consume(":")
            if key == "items":
                if found_items:
                    raise ValueError("Legacy V1 favorites object contains duplicate items fields.")
                found_items = True
                yield from reader.array_items()
            else:
                reader.value()
            reader.skip_whitespace()
            separator = reader.peek()
            if separator == "}":
                break
            if separator != ",":
                raise ValueError("Legacy V1 favorites object is malformed.")
            reader.position += 1
    reader.consume("}")
    reader.finish()
    if not found_items:
        raise ValueError("Legacy V1 favorites object has no items array.")


def _legacy_owner_id(value: Any) -> int | None:
    # Legacy writers emitted integers/null. Float tokens may already have lost
    # owner identity through JSON rounding, even when they look integral here.
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        digits = value[1:] if value.startswith("+") else value
        if not digits.isascii() or not digits.isdecimal():
            raise LegacyFavoritesImportError("Legacy V1 favorite has an invalid owner ID.")
    elif isinstance(value, bool) or not isinstance(value, int):
        raise LegacyFavoritesImportError("Legacy V1 favorite has an invalid owner ID.")
    parsed = int(value)
    if not 0 <= parsed <= 2**63 - 1:
        raise LegacyFavoritesImportError("Legacy V1 favorite has an invalid owner ID.")
    return parsed if parsed > 0 else None


def _validated_legacy_item(item: Any) -> tuple[str, int | None, str, str]:
    if not isinstance(item, dict):
        raise LegacyFavoritesImportError("Legacy V1 favorite item must be an object.")
    output_id = item.get("output_id")
    if not isinstance(output_id, str) or not output_id.strip() or "\x00" in output_id:
        raise LegacyFavoritesImportError("Legacy V1 favorite has an invalid output ID.")
    owner_id = _legacy_owner_id(item.get("veyra_user_id"))
    for field in ("created_at", "updated_at"):
        if item.get(field) is not None and not isinstance(item[field], str):
            raise LegacyFavoritesImportError("Legacy V1 favorite has an invalid timestamp.")
    created_at = item.get("created_at") or ""
    updated_at = item.get("updated_at") or created_at
    return output_id.strip(), owner_id, created_at, updated_at


def _owner_key(owner_id: int | None) -> str:
    return str(owner_id) if owner_id is not None else ""


def _ensure_imported(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE IF NOT EXISTS v1_favorites (
            output_id TEXT NOT NULL, owner_key TEXT NOT NULL, owner_id INTEGER,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            PRIMARY KEY(output_id, owner_key)
        )"""
    )
    connection.execute("CREATE INDEX IF NOT EXISTS v1_favorites_owner_idx ON v1_favorites(owner_id, output_id)")
    connection.execute(
        """CREATE TABLE IF NOT EXISTS v1_favorite_state (
            state_key TEXT PRIMARY KEY, state_value TEXT NOT NULL
        )"""
    )
    connection.execute(
        """CREATE TABLE IF NOT EXISTS v1_import_receipts (
            namespace TEXT PRIMARY KEY, importer_id TEXT NOT NULL,
            importer_version INTEGER NOT NULL, record_count INTEGER NOT NULL,
            completed_at TEXT NOT NULL
        )"""
    )
    path = favorites_path()
    connection.execute("BEGIN IMMEDIATE")
    try:
        if connection.execute(
            "SELECT 1 FROM v1_favorite_state WHERE state_key='legacy_imported'"
        ).fetchone():
            connection.commit()
            return
        if connection.execute(
            "SELECT 1 FROM v1_import_receipts WHERE namespace='favorites'"
        ).fetchone():
            raise LegacyFavoritesImportError(
                "Legacy V1 favorites import state is inconsistent; inspect the database before retrying."
            )
        if not path.exists():
            connection.commit()
            return
        imported_count = 0
        with path.open("r", encoding="utf-8") as handle:
            for item in _iter_items(handle):
                output_id, owner_id, created_at, updated_at = _validated_legacy_item(item)
                connection.execute(
                    """INSERT INTO v1_favorites(output_id, owner_key, owner_id, created_at, updated_at)
                       VALUES(?, ?, ?, ?, ?) ON CONFLICT(output_id, owner_key) DO UPDATE SET
                       updated_at=MAX(v1_favorites.updated_at, excluded.updated_at)""",
                    (output_id, _owner_key(owner_id), owner_id, created_at, updated_at),
                )
                imported_count += 1
        completed_at = datetime.now(timezone.utc).isoformat()
        connection.execute(
            """INSERT INTO v1_import_receipts(
                   namespace, importer_id, importer_version, record_count, completed_at
               ) VALUES('favorites', ?, ?, ?, ?)""",
            (_STRICT_IMPORTER_ID, _STRICT_IMPORTER_VERSION, imported_count, completed_at),
        )
        connection.execute(
            "INSERT INTO v1_favorite_state(state_key, state_value) VALUES('legacy_imported', ?)",
            (completed_at,),
        )
        connection.commit()
    except (ValueError, OSError, RecursionError, OverflowError) as exc:
        connection.rollback()
        if isinstance(exc, LegacyFavoritesImportError):
            raise
        raise LegacyFavoritesImportError(
            "Legacy V1 favorites import failed; repair the source and retry."
        ) from None
    except Exception:
        connection.rollback()
        raise


def list_favorite_ids(
    *,
    veyra_user_id: int | None = None,
    include_legacy_public: bool = True,
    output_ids: Iterable[str] | None = None,
) -> set[str]:
    connection = connect(media_store.root / "repository.sqlite3")
    try:
        _ensure_imported(connection)
        clauses: list[str] = []
        params: list[Any] = []
        if veyra_user_id is not None:
            if include_legacy_public:
                clauses.append("(owner_id=? OR owner_id IS NULL)")
                params.append(veyra_user_id)
            else:
                clauses.append("owner_id=?")
                params.append(veyra_user_id)
        if output_ids is not None:
            ids = [str(item) for item in output_ids if str(item)]
            if not ids:
                return set()
            clauses.append("output_id IN (" + ",".join("?" for _ in ids) + ")")
            params.extend(ids)
        sql = "SELECT DISTINCT output_id FROM v1_favorites"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return {str(row[0]) for row in connection.execute(sql, params)}
    finally:
        connection.close()


def set_favorite(output_id: str, favorite: bool, *, veyra_user_id: int | None = None) -> dict[str, Any]:
    clean_id = str(output_id or "").strip()
    if not clean_id:
        raise ValueError("output_id is required")
    connection = connect(media_store.root / "repository.sqlite3")
    now = datetime.now(timezone.utc).isoformat()
    try:
        _ensure_imported(connection)
        with connection:
            owner_key = _owner_key(veyra_user_id)
            existing = connection.execute(
                "SELECT 1 FROM v1_favorites WHERE output_id=? AND owner_key=?",
                (clean_id, owner_key),
            ).fetchone()
            changed = bool(existing)
            if favorite:
                connection.execute(
                    """INSERT INTO v1_favorites(output_id, owner_key, owner_id, created_at, updated_at)
                       VALUES(?, ?, ?, ?, ?) ON CONFLICT(output_id, owner_key) DO UPDATE SET
                       updated_at=excluded.updated_at""",
                    (clean_id, owner_key, veyra_user_id, now, now),
                )
            else:
                connection.execute(
                    "DELETE FROM v1_favorites WHERE output_id=? AND owner_key=?", (clean_id, owner_key)
                )
    finally:
        connection.close()
    return {"output_id": clean_id, "favorite": bool(favorite), "changed": changed or bool(favorite)}


def delete_favorite(output_id: str) -> int:
    clean_id = str(output_id or "").strip()
    if not clean_id:
        return 0
    connection = connect(media_store.root / "repository.sqlite3")
    try:
        _ensure_imported(connection)
        with connection:
            cursor = connection.execute("DELETE FROM v1_favorites WHERE output_id=?", (clean_id,))
            return int(cursor.rowcount)
    finally:
        connection.close()
