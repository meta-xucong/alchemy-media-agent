from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException

from app.config import settings


T = TypeVar("T")
_slots = threading.BoundedSemaphore(max(1, settings.history_scan_max_concurrent))


async def run_history_scan(operation: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """Bound in-flight file scans before submitting work to the default executor."""

    if not _slots.acquire(blocking=False):
        raise HTTPException(
            status_code=429,
            detail={
                "error_code": "history_scan_capacity_full",
                "message": "History is busy; retry shortly.",
                "retryable": True,
            },
            headers={"Retry-After": "2"},
        )
    task = asyncio.create_task(asyncio.to_thread(operation, *args, **kwargs))
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
    finally:
        _slots.release()
