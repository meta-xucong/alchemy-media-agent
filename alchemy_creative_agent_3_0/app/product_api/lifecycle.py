"""Storage-ready lifecycle records for V3 product jobs."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..schemas.models import V3BaseModel


class JobRecord(V3BaseModel):
    job_id: str
    scenario_id: str | None = None
    status: str
    user_input: str
    brand_id: str | None = None
    run_ids: list[str] = Field(default_factory=list)
    selection_ids: list[str] = Field(default_factory=list)
    revision_ids: list[str] = Field(default_factory=list)
    export_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunRecord(V3BaseModel):
    run_id: str
    job_id: str
    status: str
    planning_result_id: str | None = None
    generation_result_id: str | None = None
    candidate_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateRecord(V3BaseModel):
    candidate_id: str
    job_id: str
    run_id: str
    asset_id: str
    status: str
    preview_uri: str | None = None
    overall_score: float | None = None
    recommendation: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CandidateSelectionRecord(V3BaseModel):
    selection_id: str
    job_id: str
    selected_candidate_ids: list[str] = Field(default_factory=list)
    selected_asset_ids: list[str] = Field(default_factory=list)
    memory_update_applied: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class RevisionRecord(V3BaseModel):
    revision_id: str
    job_id: str
    source_candidate_id: str | None = None
    instruction: str | None = None
    status: str = "not_requested"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExportRecord(V3BaseModel):
    export_id: str
    job_id: str
    target: str
    asset_ids: list[str] = Field(default_factory=list)
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobLifecycleRecord(V3BaseModel):
    job: JobRecord
    runs: list[RunRecord] = Field(default_factory=list)
    candidates: list[CandidateRecord] = Field(default_factory=list)
    selections: list[CandidateSelectionRecord] = Field(default_factory=list)
    revisions: list[RevisionRecord] = Field(default_factory=list)
    exports: list[ExportRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
