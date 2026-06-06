from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass

from app.agents import CreativeManagerRuntime
from app.config import settings
from app.schemas import CreateCreativeRunRequest
from app.services import task_queue


@dataclass
class QueueWorker:
    runtime: CreativeManagerRuntime
    worker_id: str = "v2-inline-worker"

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        task_queue.initialize_task_queue()
        while not stop_event.is_set():
            processed = await asyncio.to_thread(process_next_task_once, self.runtime, self.worker_id)
            if not processed:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=settings.task_queue_poll_interval_seconds)
                except TimeoutError:
                    continue


def process_next_task_once(runtime: CreativeManagerRuntime, worker_id: str = "v2-worker") -> bool:
    record = task_queue.claim_next_task(worker_id)
    if record is None:
        return False
    try:
        if record.kind not in {"creative_run", "revision_run"}:
            raise ValueError(f"Unsupported task kind: {record.kind}")
        request = CreateCreativeRunRequest.model_validate(record.payload)
        run = asyncio.run(runtime.complete_queued_run(request, record.run_id))
        task_queue.complete_task(record.task_id, run)
    except Exception as exc:
        task_queue.fail_task(record.task_id, _format_error(exc))
    return True


def _format_error(exc: Exception) -> str:
    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return detail or str(exc) or "Unknown queue worker failure."
