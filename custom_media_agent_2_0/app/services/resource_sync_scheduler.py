from __future__ import annotations

import asyncio
import contextlib
import logging

from app.config import settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID
from app.services.resource_sync import sync_resource_provider


logger = logging.getLogger(__name__)


class ResourceSyncScheduler:
    def __init__(self, *, provider_id: str = EVOLINKAI_PROVIDER_ID, mode: str = "auto") -> None:
        self.provider_id = provider_id
        self.mode = mode

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        interval_seconds = max(60, int(settings.resource_sync_interval_minutes) * 60)
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
                break
            except asyncio.TimeoutError:
                pass
            try:
                sync_run = await asyncio.to_thread(sync_resource_provider, self.provider_id, self.mode)
                logger.info(
                    "Scheduled resource sync finished: provider=%s status=%s run=%s",
                    self.provider_id,
                    sync_run.status,
                    sync_run.sync_run_id,
                )
            except Exception:
                logger.exception("Scheduled resource sync failed: provider=%s", self.provider_id)

    @staticmethod
    async def stop(task: asyncio.Task | None, stop_event: asyncio.Event | None) -> None:
        if stop_event:
            stop_event.set()
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
