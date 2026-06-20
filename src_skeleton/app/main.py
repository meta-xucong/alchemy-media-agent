from __future__ import annotations

from io import BytesIO
from datetime import datetime, timezone
import hashlib
import httpx
import logging
from html import escape
from pathlib import Path
import textwrap
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response, StreamingResponse
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
    FavoriteImageRequest,
    ImageHistoryItem,
    ImageHistoryResponse,
    MessageRequest,
    ReviseImageRequest,
    RuntimeProviderSettingsRequest,
    RuntimeProviderSettingsResponse,
)
from app.services.asset_service import complete_asset_upload, create_asset_mask, create_asset_upload, get_asset, store_asset_content
from app.services.alchemy_lab import (
    LAB_PROJECT_ID,
    ExplorationRequest,
    FavoriteSelection,
    comparison_board,
    create_exploration_session,
    get_exploration_session,
    is_lab_history_record,
    list_lab_history,
    list_lab_modules,
    list_style_presets,
    public_exploration_session,
    update_favorites,
)
from app.services.alchemy_lab_style_search import SearchLabStylesRequest, search_lab_styles
from app.services.alchemy_lab_uploads import (
    complete_lab_upload,
    create_lab_upload,
    get_lab_upload,
    read_lab_upload_content,
    store_lab_upload_content,
)
from app.services.alchemy_lab_uploads_models import CreateLabUploadRequest, LabAssetContentUploadRequest
from app.services.events import format_sse_events
from app.services.favorites import delete_favorite, list_favorite_ids, set_favorite
from app.services.image_service import run_submitted_image_job, submit_image_job, submit_revise_image_job
from app.services.session_service import create_session, handle_message
from app.services.veyra_auth import (
    VeyraAuthDisabled,
    VeyraAuthError,
    VeyraAuthMisconfigured,
    VeyraAuthUnauthorized,
    load_account,
    verify_session_token,
)
from app.services.veyra_usage import list_veyra_usage
from app.services.video_service import create_video_job
from app.storage import media_store

app = FastAPI(title="Custom Media Agent API", version="0.1.0")
logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).resolve().parent / "static"
MOBILE_STATIC_DIR = Path(__file__).resolve().parent / "mobile_static"
IMMUTABLE_IMAGE_HEADERS = {"Cache-Control": "public, max-age=31536000, immutable"}
V2_BRIDGE_PROJECT_ID = "alchemy_v2_bridge"
V2_IDEMPOTENCY_PREFIX = "v2:"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.mount("/mobile-static", StaticFiles(directory=MOBILE_STATIC_DIR), name="mobile_static")


@app.get("/")
def frontend_app(request: Request):
    gate = _veyra_page_gate(request, target="alchemy")
    if gate:
        return gate
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/h5")
@app.get("/mobile")
def mobile_frontend_app(request: Request):
    gate = _veyra_page_gate(request, target="alchemy-mobile")
    if gate:
        return gate
    return FileResponse(MOBILE_STATIC_DIR / "index.html")


@app.get("/admin/billing")
def billing_admin_app(request: Request):
    return FileResponse(STATIC_DIR / "billing-admin.html")


@app.get("/share/image", response_class=HTMLResponse)
def image_share_landing(
    request: Request,
    image: str = Query(default=""),
    thumb: str | None = Query(default=None),
    title: str = Query(default="Alchemy 生成图片"),
    desc: str = Query(default="来自 Alchemy Media Agent 的 AI 影像作品。"),
):
    image_url = _safe_public_share_url(request, image, fallback="/static/showcase/city-poster.jpg")
    thumb_url = _safe_public_share_url(request, thumb or image, fallback="/static/showcase/city-poster.jpg")
    page_url = str(request.url)
    safe_title = _share_text(title, "Alchemy 生成图片", 48)
    safe_desc = _share_text(desc, "来自 Alchemy Media Agent 的 AI 影像作品。", 88)
    save_image_url = _share_save_image_url(request, image_url=thumb_url)
    return HTMLResponse(
        _share_image_html(
            title=safe_title,
            desc=safe_desc,
            page_url=page_url,
            image_url=image_url,
            thumb_url=save_image_url,
        )
    )


@app.get("/share/save-image")
def image_share_save_image(
    request: Request,
    image: str = Query(default=""),
):
    image_url = _safe_public_share_url(request, image, fallback="/static/showcase/city-poster.jpg")
    cache_path = _share_save_image_cache_path(image_url)
    if not cache_path.exists():
        _write_share_save_image(request, image_url, cache_path)
    headers = {
        "Cache-Control": "public, max-age=31536000, immutable",
        "Content-Disposition": 'inline; filename="alchemy-share-image.jpg"',
    }
    return FileResponse(cache_path, media_type="image/jpeg", headers=headers)


@app.get("/share/poster")
def image_share_poster(
    request: Request,
    image: str = Query(default=""),
    thumb: str | None = Query(default=None),
    title: str = Query(default="Alchemy Media Agent"),
    desc: str = Query(default="来自 Alchemy Media Agent 的 AI 影像作品。"),
    url: str | None = Query(default=None),
):
    safe_title = _share_text(title, "Alchemy Media Agent", 42)
    safe_desc = _share_text(desc, "扫码查看原图", 18)
    direct_image_url = _safe_public_share_url(request, image, fallback="/static/showcase/city-poster.jpg")
    direct_thumb_url = _safe_public_share_url(request, thumb or image, fallback="/static/showcase/city-poster.jpg")
    default_share_url = _share_image_url(
        request,
        image_url=direct_image_url,
        thumb_url=direct_thumb_url,
        title=safe_title,
        desc="来自 Alchemy Media Agent 的 AI 影像作品。",
    )
    share_url = _safe_public_share_url(request, url, fallback="/share/image") if url else default_share_url
    if "/share/save-image?" in share_url:
        _ensure_share_save_image_cached(request, share_url)
    poster = _render_share_poster(
        request=request,
        image_value=thumb or image,
        title=safe_title,
        desc=safe_desc,
        share_url=share_url,
    )
    headers = {
        "Cache-Control": "public, max-age=86400",
        "Content-Disposition": 'inline; filename="alchemy-share-poster.png"',
    }
    return StreamingResponse(BytesIO(poster), media_type="image/png", headers=headers)


@app.get("/healthz")
def healthz():
    return {"ok": True, "service": "custom-media-agent", "version": app.version}


@app.get("/api/lab/modules")
def list_lab_modules_endpoint(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return list_lab_modules()


@app.get("/api/lab/rare-style-explorer/styles")
def list_rare_style_explorer_styles(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return list_style_presets()


@app.post("/api/lab/rare-style-explorer/styles/search")
async def search_rare_style_explorer_styles(body: SearchLabStylesRequest, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    presets = list_style_presets()["styles"]
    return await search_lab_styles(body, presets)


@app.get("/api/lab/history")
def list_alchemy_lab_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000),
    include_mock: bool = Query(default=False),
    authorization: str = Header(default=""),
):
    _require_veyra_user_if_enabled(request, authorization)
    return list_lab_history(limit=limit, include_mock=include_mock)


@app.post("/api/lab/uploads")
def create_lab_upload_endpoint(body: CreateLabUploadRequest, request: Request, authorization: str = Header(default="")):
    user_id = _veyra_user_id_from_request(request, authorization)
    return create_lab_upload(body, veyra_user_id=user_id)


@app.put("/api/lab/uploads/{asset_id}/content")
def put_lab_upload_content_endpoint(asset_id: str, body: LabAssetContentUploadRequest, request: Request, authorization: str = Header(default="")):
    _require_lab_upload_visible(request, asset_id, authorization)
    asset = store_lab_upload_content(asset_id, body)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "lab_asset_not_found", "message": "Reference image not found."})
    if asset.status == "failed":
        error = asset.error or {}
        raise HTTPException(
            status_code=400,
            detail={"code": error.get("code") or "invalid_lab_asset", "message": error.get("message") or "Reference image is invalid."},
        )
    return asset


@app.post("/api/lab/uploads/{asset_id}/complete")
def complete_lab_upload_endpoint(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_lab_upload_visible(request, asset_id, authorization)
    asset = complete_lab_upload(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "lab_asset_not_found", "message": "Reference image not found."})
    return asset


@app.get("/api/lab/uploads/{asset_id}")
def get_lab_upload_endpoint(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_lab_upload_visible(request, asset_id, authorization)
    asset = get_lab_upload(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "lab_asset_not_found", "message": "Reference image not found."})
    return asset


@app.get("/api/lab/uploads/{asset_id}/content")
def get_lab_upload_content_endpoint(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_lab_upload_visible(request, asset_id, authorization)
    content = read_lab_upload_content(asset_id)
    if not content:
        raise HTTPException(status_code=404, detail={"code": "lab_asset_content_not_found", "message": "Reference image content not found."})
    data, media_type = content
    return Response(content=data, media_type=media_type, headers={"Cache-Control": "private, max-age=3600"})


@app.get("/api/lab/rare-style-explorer/history")
def list_rare_style_explorer_history(
    request: Request,
    limit: int = Query(default=50, ge=1, le=1000),
    include_mock: bool = Query(default=False),
    authorization: str = Header(default=""),
):
    return list_alchemy_lab_history(request=request, limit=limit, include_mock=include_mock, authorization=authorization)


@app.post("/api/lab/rare-style-explorer/sessions")
async def create_rare_style_explorer_session(
    body: ExplorationRequest,
    request: Request,
    authorization: str = Header(default=""),
):
    user_id = _veyra_user_id_from_request(request, authorization)
    try:
        session = await create_exploration_session(body, veyra_user_id=user_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "invalid_exploration_request", "message": str(exc)}) from exc
    return {"session": public_exploration_session(session), "board": comparison_board(session), "async": session.status not in {"completed", "partial_success", "failed"}}


@app.get("/api/lab/rare-style-explorer/sessions/{session_id}")
def get_rare_style_explorer_session(session_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    session = get_exploration_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "exploration_session_not_found", "message": "Exploration session not found."})
    return {"session": public_exploration_session(session), "board": comparison_board(session)}


@app.post("/api/lab/rare-style-explorer/sessions/{session_id}/favorites")
def update_rare_style_explorer_favorites(
    session_id: str,
    body: FavoriteSelection,
    request: Request,
    authorization: str = Header(default=""),
):
    _require_veyra_user_if_enabled(request, authorization)
    session = update_favorites(session_id, body)
    if not session:
        raise HTTPException(status_code=404, detail={"code": "exploration_session_not_found", "message": "Exploration session not found."})
    return {"session": public_exploration_session(session), "board": comparison_board(session)}


@app.api_route("/api/v2/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_v2_api(path: str, request: Request):
    return await _proxy_v2_request(path, request)


def _veyra_return_router_url(target: str) -> str:
    base_url = (settings.veyra_login_base_url or "https://aiself.vip").rstrip("/")
    return base_url + "/_veyra/return?" + urlencode({"target": target})


def _veyra_page_gate(request: Request, *, target: str) -> RedirectResponse | None:
    if not settings.veyra_auth_enabled or not settings.veyra_require_ui_auth:
        return None
    if request.query_params.get("ticket"):
        return None
    token = _veyra_session_token_from_request(request)
    if token:
        try:
            verify_session_token(token)
            return None
        except VeyraAuthUnauthorized:
            pass
        except (VeyraAuthDisabled, VeyraAuthMisconfigured) as exc:
            raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc
        except VeyraAuthError as exc:
            raise HTTPException(status_code=502, detail={"error_code": exc.code, "message": "Veyra auth failed."}) from exc
    return RedirectResponse(_veyra_return_router_url(target), status_code=307)


def _veyra_session_token_from_request(request: Request, authorization: str = "") -> str:
    scheme, _, token = str(authorization or "").partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        return token.strip()
    return str(request.cookies.get(settings.veyra_session_cookie_name) or "").strip()


def _veyra_user_id_from_request(request: Request, authorization: str = "") -> int | None:
    if not settings.veyra_auth_enabled:
        return None
    token = _veyra_session_token_from_request(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail={"error_code": "veyra_session_required", "message": "Veyra session is required."})
    try:
        return verify_session_token(token)
    except VeyraAuthUnauthorized as exc:
        raise HTTPException(status_code=401, detail={"error_code": exc.code, "message": "Veyra session is invalid."}) from exc
    except (VeyraAuthDisabled, VeyraAuthMisconfigured) as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc
    except VeyraAuthError as exc:
        raise HTTPException(status_code=502, detail={"error_code": exc.code, "message": "Veyra auth failed."}) from exc


def _require_veyra_user_if_enabled(request: Request, authorization: str = "") -> int | None:
    if not settings.veyra_auth_enabled:
        return None
    return _veyra_user_id_from_request(request, authorization)


async def _veyra_history_context(request: Request, authorization: str = "") -> dict:
    if not settings.veyra_auth_enabled:
        return {"authenticated": False, "user_id": None, "is_admin": False}
    user_id = _veyra_user_id_from_request(request, authorization)
    account = await _veyra_account(user_id)
    return {"authenticated": True, "user_id": user_id, "is_admin": _is_veyra_admin_account(account)}


async def _veyra_account(user_id: int):
    try:
        return await load_account(user_id)
    except VeyraAuthMisconfigured as exc:
        raise HTTPException(status_code=503, detail={"error_code": exc.code, "message": "Veyra auth is not configured."}) from exc
    except VeyraAuthError as exc:
        raise HTTPException(status_code=502, detail={"error_code": exc.code, "message": "Veyra bridge request failed."}) from exc


def _is_veyra_admin_account(account) -> bool:
    return str(getattr(account, "role", "") or "").lower() == "admin"


async def _proxy_v2_request(path: str, request: Request) -> Response:
    target_url = _v2_proxy_target_url(path, str(request.url.query))
    headers = _v2_proxy_request_headers(request)
    body = await request.body()
    timeout = httpx.Timeout(settings.v2_api_proxy_timeout_seconds, connect=8.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            upstream = await client.request(
                request.method,
                target_url,
                content=body,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.warning("V2 API proxy failed for %s: %s", target_url, exc)
        raise HTTPException(
            status_code=502,
            detail={"code": "v2_proxy_unavailable", "message": "V2 local API is not reachable."},
        ) from exc
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=_v2_proxy_response_headers(upstream.headers),
        media_type=upstream.headers.get("content-type"),
    )


def _v2_proxy_target_url(path: str, query: str = "") -> str:
    clean_path = str(path or "").lstrip("/")
    target = f"{settings.v2_api_proxy_base_url}/api/v2/{clean_path}"
    return f"{target}?{query}" if query else target


def _v2_proxy_request_headers(request: Request) -> dict[str, str]:
    excluded = {
        "host",
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-length",
    }
    return {key: value for key, value in request.headers.items() if key.lower() not in excluded}


def _v2_proxy_response_headers(headers: httpx.Headers) -> dict[str, str]:
    excluded = {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "content-encoding",
        "content-length",
    }
    return {key: value for key, value in headers.items() if key.lower() not in excluded}


def _asset_owner_id(asset_id: str) -> int | None:
    asset = get_asset(asset_id)
    if not asset:
        return None
    return _positive_int_or_none(getattr(asset, "veyra_user_id", None))


def _require_asset_visible(request: Request, asset_id: str, authorization: str = "") -> dict:
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    if not settings.veyra_auth_enabled:
        return {"authenticated": False, "user_id": None, "is_admin": False, "owner_id": _asset_owner_id(asset_id)}
    context = _veyra_asset_context(request, authorization)
    owner_id = _asset_owner_id(asset_id)
    if context.get("is_admin") or owner_id == context.get("user_id") or owner_id is None:
        return {**context, "owner_id": owner_id}
    raise HTTPException(status_code=403, detail={"error_code": "veyra_asset_forbidden", "message": "Asset is not visible to this account."})


def _require_lab_upload_visible(request: Request, asset_id: str, authorization: str = "") -> dict:
    asset = get_lab_upload(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "lab_asset_not_found", "message": "Reference image not found."})
    owner_id = _positive_int_or_none(getattr(asset, "veyra_user_id", None))
    if not settings.veyra_auth_enabled:
        return {"authenticated": False, "user_id": None, "is_admin": False, "owner_id": owner_id}
    context = _veyra_asset_context(request, authorization)
    if context.get("is_admin") or owner_id == context.get("user_id") or owner_id is None:
        return {**context, "owner_id": owner_id}
    raise HTTPException(status_code=403, detail={"error_code": "lab_asset_forbidden", "message": "Reference image is not visible to this account."})


def _require_job_assets_visible(
    request: Request,
    asset_ids: list[str] | None,
    asset_intents: list[AssetIntent] | None,
    authorization: str = "",
) -> None:
    seen: set[str] = set()
    for asset_id in [*(asset_ids or []), *(intent.asset_id for intent in (asset_intents or []))]:
        clean = str(asset_id or "").strip()
        if not clean or clean in seen:
            continue
        seen.add(clean)
    if len(seen) > settings.max_asset_upload_count:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "asset_count_exceeded",
                "message": f"最多可绑定 {settings.max_asset_upload_count} 张上传素材。",
            },
        )
    if not settings.veyra_auth_enabled:
        return
    for clean in seen:
        _require_asset_visible(request, clean, authorization)


def _veyra_asset_context(request: Request, authorization: str = "") -> dict:
    user_id = _veyra_user_id_from_request(request, authorization)
    return {"authenticated": True, "user_id": user_id, "is_admin": False}


def _v1_output_owner_id(output_id: str) -> int | None:
    output = repository.get_output(output_id)
    if output:
        owner_id = _history_output_veyra_user_id(output.metadata)
        if owner_id is not None:
            return owner_id
    for record in media_store.list_history_records(limit=10000):
        if record.get("id") == output_id:
            return _positive_int_or_none(record.get("veyra_user_id"))
    return None


def _v1_history_output_exists(output_id: str) -> bool:
    output = repository.get_output(output_id)
    if output:
        job = repository.get_job(output.job_id)
        if job and not _is_non_v1_history_job(job):
            return True
        return False
    for record in media_store.list_history_records(limit=10000):
        if record.get("id") == output_id and not _is_non_v1_history_record(record):
            return True
    for record in media_store.list_generated_output_records(limit=10000):
        if record.get("id") == output_id and not _is_non_v1_history_record(record):
            return True
    return False


def _is_lab_output_id(output_id: str) -> bool:
    for record in media_store.list_history_records(limit=10000):
        if record.get("id") == output_id:
            return is_lab_history_record(record)
    return False


async def _require_output_visible(request: Request, output_id: str, authorization: str = "", *, allow_legacy_public: bool = True) -> dict:
    if not settings.veyra_auth_enabled:
        return {"authenticated": False, "user_id": None, "is_admin": False, "owner_id": _v1_output_owner_id(output_id)}
    context = await _veyra_history_context(request, authorization)
    owner_id = _v1_output_owner_id(output_id)
    if context.get("is_admin") or owner_id == context.get("user_id") or (allow_legacy_public and _is_lab_output_id(output_id)) or (allow_legacy_public and owner_id is None):
        return {**context, "owner_id": owner_id}
    raise HTTPException(status_code=403, detail={"error_code": "veyra_output_forbidden", "message": "Output is not visible to this account."})


@app.post("/v1/sessions")
def create_session_endpoint(body: CreateSessionRequest, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return create_session(body)


@app.post("/v1/sessions/{session_id}/messages")
async def send_message(session_id: str, body: MessageRequest, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return await handle_message(session_id, body)


@app.get("/v1/sessions/{session_id}/events")
def stream_session_events(session_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return StreamingResponse(format_sse_events(session_id), media_type="text/event-stream")


@app.post("/v1/assets/upload-url")
def create_asset_upload_endpoint(body: CreateAssetUploadRequest, request: Request, authorization: str = Header(default="")):
    user_id = _require_veyra_user_if_enabled(request, authorization)
    return create_asset_upload(body, veyra_user_id=user_id)


@app.put("/v1/assets/{asset_id}/content")
def put_asset_content_endpoint(asset_id: str, body: AssetContentUploadRequest, request: Request, authorization: str = Header(default="")):
    _require_asset_visible(request, asset_id, authorization)
    asset = store_asset_content(asset_id, body)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    if asset.status == "failed":
        error = asset.error or {}
        raise HTTPException(
            status_code=400,
            detail={
                "code": error.get("code") or "invalid_asset_content",
                "message": error.get("message") or "Asset content is not valid base64.",
            },
        )
    return asset


@app.get("/v1/assets/{asset_id}/content")
def get_asset_content_endpoint(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_asset_visible(request, asset_id, authorization)
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    path = media_store.find_asset_file(asset_id)
    if not path:
        raise HTTPException(status_code=404, detail={"code": "asset_content_not_found", "message": "Asset content not found."})
    return FileResponse(path, media_type=asset.mime_type)


@app.post("/v1/assets/{asset_id}/complete")
def complete_asset_upload_endpoint(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_asset_visible(request, asset_id, authorization)
    asset = complete_asset_upload(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return asset


@app.get("/v1/assets/{asset_id}")
def get_asset_endpoint(asset_id: str, request: Request, authorization: str = Header(default="")):
    _require_asset_visible(request, asset_id, authorization)
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return asset


@app.put("/v1/assets/{asset_id}/intent")
def set_asset_intent_endpoint(asset_id: str, body: AssetIntent, request: Request, authorization: str = Header(default="")):
    _require_asset_visible(request, asset_id, authorization)
    asset = get_asset(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return body.model_copy(update={"asset_id": asset_id})


@app.post("/v1/assets/{asset_id}/masks")
def create_asset_mask_endpoint(asset_id: str, body: CreateAssetMaskRequest, request: Request, authorization: str = Header(default="")):
    _require_asset_visible(request, asset_id, authorization)
    result = create_asset_mask(asset_id, body)
    if not result:
        raise HTTPException(status_code=404, detail={"code": "asset_not_found", "message": "Asset not found."})
    return result


@app.post("/v1/image/jobs")
async def create_image_job_endpoint(
    body: CreateImageJobRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    user_id = _veyra_user_id_from_request(request, authorization)
    _require_job_assets_visible(request, body.asset_ids, body.asset_intents, authorization)
    prepared = await submit_image_job(
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
        veyra_user_id=user_id,
    )
    if prepared.request and prepared.job.status not in {"ready", "failed", "provider_not_configured", "rejected", "canceled"}:
        background_tasks.add_task(run_submitted_image_job, prepared.job.id, prepared.request, edit=prepared.edit)
    return prepared.job


@app.get("/v1/image/history")
async def list_image_history(
    request: Request,
    session_id: str | None = None,
    limit: int = Query(default=50, ge=1, le=1000),
    authorization: str = Header(default=""),
):
    veyra_context = await _veyra_history_context(request, authorization)
    favorite_ids = list_favorite_ids(
        veyra_user_id=_positive_int_or_none(veyra_context.get("user_id")),
        include_legacy_public=True,
    )
    items: list[ImageHistoryItem] = []
    known_output_ids: set[str] = set()
    blocked_output_ids: set[str] = set()
    for job in repository.list_jobs(job_type="image", session_id=session_id):
        if _is_non_v1_history_job(job):
            blocked_output_ids.update(output.id for output in job.outputs)
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
                    veyra_user_id=_history_output_veyra_user_id(output.metadata),
                    favorite=output.id in favorite_ids,
                    created_at=job.created_at,
                    updated_at=job.updated_at,
                    source="repository",
                )
            )

    for record in media_store.list_history_records(limit=limit, session_id=session_id):
        if _is_non_v1_history_record(record):
            blocked_output_ids.add(record["id"])
            continue
        if record["id"] in known_output_ids or record["id"] in blocked_output_ids or record["format"] not in {"png", "jpeg", "webp"}:
            continue
        known_output_ids.add(record["id"])
        items.append(ImageHistoryItem(**{**record, "favorite": record["id"] in favorite_ids}))

    if not session_id:
        for record in media_store.list_generated_output_records(limit=limit):
            if _is_non_v1_history_record(record):
                blocked_output_ids.add(record["id"])
                continue
            if record["id"] in known_output_ids or record["id"] in blocked_output_ids or record["format"] not in {"png", "jpeg", "webp"}:
                continue
            known_output_ids.add(record["id"])
            items.append(ImageHistoryItem(**{**record, "favorite": record["id"] in favorite_ids}))

    items = [_with_veyra_history_access(item, veyra_context) for item in items if _history_visible_to_veyra(item, veyra_context)]
    items.sort(key=_history_sort_key, reverse=True)
    return ImageHistoryResponse(items=items[:limit], total=len(items))


@app.get("/v1/veyra/usage")
def list_v1_veyra_usage(request: Request, limit: int = Query(default=50, ge=1, le=1000), authorization: str = Header(default="")):
    user_id = _veyra_user_id_from_request(request, authorization)
    if not user_id:
        return {"items": [], "total": 0}
    return list_veyra_usage(user_id, limit=limit)


@app.delete("/v1/image/history/{output_id}")
async def delete_image_history_item(output_id: str, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization, allow_legacy_public=False)
    output = repository.delete_output(output_id)
    thumbnail_existed = media_store.thumbnail_path(output_id).exists()
    deleted_file = media_store.delete_output_file(
        output_id=output_id,
        job_id=output.job_id if output else None,
        output_format=output.format if output else None,
    )
    deleted_thumbnail = media_store.delete_thumbnail(output_id) or thumbnail_existed
    removed_records = media_store.delete_history_record(output_id)
    removed_favorites = delete_favorite(output_id)
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
        "removed_favorites": removed_favorites,
        "removed_repository_output": bool(output),
    }


@app.put("/v1/image/history/{output_id}/favorite")
async def favorite_image_history_item(output_id: str, body: FavoriteImageRequest, request: Request, authorization: str = Header(default="")):
    if not _v1_history_output_exists(output_id):
        raise HTTPException(status_code=404, detail={"code": "output_not_found", "message": "Output not found."})
    await _require_output_visible(request, output_id, authorization, allow_legacy_public=True)
    context = await _veyra_history_context(request, authorization)
    return set_favorite(output_id, body.favorite, veyra_user_id=_positive_int_or_none(context.get("user_id")))


@app.get("/v1/image/jobs/{job_id}")
def get_image_job(job_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    job = repository.get_job(job_id)
    if not job or job.job_type != "image":
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Image job not found."})
    return job


@app.post("/v1/image/jobs/{job_id}/revise")
async def revise_image_job_endpoint(
    job_id: str,
    body: ReviseImageRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    authorization: str = Header(default=""),
):
    await _require_output_visible(request, body.output_id, authorization, allow_legacy_public=True)
    prepared = await submit_revise_image_job(job_id, body, veyra_user_id=_veyra_user_id_from_request(request, authorization))
    if not prepared:
        raise HTTPException(status_code=404, detail={"code": "output_not_found", "message": "Source image output not found."})
    if prepared.request and prepared.job.status not in {"ready", "failed", "provider_not_configured", "rejected", "canceled"}:
        background_tasks.add_task(run_submitted_image_job, prepared.job.id, prepared.request, edit=prepared.edit)
    return prepared.job


@app.post("/v1/video/jobs")
async def create_video_job_endpoint(body: CreateVideoJobRequest, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
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
def get_video_job(job_id: str, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    job = repository.get_job(job_id)
    if not job or job.job_type != "video":
        raise HTTPException(status_code=404, detail={"code": "job_not_found", "message": "Video job not found."})
    return job


@app.get("/v1/providers")
async def list_providers(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    capabilities = await registry.list_capabilities()
    return {
        "providers": [item.model_dump() for group in capabilities.values() for item in group],
        "image": [item.model_dump() for item in capabilities["image"]],
        "video": [item.model_dump() for item in capabilities["video"]],
    }


@app.get("/v1/runtime/provider-settings")
def get_runtime_provider_settings(request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    return _runtime_provider_settings_response()


@app.post("/v1/runtime/provider-settings")
def update_provider_settings(body: RuntimeProviderSettingsRequest, request: Request, authorization: str = Header(default="")):
    _require_veyra_user_if_enabled(request, authorization)
    update_runtime_settings(
        default_image_provider=body.default_image_provider,
        default_image_model=body.default_image_model,
        openai_image_model=body.openai_image_model,
        doubao_image_model=body.doubao_image_model,
        gemini_image_model=body.gemini_image_model,
        default_llm_provider=body.default_llm_provider,
        default_llm_model=body.default_llm_model,
        backup_llm_model=body.backup_llm_model,
        openai_llm_model=body.openai_llm_model,
        kimi_llm_model=body.kimi_llm_model,
        image_work_intensity=body.image_work_intensity,
        openai_api_key=body.openai_api_key,
        openai_base_url=body.openai_base_url,
        doubao_image_api_key=body.doubao_image_api_key,
        doubao_image_base_url=body.doubao_image_base_url,
        anthropic_api_key=body.anthropic_api_key,
        anthropic_base_url=body.anthropic_base_url,
        gemini_image_api_key=body.gemini_image_api_key,
        gemini_image_base_url=body.gemini_image_base_url,
        lab_llm_provider=body.lab_llm_provider,
        lab_llm_model=body.lab_llm_model,
        lab_openai_api_key=body.lab_openai_api_key,
        lab_openai_base_url=body.lab_openai_base_url,
        lab_kimi_api_key=body.lab_kimi_api_key,
        lab_kimi_base_url=body.lab_kimi_base_url,
        lab_doubao_vision_api_key=body.lab_doubao_vision_api_key,
        lab_doubao_vision_model=body.lab_doubao_vision_model,
        lab_doubao_vision_base_url=body.lab_doubao_vision_base_url,
    )
    persistence_warning = None
    try:
        persist_runtime_settings_to_env()
    except OSError as exc:
        persistence_warning = "运行时配置已生效，但写入 .env 失败；重启后可能恢复旧配置。"
        logger.warning("Runtime provider settings applied but failed to persist to env file: %s", exc)
    return _runtime_provider_settings_response(runtime_persistence_warning=persistence_warning)


@app.get("/v1/outputs/{output_id}/download")
async def download_output(output_id: str, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization)
    path, _ = _resolve_output_file(output_id)
    return FileResponse(path, headers=IMMUTABLE_IMAGE_HEADERS)


@app.get("/v1/outputs/{output_id}/thumbnail")
async def thumbnail_output(output_id: str, request: Request, authorization: str = Header(default="")):
    await _require_output_visible(request, output_id, authorization)
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


def _safe_public_share_url(request: Request, value: str | None, *, fallback: str) -> str:
    fallback_url = str(request.url_for("static", path="showcase/city-poster.jpg"))
    if not value:
        if fallback.startswith("/"):
            return str(request.base_url).rstrip("/") + quote(fallback, safe="/:?&=%#.-_~")
        return fallback_url
    decoded = unquote(str(value).strip())
    if not decoded:
        return fallback_url
    split = urlsplit(decoded)
    if split.scheme in {"http", "https"}:
        return decoded
    if decoded.startswith("/"):
        return str(request.base_url).rstrip("/") + quote(decoded, safe="/:?&=%#.-_~")
    return str(request.base_url).rstrip("/") + quote(fallback, safe="/:?&=%#.-_~")


def _share_text(value: str | None, fallback: str, limit: int) -> str:
    compact = " ".join(str(value or "").split())
    if not compact:
        compact = fallback
    return compact[:limit]


def _share_poster_url(request: Request, *, image: str, thumb: str | None, title: str, desc: str, target_url: str) -> str:
    params = {
        "image": image,
        "thumb": thumb or image,
        "title": title,
        "desc": desc,
        "url": target_url,
    }
    return str(request.base_url).rstrip("/") + "/share/poster?" + urlencode(params)


def _share_image_url(request: Request, *, image_url: str, thumb_url: str, title: str, desc: str) -> str:
    params = {
        "image": image_url,
        "thumb": thumb_url,
        "title": title,
        "desc": desc,
    }
    return str(request.base_url).rstrip("/") + "/share/image?" + urlencode(params)


def _share_save_image_url(request: Request, *, image_url: str) -> str:
    return str(request.base_url).rstrip("/") + "/share/save-image?" + urlencode({"image": image_url})


def _share_save_image_cache_path(image_url: str) -> Path:
    cache_key = hashlib.sha256(image_url.encode("utf-8")).hexdigest()[:32]
    return media_store.root / "share_cache" / f"{cache_key}.jpg"


def _write_share_save_image(request: Request, image_url: str, cache_path: Path) -> None:
    from PIL import ImageOps

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    image = _load_share_preview_image(request, image_url)
    image = ImageOps.exif_transpose(image)
    image = _flatten_share_image_for_jpeg(image)
    temporary_path = cache_path.with_suffix(".tmp.jpg")
    image.save(temporary_path, "JPEG", quality=90, optimize=True, progressive=True)
    temporary_path.replace(cache_path)


def _ensure_share_save_image_cached(request: Request, share_url: str) -> None:
    try:
        split = urlsplit(share_url)
        params = parse_qs(split.query)
        image_value = params.get("image", [""])[0]
        if not image_value:
            return
        image_url = _safe_public_share_url(request, image_value, fallback="/static/showcase/city-poster.jpg")
        cache_path = _share_save_image_cache_path(image_url)
        if not cache_path.exists():
            _write_share_save_image(request, image_url, cache_path)
    except Exception:
        return


def _share_image_html(*, title: str, desc: str, page_url: str, image_url: str, thumb_url: str) -> str:
    title_html = escape(title)
    desc_html = escape(desc)
    page_url_html = escape(page_url, quote=True)
    image_url_html = escape(image_url, quote=True)
    thumb_url_html = escape(thumb_url, quote=True)
    return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="description" content="{desc_html}" />
    <meta property="og:type" content="website" />
    <meta property="og:title" content="{title_html}" />
    <meta property="og:description" content="{desc_html}" />
    <meta property="og:url" content="{page_url_html}" />
    <meta property="og:image" content="{thumb_url_html}" />
    <meta itemprop="name" content="{title_html}" />
    <meta itemprop="description" content="{desc_html}" />
    <meta itemprop="image" content="{thumb_url_html}" />
    <title>{title_html}</title>
    <style>
      :root {{
        color-scheme: light;
        --ink: #24231f;
        --muted: #706b60;
        --sage: #748269;
        --brass: #9a7535;
        --paper: #f7f3e8;
        --panel: rgba(255, 253, 247, 0.86);
        --line: rgba(55, 50, 41, 0.12);
      }}
      * {{ box-sizing: border-box; }}
      body {{
        min-height: 100vh;
        margin: 0;
        display: grid;
        place-items: center;
        padding: 20px;
        color: var(--ink);
        background: radial-gradient(circle at 50% 0%, #fffdf7 0, var(--paper) 58%, #ede6d5 100%);
        font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      main {{
        width: min(100%, 560px);
        display: grid;
        gap: 16px;
      }}
      .preview {{
        overflow: hidden;
        border: 1px solid var(--line);
        border-radius: 22px;
        background: var(--panel);
        box-shadow: 0 24px 80px rgba(36, 35, 31, 0.14);
      }}
      .preview img {{
        width: 100%;
        max-height: 70vh;
        display: block;
        object-fit: contain;
        background: #f1ecde;
      }}
      .copy {{
        display: grid;
        gap: 9px;
        padding: 2px 2px 0;
      }}
      h1 {{
        margin: 0;
        font-size: clamp(24px, 7vw, 40px);
        line-height: 1.05;
        letter-spacing: 0;
        font-weight: 650;
      }}
      p {{
        margin: 0;
        color: var(--muted);
        font-size: 14px;
        line-height: 1.7;
      }}
      a {{
        width: fit-content;
        min-height: 40px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 0 18px;
        border-radius: 999px;
        color: #fffdf8;
        background: var(--sage);
        font-size: 14px;
        text-decoration: none;
      }}
      .actions {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
      }}
      .actions a:nth-child(2) {{
        color: var(--brass);
        background: rgba(154, 117, 53, 0.12);
      }}
      .save-hint {{
        color: var(--brass);
        font-size: 13px;
      }}
    </style>
  </head>
  <body>
    <main>
      <article class="preview">
        <img src="{image_url_html}" alt="{title_html}" />
      </article>
      <section class="copy">
        <h1>{title_html}</h1>
        <p>{desc_html}</p>
        <p class="save-hint">长按保存 · 右上角分享</p>
        <div class="actions">
          <a href="/h5">打开 Alchemy</a>
          <a href="{image_url_html}" target="_blank" rel="noopener">查看原图</a>
        </div>
      </section>
    </main>
  </body>
</html>"""


def _render_share_poster(*, request: Request, image_value: str | None, title: str, desc: str, share_url: str) -> bytes:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps
    import qrcode

    width, height = 1080, 1500
    image = Image.new("RGB", (width, height), "#efe8d8")
    draw = ImageDraw.Draw(image)
    _draw_soft_poster_background(draw, width, height)

    card = Image.new("RGBA", (900, 1240), (255, 253, 247, 255))
    card_shadow = Image.new("RGBA", card.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(card_shadow)
    shadow_draw.rounded_rectangle((0, 0, card.width, card.height), radius=34, fill=(40, 34, 24, 72))
    shadow = card_shadow.filter(ImageFilter.GaussianBlur(30))
    image.paste(shadow, (92, 142), shadow)

    card_draw = ImageDraw.Draw(card)
    card_draw.rounded_rectangle((0, 0, card.width - 1, card.height - 1), radius=34, fill=(255, 253, 247, 255), outline=(223, 209, 179, 255), width=2)
    card_draw.rounded_rectangle((38, 38, card.width - 39, card.height - 39), radius=24, outline=(237, 226, 202, 255), width=2)

    preview = _load_share_preview_image(request, image_value)
    preview = ImageOps.exif_transpose(preview).convert("RGB")
    preview = _cover_image(preview, (804, 820))
    preview = _round_image(preview, radius=24)
    card.paste(preview, (48, 58), preview)

    card_draw = ImageDraw.Draw(card)
    title_font = _share_font(56, bold=True)
    subtitle_font = _share_font(28)
    small_font = _share_font(24)
    mono_font = _share_font(23)
    card_draw.text((58, 930), "ALCHEMY MEDIA AGENT", fill=(154, 117, 53), font=small_font)
    for line_index, line in enumerate(_wrap_text_for_poster(title, 16, 2)):
        card_draw.text((58, 970 + line_index * 64), line, fill=(36, 35, 31), font=title_font)
    desc_y = 1100 if len(_wrap_text_for_poster(title, 16, 2)) <= 1 else 1158
    card_draw.text((58, desc_y), "长按保存 · 扫码看原图", fill=(112, 107, 96), font=subtitle_font)

    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(share_url)
    qr.make(fit=True)
    qr_image = qr.make_image(fill_color="#24231f", back_color="#fffdf7").convert("RGB").resize((220, 220), Image.Resampling.NEAREST)
    qr_box = Image.new("RGBA", (260, 260), (255, 253, 247, 255))
    qr_draw = ImageDraw.Draw(qr_box)
    qr_draw.rounded_rectangle((0, 0, 259, 259), radius=24, fill=(255, 253, 247, 255), outline=(223, 209, 179, 255), width=2)
    qr_box.paste(qr_image, (20, 20))
    card.paste(qr_box, (590, 930), qr_box)
    card_draw.text((612, 1208), "SCAN ORIGINAL", fill=(112, 107, 96), font=mono_font)

    tape = Image.new("RGBA", (320, 76), (0, 0, 0, 0))
    tape_draw = ImageDraw.Draw(tape)
    tape_draw.rounded_rectangle((0, 0, 319, 75), radius=16, fill=(245, 235, 208, 184), outline=(228, 210, 170, 150), width=1)
    tape = tape.rotate(-5, expand=True, resample=Image.Resampling.BICUBIC)
    card.paste(tape, (294, -28), tape)

    image.paste(card, (90, 130), card)

    output = BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def _draw_soft_poster_background(draw, width: int, height: int) -> None:
    draw.rectangle((0, 0, width, height), fill="#efe8d8")
    for index in range(0, width, 54):
        color = "#eadfca" if (index // 54) % 2 == 0 else "#f5efdf"
        draw.line((index, 0, index - 280, height), fill=color, width=2)
    draw.ellipse((-220, -180, 460, 500), fill="#fff8e9")
    draw.ellipse((720, 960, 1320, 1600), fill="#e3dcc8")
    draw.rounded_rectangle((60, 80, width - 60, height - 80), radius=54, outline="#d8c69d", width=3)


def _load_share_preview_image(request: Request, value: str | None):
    from PIL import Image
    import httpx

    fallback = STATIC_DIR / "showcase" / "city-poster.jpg"
    try:
        decoded = unquote(str(value or "").strip())
        split = urlsplit(decoded)
        if split.path.startswith("/v1/outputs/"):
            parts = split.path.strip("/").split("/")
            if len(parts) >= 3:
                output_id = parts[2]
                path, _ = _resolve_output_file(output_id)
                return Image.open(path)
        if split.path.startswith("/static/"):
            candidate = STATIC_DIR / split.path.removeprefix("/static/")
            if candidate.exists() and candidate.is_file():
                return Image.open(candidate)
        if split.path.startswith("/mobile-static/"):
            candidate = MOBILE_STATIC_DIR / split.path.removeprefix("/mobile-static/")
            if candidate.exists() and candidate.is_file():
                return Image.open(candidate)
        if split.scheme in {"http", "https"}:
            host = request.url.hostname
            if split.hostname in {host, "127.0.0.1", "localhost", "testserver"}:
                with httpx.Client(timeout=8, follow_redirects=True) as client:
                    response = client.get(decoded)
                    response.raise_for_status()
                    return Image.open(BytesIO(response.content))
    except Exception:
        pass
    return Image.open(fallback)


def _cover_image(image, size: tuple[int, int]):
    from PIL import Image, ImageOps

    return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS, centering=(0.5, 0.5))


def _round_image(image, radius: int):
    from PIL import Image, ImageDraw

    rounded = image.convert("RGBA")
    mask = Image.new("L", rounded.size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle((0, 0, rounded.width, rounded.height), radius=radius, fill=255)
    rounded.putalpha(mask)
    return rounded


def _flatten_share_image_for_jpeg(image):
    from PIL import Image

    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        alpha = rgba.getchannel("A")
        flattened = Image.new("RGB", rgba.size, (255, 255, 255))
        flattened.paste(rgba, mask=alpha)
        return flattened
    if image.mode != "RGB":
        return image.convert("RGB")
    return image


def _share_font(size: int, *, bold: bool = False):
    from PIL import ImageFont

    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/NotoSansSC-VF.ttf",
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text_for_poster(value: str, width: int, max_lines: int) -> list[str]:
    compact = " ".join(str(value or "").split())
    if not compact:
        return []
    if all(ord(char) < 128 for char in compact):
        lines = textwrap.wrap(compact, width=width) or [compact[:width]]
    else:
        lines = [compact[index : index + width] for index in range(0, len(compact), width)]
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .，。") + "..."
    return lines


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


def _history_visible_to_veyra(item: ImageHistoryItem, context: dict) -> bool:
    if not context.get("authenticated"):
        return not settings.veyra_auth_enabled
    if context.get("is_admin"):
        return True
    owner_id = _history_item_veyra_user_id(item)
    return owner_id is None or owner_id == context.get("user_id")


def _history_item_veyra_user_id(item: ImageHistoryItem) -> int | None:
    return _positive_int_or_none(getattr(item, "veyra_user_id", None))


def _with_veyra_history_access(item: ImageHistoryItem, context: dict) -> ImageHistoryItem:
    owner_id = _history_item_veyra_user_id(item)
    can_delete = _history_deletable_to_veyra(owner_id, context)
    if owner_id is not None:
        return item.model_copy(update={"can_delete": can_delete})
    return item.model_copy(update={"veyra_legacy_public": True, "record_label": "旧版生图记录", "can_delete": can_delete})


def _history_deletable_to_veyra(owner_id: int | None, context: dict) -> bool:
    if not settings.veyra_auth_enabled:
        return True
    if context.get("is_admin"):
        return True
    return owner_id is not None and owner_id == context.get("user_id")


def _history_output_veyra_user_id(metadata: dict | None) -> int | None:
    if not isinstance(metadata, dict):
        return None
    return _positive_int_or_none(metadata.get("veyra_user_id"))


def _positive_int_or_none(value) -> int | None:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


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


def _is_lab_history_job(job) -> bool:
    if str(job.idempotency_key or "").startswith("lab:"):
        return True
    session = repository.get_session(job.session_id) if job.session_id else None
    return session.project_id == LAB_PROJECT_ID if session else False


def _is_non_v1_history_job(job) -> bool:
    return _is_v2_bridge_job(job) or _is_lab_history_job(job)


def _is_v2_bridge_history_record(record: dict) -> bool:
    if record.get("source_app") == V2_BRIDGE_PROJECT_ID:
        return True
    if str(record.get("idempotency_key") or "").startswith(V2_IDEMPOTENCY_PREFIX):
        return True
    return False


def _is_non_v1_history_record(record: dict) -> bool:
    return _is_v2_bridge_history_record(record) or is_lab_history_record(record)


def _runtime_provider_settings_response(runtime_persistence_warning: str | None = None) -> RuntimeProviderSettingsResponse:
    return RuntimeProviderSettingsResponse(
        default_image_provider=settings.default_image_provider,
        default_image_model=settings.default_image_model,
        openai_image_model=settings.openai_image_model,
        doubao_image_model=settings.doubao_image_model,
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
        doubao_image_base_url=settings.doubao_image_base_url,
        doubao_image_api_key_configured=bool(settings.doubao_image_api_key),
        anthropic_base_url=settings.anthropic_base_url,
        anthropic_api_key_configured=bool(settings.anthropic_api_key or settings.anthropic_auth_token),
        gemini_image_base_url=settings.gemini_image_base_url,
        gemini_image_api_key_configured=bool(settings.gemini_image_api_key),
        lab_llm_provider=settings.lab_llm_provider,
        lab_llm_model=settings.lab_llm_model,
        lab_openai_base_url=settings.lab_openai_base_url,
        lab_openai_api_key_configured=bool(settings.lab_openai_api_key),
        lab_kimi_base_url=settings.lab_kimi_base_url,
        lab_kimi_api_key_configured=bool(settings.lab_kimi_api_key),
        lab_vision_provider=settings.lab_vision_provider,
        lab_doubao_vision_model=settings.lab_doubao_vision_model,
        lab_doubao_vision_base_url=settings.lab_doubao_vision_base_url,
        lab_doubao_vision_api_key_configured=bool(settings.lab_doubao_vision_api_key),
        runtime_persistence_warning=runtime_persistence_warning,
        provider_notes={
        "openai_gpt_image": "OpenAI-compatible GPT Image provider is wired for live image generation.",
        "doubao_image": "Doubao Seedream image provider uses OpenAI-compatible /images/generations and does not support image edits.",
        "gemini_image": "Gemini image provider is wired for live generateContent image generation.",
            "seedance": "Seedance video provider is a documented async placeholder; live task API is not implemented yet.",
            "thinking_models": "Prompt planning uses the selected thinking model first and automatically tries the other model when the selected one fails.",
            "alchemy_lab_brain": "Alchemy Lab uses its own LLM/Vision gateway for intent planning and does not call the V2 Claude orchestrator.",
        },
    )
