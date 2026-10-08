from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Awaitable, Callable, Iterator, TypeVar


class GenerationCapacityExceeded(RuntimeError):
    """Raised when V2 has no available provider-generation lease."""


T = TypeVar("T")


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path, timeout=5, isolation_level=None)
    connection.execute("PRAGMA busy_timeout=5000")
    return connection


@contextmanager
def _database(path: Path) -> Iterator[sqlite3.Connection]:
    connection = _connect(path)
    try:
        yield connection
    finally:
        connection.close()


def _ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_leases (
            namespace TEXT NOT NULL,
            slot INTEGER NOT NULL,
            owner_token TEXT NOT NULL,
            lease_until REAL NOT NULL,
            heartbeat_at REAL NOT NULL,
            PRIMARY KEY(namespace, slot)
        )
        """
    )


def terminalize_exhausted_stale_tasks(
    connection: sqlite3.Connection,
    *,
    stale_before: str,
    now_text: str,
) -> int:
    """Preserve exhausted crashed tasks as failed rows so they stop blocking admission."""

    exists = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'v2_tasks'"
    ).fetchone()
    if not exists:
        return 0
    error_json = json.dumps(
        {
            "error_code": "worker_recovery_exhausted",
            "message": "The worker stopped during its final allowed attempt; this task was not retried.",
            "retryable": False,
        },
        separators=(",", ":"),
    )
    cursor = connection.execute(
        """
        UPDATE v2_tasks
        SET status = 'failed', error_json = ?, locked_by = NULL, locked_at = NULL,
            not_before = NULL, updated_at = ?
        WHERE status = 'running' AND locked_at IS NOT NULL AND locked_at < ?
          AND attempts >= max_attempts
        """,
        (error_json, now_text, stale_before),
    )
    return int(cursor.rowcount or 0)


def _reserve(
    path: Path,
    namespace: str,
    limit: int,
    lease_ttl_seconds: float,
    request_kind: str,
    queue_recovery_timeout_seconds: float | None = None,
) -> tuple[int, str] | None:
    now = time.time()
    token = uuid.uuid4().hex
    with _database(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_table(connection)
        if request_kind == "direct":
            queue_table = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'v2_tasks'"
            ).fetchone()
            if queue_table and queue_recovery_timeout_seconds is not None:
                now_utc = datetime.now(timezone.utc)
                now_text = now_utc.isoformat()
                stale_before = (
                    now_utc - timedelta(seconds=max(0.01, queue_recovery_timeout_seconds))
                ).isoformat()
                terminalize_exhausted_stale_tasks(connection, stale_before=stale_before, now_text=now_text)
            if queue_table and connection.execute(
                "SELECT 1 FROM v2_tasks WHERE status IN ('queued', 'running') LIMIT 1"
            ).fetchone():
                connection.rollback()
                return None
        for slot in range(limit):
            row = connection.execute(
                "SELECT lease_until FROM resource_leases WHERE namespace = ? AND slot = ?",
                (namespace, slot),
            ).fetchone()
            if row is not None and float(row[0]) > now:
                continue
            connection.execute(
                """
                INSERT INTO resource_leases(namespace, slot, owner_token, lease_until, heartbeat_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(namespace, slot) DO UPDATE SET
                    owner_token = excluded.owner_token,
                    lease_until = excluded.lease_until,
                    heartbeat_at = excluded.heartbeat_at
                """,
                (namespace, slot, token, now + lease_ttl_seconds, now),
            )
            connection.commit()
            return slot, token
        connection.rollback()
    return None


def _heartbeat(path: Path, namespace: str, slot: int, token: str, ttl: float, stop: threading.Event) -> None:
    while not stop.wait(min(30.0, max(0.05, ttl / 3.0))):
        now = time.time()
        try:
            with _database(path) as connection:
                connection.execute("BEGIN IMMEDIATE")
                cursor = connection.execute(
                    "UPDATE resource_leases SET lease_until = ?, heartbeat_at = ? WHERE namespace = ? AND slot = ? AND owner_token = ?",
                    (now + ttl, now, namespace, slot, token),
                )
                connection.commit()
                if cursor.rowcount != 1:
                    return
        except sqlite3.Error:
            continue


@contextmanager
def generation_capacity(
    database_path: Path,
    *,
    limit: int = 1,
    namespace: str = "generation",
    request_kind: str = "direct",
    lease_ttl_seconds: float = 960.0,
    queue_recovery_timeout_seconds: float | None = None,
) -> Iterator[None]:
    """Acquire a heartbeat-renewed same-host lease shared by V2 API/workers.

    The lease uses the same SQLite file as the durable queue so worker claims,
    queue inserts and direct admission serialize. Direct work yields to pending
    queued tasks. A crashed process is not re-admitted locally until its lease
    expires; that does not establish whether remote provider work has stopped.
    """

    safe_limit = max(1, min(int(limit), 32))
    safe_namespace = "".join(char for char in str(namespace).lower() if char.isalnum() or char == "-") or "generation"
    kind = "worker" if request_kind == "worker" else "direct"
    ttl = max(0.1, float(lease_ttl_seconds))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    path = database_path
    reserved = _reserve(path, safe_namespace, safe_limit, ttl, kind, queue_recovery_timeout_seconds)
    if reserved is None:
        raise GenerationCapacityExceeded("V2 image generation capacity is currently full or queued work has priority.")

    slot, token = reserved
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        args=(path, safe_namespace, slot, token, ttl, stop),
        name=f"v2-capacity-{safe_namespace}-{slot}",
        daemon=True,
    )
    heartbeat.start()
    try:
        yield
    finally:
        stop.set()
        heartbeat.join(timeout=1.0)
        with _database(path) as connection:
            connection.execute(
                "DELETE FROM resource_leases WHERE namespace = ? AND slot = ? AND owner_token = ?",
                (safe_namespace, slot, token),
            )


async def run_with_generation_capacity(
    operation: Callable[[], Awaitable[T]],
    *,
    database_path: Path,
    limit: int = 1,
    namespace: str = "generation",
    request_kind: str = "direct",
    lease_ttl_seconds: float = 960.0,
    queue_recovery_timeout_seconds: float | None = None,
) -> T:
    """Run provider work while preserving its lease through caller cancellation."""

    with generation_capacity(
        database_path,
        limit=limit,
        namespace=namespace,
        request_kind=request_kind,
        lease_ttl_seconds=lease_ttl_seconds,
        queue_recovery_timeout_seconds=queue_recovery_timeout_seconds,
    ):
        return await run_with_existing_generation_capacity(operation)


async def run_with_existing_generation_capacity(operation: Callable[[], Awaitable[T]]) -> T:
    """Shield an operation when its caller already owns the local lease."""

    task = asyncio.create_task(operation())
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        while not task.done():
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                continue
            except BaseException:
                break
        try:
            task.result()
        except BaseException:
            pass
        raise
