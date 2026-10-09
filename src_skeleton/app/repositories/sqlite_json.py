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


def json_value(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return value


class SQLiteJsonMap(MutableMapping[str, T], Generic[T]):
    """A dict-shaped, disk-backed mapping which never retains decoded records."""

    def __init__(
        self,
        database_path: Callable[[], Path] | Path,
        namespace: str,
        *,
        validator: Callable[[str], T],
        index_fields: Callable[[T], dict[str, str | None]] | None = None,
    ) -> None:
        self._database_path = database_path
        self._namespace = namespace
        self._validator = validator
        self._index_fields = index_fields or (lambda _value: {})

    @property
    def database_path(self) -> Path:
        path = self._database_path() if callable(self._database_path) else self._database_path
        return Path(path)

    def _connect(self) -> sqlite3.Connection:
        return connect(self.database_path)

    def _dump(self, value: T) -> tuple[str, dict[str, str | None]]:
        payload = json.dumps(json_value(value), ensure_ascii=False, separators=(",", ":"))
        fields = self._index_fields(value)
        return payload, fields

    def _put_on(self, connection: sqlite3.Connection, key: str, value: T) -> None:
        payload, fields = self._dump(value)
        connection.execute(
            """INSERT INTO v1_records(namespace, record_key, payload, session_id, job_type, sort_at, idempotency_key)
               VALUES(?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(namespace, record_key) DO UPDATE SET
                 payload=excluded.payload,
                 session_id=excluded.session_id,
                 job_type=excluded.job_type,
                 sort_at=excluded.sort_at,
                 idempotency_key=excluded.idempotency_key""",
            (
                self._namespace,
                str(key),
                payload,
                fields.get("session_id"),
                fields.get("job_type"),
                fields.get("sort_at"),
                fields.get("idempotency_key"),
            ),
        )

    def __getitem__(self, key: str) -> T:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT payload FROM v1_records WHERE namespace=? AND record_key=?",
                (self._namespace, str(key)),
            ).fetchone()
        finally:
            connection.close()
        if row is None:
            raise KeyError(key)
        return self._validator(row["payload"])

    def __setitem__(self, key: str, value: T) -> None:
        connection = self._connect()
        try:
            with connection:
                self._put_on(connection, str(key), value)
        finally:
            connection.close()

    def __delitem__(self, key: str) -> None:
        connection = self._connect()
        try:
            with connection:
                cursor = connection.execute(
                    "DELETE FROM v1_records WHERE namespace=? AND record_key=?",
                    (self._namespace, str(key)),
                )
                if cursor.rowcount == 0:
                    raise KeyError(key)
        finally:
            connection.close()

    def __iter__(self) -> Iterator[str]:
        connection = self._connect()
        cursor = connection.execute(
            "SELECT record_key FROM v1_records WHERE namespace=? ORDER BY record_key",
            (self._namespace,),
        )
        try:
            while row := cursor.fetchone():
                yield row[0]
        finally:
            cursor.close()
            connection.close()

    def __len__(self) -> int:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT COUNT(*) FROM v1_records WHERE namespace=?", (self._namespace,)
            ).fetchone()
            return int(row[0])
        finally:
            connection.close()

    def clear(self) -> None:
        connection = self._connect()
        try:
            with connection:
                connection.execute("DELETE FROM v1_records WHERE namespace=?", (self._namespace,))
        finally:
            connection.close()

    def get_job_by_idempotency_key(self, key: str) -> T | None:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT payload FROM v1_records WHERE namespace=? AND idempotency_key=? "
                "ORDER BY sort_at DESC LIMIT 1",
                (self._namespace, key),
            ).fetchone()
        finally:
            connection.close()
        return self._validator(row["payload"]) if row else None

    def iter_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> Iterator[T]:
        clauses = ["namespace=?"]
        parameters: list[str] = [self._namespace]
        if job_type:
            clauses.append("job_type=?")
            parameters.append(job_type)
        if session_id:
            clauses.append("session_id=?")
            parameters.append(session_id)
        connection = self._connect()
        cursor = None
        try:
            cursor = connection.execute(
                "SELECT payload FROM v1_records WHERE " + " AND ".join(clauses) +
                # The previous dict-backed implementation used Python's stable
                # sort, which preserved insertion order when timestamps tied.
                # SQLite rowid preserves that same order for an existing key.
                " ORDER BY sort_at DESC, rowid ASC",
                parameters,
            )
            while row := cursor.fetchone():
                yield self._validator(row[0])
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

    def list_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> list[T]:
        return list(self.iter_jobs(job_type=job_type, session_id=session_id))

    def write_records(self, records: list[tuple[str, T]]) -> None:
        connection = self._connect()
        try:
            with connection:
                for key, value in records:
                    self._put_on(connection, key, value)
        finally:
            connection.close()

    def get_record_json_on(self, connection: sqlite3.Connection, key: str) -> str | None:
        row = connection.execute(
            "SELECT payload FROM v1_records WHERE namespace=? AND record_key=?",
            (self._namespace, str(key)),
        ).fetchone()
        return str(row[0]) if row else None

    def delete_on(self, connection: sqlite3.Connection, key: str) -> int:
        cursor = connection.execute(
            "DELETE FROM v1_records WHERE namespace=? AND record_key=?",
            (self._namespace, str(key)),
        )
        return int(cursor.rowcount)

    def put_on(self, connection: sqlite3.Connection, key: str, value: T) -> None:
        self._put_on(connection, key, value)

    def validator(self, payload: str) -> T:
        return self._validator(payload)


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
                        """CREATE TABLE IF NOT EXISTS v1_records (
                            namespace TEXT NOT NULL, record_key TEXT NOT NULL, payload TEXT NOT NULL,
                            session_id TEXT, job_type TEXT, sort_at TEXT, idempotency_key TEXT,
                            PRIMARY KEY(namespace, record_key)
                        )"""
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS v1_records_jobs_idx "
                        "ON v1_records(namespace, session_id, job_type, sort_at DESC)"
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS v1_records_idem_idx ON v1_records(namespace, idempotency_key)"
                    )
                    connection.execute(
                        """CREATE TABLE IF NOT EXISTS v1_events (
                            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            session_id TEXT NOT NULL, event_type TEXT NOT NULL, payload TEXT NOT NULL
                        )"""
                    )
                    connection.execute(
                        "CREATE INDEX IF NOT EXISTS v1_events_session_idx ON v1_events(session_id, event_id)"
                    )
                    _INITIALIZED_DATABASES[key] = None
                    _INITIALIZED_DATABASES.move_to_end(key)
                    while len(_INITIALIZED_DATABASES) > _INITIALIZED_DATABASES_MAX:
                        _INITIALIZED_DATABASES.popitem(last=False)
                except Exception:
                    connection.close()
                    raise
    return connection
