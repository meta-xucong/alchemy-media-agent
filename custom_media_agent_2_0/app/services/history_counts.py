"""Disposable V2 history totals, maintained in the history writer transaction.

Only managed connections with recursive_triggers=ON may write history. Manual
SQL maintenance requires verify/rebuild before serving reads again. Neither
maintenance operation reads JSONL or changes authoritative history records.
"""
from __future__ import annotations

import sqlite3


class HistoryCountIndexError(sqlite3.DatabaseError):
    """Derived state is unavailable; do not report an invented empty history."""


_VERSION = 1
_COUNTS = "v2_history_counts"
_STATE = "v2_history_count_state"
_NEW = "COALESCE(CAST(NEW.owner_id AS TEXT), 'public')"
_OLD = "COALESCE(CAST(OLD.owner_id AS TEXT), 'public')"
_GUARD = "SELECT RAISE(ABORT, 'V2 history count bucket missing') WHERE changes() != 1;"
_INCREMENT = f"""INSERT INTO {_COUNTS}(bucket, row_count) VALUES({_NEW}, 1)
    ON CONFLICT(bucket) DO UPDATE SET row_count=row_count+1;"""
_DDL = {
    _COUNTS: f"""CREATE TABLE {_COUNTS} (
        bucket TEXT PRIMARY KEY NOT NULL,
        row_count INTEGER NOT NULL CHECK(typeof(row_count)='integer' AND row_count>=0))""",
    _STATE: f"CREATE TABLE {_STATE} (singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL)",
    "v2_history_count_insert": f"""CREATE TRIGGER v2_history_count_insert
        AFTER INSERT ON v2_image_history BEGIN
        UPDATE {_COUNTS} SET row_count=row_count+1 WHERE bucket='all'; {_GUARD}
        {_INCREMENT} END""",
    "v2_history_count_delete": f"""CREATE TRIGGER v2_history_count_delete
        AFTER DELETE ON v2_image_history BEGIN
        UPDATE {_COUNTS} SET row_count=row_count-1 WHERE bucket={_OLD}; {_GUARD}
        DELETE FROM {_COUNTS} WHERE bucket={_OLD} AND row_count=0;
        UPDATE {_COUNTS} SET row_count=row_count-1 WHERE bucket='all'; {_GUARD} END""",
    "v2_history_count_owner_update": f"""CREATE TRIGGER v2_history_count_owner_update
        AFTER UPDATE OF owner_id ON v2_image_history WHEN OLD.owner_id IS NOT NEW.owner_id BEGIN
        UPDATE {_COUNTS} SET row_count=row_count-1 WHERE bucket={_OLD}; {_GUARD}
        DELETE FROM {_COUNTS} WHERE bucket={_OLD} AND row_count=0;
        {_INCREMENT} END""",
}


def _objects(connection: sqlite3.Connection) -> dict[str, str]:
    names = tuple(_DDL)
    return dict(connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE name IN (" + ",".join("?" for _ in names) + ")", names
    ))


def _validate(connection: sqlite3.Connection, objects: dict[str, str]) -> None:
    normalize = lambda value: " ".join(value.split()).lower()
    if set(objects) != set(_DDL) or any(normalize(objects[name]) != normalize(sql) for name, sql in _DDL.items()):
        raise HistoryCountIndexError("V2 history count schema is incomplete; verify and rebuild derived counts.")
    version = connection.execute(f"SELECT version FROM {_STATE} WHERE singleton=1").fetchone()
    global_count = connection.execute(f"SELECT row_count FROM {_COUNTS} WHERE bucket='all'").fetchone()
    if not version or version[0] != _VERSION or not global_count or not isinstance(global_count[0], int) or global_count[0] < 0:
        raise HistoryCountIndexError("V2 history count state is invalid; verify and rebuild derived counts.")


def _build(connection: sqlite3.Connection) -> None:
    for sql in _DDL.values():
        connection.execute(sql)
    connection.execute(f"""INSERT INTO {_COUNTS}(bucket, row_count)
        SELECT COALESCE(CAST(owner_id AS TEXT), 'public'), COUNT(*)
        FROM v2_image_history GROUP BY owner_id""")
    connection.execute(f"INSERT INTO {_COUNTS} VALUES('all', (SELECT COUNT(*) FROM v2_image_history))")
    connection.execute(f"INSERT INTO {_STATE} VALUES(1, ?)", (_VERSION,))


def ensure_history_counts(connection: sqlite3.Connection, *, allow_initialize: bool = True) -> None:
    """Validate bounded metadata each connect; backfill only a fresh schema."""
    objects = _objects(connection)
    if objects:
        _validate(connection, objects)
        return
    if not allow_initialize:
        raise HistoryCountIndexError("V2 history counts require explicit preparation.")
    connection.execute("BEGIN IMMEDIATE")
    try:
        # Another process may have published the complete schema while waiting.
        objects = _objects(connection)
        if objects:
            _validate(connection, objects)
        else:
            _build(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def read_history_count(connection: sqlite3.Connection, *, owner_id: int | None, include_public: bool, include_all: bool) -> int:
    buckets = ["all"] if include_all or owner_id is None else [str(owner_id)] + (["public"] if include_public else [])
    values = dict(connection.execute(
        f"SELECT bucket, row_count FROM {_COUNTS} WHERE bucket IN (" + ",".join("?" for _ in buckets) + ")", buckets
    ))
    for bucket in buckets:
        if bucket in values:
            continue
        # A genuinely absent owner needs no bucket; damaged populated buckets
        # must fail closed rather than silently undercount. Both probes seek
        # the existing owner index and stop after one row.
        if bucket == "all":
            raise HistoryCountIndexError("V2 history global count is missing.")
        sql, params = ("owner_id IS NULL", ()) if bucket == "public" else ("owner_id=?", (owner_id,))
        if connection.execute("SELECT 1 FROM v2_image_history WHERE " + sql + " LIMIT 1", params).fetchone():
            raise HistoryCountIndexError("V2 history owner count is missing; rebuild derived counts.")
    return sum(values.values())


def verify_history_counts(connection: sqlite3.Connection) -> None:
    """Read-only O(N) maintenance check in one snapshot; never a hot read."""
    owns_snapshot = not connection.in_transaction
    if owns_snapshot:
        connection.execute("BEGIN")
    try:
        _verify_snapshot(connection)
    finally:
        if owns_snapshot:
            connection.rollback()


def _verify_snapshot(connection: sqlite3.Connection) -> None:
    _validate(connection, _objects(connection))
    mismatch = connection.execute(f"""WITH expected AS (
        SELECT COALESCE(CAST(owner_id AS TEXT), 'public') AS bucket, COUNT(*) AS row_count
        FROM v2_image_history GROUP BY owner_id
        UNION ALL SELECT 'all', COUNT(*) FROM v2_image_history)
        SELECT 1 FROM (SELECT bucket, row_count FROM expected EXCEPT SELECT bucket, row_count FROM {_COUNTS})
        UNION ALL SELECT 1 FROM (SELECT bucket, row_count FROM {_COUNTS}
        EXCEPT SELECT bucket, row_count FROM expected) LIMIT 1""").fetchone()
    if mismatch:
        raise HistoryCountIndexError("V2 history counts disagree with authoritative rows; rebuild derived counts.")


def rebuild_history_counts(connection: sqlite3.Connection) -> None:
    """Authorized maintenance only: atomically rebuild these derived objects."""
    if connection.in_transaction:
        raise HistoryCountIndexError("Rebuild requires a connection outside a transaction.")
    connection.execute("PRAGMA recursive_triggers=ON")
    connection.execute("BEGIN IMMEDIATE")
    try:
        for name in _DDL:
            kind = "TABLE" if name in {_COUNTS, _STATE} else "TRIGGER"
            connection.execute(f"DROP {kind} IF EXISTS {name}")
        _build(connection)
        verify_history_counts(connection)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
