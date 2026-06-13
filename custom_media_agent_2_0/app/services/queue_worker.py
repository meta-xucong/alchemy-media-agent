from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass

from app.agents import CreativeManagerRuntime
from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreateCreativeRunRequest, CreativeRun
from app.services import task_queue


_UPSTREAM_BALANCE_WAIT_SECONDS = 300.0
_PROVIDER_RATE_LIMIT_WAIT_SECONDS = 180.0
_GENERIC_RETRYABLE_WAIT_SECONDS = 120.0
_MAX_WAIT_SECONDS = 900.0


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
        retry_directive = _queued_run_retry_directive(run)
        if retry_directive:
            task_queue.retry_task(
                record.task_id,
                retry_directive.message,
                _waiting_run_snapshot(run, retry_directive.message),
                retry_delay_seconds=retry_directive.retry_delay_seconds,
                consume_attempt=retry_directive.consume_attempt,
            )
            return True
        task_queue.complete_task(record.task_id, run)
    except Exception as exc:
        task_queue.fail_task(record.task_id, _format_error(exc))
    return True


@dataclass(frozen=True)
class QueueRetryDirective:
    message: str
    retry_delay_seconds: float
    consume_attempt: bool = True


def _queued_run_retry_directive(run: CreativeRun) -> QueueRetryDirective | None:
    if run.status != "failed":
        return None
    for job in run.generation_jobs:
        directive = _job_retry_directive(job.error or {})
        if directive:
            return directive
    return None


def _job_retry_directive(error: dict) -> QueueRetryDirective | None:
    code = str(error.get("error_code") or "")
    message = str(error.get("message") or "")
    lowered = message.lower()
    detail = error.get("detail") if isinstance(error.get("detail"), dict) else {}
    if code == "veyra_insufficient_balance" or "sub2api balance is insufficient" in lowered:
        return QueueRetryDirective(
            message="上游线路或额度暂时不可用，任务已保留在队列中，约 5 分钟后自动重试。",
            retry_delay_seconds=_retry_after_seconds(detail, _UPSTREAM_BALANCE_WAIT_SECONDS),
            consume_attempt=False,
        )
    if code == "provider_rate_limit":
        return QueueRetryDirective(
            message="图像上游当前限流，任务已保留在队列中，稍后自动重试。",
            retry_delay_seconds=_retry_after_seconds(detail, _PROVIDER_RATE_LIMIT_WAIT_SECONDS),
            consume_attempt=False,
        )
    if bool(error.get("retryable")):
        return QueueRetryDirective(
            message=f"图像上游暂时不可用，任务已保留在队列中，稍后自动重试。{(' 原因：' + message) if message else ''}",
            retry_delay_seconds=_retry_after_seconds(detail, _GENERIC_RETRYABLE_WAIT_SECONDS),
            consume_attempt=True,
        )
    return None


def _waiting_run_snapshot(run: CreativeRun, message: str) -> CreativeRun:
    now = utc_now()
    waiting_jobs = [
        job.model_copy(update={"status": "queued", "error": None, "updated_at": now})
        if job.status == "failed"
        else job
        for job in run.generation_jobs
    ]
    return run.model_copy(
        update={
            "status": "generating",
            "generation_jobs": waiting_jobs,
            "next_actions": [message],
            "updated_at": now,
        }
    )


def _retry_after_seconds(detail: dict, default_seconds: float) -> float:
    for key in ("retry_after_seconds", "retry_after", "cooldown_seconds", "local_cooldown_seconds"):
        value = detail.get(key)
        if value is None:
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        return min(max(parsed, 1.0), _MAX_WAIT_SECONDS)
    return default_seconds


def _format_error(exc: Exception) -> str:
    detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
    return detail or str(exc) or "Unknown queue worker failure."
