from __future__ import annotations

import asyncio
import sqlite3
import threading
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import settings
from app.schemas import CreateCreativeRunRequest
from app.services import generation_capacity as capacity
from app.services import task_queue
from app.services.generation_capacity import (
    GenerationCapacityStorageBusy,
    run_with_generation_capacity,
)


def _configure_queue(tmp_path: Path, monkeypatch) -> Path:
    database_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=database_path))
    task_queue.initialize_task_queue()
    return database_path


def _hold_write_lock(database_path: Path):
    connection = sqlite3.connect(database_path, timeout=5, isolation_level=None, check_same_thread=False)
    connection.execute("BEGIN IMMEDIATE")
    return connection


def test_v2_async_admission_keeps_loop_responsive_during_sqlite_write_lock(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "capacity.sqlite3"
    with capacity.generation_capacity(database_path):
        pass
    lock_connection = _hold_write_lock(database_path)
    reserve_started = threading.Event()
    original_reserve = capacity._reserve

    def observed_reserve(*args, **kwargs):
        reserve_started.set()
        return original_reserve(*args, **kwargs)

    monkeypatch.setattr(capacity, "_reserve", observed_reserve)
    calls = 0

    async def provider() -> str:
        nonlocal calls
        calls += 1
        return "fake-complete"

    async def exercise() -> None:
        admission = asyncio.create_task(
            run_with_generation_capacity(
                provider,
                database_path=database_path,
                limit=1,
                lease_ttl_seconds=10,
            )
        )
        assert await asyncio.to_thread(reserve_started.wait, 2)
        loop_ticked = asyncio.Event()
        asyncio.get_running_loop().call_soon(loop_ticked.set)
        await asyncio.wait_for(loop_ticked.wait(), timeout=1)
        lock_connection.rollback()
        assert await admission == "fake-complete"

    try:
        asyncio.run(exercise())
    finally:
        lock_connection.close()
    assert calls == 1


def test_v2_async_enqueue_keeps_loop_responsive_during_sqlite_write_lock(tmp_path: Path, monkeypatch) -> None:
    from app.repositories.memory import utc_now
    from app.schemas import CreativeRun

    database_path = _configure_queue(tmp_path, monkeypatch)
    lock_connection = _hold_write_lock(database_path)
    connection_started = threading.Event()
    original_connect = task_queue._connect

    def observed_connect():
        connection_started.set()
        return original_connect()

    monkeypatch.setattr(task_queue, "_connect", observed_connect)
    run = CreativeRun(
        run_id="run_async_enqueue_lock",
        status="generating",
        mode="smart_enhance",
        intent_summary="offline fake",
        trace_id="trace_async_enqueue_lock",
        created_at=utc_now(),
        updated_at=utc_now(),
    )

    async def exercise() -> None:
        enqueue = asyncio.create_task(
            task_queue.enqueue_creative_task_async(
                kind="creative_run", request_payload={"user_prompt": "offline"}, queued_run=run
            )
        )
        assert await asyncio.to_thread(connection_started.wait, 2)
        loop_ticked = asyncio.Event()
        asyncio.get_running_loop().call_soon(loop_ticked.set)
        await asyncio.wait_for(loop_ticked.wait(), timeout=1)
        lock_connection.rollback()
        task_id = await enqueue
        assert task_id

    try:
        asyncio.run(exercise())
    finally:
        lock_connection.close()
    assert task_queue.task_queue_stats()["counts"] == {"queued": 1}


def test_v2_cancellation_during_acquire_releases_late_lease(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cancel-acquire.sqlite3"
    acquire_started = threading.Event()
    continue_acquire = threading.Event()
    original_reserve = capacity._reserve

    def held_reserve(*args, **kwargs):
        acquire_started.set()
        assert continue_acquire.wait(3)
        return original_reserve(*args, **kwargs)

    monkeypatch.setattr(capacity, "_reserve", held_reserve)
    provider_calls = 0

    async def provider() -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "unexpected"

    async def exercise() -> None:
        task = asyncio.create_task(
            run_with_generation_capacity(provider, database_path=database_path, limit=1, lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(acquire_started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        continue_acquire.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert provider_calls == 0
    with capacity._database(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM resource_leases").fetchone()[0] == 0


def test_v2_cancellation_during_cleanup_waits_for_release_and_keeps_result_private(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cancel-cleanup.sqlite3"
    cleanup_started = threading.Event()
    continue_cleanup = threading.Event()
    original_release = capacity.GenerationLease._release_sync
    provider_calls = 0

    def held_release(lease):
        cleanup_started.set()
        assert continue_cleanup.wait(3)
        return original_release(lease)

    monkeypatch.setattr(capacity.GenerationLease, "_release_sync", held_release)

    async def provider() -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "created-once"

    async def exercise() -> None:
        task = asyncio.create_task(
            run_with_generation_capacity(provider, database_path=database_path, limit=1, lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(cleanup_started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        continue_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert provider_calls == 1
    with capacity._database(database_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM resource_leases").fetchone()[0] == 0


def test_v2_successful_provider_is_not_retried_when_lease_cleanup_fails(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "cleanup-error.sqlite3"
    provider_calls = 0

    def failed_cleanup(_lease):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(capacity.GenerationLease, "_release_sync", failed_cleanup)

    async def provider() -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "created-once"

    result = asyncio.run(
        run_with_generation_capacity(provider, database_path=database_path, limit=1, lease_ttl_seconds=10)
    )
    assert result == "created-once"
    assert provider_calls == 1


def test_v2_cleanup_waits_for_bounded_database_permit_without_blocking_loop(tmp_path: Path, monkeypatch) -> None:
    class Gate:
        def __init__(self):
            self.semaphore = threading.BoundedSemaphore(1)
            self.blocked = False
            self.waiting = threading.Event()

        def acquire(self, blocking=False):
            if self.blocked:
                self.waiting.set()
                return False
            return self.semaphore.acquire(blocking=blocking)

        def release(self):
            self.semaphore.release()

    gate = Gate()
    monkeypatch.setattr(capacity, "_ASYNC_DB_SLOTS", gate)

    async def provider() -> str:
        gate.blocked = True
        return "created-once"

    async def exercise() -> str:
        task = asyncio.create_task(
            run_with_generation_capacity(provider, database_path=tmp_path / "cleanup-permit.sqlite3", lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(gate.waiting.wait, 2)
        gate.blocked = False
        return await task

    assert asyncio.run(exercise()) == "created-once"


def test_v2_async_sqlite_offload_is_bounded_and_permit_survives_cancellation(monkeypatch) -> None:
    monkeypatch.setattr(capacity, "_ASYNC_DB_SLOTS", threading.BoundedSemaphore(1))
    worker_started = threading.Event()
    finish_worker = threading.Event()

    def blocking_operation() -> str:
        worker_started.set()
        assert finish_worker.wait(3)
        return "done"

    async def exercise() -> None:
        first = asyncio.create_task(capacity.run_sqlite_async(blocking_operation))
        assert await asyncio.to_thread(worker_started.wait, 2)
        with pytest.raises(GenerationCapacityStorageBusy):
            await capacity.run_sqlite_async(lambda: "should-not-run")
        first.cancel()
        await asyncio.sleep(0)
        with pytest.raises(GenerationCapacityStorageBusy):
            await capacity.run_sqlite_async(lambda: "permit-was-released-too-early")
        finish_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await capacity.run_sqlite_async(lambda: "available") == "available"

    asyncio.run(exercise())


def test_v2_queue_storage_saturation_maps_to_retryable_http_503(monkeypatch) -> None:
    import app.main as main_module
    from app.repositories.memory import utc_now
    from app.schemas import CreativeRun

    now = utc_now()
    queued_run = CreativeRun(
        run_id="run_storage_busy_route",
        status="generating",
        mode="smart_enhance",
        intent_summary="offline fake",
        trace_id="trace_storage_busy_route",
        created_at=now,
        updated_at=now,
    )
    monkeypatch.setattr(main_module.creative_manager, "queue_run", lambda _request: queued_run)
    monkeypatch.setattr(main_module.repository, "delete_creative_run", lambda _run_id: None)
    slots = threading.BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(capacity, "_ASYNC_DB_SLOTS", slots)
    request = Request({"type": "http", "method": "POST", "path": "/api/v2/creative/runs/async", "headers": []})

    async def exercise() -> None:
        with pytest.raises(HTTPException) as error:
            await main_module.create_creative_run_async(
                CreateCreativeRunRequest(user_prompt="offline fake"), request, ""
            )
        assert error.value.status_code == 503
        assert error.value.headers["Retry-After"] == "5"
        assert error.value.detail["error_code"] == "local_database_busy"
        assert error.value.detail["retryable"] is True

    try:
        asyncio.run(exercise())
    finally:
        slots.release()
