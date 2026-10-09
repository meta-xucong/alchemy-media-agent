from __future__ import annotations

import json
import sqlite3
import threading
from collections import OrderedDict
from collections.abc import Iterator, MutableMapping
from pathlib import Path
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")
_INITIALIZED_DATABASES: OrderedDict[str, None] = OrderedDict()
_SCHEMA_LOCK = threading.Lock()
_INITIALIZED_DATABASES_MAX = 8


def connect(database_path: Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=0.75)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 750")
    key = str(path.resolve())
    if key not in _INITIALIZED_DATABASES:
        with _SCHEMA_LOCK:
            if key not in _INITIALIZED_DATABASES:
                try:
                    connection.execute("PRAGMA journal_mode = WAL")
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS v2_records (
                            namespace TEXT NOT NULL, record_key TEXT NOT NULL, payload TEXT NOT NULL,
                            provider_id TEXT, active INTEGER, quality REAL, index_version TEXT,
                            PRIMARY KEY(namespace, record_key)
                        )"""
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS v2_records_provider_idx ON v2_records(namespace, provider_id)"
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS v2_records_case_sort_idx "
                        "ON v2_records(namespace, active, quality DESC, record_key)"
                    )
                    _INITIALIZED_DATABASES[key] = None
                    _INITIALIZED_DATABASES.move_to_end(key)
                    while len(_INITIALIZED_DATABASES) > _INITIALIZED_DATABASES_MAX:
                        _INITIALIZED_DATABASES.popitem(last=False)
                except Exception:
                    connection.close()
                    raise
    return connection


def _json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


class SQLiteJsonMap(MutableMapping[str, T], Generic[T]):
    """V2-owned durable mapping with no process-wide decoded-record cache."""

    def __init__(
        self,
        database_path: Callable[[], Path] | Path,
        namespace: str,
        *,
        validator: Callable[[str], T],
        index_fields: Callable[[T], dict[str, Any]] | None = None,
    ) -> None:
        self._database_path = database_path
        self._namespace = namespace
        self._validator = validator
        self._index_fields = index_fields or (lambda _value: {})

    @property
    def database_path(self) -> Path:
        return Path(self._database_path() if callable(self._database_path) else self._database_path)

    def _payload(self, value: T) -> tuple[str, dict[str, Any]]:
        return json.dumps(_json_value(value), ensure_ascii=False, separators=(",", ":")), self._index_fields(value)

    def put_on(self, connection: sqlite3.Connection, key: str, value: T) -> None:
        payload, fields = self._payload(value)
        connection.execute(
            """INSERT INTO v2_records(namespace, record_key, payload, provider_id, active, quality, index_version)
               VALUES(?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(namespace, record_key) DO UPDATE SET
                 payload=excluded.payload, provider_id=excluded.provider_id,
                 active=excluded.active, quality=excluded.quality, index_version=excluded.index_version""",
            (
                self._namespace,
                str(key),
                payload,
                fields.get("provider_id"),
                fields.get("active"),
                fields.get("quality"),
                fields.get("index_version"),
            ),
        )

    def get_json_on(self, connection: sqlite3.Connection, key: str) -> str | None:
        row = connection.execute(
            "SELECT payload FROM v2_records WHERE namespace=? AND record_key=?",
            (self._namespace, str(key)),
        ).fetchone()
        return str(row[0]) if row else None

    def delete_on(self, connection: sqlite3.Connection, key: str) -> int:
        cursor = connection.execute(
            "DELETE FROM v2_records WHERE namespace=? AND record_key=?",
            (self._namespace, str(key)),
        )
        return int(cursor.rowcount)

    def __getitem__(self, key: str) -> T:
        connection = connect(self.database_path)
        try:
            payload = self.get_json_on(connection, key)
        finally:
            connection.close()
        if payload is None:
            raise KeyError(key)
        return self._validator(payload)

    def __setitem__(self, key: str, value: T) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                self.put_on(connection, key, value)
        finally:
            connection.close()

    def __delitem__(self, key: str) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                if self.delete_on(connection, key) == 0:
                    raise KeyError(key)
        finally:
            connection.close()

    def __iter__(self) -> Iterator[str]:
        connection = connect(self.database_path)
        cursor = connection.execute(
            "SELECT record_key FROM v2_records WHERE namespace=? ORDER BY record_key", (self._namespace,)
        )
        try:
            while row := cursor.fetchone():
                yield row[0]
        finally:
            cursor.close()
            connection.close()

    def __len__(self) -> int:
        connection = connect(self.database_path)
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM v2_records WHERE namespace=?", (self._namespace,)
            ).fetchone()
            return int(row[0])
        finally:
            connection.close()

    def clear(self) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                connection.execute("DELETE FROM v2_records WHERE namespace=?", (self._namespace,))
        finally:
            connection.close()

    def delete_provider(self, provider_id: str) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                connection.execute(
                    "DELETE FROM v2_records WHERE namespace=? AND provider_id=?",
                    (self._namespace, provider_id),
                )
        finally:
            connection.close()

    def list_values(self, *, active_only: bool = False) -> list[T]:
        connection = connect(self.database_path)
        try:
            sql = "SELECT payload FROM v2_records WHERE namespace=?"
            params: tuple[Any, ...] = (self._namespace,)
            if active_only:
                sql += " AND active=1"
            sql += " ORDER BY quality DESC, record_key"
            return [self._validator(row[0]) for row in connection.execute(sql, params)]
        finally:
            connection.close()

    def active_index_versions(self) -> list[str]:
        connection = connect(self.database_path)
        try:
            rows = connection.execute(
                "SELECT DISTINCT index_version FROM v2_records "
                "WHERE namespace=? AND active=1 AND index_version IS NOT NULL ORDER BY index_version",
                (self._namespace,),
            )
            return [str(row[0]) for row in rows]
        finally:
            connection.close()
