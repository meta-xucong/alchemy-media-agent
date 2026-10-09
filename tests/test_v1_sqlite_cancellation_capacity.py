from __future__ import annotations

import asyncio
from concurrent.futures import Future
import sqlite3
import threading

from fastapi import HTTPException

from app.main import _run_sqlite_api_call
from app.services.alchemy_lab import (
    ExplorationSession,
    GenerationVariant,
    _run_lab_sqlite_call,
    _save_runner_state,
    lab_store,
)
from app.repositories.sqlite_calls import BoundedSQLiteCalls, SQLiteStorageBusy


class _DeferredExecutor:
    """Hold submitted work until the test explicitly dequeues it."""

    def __init__(self):
        self.pending = []

    def submit(self, function):
        future = Future()
        self.pending.append((future, function))
        return future

    def run_next(self):
        future, function = self.pending.pop(0)
        if future.set_running_or_notify_cancel():
            try:
                future.set_result(function())
            except BaseException as exc:
                future.set_exception(exc)


def test_v1_cancelled_awaiters_keep_capacity_until_sqlite_workers_finish():
    gate = threading.Event()
    both_started = threading.Event()
    started = 0
    active = 0
    maximum_active = 0
    guard = threading.Lock()

    def blocked_operation():
        nonlocal started, active, maximum_active
        with guard:
            started += 1
            active += 1
            maximum_active = max(maximum_active, active)
            if started == 2:
                both_started.set()
        gate.wait(timeout=3)
        with guard:
            active -= 1
        return "done"

    async def exercise():
        tasks = [asyncio.create_task(_run_sqlite_api_call(blocked_operation)) for _ in range(2)]
        started_ok = await asyncio.to_thread(both_started.wait, 2)
        assert started_ok
        for task in tasks:
            task.cancel()
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

        try:
            await _run_sqlite_api_call(lambda: "unexpected")
        except HTTPException as exc:
            rejected = exc
        else:
            rejected = None

        gate.set()
        for _ in range(100):
            try:
                result = await _run_sqlite_api_call(lambda: "available")
                break
            except HTTPException as exc:
                if exc.status_code != 503:
                    raise
                await asyncio.sleep(0.01)
        else:
            result = None
        return rejected, result

    rejected, result = asyncio.run(exercise())
    assert isinstance(rejected, HTTPException)
    assert rejected.status_code == 503
    assert rejected.headers.get("Retry-After") == "1"
    assert result == "available"
    assert maximum_active == 2
    assert active == 0


def test_v1_cancelled_queued_awaiters_do_not_grow_physical_executor_queue():
    calls = BoundedSQLiteCalls(capacity=2)
    executor = _DeferredExecutor()
    calls._executor = executor

    async def exercise():
        queued = [asyncio.create_task(calls.run(lambda: "done")) for _ in range(2)]
        await asyncio.sleep(0)
        assert len(executor.pending) == 2
        for task in queued:
            task.cancel()
        await asyncio.gather(*queued, return_exceptions=True)

        rejected = 0
        for _ in range(1000):
            try:
                await calls.run(lambda: "must-not-submit")
            except SQLiteStorageBusy:
                rejected += 1
        assert rejected == 1000
        assert len(executor.pending) == 2
        assert all(not future.cancelled() for future, _ in executor.pending)

        executor.run_next()
        executor.run_next()
        replacement = asyncio.create_task(calls.run(lambda: "available"))
        await asyncio.sleep(0)
        assert len(executor.pending) == 1
        executor.run_next()
        return await replacement

    assert asyncio.run(exercise()) == "available"


def test_lab_sqlite_calls_share_cancellation_safe_capacity():
    gate = threading.Event()
    both_started = threading.Event()
    started = 0
    guard = threading.Lock()

    def blocked_operation():
        nonlocal started
        with guard:
            started += 1
            if started == 2:
                both_started.set()
        gate.wait(timeout=3)

    async def exercise():
        tasks = [asyncio.create_task(_run_lab_sqlite_call(blocked_operation)) for _ in range(2)]
        started_ok = await asyncio.to_thread(both_started.wait, 2)
        assert started_ok
        for task in tasks:
            task.cancel()
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await _run_lab_sqlite_call(lambda: "unexpected")
        except Exception as exc:
            rejected = exc
        else:
            rejected = None
        gate.set()
        return rejected

    rejected = asyncio.run(exercise())
    assert rejected is not None
    assert "capacity is busy" in str(rejected)


def test_lab_success_checkpoint_waits_for_sqlite_capacity_without_losing_snapshot(monkeypatch):
    gate = threading.Event()
    both_started = threading.Event()
    started = 0
    guard = threading.Lock()
    simulated_provider_calls = 0
    output_snapshot = {"job_id": "job_lab_success", "output_id": "out_lab_success"}
    saved = []

    def blocked_operation():
        nonlocal started
        with guard:
            started += 1
            if started == 2:
                both_started.set()
        gate.wait(timeout=5)

    def save_runner_state(session):
        saved.append(session.model_copy(deep=True))
        return session

    monkeypatch.setattr(lab_store, "save_runner_state", save_runner_state)
    session = ExplorationSession.model_construct(
        id="lab_session_success",
        status="partial_success",
        variants=[
            GenerationVariant(
                id="variant_success",
                session_id="lab_session_success",
                prompt_id="prompt_1",
                style_preset_id="style_1",
                index_within_style=0,
                status="succeeded",
                created_at="2026-10-09T00:00:00Z",
                completed_at="2026-10-09T00:00:01Z",
                asset=output_snapshot,
            )
        ],
    )

    async def exercise():
        blockers = [asyncio.create_task(_run_lab_sqlite_call(blocked_operation)) for _ in range(2)]
        assert await asyncio.to_thread(both_started.wait, 2)

        async def persist_successful_generation():
            nonlocal simulated_provider_calls
            simulated_provider_calls += 1  # Model a provider result that already exists.
            session.variants[0].asset = output_snapshot
            return await _save_runner_state(session)

        checkpoint = asyncio.create_task(persist_successful_generation())
        await asyncio.sleep(1.15)
        still_owned_after_old_deadline = not checkpoint.done()
        gate.set()
        await asyncio.gather(*blockers)
        result = await asyncio.wait_for(checkpoint, timeout=2)
        return still_owned_after_old_deadline, result

    still_owned, result = asyncio.run(exercise())
    assert still_owned
    assert result is session
    assert len(saved) == 1
    assert saved[0].variants[0].status == "succeeded"
    assert saved[0].variants[0].asset == output_snapshot
    assert simulated_provider_calls == 1


def test_v1_sqlite_busy_error_releases_executor_capacity():
    async def exercise():
        try:
            await _run_sqlite_api_call(lambda: (_ for _ in ()).throw(sqlite3.OperationalError("database is locked")))
        except HTTPException as exc:
            busy = exc
        else:
            busy = None
        available = await _run_sqlite_api_call(lambda: "available")
        return busy, available

    busy, available = asyncio.run(exercise())
    assert isinstance(busy, HTTPException)
    assert busy.status_code == 503
    assert available == "available"
