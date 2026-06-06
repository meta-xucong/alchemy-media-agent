from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from app.agents import AGENTS_SDK_AVAILABLE, CreativeManagerRuntime
from app.config import ensure_runtime_dirs, settings
from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID
from app.repositories import repository
from app.schemas import (
    AssetContentUploadRequest,
    CreateCreativeRunRequest,
    CreateFeedbackRequest,
    CreateImageJobRequest,
    CreateRevisionRunRequest,
    CreateUploadedAssetRequest,
    CreateUploadedAssetResponse,
    FeedbackEvent,
    HealthIsolation,
    HealthResponse,
    ImageHistoryResponse,
    SearchPromptCasesRequest,
    V2RuntimeModelSettingsRequest,
    V2RuntimeModelSettingsResponse,
)
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_assets import read_case_asset, read_case_thumbnail
from app.services.case_intelligence import build_case_profile, get_prompt_case, list_templates, search_prompt_cases
from app.services.claude_orchestrator import get_orchestrator_status
from app.services.generation import create_image_job
from app.services.image_history import delete_image_history_item, list_image_history
from app.services.history_thumbnails import read_history_thumbnail
from app.services.ids import new_id
from app.services.revision import RevisionSourceError, build_revision_request
from app.services.resource_sync import get_sync_run, list_resource_providers, sync_resource_provider
from app.services.runtime_model_settings import (
    apply_persisted_runtime_model_settings,
    get_runtime_model_settings,
    update_runtime_model_settings,
)
from app.services.queue_worker import QueueWorker
from app.services.task_queue import enqueue_creative_task, get_run_snapshot, initialize_task_queue, task_queue_stats
from app.services.uploaded_assets import (
    complete_uploaded_asset,
    create_uploaded_asset,
    get_uploaded_asset,
    read_uploaded_asset_content,
    store_uploaded_asset_content,
)
from app.services.visual_review_agent import get_visual_review_agent_status, refresh_visual_review_agent
from app.repositories.memory import utc_now
from app.providers.images import list_v2_image_provider_capabilities
from app.services.output_storage import read_output_content


creative_manager = CreativeManagerRuntime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    apply_persisted_runtime_model_settings()
    creative_manager.refresh_runtime_config()
    refresh_visual_review_agent()
    bootstrap_v2_repository(seed_cases=True)
    initialize_task_queue()
    startup_sync_task: asyncio.Task | None = None
    queue_worker_task: asyncio.Task | None = None
    queue_worker_stop: asyncio.Event | None = None
    if settings.sync_github_on_startup:
        startup_sync_task = asyncio.create_task(
            asyncio.to_thread(sync_resource_provider, EVOLINKAI_PROVIDER_ID, "remote")
        )
    if settings.task_queue_inline_worker_enabled:
        queue_worker_stop = asyncio.Event()
        queue_worker_task = asyncio.create_task(
            QueueWorker(creative_manager, worker_id="v2-api-inline-worker").run_forever(queue_worker_stop)
        )
    yield
    if startup_sync_task and not startup_sync_task.done():
        startup_sync_task.cancel()
    if queue_worker_stop:
        queue_worker_stop.set()
    if queue_worker_task and not queue_worker_task.done():
        queue_worker_task.cancel()


app = FastAPI(title="Custom Media Agent 2.0 API", version=settings.version, lifespan=lifespan)
if settings.cors_allow_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
@app.get("/api/v2/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service=settings.service_name,
        version=settings.version,
        agent_runtime=settings.agent_runtime,
        agents_sdk_available=AGENTS_SDK_AVAILABLE,
        isolation=HealthIsolation(
            api_prefix=settings.api_prefix,
            db_namespace=settings.db_namespace,
            redis_prefix=settings.redis_prefix,
            storage_prefix=settings.object_storage_prefix,
            trace_project=settings.trace_project,
        ),
    )


@app.post("/api/v2/creative/runs", status_code=202)
async def create_creative_run(body: CreateCreativeRunRequest):
    return await creative_manager.run(body)


@app.post("/api/v2/creative/runs/async", status_code=202)
async def create_creative_run_async(body: CreateCreativeRunRequest):
    queued = creative_manager.queue_run(body)
    enqueue_creative_task(kind="creative_run", request_payload=body.model_dump(mode="json"), queued_run=queued)
    return queued


@app.post("/api/v2/uploads", response_model=CreateUploadedAssetResponse)
def create_upload(body: CreateUploadedAssetRequest) -> CreateUploadedAssetResponse:
    return create_uploaded_asset(body)


@app.put("/api/v2/uploads/{asset_id}/content")
def put_upload_content(asset_id: str, body: AssetContentUploadRequest):
    asset = store_uploaded_asset_content(asset_id, body)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    if asset.status == "failed":
        raise HTTPException(status_code=400, detail={"error_code": "invalid_asset_content", "message": "Asset content is invalid."})
    return asset


@app.post("/api/v2/uploads/{asset_id}/complete")
def complete_upload(asset_id: str):
    asset = complete_uploaded_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    return asset


@app.get("/api/v2/uploads/{asset_id}")
def upload_detail(asset_id: str):
    asset = get_uploaded_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    return asset


@app.get("/api/v2/uploads/{asset_id}/content")
def upload_content(asset_id: str):
    asset = read_uploaded_asset_content(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_content_not_found", "message": "Uploaded asset content not found."})
    content, media_type = asset
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/v2/orchestrator/status")
def orchestrator_status():
    return get_orchestrator_status()


@app.get("/api/v2/task-queue/status")
def task_queue_status():
    return task_queue_stats()


@app.get("/api/v2/review-agent/status")
def review_agent_status():
    return get_visual_review_agent_status()


@app.get("/api/v2/provider-capabilities")
async def provider_capabilities():
    return {"providers": [item.model_dump(mode="json") for item in await list_v2_image_provider_capabilities()]}


@app.get("/api/v2/runtime/model-settings", response_model=V2RuntimeModelSettingsResponse)
def runtime_model_settings() -> V2RuntimeModelSettingsResponse:
    return get_runtime_model_settings()


@app.post("/api/v2/runtime/model-settings", response_model=V2RuntimeModelSettingsResponse)
def update_model_settings(body: V2RuntimeModelSettingsRequest) -> V2RuntimeModelSettingsResponse:
    updated = update_runtime_model_settings(body)
    creative_manager.refresh_runtime_config()
    refresh_visual_review_agent()
    return updated


@app.get("/api/v2/creative/runs/{run_id}")
def get_creative_run(run_id: str):
    run = get_run_snapshot(run_id) or repository.get_creative_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"error_code": "run_not_found", "message": "Creative run not found."})
    return run


@app.post("/api/v2/prompt-cases/search")
def search_cases(body: SearchPromptCasesRequest):
    return search_prompt_cases(body)


@app.get("/api/v2/case-profiles/{case_id}")
def case_profile(case_id: str):
    case = get_prompt_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error_code": "case_not_found", "message": "Prompt case not found."})
    return build_case_profile(case)


@app.get("/api/v2/prompt-cases/{case_id}")
def get_case(case_id: str):
    case = get_prompt_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error_code": "case_not_found", "message": "Prompt case not found."})
    return case


@app.get("/api/v2/templates")
def templates(
    category: str | None = None,
    use_case: str | None = None,
    limit: int = Query(default=24, ge=1, le=1000),
):
    return {"templates": list_templates(category=category, use_case=use_case, limit=limit)}


@app.get("/api/v2/case-assets/{asset_path:path}")
def case_asset(asset_path: str):
    asset = read_case_asset(asset_path)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "case_asset_not_found", "message": "Case asset not found."})
    content, media_type = asset
    return Response(content=content, media_type=media_type)


@app.get("/api/v2/case-thumbnails/{asset_path:path}")
def case_thumbnail(asset_path: str):
    asset = read_case_thumbnail(asset_path)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "case_thumbnail_not_found", "message": "Case thumbnail not found."})
    content, media_type = asset
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.get("/api/v2/resource-providers")
def resource_providers():
    return {"providers": list_resource_providers()}


@app.post("/api/v2/resource-providers/{provider_id}/sync", status_code=202)
def request_provider_sync(provider_id: str, mode: str = Query(default="auto", pattern="^(auto|seed|remote)$")):
    try:
        return sync_resource_provider(provider_id, mode=mode)  # type: ignore[arg-type]
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "provider_not_found", "message": str(exc)},
        ) from exc


@app.get("/api/v2/resource-providers/{provider_id}/sync-runs/{sync_run_id}")
def provider_sync_run(provider_id: str, sync_run_id: str):
    run = get_sync_run(sync_run_id)
    if not run or run.provider_id != provider_id:
        raise HTTPException(status_code=404, detail={"error_code": "sync_run_not_found", "message": "Sync run not found."})
    return run


@app.post("/api/v2/image/jobs", status_code=202)
async def image_job(body: CreateImageJobRequest):
    return await create_image_job(body)


@app.get("/api/v2/image/history", response_model=ImageHistoryResponse)
def image_history(limit: int = Query(default=50, ge=1, le=1000)):
    return list_image_history(limit=limit)


@app.get("/api/v2/image/history/{output_id}/thumbnail")
def image_history_thumbnail(output_id: str):
    thumbnail = read_history_thumbnail(output_id)
    if not thumbnail:
        raise HTTPException(status_code=404, detail={"error_code": "history_thumbnail_not_found", "message": "History thumbnail not found."})
    content, media_type = thumbnail
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.delete("/api/v2/image/history/{output_id}")
def delete_history_item(output_id: str):
    result = delete_image_history_item(output_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=404,
            detail={"error_code": "history_output_not_found", "message": "V2 history output not found."},
        )
    return result


@app.get("/api/v2/image/jobs/{job_id}")
def get_image_job(job_id: str):
    job = repository.get_image_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error_code": "job_not_found", "message": "Image job not found."})
    return job


@app.get("/api/v2/outputs/{output_id}/download")
def output_download(output_id: str):
    output = read_output_content(output_id)
    if not output:
        raise HTTPException(status_code=404, detail={"error_code": "output_not_found", "message": "V2 output file not found."})
    content, media_type = output
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/v2/outputs/{output_id}/feedback", status_code=201, response_model=FeedbackEvent)
def output_feedback(output_id: str, body: CreateFeedbackRequest) -> FeedbackEvent:
    if not repository.get_output(output_id):
        raise HTTPException(status_code=404, detail={"error_code": "output_not_found", "message": "Output not found."})
    event = FeedbackEvent(
        feedback_id=new_id("feedback"),
        output_id=output_id,
        feedback_type=body.feedback_type,
        payload=body.payload,
        created_at=utc_now(),
    )
    return repository.save_feedback(event)


@app.post("/api/v2/outputs/{output_id}/revisions", status_code=202)
async def output_revision(output_id: str, body: CreateRevisionRunRequest):
    try:
        request = build_revision_request(output_id, body)
    except RevisionSourceError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=404,
            detail={"error_code": code, "message": "Revision source output or job not found."},
        ) from exc
    return await creative_manager.run(request)


@app.post("/api/v2/outputs/{output_id}/revisions/async", status_code=202)
async def output_revision_async(output_id: str, body: CreateRevisionRunRequest):
    try:
        request = build_revision_request(output_id, body)
    except RevisionSourceError as exc:
        code = str(exc)
        raise HTTPException(
            status_code=404,
            detail={"error_code": code, "message": "Revision source output or job not found."},
        ) from exc
    queued = creative_manager.queue_run(request)
    enqueue_creative_task(kind="revision_run", request_payload=request.model_dump(mode="json"), queued_run=queued)
    return queued
