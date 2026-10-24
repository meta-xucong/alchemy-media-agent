"""One explicit, optional host mount. Disabled means no routes or resources."""
from __future__ import annotations

import inspect
from pathlib import Path
import re
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import ValidationError

from .client import BridgeError
from .models import PreviewCreate
from .service import PreviewService
from .settings import BridgeSettings

PREFIX = "/api/integrations/render-bridge/v1"
STATIC = Path(__file__).parent / "static"
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}


def install_render_bridge(app, *, session_user, auth_enabled, project_snapshot, config=None, client=None,
                          native_gateway_factory=None):
    config = config or BridgeSettings.from_env()
    if config.mode == "disabled":
        return None
    router = APIRouter()
    runtime = {"service": None, "error": config.config_error}

    @app.on_event("startup")
    async def start():
        if runtime["error"]:
            return
        try:
            runtime["service"] = PreviewService(config, project_snapshot, client=client)
            runtime["service"].start()
        except Exception:
            # A configuration/storage problem must not prevent the host booting.
            runtime["error"] = "bridge_initialization_failed"

    @app.on_event("shutdown")
    async def stop():
        if runtime["service"]:
            await runtime["service"].close()

    async def actor(request):
        if auth_enabled():
            value = session_user(request, request.headers.get("authorization", ""))
            if inspect.isawaitable(value):
                value = await value
            if type(value) is not int or value <= 0:
                raise HTTPException(401, detail={"code": "bridge_session_required"})
            return str(value)
        # Explicit isolated development mode, never an unauthenticated public API.
        if config.allow_local_preview and request.client and request.client.host in {"127.0.0.1", "::1"}:
            return "local_preview"
        raise HTTPException(401, detail={"code": "bridge_session_required"})

    def require_write(request):
        if request.headers.get("x-alchemy-bridge-preview") != "1" or request.headers.get("sec-fetch-site") not in {None, "same-origin", "none"}:
            raise HTTPException(403, detail={"code": "same_origin_required"})
        origin = request.headers.get("origin")
        if origin:
            supplied, actual = urlsplit(origin), urlsplit(str(request.base_url))
            if supplied.scheme != actual.scheme or supplied.netloc != actual.netloc or supplied.path not in {"", "/"}:
                raise HTTPException(403, detail={"code": "same_origin_required"})

    def service():
        if runtime["error"] or runtime["service"] is None:
            raise HTTPException(503, detail={"code": runtime["error"] or "bridge_starting"})
        return runtime["service"]

    def identifier(value):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value):
            raise HTTPException(404, detail={"code": "resource_not_found"})
        return value

    async def call(awaitable):
        try:
            return await awaitable
        except BridgeError as exc:
            raise HTTPException(exc.status if 400 <= exc.status < 600 else 502,
                                detail={"code": exc.code, "retryable": exc.retryable}) from None

    @router.get(PREFIX + "/status")
    async def status(request: Request):
        await actor(request)
        return JSONResponse({"mode": config.mode, "available": runtime["service"] is not None,
                             "error": runtime["error"], "test_only": True,
                             "native_registration": "not_connected", "profiles": list(config.profiles),
                             "recovery": "running" if runtime["service"] else "paused"}, headers=HEADERS)

    @router.get(PREFIX + "/tasks")
    async def tasks(request: Request, project_id: str):
        owner = await actor(request)
        items = await call(service().list(owner, identifier(project_id)))
        return JSONResponse({"tasks": items}, headers=HEADERS)

    @router.post(PREFIX + "/tasks", status_code=202)
    async def create(request: Request):
        owner = await actor(request)
        require_write(request)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 12 * 1024 * 1024:
                raise HTTPException(413, detail={"code": "request_too_large"})
        try:
            payload = PreviewCreate.model_validate_json(body)
        except (ValidationError, ValueError):
            raise HTTPException(422, detail={"code": "invalid_preview_request"}) from None
        identifier(payload.project_id)
        record = await call(service().create(owner, payload))
        return JSONResponse(service().public(record), status_code=202, headers=HEADERS)

    @router.get(PREFIX + "/tasks/{job_id}")
    async def task(request: Request, job_id: str):
        owner = await actor(request)
        record, current = await call(service().visible(owner, identifier(job_id)))
        return JSONResponse(service().public(record, revision_current=current), headers=HEADERS)

    @router.post(PREFIX + "/tasks/{job_id}/cancel")
    async def cancel(request: Request, job_id: str):
        owner = await actor(request)
        require_write(request)
        record = await call(service().cancel(owner, identifier(job_id)))
        return JSONResponse(service().public(record), headers=HEADERS)

    @router.get(PREFIX + "/tasks/{job_id}/preview")
    async def preview(request: Request, job_id: str):
        owner = await actor(request)
        manifest, content = await call(service().preview(owner, identifier(job_id)))
        return Response(content, media_type=manifest["mime_type"], headers={**HEADERS, "Content-Disposition": "inline"})

    @router.get("/render-bridge-preview", include_in_schema=False)
    async def page():
        return FileResponse(STATIC / "index.html", headers={**HEADERS, "Content-Security-Policy":
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' blob:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})

    @router.get("/render-bridge-preview/assets/{name}", include_in_schema=False)
    async def asset(name: str):
        if name not in {"preview.js", "preview.css"}:
            raise HTTPException(404)
        return FileResponse(STATIC / name, headers=HEADERS)

    app.include_router(router)
    app.state.render_bridge_preview = runtime
    from .diagnostics import install_diagnostics_routes
    install_diagnostics_routes(app, config=config, actor=actor, require_write=require_write, get_service=service)
    if config.native_enabled:
        from .native_routes import install_native_routes
        install_native_routes(app, config=config, actor=actor, require_write=require_write,
                              project_snapshot=project_snapshot, gateway_factory=native_gateway_factory)
    return runtime
