"""Account-bound access-key UI endpoints; all product work stays in V3."""
from __future__ import annotations
import re
import sqlite3
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from app.config import settings
from app.storage import media_store
from app.services.api_keys import ApiKeyStore, KeyAccessError, PREFIX


class CreateAccessKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=50)


def key_store():
    return ApiKeyStore(media_store.root / "api_access" / "keys.sqlite3")


_ID = r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}"
# Only the already documented product surface. No administration or handoff.
_PRODUCT_PATHS = {
    "GET": [r"projects", rf"projects/{_ID}", "project-outputs", "templates",
        rf"jobs/{_ID}", rf"uploads/{_ID}", rf"uploads/{_ID}/content",
        rf"outputs/{_ID}/(?:download|preview|thumbnail)"],
    "POST": ["projects", rf"projects/{_ID}/jobs", rf"projects/{_ID}/jobs/{_ID}/select",
        "uploads", rf"uploads/{_ID}/complete"],
    "PUT": [rf"uploads/{_ID}/content"],
}


def key_allows(method, path):
    prefix = "/api/v3/creative-agent/"
    return path.startswith(prefix) and any(re.fullmatch(pattern,path[len(prefix):])
        for pattern in _PRODUCT_PATHS.get(method, ()))


def _error(code, status):
    return JSONResponse({"detail": {"code": code}}, status_code=status,
        headers={"Cache-Control": "no-store"})


def _ui_write(request):
    # A cross-site form must not create/revoke a cookie owner's credential.
    if request.headers.get("X-Alchemy-UI") != "api-access":
        raise HTTPException(403, detail={"code": "same_origin_required"})
    origin = request.headers.get("origin")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, detail={"code": "same_origin_required"})
    if origin:
        try:
            supplied, actual = urlsplit(origin), urlsplit(str(request.base_url))
            matches = ((supplied.scheme, supplied.hostname, supplied.port or (443 if supplied.scheme=="https" else 80))
                == (actual.scheme, actual.hostname, actual.port or (443 if actual.scheme=="https" else 80)))
        except ValueError:
            matches = False
        if not matches:
            raise HTTPException(403, detail={"code": "same_origin_required"})


def install_api_access(app, *, session_user, account_loader, admin_resolver):
    async def account_for(request):
        if not settings.veyra_auth_enabled:
            raise HTTPException(503, detail={"code": "account_login_not_configured"})
        authorization = request.headers.get("authorization", "")
        if authorization.partition(" ")[2].strip().startswith(PREFIX):
            raise HTTPException(403, detail={"code": "session_login_required"})
        owner = session_user(request, authorization)
        if type(owner) is not int or owner <= 0:
            raise HTTPException(401, detail={"code": "session_login_required"})
        account = await account_loader(owner)
        if account.user_id != owner or account.status != "active":
            raise HTTPException(403, detail={"code": "account_inactive"})
        return account

    @app.middleware("http")
    async def resolve_api_key(request, call_next):
        authorization = request.headers.get("authorization", "")
        scheme, _, token = authorization.partition(" ")
        token = token.strip()
        if scheme.lower() == "bearer" and token.startswith(PREFIX):
            if not settings.veyra_auth_enabled:
                return _error("account_login_not_configured", 503)
            if not key_allows(request.method, request.url.path):
                return _error("api_key_route_not_allowed", 403)
            try:
                store = key_store()
                identity = store.resolve(token)
                account = await account_loader(identity["owner_id"])
                if account.user_id != identity["owner_id"] or account.status != "active":
                    return _error("account_inactive", 403)
                store.record_use(identity["id"])
                request.state.alchemy_api_user_id = identity["owner_id"]
            except KeyAccessError as exc:
                return _error(exc.code, exc.status)
            except HTTPException as exc:
                return _error("account_verification_unavailable", exc.status_code)
            except (sqlite3.Error, OSError):
                return _error("key_service_unavailable", 503)
        if request.url.path.startswith("/api/access/"):
            try:
                response = await call_next(request)
            except (sqlite3.Error, OSError):
                return _error("key_service_unavailable", 503)
            response.headers["Cache-Control"] = "no-store"
            response.headers["Vary"] = "Authorization, Cookie"
            return response
        return await call_next(request)

    router = APIRouter(prefix="/api/access", include_in_schema=False)

    @router.get("/me")
    async def me(request: Request):
        account = await account_for(request)
        return {"user_id": account.user_id, "email": account.email,
            "is_admin": str(account.role).lower() == "admin"}

    @router.get("/keys")
    async def keys(request: Request, offset: int = Query(0, ge=0, le=100000)):
        account = await account_for(request)
        return key_store().list(owner_id=account.user_id, offset=offset)

    @router.post("/keys")
    async def create(body: CreateAccessKey, request: Request):
        _ui_write(request)
        account = await account_for(request)
        try:
            return key_store().create(account.user_id, body.name)
        except KeyAccessError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code}) from exc

    @router.post("/keys/{key_id}/revoke")
    async def revoke(key_id: str, request: Request):
        _ui_write(request)
        account = await account_for(request)
        try:
            return {"key": key_store().revoke(key_id, owner_id=account.user_id, actor_id=account.user_id)}
        except KeyAccessError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code}) from exc

    @router.get("/admin/keys")
    async def admin_keys(request: Request, q: str = Query("", max_length=50), offset: int = Query(0, ge=0, le=100000)):
        # Existing Veyra admin role remains the authority.
        await account_for(request)
        await admin_resolver(request, request.headers.get("authorization", ""))
        return key_store().list(owner_id=None, query=q.strip(), offset=offset)

    @router.post("/admin/keys/{key_id}/revoke")
    async def admin_revoke(key_id: str, request: Request):
        _ui_write(request)
        account = await account_for(request)
        await admin_resolver(request, request.headers.get("authorization", ""))
        try:
            return {"key": key_store().revoke(key_id, owner_id=None, actor_id=account.user_id)}
        except KeyAccessError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code}) from exc

    app.include_router(router)
