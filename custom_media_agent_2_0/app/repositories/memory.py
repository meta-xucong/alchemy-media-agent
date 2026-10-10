from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.config import settings
from app.repositories.sqlite_json import SQLiteJsonMap, connect
from app.schemas import (
    CreativeRun,
    FeedbackEvent,
    ImageJob,
    ImageOutput,
    PromptCase,
    ProviderSyncRun,
    ResourceProvider,
    SafetyDecision,
    UploadedAsset,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InMemoryV2Repository:
    """Compatibility-named V2 repository backed by V2-owned durable SQLite."""

    _namespaces = (
        "providers", "sync_runs", "prompt_cases", "creative_runs", "image_jobs",
        "outputs", "uploaded_assets", "feedback_events", "safety_decisions",
    )

    def __init__(self, database_path: Path | None = None) -> None:
        self._database_path_override = Path(database_path) if database_path else None
        self.providers = self._map("providers", ResourceProvider)
        self.sync_runs = self._map("sync_runs", ProviderSyncRun)
        self.prompt_cases = self._map("prompt_cases", PromptCase, self._case_index)
        self.creative_runs = self._map("creative_runs", CreativeRun)
        self.image_jobs = self._map("image_jobs", ImageJob)
        self.outputs = self._map("outputs", ImageOutput)
        self.uploaded_assets = self._map("uploaded_assets", UploadedAsset)
        self.feedback_events = self._map("feedback_events", FeedbackEvent)
        self.safety_decisions = self._map("safety_decisions", SafetyDecision)

    @property
    def database_path(self) -> Path:
        return self._database_path_override or Path(settings.data_dir) / "repository.sqlite3"

    def _map(self, namespace: str, model: Any, index_fields=None) -> SQLiteJsonMap:
        return SQLiteJsonMap(
            lambda: self.database_path,
            namespace,
            validator=model.model_validate_json,
            index_fields=index_fields,
        )

    @staticmethod
    def _case_index(case: PromptCase) -> dict[str, Any]:
        return {
            "provider_id": case.provider_id,
            "active": int(case.is_active),
            "quality": case.quality_score,
            "index_version": case.index_version,
        }

    def reset(self) -> None:
        connection = connect(self.database_path)
        try:
            with connection:
                connection.executemany(
                    "DELETE FROM v2_records WHERE namespace=?",
                    [(namespace,) for namespace in self._namespaces],
                )
        finally:
            connection.close()

    def upsert_provider(self, provider: ResourceProvider) -> ResourceProvider:
        self.providers[provider.provider_id] = provider
        return provider

    def get_provider(self, provider_id: str) -> ResourceProvider | None:
        return self.providers.get(provider_id)

    def list_providers(self) -> list[ResourceProvider]:
        return sorted(self.providers.values(), key=lambda item: item.provider_id)

    def save_sync_run(self, run: ProviderSyncRun) -> ProviderSyncRun:
        self.sync_runs[run.sync_run_id] = run
        return run

    def get_sync_run(self, sync_run_id: str) -> ProviderSyncRun | None:
        return self.sync_runs.get(sync_run_id)

    def upsert_cases(self, cases: Iterable[PromptCase]) -> int:
        connection = connect(self.database_path)
        count = 0
        try:
            with connection:
                for case in cases:
                    self.prompt_cases.put_on(connection, case.case_id, case)
                    count += 1
        finally:
            connection.close()
        return count

    def replace_cases_for_provider(self, provider_id: str, cases: Iterable[PromptCase]) -> int:
        connection = connect(self.database_path)
        count = 0
        try:
            with connection:
                connection.execute(
                    "DELETE FROM v2_records WHERE namespace='prompt_cases' AND provider_id=?",
                    (provider_id,),
                )
                for case in cases:
                    self.prompt_cases.put_on(connection, case.case_id, case)
                    count += 1
        finally:
            connection.close()
        return count

    def list_cases(self, active_only: bool = True) -> list[PromptCase]:
        return self.prompt_cases.list_values(active_only=active_only)

    def get_case(self, case_id: str) -> PromptCase | None:
        return self.prompt_cases.get(case_id)

    def get_active_index_version(self) -> str | None:
        versions = self.prompt_cases.active_index_versions()
        return versions[-1] if versions else None

    def save_safety_decision(self, decision: SafetyDecision) -> SafetyDecision:
        self.safety_decisions[decision.decision_id] = decision
        return decision

    def save_creative_run(self, run: CreativeRun) -> CreativeRun:
        self.creative_runs[run.run_id] = run
        return run

    def get_creative_run(self, run_id: str) -> CreativeRun | None:
        return self.creative_runs.get(run_id)

    def save_image_job(self, job: ImageJob) -> ImageJob:
        connection = connect(self.database_path)
        try:
            with connection:
                self.image_jobs.put_on(connection, job.job_id, job)
                for output in job.outputs:
                    self.outputs.put_on(connection, output.output_id, output)
        finally:
            connection.close()
        return job

    def get_image_job(self, job_id: str) -> ImageJob | None:
        return self.image_jobs.get(job_id)

    def delete_image_job(self, job_id: str) -> ImageJob | None:
        """Remove only an uncommitted running job, atomically with its check."""
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            payload = self.image_jobs.get_json_on(connection, job_id)
            job = ImageJob.model_validate_json(payload) if payload else None
            if job is None or job.status != "running" or job.outputs:
                connection.commit()
                return None
            self.image_jobs.delete_on(connection, job_id)
            connection.commit()
            return job
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def get_output(self, output_id: str) -> ImageOutput | None:
        return self.outputs.get(output_id)

    def delete_output(self, output_id: str) -> ImageOutput | None:
        connection = connect(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            output_payload = self.outputs.get_json_on(connection, output_id)
            if output_payload is None:
                connection.commit()
                return None
            output = ImageOutput.model_validate_json(output_payload)
            job_payload = self.image_jobs.get_json_on(connection, output.job_id)
            self.outputs.delete_on(connection, output_id)
            if job_payload:
                job = ImageJob.model_validate_json(job_payload)
                updated = [item for item in job.outputs if item.output_id != output_id]
                job = job.model_copy(update={"outputs": updated, "updated_at": utc_now()})
                self.image_jobs.put_on(connection, job.job_id, job)
            connection.commit()
            return output
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def save_uploaded_asset(self, asset: UploadedAsset) -> UploadedAsset:
        self.uploaded_assets[asset.asset_id] = asset
        return asset

    def get_uploaded_asset(self, asset_id: str) -> UploadedAsset | None:
        return self.uploaded_assets.get(asset_id)

    def save_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        connection = connect(self.database_path)
        try:
            with connection:
                self.feedback_events.put_on(connection, event.feedback_id, event)
                if event.feedback_type == "selected":
                    output_payload = self.outputs.get_json_on(connection, event.output_id)
                    if output_payload:
                        output = ImageOutput.model_validate_json(output_payload)
                        output = output.model_copy(update={"selected_by_user": True})
                        self.outputs.put_on(connection, output.output_id, output)
                        job_payload = self.image_jobs.get_json_on(connection, output.job_id)
                        if job_payload:
                            job = ImageJob.model_validate_json(job_payload)
                            updated = [
                                output if item.output_id == output.output_id else item
                                for item in job.outputs
                            ]
                            job = job.model_copy(update={"outputs": updated, "updated_at": utc_now()})
                            self.image_jobs.put_on(connection, job.job_id, job)
        finally:
            connection.close()
        return event


repository = InMemoryV2Repository()
