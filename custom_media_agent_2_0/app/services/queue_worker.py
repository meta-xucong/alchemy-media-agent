from __future__ import annotations

import asyncio
import traceback
from dataclasses import dataclass

from app.agents import CreativeManagerRuntime
from app.config import settings
from app.repositories import repository
from app.repositories.memory import utc_now
from app.schemas import CreateCreativeRunRequest, CreativeRun, ImageJob, ImagePromptPlan
from app.services import task_queue
from app.services.ids import new_id
from app.services.prompting import summarize_intent
from app.services.veyra_auth import VeyraAuthError, VeyraInsufficientBalance, VeyraSub2APIClient
from app.services.veyra_billing_settings import get_billing_rule


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
        run = asyncio.run(_preflight_veyra_balance(request, record.run_id)) or asyncio.run(runtime.complete_queued_run(request, record.run_id))
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
    repository.save_image_job(job)
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


def _job_retry_directive(error: dict) -> QueueRetryDirective | None:
    code = str(error.get("error_code") or "")
    message = str(error.get("message") or "")
    provider = str(error.get("provider") or "")
    lowered = message.lower()
    detail = error.get("detail") if isinstance(error.get("detail"), dict) else {}
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
