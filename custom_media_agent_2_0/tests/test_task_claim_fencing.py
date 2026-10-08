from __future__ import annotations

import sqlite3
import threading
from dataclasses import replace
from datetime import timedelta, timezone, datetime
from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreativeRun
from app.services import task_queue


def _run(run_id: str) -> CreativeRun:
    now = utc_now()
    return CreativeRun(
        run_id=run_id,
        status="generating",
        mode="smart_enhance",
        intent_summary="offline queue claim test",
        trace_id=f"trace_{run_id}",
        created_at=now,
        updated_at=now,
    )


def _configure_queue(tmp_path: Path, monkeypatch, *, name: str = "queue.sqlite3", timeout: float = 5.0, slots: int = 1):
    database_path = tmp_path / name
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(
            settings,
            task_queue_db_path=database_path,
            task_queue_claim_timeout_seconds=timeout,
            task_queue_max_attempts=4,
            task_queue_max_pending=20,
            max_concurrent_image_generations=slots,
        ),
    )
    task_queue.initialize_task_queue()
    return database_path


def _enqueue(run_id: str) -> str:
    run = _run(run_id)
    return task_queue.enqueue_creative_task(
        kind="creative_run",
        request_payload={"user_prompt": "offline fake"},
        queued_run=run,
    )


def _make_stale(claim) -> None:
    stale_locked_at = (utc_now() - timedelta(days=1)).isoformat()
    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, claim.task_id),
        )


@pytest.mark.parametrize("action", ["complete", "fail", "retry", "snapshot", "release"])
def test_superseded_claim_cannot_mutate_new_attempt(tmp_path: Path, monkeypatch, action: str) -> None:
    _configure_queue(tmp_path, monkeypatch, name=f"{action}.sqlite3")
    run_id = f"run_fenced_{action}"
    _enqueue(run_id)
    old_claim = task_queue.claim_next_task("worker-old")
    assert old_claim is not None
    _make_stale(old_claim)
    new_claim = task_queue.claim_next_task("worker-new")
    assert new_claim is not None
    assert new_claim.task_id == old_claim.task_id
    assert new_claim.claim_token != old_claim.claim_token

    run = _run(f"{run_id}_stale-write")
    if action == "complete":
        changed = task_queue.complete_task(old_claim, run)
    elif action == "fail":
        changed = task_queue.fail_task(old_claim, "stale error", run)
    elif action == "retry":
        changed = task_queue.retry_task(old_claim, "stale retry", run, retry_delay_seconds=60)
    elif action == "snapshot":
        changed = task_queue.update_task_snapshot(run, claim=old_claim)
    else:
        changed = task_queue.release_task(old_claim)

    assert changed is False
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, attempts, locked_by, claim_token, result_json, error_json FROM v2_tasks WHERE task_id = ?",
            (old_claim.task_id,),
        ).fetchone()
    assert row["status"] == "running"
    assert row["attempts"] == new_claim.attempts
    assert row["locked_by"] == "worker-new"
    assert row["claim_token"] == new_claim.claim_token
    assert row["result_json"] is None
    assert row["error_json"] is None
    snapshot = task_queue.get_run_snapshot(run_id)
    assert snapshot is not None and snapshot.run_id == run_id


def test_legacy_queue_schema_adds_claim_fencing_columns(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "legacy.sqlite3"
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(settings, task_queue_db_path=database_path),
    )
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
    task_queue.initialize_task_queue()
    with task_queue._connect() as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(v2_tasks)")}
    assert {"claim_token", "claim_generation"} <= columns


def test_claim_heartbeat_refreshes_active_attempt_before_recovery(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch, timeout=3.0)
    _enqueue("run_heartbeat_fresh")
    claim = task_queue.claim_next_task("worker-heartbeat")
    assert claim is not None
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    clock = [start]
    monkeypatch.setattr(task_queue, "utc_now", lambda: clock[0])
    clock[0] = start + timedelta(seconds=20)

    assert task_queue.refresh_task_claim(claim) is True
    clock[0] = start + timedelta(seconds=22)
    assert task_queue.claim_next_task("replacement") is None
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT locked_at, claim_generation FROM v2_tasks WHERE task_id = ?",
            (claim.task_id,),
        ).fetchone()
    assert row["locked_at"] == clock[0].replace(second=20).isoformat()
    assert row["claim_generation"] == 1


def test_claim_heartbeat_covers_preflight_provider_and_terminal_persistence(tmp_path: Path, monkeypatch) -> None:
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch, timeout=3.0)
    _enqueue("run_heartbeat_lifecycle")
    refresh_count = 0
    refresh_condition = threading.Condition()
    original_refresh = task_queue.refresh_task_claim

    def observed_refresh(claim):
        nonlocal refresh_count
        result = original_refresh(claim)
        with refresh_condition:
            refresh_count += 1
            refresh_condition.notify_all()
        return result

    monkeypatch.setattr(task_queue, "refresh_task_claim", observed_refresh)

    def wait_for_refresh(target: int) -> None:
        with refresh_condition:
            assert refresh_condition.wait_for(lambda: refresh_count >= target, timeout=3)

    preflight_started = threading.Event()
    continue_preflight = threading.Event()
    provider_started = threading.Event()
    continue_provider = threading.Event()
    finalize_started = threading.Event()

    async def fake_preflight(_request, _run_id):
        preflight_started.set()
        await asyncio.to_thread(continue_preflight.wait, 3)
        return None

    class Runtime:
        async def complete_queued_run(self, _request, run_id: str):
            provider_started.set()
            await asyncio.to_thread(continue_provider.wait, 3)
            return _run(run_id)

    import asyncio

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", fake_preflight)
    original_complete = task_queue.complete_task

    def observed_complete(claim, run):
        finalize_started.set()
        wait_for_refresh(refresh_count + 1)
        return original_complete(claim, run)

    monkeypatch.setattr(task_queue, "complete_task", observed_complete)
    interval = 0.02
    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(queue_worker.process_next_task_once(Runtime(), "worker-long")),
        daemon=True,
    )
    monkeypatch.setattr(task_queue, "claim_heartbeat_interval_seconds", lambda: interval)
    worker.start()
    assert preflight_started.wait(3)
    wait_for_refresh(1)
    continue_preflight.set()
    assert provider_started.wait(3)
    wait_for_refresh(2)
    continue_provider.set()
    assert finalize_started.wait(3)
    wait_for_refresh(3)
    worker.join(3)
    assert not worker.is_alive()
    assert result == [True]
    with task_queue._connect() as connection:
        terminal = connection.execute(
            "SELECT status, claim_token FROM v2_tasks WHERE run_id = ?",
            ("run_heartbeat_lifecycle",),
        ).fetchone()
    assert terminal["status"] == "completed"
    assert terminal["claim_token"] is None


def test_lost_claim_during_preflight_is_rechecked_before_provider(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch, timeout=1.0)
    _enqueue("run_claim_lost_preflight")
    preflight_started = threading.Event()
    continue_preflight = threading.Event()
    provider_calls = 0

    async def fake_preflight(_request, _run_id):
        preflight_started.set()
        await asyncio.to_thread(continue_preflight.wait, 3)
        return None

    class Runtime:
        async def complete_queued_run(self, _request, _run_id: str):
            nonlocal provider_calls
            provider_calls += 1
            return _run("run_claim_lost_preflight")

    monkeypatch.setattr(queue_worker, "_preflight_veyra_balance", fake_preflight)
    result: list[bool] = []
    worker = threading.Thread(
        target=lambda: result.append(queue_worker.process_next_task_once(Runtime(), "worker-old")),
        daemon=True,
    )
    worker.start()
    assert preflight_started.wait(3)
    with task_queue._connect() as connection:
        claim_row = connection.execute(
            "SELECT task_id FROM v2_tasks WHERE run_id = ?", ("run_claim_lost_preflight",)
        ).fetchone()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            ((utc_now() - timedelta(days=1)).isoformat(), claim_row["task_id"]),
        )
    replacement = task_queue.claim_next_task("worker-replacement")
    assert replacement is not None
    continue_preflight.set()
    worker.join(3)
    assert not worker.is_alive()
    assert result == [True]
    assert provider_calls == 0
    with task_queue._connect() as connection:
        row = connection.execute(
            "SELECT status, locked_by, claim_token FROM v2_tasks WHERE task_id = ?",
            (replacement.task_id,),
        ).fetchone()
    assert row["status"] == "running"
    assert row["locked_by"] == "worker-replacement"
    assert row["claim_token"] == replacement.claim_token


def test_default_worker_instances_have_distinct_ids_and_claim_lock_errors_recover(tmp_path: Path, monkeypatch) -> None:
    import sys
    from app.workers import task_queue_worker
    from app.services import queue_worker

    _configure_queue(tmp_path, monkeypatch)
    runtime = object()
    first = queue_worker.QueueWorker(runtime)
    second = queue_worker.QueueWorker(runtime)
    assert first.worker_id != second.worker_id

    calls = 0
    original_claim = task_queue.claim_next_task

    def busy_once(worker_id: str):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise sqlite3.OperationalError("database is locked")
        return original_claim(worker_id)

    monkeypatch.setattr(task_queue, "claim_next_task", busy_once)
    assert queue_worker.process_next_task_once(runtime, "worker-lock-retry") is False
    assert queue_worker.process_next_task_once(runtime, "worker-lock-retry") is False
    assert calls == 2

    worker_ids: list[str] = []
    monkeypatch.setattr(task_queue_worker, "ensure_runtime_dirs", lambda: None)
    monkeypatch.setattr(task_queue_worker, "bootstrap_v2_repository", lambda **_kwargs: None)
    monkeypatch.setattr(task_queue_worker, "initialize_task_queue", lambda: None)
    monkeypatch.setattr(task_queue_worker, "CreativeManagerRuntime", lambda: runtime)
    monkeypatch.setattr(
        task_queue_worker,
        "process_next_task_once",
        lambda _runtime, worker_id: worker_ids.append(worker_id) or False,
    )
    monkeypatch.setattr(sys, "argv", ["task_queue_worker", "--once"])
    task_queue_worker.main()
    task_queue_worker.main()
    assert len(worker_ids) == 2 and worker_ids[0] != worker_ids[1]
    assert all(worker_id.startswith("v2-standalone-") for worker_id in worker_ids)


def test_worker_slot_ownership_allows_spare_direct_slot_but_waits_for_unleased_claim(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch, slots=2)
    _enqueue("run_spare_slot")
    claim = task_queue.claim_next_task("worker-active")
    assert claim is not None

    with pytest.raises(task_queue.GenerationCapacityExceeded):
        with task_queue.generation_capacity(request_kind="direct"):
            pass

    with task_queue.generation_capacity(request_kind="worker", claim=claim):
        with task_queue.generation_capacity(request_kind="direct"):
            pass


def test_stale_recoverable_running_task_does_not_block_direct_admission_forever(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch, timeout=2.0)
    _enqueue("run_stale_recoverable")
    claim = task_queue.claim_next_task("worker-stopped")
    assert claim is not None
    _make_stale(claim)
    with task_queue.generation_capacity(request_kind="direct"):
        pass


def test_future_retry_and_terminal_rows_do_not_block_direct_but_due_queue_does(tmp_path: Path, monkeypatch) -> None:
    _configure_queue(tmp_path, monkeypatch)
    _enqueue("run_future_retry")
    future_claim = task_queue.claim_next_task("worker-future")
    assert future_claim is not None
    assert task_queue.retry_task(
        future_claim,
        "wait before retry",
        _run(future_claim.run_id),
        retry_delay_seconds=3600,
        consume_attempt=False,
    ) is True
    with task_queue.generation_capacity(request_kind="direct"):
        pass

    _enqueue("run_due_queue")
    with pytest.raises(task_queue.GenerationCapacityExceeded):
        with task_queue.generation_capacity(request_kind="direct"):
            pass

    due_claim = task_queue.claim_next_task("worker-due")
    assert due_claim is not None
    assert task_queue.complete_task(due_claim, _run(due_claim.run_id)) is True
    with task_queue.generation_capacity(request_kind="direct"):
        pass
