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
import re
import sqlite3
from urllib.parse import urlsplit

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from typing import Literal

from .client import BridgeClient, BridgeError, BridgeRewardClient
from .diagnostics import capabilities_projection
from .routes import HEADERS, PREFIX, install_render_bridge
from .settings import BridgeSettings
from .node_rewards import NodeRewardStoreError, POINTS_PER_IMAGE, install_node_reward_account_routes
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


class RewardBindingCorrection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    pool_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    node_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    executor_instance: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    expected_user_id: int = Field(gt=0)
    expected_revision: int = Field(ge=1)
    new_user_id: int = Field(gt=0)


class BridgeAdminController:
    def __init__(self, *, baseline, admin_resolver, session_user, auth_enabled,
                 project_snapshot, native_gateway_factory=None, client_factory=BridgeClient,
                 reward_client_factory=BridgeRewardClient):
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
        self.reward_client_factory = reward_client_factory
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
                local_http = (parsed.hostname in {"localhost", "127.0.0.1", "::1", "host.docker.internal"}
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
                "credential_source": "server_environment", "reward_metrics_configured": bool(config.reward_read_token),
                "persisted": self.persisted,
                "updated_at": self.updated_at, "configuration_error": self.error or config.config_error,
                "runtime_active": bool(self.application and not self.error),
                "recovery": "paused" if not self.application or self.error else "running",
                "real_generation_verified": False, "formal_delivery": False}

    async def reward_metrics(self):
        config = self.config
        if not config.reward_read_token or not config.base_url:
            return {"available": False, "code": "reward_metrics_not_configured", "nodes": []}
        client = None
        try:
            client = self.reward_client_factory(config.base_url, config.reward_read_token)
            async with asyncio.timeout(10):
                raw = await client.nodes()
            nodes = []
            allowed_profiles = {"fake-image", "codex-image", "midjourney-manual"}
            allowed_counts = ("total_started", "succeeded", "failed", "in_progress",
                              "awaiting_user", "unknown", "canceled", "ack_accepted",
                              "ack_rejected", "ack_pending", "rewardable_images")
            for item in raw.get("nodes", []):
                if not isinstance(item, dict):
                    continue
                node_id, executor, pool_id = (item.get("node_id"), item.get("executor_instance"),
                                               item.get("pool_id"))
                if not all(isinstance(v, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", v)
                           for v in (node_id, executor, pool_id)):
                    continue
                provider_ref = item.get("provider_ref")
                if provider_ref is not None and (not isinstance(provider_ref, str)
                        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}", provider_ref)):
                    provider_ref = None
                raw_metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
                metrics = {key: value for key in allowed_counts
                           if type(value := raw_metrics.get(key)) is int and 0 <= value <= 2**53}
                current = item.get("current_execution")
                if isinstance(current, dict):
                    state = current.get("state")
                    current = {"state": state[:32] if isinstance(state, str) else "unknown",
                               "profile": current.get("profile") if isinstance(current.get("profile"), str)
                                   and current.get("profile") in allowed_profiles else None,
                               "started_at": current.get("started_at") if isinstance(current.get("started_at"), str) else None,
                               "counted": current.get("counted") is True}
                else:
                    current = None
                profiles = item.get("profiles") if isinstance(item.get("profiles"), list) else []
                heartbeat_age = item.get("heartbeat_age_seconds")
                nodes.append({"pool_id": pool_id, "pool_name": str(item.get("pool_name", ""))[:80],
                    "node_id": node_id, "executor_instance": executor, "provider_ref": provider_ref,
                    "node_state": item.get("node_state") if isinstance(item.get("node_state"), str) and item.get("node_state") in
                        {"active", "draining", "revoked"} else "unknown",
                    "liveness": item.get("liveness") if isinstance(item.get("liveness"), str) and item.get("liveness") in
                        {"online", "busy", "needs_attention", "offline"} else "unknown",
                    "heartbeat_age_seconds": heartbeat_age if type(heartbeat_age) is int and heartbeat_age >= 0 else None,
                    "last_seen_at": item.get("last_seen_at") if isinstance(item.get("last_seen_at"), str) else None,
                    "profiles": [p for p in profiles if isinstance(p, str) and p in allowed_profiles],
                    "current_execution": current, "metrics": metrics})
            return {"available": True, "tracking": "since_schema_v5_activation",
                    "tracking_since": raw.get("tracking_since"),
                    "truncated": raw.get("truncated") is True, "nodes": nodes}
        except TimeoutError:
            return {"available": False, "code": "reward_metrics_timeout", "nodes": []}
        except BridgeError as exc:
            return {"available": False, "code": exc.code, "nodes": []}
        except (ValueError, TypeError):
            return {"available": False, "code": "reward_metrics_configuration_invalid", "nodes": []}
        finally:
            if client is not None:
                await client.close()

    async def reward_claim_approval(self, digest: str):
        config = self.config
        if (not config.reward_read_token or not config.base_url
                or not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest)):
            return {"available": False, "code": "claim_approval_not_configured"}
        client = None
        try:
            client = self.reward_client_factory(config.base_url, config.reward_read_token)
            async with asyncio.timeout(10):
                raw = await client.claim_approval(digest)
            if not isinstance(raw, dict):
                raise ValueError()
            identity = (raw.get("pool_id"), raw.get("node_id"), raw.get("executor_instance"))
            if not all(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", value)
                       for value in identity):
                raise ValueError()
            state = raw.get("node_state")
            if state not in {"active", "draining", "revoked"}:
                raise ValueError()
            images = raw.get("rewardable_images")
            if type(images) is not int or not 0 <= images <= 2**53:
                raise ValueError()
            return {"available": True, "pool_id": identity[0], "node_id": identity[1],
                    "executor_instance": identity[2], "node_state": state,
                    "rewardable_images": images,
                    "pool_name": str(raw.get("pool_name", ""))[:80]}
        except TimeoutError:
            return {"available": False, "code": "claim_approval_timeout"}
        except BridgeError:
            return {"available": False, "code": "claim_approval_unavailable"}
        except (ValueError, TypeError, AttributeError):
            return {"available": False, "code": "claim_approval_invalid"}
        finally:
            if client is not None:
                await client.close()

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
                                native_gateway_factory=None, baseline=None, client_factory=BridgeClient,
                                reward_client_factory=BridgeRewardClient, account_loader=None,
                                node_rewards_database_path=None):
    controller = BridgeAdminController(baseline=baseline or BridgeSettings.from_env(preserve_disabled=True),
        admin_resolver=admin_resolver, session_user=session_user, auth_enabled=auth_enabled,
        project_snapshot=project_snapshot, native_gateway_factory=native_gateway_factory,
        client_factory=client_factory, reward_client_factory=reward_client_factory)
    install_node_reward_account_routes(app, session_user=session_user,
        account_loader=account_loader, auth_enabled=auth_enabled,
        reward_metrics_loader=controller.reward_metrics,
        reward_claim_approval_loader=controller.reward_claim_approval,
        node_binding_status_secret=controller.baseline.reward_read_token,
        database_path=(node_rewards_database_path or
                       controller.baseline.storage / "node-rewards.sqlite3"))
    router = APIRouter(prefix="/v1/admin/render-bridge")

    async def authorize(request, *, write=False):
        value = admin_resolver(request, request.headers.get("authorization", ""))
        if inspect.isawaitable(value):
            value = await value
        if write:
            if request.headers.get("x-alchemy-bridge-admin") != "1" or request.headers.get("sec-fetch-site") not in {None, "same-origin", "none"}:
                raise HTTPException(403, detail={"code": "same_origin_required"})
            origin = request.headers.get("origin")
            if origin:
                actual, supplied = urlsplit(str(request.base_url)), urlsplit(origin)
                if (actual.scheme, actual.netloc) != (supplied.scheme, supplied.netloc) or supplied.path not in {"", "/"}:
                    raise HTTPException(403, detail={"code": "same_origin_required"})
        return value

    @router.get("/settings")
    async def settings(request: Request):
        await authorize(request)
        return JSONResponse(controller.projection(), headers=HEADERS)

    @router.get("/rewards")
    async def rewards(request: Request):
        await authorize(request)
        value = await controller.reward_metrics()
        if value.get("available") is not True or not isinstance(value.get("nodes"), list):
            return JSONResponse(value, headers=HEADERS)

        projected = dict(value)
        nodes = [dict(item) for item in value["nodes"] if isinstance(item, dict)]
        store = getattr(app.state, "node_reward_account_store", None)
        try:
            bindings = store.list_all_bindings() if store is not None else None
            binding_history = store.list_all_binding_history() if store is not None else None
        except (sqlite3.Error, OSError):
            bindings = None
            binding_history = None

        if bindings is None or binding_history is None:
            for node in nodes:
                node.update(reward_account_bound=None, reward_images=None,
                            reward_points=None, reward_status="unavailable")
            projected.update(nodes=nodes, reward_account_stats_available=False,
                             reward_totals={"complete": False, "bound_nodes": None,
                                            "reward_images": None, "reward_points": None,
                                            "pending_nodes": None})
            return JSONResponse(projected, headers=HEADERS)

        binding_index = {
            (item["pool_id"], item["node_id"], item["executor_instance"]): item
            for item in bindings
        }
        history_index = {}
        for item in binding_history:
            identity = (item["pool_id"], item["node_id"], item["executor_instance"])
            history_index[identity] = history_index.get(identity, 0) + item["final_images"]
        visible_identities = set()
        accrued_total = 0
        historical_total = sum(item["final_images"] for item in binding_history)
        pending_nodes = 0
        for node in nodes:
            identity = (node.get("pool_id"), node.get("node_id"), node.get("executor_instance"))
            visible_identities.add(identity)
            binding = binding_index.get(identity)
            historical_images = history_index.get(identity, 0)
            node.update(historical_reward_images=historical_images,
                        historical_reward_points=f"{POINTS_PER_IMAGE * historical_images:.2f}")
            if binding is None:
                node.update(reward_account_bound=False, reward_images=0,
                            reward_points="0.00", reward_status="unbound")
                continue

            node.update(reward_account_bound=True,
                        reward_account_user_id=binding["user_id"],
                        binding_revision=binding["binding_revision"])
            metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
            ledger_images = metrics.get("rewardable_images")
            baseline_images = binding.get("baseline_images")
            if (type(ledger_images) is not int or ledger_images < 0
                    or type(baseline_images) is not int or baseline_images < 0):
                node.update(reward_account_bound=True, reward_images=None,
                            reward_points=None, reward_status="baseline_pending"
                            if baseline_images is None else "metrics_unavailable")
                pending_nodes += 1
                continue

            images = max(0, ledger_images - baseline_images)
            points = f"{POINTS_PER_IMAGE * images:.2f}"
            node.update(reward_account_bound=True, reward_images=images,
                        reward_points=points, reward_status="accruing")
            accrued_total += images

        missing_bindings = len(set(binding_index) - visible_identities)
        pending_nodes += missing_bindings
        complete = pending_nodes == 0
        projected.update(nodes=nodes, reward_account_stats_available=True,
                         reward_totals={"complete": complete, "bound_nodes": len(bindings),
                                        "reward_images": accrued_total + historical_total if complete else None,
                                        "reward_points": f"{POINTS_PER_IMAGE * (accrued_total + historical_total):.2f}"
                                        if complete else None,
                                        "historical_images": historical_total,
                                        "historical_points": f"{POINTS_PER_IMAGE * historical_total:.2f}",
                                        "historical_periods": len(binding_history),
                                        "pending_nodes": pending_nodes})
        return JSONResponse(projected, headers=HEADERS)

    @router.post("/rewards/bindings/correct")
    async def correct_reward_binding(request: Request):
        admin_identity = await authorize(request, write=True)
        admin_user_id = admin_identity.get("user_id") if isinstance(admin_identity, dict) else None
        if type(admin_user_id) is not int or admin_user_id <= 0:
            raise HTTPException(503, detail={"code": "admin_identity_unavailable"}, headers=HEADERS)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 4096:
                raise HTTPException(413, detail={"code": "request_too_large"}, headers=HEADERS)
        try:
            correction = RewardBindingCorrection.model_validate_json(body)
        except ValidationError:
            raise HTTPException(422, detail={"code": "invalid_reward_binding_correction"},
                                headers=HEADERS) from None
        if correction.new_user_id == correction.expected_user_id:
            raise HTTPException(422, detail={"code": "reward_account_unchanged"}, headers=HEADERS)
        if account_loader is None:
            raise HTTPException(503, detail={"code": "reward_account_validation_unavailable"},
                                headers=HEADERS)
        try:
            target_account = account_loader(correction.new_user_id)
            if inspect.isawaitable(target_account):
                target_account = await target_account
        except Exception:
            raise HTTPException(503, detail={"code": "reward_account_validation_unavailable"},
                                headers=HEADERS) from None
        if (getattr(target_account, "user_id", None) != correction.new_user_id
                or getattr(target_account, "status", "") != "active"):
            raise HTTPException(409, detail={"code": "reward_destination_account_unavailable"},
                                headers=HEADERS)

        try:
            metrics = await controller.reward_metrics()
        except Exception:
            raise HTTPException(503, detail={"code": "reward_metrics_unavailable"},
                                headers=HEADERS) from None
        if (metrics.get("available") is not True or metrics.get("truncated") is not False
                or not isinstance(metrics.get("nodes"), list)):
            raise HTTPException(503, detail={"code": "reward_metrics_incomplete"}, headers=HEADERS)
        identity = (correction.pool_id, correction.node_id, correction.executor_instance)
        matches = [item for item in metrics["nodes"] if isinstance(item, dict) and
                   (item.get("pool_id"), item.get("node_id"), item.get("executor_instance")) == identity]
        if len(matches) != 1:
            code = "reward_node_not_found" if not matches else "reward_node_ambiguous"
            raise HTTPException(409 if matches else 404, detail={"code": code}, headers=HEADERS)
        node = matches[0]
        node_metrics = node.get("metrics") if isinstance(node.get("metrics"), dict) else {}
        observed_images = node_metrics.get("rewardable_images")
        if type(observed_images) is not int or observed_images < 0:
            raise HTTPException(503, detail={"code": "reward_image_count_unavailable"}, headers=HEADERS)
        store = getattr(app.state, "node_reward_account_store", None)
        if store is None:
            raise HTTPException(503, detail={"code": "node_reward_storage_unavailable"}, headers=HEADERS)
        try:
            result = store.correct_binding(
                pool_id=correction.pool_id,
                node_id=correction.node_id,
                executor_instance=correction.executor_instance,
                expected_user_id=correction.expected_user_id,
                expected_revision=correction.expected_revision,
                new_user_id=correction.new_user_id,
                observed_images=observed_images,
                corrected_by_admin_user_id=admin_user_id,
            )
        except NodeRewardStoreError as exc:
            raise HTTPException(exc.status, detail={"code": exc.code}, headers=HEADERS) from None
        except (sqlite3.Error, OSError):
            raise HTTPException(503, detail={"code": "node_reward_storage_unavailable"},
                                headers=HEADERS) from None
        return JSONResponse({**result, "node_id": correction.node_id,
                             "image_boundary": observed_images}, headers=HEADERS)

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
