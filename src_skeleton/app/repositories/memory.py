from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator
from datetime import datetime, timezone

from app.repositories.sqlite_json import SQLiteJsonMap, connect
from app.schemas import Asset, GenerationJob, GenerationOutput, JobStatus, ProviderError, Session


class MemoryRepository:
    """Compatibility-named V1 repository backed by SQLite, not process memory."""

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path_override = Path(database_path) if database_path else None
        jobs = self._record_map("jobs", GenerationJob, self._job_index)
        self.sessions = self._record_map("sessions", Session)
        self.assets = self._record_map("assets", Asset)
        self.jobs = jobs
        self.outputs = self._record_map("outputs", GenerationOutput)
        self.idempotency_index = self._record_map("idempotency", str)

    @property
    def database_path(self) -> Path:
        if self._database_path_override is not None:
            return self._database_path_override
        # Import lazily to avoid a repository -> storage -> application import cycle.
        from app.storage import media_store

        return Path(media_store.root) / "repository.sqlite3"

    def _record_map(self, namespace: str, model: Any, index_fields=None) -> SQLiteJsonMap:
        def validate(payload: str):
            if model is str:
                return json.loads(payload)
            return model.model_validate_json(payload)

        return SQLiteJsonMap(
            lambda: self.database_path,
            namespace,
            validator=validate,
            index_fields=index_fields,
        )

    @staticmethod
    def _job_index(job: GenerationJob) -> dict[str, str | None]:
        return {
            "session_id": job.session_id,
            "job_type": job.job_type,
            "sort_at": job.updated_at or job.created_at,
            "idempotency_key": job.idempotency_key,
        }

    def save_session(self, session: Session) -> Session:
        self.sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self.sessions.get(session_id)

    def save_asset(self, asset) -> Any:
        self.assets[asset.id] = asset
        return asset

    def get_asset(self, asset_id: str) -> Any | None:
        return self.assets.get(asset_id)

    def save_job(self, job: GenerationJob) -> GenerationJob:
        connection = connect(self.database_path)
        try:
            with connection:
                self.jobs.put_on(connection, job.id, job)
                for output in job.outputs:
                    self.outputs.put_on(connection, output.id, output)
                if job.idempotency_key:
                    self.idempotency_index.put_on(connection, job.idempotency_key, job.id)
        finally:
            connection.close()
        return job

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self.jobs.get(job_id)

    def list_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> list[GenerationJob]:
        return self.jobs.list_jobs(job_type=job_type, session_id=session_id)

    def iter_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> Iterator[GenerationJob]:
        yield from self.jobs.iter_jobs(job_type=job_type, session_id=session_id)

    def get_job_by_idempotency_key(self, idempotency_key: str | None) -> GenerationJob | None:
        if not idempotency_key:
            return None
        job_id = self.idempotency_index.get(idempotency_key)
        return self.jobs.get(job_id) if job_id else self.jobs.get_job_by_idempotency_key(idempotency_key)

    def get_output(self, output_id: str) -> GenerationOutput | None:
        return self.outputs.get(output_id)

    def delete_output(self, output_id: str) -> GenerationOutput | None:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            output_json = self.outputs.get_record_json_on(connection, output_id)
            if output_json is None:
                connection.commit()
                return None
            output = GenerationOutput.model_validate_json(output_json)
            job_json = self.jobs.get_record_json_on(connection, output.job_id)
            self.outputs.delete_on(connection, output_id)
            if job_json:
                job = GenerationJob.model_validate_json(job_json)
                job.outputs = [item for item in job.outputs if item.id != output_id]
                self.jobs.put_on(connection, job.id, job)
            connection.commit()
            return output
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def recover_interrupted_jobs(self, *, batch_size: int = 128) -> int:
        active_statuses = (
            JobStatus.created.value,
            JobStatus.queued.value,
            JobStatus.planning.value,
            JobStatus.safety_check.value,
            JobStatus.generating.value,
            JobStatus.postprocessing.value,
            JobStatus.evaluating.value,
            JobStatus.processing.value,
            JobStatus.submitted.value,
        )
        recovered = 0
        while True:
            connection = connect(self.database_path)
            try:
                connection.execute("BEGIN IMMEDIATE")
                placeholders = ",".join("?" for _ in active_statuses)
                rows = connection.execute(
                    "SELECT record_key, payload FROM v1_records "
                    f"WHERE namespace='jobs' AND json_extract(payload, '$.status') IN ({placeholders}) "
                    "ORDER BY rowid LIMIT ?",
                    (*active_statuses, max(1, int(batch_size))),
                ).fetchall()
                if not rows:
                    connection.commit()
                    return recovered
                for row in rows:
                    job = GenerationJob.model_validate_json(row["payload"])
                    job.status = JobStatus.failed
                    job.error = ProviderError(
                        code="worker_interrupted",
                        message="The server restarted before this generation completed. It was not replayed automatically; submit a new request to retry.",
                        retryable=False,
                        detail={"recovery": "process_restart", "automatic_provider_replay": False},
                    )
                    job.updated_at = datetime.now(timezone.utc).isoformat()
                    self.jobs.put_on(connection, job.id, job)
                    recovered += 1
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

    def append_event(self, session_id: str | None, event_type: str, data: dict[str, Any]) -> None:
        if not session_id:
            return
        connection = connect(self.database_path)
        try:
            with connection:
                connection.execute(
                    "INSERT INTO v1_events(session_id, event_type, payload) VALUES(?, ?, ?)",
                    (session_id, event_type, json.dumps(data, ensure_ascii=False, separators=(",", ":"))),
                )
        finally:
            connection.close()

    def iter_events(self, session_id: str):
        connection = connect(self.database_path)
        try:
            row = connection.execute(
                "SELECT COALESCE(MAX(event_id), 0) FROM v1_events WHERE session_id=?",
                (session_id,),
            ).fetchone()
            upper_event_id = int(row[0] or 0)
        finally:
            connection.close()

        last_event_id = 0
        batch_size = 128
        while last_event_id < upper_event_id:
            connection = connect(self.database_path)
            try:
                rows = connection.execute(
                    "SELECT event_id, event_type, payload FROM v1_events "
                    "WHERE session_id=? AND event_id>? AND event_id<=? "
                    "ORDER BY event_id LIMIT ?",
                    (session_id, last_event_id, upper_event_id, batch_size),
                ).fetchall()
            finally:
                connection.close()
            if not rows:
                return
            events = [
                (int(row["event_id"]), {"event": row["event_type"], "data": json.loads(row["payload"])})
                for row in rows
            ]
            for event_id, event in events:
                last_event_id = event_id
                yield event

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return list(self.iter_events(session_id))

    def reset(self) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                connection.execute(
                    "DELETE FROM v1_records WHERE namespace IN (?, ?, ?, ?, ?)",
                    ("sessions", "assets", "jobs", "outputs", "idempotency"),
                )
                connection.execute("DELETE FROM v1_events")
        finally:
            connection.close()


repository = MemoryRepository()
