from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreativeRun
from app.services.ids import new_id


TaskStatus = str


@dataclass(frozen=True)
class QueuedTask:
    task_id: str
    kind: str
    run_id: str
    payload: dict[str, Any]
    attempts: int
    max_attempts: int


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
                updated_at TEXT NOT NULL
            )
            """
        )
        _ensure_column(conn, "v2_tasks", "not_before", "TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_tasks_run_id ON v2_tasks(run_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_v2_tasks_status_created ON v2_tasks(status, created_at)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_v2_tasks_status_not_before_created ON v2_tasks(status, not_before, created_at)"
        )


def enqueue_creative_task(*, kind: str, request_payload: dict[str, Any], queued_run: CreativeRun) -> str:
    initialize_task_queue()
    now = utc_now().isoformat()
    task_id = new_id("task")
    with _connect() as conn:
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
    return task_id


def claim_next_task(worker_id: str) -> QueuedTask | None:
    initialize_task_queue()
    now = utc_now()
    now_text = now.isoformat()
    stale_before = (now - timedelta(seconds=settings.task_queue_claim_timeout_seconds)).isoformat()
    with _connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM v2_tasks
            WHERE
                (
                    status = 'queued'
                    AND (not_before IS NULL OR not_before <= ?)
                )
                OR (
                    status = 'running'
                    AND locked_at IS NOT NULL
                    AND locked_at < ?
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
        conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'running', attempts = ?, locked_by = ?, locked_at = ?, not_before = NULL, updated_at = ?
            WHERE task_id = ?
            """,
            (attempts, worker_id, now_text, now_text, row["task_id"]),
        )
        conn.commit()
    return QueuedTask(
        task_id=str(row["task_id"]),
        kind=str(row["kind"]),
        run_id=str(row["run_id"]),
        payload=_json_loads(row["payload_json"]),
        attempts=attempts,
        max_attempts=int(row["max_attempts"]),
    )


def complete_task(task_id: str, run: CreativeRun) -> None:
    now = utc_now().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'completed', result_json = ?, error_json = NULL,
                locked_by = NULL, locked_at = NULL, not_before = NULL, updated_at = ?
            WHERE task_id = ?
            """,
            (_json_dumps(run.model_dump(mode="json")), now, task_id),
        )


def update_task_snapshot(run: CreativeRun) -> None:
    initialize_task_queue()
    now = utc_now().isoformat()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE v2_tasks
            SET queued_run_json = ?, updated_at = ?
            WHERE run_id = ? AND status IN ('queued', 'running')
            """,
            (_json_dumps(run.model_dump(mode="json")), now, run.run_id),
        )


def fail_task(task_id: str, error: str, run: CreativeRun | None = None) -> None:
    now = utc_now().isoformat()
    with _connect() as conn:
        row = conn.execute("SELECT attempts, max_attempts FROM v2_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return
        can_retry = int(row["attempts"]) < int(row["max_attempts"])
        status = "queued" if can_retry else "failed"
        run_json = _json_dumps(run.model_dump(mode="json")) if run else None
        if can_retry:
            conn.execute(
                """
                UPDATE v2_tasks
                SET status = ?, queued_run_json = COALESCE(?, queued_run_json), result_json = NULL, error_json = ?,
                    locked_by = NULL, locked_at = NULL, not_before = NULL, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    status,
                    run_json,
                    _json_dumps({"message": error, "retryable": True}),
                    now,
                    task_id,
                ),
            )
            return
        conn.execute(
            """
            UPDATE v2_tasks
            SET status = ?, result_json = COALESCE(?, result_json), error_json = ?,
                locked_by = NULL, locked_at = NULL, not_before = NULL, updated_at = ?
            WHERE task_id = ?
            """,
            (
                status,
                run_json,
                _json_dumps({"message": error, "retryable": False}),
                now,
                task_id,
            ),
        )


def retry_task(
    task_id: str,
    error: str,
    run: CreativeRun,
    *,
    retry_delay_seconds: float,
    consume_attempt: bool = False,
) -> None:
    now_dt = utc_now()
    now = now_dt.isoformat()
    delay = max(0.0, float(retry_delay_seconds))
    not_before = (now_dt + timedelta(seconds=delay)).isoformat() if delay else None
    with _connect() as conn:
        row = conn.execute("SELECT attempts, max_attempts FROM v2_tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return
        attempts = int(row["attempts"])
        if not consume_attempt:
            attempts = max(0, attempts - 1)
        can_retry = (attempts < int(row["max_attempts"])) or not consume_attempt
        if not can_retry:
            conn.execute(
                """
                UPDATE v2_tasks
                SET status = 'failed', attempts = ?, result_json = ?, error_json = ?,
                    locked_by = NULL, locked_at = NULL, not_before = NULL, updated_at = ?
                WHERE task_id = ?
                """,
                (
                    attempts,
                    _json_dumps(run.model_dump(mode="json")),
                    _json_dumps({"message": error, "retryable": False}),
                    now,
                    task_id,
                ),
            )
            return
        conn.execute(
            """
            UPDATE v2_tasks
            SET status = 'queued', attempts = ?, queued_run_json = ?, result_json = NULL, error_json = ?,
                locked_by = NULL, locked_at = NULL, not_before = ?, updated_at = ?
            WHERE task_id = ?
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
                task_id,
            ),
        )


def get_run_snapshot(run_id: str) -> CreativeRun | None:
    initialize_task_queue()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT status, queued_run_json, result_json, error_json
            FROM v2_tasks
            WHERE run_id = ?
            ORDER BY created_at DESC
            LIMIT 1
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


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(Path(settings.task_queue_db_path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
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
