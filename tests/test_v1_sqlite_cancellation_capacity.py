from __future__ import annotations

import asyncio
import sqlite3
import threading

from fastapi import HTTPException

from app.main import _run_sqlite_api_call
from app.services.alchemy_lab import _run_lab_sqlite_call


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
