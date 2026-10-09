from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import threading
import time
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
from app.services.task_queue import QueueStorageBusy


def _configure_queue(tmp_path: Path, monkeypatch) -> Path:
    database_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(task_queue, "settings", replace(settings, task_queue_db_path=database_path))
    task_queue.initialize_task_queue()
    return database_path


def _hold_write_lock(database_path: Path):
    connection = sqlite3.connect(database_path, timeout=5, isolation_level=None, check_same_thread=False)
    connection.execute("BEGIN IMMEDIATE")
    return connection


@pytest.mark.parametrize("legacy_schema", [False, True], ids=["new-database", "legacy-upgrade"])
def test_v2_queue_initialization_repeats_across_independent_processes(
    tmp_path: Path, legacy_schema: bool
) -> None:
    project_root = Path(__file__).resolve().parents[1]
    child_code = textwrap.dedent(
        """
        import json, sys, time
        from dataclasses import replace
        from pathlib import Path
        sys.dont_write_bytecode = True
        from app.config import settings
        from app.services import generation_capacity, task_queue
        database_path, ready_path, start_path = map(Path, sys.argv[1:4])
        task_queue.settings = replace(settings, task_queue_db_path=database_path, task_queue_busy_timeout_seconds=1.0)
        ready_path.write_text("ready", encoding="utf-8")
        deadline = time.monotonic() + 20
        while not start_path.exists():
            if time.monotonic() >= deadline:
                raise TimeoutError("process start barrier timed out")
            time.sleep(0.002)
        retry_loops = 0
        for _ in range(3):
            retry_loops += int(task_queue.initialize_task_queue() or 0)
            with generation_capacity._database(database_path) as connection:
                mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
                if mode != "wal":
                    raise AssertionError(f"capacity connection observed journal_mode={mode}")
        print(json.dumps({"retry_loops": retry_loops}), flush=True)
        """
    )

    worker_count = 5
    rounds = 2
    failures: list[str] = []
    retry_loops = 0
    initialization_calls = 0

    for round_index in range(rounds):
        database_path = tmp_path / f"queue-{int(legacy_schema)}-{round_index}.sqlite3"
        if legacy_schema:
            with sqlite3.connect(database_path) as connection:
                connection.execute(
                    """
                    CREATE TABLE v2_tasks (
                        task_id TEXT PRIMARY KEY, kind TEXT NOT NULL, run_id TEXT NOT NULL,
                        status TEXT NOT NULL, payload_json TEXT NOT NULL, queued_run_json TEXT NOT NULL,
                        result_json TEXT, error_json TEXT, attempts INTEGER NOT NULL DEFAULT 0,
                        max_attempts INTEGER NOT NULL DEFAULT 3, locked_by TEXT, locked_at TEXT,
                        not_before TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                    )
                    """
                )

        gate = tmp_path / f"start-{int(legacy_schema)}-{round_index}.flag"
        ready_paths = [
            tmp_path / f"ready-{int(legacy_schema)}-{round_index}-{worker}.flag"
            for worker in range(worker_count)
        ]
        environment = os.environ.copy()
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        processes = [
            subprocess.Popen(
                [sys.executable, "-B", "-c", child_code, str(database_path), str(ready), str(gate)],
                cwd=project_root,
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            for ready in ready_paths
        ]
        try:
            ready_deadline = time.monotonic() + 20
            while not all(path.exists() for path in ready_paths) and time.monotonic() < ready_deadline:
                if any(process.poll() is not None for process in processes):
                    break
                time.sleep(0.01)
            if not all(path.exists() for path in ready_paths):
                missing = [path.name for path in ready_paths if not path.exists()]
                statuses = [process.poll() for process in processes]
                raise AssertionError(
                    f"independent queue initializers did not reach the shared start barrier; "
                    f"missing={missing}, exit_statuses={statuses}"
                )
            gate.write_text("go", encoding="utf-8")
            for process in processes:
                try:
                    stdout, stderr = process.communicate(timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    stdout, stderr = process.communicate(timeout=5)
                initialization_calls += 3
                if process.returncode != 0:
                    failures.append(f"exit={process.returncode}; stdout={stdout!r}; stderr={stderr!r}")
                    continue
                try:
                    retry_loops += int(json.loads(stdout.strip().splitlines()[-1])["retry_loops"])
                except (IndexError, KeyError, ValueError, json.JSONDecodeError) as exc:
                    failures.append(f"invalid child output: {stdout!r}; error={exc!r}")
        finally:
            gate.write_text("go", encoding="utf-8")
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)

        with sqlite3.connect(database_path) as connection:
            mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(v2_tasks)")}
        assert mode == "wal"
        assert {"claim_token", "claim_generation", "success_checkpoint_json"} <= columns

    print(
        f"queue_init_stress legacy={legacy_schema} rounds={rounds} processes_per_round={worker_count} "
        f"initialize_calls={initialization_calls} wal_retry_loops={retry_loops} failures={len(failures)}",
        flush=True,
    )
    assert failures == []
    assert initialization_calls == rounds * worker_count * 3


def test_v2_wal_setup_is_bounded_off_loop_and_retries_after_lock_timeout(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "wal-setup-timeout.sqlite3"
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(settings, task_queue_db_path=database_path, task_queue_busy_timeout_seconds=0.2),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE legacy_probe (id INTEGER PRIMARY KEY)")
        assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "delete"

    reader = sqlite3.connect(database_path, timeout=1, isolation_level=None, check_same_thread=False)
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM legacy_probe").fetchall()
    wal_setup_started = threading.Event()
    wal_setup_started_at: list[float] = []
    original_ensure_wal_mode = task_queue._ensure_wal_mode

    def observed_wal_setup(connection: sqlite3.Connection) -> int:
        wal_setup_started_at.append(time.monotonic())
        wal_setup_started.set()
        return original_ensure_wal_mode(connection)

    monkeypatch.setattr(task_queue, "_ensure_wal_mode", observed_wal_setup)

    async def exercise() -> None:
        start = time.monotonic()
        ticks: list[float] = []
        stop_ticker = asyncio.Event()

        async def ticker() -> None:
            while not stop_ticker.is_set():
                ticks.append(time.monotonic())
                await asyncio.sleep(0.01)

        ticker_task = asyncio.create_task(ticker())
        await asyncio.sleep(0)
        initializing = asyncio.create_task(task_queue.initialize_task_queue_async())
        try:
            assert await asyncio.to_thread(wal_setup_started.wait, 2)
            with pytest.raises(QueueStorageBusy) as busy:
                await asyncio.wait_for(initializing, timeout=1)
            finished = time.monotonic()
        finally:
            stop_ticker.set()
            await ticker_task
        assert "busy" in str(busy.value).lower()
        elapsed = finished - start
        assert 0.1 <= elapsed < 0.8
        setup_started = wal_setup_started_at[0]
        ticks_during_lock_wait = [tick for tick in ticks if setup_started <= tick <= finished]
        assert len(ticks_during_lock_wait) >= 5
        assert ticks_during_lock_wait[-1] >= setup_started + 0.05

    try:
        asyncio.run(exercise())
    finally:
        reader.rollback()
        reader.close()

    asyncio.run(task_queue.initialize_task_queue_async())
    with task_queue._connect() as connection:
        assert str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower() == "wal"
        columns = {str(row[1]) for row in connection.execute("PRAGMA table_info(v2_tasks)")}
    assert "claim_token" in columns


def test_v2_queue_connection_does_not_switch_journal_mode_under_reader_lock(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "queue-connect-reader.sqlite3"
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(settings, task_queue_db_path=database_path, task_queue_busy_timeout_seconds=0.1),
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY)")
    reader = sqlite3.connect(database_path, timeout=1, isolation_level=None, check_same_thread=False)
    reader.execute("BEGIN")
    reader.execute("SELECT * FROM probe").fetchall()
    try:
        with task_queue._connect() as connection:
            mode = str(connection.execute("PRAGMA journal_mode").fetchone()[0]).lower()
        assert mode == "delete"
    finally:
        reader.rollback()
        reader.close()


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
