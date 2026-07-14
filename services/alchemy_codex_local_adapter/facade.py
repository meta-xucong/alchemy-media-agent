"""Explicit interactive facade for the Doc117 local adapter.

The facade deliberately stops before shared review/finalization.  Providing a
locally invented verdict would violate the shared runtime boundary, so those
methods fail closed until Phase C performs the approved integration.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .artifact_import import LocalArtifactImporter
from .contracts import (
    ImportedLocalCandidate,
    LocalJobSpec,
    LocalModeAdapterError,
    LocalModeDisabledError,
    _clean_direction,
)
from .platform_renderer import PlatformImageRenderer
from .provenance import local_job_provenance, utc_now_iso


_DEPRECATED_LOCAL_DIRECTION_TOKENS = (
    "copyrenderplan",
    "copy_render_plan",
    "local ocr",
    "canvas overlay",
    "html overlay",
    "svg overlay",
    "safe-area coordinates",
    "pixel coordinates",
    "local text renderer",
)


class CodexLocalExecutionFacade:
    """Local stdio adapter state; disabled until an interactive caller opts in."""

    def __init__(self, storage_root: str | Path, *, enabled: bool = False) -> None:
        self.storage_root = Path(storage_root).resolve()
        self.enabled = bool(enabled)
        self._jobs_path = self.storage_root / "local_jobs.json"
        self._artifact_importer = LocalArtifactImporter(self.storage_root)

    def create_local_job(self, spec: LocalJobSpec) -> dict[str, Any]:
        self._require_enabled()
        records = self._load_records()
        if spec.job_id in records:
            raise LocalModeAdapterError("codex_local_job_duplicate", "Local job already exists.")
        records[spec.job_id] = {
            "contract": spec.storage_record(),
            "provenance": local_job_provenance(job_id=spec.job_id, project_id=spec.project_id),
            "creative_directions": [],
            "candidates": [],
            "created_at": utc_now_iso(),
            "status": "awaiting_creative_direction",
        }
        self._save_records(records)
        return self.get_local_job_status(spec.job_id)

    def get_render_contract(self, job_id: str) -> dict[str, Any]:
        self._require_enabled()
        record = self._record_for(job_id)
        contract = LocalJobSpec.from_storage_record(dict(record.get("contract") or {}))
        return contract.safe_render_contract()

    def record_creative_direction(self, job_id: str, role_id: str, direction: str) -> dict[str, Any]:
        self._require_enabled()
        cleaned_direction = _clean_direction(direction)
        lowered = cleaned_direction.lower()
        if any(token in lowered for token in _DEPRECATED_LOCAL_DIRECTION_TOKENS):
            raise LocalModeAdapterError(
                "codex_local_deprecated_direction_structure",
                "Creative direction contains a prohibited local rendering structure.",
            )
        records = self._load_records()
        record = self._record_for(job_id, records)
        contract = LocalJobSpec.from_storage_record(dict(record.get("contract") or {}))
        if role_id not in contract.role_ids:
            raise LocalModeAdapterError("codex_local_role_binding_mismatch", "Creative direction role is not frozen for this job.")
        directions = list(record.get("creative_directions") or [])
        if any(str(item.get("role_id") or "") == role_id for item in directions if isinstance(item, dict)):
            raise LocalModeAdapterError("codex_local_direction_duplicate", "A creative direction is already recorded for this role.")
        directions.append(
            {
                "role_id": role_id,
                "direction": cleaned_direction,
                "creative_direction_owner": "codex_local_agent",
                "recorded_at": utc_now_iso(),
            }
        )
        record["creative_directions"] = directions
        record["status"] = "awaiting_materialized_artifact"
        self._save_records(records)
        return {"job_id": contract.job_id, "role_id": role_id, "recorded": True}

    def render_platform_candidate(
        self,
        job_id: str,
        role_id: str,
        *,
        renderer: PlatformImageRenderer,
    ) -> ImportedLocalCandidate:
        """Render/import one role through the explicitly selected Platform path."""

        self._require_enabled()
        records = self._load_records()
        record = self._record_for(job_id, records)
        contract = LocalJobSpec.from_storage_record(dict(record.get("contract") or {}))
        directions = list(record.get("creative_directions") or [])
        direction_entry = next(
            (item for item in directions if isinstance(item, dict) and str(item.get("role_id") or "") == role_id),
            None,
        )
        if direction_entry is None:
            raise LocalModeAdapterError("codex_local_direction_required", "Record a creative direction before importing an artifact.")
        rendered = renderer.render(direction=str(direction_entry.get("direction") or ""), role_id=role_id)
        staged = self._artifact_importer.stage_platform_response(rendered)
        candidate = self._artifact_importer.import_staged_platform_candidate(
            job_id=job_id,
            role_id=role_id,
            contract=contract,
            staged=staged,
        )
        candidates = list(record.get("candidates") or [])
        candidates.append(candidate.storage_record())
        record["candidates"] = candidates
        record["status"] = "imported_not_certified"
        self._save_records(records)
        return candidate

    def render_platform_candidates(
        self,
        job_id: str,
        role_ids: list[str],
        *,
        renderer: PlatformImageRenderer,
    ) -> list[ImportedLocalCandidate]:
        """Run exactly one bounded API request for each explicit frozen role."""

        if not role_ids or len(role_ids) != len(set(role_ids)):
            raise LocalModeAdapterError("codex_local_invalid_role_binding", "Platform render roles must be non-empty and unique.")
        return [self.render_platform_candidate(job_id, role_id, renderer=renderer) for role_id in role_ids]

    def import_generated_candidate(self, *_: Any, **__: Any) -> None:
        """Former Phase A path; never trust a caller-supplied artifact path."""

        self._require_enabled()
        self._artifact_importer.reject_uncontrolled_external_import()

    def get_local_job_status(self, job_id: str) -> dict[str, Any]:
        self._require_enabled()
        record = self._record_for(job_id)
        return {
            "job_id": job_id,
            "status": str(record.get("status") or "unknown"),
            "provenance": dict(record.get("provenance") or {}),
            "creative_directions": [
                {"role_id": item.get("role_id"), "recorded_at": item.get("recorded_at")}
                for item in record.get("creative_directions") or []
                if isinstance(item, dict)
            ],
            "candidates": [
                {
                    "candidate_id": item.get("candidate_id"),
                    "role_id": item.get("role_id"),
                    "sha256": item.get("sha256"),
                    "certification_state": "not_certified_development_artifact",
                }
                for item in record.get("candidates") or []
                if isinstance(item, dict)
            ],
            "final_deliveries": [],
            "certified_delivery": False,
            "next_permitted_action": "shared_runtime_integration_pending",
        }

    def review_candidate(self, job_id: str, candidate_id: str) -> None:
        self._require_enabled()
        self._record_for(job_id)
        raise LocalModeAdapterError(
            "codex_local_shared_runtime_integration_pending",
            "Shared review is not wired in the Phase A--B spike; no candidate can self-certify.",
        )

    def request_bounded_revision(self, job_id: str, candidate_id: str) -> None:
        self._require_enabled()
        self._record_for(job_id)
        raise LocalModeAdapterError(
            "codex_local_shared_runtime_integration_pending",
            "Shared retry is not wired in the Phase A--B spike.",
        )

    def finalize_local_job(self, job_id: str) -> None:
        self._require_enabled()
        self._record_for(job_id)
        raise LocalModeAdapterError(
            "codex_local_shared_runtime_integration_pending",
            "Shared final delivery is not wired in the Phase A--B spike.",
        )

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise LocalModeDisabledError()

    def _record_for(self, job_id: str, records: dict[str, Any] | None = None) -> dict[str, Any]:
        records = records if records is not None else self._load_records()
        record = records.get(str(job_id or ""))
        if not isinstance(record, dict):
            raise LocalModeAdapterError("codex_local_job_not_found", "Local job does not exist.")
        return record

    def _load_records(self) -> dict[str, Any]:
        if not self._jobs_path.exists():
            return {}
        try:
            payload = json.loads(self._jobs_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise LocalModeAdapterError("codex_local_job_store_unreadable", "Local job store is unreadable.") from exc
        if not isinstance(payload, dict):
            raise LocalModeAdapterError("codex_local_job_store_unreadable", "Local job store is invalid.")
        return payload

    def _save_records(self, records: dict[str, Any]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        temporary = self._jobs_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self._jobs_path)
