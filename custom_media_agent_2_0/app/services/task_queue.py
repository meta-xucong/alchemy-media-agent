from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Callable, Iterator

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreativeRun
from app.services.generation_capacity import (
    GenerationCapacityExceeded,
    GenerationCapacityStorageBusy,
    generation_capacity as _generation_capacity,
    run_sqlite_async,
    run_with_generation_capacity as _run_with_generation_capacity,
    terminalize_exhausted_stale_tasks,
)
from app.services.ids import new_id


logger = logging.getLogger(__name__)
TaskStatus = str
_SUCCESS_CHECKPOINT_VERSION = 2


class QueueCapacityExceeded(RuntimeError):
    """Raised when the durable V2 queue has no pending capacity."""


class QueueStorageBusy(RuntimeError):
    """Raised when bounded queue persistence is saturated or locked."""


class StaleTaskClaim(RuntimeError):
    """Raised when a superseded worker tries to commit task-owned output."""


class InvalidSuccessCheckpoint(RuntimeError):
    """Raised when persisted success evidence cannot be safely recovered."""

    def __init__(self, cause_type: str) -> None:
        super().__init__("Persisted V2 success checkpoint failed integrity validation.")
        self.cause_type = cause_type


@dataclass(frozen=True)
class QueuedTask:
    task_id: str
    kind: str
    run_id: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int
    worker_id: str
    claim_token: str


_CURRENT_CLAIM: ContextVar[QueuedTask | None] = ContextVar("v2_current_task_claim", default=None)


def initialize_task_queue() -> int:
    settings.task_queue_db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        wal_retry_loops = _ensure_wal_mode(conn)
        # API and standalone workers may initialize the same database at once.
        # Serialize schema inspection and ALTERs so both cannot add one column.
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS v2_tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                run_id TEXT NOT NULL,
                status TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                queued_run_json TEXT NOT NULL,
                result_json TEXT,
                error_json TEXT,
                attempts INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 3,
                locked_by TEXT,
                locked_at TEXT,
                not_before TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                claim_token TEXT,
                claim_generation INTEGER NOT NULL DEFAULT 0,
                success_checkpoint_json TEXT
            )
            """
        )
        _ensure_column(conn, "v2_tasks", "not_before", "TEXT")
        _ensure_column(conn, "v2_tasks", "claim_token", "TEXT")
        _ensure_column(conn, "v2_tasks", "claim_generation", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "v2_tasks", "success_checkpoint_json", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_tasks_run_id ON v2_tasks(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_tasks_status_created ON v2_tasks(status, created_at)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_v2_tasks_status_not_before_created ON v2_tasks(status, not_before, created_at)"
        )
        conn.commit()
    return wal_retry_loops


async def initialize_task_queue_async() -> None:
    try:
        await run_sqlite_async(initialize_task_queue)
    except GenerationCapacityStorageBusy as exc:
        raise QueueStorageBusy(str(exc)) from exc


def enqueue_creative_task(*, kind: str, request_payload: dict[str, Any], queued_run: CreativeRun) -> str:
    initialize_task_queue()
    now = utc_now().isoformat()
    task_id = new_id("task")
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        pending = conn.execute("SELECT COUNT(*) FROM v2_tasks WHERE status = 'queued'").fetchone()[0]
        if int(pending) >= settings.task_queue_max_pending:
            conn.rollback()
            raise QueueCapacityExceeded("V2 task queue is full.")
        conn.execute(
            """
            INSERT INTO v2_tasks (
                task_id, kind, run_id, status, payload_json, queued_run_json,
                attempts, max_attempts, created_at, updated_at
            )
            VALUES (?, ?, ?, 'queued', ?, ?, 0, ?, ?, ?)
            """,
            (
                task_id,
                kind,
                queued_run.run_id,
                _json_dumps(request_payload),
                _json_dumps(queued_run.model_dump(mode="json")),
                settings.task_queue_max_attempts,
                now,
                now,
            ),
        )
        conn.commit()
    return task_id


async def enqueue_creative_task_async(*, kind: str, request_payload: dict[str, Any], queued_run: CreativeRun) -> str:
    try:
        return await run_sqlite_async(
            lambda: enqueue_creative_task(kind=kind, request_payload=request_payload, queued_run=queued_run)
        )
    except GenerationCapacityStorageBusy as exc:
        raise QueueStorageBusy(str(exc)) from exc


@contextmanager
def generation_capacity(*, request_kind: str = "direct", claim: QueuedTask | None = None) -> Iterator[None]:
    """Hold a same-host slot coordinated with queue work in this database."""

    with _generation_capacity(
        Path(settings.task_queue_db_path),
        limit=settings.max_concurrent_image_generations,
        request_kind=request_kind,
        lease_ttl_seconds=settings.generation_capacity_lease_ttl_seconds,
        queue_recovery_timeout_seconds=settings.task_queue_claim_timeout_seconds,
        task_id=claim.task_id if claim else None,
        claim_token=claim.claim_token if claim else None,
        worker_id=claim.worker_id if claim else None,
    ):
        yield


async def run_with_generation_capacity(
    operation,
    *,
    request_kind: str = "direct",
    claim: QueuedTask | None = None,
):
    """Run provider work under the local lease with task ownership rechecked."""

    return await _run_with_generation_capacity(
        operation,
        database_path=Path(settings.task_queue_db_path),
        limit=settings.max_concurrent_image_generations,
        request_kind=request_kind,
        lease_ttl_seconds=settings.generation_capacity_lease_ttl_seconds,
        queue_recovery_timeout_seconds=settings.task_queue_claim_timeout_seconds,
        task_id=claim.task_id if claim else None,
        claim_token=claim.claim_token if claim else None,
        worker_id=claim.worker_id if claim else None,
        before_operation=(lambda: task_claim_is_current(claim)) if request_kind == "worker" and claim else None,
    )


def claim_next_task(worker_id: str) -> QueuedTask | None:
    initialize_task_queue()
    now = utc_now()
    now_text = now.isoformat()
    stale_before = (now - timedelta(seconds=settings.task_queue_claim_timeout_seconds)).isoformat()
    new_claim_token = uuid.uuid4().hex
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        terminalize_exhausted_stale_tasks(conn, stale_before=stale_before, now_text=now_text)
        row = conn.execute(
            """
            SELECT * FROM v2_tasks
            WHERE
                (status = 'queued' AND (not_before IS NULL OR not_before <= ?))
                OR (
                    status = 'running' AND locked_at IS NOT NULL AND locked_at < ?
                    AND (
                        attempts < max_attempts
                        OR (success_checkpoint_json IS NOT NULL AND success_checkpoint_json <> '')
                    )
                )
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (now_text, stale_before),
        ).fetchone()
        if row is None:
            conn.commit()
            return None

        has_success_checkpoint = bool(row["success_checkpoint_json"])
        attempts = int(row["attempts"]) if has_success_checkpoint else int(row["attempts"]) + 1
        old_status = str(row["status"])
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'running', attempts = ?, locked_by = ?, locked_at = ?, not_before = NULL,
                claim_token = ?, claim_generation = claim_generation + 1, updated_at = ?
            WHERE task_id = ? AND status = ? AND COALESCE(locked_at, '') = ?
              AND COALESCE(claim_token, '') = ?
            """,
            (
                attempts,
                worker_id,
                now_text,
                new_claim_token,
                now_text,
                row["task_id"],
                old_status,
                str(row["locked_at"] or ""),
                str(row["claim_token"] or ""),
            ),
        )
        if cursor.rowcount != 1:
            conn.rollback()
            return None
        conn.commit()
    return QueuedTask(
        task_id=str(row["task_id"]),
        kind=str(row["kind"]),
        run_id=str(row["run_id"]),
        payload=_json_loads(row["payload_json"]),
        attempts=attempts,
        max_attempts=int(row["max_attempts"]),
        worker_id=worker_id,
        claim_token=new_claim_token,
    )


def refresh_task_claim(claim: QueuedTask) -> bool:
    now = utc_now().isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE v2_tasks SET locked_at = ?, updated_at = ?
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (now, now, claim.task_id, claim.worker_id, claim.claim_token),
        )
        return cursor.rowcount == 1


def task_claim_is_current(claim: QueuedTask | None) -> bool:
    if claim is None:
        return False
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM v2_tasks
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (claim.task_id, claim.worker_id, claim.claim_token),
        ).fetchone()
    return row is not None


def current_claim() -> QueuedTask | None:
    return _CURRENT_CLAIM.get()


def ensure_current_claim(claim: QueuedTask | None = None) -> None:
    active_claim = claim or current_claim()
    if active_claim is not None and not task_claim_is_current(active_claim):
        raise StaleTaskClaim("The V2 task claim was superseded before output commit.")


def persist_claimed_operation(
    operation: Callable[[], Any],
    *,
    on_persisted: Callable[[sqlite3.Connection, Any], None] | None = None,
):
    """Commit local task-owned effects only while this claim fences queue takeover.

    Keep the transaction around local persistence only. Provider and billing
    network calls must happen outside this lock.
    """

    claim = current_claim()
    if claim is None:
        return operation()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT 1 FROM v2_tasks
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (claim.task_id, claim.worker_id, claim.claim_token),
        ).fetchone()
        if row is None:
            conn.rollback()
            raise StaleTaskClaim("The V2 task claim was superseded before output commit.")
        try:
            result = operation()
            if on_persisted is not None:
                on_persisted(conn, result)
            conn.commit()
            return result
        except BaseException:
            conn.rollback()
            raise


def checkpoint_completed_generation(connection: sqlite3.Connection, job) -> None:
    """Persist a complete task snapshot after its final image job is durable.

    A task with more than one generation job is checkpointed only when every
    job in its current run snapshot is completed. This prevents a partial
    generation from becoming a terminal success.
    """

    if getattr(job, "status", None) != "completed":
        return
    claim = current_claim()
    if claim is None:
        return
    row = connection.execute(
        """
        SELECT queued_run_json FROM v2_tasks
        WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
        """,
        (claim.task_id, claim.worker_id, claim.claim_token),
    ).fetchone()
    if row is None:
        raise StaleTaskClaim("The V2 task claim was superseded before success checkpoint persistence.")
    snapshot = CreativeRun.model_validate(_json_loads(row["queued_run_json"]))
    if snapshot.run_id != job.run_id or snapshot.status != "generating":
        return
    jobs = list(snapshot.generation_jobs)
    match_indexes = [index for index, existing in enumerate(jobs) if existing.job_id == job.job_id]
    if len(match_indexes) != 1:
        # A generation result that is not represented in the complete task
        # snapshot cannot prove task completion.
        return
    jobs[match_indexes[0]] = job
    if not jobs or any(item.status != "completed" for item in jobs):
        return
    completed = snapshot.model_copy(
        update={
            "status": "completed",
            "generation_jobs": jobs,
            "prompt_plan": jobs[0].prompt_plan if jobs else snapshot.prompt_plan,
            "next_actions": ["Review generated outputs and select a favorite or request revisions."],
            "updated_at": utc_now(),
        }
    )
    _validate_success_checkpoint_run(completed, expected_snapshot=snapshot)
    cursor = connection.execute(
        """
        UPDATE v2_tasks SET success_checkpoint_json = ?, updated_at = ?
        WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
        """,
        (
            _encode_success_checkpoint(completed),
            utc_now().isoformat(),
            claim.task_id,
            claim.worker_id,
            claim.claim_token,
        ),
    )
    if cursor.rowcount != 1:
        raise StaleTaskClaim("The V2 task claim was superseded before success checkpoint persistence.")


def get_success_checkpoint(claim: QueuedTask | None = None) -> CreativeRun | None:
    active_claim = claim or current_claim()
    if active_claim is None:
        return None
    initialize_task_queue()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT success_checkpoint_json, queued_run_json FROM v2_tasks
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (active_claim.task_id, active_claim.worker_id, active_claim.claim_token),
        ).fetchone()
    if row is None:
        raise StaleTaskClaim("The V2 task claim was superseded before success checkpoint recovery.")
    raw = row["success_checkpoint_json"]
    if not raw:
        return None
    try:
        expected_snapshot = CreativeRun.model_validate(_json_loads(row["queued_run_json"]))
        recovered = _decode_success_checkpoint(raw, expected_snapshot=expected_snapshot)
        if recovered.run_id != active_claim.run_id:
            raise ValueError("The V2 task success checkpoint does not belong to the claimed run.")
    except StaleTaskClaim:
        raise
    except Exception as exc:
        raise InvalidSuccessCheckpoint(type(exc).__name__) from exc
    return recovered


def terminalize_invalid_success_checkpoint(claim: QueuedTask, error: InvalidSuccessCheckpoint) -> bool:
    """Quarantine corrupt success evidence without retrying or rewriting it."""

    now = utc_now().isoformat()
    error_json = _json_dumps(
        {
            "code": "success_checkpoint_recovery_failed",
            "message": str(error),
            "cause_type": error.cause_type,
            "retryable": False,
        }
    )
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'failed', error_json = ?, locked_by = NULL, locked_at = NULL,
                claim_token = NULL, not_before = NULL, updated_at = ?
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (error_json, now, claim.task_id, claim.worker_id, claim.claim_token),
        )
        conn.commit()
    return cursor.rowcount == 1


def restore_success_checkpoint(run: CreativeRun) -> CreativeRun:
    """Rehydrate in-memory V2 projections from a claim-fenced durable checkpoint."""

    from app.repositories import repository

    claim = current_claim()
    if claim is None or claim.run_id != run.run_id:
        raise StaleTaskClaim("A V2 success checkpoint can only be restored by its active task claim.")

    def restore() -> CreativeRun:
        for job in run.generation_jobs:
            repository.save_image_job(job)
        return repository.save_creative_run(run)

    return persist_claimed_operation(restore)


def claim_heartbeat_interval_seconds() -> float:
    return max(0.01, min(30.0, float(settings.task_queue_claim_timeout_seconds) / 3.0))


@contextmanager
def claim_heartbeat(claim: QueuedTask, *, interval_seconds: float | None = None) -> Iterator[threading.Event]:
    """Renew a claim through preflight, provider work, and terminal DB writes."""

    stop = threading.Event()
    lost = threading.Event()
    interval = max(0.01, float(interval_seconds or claim_heartbeat_interval_seconds()))

    def heartbeat_loop() -> None:
        while not stop.wait(interval):
            try:
                if not refresh_task_claim(claim):
                    lost.set()
                    return
            except sqlite3.OperationalError as exc:
                if "locked" not in str(exc).lower() and "busy" not in str(exc).lower():
                    logger.exception("V2 task claim heartbeat failed")
                continue
            except Exception:
                logger.exception("V2 task claim heartbeat failed")
                continue

    heartbeat = threading.Thread(
        target=heartbeat_loop,
        name=f"v2-task-claim-{claim.task_id[-8:]}",
        daemon=True,
    )
    heartbeat.start()
    token: Token[QueuedTask | None] = _CURRENT_CLAIM.set(claim)
    try:
        yield lost
    finally:
        _CURRENT_CLAIM.reset(token)
        stop.set()
        heartbeat.join()


def release_task(claim: QueuedTask) -> bool:
    now = utc_now().isoformat()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'queued', locked_by = NULL, locked_at = NULL, claim_token = NULL,
                not_before = NULL, updated_at = ?
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (now, claim.task_id, claim.worker_id, claim.claim_token),
        )
        conn.commit()
    return cursor.rowcount == 1


def complete_task(claim: QueuedTask, run: CreativeRun) -> bool:
    now = utc_now().isoformat()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'completed', result_json = ?, error_json = NULL,
                success_checkpoint_json = NULL, locked_by = NULL, locked_at = NULL,
                claim_token = NULL, not_before = NULL, updated_at = ?
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (_json_dumps(run.model_dump(mode="json")), now, claim.task_id, claim.worker_id, claim.claim_token),
        )
        conn.commit()
    return cursor.rowcount == 1


def update_task_snapshot(run: CreativeRun, *, claim: QueuedTask | None = None) -> bool:
    active_claim = claim or _CURRENT_CLAIM.get()
    if active_claim is None:
        return False
    now = utc_now().isoformat()
    with _connect() as conn:
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET queued_run_json = ?, updated_at = ?
            WHERE task_id = ? AND run_id = ? AND status = 'running'
              AND locked_by = ? AND claim_token = ?
            """,
            (
                _json_dumps(run.model_dump(mode="json")),
                now,
                active_claim.task_id,
                run.run_id,
                active_claim.worker_id,
                active_claim.claim_token,
            ),
        )
        return conn.total_changes == 1


def fail_task(claim: QueuedTask, error: str, run: CreativeRun | None = None) -> bool:
    now = utc_now().isoformat()
    run_json = _json_dumps(run.model_dump(mode="json")) if run else None
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT attempts, max_attempts FROM v2_tasks
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (claim.task_id, claim.worker_id, claim.claim_token),
        ).fetchone()
        if row is None:
            conn.commit()
            return False
        can_retry = int(row["attempts"]) < int(row["max_attempts"])
        status = "queued" if can_retry else "failed"
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET status = ?, queued_run_json = CASE WHEN ? = 'queued' THEN COALESCE(?, queued_run_json) ELSE queued_run_json END,
                result_json = CASE WHEN ? = 'failed' THEN COALESCE(?, result_json) ELSE NULL END,
                error_json = ?, locked_by = NULL, locked_at = NULL, claim_token = NULL,
                not_before = NULL, updated_at = ?
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (
                status,
                status,
                run_json,
                status,
                run_json,
                _json_dumps({"message": error, "retryable": can_retry}),
                now,
                claim.task_id,
                claim.worker_id,
                claim.claim_token,
            ),
        )
        conn.commit()
    return cursor.rowcount == 1


def retry_task(
    claim: QueuedTask,
    error: str,
    run: CreativeRun,
    *,
    retry_delay_seconds: float,
    consume_attempt: bool = False,
) -> bool:
    now_dt = utc_now()
    now = now_dt.isoformat()
    delay = max(0.0, float(retry_delay_seconds))
    not_before = (now_dt + timedelta(seconds=delay)).isoformat() if delay else None
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT attempts, max_attempts FROM v2_tasks
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (claim.task_id, claim.worker_id, claim.claim_token),
        ).fetchone()
        if row is None:
            conn.commit()
            return False
        attempts = int(row["attempts"])
        if not consume_attempt:
            attempts = max(0, attempts - 1)
        can_retry = (attempts < int(row["max_attempts"])) or not consume_attempt
        if not can_retry:
            cursor = conn.execute(
                """
                UPDATE v2_tasks
                SET status = 'failed', attempts = ?, result_json = ?, error_json = ?,
                    locked_by = NULL, locked_at = NULL, claim_token = NULL, not_before = NULL, updated_at = ?
                WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
                """,
                (
                    attempts,
                    _json_dumps(run.model_dump(mode="json")),
                    _json_dumps({"message": error, "retryable": False}),
                    now,
                    claim.task_id,
                    claim.worker_id,
                    claim.claim_token,
                ),
            )
            conn.commit()
            return cursor.rowcount == 1
        cursor = conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'queued', attempts = ?, queued_run_json = ?, result_json = NULL, error_json = ?,
                locked_by = NULL, locked_at = NULL, claim_token = NULL, not_before = ?, updated_at = ?
            WHERE task_id = ? AND status = 'running' AND locked_by = ? AND claim_token = ?
            """,
            (
                attempts,
                _json_dumps(run.model_dump(mode="json")),
                _json_dumps(
                    {
                        "message": error,
                        "retryable": True,
                        "retry_after_seconds": delay,
                        "next_retry_at": not_before,
                    }
                ),
                not_before,
                now,
                claim.task_id,
                claim.worker_id,
                claim.claim_token,
            ),
        )
        conn.commit()
    return cursor.rowcount == 1


def get_run_snapshot(run_id: str) -> CreativeRun | None:
    initialize_task_queue()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT status, queued_run_json, result_json, success_checkpoint_json, error_json
            FROM v2_tasks WHERE run_id = ? ORDER BY created_at DESC LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    queued_payload = _json_loads(row["queued_run_json"])
    if row["result_json"]:
        payload = _json_loads(row["result_json"])
    elif row["success_checkpoint_json"]:
        try:
            expected_snapshot = CreativeRun.model_validate(queued_payload)
            payload = _decode_success_checkpoint(
                row["success_checkpoint_json"],
                expected_snapshot=expected_snapshot,
            ).model_dump(mode="json")
        except Exception:
            payload = queued_payload
    else:
        payload = queued_payload
    if row["status"] == "failed" and not row["result_json"]:
        error = _json_loads(row["error_json"]) if row["error_json"] else {}
        payload = {
            **payload,
            "status": "failed",
            "next_actions": [error.get("message") or "Queued task failed."],
            "updated_at": utc_now().isoformat(),
        }
    try:
        return CreativeRun.model_validate(payload)
    except Exception:
        return None


def task_queue_stats() -> dict[str, Any]:
    initialize_task_queue()
    with _connect() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS count FROM v2_tasks GROUP BY status").fetchall()
        oldest = conn.execute(
            "SELECT created_at FROM v2_tasks WHERE status IN ('queued', 'running') ORDER BY created_at ASC LIMIT 1"
        ).fetchone()
    return {
        "db_path": str(settings.task_queue_db_path),
        "inline_worker_enabled": settings.task_queue_inline_worker_enabled,
        "counts": {str(row["status"]): int(row["count"]) for row in rows},
        "oldest_active_task_at": oldest["created_at"] if oldest else None,
    }


def clear_task_queue() -> None:
    if settings.task_queue_db_path.exists():
        settings.task_queue_db_path.unlink()
    initialize_task_queue()


@contextmanager
def claimed_task(claim: QueuedTask) -> Iterator[None]:
    token = _CURRENT_CLAIM.set(claim)
    try:
        yield
    finally:
        _CURRENT_CLAIM.reset(token)


def _connect() -> sqlite3.Connection:
    timeout = max(0.1, min(30.0, float(settings.task_queue_busy_timeout_seconds)))
    conn = sqlite3.connect(Path(settings.task_queue_db_path), timeout=timeout, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn


def _ensure_wal_mode(conn: sqlite3.Connection) -> int:
    """Switch a newly created or legacy queue database to WAL once, before transactions."""

    if conn.in_transaction:
        raise RuntimeError("V2 queue journal mode must be configured outside a transaction.")

    timeout = max(0.1, min(30.0, float(settings.task_queue_busy_timeout_seconds)))
    deadline = time.monotonic() + timeout
    retry_loops = 0

    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise QueueStorageBusy(
                f"V2 queue database is busy; WAL setup timed out after {timeout:.2f}s "
                f"(retry_loops={retry_loops})."
            )

        conn.execute(f"PRAGMA busy_timeout={max(1, int(remaining * 1000))}")
        try:
            mode = str(conn.execute("PRAGMA journal_mode").fetchone()[0]).lower()
            if mode == "wal":
                break

            remaining = deadline - time.monotonic()
            if remaining <= 0:
                continue
            conn.execute(f"PRAGMA busy_timeout={max(1, int(remaining * 1000))}")
            mode = str(conn.execute("PRAGMA journal_mode=WAL").fetchone()[0]).lower()
            if mode == "wal":
                break
        except sqlite3.OperationalError as exc:
            message = str(exc).lower()
            if "locked" not in message and "busy" not in message:
                raise
            if time.monotonic() >= deadline:
                retry_loops += 1
                raise QueueStorageBusy(
                    f"V2 queue database is busy; WAL setup timed out after {timeout:.2f}s "
                    f"(retry_loops={retry_loops})."
                ) from exc

        retry_loops += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise QueueStorageBusy(
                f"V2 queue database is busy; WAL setup timed out after {timeout:.2f}s "
                f"(retry_loops={retry_loops})."
            )
        time.sleep(min(0.025, remaining))

    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return retry_loops


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(str(row["name"]) == column for row in rows):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _encode_success_checkpoint(run: CreativeRun) -> str:
    return _json_dumps(
        {
            "version": _SUCCESS_CHECKPOINT_VERSION,
            "generation_job_ids": [job.job_id for job in run.generation_jobs],
            "generation_output_ids": {
                job.job_id: [output.output_id for output in job.outputs]
                for job in run.generation_jobs
            },
            "run": run.model_dump(mode="json"),
        }
    )


def _decode_success_checkpoint(
    raw: str | bytes,
    *,
    expected_snapshot: CreativeRun | None = None,
) -> CreativeRun:
    payload = _json_loads(raw)
    if payload.get("version") != _SUCCESS_CHECKPOINT_VERSION:
        raise ValueError("The V2 task success checkpoint version is missing or unsupported.")
    expected_job_ids = payload.get("generation_job_ids")
    if (
        not isinstance(expected_job_ids, list)
        or not expected_job_ids
        or any(not isinstance(job_id, str) for job_id in expected_job_ids)
        or len(set(expected_job_ids)) != len(expected_job_ids)
    ):
        raise ValueError("The V2 task success checkpoint has no complete generation-job manifest.")
    expected_output_ids = payload.get("generation_output_ids")
    if not isinstance(expected_output_ids, dict):
        raise ValueError("The V2 task success checkpoint has no complete generation-output manifest.")
    run_payload = payload.get("run")
    if not isinstance(run_payload, dict):
        raise ValueError("The V2 task success checkpoint has no run result.")
    recovered = CreativeRun.model_validate(run_payload)
    actual_job_ids = [job.job_id for job in recovered.generation_jobs]
    if actual_job_ids != expected_job_ids:
        raise ValueError("The V2 task success checkpoint generation-job manifest does not match the result.")
    actual_output_ids = {
        job.job_id: [output.output_id for output in job.outputs]
        for job in recovered.generation_jobs
    }
    if actual_output_ids != expected_output_ids:
        raise ValueError("The V2 task success checkpoint generation-output manifest does not match the result.")
    _validate_success_checkpoint_run(recovered, expected_snapshot=expected_snapshot)
    return recovered


def _validate_success_checkpoint_run(
    run: CreativeRun,
    *,
    expected_snapshot: CreativeRun | None = None,
) -> None:
    if run.status != "completed" or not run.generation_jobs:
        raise ValueError("The V2 task success checkpoint is incomplete and cannot be recovered as success.")
    job_ids = [job.job_id for job in run.generation_jobs]
    if len(set(job_ids)) != len(job_ids):
        raise ValueError("The V2 task success checkpoint contains duplicate generation jobs.")
    if any(job.status != "completed" for job in run.generation_jobs):
        raise ValueError("The V2 task success checkpoint contains an unfinished generation job.")
    if any(job.run_id != run.run_id for job in run.generation_jobs):
        raise ValueError("The V2 task success checkpoint contains a job from another run.")
    output_ids: list[str] = []
    for job in run.generation_jobs:
        for output in job.outputs:
            if output.job_id != job.job_id:
                raise ValueError("The V2 task success checkpoint contains an output from another job.")
            output_ids.append(output.output_id)
    if len(set(output_ids)) != len(output_ids):
        raise ValueError("The V2 task success checkpoint contains duplicate output IDs.")
    if expected_snapshot is not None:
        if expected_snapshot.run_id != run.run_id:
            raise ValueError("The V2 task success checkpoint does not match the queued run snapshot.")
        expected_ids = [job.job_id for job in expected_snapshot.generation_jobs]
        if not expected_ids or len(set(expected_ids)) != len(expected_ids) or job_ids != expected_ids:
            raise ValueError(
                "The V2 task success checkpoint job manifest does not match the authoritative queued run snapshot."
            )


def _json_loads(payload: str | bytes | None) -> dict[str, Any]:
    if not payload:
        return {}
    parsed = json.loads(payload)
    return parsed if isinstance(parsed, dict) else {}
