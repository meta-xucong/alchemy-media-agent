from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from urllib.parse import quote

from app.config import settings
from app.repositories import repository
from app.schemas import ImageHistoryItem, ImageHistoryResponse, ImageJob, ImageOutput
from app.services.output_storage import delete_output_storage


def persist_image_job_history(job: ImageJob) -> None:
    if not settings.persist_image_history:
        return
    if not job.outputs:
        return
    settings.image_history_path.parent.mkdir(parents=True, exist_ok=True)
    with settings.image_history_path.open("a", encoding="utf-8") as handle:
        for output in job.outputs:
            item = ImageHistoryItem(
                output_id=output.output_id,
                job_id=job.job_id,
                run_id=job.run_id,
                status=job.status,
                provider_id=job.provider_id,
                model=job.model,
                mode=job.prompt_plan.mode,
                template_case_id=_template_case_id(job),
                prompt=job.prompt_plan.prompt,
                url=output.url,
                thumbnail_url=_thumbnail_url(output),
                score=output.score,
                metadata=_history_metadata(job, output),
                created_at=output.created_at,
                updated_at=job.updated_at,
            )
            handle.write(item.model_dump_json())
            handle.write("\n")


def list_image_history(limit: int = 50) -> ImageHistoryResponse:
    if not settings.image_history_path.exists():
        return ImageHistoryResponse(items=[], total=0)
    records_by_output: dict[str, ImageHistoryItem] = {}
    for line in settings.image_history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = ImageHistoryItem.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
        item = _normalize_thumbnail_url(item)
        existing = records_by_output.get(item.output_id)
        if existing is None or _timestamp(item.updated_at) >= _timestamp(existing.updated_at):
            records_by_output[item.output_id] = item
    items = sorted(records_by_output.values(), key=lambda item: (_timestamp(item.created_at), item.job_id), reverse=True)
    return ImageHistoryResponse(items=items[:limit], total=len(items))


def get_image_history_item(output_id: str) -> ImageHistoryItem | None:
    if not settings.image_history_path.exists():
        return None
    newest: ImageHistoryItem | None = None
    for line in settings.image_history_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = ImageHistoryItem.model_validate(json.loads(line))
        except (json.JSONDecodeError, ValueError):
            continue
        if item.output_id != output_id:
            continue
        if newest is None or _timestamp(item.updated_at) >= _timestamp(newest.updated_at):
            newest = item
    return newest


def delete_image_history_item(output_id: str) -> dict[str, Any]:
    removed_records = 0
    newest_removed: ImageHistoryItem | None = None
    kept_lines: list[str] = []
    if settings.image_history_path.exists():
        for line in settings.image_history_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = ImageHistoryItem.model_validate(json.loads(line))
            except (json.JSONDecodeError, ValueError):
                kept_lines.append(line)
                continue
            if item.output_id != output_id:
                kept_lines.append(line)
                continue
            removed_records += 1
            if newest_removed is None or _timestamp(item.updated_at) >= _timestamp(newest_removed.updated_at):
                newest_removed = item
        if removed_records:
            settings.image_history_path.write_text(
                ("\n".join(kept_lines) + "\n") if kept_lines else "",
                encoding="utf-8",
            )

    output = repository.delete_output(output_id)
    metadata = dict(newest_removed.metadata if newest_removed else output.metadata if output else {})
    storage_result = delete_output_storage(output_id, metadata)
    removed_output = bool(output)
    if not removed_records and not removed_output and not any(storage_result.values()):
        return {
            "ok": False,
            "output_id": output_id,
            "removed_history_records": 0,
            "removed_repository_output": False,
            **storage_result,
        }
    return {
        "ok": True,
        "output_id": output_id,
        "removed_history_records": removed_records,
        "removed_repository_output": removed_output,
        **storage_result,
    }


def _template_case_id(job: ImageJob) -> str | None:
    value = job.prompt_plan.user_variables.get("primary_case_id")
    return str(value) if value else None


def _history_metadata(job: ImageJob, output: ImageOutput) -> dict[str, Any]:
    metadata = dict(output.metadata)
    user_variables = job.prompt_plan.user_variables or {}
    metadata.setdefault("original_prompt", str(user_variables.get("user_prompt") or ""))
    metadata.setdefault("final_prompt", job.prompt_plan.prompt)
    if job.prompt_plan.negative_prompt:
        metadata.setdefault("negative_prompt", job.prompt_plan.negative_prompt)
    if job.prompt_plan.explanation:
        metadata.setdefault("prompt_explanation", job.prompt_plan.explanation)
    if user_variables.get("orchestrator_decision_id"):
        metadata.setdefault("orchestrator_decision_id", str(user_variables["orchestrator_decision_id"]))
    if user_variables.get("orchestrator_provider"):
        metadata.setdefault("orchestrator_provider", str(user_variables["orchestrator_provider"]))
    if user_variables.get("prompt_source"):
        metadata.setdefault("prompt_source", str(user_variables["prompt_source"]))
    metadata.setdefault("claude_final_prompt_used", bool(user_variables.get("claude_final_prompt_used")))
    for key in [
        "template_lock_enabled",
        "template_lock_contract",
        "asset_binding_plan",
        "provider_input_plan",
        "uploaded_assets",
        "provider_input_asset_ids",
    ]:
        if key in user_variables:
            metadata.setdefault(key, user_variables[key])
    return metadata


def _thumbnail_url(output: ImageOutput) -> str | None:
    if output.metadata.get("native_v2_storage"):
        return _thumbnail_endpoint(output.output_id)
    if output.metadata.get("mock"):
        return output.metadata.get("thumbnail_url")
    return _thumbnail_endpoint(output.output_id)


def _normalize_thumbnail_url(item: ImageHistoryItem) -> ImageHistoryItem:
    if item.metadata.get("native_v2_storage"):
        return item.model_copy(update={"thumbnail_url": _thumbnail_endpoint(item.output_id)})
    if item.metadata.get("mock"):
        return item
    return item.model_copy(update={"thumbnail_url": _thumbnail_endpoint(item.output_id)})


def _thumbnail_endpoint(output_id: str) -> str:
    return f"/api/v2/image/history/{quote(output_id, safe='')}/thumbnail"


def _timestamp(value: datetime) -> float:
    return value.timestamp()
