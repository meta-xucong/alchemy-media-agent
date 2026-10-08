from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, TypeVar

from app.config import settings


logger = logging.getLogger(__name__)


class GenerationCapacityExceeded(RuntimeError):
    """Raised when V2 has no available provider-generation lease."""


class GenerationCapacityStorageBusy(RuntimeError):
    """Raised when bounded local SQLite admission cannot proceed promptly."""


T = TypeVar("T")
_NO_RESULT = object()
_ASYNC_DB_SLOTS = threading.BoundedSemaphore(max(1, min(16, int(settings.resource_db_async_workers))))


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


def _is_sqlite_busy(exc: BaseException) -> bool:
    return isinstance(exc, sqlite3.OperationalError) and any(
        token in str(exc).lower() for token in ("locked", "busy")
    )


async def _wait_task_to_finish(task: asyncio.Task[T]) -> T:
    """Wait out caller cancellation so a SQLite thread cannot outlive its permit."""

    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            continue
        except BaseException:
            break
    return task.result()


async def run_sqlite_async(
    operation: Callable[[], T],
    *,
    on_cancel_result: Callable[[T], Any] | None = None,
    wait_for_slot: bool = False,
) -> T:
    """Run one local SQLite operation with finite, fail-fast thread admission.

    The permit remains held until the worker thread exits, including after
    caller cancellation. Callers that reserve a resource can provide a cleanup
    callback so a late reservation is released before cancellation is returned.
    """

    while not _ASYNC_DB_SLOTS.acquire(blocking=False):
        if not wait_for_slot:
            raise GenerationCapacityStorageBusy("V2 local database work is busy; please retry shortly.")
        await asyncio.sleep(0.01)

    def invoke() -> T:
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if _is_sqlite_busy(exc):
                raise GenerationCapacityStorageBusy("V2 local database work is busy; please retry shortly.") from exc
            raise

    worker = asyncio.create_task(asyncio.to_thread(invoke))
    permit_released = False

    def release_permit() -> None:
        nonlocal permit_released
        if not permit_released:
            permit_released = True
            _ASYNC_DB_SLOTS.release()

    try:
        return await asyncio.shield(worker)
    except asyncio.CancelledError as cancelled:
        result: T | object = _NO_RESULT
        try:
            result = await _wait_task_to_finish(worker)
        except BaseException:
            pass
        release_permit()
        if on_cancel_result is not None and result is not _NO_RESULT and result is not None:
            cleanup = asyncio.create_task(run_sqlite_async(lambda: on_cancel_result(result), wait_for_slot=True))
            try:
                await _wait_task_to_finish(cleanup)
            except BaseException:
                logger.exception("V2 late SQLite reservation cleanup failed after caller cancellation")
        raise cancelled
    finally:
        if worker.done():
            release_permit()
        else:
            worker.add_done_callback(lambda _task: release_permit())


def _ensure_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS resource_leases (
            namespace TEXT NOT NULL,
            slot INTEGER NOT NULL,
            owner_token TEXT NOT NULL,
            lease_until REAL NOT NULL,
            heartbeat_at REAL NOT NULL,
            owner_task_id TEXT,
            owner_claim_token TEXT,
            PRIMARY KEY(namespace, slot)
        )
        """
    )
    _ensure_column(connection, "resource_leases", "owner_task_id", "TEXT")
    _ensure_column(connection, "resource_leases", "owner_claim_token", "TEXT")


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
            claim_token = NULL, not_before = NULL, updated_at = ?
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
    *,
    task_id: str | None = None,
    claim_token: str | None = None,
    worker_id: str | None = None,
) -> tuple[int, str] | None:
    now = time.time()
    token = uuid.uuid4().hex
    with _database(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_table(connection)
        queue_table = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'v2_tasks'"
        ).fetchone()
        stale_before_text: str | None = None
        if queue_table:
            now_utc = datetime.now(timezone.utc)
            now_text = now_utc.isoformat()
            stale_before_text = (
                now_utc - timedelta(seconds=max(0.01, queue_recovery_timeout_seconds or 900.0))
            ).isoformat()
            terminalize_exhausted_stale_tasks(connection, stale_before=stale_before_text, now_text=now_text)

        if request_kind == "worker" and task_id and claim_token and worker_id:
            if stale_before_text is None:
                timeout = max(0.01, float(queue_recovery_timeout_seconds or 900.0))
                stale_before_text = (datetime.now(timezone.utc) - timedelta(seconds=timeout)).isoformat()
            owned = connection.execute(
                """
                SELECT 1 FROM v2_tasks
                WHERE task_id = ? AND status = 'running' AND locked_by = ?
                  AND claim_token = ? AND locked_at >= ?
                """,
                (task_id, worker_id, claim_token, stale_before_text),
            ).fetchone()
            if not owned:
                connection.rollback()
                return None

        if request_kind == "direct" and queue_table and stale_before_text is not None:
            now_text = datetime.now(timezone.utc).isoformat()
            due_queued = connection.execute(
                """
                SELECT 1 FROM v2_tasks
                WHERE status = 'queued' AND (not_before IS NULL OR not_before <= ?)
                LIMIT 1
                """,
                (now_text,),
            ).fetchone()
            unleased_fresh_claim = connection.execute(
                """
                SELECT 1 FROM v2_tasks AS task
                WHERE task.status = 'running' AND task.locked_at IS NOT NULL
                  AND task.locked_at >= ? AND task.attempts < task.max_attempts
                  AND NOT EXISTS (
                      SELECT 1 FROM resource_leases AS lease
                      WHERE lease.namespace = ? AND lease.owner_task_id = task.task_id
                        AND lease.owner_claim_token = task.claim_token AND lease.lease_until > ?
                  )
                LIMIT 1
                """,
                (stale_before_text, namespace, now),
            ).fetchone()
            if due_queued or unleased_fresh_claim:
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
                INSERT INTO resource_leases(
                    namespace, slot, owner_token, lease_until, heartbeat_at, owner_task_id, owner_claim_token
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(namespace, slot) DO UPDATE SET
                    owner_token = excluded.owner_token,
                    lease_until = excluded.lease_until,
                    heartbeat_at = excluded.heartbeat_at,
                    owner_task_id = excluded.owner_task_id,
                    owner_claim_token = excluded.owner_claim_token
                """,
                (namespace, slot, token, now + lease_ttl_seconds, now, task_id, claim_token),
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


class GenerationLease:
    def __init__(self, path: Path, namespace: str, slot: int, token: str, stop: threading.Event, heartbeat: threading.Thread):
        self.path = path
        self.namespace = namespace
        self.slot = slot
        self.token = token
        self.stop = stop
        self.heartbeat = heartbeat
        self._release_lock = threading.Lock()
        self._released = False

    def _release_sync(self) -> bool:
        with self._release_lock:
            if self._released:
                return True
            self._released = True
        self.stop.set()
        self.heartbeat.join(timeout=1.0)
        with _database(self.path) as connection:
            connection.execute(
                "DELETE FROM resource_leases WHERE namespace = ? AND slot = ? AND owner_token = ?",
                (self.namespace, self.slot, self.token),
            )
        return True

    async def release_async(self) -> bool:
        cleanup = asyncio.create_task(run_sqlite_async(self._release_sync, wait_for_slot=True))
        try:
            return await asyncio.shield(cleanup)
        except asyncio.CancelledError as cancelled:
            try:
                await _wait_task_to_finish(cleanup)
            except BaseException:
                logger.exception("V2 generation lease cleanup failed during caller cancellation")
            raise cancelled
        except Exception:
            logger.exception("V2 generation lease cleanup failed; the lease will expire by TTL")
            return False

    def release_sync(self) -> bool:
        try:
            return self._release_sync()
        except Exception:
            logger.exception("V2 generation lease cleanup failed; the lease will expire by TTL")
            return False


def _start_lease(path: Path, namespace: str, slot: int, token: str, ttl: float) -> GenerationLease:
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        args=(path, namespace, slot, token, ttl, stop),
        name=f"v2-capacity-{namespace}-{slot}",
        daemon=True,
    )
    heartbeat.start()
    return GenerationLease(path, namespace, slot, token, stop, heartbeat)


def _normalized_namespace(namespace: str) -> str:
    return "".join(char for char in str(namespace).lower() if char.isalnum() or char == "-") or "generation"


def _acquire_sync(
    database_path: Path,
    *,
    limit: int,
    namespace: str,
    request_kind: str,
    lease_ttl_seconds: float,
    queue_recovery_timeout_seconds: float | None,
    task_id: str | None,
    claim_token: str | None,
    worker_id: str | None,
) -> GenerationLease:
    safe_limit = max(1, min(int(limit), 32))
    safe_namespace = _normalized_namespace(namespace)
    ttl = max(0.1, float(lease_ttl_seconds))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    reserved = _reserve(
        database_path,
        safe_namespace,
        safe_limit,
        ttl,
        "worker" if request_kind == "worker" else "direct",
        queue_recovery_timeout_seconds,
        task_id=task_id,
        claim_token=claim_token,
        worker_id=worker_id,
    )
    if reserved is None:
        raise GenerationCapacityExceeded("V2 image generation capacity is currently full or queued work has priority.")
    slot, token = reserved
    return _start_lease(database_path, safe_namespace, slot, token, ttl)


@contextmanager
def generation_capacity(
    database_path: Path,
    *,
    limit: int = 1,
    namespace: str = "generation",
    request_kind: str = "direct",
    lease_ttl_seconds: float = 960.0,
    queue_recovery_timeout_seconds: float | None = None,
    task_id: str | None = None,
    claim_token: str | None = None,
    worker_id: str | None = None,
) -> Iterator[GenerationLease]:
    """Acquire a same-host SQLite generation slot, held by a renewing lease."""

    lease = _acquire_sync(
        database_path,
        limit=limit,
        namespace=namespace,
        request_kind=request_kind,
        lease_ttl_seconds=lease_ttl_seconds,
        queue_recovery_timeout_seconds=queue_recovery_timeout_seconds,
        task_id=task_id,
        claim_token=claim_token,
        worker_id=worker_id,
    )
    try:
        yield lease
    finally:
        lease.release_sync()


async def acquire_generation_capacity_async(
    database_path: Path,
    *,
    limit: int = 1,
    namespace: str = "generation",
    request_kind: str = "direct",
    lease_ttl_seconds: float = 960.0,
    queue_recovery_timeout_seconds: float | None = None,
    task_id: str | None = None,
    claim_token: str | None = None,
    worker_id: str | None = None,
) -> GenerationLease:
    safe_limit = max(1, min(int(limit), 32))
    safe_namespace = _normalized_namespace(namespace)
    ttl = max(0.1, float(lease_ttl_seconds))
    database_path.parent.mkdir(parents=True, exist_ok=True)
    reserve_call = lambda: _reserve(
        database_path,
        safe_namespace,
        safe_limit,
        ttl,
        "worker" if request_kind == "worker" else "direct",
        queue_recovery_timeout_seconds,
        task_id=task_id,
        claim_token=claim_token,
        worker_id=worker_id,
    )
    reserved = await run_sqlite_async(
        reserve_call,
        on_cancel_result=lambda result: _release_reserved_lease(database_path, safe_namespace, result),
    )
    if reserved is None:
        raise GenerationCapacityExceeded("V2 image generation capacity is currently full or queued work has priority.")
    slot, token = reserved
    return _start_lease(database_path, safe_namespace, slot, token, ttl)


def _release_reserved_lease(path: Path, namespace: str, reservation: tuple[int, str]) -> bool:
    slot, token = reservation
    with _database(path) as connection:
        connection.execute(
            "DELETE FROM resource_leases WHERE namespace = ? AND slot = ? AND owner_token = ?",
            (namespace, slot, token),
        )
    return True


@asynccontextmanager
async def async_generation_capacity(
    database_path: Path,
    **kwargs: Any,
) -> AsyncIterator[GenerationLease]:
    lease = await acquire_generation_capacity_async(database_path, **kwargs)
    try:
        yield lease
    finally:
        await lease.release_async()


async def run_with_generation_capacity(
    operation: Callable[[], Awaitable[T]],
    *,
    database_path: Path,
    limit: int = 1,
    namespace: str = "generation",
    request_kind: str = "direct",
    lease_ttl_seconds: float = 960.0,
    queue_recovery_timeout_seconds: float | None = None,
    task_id: str | None = None,
    claim_token: str | None = None,
    worker_id: str | None = None,
    before_operation: Callable[[], bool] | None = None,
) -> T:
    """Run provider work under a cross-process slot, releasing off the loop."""

    lease = await acquire_generation_capacity_async(
        database_path,
        limit=limit,
        namespace=namespace,
        request_kind=request_kind,
        lease_ttl_seconds=lease_ttl_seconds,
        queue_recovery_timeout_seconds=queue_recovery_timeout_seconds,
        task_id=task_id,
        claim_token=claim_token,
        worker_id=worker_id,
    )
    try:
        if before_operation is not None:
            current = await run_sqlite_async(before_operation)
            if not current:
                raise GenerationCapacityExceeded("V2 queue task claim was superseded before provider start.")
        return await run_with_existing_generation_capacity(operation)
    finally:
        await lease.release_async()


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


def _ensure_column(connection: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    columns = connection.execute(f"PRAGMA table_info({table})").fetchall()
    if any(str(row[1]) == column for row in columns):
        return
    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")
