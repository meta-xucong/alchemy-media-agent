from __future__ import annotations

import sqlite3
import threading
import time
import uuid
import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Awaitable, Callable, Iterator, TypeVar


class GenerationCapacityExceeded(RuntimeError):
    """Raised when all cross-process V1 generation leases are occupied."""


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


@contextmanager
def generation_capacity(
    root: Path,
    *,
    limit: int = 1,
    namespace: str = "generation",
    lease_ttl_seconds: float = 960.0,
) -> Iterator[None]:
    """Acquire a heartbeat-renewed local SQLite lease across processes.

    A crashed process leaves a lease in place until its TTL expires. Normal
    completion releases it; async callers use run_with_generation_capacity to
    keep it through cancellation. This coordinates only processes sharing this
    local filesystem and cannot report whether remote provider work terminated.
    """

    safe_limit = max(1, min(int(limit), 32))
    safe_namespace = "".join(char for char in str(namespace).lower() if char.isalnum() or char == "-") or "generation"
    ttl = max(0.1, float(lease_ttl_seconds))
    root.mkdir(parents=True, exist_ok=True)
    path = root / ".v1-resource-admission.sqlite3"
    reserved = _reserve(path, safe_namespace, safe_limit, ttl)
    if reserved is None:
        raise GenerationCapacityExceeded("V1 image generation capacity is currently full.")

    slot, token = reserved
    stop = threading.Event()
    heartbeat = threading.Thread(
        target=_heartbeat,
        args=(path, safe_namespace, slot, token, ttl, stop),
        name=f"v1-capacity-{safe_namespace}-{slot}",
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
    root: Path,
    limit: int = 1,
    namespace: str = "generation",
    lease_ttl_seconds: float = 960.0,
    wait_for_capacity: bool = False,
    capacity_wait_seconds: float = 900.0,
) -> T:
    """Run an async provider flow while retaining its local lease through cancellation.

    Shielding keeps the provider coroutine alive if its caller is cancelled; the
    caller still receives cancellation after the provider coroutine actually
    returns, so the lease cannot be released while that local work is running.
    """

    deadline = time.monotonic() + max(0.0, float(capacity_wait_seconds))
    while True:
        try:
            with generation_capacity(
                root,
                limit=limit,
                namespace=namespace,
                lease_ttl_seconds=lease_ttl_seconds,
            ):
                return await run_with_existing_generation_capacity(operation)
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
