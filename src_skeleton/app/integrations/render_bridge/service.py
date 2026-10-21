from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
import time
from uuid import uuid4

from .attention import attention_projection
from .client import BridgeClient, BridgeError
from .models import PreviewCreate, decode_inputs, validate_image
from .store import PreviewStore


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class PreviewService:
    """Dedicated bounded resource owner; never touches native job executors."""
    def __init__(self, settings, project_snapshot, *, client=None):
        self.settings, self.project_snapshot = settings, project_snapshot
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bridge-preview")
        self.store = PreviewStore(settings.storage, max_jobs=settings.max_jobs, max_bytes=settings.max_storage_bytes)
        self.client = client or BridgeClient(settings.base_url, settings.token)
        self.worker = None
        self.tick_lock = asyncio.Lock()
        self.local_gate = asyncio.Semaphore(8)

    async def local(self, function, *args, **kwargs):
        # Bound submissions to our own executor, not the host's thread/worker pool.
        if self.local_gate.locked():
            raise BridgeError("preview_busy", status=503)
        async with self.local_gate:
            from functools import partial
            return await asyncio.get_running_loop().run_in_executor(self.executor, partial(function, *args, **kwargs))

    def start(self):
        self.worker = asyncio.create_task(self._run(), name="render-bridge-preview-reconciler")

    async def close(self):
        if self.worker:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
        await self.client.close()
        self.executor.shutdown(wait=True, cancel_futures=True)

    async def _run(self):
        while True:
            try:
                await self.tick()
            except Exception:
                # Isolated failure; the next bounded scan can resume durable work.
                pass
            await asyncio.sleep(self.settings.poll_seconds)

    async def snapshot(self, owner, project_id):
        return await self.local(self.project_snapshot, owner, project_id)

    async def create(self, owner, request: PreviewCreate):
        if self.settings.mode != "enabled":
            raise BridgeError("bridge_draining", status=409, retryable=False)
        snapshot = await self.snapshot(owner, request.project_id)
        if not snapshot:
            raise BridgeError("project_not_found", status=404, retryable=False)
        if request.profile_id not in self.settings.profiles:
            raise BridgeError("profile_not_enabled", status=422, retryable=False)
        inputs = await self.local(decode_inputs, request)
        summary = request.model_dump(exclude={"references", "client_request_id"})
        summary["references"] = [metadata for _, metadata in inputs]
        job_id = "brp_" + uuid4().hex
        record = {
            "id": job_id, "owner": owner, "workspace": self.settings.workspace,
            "endpoint_fingerprint": digest(self.settings.base_url),
            "project_id": request.project_id, "project_revision": snapshot["revision"],
            "request_key": request.client_request_id, "digest": digest(summary),
            "origin_key": "alchemy_preview_" + uuid4().hex,
            "binding_id": "preview_" + digest([self.settings.workspace, owner, request.project_id, job_id]),
            "state": "queued", "created_at": datetime.now(timezone.utc).isoformat(),
            "next_poll_at": 0, "errors": 0, "last_error": None,
            "request": summary, "remote_task_id": None, "wire_request": None,
            "cancel_requested": False, "native_registration": "not_connected",
            "delivery_ack": "pending", "client_receipt_id": "preview_ack_" + uuid4().hex,
        }
        return await self.local(self.store.create, record, inputs)

    async def visible(self, owner, job_id):
        record = await self.local(self.store.get, job_id)
        if not record or record["owner"] != owner or record["workspace"] != self.settings.workspace:
            raise BridgeError("task_not_found", status=404, retryable=False)
        snapshot = await self.snapshot(owner, record["project_id"])
        if not snapshot:
            raise BridgeError("task_not_found", status=404, retryable=False)
        return record, snapshot["revision"] == record["project_revision"]

    async def list(self, owner, project_id):
        snapshot = await self.snapshot(owner, project_id)
        if not snapshot:
            raise BridgeError("project_not_found", status=404, retryable=False)
        records = await self.local(self.store.list, owner, project_id)
        return [self.public(record, revision_current=snapshot["revision"] == record["project_revision"])
                for record in records if record["workspace"] == self.settings.workspace]

    async def cancel(self, owner, job_id):
        record, _ = await self.visible(owner, job_id)
        if record["state"] == "canceled":
            return record
        return await self.local(self.store.patch, job_id,
                                {"cancel_requested": True, "state": "cancel_requested", "next_poll_at": 0})

    async def preview(self, owner, job_id):
        record, current = await self.visible(owner, job_id)
        if record["cancel_requested"] or not current or record["state"] != "preview_ready":
            raise BridgeError("preview_not_available", status=409, retryable=False)
        result = await self.local(self.store.receipt, job_id)
        if not result:
            raise BridgeError("preview_not_available", status=404, retryable=False)
        return result

    @staticmethod
    def public(record, *, revision_current=True):
        state = record["state"] if revision_current else "blocked_revision"
        return {"integration_job_id": record["id"], "project_id": record["project_id"],
                "state": state, "created_at": record["created_at"],
                "profile_id": record["request"]["profile_id"], "last_error": record.get("last_error"),
                "action_required_detail": attention_projection(record),
                "remote_state": record.get("remote_state"), "native_registration": "not_connected",
                "delivery_ack": record.get("delivery_ack", "pending"), "test_only": True,
                "preview_url": (f"/api/integrations/render-bridge/v1/tasks/{record['id']}/preview"
                                if state == "preview_ready" and not record["cancel_requested"] else None)}

    async def tick(self):
        if self.settings.mode == "disabled" or self.tick_lock.locked():
            return
        async with self.tick_lock:
            records = await self.local(self.store.claim_due, self.settings.batch_size)
            for record in records:
                try:
                    # HTTP read timeouts alone do not bound a slow trickle stream.
                    # One reconciliation step has a wall-clock bound as well.
                    async with asyncio.timeout(45):
                        await self._advance(record)
                except asyncio.CancelledError:
                    # Durable lease expires after restart; no second origin or import.
                    raise
                except TimeoutError:
                    await self.local(self.store.patch, record["id"], {
                        "last_error": "bridge_step_timeout", "state": "remote_unavailable",
                        "next_poll_at": time.time() + 30,
                    }, release=True)
                except BridgeError as exc:
                    count = record.get("errors", 0) + 1
                    await self.local(self.store.patch, record["id"], {
                        "last_error": exc.code, "errors": count,
                        "state": "remote_unavailable" if exc.retryable else "protocol_error",
                        "next_poll_at": time.time() + min(60, 2 ** min(count, 6)),
                    }, release=True)
                except Exception:
                    await self.local(self.store.patch, record["id"], {
                        "last_error": "preview_reconcile_error", "next_poll_at": time.time() + 30,
                    }, release=True)

    async def _patch(self, record, **values):
        updated = await self.local(self.store.patch, record["id"], values)
        record.clear()
        record.update(updated)

    async def _finish(self, record, **values):
        values.setdefault("last_error", None)
        values.setdefault("next_poll_at", time.time() + self.settings.poll_seconds)
        await self.local(self.store.patch, record["id"], values, release=True)

    async def _check_scope(self, record):
        snapshot = await self.snapshot(record["owner"], record["project_id"])
        if (record["workspace"] != self.settings.workspace or not snapshot
                or record.get("endpoint_fingerprint") != digest(self.settings.base_url)):
            await self._finish(record, state="blocked_scope")
            return False
        if snapshot["revision"] != record["project_revision"]:
            await self._finish(record, state="blocked_revision")
            return False
        return True

    async def _advance(self, record):
        if not await self._check_scope(record):
            return
        # Always load durable cancellation again after claiming a record.
        record = await self.local(self.store.get, record["id"])
        if not record["remote_task_id"]:
            if record["wire_request"] is not None:
                try:
                    remote = await self.client.by_origin(record["origin_key"])
                except BridgeError as exc:
                    if exc.status != 404:
                        raise
                    remote = None
                if remote:
                    self._validate_task(record, remote)
                    await self._patch(record, remote_task_id=remote["remote_task_id"])
            if not record["remote_task_id"] and record["cancel_requested"]:
                await self._finish(record, state="canceled")
                return
            if not record["remote_task_id"]:
                if record["wire_request"] is None:
                    await self._prepare_wire(record)
                # Preparation awaits remote capabilities/uploads. Cancellation
                # or a project change during that interval still forbids create.
                record = await self.local(self.store.get, record["id"])
                if record["cancel_requested"]:
                    await self._finish(record, state="canceled")
                    return
                if not await self._check_scope(record):
                    return
                # Persisted, byte-for-byte frozen request, even after response loss.
                remote = await self.client.create_task(record["wire_request"])
                self._validate_task(record, remote)
                await self._patch(record, remote_task_id=remote["remote_task_id"])
        record = await self.local(self.store.get, record["id"])
        if record["cancel_requested"]:
            remote = await self.client.cancel(record["remote_task_id"])
        else:
            remote = await self.client.task(record["remote_task_id"])
        self._validate_task(record, remote)
        await self._patch(record, remote_state=remote["state"], action_required_detail=attention_projection(remote))
        if record["cancel_requested"]:
            if remote.get("receipt_id"):
                receipt = await self.client.receipt(remote["receipt_id"])
                self._validate_receipt(record, remote, receipt)
                await self.client.reject_receipt(receipt["receipt_id"],
                    client_receipt_id=record["client_receipt_id"], original_hash=receipt["original_sha256"],
                    reason_code="preview_canceled")
            # Local cancel is final; remote may still be settling execution.
            await self._finish(record, state="canceled", delivery_ack="rejected" if remote.get("receipt_id") else "pending")
            return
        if remote["state"] in {"failed", "expired", "canceled"}:
            await self._finish(record, state=remote["state"])
            return
        if remote.get("receipt_id"):
            receipt = await self.client.receipt(remote["receipt_id"])
            self._validate_receipt(record, remote, receipt)
            limits = record["profile_snapshot"]["limits"]
            content, headers = await self.client.artifact(receipt["artifact_id"], limits["max_output_bytes"])
            if headers.get("content-type", "").split(";")[0] != receipt["mime_type"]:
                raise BridgeError("artifact_mime_mismatch", retryable=False)
            metadata = await self.local(validate_image, content, receipt["mime_type"],
                expected_hash=receipt["original_sha256"], expected_size=receipt["size"],
                max_bytes=limits["max_output_bytes"], max_pixels=limits["max_image_pixels"])
            if metadata["dimensions"] != receipt["dimensions"]:
                raise BridgeError("artifact_dimensions_mismatch", retryable=False)
            if not await self._check_scope(record):
                return
            latest = await self.local(self.store.get, record["id"])
            if latest["cancel_requested"]:
                await self._finish(latest, state="cancel_requested", next_poll_at=0)
                return
            await self.local(self.store.save_receipt, record["id"], receipt, content)
            await self._finish(record, state="preview_ready", receipt_id=receipt["receipt_id"],
                               delivery_ack="pending", native_registration="not_connected")
            return
        await self._finish(record, state=remote["state"], errors=0)

    async def _prepare_wire(self, record):
        capabilities = await self.client.capabilities()
        profiles = capabilities.get("profiles", [])
        profile = next((p for p in profiles if p.get("execution_profile_id") == record["request"]["profile_id"]
                        and p.get("execution_profile_revision") == "1" and p.get("operation") == "image.generate"), None)
        if capabilities.get("schema_version") != "1" or not profile:
            raise BridgeError("unsupported_bridge_capability", retryable=False)
        limits = profile.get("limits", {})
        if any(type(limits.get(k)) is not int or limits[k] < 1 for k in
               ("max_output_bytes", "max_image_pixels", "max_dimension")):
            raise BridgeError("invalid_bridge_capabilities", retryable=False)
        limits = {"max_output_bytes": min(limits["max_output_bytes"], 16777216),
                  "max_image_pixels": min(limits["max_image_pixels"], 40000000),
                  "max_dimension": min(limits["max_dimension"], 40000000)}
        request = record["request"]
        if max(request["width"], request["height"]) > limits["max_dimension"] or request["width"] * request["height"] > limits["max_image_pixels"]:
            raise BridgeError("profile_dimensions_exceeded", retryable=False)
        await self._patch(record, profile_snapshot={**profile, "limits": limits})
        references = []
        for index, (content, metadata) in enumerate(await self.local(self.store.inputs, record["id"])):
            payload = {k: metadata[k] for k in ("original_sha256", "size", "mime_type")}
            payload["input_key"] = f"{record['origin_key']}_{index}"
            result = await self.client.create_input(payload)
            if any(result.get(k) != v for k, v in payload.items()):
                raise BridgeError("input_binding_mismatch", retryable=False)
            await self.client.upload_input(result["input_id"], content, metadata["mime_type"])
            references.append({"input_ref": result["input_id"], "role": "reference", "hash": metadata["original_sha256"]})
        wire = {"schema_version": "1", "origin_key": record["origin_key"], "binding_id": record["binding_id"],
                "operation": "image.generate", "execution_profile_id": request["profile_id"],
                "execution_profile_revision": "1", "prompt": request["prompt"],
                "parameters": {k: request[k] for k in ("width", "height", "seed")},
                "references": references, "output_slot": {"slot_id": "primary", "count": 1},
                "deadline": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
                "routing": "bridge_only"}
        await self._patch(record, wire_request=wire, state="submitting")

    @staticmethod
    def _validate_task(record, remote):
        if (remote.get("origin_key") != record["origin_key"] or remote.get("request") != record["wire_request"]
                or not isinstance(remote.get("remote_task_id"), str)
                or (record["remote_task_id"] and remote["remote_task_id"] != record["remote_task_id"])
                or remote.get("state") not in {"queued", "claimed", "running", "uploading", "awaiting_user", "execution_unknown",
                                               "artifacts_ready", "cancel_requested", "canceled", "failed", "expired"}):
            raise BridgeError("task_binding_mismatch", retryable=False)

    @staticmethod
    def _validate_receipt(record, remote, receipt):
        if (receipt.get("receipt_id") != remote["receipt_id"] or receipt.get("task_id") != record["remote_task_id"]
                or receipt.get("attempt_id") != remote.get("attempt_id") or receipt.get("slot_id") != "primary"
                or receipt.get("execution_profile_id") != record["request"]["profile_id"]
                or receipt.get("execution_profile_revision") != "1"
                or not isinstance(receipt.get("original_sha256"), str) or len(receipt["original_sha256"]) != 64
                or type(receipt.get("size")) is not int or receipt["size"] < 1):
            raise BridgeError("receipt_binding_mismatch", retryable=False)
