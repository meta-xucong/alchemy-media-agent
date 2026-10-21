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
    acknowledge_synthetic_native_test: bool = False
    acknowledge_native_development: bool = False

    @model_validator(mode="after")
    def require_explicit_development_ack(self):
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
        width, height = map(int, request.size.split("x"))
        summary = {"project_id": request.project_id, "user_input": request.user_input,
                   "profile_id": request.profile_id, "width": width, "height": height, "seed": 0}
        # Preserve the original no-reference/square idempotency digest.
        if request.uploaded_asset_ids:
            summary["uploaded_asset_ids"] = request.uploaded_asset_ids
        if request.output_format != "png":
            summary["output_format"] = request.output_format
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
            "remote_task_id": None, "native_phase": "planning", "native_outcome": None,
            "delivery_ack": "pending"}
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
        return record, True

    async def list(self, owner, project_id):
        if not await self.snapshot(owner, project_id):
            raise BridgeError("project_not_found", status=404, retryable=False)
        return [self.public(record) for record in await self.local(self.store.list, owner, project_id)
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
            "test_fixture": record["request"]["profile_id"] == "fake-image", "real_tool_verified": False,
            "native_registration": native.get("status", "pending"), "delivery_ack": record.get("delivery_ack", "pending"),
            "native_registration_ref": native.get("native_registration_ref"),
            "review_status": native.get("review_status"), "formal_delivery": False,
            "billing": native.get("billing", {"mode": "v3_zero_credit_stub", "charged": False}),
            "size": f"{record['request']['width']}x{record['request']['height']}",
            "output_format": record["request"].get("output_format", "png"),
            "format_semantics": "original_artifact_postcondition",
            "quality": "auto", "quality_semantics": "unspecified_only", "input_fidelity": None,
            "reference_count": len(record["request"].get("uploaded_asset_ids", [])),
            "reference_effect_verified": False,
            "target": record.get("target")}

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
        # Negotiate before any Brain planning effect. The old fake/PNG v1
        # contract remains usable without the additive descriptor. Persisted
        # wire requests are never reinterpreted or upgraded during recovery.
        if not record.get("wire_request") and not record.get("profile_snapshot"):
            if profile_id not in self.settings.native_profiles or profile_id not in self.settings.profiles:
                raise BridgeError("native_profile_not_enabled", retryable=False)
            profile = native_profile(await self.client.capabilities(), profile_id=profile_id,
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
            await self._patch(record, frozen=frozen)
        options = record["frozen"].get("image_options", {})
        if (options.get("quality") != "auto" or options.get("input_fidelity") is not None
                or options.get("output_format") != record["request"].get("output_format", "png")):
            raise BridgeError("native_frozen_image_options_unsupported", retryable=False)
        dimensions = self._frozen_dimensions(record)
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
                remote = await self.client.create_task(record["wire_request"])
            self._validate_task(record, remote)
            await self._patch(record, remote_task_id=remote["remote_task_id"])
        remote = await self.client.task(record["remote_task_id"])
        self._validate_task(record, remote)
        await self._patch(record, remote_state=remote["state"], action_required_detail=attention_projection(remote))
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
        await self.client.accept_registered_receipt(record["receipt_id"],
            client_receipt_id=record["client_receipt_id"], original_hash=outcome["original_sha256"],
            normalized_hash=outcome.get("normalized_sha256"), native_registration_ref=outcome["native_registration_ref"])
        await self._finish(record, state="registered", native_phase="complete", delivery_ack="accepted")

    async def _cancel_native(self, record):
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
