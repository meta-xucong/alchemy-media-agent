from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from json import JSONDecoder
from pathlib import Path
from typing import Any, Iterable

from app.config import settings


_INITIALIZED_PATHS: dict[str, None] = {}
_INITIALIZED_PATHS_MAX = 8
_SCHEMA_LOCK = threading.Lock()


def favorites_path() -> Path:
    """Legacy JSON location; retained as an import source and never truncated."""
    return settings.data_dir / "image_favorites.json"


def _database_path() -> Path:
    return settings.data_dir / "image_favorites.sqlite3"


def _connect() -> sqlite3.Connection:
    path = _database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=3.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout=3000")
    key = str(path.resolve())
    if key not in _INITIALIZED_PATHS:
        with _SCHEMA_LOCK:
            if key not in _INITIALIZED_PATHS:
                try:
                    connection.execute("PRAGMA journal_mode=WAL")
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS favorites (
                            output_id TEXT NOT NULL,
                            owner_key TEXT NOT NULL,
                            owner_id INTEGER,
                            created_at TEXT NOT NULL,
                            updated_at TEXT NOT NULL,
                            PRIMARY KEY(output_id, owner_key)
                        )"""
                    )
                    connection.execute("CREATE INDEX IF NOT EXISTS favorites_owner_idx ON favorites(owner_id, output_id)")
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS favorite_migrations (
                            migration_key TEXT PRIMARY KEY,
                            completed_at TEXT NOT NULL
                        )"""
                    )
                    _INITIALIZED_PATHS[key] = None
                    while len(_INITIALIZED_PATHS) > _INITIALIZED_PATHS_MAX:
                        _INITIALIZED_PATHS.pop(next(iter(_INITIALIZED_PATHS)))
                except Exception:
                    connection.close()
                    raise
    return connection


def _positive_int_or_none(value: Any) -> int | None:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _owner_key(owner_id: int | None) -> str:
    return str(owner_id) if owner_id is not None else ""


def _iter_json_array_items(handle, *, array_name: str = "items"):
    decoder = JSONDecoder()
    buffer = ""
    marker = f'"{array_name}"'
    array_started = False
    index = 0
    while not array_started:
        chunk = handle.read(64 * 1024)
        if not chunk:
            return
        buffer += chunk
        marker_index = buffer.find(marker)
        if marker_index < 0:
            buffer = buffer[-len(marker) :]
            continue
        array_index = buffer.find("[", marker_index + len(marker))
        if array_index < 0:
            continue
        buffer = buffer[array_index + 1 :]
        array_started = True

    while True:
        while index < len(buffer) and (buffer[index].isspace() or buffer[index] == ","):
            index += 1
        if index < len(buffer) and buffer[index] == "]":
            return
        try:
            item, end = decoder.raw_decode(buffer, index)
        except json.JSONDecodeError:
            chunk = handle.read(64 * 1024)
            if not chunk:
                raise ValueError("Legacy favorites JSON ended before the items array was complete.")
            buffer = buffer[index:] + chunk
            index = 0
            continue
        yield item
        buffer = buffer[end:]
        index = 0


def _ensure_imported(connection: sqlite3.Connection) -> None:
    if connection.execute(
        "SELECT 1 FROM favorite_migrations WHERE migration_key='legacy_json'"
    ).fetchone():
        return
    path = favorites_path()
    with connection:
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                for item in _iter_json_array_items(handle):
                    if not isinstance(item, dict):
                        continue
                    output_id = str(item.get("output_id") or "").strip()
                    if not output_id:
                        continue
                    owner_id = _positive_int_or_none(item.get("veyra_user_id"))
                    created_at = str(item.get("created_at") or "")
                    updated_at = str(item.get("updated_at") or created_at)
                    connection.execute(
                        """INSERT INTO favorites(output_id, owner_key, owner_id, created_at, updated_at)
                           VALUES(?, ?, ?, ?, ?) ON CONFLICT(output_id, owner_key) DO UPDATE SET
                           updated_at=MAX(favorites.updated_at, excluded.updated_at)""",
                        (output_id, _owner_key(owner_id), owner_id, created_at, updated_at),
                    )
        connection.execute(
            "INSERT INTO favorite_migrations(migration_key, completed_at) VALUES('legacy_json', ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )


def list_favorite_ids(
    *,
    veyra_user_id: int | None = None,
    include_legacy_public: bool = True,
    include_all: bool = False,
    output_ids: Iterable[str] | None = None,
) -> set[str]:
    if not include_all and veyra_user_id is None and settings.veyra_auth_enabled:
        return set()
    connection = _connect()
    try:
        _ensure_imported(connection)
        clauses: list[str] = []
        params: list[Any] = []
        if not include_all and veyra_user_id is not None:
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
        sql = "SELECT DISTINCT output_id FROM favorites"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        return {str(row[0]) for row in connection.execute(sql, params)}
    finally:
        connection.close()


def set_favorite(output_id: str, favorite: bool, *, veyra_user_id: int | None = None) -> dict[str, Any]:
    clean_id = str(output_id or "").strip()
    if not clean_id:
        raise ValueError("output_id is required")
    connection = _connect()
    changed = False
    now = datetime.now(timezone.utc).isoformat()
    try:
        _ensure_imported(connection)
        with connection:
            key = _owner_key(veyra_user_id)
            existing = connection.execute(
                "SELECT 1 FROM favorites WHERE output_id=? AND owner_key=?", (clean_id, key)
            ).fetchone()
            changed = bool(existing)
            if favorite:
                connection.execute(
                    """INSERT INTO favorites(output_id, owner_key, owner_id, created_at, updated_at)
                       VALUES(?, ?, ?, ?, ?) ON CONFLICT(output_id, owner_key) DO UPDATE SET
                       updated_at=excluded.updated_at""",
                    (clean_id, key, veyra_user_id, now, now),
                )
            else:
                connection.execute(
                    "DELETE FROM favorites WHERE output_id=? AND owner_key=?", (clean_id, key)
                )
    finally:
        connection.close()
    return {"output_id": clean_id, "favorite": bool(favorite), "changed": changed or bool(favorite)}


def delete_favorite(output_id: str) -> int:
    clean_id = str(output_id or "").strip()
    if not clean_id:
        return 0
    connection = _connect()
    try:
        with connection:
            _ensure_imported(connection)
            cursor = connection.execute("DELETE FROM favorites WHERE output_id=?", (clean_id,))
            return int(cursor.rowcount)
    finally:
        connection.close()
