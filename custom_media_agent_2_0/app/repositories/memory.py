from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

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
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.providers: dict[str, ResourceProvider] = {}
        self.sync_runs: dict[str, ProviderSyncRun] = {}
        self.prompt_cases: dict[str, PromptCase] = {}
        self.creative_runs: dict[str, CreativeRun] = {}
        self.image_jobs: dict[str, ImageJob] = {}
        self.outputs: dict[str, ImageOutput] = {}
        self.uploaded_assets: dict[str, UploadedAsset] = {}
        self.feedback_events: dict[str, FeedbackEvent] = {}
        self.safety_decisions: dict[str, SafetyDecision] = {}

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
        count = 0
        for case in cases:
            self.prompt_cases[case.case_id] = case
            count += 1
        return count

    def replace_cases_for_provider(self, provider_id: str, cases: Iterable[PromptCase]) -> int:
        self.prompt_cases = {
            case_id: case
            for case_id, case in self.prompt_cases.items()
            if case.provider_id != provider_id
        }
        return self.upsert_cases(cases)

    def list_cases(self, active_only: bool = True) -> list[PromptCase]:
        cases = list(self.prompt_cases.values())
        if active_only:
            cases = [case for case in cases if case.is_active]
        return sorted(cases, key=lambda item: (-item.quality_score, item.case_id))

    def get_case(self, case_id: str) -> PromptCase | None:
        return self.prompt_cases.get(case_id)

    def get_active_index_version(self) -> str | None:
        versions = {case.index_version for case in self.prompt_cases.values() if case.is_active}
        return sorted(versions)[-1] if versions else None

    def save_safety_decision(self, decision: SafetyDecision) -> SafetyDecision:
        self.safety_decisions[decision.decision_id] = decision
        return decision

    def save_creative_run(self, run: CreativeRun) -> CreativeRun:
        self.creative_runs[run.run_id] = run
        return run

    def get_creative_run(self, run_id: str) -> CreativeRun | None:
        return self.creative_runs.get(run_id)

    def save_image_job(self, job: ImageJob) -> ImageJob:
        self.image_jobs[job.job_id] = job
        for output in job.outputs:
            self.outputs[output.output_id] = output
        return job

    def get_image_job(self, job_id: str) -> ImageJob | None:
        return self.image_jobs.get(job_id)

    def get_output(self, output_id: str) -> ImageOutput | None:
        return self.outputs.get(output_id)

    def delete_output(self, output_id: str) -> ImageOutput | None:
        output = self.outputs.pop(output_id, None)
        if output:
            job = self.image_jobs.get(output.job_id)
            if job:
                kept_outputs = [item for item in job.outputs if item.output_id != output_id]
                self.image_jobs[job.job_id] = job.model_copy(update={"outputs": kept_outputs, "updated_at": utc_now()})
        return output

    def save_uploaded_asset(self, asset: UploadedAsset) -> UploadedAsset:
        self.uploaded_assets[asset.asset_id] = asset
        return asset

    def get_uploaded_asset(self, asset_id: str) -> UploadedAsset | None:
        return self.uploaded_assets.get(asset_id)

    def save_feedback(self, event: FeedbackEvent) -> FeedbackEvent:
        self.feedback_events[event.feedback_id] = event
        if event.feedback_type == "selected" and event.output_id in self.outputs:
            output = self.outputs[event.output_id]
            self.outputs[event.output_id] = output.model_copy(update={"selected_by_user": True})
            job = self.image_jobs.get(output.job_id)
            if job:
                updated_outputs = [
                    self.outputs[item.output_id] if item.output_id == event.output_id else item
                    for item in job.outputs
                ]
                self.image_jobs[job.job_id] = job.model_copy(update={"outputs": updated_outputs, "updated_at": utc_now()})
        return event


repository = InMemoryV2Repository()
