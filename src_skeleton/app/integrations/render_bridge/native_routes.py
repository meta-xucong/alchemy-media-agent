"""Explicit synthetic native-development entry, enabled separately from preview."""
from pathlib import Path
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import ValidationError
from .client import BridgeError
from .native_service import NativeBridgeService, NativeTaskCreate
from .routes import HEADERS, PREFIX, STATIC


def install_native_routes(app, *, config, actor, require_write, project_snapshot, gateway_factory):
    if not config.native_enabled:
        return None
    runtime = {"service": None, "error": config.config_error}
    router = APIRouter()
    native_prefix = PREFIX + "/native"

    @app.on_event("startup")
    async def start_native():
        if runtime["error"]:
            return
        if gateway_factory is None:
            runtime["error"] = "native_gateway_unavailable"
            return
        try:
            gateway = gateway_factory(config)
            runtime["service"] = NativeBridgeService(config, project_snapshot, gateway)
            runtime["service"].start()
        except Exception:
            runtime["error"] = "native_initialization_failed"

    @app.on_event("shutdown")
    async def stop_native():
        if runtime["service"]:
            await runtime["service"].close()

    async def owner(request):
        value = await actor(request)
        if not value.isdigit() or int(value) <= 0:
            raise HTTPException(403, detail={"code": "native_authenticated_owner_required"})
        return value

    def service():
        if runtime["error"] or runtime["service"] is None:
            raise HTTPException(503, detail={"code": runtime["error"] or "native_starting"})
        return runtime["service"]

    async def call(awaitable):
        try:
            return await awaitable
        except BridgeError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code, "retryable": exc.retryable}) from None

    @router.get(native_prefix + "/status")
    async def status(request: Request):
        await owner(request)
        return JSONResponse({"available": runtime["service"] is not None, "mode": config.mode,
            "error": runtime["error"], "profile_id": "fake-image", "test_fixture": True,
            "real_tool_verified": False, "formal_delivery": False,
            "billing": {"mode": "v3_zero_credit_stub", "charged": False}}, headers=HEADERS)

    @router.post(native_prefix + "/tasks", status_code=202)
    async def create(request: Request):
        current = await owner(request)
        require_write(request)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                raise HTTPException(413, detail={"code": "request_too_large"})
        try:
            payload = NativeTaskCreate.model_validate_json(body)
        except (ValidationError, ValueError):
            raise HTTPException(422, detail={"code": "invalid_native_test_request"}) from None
        record = await call(service().create(current, payload))
        return JSONResponse(service().public(record), status_code=202, headers=HEADERS)

    @router.get(native_prefix + "/tasks")
    async def tasks(request: Request, project_id: str):
        current = await owner(request)
        import re
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", project_id):
            raise HTTPException(404)
        return JSONResponse({"tasks": await call(service().list(current, project_id))}, headers=HEADERS)

    @router.get(native_prefix + "/tasks/{job_id}")
    async def task(request: Request, job_id: str):
        current = await owner(request)
        record, _ = await call(service().visible(current, job_id))
        return JSONResponse(service().public(record), headers=HEADERS)

    @router.post(native_prefix + "/tasks/{job_id}/cancel")
    async def cancel(request: Request, job_id: str):
        current = await owner(request)
        require_write(request)
        record = await call(service().cancel(current, job_id))
        return JSONResponse(service().public(record), headers=HEADERS)

    @router.get("/render-bridge-native-test", include_in_schema=False)
    async def page():
        return FileResponse(STATIC / "native.html", headers={**HEADERS, "Content-Security-Policy":
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"})

    @router.get("/render-bridge-native-test/assets/native.js", include_in_schema=False)
    async def script():
        return FileResponse(STATIC / "native.js", headers=HEADERS)

    app.include_router(router)
    app.state.render_bridge_native = runtime
    return runtime
