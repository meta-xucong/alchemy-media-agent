from __future__ import annotations

import asyncio
import math
import sqlite3
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from contextvars import ContextVar
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable

# These are burst-buffer limits, not additional execution capacity.
READ_QUEUE_CAPACITY = 6
READ_MAX_WAIT_SECONDS = 0.250


class SQLiteStorageBusy(RuntimeError):
    """The bounded SQLite executor is full or SQLite reported a busy lock."""

    def __init__(self, message: str, *, capacity_full: bool = False) -> None:
        super().__init__(message)
        self.capacity_full = capacity_full


@dataclass(eq=False)
class _ReadWaiter:
    loop: asyncio.AbstractEventLoop
    ready: asyncio.Event
    queued_at: float
    deadline: float


class BoundedSQLiteCalls:
    def __init__(
        self, *, capacity: int = 2, thread_name_prefix: str = "v1-sqlite",
        read_queue_capacity: int = READ_QUEUE_CAPACITY,
        read_max_wait_seconds: float = READ_MAX_WAIT_SECONDS,
    ) -> None:
        if not isinstance(read_queue_capacity, int) or not 0 <= read_queue_capacity <= READ_QUEUE_CAPACITY:
            raise ValueError("read_queue_capacity must be between 0 and 6")
        if not math.isfinite(read_max_wait_seconds) or not 0 <= read_max_wait_seconds <= READ_MAX_WAIT_SECONDS:
            raise ValueError("read_max_wait_seconds must be between 0 and 0.250")
        self._capacity = threading.BoundedSemaphore(capacity)
        self._executor = ThreadPoolExecutor(max_workers=capacity, thread_name_prefix=thread_name_prefix)
        # A Future can already be complete when add_done_callback is called.
        # Reentrancy makes its inline completion callback safe during admission.
        self._lock = threading.RLock()
        self._pending: deque[_ReadWaiter] = deque()
        self._read_queue_capacity = read_queue_capacity
        self._read_max_wait_seconds = read_max_wait_seconds
        self._closed = False
        self._worker = ContextVar(f"{thread_name_prefix}_worker", default=False)
        self._metrics: dict[str, int | float] = dict(
            submitted=0, completed=0, inflight=0, peak_inflight=0,
            running=0, peak_running=0, peak_pending=0,
            read_immediate=0, read_waited=0, queue_full=0, wait_expired=0,
            pending_cancelled=0, submitted_cancelled=0, capacity_rejected=0,
            sqlite_busy=0, submission_failed=0, wait_seconds=0.0,
            max_wait_seconds=0.0, service_seconds=0.0, max_service_seconds=0.0,
        )

    def snapshot(self) -> dict[str, int | float]:
        """Return bounded aggregate diagnostics; never retain operation payloads."""
        with self._lock:
            return {**self._metrics, "pending": len(self._pending)}

    @staticmethod
    def _capacity_busy() -> SQLiteStorageBusy:
        return SQLiteStorageBusy("SQLite worker capacity is busy; retry shortly.", capacity_full=True)

    def _execute(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        worker_token = self._worker.set(True)
        started = time.monotonic()
        with self._lock:
            self._metrics["running"] += 1
            self._metrics["peak_running"] = max(self._metrics["peak_running"], self._metrics["running"])
        try:
            return function(*args, **kwargs)
        finally:
            elapsed = time.monotonic() - started
            self._worker.reset(worker_token)
            with self._lock:
                self._metrics["running"] -= 1
                self._metrics["completed"] += 1
                self._metrics["service_seconds"] += elapsed
                self._metrics["max_service_seconds"] = max(self._metrics["max_service_seconds"], elapsed)

    def _wake_head_locked(self) -> None:
        while self._pending:
            waiter = self._pending[0]
            try:
                # Wake only; do not reserve capacity against immediate writes.
                waiter.loop.call_soon_threadsafe(waiter.ready.set)
                return
            except RuntimeError:
                # A closed caller loop cannot be allowed to strand later loops.
                self._remove_waiter_locked(waiter)
                self._metrics["pending_cancelled"] += 1

    def _work_done(self, _future: Future) -> None:
        # Only the concurrent Future's real completion returns execution capacity.
        # Awaiter cancellation never cancels this Future.
        with self._lock:
            self._metrics["inflight"] -= 1
            self._capacity.release()
            self._wake_head_locked()

    def _submit_locked(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
        if self._closed:
            raise SQLiteStorageBusy("SQLite worker is shutting down; retry shortly.", capacity_full=True)
        if not self._capacity.acquire(blocking=False):
            raise self._capacity_busy()
        try:
            future = self._executor.submit(partial(self._execute, function, *args, **kwargs))
        except BaseException:
            self._capacity.release()
            self._metrics["submission_failed"] += 1
            self._wake_head_locked()
            raise
        self._metrics["submitted"] += 1
        self._metrics["inflight"] += 1
        self._metrics["peak_inflight"] = max(self._metrics["peak_inflight"], self._metrics["inflight"])
        future.add_done_callback(self._work_done)
        return future

    async def _result(self, future: Future) -> Any:
        wrapped = asyncio.wrap_future(future)
        try:
            return await asyncio.shield(wrapped)
        except asyncio.CancelledError:
            with self._lock:
                self._metrics["submitted_cancelled"] += 1
            # Retrieve a later exception if the caller no longer owns the result.
            # This callback does not cancel the work or release its permit.
            wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
            raise
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                with self._lock:
                    self._metrics["sqlite_busy"] += 1
                raise SQLiteStorageBusy("SQLite database is busy; retry shortly.") from exc
            raise

    async def run(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Keep existing immediate admission, including mutation semantics."""
        with self._lock:
            try:
                future = self._submit_locked(function, *args, **kwargs)
            except SQLiteStorageBusy:
                self._metrics["capacity_rejected"] += 1
                raise
        return await self._result(future)

    def _remove_waiter_locked(self, waiter: _ReadWaiter) -> bool:
        try:
            self._pending.remove(waiter)
        except ValueError:
            return False
        elapsed = time.monotonic() - waiter.queued_at
        self._metrics["wait_seconds"] += elapsed
        self._metrics["max_wait_seconds"] = max(self._metrics["max_wait_seconds"], elapsed)
        return True

    async def run_read(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Opt into a small FIFO wait before submission, never an execution timeout.

        Pending reads hold no execution permit. Writes retain immediate admission;
        FIFO is between readers, not a starvation guarantee between reads/writes.
        """
        if self._worker.get():
            raise RuntimeError("Nested run_read on the same SQLite executor is unsupported")
        loop = asyncio.get_running_loop()
        waiter: _ReadWaiter | None = None
        future: Future | None = None
        with self._lock:
            if self._closed:
                raise SQLiteStorageBusy("SQLite worker is shutting down; retry shortly.", capacity_full=True)
            if not self._pending:
                try:
                    future = self._submit_locked(function, *args, **kwargs)
                except SQLiteStorageBusy:
                    pass
            if future is not None:
                self._metrics["read_immediate"] += 1
            else:
                if len(self._pending) >= self._read_queue_capacity or self._read_max_wait_seconds == 0:
                    self._metrics["queue_full"] += 1
                    raise self._capacity_busy()
                now = time.monotonic()
                waiter = _ReadWaiter(loop, asyncio.Event(), now, now + self._read_max_wait_seconds)
                self._pending.append(waiter)
                self._metrics["peak_pending"] = max(self._metrics["peak_pending"], len(self._pending))
                self._wake_head_locked()
        try:
            while future is None:
                assert waiter is not None
                remaining = waiter.deadline - time.monotonic()
                if remaining > 0:
                    try:
                        await asyncio.wait_for(waiter.ready.wait(), remaining)
                    except asyncio.TimeoutError:
                        pass
                with self._lock:
                    waiter.ready.clear()
                    if self._closed:
                        raise SQLiteStorageBusy("SQLite worker is shutting down; retry shortly.", capacity_full=True)
                    if time.monotonic() >= waiter.deadline:
                        self._metrics["wait_expired"] += 1
                        raise self._capacity_busy()
                    if self._pending and self._pending[0] is waiter:
                        try:
                            future = self._submit_locked(function, *args, **kwargs)
                        except SQLiteStorageBusy:
                            continue
                        self._remove_waiter_locked(waiter)
                        self._metrics["read_waited"] += 1
                        self._wake_head_locked()
            return await self._result(future)
        except asyncio.CancelledError:
            with self._lock:
                if waiter is not None and self._remove_waiter_locked(waiter):
                    self._metrics["pending_cancelled"] += 1
            raise
        finally:
            with self._lock:
                if waiter is not None:
                    self._remove_waiter_locked(waiter)
                self._wake_head_locked()

    def shutdown(self, *, wait: bool = True) -> None:
        """Stop admission and drain submitted work; call off-loop when wait=True."""
        with self._lock:
            self._closed = True
            for waiter in list(self._pending):
                self._remove_waiter_locked(waiter)
                try:
                    waiter.loop.call_soon_threadsafe(waiter.ready.set)
                except RuntimeError:
                    pass
        self._executor.shutdown(wait=wait, cancel_futures=False)


sqlite_calls = BoundedSQLiteCalls()
