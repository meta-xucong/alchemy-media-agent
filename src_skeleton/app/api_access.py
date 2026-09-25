"""Account-bound access-key UI endpoints; all product work stays in V3."""
from __future__ import annotations
import re
import sqlite3
from urllib.parse import urlsplit
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.config import settings
from app.storage import media_store
from app.services.api_keys import ALL_SURFACES, ApiKeyStore, KeyAccessError, LIVE_PREFIX, PREFIX


class CreateAccessKey(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(default="", max_length=50)
    surfaces: list[str] = Field(default_factory=lambda: list(ALL_SURFACES), min_length=1, max_length=4)

    @field_validator("surfaces")
    @classmethod
    def validate_surfaces(cls, value):
        normalized = sorted({str(item).strip().lower() for item in value if str(item).strip()})
        if not normalized or any(item not in ALL_SURFACES for item in normalized):
            raise ValueError("invalid key surfaces")
        return normalized


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


def _surface_for_path(method: str, path: str) -> str | None:
    prefix = "/api/v3/creative-agent/"
    if path == "/api/access/capabilities":
        return "capabilities"
    if path.startswith("/v1/"):
        if path.startswith(("/v1/admin/", "/v1/runtime/")):
            return None
        return "v1"
    if path.startswith("/api/v2/"):
        if path.startswith(("/api/v2/veyra/login", "/api/v2/veyra/billing", "/api/v2/admin/")):
            return None
        return "v2"
    if path.startswith("/api/lab/"):
        return "lab"
    if path.startswith(prefix) and any(re.fullmatch(pattern, path[len(prefix):]) for pattern in _PRODUCT_PATHS.get(method, ())):
        return "v3"
    return None


def key_allows(method, path, surfaces=None):
    surface = _surface_for_path(method, path)
    if surface == "capabilities":
        return True
    allowed = set(surfaces or ("v3",))
    return surface in allowed


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
        if authorization.partition(" ")[2].strip().startswith((PREFIX, LIVE_PREFIX)):
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
        if scheme.lower() == "bearer" and token.startswith((PREFIX, LIVE_PREFIX)):
            if not settings.veyra_auth_enabled:
                return _error("account_login_not_configured", 503)
            try:
                store = key_store()
                identity = store.resolve(token)
            except KeyAccessError as exc:
                return _error(exc.code, exc.status)
            except (sqlite3.Error, OSError):
                return _error("key_service_unavailable", 503)
            if not key_allows(request.method, request.url.path, identity.get("surfaces")):
                return _error("api_key_route_not_allowed", 403)
            try:
                account = await account_loader(identity["owner_id"])
                if account.user_id != identity["owner_id"] or account.status != "active":
                    return _error("account_inactive", 403)
                store.record_use(identity["id"])
                request.state.alchemy_api_user_id = identity["owner_id"]
                request.state.alchemy_api_key_id = identity["id"]
                request.state.alchemy_api_key_surfaces = list(identity.get("surfaces") or ())
                request.state.alchemy_api_key_token = token
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
        response = await call_next(request)
        if getattr(request.state, "alchemy_api_user_id", None) is not None:
            response.headers["X-Alchemy-API-Key-Auth"] = "accepted"
        return response

    router = APIRouter(prefix="/api/access", include_in_schema=False)

    @router.get("/me")
    async def me(request: Request):
        account = await account_for(request)
        return {"user_id": account.user_id, "email": account.email,
            "is_admin": str(account.role).lower() == "admin"}

    @router.get("/capabilities")
    async def capabilities(request: Request):
        if getattr(request.state, "alchemy_api_user_id", None) is not None:
            surfaces = list(getattr(request.state, "alchemy_api_key_surfaces", ()) or ())
            user_id = request.state.alchemy_api_user_id
        else:
            account = await account_for(request)
            surfaces = list(ALL_SURFACES)
            user_id = account.user_id
        return {
            "user_id": user_id,
            "surfaces": surfaces,
            "api": {
                "v1": "/v1",
                "v2": "/api/v2",
                "v3": "/api/v3/creative-agent",
                "lab": "/api/lab",
            },
            "mcp": {
                "v1": ["alchemy_v1_create_session", "alchemy_v1_upload_asset", "alchemy_v1_create_image_job", "alchemy_v1_get_image_job", "alchemy_v1_list_history", "alchemy_v1_revise_image"],
                "v2": ["alchemy_v2_create_creative_run", "alchemy_v2_get_creative_run", "alchemy_v2_upload_asset", "alchemy_v2_create_image_job", "alchemy_v2_get_image_job", "alchemy_v2_list_history", "alchemy_v2_search_cases", "alchemy_v2_get_case"],
                "v3": ["alchemy_create_project", "alchemy_upload_asset", "alchemy_create_generation", "alchemy_get_generation", "alchemy_list_outputs", "alchemy_select_outputs"],
                "lab": ["alchemy_lab_list_modules", "alchemy_lab_list_styles", "alchemy_lab_search_styles", "alchemy_lab_upload_reference", "alchemy_lab_create_session", "alchemy_lab_get_session", "alchemy_lab_list_history", "alchemy_lab_update_favorites"],
            },
        }

    @router.get("/keys")
    async def keys(request: Request, offset: int = Query(0, ge=0, le=100000)):
        account = await account_for(request)
        return key_store().list(owner_id=account.user_id, offset=offset)

    @router.post("/keys")
    async def create(body: CreateAccessKey, request: Request):
        _ui_write(request)
        account = await account_for(request)
        try:
            return key_store().create(account.user_id, body.name, body.surfaces)
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
