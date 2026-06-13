from __future__ import annotations

import asyncio
import hashlib
import json
from collections import OrderedDict
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.encoders import jsonable_encoder
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
    VeyraBillingSettingsRequest,
    VeyraBillingSettingsResponse,
)
from app.services.bootstrap import bootstrap_v2_repository
from app.services.case_assets import read_case_asset, read_case_thumbnail
from app.services import case_intelligence
from app.services.case_intelligence import build_case_profile, get_prompt_case, list_templates, search_prompt_cases
from app.services.claude_orchestrator import get_orchestrator_status
from app.services.generation import create_image_job
from app.services.image_history import delete_image_history_item, list_image_history
from app.services.history_thumbnails import read_history_thumbnail
from app.services.ids import new_id
from app.services.revision import RevisionSourceError, build_revision_request
from app.services.resource_sync import get_sync_run, list_resource_providers, sync_resource_provider
from app.services.resource_sync_scheduler import ResourceSyncScheduler
from app.services.runtime_model_settings import (
    apply_persisted_runtime_model_settings,
    get_runtime_model_settings,
    update_runtime_model_settings,
)
from app.services.veyra_billing_settings import (
    apply_persisted_billing_settings,
    get_billing_settings,
    update_billing_settings,
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
from app.services.veyra_auth import (
    VeyraAuthDisabled,
    VeyraAuthError,
    VeyraAuthMisconfigured,
    VeyraAuthUnauthorized,
    VeyraSub2APIClient,
    login_with_ticket,
    verify_session_token,
)
from app.services.veyra_usage import list_veyra_usage
from app.services.visual_review_agent import get_visual_review_agent_status, refresh_visual_review_agent
from app.repositories.memory import utc_now
from app.providers.images import list_v2_image_provider_capabilities
from app.services.output_storage import read_output_content


creative_manager = CreativeManagerRuntime()
_TEMPLATE_RESPONSE_CACHE_MAX = 128
_template_response_cache: OrderedDict[str, tuple[bytes, str]] = OrderedDict()


@asynccontextmanager
async def lifespan(_: FastAPI):
    ensure_runtime_dirs()
    apply_persisted_runtime_model_settings()
    apply_persisted_billing_settings()
    creative_manager.refresh_runtime_config()
    refresh_visual_review_agent()
    bootstrap_v2_repository(seed_cases=True)
    initialize_task_queue()
    startup_sync_task: asyncio.Task | None = None
    resource_sync_task: asyncio.Task | None = None
    resource_sync_stop: asyncio.Event | None = None
    queue_worker_task: asyncio.Task | None = None
    queue_worker_stop: asyncio.Event | None = None
    if settings.sync_github_on_startup:
        startup_sync_task = asyncio.create_task(
            asyncio.to_thread(sync_resource_provider, EVOLINKAI_PROVIDER_ID, "remote")
        )
    if settings.enable_remote_github_sync and settings.resource_sync_interval_minutes > 0:
        resource_sync_stop = asyncio.Event()
        resource_sync_task = asyncio.create_task(
            ResourceSyncScheduler(provider_id=EVOLINKAI_PROVIDER_ID, mode="auto").run_forever(resource_sync_stop)
        )
    if settings.task_queue_inline_worker_enabled:
        queue_worker_stop = asyncio.Event()
        queue_worker_task = asyncio.create_task(
            QueueWorker(creative_manager, worker_id="v2-api-inline-worker").run_forever(queue_worker_stop)
        )
    yield
    if startup_sync_task and not startup_sync_task.done():
        startup_sync_task.cancel()
    await ResourceSyncScheduler.stop(resource_sync_task, resource_sync_stop)
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


@app.get("/api/v2/veyra/auth-policy")
def veyra_auth_policy():
    return {
        "enabled": settings.veyra_auth_enabled,
        "require_ui_auth": settings.veyra_require_ui_auth,
        "login_base_url": settings.veyra_login_base_url,
        "desktop_target": "alchemy",
        "mobile_target": "alchemy-mobile",
        "session_cookie_name": settings.veyra_session_cookie_name,
    }


@app.post("/api/v2/veyra/login")
async def veyra_login(body: dict, response: Response):
    try:
        ticket = str(body.get("ticket") or "").strip()
    except AttributeError:
        ticket = ""
    if not ticket:
        raise HTTPException(status_code=400, detail={"error_code": "veyra_ticket_required", "message": "Ticket is required."})
    try:
        session = await login_with_ticket(ticket)
        _set_veyra_session_cookie(response, str(session.get("access_token") or ""))
        return session
    except VeyraAuthDisabled as exc:
        raise HTTPException(status_code=404, detail={"error_code": exc.code, "message": "Veyra auth is disabled."}) from exc
    except VeyraAuthMisconfigured as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc
    except VeyraAuthUnauthorized as exc:
        raise HTTPException(status_code=401, detail={"error_code": exc.code, "message": "Ticket is invalid or expired."}) from exc
    except VeyraAuthError as exc:
        raise HTTPException(status_code=502, detail={"error_code": exc.code, "message": "Veyra bridge request failed."}) from exc


@app.post("/api/v2/veyra/logout")
def veyra_logout(response: Response):
    _clear_veyra_session_cookie(response)
    return {"ok": True}


@app.post("/api/v2/veyra/session-cookie")
def veyra_session_cookie(request: Request, response: Response, authorization: str = Header(default="")):
    if not settings.veyra_auth_enabled:
        _clear_veyra_session_cookie(response)
        return {"ok": True, "user_id": None, "auth_enabled": False}
    token = _veyra_session_token_from_request(request, authorization)
    user_id = _veyra_user_id_from_request(request, authorization)
    _set_veyra_session_cookie(response, token)
    return {"ok": True, "user_id": user_id}


@app.get("/api/v2/veyra/me")
async def veyra_me(request: Request, authorization: str = Header(default="")):
    if not settings.veyra_auth_enabled:
        raise HTTPException(
            status_code=401,
            detail={"error_code": "veyra_auth_disabled", "message": "Veyra auth is disabled."},
        )
    user_id = _veyra_user_id_from_request(request, authorization)
    try:
        account = await VeyraSub2APIClient().account(user_id)
    except VeyraAuthMisconfigured as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc
    except VeyraAuthError as exc:
        raise HTTPException(status_code=502, detail={"error_code": exc.code, "message": "Veyra bridge request failed."}) from exc
    return {"user": account.__dict__}


@app.get("/api/v2/veyra/history", response_model=ImageHistoryResponse)
async def veyra_history(request: Request, limit: int = Query(default=50, ge=1, le=1000), authorization: str = Header(default="")):
    if not settings.veyra_auth_enabled:
        return list_image_history(limit=limit, veyra_user_id=None, include_legacy_public=True, include_all=True)
    context = await _veyra_request_context(request, authorization)
    return list_image_history(
        limit=limit,
        veyra_user_id=context["user_id"],
        include_legacy_public=True,
        include_all=context["is_admin"],
    )


@app.get("/api/v2/veyra/usage")
def veyra_usage(request: Request, limit: int = Query(default=50, ge=1, le=1000), authorization: str = Header(default="")):
    if not settings.veyra_auth_enabled:
        return {"items": [], "total": 0}
    user_id = _veyra_user_id_from_request(request, authorization)
    return list_veyra_usage(user_id, limit=limit)


@app.get("/api/v2/veyra/billing/settings", response_model=VeyraBillingSettingsResponse)
async def veyra_billing_settings(request: Request, rule_key: str | None = Query(default=None), authorization: str = Header(default="")):
    await _require_veyra_admin(request, authorization)
    return get_billing_settings(rule_key)


@app.get("/api/v2/veyra/billing/settings/public", response_model=VeyraBillingSettingsResponse)
def public_veyra_billing_settings(rule_key: str | None = Query(default=None)):
    return get_billing_settings(rule_key)


@app.post("/api/v2/veyra/billing/settings", response_model=VeyraBillingSettingsResponse)
async def update_veyra_billing_settings(
    body: VeyraBillingSettingsRequest,
    request: Request,
    authorization: str = Header(default=""),
):
    await _require_veyra_admin(request, authorization)
    return update_billing_settings(body)


def _set_veyra_session_cookie(response: Response, token: str) -> None:
    if not token:
        return
    response.set_cookie(
        settings.veyra_session_cookie_name,
        token,
        max_age=settings.veyra_session_ttl_seconds,
        path="/",
        httponly=True,
        secure=settings.veyra_session_cookie_secure,
        samesite="lax",
    )


def _clear_veyra_session_cookie(response: Response) -> None:
    response.delete_cookie(
        settings.veyra_session_cookie_name,
        path="/",
        secure=settings.veyra_session_cookie_secure,
        httponly=True,
        samesite="lax",
    )


def _veyra_session_token_from_request(request: Request, authorization: str = "") -> str:
    scheme, _, token = str(authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return str(request.cookies.get(settings.veyra_session_cookie_name) or "").strip()


def _veyra_user_id_from_request(request: Request, authorization: str = "") -> int:
    token = _veyra_session_token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail={"error_code": "veyra_session_required", "message": "Veyra session is required."})
    try:
        return verify_session_token(token)
    except VeyraAuthUnauthorized as exc:
        raise HTTPException(status_code=401, detail={"error_code": exc.code, "message": "Veyra session is invalid."}) from exc
    except (VeyraAuthDisabled, VeyraAuthMisconfigured) as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc


def _require_veyra_user_if_enabled(request: Request, authorization: str = "") -> int | None:
    if not settings.veyra_auth_enabled:
        return None
    return _veyra_user_id_from_request(request, authorization)


async def _veyra_request_context(request: Request, authorization: str = "") -> dict:
    user_id = _veyra_user_id_from_request(request, authorization)
    try:
        account = await VeyraSub2APIClient().account(user_id)
    except VeyraAuthMisconfigured as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc
    except VeyraAuthError as exc:
        raise HTTPException(status_code=502, detail={"error_code": exc.code, "message": "Veyra bridge request failed."}) from exc
    return {"user_id": user_id, "account": account, "is_admin": str(account.role).lower() == "admin"}


async def _require_veyra_admin(request: Request, authorization: str = ""):
    context = await _veyra_request_context(request, authorization)
    account = context["account"]
    if str(account.role).lower() != "admin":
        raise HTTPException(status_code=403, detail={"error_code": "veyra_admin_required", "message": "Veyra admin role is required."})
    return account


def _with_veyra_user(body: CreateCreativeRunRequest, request: Request, authorization: str) -> CreateCreativeRunRequest:
    if not settings.veyra_auth_enabled:
        return body.model_copy(update={"veyra_user_id": None})
    return body.model_copy(update={"veyra_user_id": _veyra_user_id_from_request(request, authorization)})


def _uploaded_asset_owner_id(asset_id: str) -> int | None:
    asset = get_uploaded_asset(asset_id)
    if not asset:
        return None
    try:
        owner_id = int(getattr(asset, "veyra_user_id", None) or 0)
    except (TypeError, ValueError):
        return None
    return owner_id if owner_id > 0 else None


def _require_uploaded_asset_visible(request: Request, asset_id: str, authorization: str = "") -> dict:
    asset = get_uploaded_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    if not settings.veyra_auth_enabled:
        return {"user_id": None, "is_admin": False, "owner_id": _uploaded_asset_owner_id(asset_id)}
    user_id = _veyra_user_id_from_request(request, authorization)
    owner_id = _uploaded_asset_owner_id(asset_id)
    if owner_id is None or owner_id == user_id:
        return {"user_id": user_id, "is_admin": False, "owner_id": owner_id}
    raise HTTPException(status_code=403, detail={"error_code": "veyra_asset_forbidden", "message": "Uploaded asset is not visible to this account."})


def _require_creative_asset_count(raw_assets) -> None:
    seen: set[str] = set()
    for item in raw_assets or []:
        asset_id = item if isinstance(item, str) else getattr(item, "asset_id", "")
        clean = str(asset_id or "").strip()
        if clean:
            seen.add(clean)
    if len(seen) > settings.max_uploaded_asset_count:
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": "asset_count_exceeded",
                "message": f"最多可绑定 {settings.max_uploaded_asset_count} 张上传素材。",
            },
        )


def _image_job_with_veyra_user(body: CreateImageJobRequest, request: Request, authorization: str) -> CreateImageJobRequest:
    if not settings.veyra_auth_enabled:
        return body.model_copy(update={"veyra_user_id": None})
    return body.model_copy(update={"veyra_user_id": _veyra_user_id_from_request(request, authorization)})


def _v2_output_owner_id(output_id: str) -> int | None:
    output = repository.get_output(output_id)
    metadata = output.metadata if output else {}
    if not metadata:
        from app.services.image_history import get_image_history_item

        item = get_image_history_item(output_id)
        metadata = item.metadata if item else {}
    try:
        owner_id = int((metadata or {}).get("veyra_user_id") or 0)
    except (TypeError, ValueError):
        return None
    return owner_id if owner_id > 0 else None


async def _require_output_visible(request: Request, output_id: str, authorization: str = "", *, allow_legacy_public: bool = True) -> dict:
    if not settings.veyra_auth_enabled:
        return {"user_id": None, "is_admin": False, "owner_id": _v2_output_owner_id(output_id)}
    context = await _veyra_request_context(request, authorization)
    owner_id = _v2_output_owner_id(output_id)
    if context["is_admin"] or owner_id == context["user_id"] or (allow_legacy_public and owner_id is None):
        return {**context, "owner_id": owner_id}
    raise HTTPException(status_code=403, detail={"error_code": "veyra_output_forbidden", "message": "Output is not visible to this account."})


@app.post("/api/v2/creative/runs", status_code=202)
async def create_creative_run(body: CreateCreativeRunRequest, request: Request, authorization: str = Header(default="")):
    _require_creative_asset_count(body.assets)
    return await creative_manager.run(_with_veyra_user(body, request, authorization))


@app.post("/api/v2/creative/runs/async", status_code=202)
async def create_creative_run_async(body: CreateCreativeRunRequest, request: Request, authorization: str = Header(default="")):
    _require_creative_asset_count(body.assets)
    body = _with_veyra_user(body, request, authorization)
    queued = creative_manager.queue_run(body)
    enqueue_creative_task(kind="creative_run", request_payload=body.model_dump(mode="json"), queued_run=queued)
    return queued


@app.post("/api/v2/uploads", response_model=CreateUploadedAssetResponse)
def create_upload(body: CreateUploadedAssetRequest, request: Request, authorization: str = Header(default="")) -> CreateUploadedAssetResponse:
    user_id = _require_veyra_user_if_enabled(request, authorization)
    return create_uploaded_asset(body, veyra_user_id=user_id)


@app.put("/api/v2/uploads/{asset_id}/content")
def put_upload_content(asset_id: str, body: AssetContentUploadRequest, request: Request, authorization: str = Header(default="")):
    _require_uploaded_asset_visible(request, asset_id, authorization)
    asset = store_uploaded_asset_content(asset_id, body)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    if asset.status == "failed":
        error = asset.error or {}
        raise HTTPException(
            status_code=400,
            detail={
                "error_code": error.get("code") or "invalid_asset_content",
                "message": error.get("message") or "Asset content is invalid.",
            },
        )
    return asset


@app.post("/api/v2/uploads/{asset_id}/complete")
def complete_upload(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_uploaded_asset_visible(request, asset_id, authorization)
    asset = complete_uploaded_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    return asset


@app.get("/api/v2/uploads/{asset_id}")
def upload_detail(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_uploaded_asset_visible(request, asset_id, authorization)
    asset = get_uploaded_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_not_found", "message": "Uploaded asset not found."})
    return asset


@app.get("/api/v2/uploads/{asset_id}/content")
def upload_content(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_uploaded_asset_visible(request, asset_id, authorization)
    asset = read_uploaded_asset_content(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "asset_content_not_found", "message": "Uploaded asset content not found."})
    content, media_type = asset
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/v2/orchestrator/status")
def orchestrator_status(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return get_orchestrator_status()


@app.get("/api/v2/task-queue/status")
def task_queue_status(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return task_queue_stats()


@app.get("/api/v2/review-agent/status")
def review_agent_status(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return get_visual_review_agent_status()


@app.get("/api/v2/provider-capabilities")
async def provider_capabilities(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return {"providers": [item.model_dump(mode="json") for item in await list_v2_image_provider_capabilities()]}


@app.get("/api/v2/runtime/model-settings", response_model=V2RuntimeModelSettingsResponse)
def runtime_model_settings(request: Request, authorization: str = Header(default="")) -> V2RuntimeModelSettingsResponse:
    _require_veyra_user_if_enabled(request, authorization)
    return get_runtime_model_settings()


@app.post("/api/v2/runtime/model-settings", response_model=V2RuntimeModelSettingsResponse)
def update_model_settings(body: V2RuntimeModelSettingsRequest, request: Request, authorization: str = Header(default="")) -> V2RuntimeModelSettingsResponse:
    _require_veyra_user_if_enabled(request, authorization)
    updated = update_runtime_model_settings(body)
    creative_manager.refresh_runtime_config()
    refresh_visual_review_agent()
    return updated


@app.get("/api/v2/creative/runs/{run_id}")
def get_creative_run(run_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    run = get_run_snapshot(run_id) or repository.get_creative_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail={"error_code": "run_not_found", "message": "Creative run not found."})
    return run


@app.post("/api/v2/prompt-cases/search")
def search_cases(body: SearchPromptCasesRequest, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return search_prompt_cases(body)


@app.get("/api/v2/case-profiles/{case_id}")
def case_profile(case_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    case = get_prompt_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error_code": "case_not_found", "message": "Prompt case not found."})
    return build_case_profile(case)


@app.get("/api/v2/prompt-cases/{case_id}")
def get_case(case_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    case = get_prompt_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail={"error_code": "case_not_found", "message": "Prompt case not found."})
    return case


@app.get("/api/v2/templates")
def templates(
    request: Request,
    category: str | None = None,
    use_case: str | None = None,
    limit: int = Query(default=24, ge=1, le=1000),
    authorization: str = Header(default=""),
):
    _require_veyra_user_if_enabled(request, authorization)
    return {"templates": list_templates(category=category, use_case=use_case, limit=limit)}


@app.get("/api/v2/templates/index")
def templates_index(request: Request, authorization: str = Header(default=""), if_none_match: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    index_version = repository.get_active_index_version() or "none"
    return _cacheable_template_response(
        f"template:index:{index_version}",
        lambda: case_intelligence.list_template_index(),
        if_none_match=if_none_match,
    )


@app.get("/api/v2/templates/page")
def templates_page(
    request: Request,
    category: str | None = None,
    use_case: str | None = None,
    facet: str | None = None,
    cursor: str | None = None,
    limit: int = Query(default=24, ge=1, le=96),
    authorization: str = Header(default=""),
    if_none_match: str = Header(default=""),
):
    _require_veyra_user_if_enabled(request, authorization)
    index_version = repository.get_active_index_version() or "none"
    return _cacheable_template_response(
        _template_page_cache_key(
            index_version=index_version,
            category=category,
            use_case=use_case,
            facet=facet,
            cursor=cursor,
            limit=limit,
        ),
        lambda: case_intelligence.list_templates_page(category=category, use_case=use_case, facet=facet, cursor=cursor, limit=limit),
        if_none_match=if_none_match,
    )


def _cacheable_template_response(cache_key: str, payload_factory, *, if_none_match: str = "") -> Response:
    body, etag = _cached_template_body(cache_key, payload_factory)
    headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=300, stale-while-revalidate=86400",
        "Vary": "Authorization, Cookie",
    }
    if _etag_matches(if_none_match, etag):
        return Response(status_code=304, headers=headers)
    return Response(content=body, media_type="application/json", headers=headers)


def _cached_template_body(cache_key: str, payload_factory) -> tuple[bytes, str]:
    cached = _template_response_cache.get(cache_key)
    if cached:
        _template_response_cache.move_to_end(cache_key)
        return cached
    payload = payload_factory()
    body = json.dumps(jsonable_encoder(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    etag = f'"v2-templates-{hashlib.sha1(body).hexdigest()}"'
    _template_response_cache[cache_key] = (body, etag)
    _template_response_cache.move_to_end(cache_key)
    while len(_template_response_cache) > _TEMPLATE_RESPONSE_CACHE_MAX:
        _template_response_cache.popitem(last=False)
    return body, etag


def _template_page_cache_key(
    *,
    index_version: str,
    category: str | None,
    use_case: str | None,
    facet: str | None,
    cursor: str | None,
    limit: int,
) -> str:
    parts = ["template:page", index_version, category or "", use_case or "", facet or "", cursor or "", str(limit)]
    return ":".join(part.replace(":", "%3A") for part in parts)


def _etag_matches(if_none_match: str, etag: str) -> bool:
    if not if_none_match:
        return False
    return any(candidate.strip() in {etag, "*"} for candidate in if_none_match.split(","))


@app.get("/api/v2/case-assets/{asset_path:path}")
def case_asset(asset_path: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    asset = read_case_asset(asset_path)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "case_asset_not_found", "message": "Case asset not found."})
    content, media_type = asset
    return Response(content=content, media_type=media_type)


@app.get("/api/v2/case-thumbnails/{asset_path:path}")
def case_thumbnail(asset_path: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    variant, normalized_asset_path = _case_thumbnail_request(asset_path)
    asset = read_case_thumbnail(normalized_asset_path, variant=variant)
    if not asset:
        raise HTTPException(status_code=404, detail={"error_code": "case_thumbnail_not_found", "message": "Case thumbnail not found."})
    content, media_type = asset
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


def _case_thumbnail_request(asset_path: str) -> tuple[str, str]:
    normalized = (asset_path or "").replace("\\", "/").lstrip("/")
    for variant in ("grid", "preview"):
        prefix = f"{variant}/"
        if normalized.startswith(prefix):
            return variant, normalized[len(prefix) :]
    return "grid", normalized


@app.get("/api/v2/resource-providers")
def resource_providers(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return {"providers": list_resource_providers()}


@app.post("/api/v2/resource-providers/{provider_id}/sync", status_code=202)
def request_provider_sync(provider_id: str, request: Request, mode: str = Query(default="auto", pattern="^(auto|seed|remote)$"), authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    try:
        return sync_resource_provider(provider_id, mode=mode)  # type: ignore[arg-type]
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error_code": "provider_not_found", "message": str(exc)},
        ) from exc


@app.get("/api/v2/resource-providers/{provider_id}/sync-runs/{sync_run_id}")
def provider_sync_run(provider_id: str, sync_run_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    run = get_sync_run(sync_run_id)
    if not run or run.provider_id != provider_id:
        raise HTTPException(status_code=404, detail={"error_code": "sync_run_not_found", "message": "Sync run not found."})
    return run


@app.post("/api/v2/image/jobs", status_code=202)
async def image_job(body: CreateImageJobRequest, request: Request, authorization: str = Header(default="")):
    return await create_image_job(_image_job_with_veyra_user(body, request, authorization))


@app.get("/api/v2/image/history", response_model=ImageHistoryResponse)
async def image_history(request: Request, limit: int = Query(default=50, ge=1, le=1000), authorization: str = Header(default="")):
    if not settings.veyra_auth_enabled:
        return list_image_history(limit=limit)
    context = await _veyra_request_context(request, authorization)
    return list_image_history(
        limit=limit,
        veyra_user_id=context["user_id"],
        include_legacy_public=True,
        include_all=context["is_admin"],
    )


@app.get("/api/v2/image/history/{output_id}/thumbnail")
async def image_history_thumbnail(output_id: str, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization)
    thumbnail = read_history_thumbnail(output_id)
    if not thumbnail:
        raise HTTPException(status_code=404, detail={"error_code": "history_thumbnail_not_found", "message": "History thumbnail not found."})
    content, media_type = thumbnail
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "public, max-age=31536000, immutable"})


@app.delete("/api/v2/image/history/{output_id}")
async def delete_history_item(output_id: str, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization, allow_legacy_public=False)
    result = delete_image_history_item(output_id)
    if not result.get("ok"):
        raise HTTPException(
            status_code=404,
            detail={"error_code": "history_output_not_found", "message": "V2 history output not found."},
        )
    return result


@app.get("/api/v2/image/jobs/{job_id}")
def get_image_job(job_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    job = repository.get_image_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error_code": "job_not_found", "message": "Image job not found."})
    return job


@app.get("/api/v2/outputs/{output_id}/download")
async def output_download(output_id: str, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization)
    output = read_output_content(output_id)
    if not output:
        raise HTTPException(status_code=404, detail={"error_code": "output_not_found", "message": "V2 output file not found."})
    content, media_type = output
    return Response(content=content, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.post("/api/v2/outputs/{output_id}/feedback", status_code=201, response_model=FeedbackEvent)
async def output_feedback(output_id: str, body: CreateFeedbackRequest, request: Request, authorization: str = Header(default="")) -> FeedbackEvent:
    await _require_output_visible(request, output_id, authorization)
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
async def output_revision(output_id: str, body: CreateRevisionRunRequest, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization)
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
async def output_revision_async(output_id: str, body: CreateRevisionRunRequest, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization)
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
