from __future__ import annotations

import asyncio
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Any, Callable


class SQLiteStorageBusy(RuntimeError):
    """The bounded SQLite executor is full or SQLite reported a busy lock."""

    def __init__(self, message: str, *, capacity_full: bool = False) -> None:
        super().__init__(message)
        self.capacity_full = capacity_full


class BoundedSQLiteCalls:
    def __init__(self, *, capacity: int = 2, thread_name_prefix: str = "v1-sqlite") -> None:
        self._capacity = threading.BoundedSemaphore(capacity)
        self._executor = ThreadPoolExecutor(max_workers=capacity, thread_name_prefix=thread_name_prefix)

    async def run(self, function: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if not self._capacity.acquire(blocking=False):
            raise SQLiteStorageBusy("SQLite worker capacity is busy; retry shortly.", capacity_full=True)
        try:
            future = self._executor.submit(partial(function, *args, **kwargs))
        except BaseException:
            self._capacity.release()
            raise
        future.add_done_callback(lambda _future: self._capacity.release())
        try:
            # Cancelling an asyncio waiter must not cancel a queued concurrent
            # Future: ThreadPoolExecutor keeps its cancelled work item in the
            # physical queue until a worker dequeues it, while the done
            # callback would otherwise release admission early.
            return await asyncio.shield(asyncio.wrap_future(future))
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                raise SQLiteStorageBusy("SQLite database is busy; retry shortly.") from exc
            raise


sqlite_calls = BoundedSQLiteCalls()
