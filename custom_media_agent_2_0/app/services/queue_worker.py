from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
import traceback
import uuid
from dataclasses import dataclass, field

from app.agents import CreativeManagerRuntime
from app.config import settings
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import CreateCreativeRunRequest, CreativeRun, ImageJob, ImagePromptPlan
from app.services import task_queue
from app.services.generation_capacity import GenerationCapacityExceeded, GenerationCapacityStorageBusy
from app.services.ids import new_id
from app.services.prompting import summarize_intent
from app.services.veyra_auth import VeyraAuthError, VeyraInsufficientBalance, VeyraSub2APIClient
from app.services.veyra_billing_settings import get_billing_rule


_UPSTREAM_BALANCE_WAIT_SECONDS = 300.0
_PROVIDER_RATE_LIMIT_WAIT_SECONDS = 180.0
_GENERIC_RETRYABLE_WAIT_SECONDS = 120.0
_MAX_WAIT_SECONDS = 900.0
_BRIDGE_RECONCILIATION_WAIT_SECONDS = 120.0
_FINALIZATION_RETRIES = 3
_FINALIZATION_RETRY_DELAY_SECONDS = 0.05
logger = logging.getLogger(__name__)


def _worker_instance_id() -> str:
    return f"v2-inline-{uuid.uuid4().hex}"


def _recover_success_checkpoint(claim: task_queue.QueuedTask) -> tuple[CreativeRun | None, bool]:
    try:
        return task_queue.get_success_checkpoint(claim), False
    except task_queue.InvalidSuccessCheckpoint as exc:
        if task_queue.terminalize_invalid_success_checkpoint(claim, exc):
            logger.error(
                "V2 task %s was quarantined because its success checkpoint failed integrity validation (%s)",
                claim.task_id,
                exc.cause_type,
            )
        else:
            logger.info("V2 task %s checkpoint quarantine skipped because its claim was superseded", claim.task_id)
        return None, True


@dataclass
class QueueWorker:
    runtime: CreativeManagerRuntime
    worker_id: str = field(default_factory=_worker_instance_id)

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        next_cache_maintenance = 0.0
        while not stop_event.is_set():
            try:
                await task_queue.initialize_task_queue_async()
                break
            except task_queue.QueueStorageBusy:
                await asyncio.sleep(max(0.1, settings.task_queue_poll_interval_seconds))
        while not stop_event.is_set():
            if time.monotonic() >= next_cache_maintenance:
                next_cache_maintenance = time.monotonic() + 60.0
                from app.services.render_bridge_primary import maintain_completed_caches
                try:
                    await asyncio.wait_for(maintain_completed_caches(), timeout=5.0)
                except (TimeoutError, OSError, sqlite3.Error, ValueError):
                    logger.warning('V2 Bridge completed-cache maintenance deferred')
            try:
                processed = await asyncio.to_thread(process_next_task_once, self.runtime, self.worker_id)
            except task_queue.QueueStorageBusy:
                processed = False
                logger.warning("V2 task queue database is busy; worker will retry")
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    raise
                processed = False
                logger.warning("V2 task queue database is locked; worker will retry")
            if not processed:
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=settings.task_queue_poll_interval_seconds)
                except TimeoutError:
                    continue


def process_next_task_once(runtime: CreativeManagerRuntime, worker_id: str | None = None) -> bool:
    worker_id = worker_id or _worker_instance_id()
    try:
        record = task_queue.claim_next_task(worker_id)
    except sqlite3.OperationalError as exc:
        if "locked" in str(exc).lower() or "busy" in str(exc).lower():
            logger.warning("V2 task claim skipped because the queue database is locked")
            return False
        raise
    if record is None:
        return False
    with task_queue.claim_heartbeat(record) as claim_lost:
        try:
            if record.kind not in {"creative_run", "revision_run"}:
                raise ValueError(f"Unsupported task kind: {record.kind}")
            request = CreateCreativeRunRequest.model_validate(record.payload)
            run, invalid_checkpoint = _recover_success_checkpoint(record)
            if invalid_checkpoint:
                return True
            if run is not None:
                run = task_queue.restore_success_checkpoint(run)
                from app.services import render_bridge_primary
                frozen = render_bridge_primary.load_frozen()
                if frozen is not None:
                    asyncio.run(render_bridge_primary.acknowledge(frozen))
                _complete_task_with_bounded_retry(record, run)
                return True
            # A frozen request already passed billing preflight before admission.
            # Recovery may follow a successful debit; low remaining balance must
            # not replace that job or prevent its idempotent completion.
            from app.services import render_bridge_primary
            frozen = render_bridge_primary.load_frozen()
            run = None if frozen is not None else asyncio.run(_preflight_veyra_balance(request, record.run_id))
            if run is not None:
                run = task_queue.persist_claimed_operation(lambda: _save_preflight_run(run))
            if not task_queue.task_claim_is_current(record):
                logger.info("V2 task claim was superseded during preflight; provider work was skipped")
                return True
            if run is None:
                try:
                    run = asyncio.run(
                        task_queue.run_with_generation_capacity(
                            lambda: runtime.complete_queued_run(request, record.run_id),
                            request_kind="worker",
                            claim=record,
                        )
                    )
                except GenerationCapacityExceeded:
                    snapshot = task_queue.get_run_snapshot(record.run_id)
                    if snapshot is None:
                        task_queue.fail_task(
                            record,
                            "Generation capacity is busy; queued run snapshot was unavailable.",
                        )
                    else:
                        task_queue.retry_task(
                            record,
                            "Image generation is busy. The task remains queued and will retry shortly.",
                            snapshot,
                            retry_delay_seconds=5,
                            consume_attempt=False,
                        )
                    return True
                except GenerationCapacityStorageBusy:
                    snapshot = task_queue.get_run_snapshot(record.run_id)
                    if snapshot is not None:
                        task_queue.retry_task(
                            record,
                            "Local image generation storage is busy; the task will retry shortly.",
                            snapshot,
                            retry_delay_seconds=5,
                            consume_attempt=False,
                        )
                    return True
            checkpoint, invalid_checkpoint = _recover_success_checkpoint(record)
            if invalid_checkpoint:
                return True
            if checkpoint is not None:
                run = task_queue.restore_success_checkpoint(checkpoint)
            if not task_queue.task_claim_is_current(record):
                logger.info("V2 task claim was superseded during provider work; stale result was not persisted")
                return True
            retry_directive = _queued_run_retry_directive(run)
            if retry_directive:
                exhausted = retry_directive.consume_attempt and record.attempts >= record.max_attempts
                snapshot = (
                    _retry_exhausted_run_snapshot(run, retry_directive.message)
                    if exhausted
                    else _waiting_run_snapshot(run, retry_directive.message)
                )
                message = snapshot.next_actions[0] if snapshot.next_actions else retry_directive.message
                task_queue.retry_task(
                    record,
                    message,
                    snapshot,
                    retry_delay_seconds=retry_directive.retry_delay_seconds,
                    consume_attempt=retry_directive.consume_attempt,
                )
                return True
            bridge_terminal_job = next(
                (
                    job
                    for job in run.generation_jobs
                    if run.status == "failed"
                    and job.provider_id == "render_bridge"
                    and (job.error or {}).get("error_code") == "bridge_terminal"
                    and (job.error or {}).get("retryable") is False
                ),
                None,
            )
            if bridge_terminal_job is not None:
                error = bridge_terminal_job.error or {}
                message = str(
                    error.get("message")
                    or (run.next_actions[0] if run.next_actions else "Render Bridge task failed terminally.")
                )
                task_queue.fail_task(record, message, run, force_terminal=True)
                return True
            if _bridge_reconciliation_required(run):
                message = run.next_actions[0] if run.next_actions else "Render Bridge reconciliation deadline elapsed."
                task_queue.fail_task(record, message, run, force_terminal=True)
                return True
            _complete_task_with_bounded_retry(record, run)
        except GenerationCapacityStorageBusy:
            snapshot = task_queue.get_run_snapshot(record.run_id)
            if snapshot is not None:
                task_queue.retry_task(
                    record,
                    "Local image generation storage is busy; the task will retry shortly.",
                    snapshot,
                    retry_delay_seconds=5,
                    consume_attempt=False,
                )
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() or "busy" in str(exc).lower():
                logger.warning("V2 task processing deferred because the queue database is locked")
                return True
            raise
        except Exception as exc:
            if claim_lost.is_set() or not task_queue.task_claim_is_current(record):
                logger.info("V2 task claim was superseded; stale failure was not persisted")
                return True
            task_queue.fail_task(record, _format_error(exc))
    return True


def _complete_task_with_bounded_retry(claim: task_queue.QueuedTask, run: CreativeRun) -> bool:
    for attempt in range(_FINALIZATION_RETRIES):
        try:
            return task_queue.complete_task(claim, run)
        except sqlite3.OperationalError as exc:
            if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                raise
            if attempt + 1 == _FINALIZATION_RETRIES:
                logger.error(
                    "V2 task result was ready, but terminal queue finalization remained busy after %s attempts",
                    _FINALIZATION_RETRIES,
                )
                return False
            time.sleep(_FINALIZATION_RETRY_DELAY_SECONDS * (attempt + 1))
    return False


@dataclass(frozen=True)
class QueueRetryDirective:
    message: str
    retry_delay_seconds: float
    consume_attempt: bool = True


async def _preflight_veyra_balance(request: CreateCreativeRunRequest, run_id: str) -> CreativeRun | None:
    rule = get_billing_rule("alchemy:v2")
    if not (settings.veyra_auth_enabled and rule.enabled and request.veyra_user_id and rule.charge_amount > 0):
        return None
    try:
        account = await VeyraSub2APIClient().account(int(request.veyra_user_id))
        if float(account.balance) + 1e-9 >= float(rule.charge_amount):
            return None
        raise VeyraInsufficientBalance("Insufficient sub2api balance.")
    except VeyraInsufficientBalance:
        return _veyra_balance_failed_run(request, run_id)
    except VeyraAuthError:
        return None


def _veyra_balance_failed_run(request: CreateCreativeRunRequest, run_id: str) -> CreativeRun:
    now = utc_now()
    mode = request.mode_hint or ("template_customize" if request.template_case_id else "smart_enhance")
    prompt_plan = ImagePromptPlan(
        plan_id=new_id("plan"),
        mode=mode,  # type: ignore[arg-type]
        prompt=summarize_intent(request.user_prompt) or "Veyra balance preflight failed.",
        explanation="Stopped before creative orchestration because the linked Veyra account balance is insufficient.",
    )
    job = ImageJob(
        veyra_user_id=request.veyra_user_id,
        job_id=new_id("job"),
        run_id=run_id,
        status="failed",
        provider_id="veyra_billing",
        model="veyra-billing-preflight",
        prompt_plan=prompt_plan,
        outputs=[],
        error=_veyra_balance_error_payload(),
        created_at=now,
        updated_at=now,
    )
    run = CreativeRun(
        run_id=run_id,
        status="failed",
        mode=mode,  # type: ignore[arg-type]
        intent_summary=summarize_intent(request.user_prompt),
        prompt_plan=prompt_plan,
        generation_jobs=[job],
        trace_id=new_id("trace"),
        next_actions=[_VEYRA_BALANCE_MESSAGE],
        created_at=now,
        updated_at=now,
    )
    return run


def _save_preflight_run(run: CreativeRun) -> CreativeRun:
    for job in run.generation_jobs:
        repository.save_image_job(job)
    return repository.save_creative_run(run)


_VEYRA_BALANCE_MESSAGE = "账户余额不足，请先充值后再生成。"


def _veyra_balance_error_payload() -> dict:
    return {
        "error_code": "veyra_insufficient_balance",
        "message": _VEYRA_BALANCE_MESSAGE,
        "detail": {"reason": "user_balance_insufficient"},
        "provider": "veyra_billing",
        "retryable": False,
        "native_v2": True,
    }


def _queued_run_retry_directive(run: CreativeRun) -> QueueRetryDirective | None:
    if run.status != "failed":
        return None
    for job in run.generation_jobs:
        directive = _job_retry_directive(job.error or {})
        if directive:
            return directive
    return None


def _bridge_reconciliation_required(run: CreativeRun) -> bool:
    return any(
        (job.error or {}).get("provider") == "render_bridge"
        and isinstance((job.error or {}).get("detail"), dict)
        and (job.error or {})["detail"].get("queue_reconciliation_required") is True
        for job in run.generation_jobs
    )


def _job_retry_directive(error: dict) -> QueueRetryDirective | None:
    code = str(error.get("error_code") or "")
    message = str(error.get("message") or "")
    provider = str(error.get("provider") or "")
    lowered = message.lower()
    detail = error.get("detail") if isinstance(error.get("detail"), dict) else {}
    if provider == "veyra_billing" and code == "bridge_finalization_wait":
        return QueueRetryDirective(message="Completing the existing image and billing transaction; no new image will be generated.",
                                   retry_delay_seconds=120.0, consume_attempt=False)
    if provider == "render_bridge" and code == "bridge_wait":
        if not bool(error.get("retryable")):
            return None
        return QueueRetryDirective(
            message=("Render Bridge has not confirmed a final result. The same task will be queried "
                     "until its persisted Bridge deadline; no API fallback or new image is allowed."),
            retry_delay_seconds=_BRIDGE_RECONCILIATION_WAIT_SECONDS,
            consume_attempt=False,
        )
    if provider == "veyra_billing" and code == "veyra_insufficient_balance":
        return None
    if "sub2api balance is insufficient" in lowered:
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


def _retry_exhausted_run_snapshot(run: CreativeRun, retry_message: str) -> CreativeRun:
    now = utc_now()
    bridge_unresolved = any(
        (job.error or {}).get("provider") == "render_bridge"
        and (job.error or {}).get("error_code") == "bridge_wait"
        for job in run.generation_jobs
    )
    if bridge_unresolved:
        final_message = (
            "Render Bridge 未在有限恢复窗口内返回最终结果；任务已停止自动轮询并移出活跃队列。"
            "原 Bridge 任务、attempt 和对账账本仍保留；后续只能对原任务恢复，不会转 API 或重新生图。"
        )
    else:
        final_message = _retry_exhausted_message(retry_message)
    jobs = []
    for job in run.generation_jobs:
        error = dict(job.error or {})
        if error.get("provider") == "render_bridge" and error.get("error_code") == "bridge_wait":
            detail = dict(error.get("detail") or {})
            detail["queue_reconciliation_required"] = True
            error.update({"retryable": False, "detail": detail})
            job = job.model_copy(update={"status": "failed", "error": error, "updated_at": now})
        jobs.append(job)
    return run.model_copy(
        update={
            "status": "failed",
            "generation_jobs": jobs,
            "next_actions": [final_message],
            "updated_at": now,
        }
    )


def _retry_exhausted_message(retry_message: str) -> str:
    reason = retry_message
    marker = "原因："
    if marker in reason:
        reason = reason.split(marker, 1)[1].strip()
    return f"图像上游连续重试后仍不可用，任务已停止自动重试。{('最后原因：' + reason) if reason else ''}"


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
