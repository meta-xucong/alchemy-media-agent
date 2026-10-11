"""Identical offline scheduling contracts for independently owned V1/V2 pools."""
from __future__ import annotations

import asyncio
from concurrent.futures import Future, ThreadPoolExecutor
import importlib.util
from pathlib import Path
import sqlite3
import sys
import threading
from types import SimpleNamespace

import pytest


@pytest.fixture(params=["src_skeleton", "custom_media_agent_2_0"], ids=["v1", "v2"])
def module(request):
    path = Path(__file__).resolve().parents[1] / request.param / "app/repositories/sqlite_calls.py"
    name = f"read_admission_{request.param}"
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    sys.modules[name] = loaded
    spec.loader.exec_module(loaded)
    # Admission time is controlled independently of scheduler/CI load.
    loaded._test_clock = [0.0]
    loaded.time = SimpleNamespace(monotonic=lambda: loaded._test_clock[0])
    yield loaded
    loaded.sqlite_calls.shutdown()
    sys.modules.pop(name, None)


class DeferredExecutor:
    """Physical submission and actual dequeue are controlled independently."""
    def __init__(self):
        self.pending = []

    def submit(self, function):
        future = Future()
        self.pending.append((future, function))
        return future

    def finish_one(self):
        future, function = self.pending.pop(0)
        assert future.set_running_or_notify_cancel(), "Caller cancelled physical work"
        try:
            future.set_result(function())
        except BaseException as exc:
            future.set_exception(exc)

    def shutdown(self, *, wait=True, cancel_futures=False):
        assert not cancel_futures
        if wait:
            while self.pending:
                self.finish_one()


async def until(predicate):
    async def poll():
        while not predicate():
            await asyncio.sleep(0)
    await asyncio.wait_for(poll(), 5)


def deferred(module, **kwargs):
    calls = module.BoundedSQLiteCalls(**kwargs)
    calls._executor.shutdown()
    executor = DeferredExecutor()
    calls._executor = executor
    return calls, executor


def test_read_burst_is_fifo_and_does_not_expand_physical_queue(module):
    calls, executor = deferred(module)
    executed = []

    async def exercise():
        active = [asyncio.create_task(calls.run(lambda: "write")) for _ in range(2)]
        await until(lambda: len(executor.pending) == 2)
        waiting = []
        for index in range(6):
            waiting.append(asyncio.create_task(calls.run_read(lambda index=index: executed.append(index))))
            await until(lambda: calls.snapshot()["pending"] == index + 1)
        with pytest.raises(module.SQLiteStorageBusy) as full:
            await calls.run_read(lambda: executed.append("overflow"))
        assert full.value.capacity_full
        assert len(executor.pending) == 2
        for _ in range(6):
            executor.finish_one()
            await until(lambda: len(executor.pending) == 2)
        executor.finish_one()
        executor.finish_one()
        await asyncio.gather(*active, *waiting)

    asyncio.run(exercise())
    stats = calls.snapshot()
    assert executed == list(range(6))
    assert stats["peak_pending"] == 6
    assert stats["peak_inflight"] == 2
    assert stats["read_waited"] == 6
    assert stats["queue_full"] == 1
    assert stats["completed"] == 8
    assert stats["pending"] == stats["inflight"] == 0
    calls.shutdown()


def test_pending_timeout_never_submits_or_runs(module):
    calls, executor = deferred(module, capacity=1, read_max_wait_seconds=.02)
    ran = []

    async def exercise():
        active = asyncio.create_task(calls.run(lambda: "active"))
        await until(lambda: len(executor.pending) == 1)
        expired = asyncio.create_task(calls.run_read(lambda: ran.append("expired")))
        await until(lambda: calls.snapshot()["pending"] == 1)
        module._test_clock[0] += .03
        with calls._lock:
            calls._wake_head_locked()
        with pytest.raises(module.SQLiteStorageBusy):
            await expired
        assert len(executor.pending) == 1
        assert calls.snapshot()["pending"] == 0
        replacement = asyncio.create_task(calls.run_read(lambda: ran.append("replacement")))
        await until(lambda: calls.snapshot()["pending"] == 1)
        executor.finish_one()
        await until(lambda: len(executor.pending) == 1)
        executor.finish_one()
        await asyncio.gather(active, replacement)

    asyncio.run(exercise())
    assert ran == ["replacement"]
    assert calls.snapshot()["wait_expired"] == 1
    calls.shutdown()


def test_pending_cancellation_storm_never_grows_physical_queue(module):
    calls, executor = deferred(module, capacity=1)
    ran = []

    async def exercise():
        active = asyncio.create_task(calls.run(lambda: None))
        await until(lambda: len(executor.pending) == 1)
        for _ in range(1000):
            waiting = asyncio.create_task(calls.run_read(lambda: ran.append("cancelled")))
            await until(lambda: calls.snapshot()["pending"] == 1)
            waiting.cancel()
            waiting.cancel()
            await asyncio.gather(waiting, return_exceptions=True)
            assert calls.snapshot()["pending"] == 0
            assert len(executor.pending) == 1
        executor.finish_one()
        await active

    asyncio.run(exercise())
    assert ran == []
    assert calls.snapshot()["pending_cancelled"] == 1000
    assert calls.snapshot()["submitted"] == 1
    calls.shutdown()


def test_cancel_after_submit_retains_permit_until_real_completion(module):
    calls, executor = deferred(module, capacity=1)
    ran = []

    async def exercise():
        task = asyncio.create_task(calls.run_read(lambda: ran.append("submitted")))
        await until(lambda: len(executor.pending) == 1)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        assert calls.snapshot()["inflight"] == 1
        with pytest.raises(module.SQLiteStorageBusy):
            await calls.run(lambda: "must reject immediate write")
        assert not executor.pending[0][0].cancelled()
        executor.finish_one()
        assert calls.snapshot()["inflight"] == 0

    asyncio.run(exercise())
    assert ran == ["submitted"]
    assert calls.snapshot()["submitted_cancelled"] == 1
    calls.shutdown()


@pytest.mark.parametrize("cancel_first", [False, True])
def test_cancel_racing_completion_does_not_submit_pending_read(module, cancel_first):
    calls, executor = deferred(module, capacity=1)
    ran = []

    async def exercise():
        active = asyncio.create_task(calls.run(lambda: None))
        await until(lambda: len(executor.pending) == 1)
        queued = asyncio.create_task(calls.run_read(lambda: ran.append("wrong")))
        await until(lambda: calls.snapshot()["pending"] == 1)
        if cancel_first:
            queued.cancel()
        executor.finish_one()
        if not cancel_first:
            queued.cancel()
        await asyncio.gather(active, queued, return_exceptions=True)
        assert not executor.pending
        assert calls.snapshot()["inflight"] == calls.snapshot()["pending"] == 0
        replacement = asyncio.create_task(calls.run_read(lambda: "replacement"))
        await until(lambda: len(executor.pending) == 1)
        executor.finish_one()
        assert await replacement == "replacement"

    asyncio.run(exercise())
    assert not ran
    calls.shutdown()


def test_deadline_is_rechecked_after_notification_before_submit(module, monkeypatch):
    calls, executor = deferred(module, capacity=1)
    real_monotonic = module.time.monotonic
    clock = [real_monotonic()]
    # Patch only this module's clock, never global time/asyncio's clock.
    monkeypatch.setattr(module, "time", type("Clock", (), {"monotonic": staticmethod(lambda: clock[0])}))

    async def exercise():
        active = asyncio.create_task(calls.run(lambda: None))
        await until(lambda: len(executor.pending) == 1)
        queued = asyncio.create_task(calls.run_read(lambda: "must not execute"))
        await until(lambda: calls.snapshot()["pending"] == 1)
        executor.finish_one()
        clock[0] += 1
        with pytest.raises(module.SQLiteStorageBusy):
            await queued
        await active
        assert not executor.pending

    asyncio.run(exercise())
    assert calls.snapshot()["wait_expired"] == 1
    calls.shutdown()


def test_actual_worker_completion_not_caller_timeout_controls_capacity(module):
    calls = module.BoundedSQLiteCalls(capacity=1, read_max_wait_seconds=.02)
    started = threading.Event()
    release = threading.Event()

    def blocked():
        started.set()
        assert release.wait(10)
        return "done"

    async def exercise():
        running = asyncio.create_task(calls.run_read(blocked))
        assert await asyncio.to_thread(started.wait, 5)
        # Its admission limit is .02; after admission this is not a work timeout.
        expired = asyncio.create_task(calls.run_read(lambda: "expired"))
        await until(lambda: calls.snapshot()["pending"] == 1)
        module._test_clock[0] += .03
        with calls._lock:
            calls._wake_head_locked()
        with pytest.raises(module.SQLiteStorageBusy):
            await expired
        assert not running.done()
        assert calls.snapshot()["running"] == 1
        running.cancel()
        await asyncio.gather(running, return_exceptions=True)
        assert calls.snapshot()["running"] == calls.snapshot()["inflight"] == 1
        release.set()
        await asyncio.to_thread(calls.shutdown)

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        calls.shutdown()
    stats = calls.snapshot()
    assert stats["completed"] == 1
    assert stats["running"] == stats["inflight"] == 0
    assert stats["service_seconds"] > 0


def test_busy_and_ordinary_errors_return_capacity(module):
    calls = module.BoundedSQLiteCalls(capacity=1)

    async def exercise():
        for error in [sqlite3.OperationalError("database is locked"), ValueError("ordinary")]:
            expected = module.SQLiteStorageBusy if isinstance(error, sqlite3.OperationalError) else ValueError
            with pytest.raises(expected):
                await calls.run_read(lambda: (_ for _ in ()).throw(error))
            assert await calls.run(lambda: "available") == "available"

    try:
        asyncio.run(exercise())
    finally:
        calls.shutdown()
    assert calls.snapshot()["sqlite_busy"] == 1
    assert calls.snapshot()["completed"] == 4


def test_submit_failure_returns_permit_and_cleans_ticket(module):
    calls, executor = deferred(module, capacity=1)
    original_submit = executor.submit

    async def exercise():
        active = asyncio.create_task(calls.run(lambda: None))
        await until(lambda: len(executor.pending) == 1)
        queued = asyncio.create_task(calls.run_read(lambda: None))
        await until(lambda: calls.snapshot()["pending"] == 1)
        executor.submit = lambda _fn: (_ for _ in ()).throw(RuntimeError("submission failed"))
        executor.finish_one()
        with pytest.raises(RuntimeError, match="submission failed"):
            await queued
        await active
        executor.submit = original_submit
        replacement = asyncio.create_task(calls.run(lambda: "available"))
        await until(lambda: len(executor.pending) == 1)
        executor.finish_one()
        assert await replacement == "available"

    asyncio.run(exercise())
    assert calls.snapshot()["submission_failed"] == 1
    assert calls.snapshot()["pending"] == calls.snapshot()["inflight"] == 0
    calls.shutdown()


def test_immediately_completed_future_callback_does_not_deadlock(module):
    calls, executor = deferred(module, capacity=1)
    original = executor.submit

    def immediate(function):
        future = original(function)
        executor.finish_one()
        return future

    executor.submit = immediate
    assert asyncio.run(calls.run_read(lambda: "done")) == "done"
    assert calls.snapshot()["inflight"] == 0
    calls.shutdown()


def test_nested_read_rejected_without_deadlock(module):
    calls = module.BoundedSQLiteCalls(capacity=1)

    def nested():
        return asyncio.run(calls.run_read(lambda: "not reached"))

    try:
        with pytest.raises(RuntimeError, match="Nested run_read"):
            asyncio.run(calls.run_read(nested))
        assert asyncio.run(calls.run_read(lambda: "available")) == "available"
    finally:
        calls.shutdown()


def test_shutdown_wakes_pending_without_cancelling_submitted_work(module):
    calls, executor = deferred(module, capacity=1)
    ran = []

    async def exercise():
        active = asyncio.create_task(calls.run(lambda: ran.append("active")))
        await until(lambda: len(executor.pending) == 1)
        queued = asyncio.create_task(calls.run_read(lambda: ran.append("wrong")))
        await until(lambda: calls.snapshot()["pending"] == 1)
        calls.shutdown(wait=False)
        with pytest.raises(module.SQLiteStorageBusy, match="shutting down"):
            await queued
        with pytest.raises(module.SQLiteStorageBusy):
            await calls.run_read(lambda: None)
        assert calls.snapshot()["inflight"] == 1
        executor.finish_one()
        await active

    asyncio.run(exercise())
    assert ran == ["active"]
    assert calls.snapshot()["pending"] == calls.snapshot()["inflight"] == 0


def test_waiting_reads_do_not_reserve_permits_against_immediate_writes(module):
    calls, executor = deferred(module, capacity=1)
    executed = []

    async def exercise():
        first = asyncio.create_task(calls.run(lambda: None))
        await until(lambda: len(executor.pending) == 1)
        read = asyncio.create_task(calls.run_read(lambda: executed.append("read")))
        await until(lambda: calls.snapshot()["pending"] == 1)
        executor.finish_one()
        # Before the reader loop resumes, an existing immediate-write caller may
        # acquire the genuinely free permit. No strict cross-class FIFO is claimed.
        with calls._lock:
            write_future = calls._submit_locked(lambda: executed.append("write"))
        executor.finish_one()
        await until(lambda: len(executor.pending) == 1)
        executor.finish_one()
        await asyncio.gather(first, read)
        assert write_future.done()

    asyncio.run(exercise())
    assert executed == ["write", "read"]
    calls.shutdown()


def test_multiple_event_loops_can_share_wait_queue(module):
    calls = module.BoundedSQLiteCalls(capacity=1)
    first_started = threading.Event()
    release = threading.Event()

    def block():
        first_started.set()
        assert release.wait(10)
        return "first"

    with ThreadPoolExecutor(max_workers=2) as callers:
        first = callers.submit(asyncio.run, calls.run_read(block))
        assert first_started.wait(5)
        second = callers.submit(asyncio.run, calls.run_read(lambda: "second"))
        try:
            # Inspect registration under the gate's own lock, not a sleep-based race.
            for _ in range(10000):
                if calls.snapshot()["pending"] == 1:
                    break
                threading.Event().wait(.0001)
            assert calls.snapshot()["pending"] == 1
            release.set()
            assert first.result(5) == "first"
            assert second.result(5) == "second"
        finally:
            release.set()
            calls.shutdown()


@pytest.mark.parametrize("kwargs", [
    {"read_queue_capacity": 7}, {"read_queue_capacity": -1},
    {"read_max_wait_seconds": .251}, {"read_max_wait_seconds": -1},
    {"read_max_wait_seconds": float("nan")},
])
def test_configuration_cannot_expand_bounds(module, kwargs):
    with pytest.raises(ValueError):
        module.BoundedSQLiteCalls(**kwargs)


def test_closed_loop_head_cannot_strand_following_readers(module):
    calls, executor = deferred(module, capacity=1)
    closed = asyncio.new_event_loop()
    closed.close()
    orphan = module._ReadWaiter(closed, asyncio.Event(), 0.0, .25)
    with calls._lock:
        calls._pending.append(orphan)

    async def exercise():
        replacement = asyncio.create_task(calls.run_read(lambda: "available"))
        await until(lambda: len(executor.pending) == 1)
        executor.finish_one()
        assert await replacement == "available"

    asyncio.run(exercise())
    assert calls.snapshot()["pending_cancelled"] == 1
    assert calls.snapshot()["pending"] == 0
    calls.shutdown()


def test_nested_read_dispatched_back_to_owner_loop_is_rejected(module):
    calls = module.BoundedSQLiteCalls(capacity=1)

    async def exercise():
        loop = asyncio.get_running_loop()
        def nested():
            future = asyncio.run_coroutine_threadsafe(calls.run_read(lambda: "not reached"), loop)
            return future.result(5)
        with pytest.raises(RuntimeError, match="Nested run_read"):
            await calls.run_read(nested)
        assert await calls.run_read(lambda: "available") == "available"

    try:
        asyncio.run(exercise())
    finally:
        calls.shutdown()
