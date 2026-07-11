from __future__ import annotations

import asyncio
from collections import OrderedDict
import time
from typing import Awaitable, Callable, TypeVar


T = TypeVar("T")


class RequestCoordinator:
    """Serialize GPU work and collapse duplicate idempotent requests."""

    def __init__(self, *, concurrency: int, ttl_seconds: float, max_entries: int) -> None:
        self._semaphore = asyncio.Semaphore(max(1, concurrency))
        self._ttl_seconds = max(0.0, ttl_seconds)
        self._max_entries = max(1, max_entries)
        self._lock = asyncio.Lock()
        self._inflight: dict[str, asyncio.Future] = {}
        self._cache: OrderedDict[str, tuple[float, object]] = OrderedDict()

    async def execute(self, key: str, operation: Callable[[], Awaitable[T]]) -> T:
        owner = False
        async with self._lock:
            self._purge_expired()
            cached = self._cache.get(key)
            if cached is not None:
                self._cache.move_to_end(key)
                return cached[1]  # type: ignore[return-value]
            future = self._inflight.get(key)
            if future is None:
                future = asyncio.get_running_loop().create_future()
                self._inflight[key] = future
                owner = True

        if not owner:
            return await asyncio.shield(future)

        try:
            async with self._semaphore:
                result = await operation()
            async with self._lock:
                if self._ttl_seconds > 0:
                    self._cache[key] = (time.monotonic() + self._ttl_seconds, result)
                    self._cache.move_to_end(key)
                    while len(self._cache) > self._max_entries:
                        self._cache.popitem(last=False)
                current = self._inflight.pop(key, None)
                if current is not None and not current.done():
                    current.set_result(result)
            return result
        except BaseException as exc:
            async with self._lock:
                current = self._inflight.pop(key, None)
                if current is not None and not current.done():
                    current.set_exception(exc)
                    current.add_done_callback(lambda item: item.exception())
            raise

    def _purge_expired(self) -> None:
        now = time.monotonic()
        expired = [key for key, (expires_at, _value) in self._cache.items() if expires_at <= now]
        for key in expired:
            self._cache.pop(key, None)
