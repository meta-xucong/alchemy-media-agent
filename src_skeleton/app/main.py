from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import persist_runtime_settings_to_env, settings, update_runtime_settings
from app.providers.registry import registry
from app.repositories import repository
from app.schemas import (
    AssetContentUploadRequest,
    AssetIntent,
    CreateAssetMaskRequest,
    CreateAssetUploadRequest,
    CreateImageJobRequest,
    CreateSessionRequest,
    CreateVideoJobRequest,
    ImageHistoryItem,
    ImageHistoryResponse,
    MessageRequest,
    ReviseImageRequest,
    RuntimeProviderSettingsRequest,
    RuntimeProviderSettingsResponse,
)
from app.services.asset_service import complete_asset_upload, create_asset_mask, create_asset_upload, get_asset, store_asset_content
from app.services.events import format_sse_events
from app.services.image_service import create_image_job, revise_image_job
from app.services.session_service import create_session, handle_message
from app.services.video_service import create_video_job
from app.storage import media_store

app = FastAPI(title="Custom Media Agent API", version="0.1.0")
STATIC_DIR = Path(__file__).resolve().parent / "static"
IMMUTABLE_IMAGE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}
V2_BRIDGE_PROJECT_ID = "alchemy_v2_bridge"
V2_IDEMPOTENCY_PREFIX = "v2:"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def frontend_app():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "custom-media-agent", "version": app.version}


@app.post("/v1/sessions")
def create_session_endpoint(body: CreateSessionRequest):
    return create_session(body)


@app.post("/v1/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest):
    return await handle_message(session_id, body)


@app.get("/v1/sessions/{session_id}/events")
def stream_session_events(session_id: str):
    return StreamingResponse(format_sse_events(session_id), media_type="text/event-stream")


@app.post("/v1/assets/upload-url")
def create_asset_upload_endpoint(body: CreateAssetUploadRequest):
    return create_asset_upload(body)


@app.put("/v1/assets/{asset_id}/content")
def put_asset_content_endpoint(asset_id: str, body: AssetContentUploadRequest):
    asset = store_asset_content(asset_id, body)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    if asset.status == "failed":
        raise HTTPException(status_code=400, detail={"code": "invalid_asset_content", "message": "Asset content is not valid base64."})
    return asset


@app.get("/v1/assets/{asset_id}/content")
def get_asset_content_endpoint(asset_id: str):
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    path = media_store.find_asset_file(asset_id)
    if not path:
        raise HTTPException(status_code=404, detail={"code": "asset_content_not_found", "message": "Asset content not found."})
    return FileResponse(path, media_type=asset.mime_type)


@app.post("/v1/assets/{asset_id}/complete")
def complete_asset_upload_endpoint(asset_id: str):
    asset = complete_asset_upload(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return asset


@app.get("/v1/assets/{asset_id}")
def get_asset_endpoint(asset_id: str):
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return asset


@app.put("/v1/assets/{asset_id}/intent")
def set_asset_intent_endpoint(asset_id: str, body: AssetIntent):
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return body.model_copy(update={"asset_id": asset_id})


@app.post("/v1/assets/{asset_id}/masks")
def create_asset_mask_endpoint(asset_id: str, body: CreateAssetMaskRequest):
    result = create_asset_mask(asset_id, body)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return result


@app.post("/v1/image/jobs")
async def create_image_job_endpoint(body: CreateImageJobRequest):
    return await create_image_job(
        session_id=body.session_id,
        prompt=body.prompt,
        asset_mode=body.asset_mode,
        asset_ids=body.asset_ids,
        asset_intents=body.asset_intents,
        count=body.count,
        size=body.size,
        quality=body.quality,
        output_format=body.output_format,
        work_intensity=body.work_intensity,
        provider_preference=body.provider_preference,
        idempotency_key=body.idempotency_key,
    )


@app.get("/v1/image/history")
def list_image_history(
    session_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
):
    items: list[ImageHistoryItem] = []
    known_output_ids: set[str] = set()
    for job in repository.list_jobs(job_type="image", session_id=session_id):
        if _is_v2_bridge_job(job):
            continue
        for output in job.outputs:
            if output.format not in {"png", "jpeg", "webp"}:
                continue
            known_output_ids.add(output.id)
            items.append(
                ImageHistoryItem(
                    id=output.id,
                    job_id=job.id,
                    session_id=job.session_id,
                    url=output.url,
                    thumbnail_url=media_store.thumbnail_url(output.id),
                    format=output.format,
                    width=output.width,
                    height=output.height,
                    provider=job.provider,
                    model=job.model,
                    requested_provider=_job_requested_provider(job),
                    requested_model=_job_requested_model(job),
                    provider_fallback=job.raw_response_summary.get("image_provider_fallback") if job.raw_response_summary else None,
                    asset_mode=job.asset_mode,
                    asset_intents=_job_asset_intents(job),
                    asset_plan=job.asset_plan,
                    asset_vision_profiles=_job_asset_vision_profiles(job),
                    provider_input_plan=_job_provider_input_plan(job),
                    visual_review=output.visual_review.model_dump() if output.visual_review else None,
                    prompt_plan=job.prompt_plan.variables.get("advanced_prompt_plan") if job.prompt_plan and job.prompt_plan.variables else None,
                    original_prompt=job.provenance.get("original_prompt") if job.provenance else None,
                    final_prompt=_job_prompt(job),
                    work_intensity=_job_work_intensity(job),
                    work_intensity_label=_job_work_intensity_label(job),
                    prompt=_job_prompt(job),
                    size=job.prompt_plan.size if job.prompt_plan else None,
                    version_parent_id=output.version_parent_id,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    source="repository",
                )
            )

    if len(items) < limit:
        for record in media_store.list_history_records(limit=limit, session_id=session_id):
            if record["id"] in known_output_ids or record["format"] not in {"png", "jpeg", "webp"} or _is_v2_bridge_history_record(record):
                continue
            items.append(ImageHistoryItem(**record))
            if len(items) >= limit:
                break

    items.sort(key=_history_sort_key, reverse=True)
    return ImageHistoryResponse(items=items[:limit], total=len(items))


@app.delete("/v1/image/history/{output_id}")
def delete_image_history_item(output_id: str):
    output = repository.delete_output(output_id)
    thumbnail_existed = media_store.thumbnail_path(output_id).exists()
    deleted_file = media_store.delete_output_file(
        output_id=output_id,
        job_id=output.job_id if output else None,
        output_format=output.format if output else None,
    )
    deleted_thumbnail = media_store.delete_thumbnail(output_id) or thumbnail_existed
    removed_records = media_store.delete_history_record(output_id)
    if not output and not deleted_file and not deleted_thumbnail and removed_records == 0:
        raise HTTPException(status_code=404, detail={"code": "output_not_found", "message": "Output not found."})
    if output:
        repository.append_event(
            repository.get_job(output.job_id).session_id if repository.get_job(output.job_id) else None,
            "generation.output.deleted",
            {"output_id": output_id, "job_id": output.job_id},
        )
    return {
        "ok": True,
        "output_id": output_id,
        "deleted_file": deleted_file,
        "deleted_thumbnail": deleted_thumbnail,
        "removed_history_records": removed_records,
        "removed_repository_output": bool(output),
    }


@app.get("/v1/image/jobs/{job_id}")
def get_image_job(job_id: str):
    job = repository.get_job(job_id)
    if not job or job.job_type != "image":
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Image job not found."})
    return job


@app.post("/v1/image/jobs/{job_id}/revise")
async def revise_image_job_endpoint(job_id: str, body: ReviseImageRequest):
    job = await revise_image_job(job_id, body)
    if not job:
        raise HTTPException(status_code=404, detail={"code": "output_not_found", "message": "Source image output not found."})
    return job


@app.post("/v1/video/jobs")
async def create_video_job_endpoint(body: CreateVideoJobRequest):
    return await create_video_job(
        session_id=body.session_id,
        task_type=body.task_type,
        prompt=body.prompt,
        asset_ids=body.asset_ids,
        duration_seconds=body.duration_seconds,
        aspect_ratio=body.aspect_ratio,
        resolution=body.resolution,
        provider_preference=body.provider_preference,
    )


@app.get("/v1/video/jobs/{job_id}")
def get_video_job(job_id: str):
    job = repository.get_job(job_id)
    if not job or job.job_type != "video":
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Video job not found."})
    return job


@app.get("/v1/providers")
async def list_providers():
    capabilities = await registry.list_capabilities()
    return {
        "providers": [item.model_dump() for group in capabilities.values() for item in group],
        "image": [item.model_dump() for item in capabilities["image"]],
        "video": [item.model_dump() for item in capabilities["video"]],
    }


@app.get("/v1/runtime/provider-settings")
def get_runtime_provider_settings():
    return _runtime_provider_settings_response()


@app.post("/v1/runtime/provider-settings")
def update_provider_settings(body: RuntimeProviderSettingsRequest):
    update_runtime_settings(
        default_image_provider=body.default_image_provider,
        default_image_model=body.default_image_model,
        openai_image_model=body.openai_image_model,
        gemini_image_model=body.gemini_image_model,
        default_llm_provider=body.default_llm_provider,
        default_llm_model=body.default_llm_model,
        backup_llm_model=body.backup_llm_model,
        openai_llm_model=body.openai_llm_model,
        kimi_llm_model=body.kimi_llm_model,
        image_work_intensity=body.image_work_intensity,
        openai_api_key=body.openai_api_key,
        openai_base_url=body.openai_base_url,
        anthropic_api_key=body.anthropic_api_key,
        anthropic_base_url=body.anthropic_base_url,
        gemini_image_api_key=body.gemini_image_api_key,
        gemini_image_base_url=body.gemini_image_base_url,
    )
    persist_runtime_settings_to_env()
    return _runtime_provider_settings_response()


@app.get("/v1/outputs/{output_id}/download")
def download_output(output_id: str):
    path, _ = _resolve_output_file(output_id)
    return FileResponse(path, headers=IMMUTABLE_IMAGE_HEADERS)


@app.get("/v1/outputs/{output_id}/thumbnail")
def thumbnail_output(output_id: str):
    path, _ = _resolve_output_file(output_id)
    thumbnail_path = media_store.ensure_thumbnail(output_id=output_id, source_path=path)
    if thumbnail_path == media_store.thumbnail_path(output_id):
        return FileResponse(thumbnail_path, media_type="image/jpeg", headers=IMMUTABLE_IMAGE_HEADERS)
    return FileResponse(thumbnail_path, headers=IMMUTABLE_IMAGE_HEADERS)


def _resolve_output_file(output_id: str) -> tuple[Path, str]:
    output = repository.get_output(output_id)
    if not output:
        fallback = media_store.find_output_file(output_id)
        if not fallback:
            raise HTTPException(status_code=404, detail={"code": "output_not_found", "message": "Output not found."})
        path, output_format, _ = fallback
        return path, output_format
    path = media_store.output_path(job_id=output.job_id, output_id=output.id, output_format=output.format)
    if not path.exists():
        fallback = media_store.find_output_file(output_id)
        if not fallback:
            raise HTTPException(status_code=404, detail={"code": "output_file_not_found", "message": "Output file not found."})
        path, output_format, _ = fallback
        return path, output_format
    return path, output.format


def _job_prompt(job) -> str | None:
    if not job.prompt_plan:
        return None
    generation_prompt = job.prompt_plan.variables.get("generation_prompt") if job.prompt_plan.variables else None
    if generation_prompt:
        return str(generation_prompt)
    parts = [
        job.prompt_plan.main_subject,
        job.prompt_plan.scene,
        job.prompt_plan.style,
        job.prompt_plan.composition,
    ]
    return "，".join(part for part in parts if part)


def _job_asset_intents(job) -> list[dict]:
    if not job.asset_plan:
        return []
    return [
        {
            "asset_id": item.get("asset_id"),
            "role": item.get("role"),
            "role_label": item.get("role_label"),
            "priority": item.get("priority"),
            "preservation": item.get("preservation"),
            "strength": item.get("strength"),
        }
        for item in job.asset_plan.get("assets", [])
    ]


def _job_asset_vision_profiles(job) -> list[dict]:
    if not job.asset_plan:
        return []
    profiles = []
    for item in job.asset_plan.get("assets", []):
        profile = item.get("vision_profile")
        if profile:
            profiles.append(profile)
    return profiles


def _job_provider_input_plan(job) -> dict | None:
    if not job.asset_plan:
        return None
    value = job.asset_plan.get("provider_input_plan")
    return dict(value) if isinstance(value, dict) else None


def _job_work_intensity(job) -> str | None:
    if not job.prompt_plan or not job.prompt_plan.variables:
        return None
    value = job.prompt_plan.variables.get("work_intensity")
    return str(value) if value else None


def _job_work_intensity_label(job) -> str | None:
    if not job.prompt_plan or not job.prompt_plan.variables:
        return None
    value = job.prompt_plan.variables.get("work_intensity_label")
    return str(value) if value else None


def _job_requested_provider(job) -> str | None:
    value = job.raw_response_summary.get("requested_image_provider") if job.raw_response_summary else None
    return str(value) if value else None


def _job_requested_model(job) -> str | None:
    value = job.raw_response_summary.get("requested_image_model") if job.raw_response_summary else None
    return str(value) if value else None


def _history_sort_key(item: ImageHistoryItem) -> tuple[float, str, str]:
    timestamp = _parse_history_timestamp(item.created_at or item.updated_at)
    return (timestamp, item.job_id, item.id)


def _parse_history_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except ValueError:
        return 0.0


def _is_v2_bridge_job(job) -> bool:
    if str(job.idempotency_key or "").startswith(V2_IDEMPOTENCY_PREFIX):
        return True
    session = repository.get_session(job.session_id) if job.session_id else None
    return session.project_id == V2_BRIDGE_PROJECT_ID if session else False


def _is_v2_bridge_history_record(record: dict) -> bool:
    if record.get("source_app") == V2_BRIDGE_PROJECT_ID:
        return True
    if str(record.get("idempotency_key") or "").startswith(V2_IDEMPOTENCY_PREFIX):
        return True
    return False


def _runtime_provider_settings_response() -> RuntimeProviderSettingsResponse:
    return RuntimeProviderSettingsResponse(
        default_image_provider=settings.default_image_provider,
        default_image_model=settings.default_image_model,
        openai_image_model=settings.openai_image_model,
        gemini_image_model=settings.gemini_image_model,
        default_llm_provider=settings.default_llm_provider,
        default_llm_model=settings.default_llm_model,
        backup_llm_provider=settings.backup_llm_provider,
        backup_llm_model=settings.backup_llm_model,
        openai_llm_model=settings.openai_llm_model,
        kimi_llm_model=settings.kimi_llm_model,
        image_work_intensity=settings.image_work_intensity,
        openai_base_url=settings.openai_base_url,
        openai_api_key_configured=bool(settings.openai_api_key),
        anthropic_base_url=settings.anthropic_base_url,
        anthropic_api_key_configured=bool(settings.anthropic_api_key or settings.anthropic_auth_token),
        gemini_image_base_url=settings.gemini_image_base_url,
        gemini_image_api_key_configured=bool(settings.gemini_image_api_key),
        provider_notes={
            "openai_gpt_image": "OpenAI-compatible GPT Image provider is wired for live image generation.",
            "gemini_image": "Gemini image provider is wired for live generateContent image generation.",
            "seedance": "Seedance video provider is a documented async placeholder; live task API is not implemented yet.",
            "thinking_models": "Prompt planning uses the selected thinking model first and automatically tries the other model when the selected one fails.",
        },
    )
