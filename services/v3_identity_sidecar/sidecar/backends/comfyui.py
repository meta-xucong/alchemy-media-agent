from __future__ import annotations

import asyncio
from contextlib import ExitStack
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import time
from typing import Any, Awaitable, Callable
from uuid import uuid4

import httpx
from PIL import Image

from ..config import SidecarSettings
from ..contracts import (
    BackendCapabilities,
    BackendGenerationResult,
    BackendImage,
    IdentityGenerationManifest,
)
from .base import SidecarBackendError, SidecarBackendUnavailable


_TOKEN_PATTERN = re.compile(r"\$\{([a-zA-Z0-9_]+)\}")


class ComfyUIIdentityBackend:
    """Execute an operator-supplied identity workflow through ComfyUI's HTTP API."""

    def __init__(
        self,
        config: SidecarSettings,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.config = config
        self._transport = transport
        self._sleep = sleep
        self._capability_cache: tuple[float, BackendCapabilities] | None = None

    async def capabilities(self) -> BackendCapabilities:
        now = time.monotonic()
        if self._capability_cache is not None and self._capability_cache[0] > now:
            return self._capability_cache[1].model_copy(deep=True)
        configured, reason, identity_slots = self._workflow_state(self.config.workflow_path)
        repair_configured = False
        if self.config.repair_workflow_path is not None:
            repair_configured, _repair_reason, _repair_slots = self._workflow_state(
                self.config.repair_workflow_path,
                repair=True,
            )
        if not self.config.model_license_confirmed:
            configured = False
            reason = "Identity model and dependency licenses have not been explicitly confirmed."
        elif not self.config.identity_conditioning_confirmed:
            configured = False
            reason = "The operator has not confirmed that the workflow performs identity conditioning."
        healthy = False
        health_metadata: dict[str, Any] = {}
        if configured:
            try:
                async with self._client(timeout_seconds=self.config.health_timeout_seconds) as client:
                    response = await client.get("/system_stats")
                    response.raise_for_status()
                    payload = response.json()
                    object_response = await client.get("/object_info")
                    object_response.raise_for_status()
                    object_info = object_response.json()
                    required_nodes = self._workflow_node_types(self.config.workflow_path)
                    if self.config.repair_workflow_path is not None:
                        required_nodes.update(self._workflow_node_types(self.config.repair_workflow_path))
                    available_nodes = set(object_info.keys()) if isinstance(object_info, dict) else set()
                    missing_nodes = sorted(required_nodes - available_nodes)
                    healthy = isinstance(payload, dict) and not missing_nodes
                    if missing_nodes:
                        reason = f"ComfyUI is missing workflow nodes: {', '.join(missing_nodes[:12])}"
                    health_metadata = {
                        "comfyui_system_stats": True,
                        "comfyui_object_info": isinstance(object_info, dict),
                        "device_count": len(payload.get("devices", [])) if isinstance(payload.get("devices"), list) else None,
                        "required_node_count": len(required_nodes),
                        "missing_node_count": len(missing_nodes),
                    }
            except Exception as exc:
                reason = f"ComfyUI health probe failed: {type(exc).__name__}: {str(exc)[:180]}"
        result = BackendCapabilities(
            configured=configured,
            healthy=healthy,
            identity_conditioning=bool(configured and healthy),
            multi_reference=bool(configured and healthy and identity_slots > 1),
            identity_native_local_repair=bool(
                configured
                and healthy
                and repair_configured
                and self.config.identity_local_repair_confirmed
            ),
            max_reference_images=min(self.config.max_references, max(1, identity_slots)),
            provider=self.config.provider_family,
            model=self.config.model_name,
            backend="comfyui",
            reason=None if configured and healthy else reason or "ComfyUI identity workflow is unavailable.",
            metadata={
                **health_metadata,
                "workflow_path": str(self.config.workflow_path),
                "repair_workflow_configured": repair_configured,
                "model_license_confirmed": self.config.model_license_confirmed,
                "identity_conditioning_confirmed": self.config.identity_conditioning_confirmed,
                "identity_local_repair_confirmed": self.config.identity_local_repair_confirmed,
            },
        )
        if result.configured and result.healthy and self.config.capability_ttl_seconds > 0:
            self._capability_cache = (now + self.config.capability_ttl_seconds, result.model_copy(deep=True))
        return result

    async def generate(
        self,
        manifest: IdentityGenerationManifest,
        references: list[Path],
        *,
        canvas: Path | None = None,
        mask: Path | None = None,
    ) -> BackendGenerationResult:
        capabilities = await self.capabilities()
        if not capabilities.identity_conditioning:
            raise SidecarBackendUnavailable(
                capabilities.reason or "ComfyUI identity backend is unavailable.",
                detail=capabilities.model_dump(mode="json"),
            )
        repair_active = canvas is not None or mask is not None
        if repair_active and (canvas is None or mask is None):
            raise SidecarBackendError("Identity repair requires both canvas and mask.")
        if repair_active and not capabilities.identity_native_local_repair:
            raise SidecarBackendError("Configured ComfyUI backend does not support identity-native local repair.")
        if not references:
            raise SidecarBackendError("At least one identity reference is required.")
        if len(references) > capabilities.max_reference_images:
            raise SidecarBackendError(
                "Reference count exceeds the configured identity workflow capacity.",
                detail={
                    "reference_count": len(references),
                    "max_reference_images": capabilities.max_reference_images,
                },
            )

        workflow_path = self.config.repair_workflow_path if repair_active else self.config.workflow_path
        if workflow_path is None:
            raise SidecarBackendError("Repair workflow is not configured.")
        workflow = self._load_workflow(workflow_path)
        client_id = _safe_identifier(manifest.trace_id or uuid4().hex)
        deadline = time.monotonic() + max(30.0, self.config.request_timeout_seconds)
        async with self._client(timeout_seconds=self.config.request_timeout_seconds) as client:
            uploaded_references = [
                await self._upload_image(client, path, client_id=client_id, label=f"reference_{index}")
                for index, path in enumerate(references)
            ]
            uploaded_canvas = (
                await self._upload_image(client, canvas, client_id=client_id, label="canvas")
                if canvas is not None
                else None
            )
            uploaded_mask = (
                await self._upload_image(client, mask, client_id=client_id, label="mask")
                if mask is not None
                else None
            )
            context = self._template_context(
                manifest,
                uploaded_references,
                canvas=uploaded_canvas,
                mask=uploaded_mask,
                workflow=workflow,
            )
            rendered = _render_template(workflow, context)
            unresolved = sorted(set(_TOKEN_PATTERN.findall(json.dumps(rendered, ensure_ascii=False))))
            if unresolved:
                raise SidecarBackendError(
                    "ComfyUI workflow contains unresolved sidecar tokens.",
                    detail={"unresolved_tokens": unresolved},
                )
            prompt_id = await self._queue_prompt(client, rendered, client_id=client_id)
            history = await self._wait_for_history(client, prompt_id, deadline=deadline)
            images = await self._download_outputs(client, history)

        if not images:
            raise SidecarBackendError("ComfyUI workflow completed without image outputs.")
        return BackendGenerationResult(
            provider=self.config.provider_family,
            model=self.config.model_name,
            images=images[: manifest.count],
            metadata={
                "prompt_id": prompt_id,
                "backend": "comfyui",
                "reference_count": len(references),
                "repair_active": repair_active,
                "workflow_sha256": _file_sha256(workflow_path),
            },
        )

    def _workflow_state(self, path: Path, *, repair: bool = False) -> tuple[bool, str | None, int]:
        try:
            workflow = self._load_workflow(path)
        except Exception as exc:
            return False, str(exc), 0
        serialized = json.dumps(workflow, ensure_ascii=False)
        tokens = set(_TOKEN_PATTERN.findall(serialized))
        required = {"prompt", "reference_0"}
        if repair:
            required.update({"canvas", "mask"})
        missing = sorted(required - tokens)
        if missing:
            return False, f"Workflow is missing required tokens: {', '.join(missing)}", 0
        reference_indexes = sorted(
            int(token.removeprefix("reference_"))
            for token in tokens
            if token.startswith("reference_") and token.removeprefix("reference_").isdigit()
        )
        slots = max(reference_indexes, default=0) + 1
        return True, None, slots

    def _load_workflow(self, path: Path) -> dict[str, Any]:
        if not path.is_file():
            raise SidecarBackendError(f"ComfyUI workflow file was not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SidecarBackendError(f"ComfyUI workflow is not valid JSON: {path}") from exc
        if not isinstance(payload, dict) or not payload:
            raise SidecarBackendError("ComfyUI workflow must be a non-empty API-format JSON object.")
        return payload

    async def _upload_image(
        self,
        client: httpx.AsyncClient,
        path: Path,
        *,
        client_id: str,
        label: str,
    ) -> str:
        remote_name = f"alchemy_{client_id}_{label}{path.suffix.lower() or '.png'}"
        mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
        try:
            with ExitStack() as stack:
                response = await client.post(
                    "/upload/image",
                    data={"overwrite": "true", "type": "input"},
                    files={"image": (remote_name, stack.enter_context(path.open("rb")), mime_type)},
                )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise SidecarBackendUnavailable(
                "ComfyUI input upload failed.",
                detail={"error_type": type(exc).__name__, "message": str(exc)[:300]},
            ) from exc
        if not isinstance(payload, dict) or not payload.get("name"):
            raise SidecarBackendError("ComfyUI upload response did not include a file name.")
        subfolder = str(payload.get("subfolder") or "").strip("/\\")
        return f"{subfolder}/{payload['name']}" if subfolder else str(payload["name"])

    async def _queue_prompt(self, client: httpx.AsyncClient, workflow: dict[str, Any], *, client_id: str) -> str:
        try:
            response = await client.post("/prompt", json={"prompt": workflow, "client_id": client_id})
            if response.status_code == 400:
                payload = response.json()
                raise SidecarBackendError(
                    "ComfyUI rejected the workflow.",
                    detail={"node_errors": payload.get("node_errors", {}), "error": payload.get("error")},
                )
            response.raise_for_status()
            payload = response.json()
        except SidecarBackendError:
            raise
        except Exception as exc:
            raise SidecarBackendUnavailable(
                "ComfyUI prompt submission failed.",
                detail={"error_type": type(exc).__name__, "message": str(exc)[:300]},
            ) from exc
        if not isinstance(payload, dict) or not payload.get("prompt_id"):
            raise SidecarBackendError(
                "ComfyUI rejected the workflow.",
                detail={"response": payload if isinstance(payload, dict) else {}},
            )
        return str(payload["prompt_id"])

    async def _wait_for_history(
        self,
        client: httpx.AsyncClient,
        prompt_id: str,
        *,
        deadline: float,
    ) -> dict[str, Any]:
        while time.monotonic() < deadline:
            try:
                response = await client.get(f"/history/{prompt_id}")
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                raise SidecarBackendUnavailable(
                    "ComfyUI history polling failed.",
                    detail={"error_type": type(exc).__name__, "message": str(exc)[:300]},
                ) from exc
            record = payload.get(prompt_id) if isinstance(payload, dict) else None
            if isinstance(record, dict):
                status = record.get("status") if isinstance(record.get("status"), dict) else {}
                if status.get("status_str") in {"error", "failed"}:
                    raise SidecarBackendError(
                        "ComfyUI workflow execution failed.",
                        detail={"status": status},
                    )
                if isinstance(record.get("outputs"), dict) and record["outputs"]:
                    return record
            await self._sleep(max(0.05, self.config.poll_interval_seconds))
        raise SidecarBackendUnavailable(
            "ComfyUI workflow timed out.",
            detail={"prompt_id": prompt_id, "timeout_seconds": self.config.request_timeout_seconds},
        )

    async def _download_outputs(
        self,
        client: httpx.AsyncClient,
        history: dict[str, Any],
    ) -> list[BackendImage]:
        outputs = history.get("outputs") if isinstance(history.get("outputs"), dict) else {}
        node_ids = self.config.comfyui_output_node_ids or list(outputs.keys())
        images: list[BackendImage] = []
        for node_id in node_ids:
            node_output = outputs.get(str(node_id))
            if not isinstance(node_output, dict):
                continue
            for descriptor in node_output.get("images", []) if isinstance(node_output.get("images"), list) else []:
                if not isinstance(descriptor, dict) or not descriptor.get("filename"):
                    continue
                try:
                    response = await client.get(
                        "/view",
                        params={
                            "filename": descriptor["filename"],
                            "subfolder": descriptor.get("subfolder") or "",
                            "type": descriptor.get("type") or "output",
                        },
                    )
                    response.raise_for_status()
                except Exception as exc:
                    raise SidecarBackendUnavailable(
                        "ComfyUI output download failed.",
                        detail={"error_type": type(exc).__name__, "message": str(exc)[:300]},
                    ) from exc
                content = response.content
                if not content or len(content) > self.config.max_output_bytes:
                    raise SidecarBackendError(
                        "ComfyUI output is empty or exceeds the configured limit.",
                        detail={"size_bytes": len(content)},
                    )
                width, height = _image_dimensions(content)
                images.append(
                    BackendImage(
                        content=content,
                        mime_type=response.headers.get("content-type") or "image/png",
                        width=width,
                        height=height,
                        metadata={"node_id": str(node_id)},
                    )
                )
        return images

    def _template_context(
        self,
        manifest: IdentityGenerationManifest,
        references: list[str],
        *,
        canvas: str | None,
        mask: str | None,
        workflow: dict[str, Any],
    ) -> dict[str, Any]:
        width, height = _parse_size(manifest.size)
        context: dict[str, Any] = {
            "prompt": manifest.prompt,
            "negative_prompt": ", ".join(manifest.negative_constraints),
            "seed": _stable_seed(manifest.idempotency_key or manifest.trace_id or manifest.prompt),
            "width": width,
            "height": height,
            "quality": manifest.quality,
            "input_fidelity": manifest.input_fidelity,
            "canvas": canvas or "",
            "mask": mask or "",
        }
        serialized = json.dumps(workflow, ensure_ascii=False)
        indexes = sorted(
            int(token.removeprefix("reference_"))
            for token in set(_TOKEN_PATTERN.findall(serialized))
            if token.startswith("reference_") and token.removeprefix("reference_").isdigit()
        )
        for index in indexes:
            context[f"reference_{index}"] = references[min(index, len(references) - 1)]
        return context

    def _workflow_node_types(self, path: Path) -> set[str]:
        workflow = self._load_workflow(path)
        return {
            str(node.get("class_type"))
            for node in workflow.values()
            if isinstance(node, dict) and node.get("class_type")
        }

    def _client(self, *, timeout_seconds: float) -> httpx.AsyncClient:
        total = max(2.0, timeout_seconds)
        timeout = httpx.Timeout(total, connect=min(20.0, total), write=min(120.0, total), pool=min(30.0, total))
        headers = {"Authorization": f"Bearer {self.config.comfyui_api_key}"} if self.config.comfyui_api_key else {}
        return httpx.AsyncClient(
            base_url=self.config.comfyui_base_url,
            timeout=timeout,
            headers=headers,
            transport=self._transport,
            follow_redirects=True,
        )


def _render_template(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, dict):
        return {key: _render_template(item, context) for key, item in value.items()}
    if isinstance(value, list):
        return [_render_template(item, context) for item in value]
    if not isinstance(value, str):
        return value
    exact = _TOKEN_PATTERN.fullmatch(value)
    if exact and exact.group(1) in context:
        return context[exact.group(1)]

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        return str(context[key]) if key in context else match.group(0)

    return _TOKEN_PATTERN.sub(replace, value)


def _safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value).strip("-")
    return cleaned[:64] or uuid4().hex


def _stable_seed(value: str) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16) % 2_147_483_647


def _parse_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{3,4})x(\d{3,4})", str(value or ""))
    if not match:
        return 1024, 1024
    return int(match.group(1)), int(match.group(2))


def _image_dimensions(content: bytes) -> tuple[int, int]:
    from io import BytesIO

    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            return int(image.width), int(image.height)
    except Exception as exc:
        raise SidecarBackendError("ComfyUI output is not a valid image.") from exc


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
