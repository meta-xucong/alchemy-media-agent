from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator

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


class QueueCapacityExceeded(RuntimeError):
    """Raised when the durable V2 queue has no pending capacity."""


class QueueStorageBusy(RuntimeError):
    """Raised when bounded queue persistence is saturated or locked."""


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


def initialize_task_queue() -> None:
    settings.task_queue_db_path.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
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
                claim_generation INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        _ensure_column(conn, "v2_tasks", "not_before", "TEXT")
        _ensure_column(conn, "v2_tasks", "claim_token", "TEXT")
        _ensure_column(conn, "v2_tasks", "claim_generation", "INTEGER NOT NULL DEFAULT 0")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_tasks_run_id ON v2_tasks(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_tasks_status_created ON v2_tasks(status, created_at)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_v2_tasks_status_not_before_created ON v2_tasks(status, not_before, created_at)"
        )


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
                    AND attempts < max_attempts
                )
            ORDER BY created_at ASC
            LIMIT 1
            """,
            (now_text, stale_before),
        ).fetchone()
        if row is None:
            conn.commit()
            return None

        attempts = int(row["attempts"]) + 1
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
                locked_by = NULL, locked_at = NULL, claim_token = NULL, not_before = NULL, updated_at = ?
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
            SELECT status, queued_run_json, result_json, error_json
            FROM v2_tasks WHERE run_id = ? ORDER BY created_at DESC LIMIT 1
            """,
            (run_id,),
        ).fetchone()
    if row is None:
        return None
    raw = row["result_json"] or row["queued_run_json"]
    payload = _json_loads(raw)
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
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(f"PRAGMA busy_timeout={int(timeout * 1000)}")
    return conn


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, column_type: str) -> None:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    if any(str(row["name"]) == column for row in rows):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def _json_dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_loads(payload: str | bytes | None) -> dict[str, Any]:
    if not payload:
        return {}
    parsed = json.loads(payload)
    return parsed if isinstance(parsed, dict) else {}
