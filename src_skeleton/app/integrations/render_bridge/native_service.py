"""Opt-in bounded native integration, separate from the free-prompt preview.

The injected Alchemy gateway owns planning, freeze, native checkpoint, review and
registration. This coordinator owns only HTTP delivery/mappings. It never writes
native job/output/usage stores itself.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
import time
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing import Annotated, Literal

from .attention import attention_projection
from .client import BridgeError
from .models import validate_image
from .options import FORMAT_MIMES, native_profile
from .service import PreviewService, digest
from .routing_policy import routing_decision


class NativeTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    client_request_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")
    project_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    user_input: str = Field(min_length=1, max_length=16000)
    uploaded_asset_ids: list[Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")]] = Field(default_factory=list, max_length=2)
    size: Literal["1024x1024", "1024x768", "768x1024"] = "1024x1024"
    profile_id: Literal["fake-image", "codex-image", "midjourney-manual"] = "fake-image"
    quality: Literal["auto"] = "auto"
    output_format: Literal["png", "jpeg"] = "png"
    routing_strategy: Literal["bridge_only", "prefer_bridge"] = "bridge_only"
    local_only: bool = False
    acknowledge_cloud_fallback: bool = False
    acknowledge_synthetic_native_test: bool = False
    acknowledge_native_development: bool = False

    @model_validator(mode="after")
    def require_explicit_development_ack(self):
        if self.routing_strategy == "prefer_bridge" and not self.acknowledge_cloud_fallback:
            raise ValueError("Cloud cost and material transmission acknowledgement required")
        if self.profile_id == "fake-image":
            if not (self.acknowledge_synthetic_native_test or self.acknowledge_native_development):
                raise ValueError("Synthetic/native development acknowledgement required")
        elif not self.acknowledge_native_development:
            raise ValueError("Real-profile development acknowledgement required")
        return self

    @field_validator("uploaded_asset_ids")
    @classmethod
    def distinct_references(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Duplicate references are not supported")
        return values


class NativeBridgeService(PreviewService):
    def __init__(self, settings, project_snapshot, gateway, *, client=None, target_factory=None):
        super().__init__(replace(settings, storage=Path(settings.storage) / "native"), project_snapshot, client=client)
        self.gateway = gateway
        self.target_factory = target_factory
        self.gateway_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-native-authority")
        self.gateway_busy = False

    async def close(self):
        await super().close()
        self.gateway_executor.shutdown(wait=True, cancel_futures=True)

    def _health_key(self):
        return "health_" + digest([digest(self.settings.base_url), self.settings.workspace])

    async def tick(self):
        # Recovery must progress between user requests, not depend on repeated
        # Generate clicks. One bounded authenticated capabilities fetch per 5s,
        # only while the administrator enabled this explicit default-off policy.
        if self.settings.mode == "enabled" and self.settings.auto_fallback_enabled and not self.tick_lock.locked():
            key = self._health_key()
            if await self.local(self.store.health_poll, key, time.time()):
                try:
                    async with asyncio.timeout(5):
                        caps = await self.client.capabilities()
                    for profile_id in self.settings.native_profiles:
                        cache_key = digest([digest(self.settings.base_url), self.settings.workspace, profile_id])
                        await self.local(self.store.routing_observation, cache_key, caps, profile_id, time.time())
                except BridgeError as exc:
                    if exc.retry_not_before:
                        await self.local(self.store.health_poll, key, time.time(), defer_until=exc.retry_not_before)
                    await self._health_fault(clear=not exc.retryable or exc.status in {401, 403})
                except TimeoutError:
                    await self._health_fault()
        await super().tick()

    async def _health_fault(self, *, clear=False):
        # Interrupt recovery evidence, not task execution. Known authorization
        # denial invalidates cached negotiation until a successful live read.
        for profile_id in self.settings.native_profiles:
            key = digest([digest(self.settings.base_url), self.settings.workspace, profile_id])
            if clear:
                await self.local(self.store.routing_observation, key, {}, profile_id, time.time())
            else:
                await self.local(self.store.routing_fault, key)

    def target(self, record):
        if self.target_factory:
            return self.target_factory(**record["target"])
        from alchemy_creative_agent_3_0.app.product_api.render_bridge_facade import NativeFreezeTarget
        return NativeFreezeTarget(**record["target"])

    async def authority(self, method, *args, **kwargs):
        # Native planning/review may wait on its own dependencies. It does not
        # occupy the host or our short mapping-read executor. A timed-out waiter
        # must not free admission while the synchronous authority is still alive.
        if self.gateway_busy:
            raise BridgeError("native_authority_busy", status=503)
        self.gateway_busy = True
        from functools import partial
        future = asyncio.get_running_loop().run_in_executor(self.gateway_executor, partial(method, *args, **kwargs))
        future.add_done_callback(lambda _: setattr(self, "gateway_busy", False))
        try:
            result = await asyncio.shield(future)
            if not isinstance(result, dict):
                raise BridgeError("invalid_native_outcome", retryable=False)
            return result
        except BridgeError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "native_operation_failed")
            if not isinstance(code, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,95}", code):
                code = "native_operation_failed"
            status = getattr(exc, "status_code", 503)
            raise BridgeError(code, status=status,
                              retryable=status >= 500 or code == "render_bridge_registration_in_progress") from None

    async def create(self, owner, request: NativeTaskCreate):
        if self.settings.mode != "enabled":
            raise BridgeError("bridge_draining", status=409, retryable=False)
        if not owner.isdigit() or int(owner) <= 0:
            raise BridgeError("native_authenticated_owner_required", status=403, retryable=False)
        if not await self.snapshot(owner, request.project_id):
            raise BridgeError("project_not_found", status=404, retryable=False)
        if request.profile_id not in self.settings.native_profiles or request.profile_id not in self.settings.profiles:
            raise BridgeError("native_profile_not_enabled", status=422, retryable=False)
        if request.profile_id == "midjourney-manual" and request.uploaded_asset_ids:
            raise BridgeError("native_profile_references_unsupported", status=422, retryable=False)
        if request.routing_strategy == "prefer_bridge" and not self.settings.auto_fallback_enabled:
            raise BridgeError("auto_fallback_disabled", status=409, retryable=False)
        width, height = map(int, request.size.split("x"))
        summary = {"project_id": request.project_id, "user_input": request.user_input,
                   "profile_id": request.profile_id, "width": width, "height": height, "seed": 0}
        # Preserve the original no-reference/square idempotency digest.
        if request.uploaded_asset_ids:
            summary["uploaded_asset_ids"] = request.uploaded_asset_ids
        if request.output_format != "png":
            summary["output_format"] = request.output_format
        if request.routing_strategy != "bridge_only" or request.local_only:
            summary.update(routing_strategy=request.routing_strategy, local_only=request.local_only,
                           acknowledge_cloud_fallback=request.acknowledge_cloud_fallback)
        job_id = "brn_" + uuid4().hex
        record = {"id": job_id, "owner": owner, "workspace": self.settings.workspace,
            "endpoint_fingerprint": digest(self.settings.base_url), "project_id": request.project_id,
            "request_key": request.client_request_id, "digest": digest(summary), "request": summary,
            "origin_key": "alchemy_native_test_" + uuid4().hex, "binding_id": "native_test_" + uuid4().hex,
            "plan_key": "bridge_plan_" + uuid4().hex, "import_key": "bridge_import_" + uuid4().hex,
            "client_receipt_id": "native_ack_" + uuid4().hex,
            "state": "plan_pending", "created_at": datetime.now(timezone.utc).isoformat(),
            "next_poll_at": 0, "errors": 0, "last_error": None, "cancel_requested": False,
            "plan_attempted": False, "target": None, "frozen": None, "wire_request": None,
            "project_binding_version": "semantic_v2",
            "remote_task_id": None, "native_phase": "planning", "native_outcome": None,
            "delivery_ack": "pending", "selected_route": None, "route_generation": 0,
            "bridge_create_attempted": False, "cloud_execution_attempted": False,
            "cloud_execution_key": "cloud_" + uuid4().hex, "queue_elapsed": 0.0,
            "queue_wait_seconds": self.settings.queue_wait_seconds}
        return await self.local(self.store.create, record, [])

    async def references(self, owner, project_id):
        if not await self.snapshot(owner, project_id):
            raise BridgeError("project_not_found", status=404, retryable=False)
        return await self.authority(self.gateway.list_references, int(owner), project_id)

    async def visible(self, owner, job_id):
        record = await self.local(self.store.get, job_id)
        if (not record or record["owner"] != owner or record["workspace"] != self.settings.workspace
                or not await self.snapshot(owner, record["project_id"])):
            raise BridgeError("task_not_found", status=404, retryable=False)
        record = await self._reopen_legacy_review(record)
        return record, True

    async def _reopen_legacy_review(self, record):
        outcome = record.get("native_outcome") or {}
        if (self.settings.mode != "disabled" and record["state"] == "registered"
                and "review_pending" not in outcome
                and outcome.get("review_status") in {"finalizing", "blocked"}):
            record = await self.local(self.store.patch, record["id"], {
                "state": "review_pending", "native_phase": "ack_pending", "next_poll_at": 0,
            })
        return record

    async def list(self, owner, project_id):
        if not await self.snapshot(owner, project_id):
            raise BridgeError("project_not_found", status=404, retryable=False)
        return [self.public(await self._reopen_legacy_review(record))
                for record in await self.local(self.store.list, owner, project_id)
                if record["workspace"] == self.settings.workspace]

    async def cancel(self, owner, job_id):
        record, _ = await self.visible(owner, job_id)
        if record["state"] == "registered" or (record.get("native_outcome") or {}).get("status") == "registered":
            raise BridgeError("native_already_registered", status=409, retryable=False)
        return await super().cancel(owner, job_id)

    @staticmethod
    def public(record, **_):
        native = record.get("native_outcome") or {}
        return {"integration_job_id": record["id"], "project_id": record["project_id"],
            "state": record["state"], "created_at": record["created_at"], "last_error": record.get("last_error"),
            "profile_id": record["request"]["profile_id"],
            "action_required_detail": attention_projection(record),
            "test_fixture": record["request"]["profile_id"] == "fake-image" and record.get("selected_route") != "cloud", "real_tool_verified": False,
            "native_registration": native.get("status", "pending"), "delivery_ack": record.get("delivery_ack", "pending"),
            "native_registration_ref": native.get("native_registration_ref"),
            "review_status": native.get("current_review_status", native.get("review_status")),
            "review_pending": native.get("review_pending", record["state"] == "review_pending"), "formal_delivery": False,
            "billing": native.get("billing", {"mode": "v3_zero_credit_stub", "charged": False}),
            "size": f"{record['request']['width']}x{record['request']['height']}",
            "output_format": record["request"].get("output_format", "png"),
            "format_semantics": "original_artifact_postcondition",
            "quality": "auto", "quality_semantics": "unspecified_only", "input_fidelity": None,
            "reference_count": len(record["request"].get("uploaded_asset_ids", [])),
            "reference_effect_verified": False,
            "target": record.get("target"),
            "routing_strategy": record["request"].get("routing_strategy", "bridge_only"),
            "selected_route": record.get("selected_route"), "routing_reason": record.get("routing_reason"),
            "cloud_execution_status": record.get("cloud_execution_status"),
            "cloud_upstream_cost_possible": record.get("selected_route") == "cloud"}

    async def _advance(self, record):
        owner = int(record["owner"])
        profile_id = record["request"]["profile_id"]
        if (record["endpoint_fingerprint"] != digest(self.settings.base_url)
                or record["workspace"] != self.settings.workspace
                or not await self.snapshot(record["owner"], record["project_id"])):
            await self._finish(record, state="blocked_scope")
            return
        record = await self.local(self.store.get, record["id"])
        if record["cancel_requested"]:
            await self._cancel_native(record)
            return
        if record.get("selected_route") == "cloud":
            await self._cloud(record)
            return
        routing_context = None
        if self._prefers_bridge(record):
            routing_context = await self._routing_context(record)
            action, reason = self._route_decision(record, routing_context, submitted=bool(record.get("bridge_create_attempted")))
            if action == "wait" and not record.get("bridge_create_attempted") and not record.get("remote_task_id"):
                await self._finish(record, state="routing_wait", routing_reason=reason)
                return
        # Negotiate before any Brain planning effect. The old fake/PNG v1
        # contract remains usable without the additive descriptor. Persisted
        # wire requests are never reinterpreted or upgraded during recovery.
        if not record.get("wire_request") and not record.get("profile_snapshot"):
            if profile_id not in self.settings.native_profiles or profile_id not in self.settings.profiles:
                raise BridgeError("native_profile_not_enabled", retryable=False)
            capabilities = routing_context.get("capabilities", {}) if routing_context is not None else await self.client.capabilities()
            profile = native_profile(capabilities, profile_id=profile_id,
                output_format=record["request"].get("output_format", "png"),
                reference_count=len(record["request"].get("uploaded_asset_ids", [])),
                width=record["request"]["width"], height=record["request"]["height"])
            await self._patch(record, profile_snapshot=profile)
        if not record["target"]:
            if record["plan_attempted"]:
                plan = await self.authority(self.gateway.plan_status, owner, record["project_id"], record["plan_key"])
                # Unknown planning effects never cause a new Brain invocation.
                if plan["status"] in {"plan_unknown", "not_planned"}:
                    await self._finish(record, state="plan_unknown", last_error="native_plan_outcome_unknown")
                    return
            else:
                await self._patch(record, plan_attempted=True)
                kwargs = {"uploaded_asset_ids": record["request"].get("uploaded_asset_ids", []),
                          "size": f"{record['request']['width']}x{record['request']['height']}"}
                if profile_id != "fake-image" or record["request"].get("output_format", "png") != "png":
                    kwargs.update(execution_profile_id=profile_id, output_format=record["request"].get("output_format", "png"))
                plan = await self.authority(self.gateway.create_plan, owner, record["project_id"],
                                            record["request"]["user_input"], record["plan_key"], **kwargs)
            if plan["status"] != "planned":
                await self._finish(record, state="plan_blocked" if plan["status"] == "plan_blocked" else "plan_unknown",
                                   last_error=plan.get("code", "native_plan_not_ready"))
                return
            await self._patch(record, target=plan["target"], native_phase="planned")
        record = await self.local(self.store.get, record["id"])
        if record["cancel_requested"]:
            await self._cancel_native(record)
            return
        if record["native_phase"] in {"registering", "ack_pending"}:
            await self._register_or_confirm(record)
            return
        frozen = await self.authority(self.gateway.prepare, owner, self.target(record), execution_profile_id=profile_id)
        if record["frozen"] and frozen["frozen_request_id"] != record["frozen"]["frozen_request_id"]:
            await self._finish(record, state="blocked_revision")
            return
        if not record["frozen"]:
            await self._patch(record, frozen=frozen, native_intent_digest=digest(frozen))
        options = record["frozen"].get("image_options", {})
        if (options.get("quality") != "auto" or options.get("input_fidelity") is not None
                or options.get("output_format") != record["request"].get("output_format", "png")):
            raise BridgeError("native_frozen_image_options_unsupported", retryable=False)
        dimensions = self._frozen_dimensions(record)
        if record.get("withdrawal_request") and not record.get("fallback_fenced"):
            if await self._consider_cloud(record, routing_context, submitted=True):
                return
        if self._prefers_bridge(record) and not record.get("bridge_create_attempted"):
            if await self._consider_cloud(record, routing_context, submitted=False):
                return
        if record["wire_request"] is None:
            profile = record["profile_snapshot"]
            await self._freeze_inputs(record)
            references = []
            for index, (content, metadata) in enumerate(await self.local(self.store.inputs, record["id"])):
                payload = {key: metadata[key] for key in ("original_sha256", "size", "mime_type")}
                payload["input_key"] = f"{record['origin_key']}_{index}"
                result = await self.client.create_input(payload)
                if any(result.get(key) != value for key, value in payload.items()):
                    raise BridgeError("input_binding_mismatch", retryable=False)
                await self.client.upload_input(result["input_id"], content, metadata["mime_type"])
                references.append({"input_ref": result["input_id"], "role": "reference", "hash": metadata["original_sha256"]})
            parameters = {**dimensions, "seed": 0}
            if profile.get("negotiated_image_options"):
                parameters["image_options"] = profile["negotiated_image_options"]
            wire = {"schema_version": "1", "origin_key": record["origin_key"], "binding_id": record["binding_id"],
                "operation": "image.generate", "execution_profile_id": profile_id, "execution_profile_revision": "1",
                "prompt": frozen["prompt"], "parameters": parameters,
                "references": references, "output_slot": {"slot_id": "primary", "count": 1},
                "deadline": (datetime.now(timezone.utc)+timedelta(hours=1)).isoformat().replace("+00:00", "Z"), "routing": "bridge_only"}
            await self._patch(record, wire_request=wire, profile_snapshot=profile)
        if not record["remote_task_id"]:
            # Query same origin before every create, including the first one.
            try:
                remote = await self.client.by_origin(record["origin_key"])
            except BridgeError as exc:
                if exc.status != 404:
                    raise
                latest = await self.local(self.store.get, record["id"])
                if latest["cancel_requested"]:
                    await self._cancel_native(latest)
                    return
                current = await self.authority(self.gateway.prepare, owner, self.target(record), execution_profile_id=profile_id)
                if current["frozen_request_id"] != record["frozen"]["frozen_request_id"]:
                    await self._finish(record, state="blocked_revision")
                    return
                if self._prefers_bridge(record):
                    if record.get("bridge_create_attempted"):
                        await self._finish(record, state="creating_unknown", routing_reason="bridge_create_requires_reconciliation")
                        return
                    won = await self.local(self.store.compare_patch, record["id"],
                        {"route_generation": record["route_generation"], "selected_route": record.get("selected_route"),
                         "bridge_create_attempted": False},
                        {"selected_route": "bridge", "route_generation": record["route_generation"] + 1,
                         "bridge_create_attempted": True})
                    if won is None:
                        return
                    record.update(won)
                remote = await self.client.create_task(record["wire_request"])
            self._validate_task(record, remote)
            await self._patch(record, remote_task_id=remote["remote_task_id"])
        remote = await self.client.task(record["remote_task_id"])
        self._validate_task(record, remote)
        await self._patch(record, remote_state=remote["state"], action_required_detail=attention_projection(remote))
        if self._prefers_bridge(record) and remote["state"] in {"queued", "awaiting_user"} and not remote.get("receipt_id"):
            now = time.monotonic()
            epoch = time.time() - now
            # System monotonic time survives process restarts (including Windows).
            # A reboot/clock discontinuity starts a new sample, never guesses a
            # budget from a potentially jumped wall clock; accrued budget remains.
            same_clock = abs(epoch - record.get("queue_clock_epoch", epoch)) < 5
            previous = (record.get("queue_observed_monotonic") or now) if same_clock else now
            await self._patch(record, queue_elapsed=record.get("queue_elapsed", 0) + max(0, now - previous),
                              queue_observed_monotonic=now, queue_clock_epoch=epoch)
            if await self._consider_cloud(record, routing_context, submitted=True, remote=remote):
                return
        else:
            await self._patch(record, queue_observed_monotonic=None)

        if remote["state"] in {"failed", "canceled", "expired"}:
            await self._finish(record, state=remote["state"])
            return
        if not remote.get("receipt_id"):
            await self._finish(record, state=remote["state"])
            return
        receipt = await self.client.receipt(remote["receipt_id"])
        self._validate_receipt(record, remote, receipt)
        limit = min(record.get("profile_snapshot", {}).get("limits", {}).get("max_output_bytes", 1048576),
                    1048576 if profile_id == "fake-image" else 16777216)
        mime = FORMAT_MIMES[record["request"].get("output_format", "png")]
        content, headers = await self.client.artifact(receipt["artifact_id"], limit)
        if headers.get("content-type", "").split(";")[0] != mime or receipt["mime_type"] != mime:
            raise BridgeError("native_output_format_mismatch", retryable=False)
        metadata = await self.local(validate_image, content, mime, expected_hash=receipt["original_sha256"],
                                   expected_size=receipt["size"], max_bytes=limit, max_pixels=1048576)
        if metadata["dimensions"] != dimensions or receipt["dimensions"] != metadata["dimensions"]:
            raise BridgeError("native_fixture_dimensions_required", retryable=False)
        latest = await self.local(self.store.get, record["id"])
        if latest["cancel_requested"]:
            await self._cancel_native(latest)
            return
        await self.local(self.store.save_receipt, record["id"], receipt, content)
        await self._patch(record, native_phase="registering", receipt_id=receipt["receipt_id"])
        await self._register_or_confirm(record)

    @staticmethod
    def _prefers_bridge(record):
        return (record["request"].get("routing_strategy") == "prefer_bridge"
                and not record["request"].get("local_only", False)
                and record["request"].get("acknowledge_cloud_fallback") is True)

    async def _routing_context(self, record):
        key = digest([record["endpoint_fingerprint"], record["workspace"], record["request"]["profile_id"]])
        deadline = await self.local(self.store.health_retry_deadline, self._health_key())
        if deadline > time.time():
            raise BridgeError("bridge_retry_deferred", status=503, retry_not_before=deadline)
        try:
            capabilities = await self.client.capabilities()
        except BridgeError as exc:
            if exc.retry_not_before:
                await self.local(self.store.health_poll, self._health_key(), time.time(), defer_until=exc.retry_not_before)
            # Authorization failures and administrator rejections are not faults
            # that permit bypassing policy. Only transport/server outage can use
            # a previously authenticated, negotiated compatible profile cache.
            if not exc.retryable or exc.status in {401, 403}:
                cached = await self.local(self.store.routing_observation, key, {}, record["request"]["profile_id"], time.time())
            else:
                cached = await self.local(self.store.routing_fault, key)
            if not exc.retryable or exc.status < 500 or exc.retry_not_before:
                raise
            if not cached.get("observation"):
                raise
            return cached
        return await self.local(self.store.routing_observation, key, capabilities,
                                record["request"]["profile_id"], time.time())

    def _route_decision(self, record, context, *, submitted):
        return routing_decision(observation=context.get("observation"),
            capabilities=context.get("capabilities", {}), enabled=self._prefers_bridge(record),
            local_only=record["request"].get("local_only", False), submitted=submitted,
            queue_elapsed=record.get("queue_elapsed") if submitted else None,
            queue_wait_seconds=record.get("queue_wait_seconds", self.settings.queue_wait_seconds),
            now=time.time(), monotonic_now=time.monotonic())

    async def _consider_cloud(self, record, context, *, submitted, remote=None):
        if record.get("fallback_fenced"):
            return False
        action, reason = self._route_decision(record, context, submitted=submitted)
        if action == "wait" and record.get("withdrawal_request"):
            await self._finish(record, state="routing_wait", routing_reason=reason)
            return True
        if not record.get("withdrawal_request") and action not in {"cloud", "withdraw"}:
            return False
        if not hasattr(self.gateway, "cloud_admission"):
            await self._finish(record, state="routing_wait", routing_reason="cloud_continuation_unavailable")
            return True
        admission = await self.authority(self.gateway.cloud_admission, int(record["owner"]), self.target(record),
            frozen_request_id=record["frozen"]["frozen_request_id"], execution_profile_id=record["request"]["profile_id"])
        if admission.get("status") != "ready":
            await self._finish(record, state="routing_wait", routing_reason=admission.get("reason_code", "cloud_admission_blocked"))
            return True
        proof = record.get("withdrawal_proof")
        if submitted and not proof:
            payload = record.get("withdrawal_request")
            if not payload:
                if (remote is None or remote.get("task_digest") != digest(record["wire_request"])
                        or not isinstance(remote.get("attempt_id"), str)):
                    raise BridgeError("withdrawal_task_binding_missing", retryable=False)
                payload = {"schema_version": "1", "withdrawal_key": "withdraw_" + record["id"],
                    "origin_key": record["origin_key"], "attempt_id": remote["attempt_id"],
                    "task_digest": remote["task_digest"]}
                await self._patch(record, withdrawal_request=payload, withdrawal_reason=reason)
            try:
                proof = await self.client.withdrawal(record["remote_task_id"], payload["withdrawal_key"])
            except BridgeError as exc:
                if exc.status != 404:
                    raise
                try:
                    proof = await self.client.withdraw_before_start(record["remote_task_id"], payload)
                except BridgeError as rejected:
                    if rejected.status == 409 and rejected.code == "withdrawal_not_safe":
                        # This task now belongs exclusively to Bridge. A later
                        # health report cannot reset its execution authority.
                        await self._patch(record, withdrawal_request=None, fallback_fenced=True,
                                          routing_reason="bridge_execution_not_withdrawable")
                        return False
                    raise
            expected = {**payload, "status": "withdrawn_before_start", "task_id": record["remote_task_id"]}
            if (any(proof.get(k) != v for k, v in expected.items())
                    or not isinstance(proof.get("withdrawal_ref"), str) or not proof["withdrawal_ref"]):
                raise BridgeError("withdrawal_proof_binding_mismatch", retryable=False)
            await self._patch(record, withdrawal_proof=proof)
        if submitted and not proof:
            return False
        if record.get("bridge_create_attempted") and not proof:
            raise BridgeError("cloud_route_requires_withdrawal", retryable=False)
        won = await self.local(self.store.compare_patch, record["id"],
            {"route_generation": record["route_generation"], "selected_route": record.get("selected_route"),
             "cloud_execution_attempted": False},
            {"selected_route": "cloud", "route_generation": record["route_generation"] + 1,
             "routing_reason": record.get("withdrawal_reason", reason), "cloud_execution_status": "pending", "native_phase": "cloud"})
        if won is None:
            return True
        record.update(won)
        await self._cloud(record)
        return True

    async def _cloud(self, record, *, status_only=False):
        kwargs = {"frozen_request_id": record["frozen"]["frozen_request_id"],
                  "execution_key": record["cloud_execution_key"],
                  "execution_profile_id": record["request"]["profile_id"]}
        args = (int(record["owner"]), self.target(record))
        outcome = await self.authority(self.gateway.cloud_status, *args, **kwargs)
        if outcome.get("status") == "not_started" and not record.get("cloud_execution_attempted") and not status_only:
            # Commit possible execution BEFORE calling the configured provider.
            # Neither an exception nor a missing checkpoint ever clears this.
            won = await self.local(self.store.compare_patch, record["id"],
                {"selected_route": "cloud", "route_generation": record["route_generation"],
                 "cloud_execution_attempted": False},
                {"cloud_execution_attempted": True, "cloud_execution_status": "possible_execution"})
            if won is None:
                return
            record.update(won)
            outcome = await self.authority(self.gateway.cloud_execute, *args, **kwargs)
        registered = outcome.get("status") == "registered"
        blocked = outcome.get("status") == "blocked"
        if registered and record.get("cancel_requested"):
            await self._patch(record, cancel_requested=False)
        pending = registered and outcome.get("review_pending", False)
        await self._finish(record,
            state=("review_pending" if pending else "registered") if registered else ("routing_wait" if blocked else "cloud_unknown"),
            native_phase="cloud" if pending or not registered else "complete",
            native_outcome=outcome, cloud_execution_status="registered" if registered else ("blocked" if blocked else "cloud_unknown"),
            delivery_ack="not_applicable", routing_reason=record.get("routing_reason"),
            last_error=None if registered else outcome.get("reason_code", "cloud_execution_requires_reconciliation"),
            next_poll_at=time.time() + max(30, self.settings.poll_seconds))

    @staticmethod
    def _frozen_dimensions(record):
        size = record["frozen"].get("image_options", {}).get("size")
        if size not in {"1024x1024", "1024x768", "768x1024"}:
            raise BridgeError("native_fixture_dimensions_required", retryable=False)
        width, height = map(int, size.split("x"))
        if (width, height) != (record["request"]["width"], record["request"]["height"]):
            raise BridgeError("native_frozen_size_mismatch", retryable=False)
        return {"width": width, "height": height}

    async def _freeze_inputs(self, record):
        if record.get("inputs_frozen"):
            return
        references = record["frozen"].get("references", [])
        if not isinstance(references, list) or len(references) > 2:
            raise BridgeError("native_reference_count_invalid", retryable=False)
        inputs = []
        for reference in references:
            value = await self.authority(self.gateway.read_reference, int(record["owner"]), self.target(record),
                frozen_request_id=record["frozen"]["frozen_request_id"], reference_id=reference["reference_id"],
                **({"execution_profile_id": record["request"]["profile_id"]} if record["request"]["profile_id"] != "fake-image" else {}))
            content, mime = value["content"], value["mime_type"]
            metadata = await self.local(validate_image, content, mime, expected_hash=reference["sha256"],
                                       expected_size=reference["size_bytes"], max_pixels=1048576)
            inputs.append((content, metadata))
        # Atomic and idempotent snapshot, before the first remote input effect.
        await self.local(self.store.save_inputs, record["id"], inputs)
        await self._patch(record, inputs_frozen=True)

    async def _register_or_confirm(self, record):
        owner, target = int(record["owner"]), self.target(record)
        outcome = await self.authority(self.gateway.registration_status, owner, target, import_key=record["import_key"])
        if outcome["status"] == "not_registered" or (outcome["status"] == "import_unknown" and outcome.get("retry_safe") is True):
            stored = await self.local(self.store.receipt, record["id"])
            if not stored:
                raise BridgeError("native_receipt_missing", retryable=False)
            manifest, content = stored
            outcome = await self.authority(self.gateway.register_receipt, owner, target,
                import_key=record["import_key"], frozen_request_id=record["frozen"]["frozen_request_id"],
                receipt_id=manifest["receipt_id"], original_sha256=manifest["original_sha256"], artifact_bytes=content,
                execution_profile_id=record["request"]["profile_id"])
        await self._patch(record, native_outcome=outcome)
        if outcome["status"] == "rejected":
            stored = await self.local(self.store.receipt, record["id"])
            if not stored:
                raise BridgeError("native_receipt_missing", retryable=False)
            await self.client.reject_receipt(record["receipt_id"],
                client_receipt_id=record["client_receipt_id"], original_hash=stored[0]["original_sha256"],
                reason_code="native_registration_rejected")
            await self._finish(record, state="rejected", delivery_ack="rejected",
                               last_error=outcome.get("reason_code", "native_registration_rejected"))
            return
        if outcome["status"] != "registered":
            await self._finish(record, state="import_unknown", last_error="native_registration_unconfirmed")
            return
        if not outcome.get("native_registration_ref") or not outcome.get("original_sha256"):
            raise BridgeError("native_confirmation_missing", retryable=False)
        stored = await self.local(self.store.receipt, record["id"])
        if not stored or stored[0]["original_sha256"] != outcome["original_sha256"]:
            raise BridgeError("native_confirmation_hash_mismatch", retryable=False)
        await self._patch(record, native_phase="ack_pending")
        if record.get("delivery_ack") != "accepted":
            await self.client.accept_registered_receipt(record["receipt_id"],
                client_receipt_id=record["client_receipt_id"], original_hash=outcome["original_sha256"],
                normalized_hash=outcome.get("normalized_sha256"), native_registration_ref=outcome["native_registration_ref"])
        pending = outcome.get("review_pending", False)
        await self._finish(record, state="review_pending" if pending else "registered",
                           native_phase="ack_pending" if pending else "complete", delivery_ack="accepted",
                           next_poll_at=time.time() + (max(30, self.settings.poll_seconds) if pending
                                                     else self.settings.poll_seconds))

    async def _cancel_native(self, record):
        if record.get("selected_route") == "cloud" and record.get("cloud_execution_attempted"):
            # Mark the native target canceled before reconciliation so a checkpoint
            # may be reported read-only, but cannot resume review after cancellation.
            await self.authority(self.gateway.cancel_target, int(record["owner"]), self.target(record))
            # Cancellation cannot revoke an already possible provider execution.
            await self._cloud(record, status_only=True)
            return
        if not record["target"] and record["plan_attempted"]:
            plan = await self.authority(self.gateway.plan_status, int(record["owner"]),
                                        record["project_id"], record["plan_key"])
            if plan["status"] == "planned":
                await self._patch(record, target=plan["target"])
            elif plan["status"] == "plan_unknown":
                await self._finish(record, state="cancel_requested", last_error="native_plan_outcome_unknown")
                return
        if record["target"]:
            outcome = await self.authority(self.gateway.cancel_target, int(record["owner"]), self.target(record))
            if outcome.get("status") == "already_registered":
                # Do not revoke an already committed native result or lie that it
                # was canceled. Finish same receipt confirmation instead.
                await self._patch(record, cancel_requested=False)
                await self._register_or_confirm(record)
                return
        if not record["remote_task_id"] and record["wire_request"]:
            try:
                remote = await self.client.by_origin(record["origin_key"])
                self._validate_task(record, remote)
                await self._patch(record, remote_task_id=remote["remote_task_id"])
            except BridgeError as exc:
                if exc.status != 404:
                    raise
        if record["remote_task_id"]:
            remote = await self.client.cancel(record["remote_task_id"])
            self._validate_task(record, remote)
            if remote.get("receipt_id"):
                receipt = await self.client.receipt(remote["receipt_id"])
                self._validate_receipt(record, remote, receipt)
                await self.client.reject_receipt(receipt["receipt_id"], client_receipt_id=record["client_receipt_id"],
                    original_hash=receipt["original_sha256"], reason_code="native_target_canceled")
                await self._patch(record, delivery_ack="rejected")
        await self._finish(record, state="canceled")
