"""Administrator-only nonsecret configuration and lazy Bridge lifecycle."""
from __future__ import annotations

import asyncio
from asyncio import sleep as _primary_maintenance_sleep
from dataclasses import replace
from datetime import datetime, timezone
import inspect
import json
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from .client import BridgeClient, BridgeError
from .diagnostics import capabilities_projection
from .routes import HEADERS, PREFIX, install_render_bridge
from .settings import BridgeSettings
from .store import TERMINAL

from render_bridge_primary import (PrimarySettings, PrimaryTransport, control_path, state_root,
                                   pending_count as primary_pending_count)
from render_bridge_primary.health import PrimaryHealthMonitor


class AdminSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    mode: Literal["disabled", "enabled", "draining"]
    base_url: str = Field(max_length=2048)
    workspace: str = Field(max_length=128)
    profiles: list[Literal["fake-image", "codex-image", "midjourney-manual"]] = Field(min_length=1, max_length=3)
    auto_fallback_enabled: bool = False
    queue_wait_seconds: int = Field(default=30, ge=1, le=3600)
    native_enabled: bool = False
    native_profiles: list[Literal["fake-image", "codex-image", "midjourney-manual"]] = Field(default=["fake-image"], min_length=1, max_length=3)


class BridgeAdminController:
    def __init__(self, *, baseline, admin_resolver, session_user, auth_enabled,
                 project_snapshot, native_gateway_factory=None, client_factory=BridgeClient):
        self.baseline = baseline
        self.config = baseline
        # Shared control-plane configuration is product-neutral. In particular,
        # V2 never imports this module or reads the V1 preview database.
        self.path = control_path()
        self.legacy_path = baseline.storage / "admin-settings.json"
        self.admin_resolver = admin_resolver
        self.session_user, self.auth_enabled = session_user, auth_enabled
        self.project_snapshot, self.native_gateway_factory = project_snapshot, native_gateway_factory
        self.client_factory = client_factory
        self.application = None
        self.lifespan = None
        self.lock = asyncio.Lock()
        self.error = None
        self.persisted = False
        self.updated_at = None
        self.primary_maintenance_task = None
        self.primary_health_task = None

    async def maintain_primary_once(self):
        # Only reconcile durable post-registration ACKs and cancellation intents.
        # Never submit, generate, import, or decide a new route in this worker.
        if not state_root().exists():
            return
        for product in ("v1", "lab", "v2", "v3"):
            transport = None
            try:
                config = PrimarySettings.from_env(product=product)
                if not (config.base_url and config.workspace and config.token):
                    continue
                if not primary_pending_count(config):
                    continue
                transport = PrimaryTransport(config)
                async with asyncio.timeout(8):
                    await transport.reconcile_pending(limit=32)
            except asyncio.CancelledError:
                raise
            except Exception:
                # A transient ACK outage cannot invalidate native pixels or
                # turn an owned task into another provider generation.
                continue
            finally:
                if transport is not None:
                    try:
                        await transport.close()
                    except Exception:
                        pass

    async def maintain_primary(self):
        while True:
            # Keep this worker's clock independent of product-specific injected
            # sleeps (for example Lab's serial-generation interval tests).
            await _primary_maintenance_sleep(5)
            await self.maintain_primary_once()

    def validate(self, body):
        base = body.base_url.strip().rstrip("/")
        workspace = body.workspace.strip()
        if len(set(body.profiles)) != len(body.profiles) or len(set(body.native_profiles)) != len(body.native_profiles):
            raise ValueError("invalid_profiles")
        if body.native_enabled and not set(body.native_profiles).issubset(body.profiles):
            raise ValueError("invalid_native_profiles")
        if base:
            try:
                parsed = urlsplit(base)
                local_http = (parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                              and parsed.scheme == "http"
                              and os.getenv("ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK") == "true")
                if (not parsed.hostname or not (parsed.scheme == "https" or local_http)
                        or parsed.username or parsed.password or parsed.query or parsed.fragment
                        or parsed.path not in {"", "/"}):
                    raise ValueError()
                parsed.port
            except ValueError:
                raise ValueError("invalid_bridge_url") from None
        if self.baseline.token and base != self.baseline.base_url:
            raise ValueError("credential_endpoint_mismatch")
        expected_workspace = os.getenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", "")
        if expected_workspace and workspace != expected_workspace:
            raise ValueError("credential_workspace_mismatch")
        error = None if base and workspace and self.baseline.token else "bridge_configuration_missing"
        if body.mode != "disabled" and error:
            raise ValueError(error)
        return replace(self.baseline, mode=body.mode, base_url=base, workspace=workspace,
                       profiles=tuple(body.profiles), native_profiles=tuple(body.native_profiles),
                       native_enabled=body.native_enabled, auto_fallback_enabled=body.auto_fallback_enabled,
                       queue_wait_seconds=body.queue_wait_seconds, config_error=error)

    def read_saved(self):
        source = self.path if self.path.exists() else self.legacy_path
        if not source.exists():
            return
        try:
            value = json.loads(source.read_text(encoding="utf-8"))
            if value.pop("schema_version", "1") != "1":
                raise ValueError("invalid_control_version")
            if value.pop("profile", "codex-image") != "codex-image":
                raise ValueError("invalid_primary_profile")
            self.updated_at = value.pop("updated_at", None)
            self.config = self.validate(AdminSettingsUpdate.model_validate(value))
            self.persisted = True
            if source != self.path:
                # One-time migration, never persist the environment token.
                self._write_control({**value, "updated_at": self.updated_at})
        except (OSError, ValueError, ValidationError, TypeError, AttributeError):
            # A broken admin file never activates the fallback environment config.
            self.config = replace(self.baseline, mode="disabled")
            self.error = "invalid_saved_bridge_settings"

    def _write_control(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps({**value, "schema_version": "1", "profile": "codex-image"},
                                        ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def publish_environment_defaults(self):
        if self.path.exists() or self.config.mode == "disabled" or self.config.config_error:
            return
        config = self.config
        value = {key: getattr(config, key) for key in (
            "mode", "base_url", "workspace", "native_enabled", "auto_fallback_enabled", "queue_wait_seconds")}
        value.update(profiles=list(config.profiles), native_profiles=list(config.native_profiles))
        self._write_control(value)

    async def activate(self, config):
        if self.application:
            await self.lifespan.__aexit__(None, None, None)
            self.application = None
        self.config = config
        self.error = config.config_error if config.mode != "disabled" else None
        if config.mode == "disabled" or self.error:
            return
        application = FastAPI()
        client = None
        try:
            client = self.client_factory(config.base_url, config.token)
            install_render_bridge(application, session_user=self.session_user,
                                  auth_enabled=self.auth_enabled, project_snapshot=self.project_snapshot,
                                  config=config, client=client,
                                  native_gateway_factory=self.native_gateway_factory)
            self.lifespan = application.router.lifespan_context(application)
            await self.lifespan.__aenter__()
            self.application = application
            runtime = application.state.render_bridge_preview
            self.error = runtime["error"]
            if self.error and runtime["service"] is None:
                await client.close()
        except Exception:
            # Configuration is saved, but availability is explicitly false; the
            # surrounding Alchemy application must remain healthy.
            if client is not None:
                await client.close()
            self.application = None
            self.error = "bridge_initialization_failed"

    def pending_count(self):
        count = 0
        try:
            count += primary_pending_count(state_root())
        except (OSError, sqlite3.Error, ValueError):
            raise HTTPException(409, detail={"code": "bridge_pending_state_unavailable"}) from None
        for root in (self.config.storage, self.config.storage / "native"):
            path = root / "integration.sqlite3"
            if not path.exists():
                continue
            try:
                with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=1) as db:
                    placeholders = ",".join("?" for _ in TERMINAL)
                    count += db.execute(f"SELECT COUNT(*) FROM integration_jobs WHERE state NOT IN ({placeholders})", tuple(TERMINAL)).fetchone()[0]
            except sqlite3.Error:
                raise HTTPException(409, detail={"code": "bridge_pending_state_unavailable"}) from None
        return count

    def projection(self):
        config = self.config
        public_url = config.base_url
        try:
            parsed = urlsplit(public_url)
            if parsed.username or parsed.password or parsed.query or parsed.fragment:
                public_url = ""
        except ValueError:
            public_url = ""
        native_runtime = getattr(self.application.state, "render_bridge_native", None) if self.application else None
        return {"mode": config.mode, "base_url": public_url,
                "primary_routing_active": config.mode == "enabled" and "codex-image" in config.profiles and not config.config_error,
                "primary_routing_policy": "bridge_primary_nonadmission_only_v1",
                "native_runtime_active": bool(native_runtime and native_runtime["service"]),
                "native_runtime_error": native_runtime["error"] if native_runtime else None, "workspace": config.workspace,
                "profiles": list(config.profiles), "native_enabled": config.native_enabled,
                "auto_fallback_enabled": config.auto_fallback_enabled, "queue_wait_seconds": config.queue_wait_seconds,
                "native_profiles": list(config.native_profiles), "credential_configured": bool(config.token),
                "credential_source": "server_environment", "persisted": self.persisted,
                "updated_at": self.updated_at, "configuration_error": self.error or config.config_error,
                "runtime_active": bool(self.application and not self.error),
                "recovery": "paused" if not self.application or self.error else "running",
                "real_generation_verified": False, "formal_delivery": False}

    async def save(self, body):
        try:
            config = self.validate(body)
        except ValueError as exc:
            raise HTTPException(422, detail={"code": str(exc)}) from None
        async with self.lock:
            changed_scope = any(getattr(config, field) != getattr(self.config, field) for field in
                                ("base_url", "workspace", "profiles", "native_enabled", "native_profiles"))
            if changed_scope and self.pending_count():
                raise HTTPException(409, detail={"code": "bridge_pending_tasks_require_existing_configuration"})
            value = body.model_dump()
            value.update(base_url=config.base_url, workspace=config.workspace,
                         updated_at=datetime.now(timezone.utc).isoformat())
            try:
                self._write_control(value)
            except OSError:
                raise HTTPException(503, detail={"code": "bridge_settings_write_failed"}) from None
            self.persisted, self.updated_at = True, value["updated_at"]
            await self.activate(config)
            return self.projection()

    async def probe(self):
        async with self.lock:
            result = {"source": "configured_bridge_http", "connection": "not_checked",
                      "authentication": "not_checked", "capabilities": "not_checked",
                      "profiles": [], "node_readiness": "unknown", "admission": None, "real_generation_verified": False,
                      "formal_delivery": False, "code": None}
            if self.config.mode == "disabled":
                return {**result, "code": "bridge_disabled"}
            if self.error or self.config.config_error:
                return {**result, "code": "bridge_not_available"}
            client = self.client_factory(self.config.base_url, self.config.token)
            try:
                async with asyncio.timeout(8):
                    value = await client.capabilities()
                result.update(connection="reachable", authentication="accepted")
                result.update(profiles=capabilities_projection(value), capabilities="compatible")
                states = {"unknown", "offline", "available", "busy", "attention"}
                node = value.get("node_status")
                if isinstance(node, dict) and isinstance(node.get("state"), str) and node["state"] in states:
                    result["node_readiness"] = node["state"]
                admission = value.get("admission")
                if (isinstance(admission, dict) and type(admission.get("accepting_new_tasks")) is bool
                        and isinstance(admission.get("mode"), str) and admission["mode"] in {"enabled", "draining"}):
                    result["admission"] = {"accepting_new_tasks": admission["accepting_new_tasks"], "mode": admission["mode"]}
                advertised = {p.get("execution_profile_id"): p for p in value.get("profiles", []) if isinstance(p, dict)}
                for profile in result["profiles"]:
                    state = advertised.get(profile["execution_profile_id"], {}).get("availability")
                    profile["availability"] = state if isinstance(state, str) and state in states else "unknown"
            except BridgeError as exc:
                if exc.status in {401, 403}:
                    result.update(connection="reachable", authentication="rejected", code="bridge_authentication_failed")
                elif exc.code in {"invalid_bridge_response", "unsupported_capabilities_version", "invalid_bridge_capabilities"}:
                    result.update(connection="reachable", capabilities="incompatible", code=exc.code)
                else:
                    result.update(connection="unavailable" if exc.code == "bridge_unreachable" else "reachable",
                                  code="bridge_unreachable" if exc.code == "bridge_unreachable" else "bridge_probe_failed")
            except TimeoutError:
                result.update(connection="unavailable", code="bridge_probe_timeout")
            finally:
                await client.close()
            return result


class BridgeDispatch:
    """Route only bridge paths to a lifecycle-owned app, never the host APIs."""
    def __init__(self, app, controller):
        self.app, self.controller = app, controller

    async def __call__(self, scope, receive, send):
        path = scope.get("path", "")
        bridge = path == PREFIX or path.startswith(PREFIX + "/") or any(
            path == root or path.startswith(root + "/") for root in
            ("/render-bridge-preview", "/render-bridge-native-test", "/render-bridge-diagnostics"))
        if scope["type"] == "http" and bridge:
            async with self.controller.lock:
                application = self.controller.application
                if application is None:
                    await JSONResponse({"detail": "Not Found"}, status_code=404, headers=HEADERS)(scope, receive, send)
                else:
                    await application(scope, receive, send)
            return
        await self.app(scope, receive, send)


def install_render_bridge_admin(app, *, admin_resolver, session_user, auth_enabled, project_snapshot,
                                native_gateway_factory=None, baseline=None, client_factory=BridgeClient):
    controller = BridgeAdminController(baseline=baseline or BridgeSettings.from_env(preserve_disabled=True),
        admin_resolver=admin_resolver, session_user=session_user, auth_enabled=auth_enabled,
        project_snapshot=project_snapshot, native_gateway_factory=native_gateway_factory,
        client_factory=client_factory)
    router = APIRouter(prefix="/v1/admin/render-bridge")

    async def authorize(request, *, write=False):
        value = admin_resolver(request, request.headers.get("authorization", ""))
        if inspect.isawaitable(value):
            await value
        if write:
            if request.headers.get("x-alchemy-bridge-admin") != "1" or request.headers.get("sec-fetch-site") not in {None, "same-origin", "none"}:
                raise HTTPException(403, detail={"code": "same_origin_required"})
            origin = request.headers.get("origin")
            if origin:
                actual, supplied = urlsplit(str(request.base_url)), urlsplit(origin)
                if (actual.scheme, actual.netloc) != (supplied.scheme, supplied.netloc) or supplied.path not in {"", "/"}:
                    raise HTTPException(403, detail={"code": "same_origin_required"})

    @router.get("/settings")
    async def settings(request: Request):
        await authorize(request)
        return JSONResponse(controller.projection(), headers=HEADERS)

    @router.post("/settings")
    async def save(request: Request):
        await authorize(request, write=True)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 8192:
                raise HTTPException(413, detail={"code": "request_too_large"})
        try:
            value = AdminSettingsUpdate.model_validate_json(body)
        except ValidationError:
            raise HTTPException(422, detail={"code": "invalid_bridge_settings"}) from None
        return JSONResponse(await controller.save(value), headers=HEADERS)

    @router.post("/probe")
    async def probe(request: Request):
        await authorize(request, write=True)
        return JSONResponse(await controller.probe(), headers=HEADERS)

    @app.on_event("startup")
    async def start():
        controller.read_saved()
        controller.primary_maintenance_task = asyncio.create_task(controller.maintain_primary())
        controller.primary_health_task = asyncio.create_task(PrimaryHealthMonitor("v1").run_forever())
        if controller.error:
            return
        try:
            controller.publish_environment_defaults()
        except OSError:
            controller.error = "bridge_settings_write_failed"
            return
        await controller.activate(controller.config)

    @app.on_event("shutdown")
    async def stop():
        if controller.primary_health_task:
            controller.primary_health_task.cancel()
            try:
                await controller.primary_health_task
            except asyncio.CancelledError:
                pass
        if controller.primary_maintenance_task:
            controller.primary_maintenance_task.cancel()
            try:
                await controller.primary_maintenance_task
            except asyncio.CancelledError:
                pass
        async with controller.lock:
            if controller.application:
                await controller.lifespan.__aexit__(None, None, None)
                controller.application = None

    app.include_router(router)
    app.add_middleware(BridgeDispatch, controller=controller)
    app.state.render_bridge_admin = controller
    return controller
