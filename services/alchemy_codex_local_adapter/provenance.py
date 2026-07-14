"""Immutable public-safe provenance for Doc117 Local Mode artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .contracts import (
    LOCAL_CREATIVE_DIRECTION_OWNER,
    LOCAL_EVIDENCE_SCOPE,
    LOCAL_EXECUTION_CHANNEL,
    LOCAL_RENDERER,
)


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def local_job_provenance(*, job_id: str, project_id: str) -> dict[str, Any]:
    return {
        "execution_channel": LOCAL_EXECUTION_CHANNEL,
        "creative_direction_owner": LOCAL_CREATIVE_DIRECTION_OWNER,
        "creative_direction_source": "recorded_local_agent_direction",
        "renderer": LOCAL_RENDERER,
        "fallback_used": False,
        "evidence_scope": LOCAL_EVIDENCE_SCOPE,
        "job_id": job_id,
        "project_id": project_id,
        "created_at": utc_now_iso(),
    }


def imported_artifact_provenance(
    *,
    job_id: str,
    project_id: str,
    role_id: str,
    sha256: str,
    declared_origin: str,
    codex_run_id: str | None,
) -> dict[str, Any]:
    """Return provenance without inventing a provider model or API route."""

    result = local_job_provenance(job_id=job_id, project_id=project_id)
    result.update(
        {
            "artifact_origin": declared_origin,
            "artifact_materialization": "local_file_copy",
            "artifact_sha256": f"sha256:{sha256}",
            "role_id": role_id,
            "certification_state": "not_certified_phase_a_b",
            "imported_at": utc_now_iso(),
        }
    )
    if codex_run_id:
        result["opaque_codex_run_id"] = codex_run_id
    return result
