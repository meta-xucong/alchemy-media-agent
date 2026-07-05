"""Resolve V3 generated outputs into inspectable local image records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..creative_core.rules import stable_id
from ..schemas import PackagedAsset, PlanningResult
from ..shared_capabilities.visual_cluster import GeneratedOutputResolution
from .outputs import V3GeneratedOutputRecord, V3GeneratedOutputStore


class GeneratedOutputResolver:
    """Infrastructure helper for Doc55 post-generation inspection."""

    def __init__(self, output_store: V3GeneratedOutputStore | None = None) -> None:
        self.output_store = output_store or V3GeneratedOutputStore()

    def resolve_result(self, result: PlanningResult, project_id: str | None = None) -> list[GeneratedOutputResolution]:
        return [self.resolve_asset(result.creative_job.job_id, asset, project_id=project_id) for asset in result.asset_pack.assets]

    def resolve_asset(
        self,
        job_id: str,
        asset: PackagedAsset,
        *,
        project_id: str | None = None,
    ) -> GeneratedOutputResolution:
        metadata = dict(asset.metadata or {})
        candidate_metadata = metadata.get("candidate_metadata") if isinstance(metadata.get("candidate_metadata"), dict) else {}
        candidate_id = metadata.get("selected_candidate_id") or candidate_metadata.get("candidate_id")
        output_id = candidate_metadata.get("output_id") or metadata.get("output_id")
        if output_id:
            record = self.output_store.get_output(str(output_id))
            if record is not None:
                return self._from_record(record, asset, project_id=project_id)
        file_path = asset.file_path or candidate_metadata.get("file_path")
        if file_path:
            path = Path(str(file_path))
            if path.exists() and path.is_file():
                return GeneratedOutputResolution(
                    resolution_id=stable_id("output_resolution", job_id, candidate_id, asset.asset_id, file_path),
                    project_id=project_id,
                    job_id=job_id,
                    candidate_id=str(candidate_id) if candidate_id else None,
                    asset_id=asset.asset_id,
                    output_id=str(output_id) if output_id else None,
                    file_path=str(path),
                    preview_url=candidate_metadata.get("preview_url"),
                    thumbnail_url=candidate_metadata.get("thumbnail_url"),
                    download_url=candidate_metadata.get("download_url") or candidate_metadata.get("url"),
                    mime_type=candidate_metadata.get("mime_type"),
                    width=self._safe_int(candidate_metadata.get("width")),
                    height=self._safe_int(candidate_metadata.get("height")),
                    provider=candidate_metadata.get("actual_provider") or candidate_metadata.get("provider"),
                    model=candidate_metadata.get("actual_model") or candidate_metadata.get("model"),
                    status="ready",
                    metadata={"candidate_metadata": dict(candidate_metadata), "asset_metadata": metadata},
                )
            return self._missing_resolution(
                job_id,
                asset,
                project_id=project_id,
                candidate_id=candidate_id,
                output_id=output_id,
                status="unreadable",
                warning=f"Output file is missing or unreadable: {file_path}",
                candidate_metadata=candidate_metadata,
            )
        if candidate_metadata.get("download_url") or candidate_metadata.get("url") or asset.uri:
            return GeneratedOutputResolution(
                resolution_id=stable_id("output_resolution", job_id, candidate_id, asset.asset_id, "remote_only"),
                project_id=project_id,
                job_id=job_id,
                candidate_id=str(candidate_id) if candidate_id else None,
                asset_id=asset.asset_id,
                output_id=str(output_id) if output_id else None,
                download_url=candidate_metadata.get("download_url") or candidate_metadata.get("url") or asset.uri,
                preview_url=candidate_metadata.get("preview_url"),
                thumbnail_url=candidate_metadata.get("thumbnail_url"),
                width=self._safe_int(candidate_metadata.get("width")),
                height=self._safe_int(candidate_metadata.get("height")),
                status="remote_only",
                warnings=["Output is remote-only and cannot be inspected locally yet."],
                metadata={"candidate_metadata": dict(candidate_metadata), "asset_metadata": metadata},
            )
        return self._missing_resolution(
            job_id,
            asset,
            project_id=project_id,
            candidate_id=candidate_id,
            output_id=output_id,
            status="missing",
            warning="No generated output file or URL was found for this candidate.",
            candidate_metadata=candidate_metadata,
        )

    def _from_record(
        self,
        record: V3GeneratedOutputRecord,
        asset: PackagedAsset,
        *,
        project_id: str | None = None,
    ) -> GeneratedOutputResolution:
        status = "ready"
        warnings: list[str] = []
        if not Path(record.file_path).exists():
            status = "unreadable"
            warnings.append(f"Output record file is missing: {record.file_path}")
        return GeneratedOutputResolution(
            resolution_id=stable_id("output_resolution", record.job_id, record.candidate_id, record.output_id),
            project_id=project_id or record.metadata.get("project_id"),
            job_id=record.job_id,
            candidate_id=record.candidate_id,
            asset_id=record.asset_id or asset.asset_id,
            output_id=record.output_id,
            file_path=record.file_path,
            preview_path=record.preview_path,
            thumbnail_path=record.thumbnail_path,
            download_url=record.download_url,
            preview_url=record.preview_url,
            thumbnail_url=record.thumbnail_url,
            mime_type=record.mime_type,
            width=record.width,
            height=record.height,
            provider=record.provider,
            model=record.model,
            status=status,
            warnings=warnings,
            metadata={"output_record": record.to_json_dict(), "asset_metadata": dict(asset.metadata or {})},
        )

    def _missing_resolution(
        self,
        job_id: str,
        asset: PackagedAsset,
        *,
        project_id: str | None,
        candidate_id: Any,
        output_id: Any,
        status: str,
        warning: str,
        candidate_metadata: dict[str, Any],
    ) -> GeneratedOutputResolution:
        return GeneratedOutputResolution(
            resolution_id=stable_id("output_resolution", job_id, candidate_id, asset.asset_id, status),
            project_id=project_id,
            job_id=job_id,
            candidate_id=str(candidate_id) if candidate_id else None,
            asset_id=asset.asset_id,
            output_id=str(output_id) if output_id else None,
            status=status,
            warnings=[warning],
            metadata={"candidate_metadata": dict(candidate_metadata), "asset_metadata": dict(asset.metadata or {})},
        )

    def _safe_int(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

