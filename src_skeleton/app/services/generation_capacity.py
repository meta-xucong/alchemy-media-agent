from __future__ import annotations

import asyncio
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Iterator, TypeVar

from app.config import settings


logger = logging.getLogger(__name__)


class GenerationCapacityExceeded(RuntimeError):
    """Raised when all cross-process V1 generation leases are occupied."""


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
    """Run local SQLite work on a bounded thread, retaining its permit after cancellation."""

    while not _ASYNC_DB_SLOTS.acquire(blocking=False):
        if not wait_for_slot:
            raise GenerationCapacityStorageBusy("V1 local database work is busy; please retry shortly.")
        await asyncio.sleep(0.01)

    def invoke() -> T:
        try:
            return operation()
        except sqlite3.OperationalError as exc:
            if _is_sqlite_busy(exc):
                raise GenerationCapacityStorageBusy("V1 local database work is busy; please retry shortly.") from exc
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
                logger.exception("V1 late SQLite reservation cleanup failed after caller cancellation")
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
            PRIMARY KEY(namespace, slot)
        )
        """
    )


def _reserve(path: Path, namespace: str, limit: int, lease_ttl_seconds: float) -> tuple[int, str] | None:
    now = time.time()
    token = uuid.uuid4().hex
    with _database(path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _ensure_table(connection)
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
            # A transient local DB contention must not discard a live lease.
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
                logger.exception("V1 generation lease cleanup failed during caller cancellation")
            raise cancelled
        except Exception:
            logger.exception("V1 generation lease cleanup failed; the lease will expire by TTL")
            return False

    def release_sync(self) -> bool:
        try:
            return self._release_sync()
        except Exception:
            logger.exception("V1 generation lease cleanup failed; the lease will expire by TTL")
            return False


def _normalized_namespace(namespace: str) -> str:
    return "".join(char for char in str(namespace).lower() if char.isalnum() or char == "-") or "generation"


def _start_lease(path: Path, namespace: str, slot: int, token: str, ttl: float) -> GenerationLease:
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        args=(path, namespace, slot, token, ttl, stop),
        name=f"v1-capacity-{namespace}-{slot}",
        daemon=True,
    )
    heartbeat.start()
    return GenerationLease(path, namespace, slot, token, stop, heartbeat)


def _reserve_lease(root: Path, *, limit: int, namespace: str, lease_ttl_seconds: float) -> GenerationLease:
    safe_limit = max(1, min(int(limit), 32))
    safe_namespace = _normalized_namespace(namespace)
    ttl = max(0.1, float(lease_ttl_seconds))
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".v1-resource-admission.sqlite3"
    reserved = _reserve(path, safe_namespace, safe_limit, ttl)
    if reserved is None:
        raise GenerationCapacityExceeded("V1 image generation capacity is currently full.")
    slot, token = reserved
    return _start_lease(path, safe_namespace, slot, token, ttl)


@contextmanager
def generation_capacity(
    root: Path,
    *,
    limit: int = 1,
    namespace: str = "generation",
    lease_ttl_seconds: float = 960.0,
) -> Iterator[GenerationLease]:
    """Acquire a heartbeat-renewed local SQLite lease across processes."""

    lease = _reserve_lease(root, limit=limit, namespace=namespace, lease_ttl_seconds=lease_ttl_seconds)
    try:
        yield lease
    finally:
        lease.release_sync()


async def acquire_generation_capacity_async(
    root: Path,
    *,
    limit: int = 1,
    namespace: str = "generation",
    lease_ttl_seconds: float = 960.0,
) -> GenerationLease:
    safe_limit = max(1, min(int(limit), 32))
    safe_namespace = _normalized_namespace(namespace)
    ttl = max(0.1, float(lease_ttl_seconds))
    path = root / ".v1-resource-admission.sqlite3"
    root.mkdir(parents=True, exist_ok=True)
    reserved = await run_sqlite_async(
        lambda: _reserve(path, safe_namespace, safe_limit, ttl),
        on_cancel_result=lambda result: _release_reserved_lease(path, safe_namespace, result),
    )
    if reserved is None:
        raise GenerationCapacityExceeded("V1 image generation capacity is currently full.")
    slot, token = reserved
    return _start_lease(path, safe_namespace, slot, token, ttl)


def _release_reserved_lease(path: Path, namespace: str, reservation: tuple[int, str]) -> bool:
    slot, token = reservation
    with _database(path) as connection:
        connection.execute(
            "DELETE FROM resource_leases WHERE namespace = ? AND slot = ? AND owner_token = ?",
            (namespace, slot, token),
        )
    return True


@asynccontextmanager
async def async_generation_capacity(root: Path, **kwargs: Any) -> AsyncIterator[GenerationLease]:
    lease = await acquire_generation_capacity_async(root, **kwargs)
    try:
        yield lease
    finally:
        await lease.release_async()


async def run_with_generation_capacity(
    operation: Callable[[], Awaitable[T]],
    *,
    root: Path,
    limit: int = 1,
    namespace: str = "generation",
    lease_ttl_seconds: float = 960.0,
    wait_for_capacity: bool = False,
    capacity_wait_seconds: float = 900.0,
) -> T:
    """Run an async provider flow while retaining its local lease through cancellation."""

    deadline = time.monotonic() + max(0.0, float(capacity_wait_seconds))
    while True:
        try:
            lease = await acquire_generation_capacity_async(
                root,
                limit=limit,
                namespace=namespace,
                lease_ttl_seconds=lease_ttl_seconds,
            )
            try:
                return await run_with_existing_generation_capacity(operation)
            finally:
                await lease.release_async()
        except GenerationCapacityExceeded:
            if not wait_for_capacity or time.monotonic() >= deadline:
                raise
            await asyncio.sleep(min(0.25, max(0.0, deadline - time.monotonic())))


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
