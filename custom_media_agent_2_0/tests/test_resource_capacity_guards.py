from __future__ import annotations

import json
import sqlite3
import multiprocessing
import asyncio
import os
import threading
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreativeRun
from app.services.generation_capacity import GenerationCapacityExceeded, generation_capacity
from app.services import task_queue as task_queue_service
from app.services import generation_capacity as capacity_module
from app.services.generation_capacity import run_with_generation_capacity
from app.services.task_queue import QueueCapacityExceeded, claim_next_task, enqueue_creative_task, task_queue_stats


def _hold_generation_slot(data_dir: str, acquired, release) -> None:
    with generation_capacity(Path(data_dir) / "queue.sqlite3", limit=1, lease_ttl_seconds=0.5):
        acquired.set()
        release.wait(10)



def _crash_with_generation_slot(data_dir: str, acquired) -> None:
    with generation_capacity(Path(data_dir) / "queue.sqlite3", limit=1, lease_ttl_seconds=0.5):
        acquired.set()
        os._exit(0)



def test_v2_generation_capacity_is_cross_process_and_released_on_exit(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    release = context.Event()
    process = context.Process(target=_hold_generation_slot, args=(str(tmp_path), acquired, release))
    process.start()
    try:
        assert acquired.wait(10)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path / "queue.sqlite3", limit=1, lease_ttl_seconds=0.5):
                pass
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0
    with generation_capacity(tmp_path / "queue.sqlite3", limit=1):
        pass



def _queued_run(run_id: str) -> CreativeRun:
    now = utc_now()
    return CreativeRun(
        run_id=run_id,
        status="generating",
        mode="smart_enhance",
        intent_summary="capacity test",
        trace_id=f"trace_{run_id}",
        created_at=now,
        updated_at=now,
    )



def test_v2_pending_queue_limit_is_enforced_transactionally(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.task_queue.settings",
        replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3", task_queue_max_pending=1),
    )
    first = _queued_run("run_capacity_1")
    second = _queued_run("run_capacity_2")
    enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "first"}, queued_run=first)
    with pytest.raises(GenerationCapacityExceeded):
        with generation_capacity(tmp_path / "queue.sqlite3", request_kind="direct"):
            pass
    with generation_capacity(tmp_path / "queue.sqlite3", request_kind="worker"):
        pass
    with pytest.raises(QueueCapacityExceeded):
        enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "second"}, queued_run=second)
    assert task_queue_stats()["counts"] == {"queued": 1}



def test_v2_stale_running_task_recovers_same_durable_identity(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(
        "app.services.task_queue.settings",
        replace(settings, task_queue_db_path=database_path, task_queue_max_attempts=3, task_queue_claim_timeout_seconds=0.01),
    )
    run = _queued_run("run_recovery_same_task")
    enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline recovery"}, queued_run=run)
    first = claim_next_task("crashed-worker")
    assert first is not None
    assert first.attempts == 1
    with task_queue_service._connect() as connection:
        stale_locked_at = (utc_now() - timedelta(seconds=1)).isoformat()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, first.task_id),
        )
    recovered = claim_next_task("replacement-worker")
    assert recovered is not None
    assert recovered.task_id == first.task_id
    assert recovered.run_id == first.run_id
    assert recovered.attempts == 2



def test_v2_exhausted_stale_task_is_terminalized_and_releases_direct_priority(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(
        "app.services.task_queue.settings",
        replace(
            settings,
            task_queue_db_path=database_path,
            task_queue_max_attempts=1,
            task_queue_claim_timeout_seconds=0.01,
            max_concurrent_image_generations=1,
        ),
    )
    run = _queued_run("run_recovery_exhausted")
    enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline recovery"}, queued_run=run)
    claimed = claim_next_task("last-attempt-worker")
    assert claimed is not None
    assert claimed.attempts == claimed.max_attempts == 1
    with task_queue_service._connect() as connection:
        stale_locked_at = (utc_now() - timedelta(seconds=1)).isoformat()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, claimed.task_id),
        )

    # A dead worker on its final attempt must not hold queue priority forever.
    with task_queue_service.generation_capacity(request_kind="direct"):
        pass

    with task_queue_service._connect() as connection:
        row = connection.execute(
            "SELECT status, error_json, locked_by, locked_at FROM v2_tasks WHERE task_id = ?",
            (claimed.task_id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "failed"
    assert row["locked_by"] is None and row["locked_at"] is None
    error = json.loads(row["error_json"])
    assert error["error_code"] == "worker_recovery_exhausted"
    assert error["retryable"] is False
    snapshot = task_queue_service.get_run_snapshot(run.run_id)
    assert snapshot is not None and snapshot.status == "failed"
    assert "final allowed attempt" in snapshot.next_actions[0]



def test_v2_capacity_release_after_exception(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        with generation_capacity(tmp_path / "queue.sqlite3", limit=1):
            raise RuntimeError("simulated provider failure")
    with generation_capacity(tmp_path / "queue.sqlite3", limit=1):
        pass



def test_v2_heartbeat_keeps_long_running_slot_active(tmp_path: Path) -> None:
    with generation_capacity(tmp_path / "queue.sqlite3", limit=1, lease_ttl_seconds=0.2):
        time.sleep(0.35)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path / "queue.sqlite3", limit=1, lease_ttl_seconds=0.2):
                pass



def test_v2_crash_lease_waits_for_timeout_before_reuse(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    process = context.Process(target=_crash_with_generation_slot, args=(str(tmp_path), acquired))
    process.start()
    assert acquired.wait(10)
    process.join(10)
    assert process.exitcode == 0
    with pytest.raises(GenerationCapacityExceeded):
        with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.5):
            pass
    time.sleep(0.55)
    with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.5):
        pass



def test_v2_heartbeat_retries_transient_database_error_without_releasing_slot(tmp_path: Path, monkeypatch) -> None:
    original_connect = capacity_module._connect
    calls = 0

    def fail_one_heartbeat(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("temporary heartbeat failure")
        return original_connect(path)

    monkeypatch.setattr(capacity_module, "_connect", fail_one_heartbeat)
    with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.6):
        time.sleep(0.4)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.6):
                pass



def test_v2_cancellation_keeps_slot_until_provider_thread_finishes(tmp_path: Path) -> None:
    started = threading.Event()
    finish_provider = threading.Event()
    database_path = tmp_path / "queue.sqlite3"

    def fake_blocking_provider() -> str:
        started.set()
        finish_provider.wait(10)
        return "done"

    async def provider_operation() -> str:
        return await asyncio.to_thread(fake_blocking_provider)

    async def exercise() -> None:
        task = asyncio.create_task(
            run_with_generation_capacity(
                provider_operation,
                database_path=database_path,
                lease_ttl_seconds=1,
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(database_path, lease_ttl_seconds=1):
                pass
        finish_provider.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        with generation_capacity(database_path, lease_ttl_seconds=1):
            pass

    asyncio.run(exercise())



def test_v2_provider_timeout_does_not_prove_remote_work_stopped(tmp_path: Path) -> None:
    remote_still_running = threading.Event()
    finish_remote = threading.Event()
    database_path = tmp_path / "queue.sqlite3"

    def fake_remote_operation() -> None:
        remote_still_running.set()
        finish_remote.wait(10)

    async def provider_client_timeout() -> None:
        asyncio.create_task(asyncio.to_thread(fake_remote_operation))
        while not remote_still_running.is_set():
            await asyncio.sleep(0.01)
        raise TimeoutError("client deadline elapsed")

    async def exercise() -> None:
        with pytest.raises(TimeoutError):
            await run_with_generation_capacity(
                provider_client_timeout,
                database_path=database_path,
                lease_ttl_seconds=1,
            )
        assert remote_still_running.is_set()
        with generation_capacity(database_path, lease_ttl_seconds=1):
            pass
        finish_remote.set()

    asyncio.run(exercise())

