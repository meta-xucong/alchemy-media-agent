from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.schemas import GenerationJob, GenerationOutput, Session


@dataclass
class MemoryRepository:
    sessions: dict[str, Session] = field(default_factory=dict)
    assets: dict[str, Any] = field(default_factory=dict)
    jobs: dict[str, GenerationJob] = field(default_factory=dict)
    outputs: dict[str, GenerationOutput] = field(default_factory=dict)
    idempotency_index: dict[str, str] = field(default_factory=dict)
    video_requests: dict[str, dict[str, Any]] = field(default_factory=dict)
    events_by_session: dict[str, list[dict[str, Any]]] = field(default_factory=dict)

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
        self.jobs[job.id] = job
        if job.idempotency_key:
            self.idempotency_index[job.idempotency_key] = job.id
        for output in job.outputs:
            self.outputs[output.id] = output
        return job

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self.jobs.get(job_id)

    def list_jobs(self, *, job_type: str | None = None, session_id: str | None = None) -> list[GenerationJob]:
        jobs = list(self.jobs.values())
        if job_type:
            jobs = [job for job in jobs if job.job_type == job_type]
        if session_id:
            jobs = [job for job in jobs if job.session_id == session_id]
        return sorted(jobs, key=lambda job: job.updated_at or job.created_at, reverse=True)

    def get_job_by_idempotency_key(self, idempotency_key: str | None) -> GenerationJob | None:
        if not idempotency_key:
            return None
        job_id = self.idempotency_index.get(idempotency_key)
        return self.jobs.get(job_id) if job_id else None

    def get_output(self, output_id: str) -> GenerationOutput | None:
        return self.outputs.get(output_id)

    def delete_output(self, output_id: str) -> GenerationOutput | None:
        output = self.outputs.pop(output_id, None)
        if not output:
            return None
        job = self.jobs.get(output.job_id)
        if job:
            job.outputs = [item for item in job.outputs if item.id != output_id]
        return output

    def append_event(self, session_id: str | None, event_type: str, data: dict[str, Any]) -> None:
        if not session_id:
            return
        self.events_by_session.setdefault(session_id, []).append({"event": event_type, "data": data})

    def list_events(self, session_id: str) -> list[dict[str, Any]]:
        return list(self.events_by_session.get(session_id, []))

    def reset(self) -> None:
        self.sessions.clear()
        self.assets.clear()
        self.jobs.clear()
        self.outputs.clear()
        self.idempotency_index.clear()
        self.video_requests.clear()
        self.events_by_session.clear()


repository = MemoryRepository()
