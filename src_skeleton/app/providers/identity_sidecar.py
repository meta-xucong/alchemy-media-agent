from __future__ import annotations

import base64
from contextlib import ExitStack
import json
import mimetypes
from pathlib import Path
import threading
import time
from typing import Any

import httpx

from app.config import settings
from app.providers.base import (
    ProviderCapabilities,
    ProviderCapabilityMismatchError,
    ProviderNotConfiguredError,
    ProviderRuntimeError,
)
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.services.provider_reference import prepare_provider_reference_images


class IdentityNativeSidecarProvider:
    """Normalized HTTP adapter for optional identity-specialized image backends."""

    name = "identity_native_sidecar"
    _capability_cache: dict[str, tuple[float, dict[str, Any]]] = {}
    _capability_cache_lock = threading.Lock()

    def __init__(self, *, transport: httpx.AsyncBaseTransport | None = None) -> None:
        self._transport = transport

    async def capabilities(self) -> ProviderCapabilities:
        configured = self._locally_configured()
        reason = None if configured else (
            "V3 identity sidecar is disabled or V3_IDENTITY_SIDECAR_BASE_URL is not configured."
        )
        return ProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.v3_identity_sidecar_model],
            operations=["identity_reference_generation", "multi_reference_identity_conditioning"],
            advanced_asset_roles=["portrait_identity"],
            model_capabilities=[
                {
                    "id": settings.v3_identity_sidecar_model,
                    "backend_family": settings.v3_identity_sidecar_provider,
                    "capabilities": ["identity_conditioning", "multi_reference"],
                    "advanced_asset_roles": ["portrait_identity"],
                }
            ],
            limits={
                "max_batch": 1,
                "max_reference_images": max(1, settings.v3_identity_sidecar_max_references),
                "formats": ["png", "jpeg", "webp"],
                "timeout_seconds": max(30.0, settings.v3_identity_sidecar_timeout_seconds),
                "remote_capabilities_required": True,
            },
            reason=reason,
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        self._require_local_configuration()
        remote_capabilities = await self._remote_capabilities()
        if not _capability_enabled(remote_capabilities, "identity_conditioning"):
            raise ProviderCapabilityMismatchError(
                "Identity sidecar did not advertise identity_conditioning=true.",
                provider=self.name,
                detail={"capabilities": _public_capability_summary(remote_capabilities)},
            )

        references = self._identity_references(request)
        if not references:
            raise ProviderCapabilityMismatchError(
                "Identity sidecar requires at least one portrait identity reference.",
                provider=self.name,
                detail={"missing_capability": "portrait_identity_reference"},
            )

        repair_assets = self._repair_assets(request)
        repair_active = bool(repair_assets)
        if repair_active and not _capability_enabled(remote_capabilities, "identity_native_local_repair"):
            raise ProviderCapabilityMismatchError(
                "Identity sidecar did not advertise identity_native_local_repair=true.",
                provider=self.name,
                detail={"capabilities": _public_capability_summary(remote_capabilities)},
            )
        prompt = str(request.prompt_plan.variables.get("generation_prompt") or request.prompt_plan.main_subject).strip()
        manifest = self._manifest(
            request,
            references,
            remote_capabilities,
            prompt=prompt,
            repair_assets=repair_assets,
        )
        response_payload = await self._post_generation(manifest, references, repair_assets)
        outputs = self._validated_outputs(
            response_payload,
            remote_capabilities,
            repair_active=repair_active,
        )
        backend_provider = str(response_payload.get("provider") or settings.v3_identity_sidecar_provider or "custom")
        model = str(response_payload.get("model") or settings.v3_identity_sidecar_model)
        return ImageGenerationResult(
            provider=f"identity_native_sidecar:{backend_provider}",
            model=model,
            outputs=outputs,
            raw_response_summary={
                "output_count": len(outputs),
                "reference_image_count": len(references),
                "identity_native_provider": True,
                "identity_conditioning": True,
                "identity_native_local_repair": _capability_enabled(
                    remote_capabilities, "identity_native_local_repair"
                ),
                "multi_reference": _capability_enabled(remote_capabilities, "multi_reference"),
                "backend_family": backend_provider,
                "contract_version": "doc98-v1",
            },
        )

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        return await self.generate(request)

    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate:
        return CostEstimate(
            provider=self.name,
            model=settings.v3_identity_sidecar_model,
            estimated_cost=0.0,
            detail={"cost_is_managed_by_external_sidecar": True},
        )

    def _locally_configured(self) -> bool:
        return bool(settings.v3_identity_sidecar_enabled and settings.v3_identity_sidecar_base_url)

    def _require_local_configuration(self) -> None:
        if not self._locally_configured():
            raise ProviderNotConfiguredError(
                "V3 identity sidecar is disabled or V3_IDENTITY_SIDECAR_BASE_URL is not configured.",
                provider=self.name,
            )

    async def _remote_capabilities(self) -> dict[str, Any]:
        base_url = str(settings.v3_identity_sidecar_base_url or "").rstrip("/")
        cache_key = f"{base_url}|{settings.v3_identity_sidecar_capabilities_path}"
        now = time.monotonic()
        with self._capability_cache_lock:
            cached = self._capability_cache.get(cache_key)
            if cached and cached[0] > now:
                return dict(cached[1])

        url = _endpoint_url(base_url, settings.v3_identity_sidecar_capabilities_path)
        try:
            async with self._client(timeout_seconds=settings.v3_identity_sidecar_health_timeout_seconds) as client:
                response = await client.get(url, headers=self._headers())
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            raise ProviderRuntimeError(
                "Identity sidecar capability probe failed.",
                provider=self.name,
                detail={
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:500],
                    "retryable": True,
                    "endpoint": settings.v3_identity_sidecar_capabilities_path,
                },
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderCapabilityMismatchError(
                "Identity sidecar capability response must be a JSON object.",
                provider=self.name,
            )
        ttl = max(0.0, settings.v3_identity_sidecar_health_ttl_seconds)
        with self._capability_cache_lock:
            self._capability_cache[cache_key] = (now + ttl, dict(payload))
        return payload

    async def _post_generation(
        self,
        manifest: dict[str, Any],
        references: list[dict[str, Any]],
        repair_assets: dict[str, Path],
    ) -> dict[str, Any]:
        base_url = str(settings.v3_identity_sidecar_base_url or "").rstrip("/")
        url = _endpoint_url(base_url, settings.v3_identity_sidecar_generate_path)
        try:
            with ExitStack() as stack:
                files: list[tuple[str, tuple[str | None, Any, str]]] = [
                    ("manifest", (None, json.dumps(manifest, ensure_ascii=False), "application/json"))
                ]
                for index, reference in enumerate(references):
                    path = Path(reference["path"])
                    mime_type = str(reference.get("mime_type") or mimetypes.guess_type(path.name)[0] or "image/jpeg")
                    files.append(
                        (
                            f"reference_{index}",
                            (path.name, stack.enter_context(path.open("rb")), mime_type),
                        )
                    )
                for field_name in ("canvas", "mask"):
                    path = repair_assets.get(field_name)
                    if path is None:
                        continue
                    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
                    files.append(
                        (
                            field_name,
                            (path.name, stack.enter_context(path.open("rb")), mime_type),
                        )
                    )
                async with self._client() as client:
                    response = await client.post(url, headers=self._headers(), files=files)
                    response.raise_for_status()
                    payload = response.json()
        except Exception as exc:
            raise ProviderRuntimeError(
                "Identity sidecar generation failed.",
                provider=self.name,
                detail={
                    "error_type": type(exc).__name__,
                    "message": str(exc)[:500],
                    "retryable": True,
                    "reference_image_count": len(references),
                    "endpoint": settings.v3_identity_sidecar_generate_path,
                },
            ) from exc
        if not isinstance(payload, dict):
            raise ProviderRuntimeError(
                "Identity sidecar generation response must be a JSON object.",
                provider=self.name,
            )
        return payload

    def _identity_references(self, request: ImageGenerationRequest) -> list[dict[str, Any]]:
        asset_plan = request.asset_plan or request.prompt_plan.variables.get("asset_plan") or {}
        candidates = sorted(
            asset_plan.get("assets", []) if isinstance(asset_plan, dict) else [],
            key=lambda item: int(item.get("priority") or 0),
            reverse=True,
        )
        selected: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for item in candidates:
            if not isinstance(item, dict) or item.get("provider_input_mode") != "reference_image":
                continue
            truth_layers = {str(value) for value in item.get("truth_layers", []) if value}
            truth_layer = str(item.get("reference_truth_layer") or "")
            role = str(item.get("role") or "").lower()
            if "portrait_identity_truth" not in truth_layers and truth_layer != "portrait_identity_truth" and not any(
                marker in role for marker in ("portrait", "identity", "face")
            ):
                continue
            storage_path = item.get("storage_path")
            if not storage_path:
                continue
            path = Path(str(storage_path))
            if not path.exists() or not path.is_file():
                continue
            resolved = str(path.resolve())
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            selected.append(
                {
                    "asset_id": str(item.get("asset_id") or path.stem),
                    "source_asset_id": str(item.get("source_asset_id") or item.get("asset_id") or path.stem),
                    "path": path,
                    "mime_type": item.get("mime_type"),
                    "truth_layer": truth_layer or "portrait_identity_truth",
                    "derivative_kind": item.get("derivative_kind"),
                    "authority": item.get("authority"),
                }
            )
            if len(selected) >= max(1, settings.v3_identity_sidecar_max_references):
                break
        prepared_paths = prepare_provider_reference_images([item["path"] for item in selected])
        prepared_by_original = {str(item["path"]): item for item in selected}
        normalized: list[dict[str, Any]] = []
        for index, prepared in enumerate(prepared_paths):
            source = selected[index] if index < len(selected) else prepared_by_original.get(str(prepared), {})
            normalized.append({**source, "path": Path(prepared)})
        return normalized

    def _repair_assets(self, request: ImageGenerationRequest) -> dict[str, Path]:
        variables = request.prompt_plan.variables or {}
        raw_canvas = variables.get("identity_repair_canvas_path")
        raw_mask = variables.get("identity_repair_mask_path")
        if not raw_canvas and not raw_mask:
            return {}
        if not raw_canvas or not raw_mask:
            raise ProviderCapabilityMismatchError(
                "Identity-native local repair requires both canvas and mask files.",
                provider=self.name,
            )
        assets = {"canvas": Path(str(raw_canvas)), "mask": Path(str(raw_mask))}
        missing = [name for name, path in assets.items() if not path.exists() or not path.is_file()]
        if missing:
            raise ProviderCapabilityMismatchError(
                "Identity-native local repair canvas or mask file was not found.",
                provider=self.name,
                detail={"missing_repair_files": missing},
            )
        return assets

    def _manifest(
        self,
        request: ImageGenerationRequest,
        references: list[dict[str, Any]],
        remote_capabilities: dict[str, Any],
        *,
        prompt: str,
        repair_assets: dict[str, Path],
    ) -> dict[str, Any]:
        variables = request.prompt_plan.variables or {}
        return {
            "contract_version": "doc98-v1",
            "operation": "identity_reference_generation",
            "backend_family": settings.v3_identity_sidecar_provider,
            "model": settings.v3_identity_sidecar_model,
            "prompt": prompt,
            "negative_constraints": list(request.prompt_plan.negative_constraints),
            "count": 1,
            "size": request.prompt_plan.size or "auto",
            "quality": request.prompt_plan.quality,
            "output_format": request.prompt_plan.output_format,
            "idempotency_key": request.idempotency_key,
            "trace_id": request.trace_id,
            "input_fidelity": variables.get("input_fidelity") or "high",
            "reference_manifest": [
                {
                    "field": f"reference_{index}",
                    "asset_id": item.get("asset_id"),
                    "source_asset_id": item.get("source_asset_id"),
                    "truth_layer": item.get("truth_layer"),
                    "derivative_kind": item.get("derivative_kind"),
                }
                for index, item in enumerate(references)
            ],
            "requested_capabilities": {
                "identity_conditioning": True,
                "multi_reference": len(references) > 1,
                "identity_native_local_repair": bool(
                    repair_assets
                    and _capability_enabled(remote_capabilities, "identity_native_local_repair")
                ),
            },
            "repair": {
                "active": bool(repair_assets),
                "canvas_field": "canvas" if repair_assets.get("canvas") else None,
                "mask_field": "mask" if repair_assets.get("mask") else None,
            },
        }

    def _validated_outputs(
        self,
        payload: dict[str, Any],
        remote_capabilities: dict[str, Any],
        *,
        repair_active: bool,
    ) -> list[dict[str, Any]]:
        raw_outputs = payload.get("outputs")
        if not isinstance(raw_outputs, list) or not raw_outputs:
            raise ProviderRuntimeError(
                "Identity sidecar returned no image outputs.",
                provider=self.name,
            )
        outputs: list[dict[str, Any]] = []
        for item in raw_outputs:
            if not isinstance(item, dict) or not item.get("b64_json"):
                continue
            encoded = str(item["b64_json"])
            try:
                base64.b64decode(encoded, validate=True)
            except Exception as exc:
                raise ProviderRuntimeError(
                    "Identity sidecar returned invalid base64 image data.",
                    provider=self.name,
                ) from exc
            outputs.append(
                {
                    **item,
                    "b64_json": encoded,
                    "mime_type": item.get("mime_type") or "image/png",
                    "format": item.get("format") or "png",
                    "api_operation": "identity_reference_generation",
                    "identity_native_provider": True,
                    "identity_conditioning": True,
                    "identity_native_local_repair_capable": _capability_enabled(
                        remote_capabilities, "identity_native_local_repair"
                    ),
                    "identity_local_repair": repair_active,
                }
            )
        if not outputs:
            raise ProviderRuntimeError(
                "Identity sidecar returned no usable base64 image outputs.",
                provider=self.name,
            )
        return outputs[:1]

    def _client(self, *, timeout_seconds: float | None = None) -> httpx.AsyncClient:
        total_timeout = max(
            2.0,
            timeout_seconds
            if timeout_seconds is not None
            else settings.v3_identity_sidecar_timeout_seconds,
        )
        timeout = httpx.Timeout(
            total_timeout,
            connect=min(20.0, total_timeout),
            write=min(120.0, total_timeout),
            pool=min(30.0, total_timeout),
        )
        return httpx.AsyncClient(timeout=timeout, transport=self._transport, follow_redirects=True)

    def _headers(self) -> dict[str, str]:
        if not settings.v3_identity_sidecar_api_key:
            return {}
        return {"Authorization": f"Bearer {settings.v3_identity_sidecar_api_key}"}


def _endpoint_url(base_url: str, path: str) -> str:
    normalized_path = str(path or "").strip()
    if normalized_path.startswith("http://") or normalized_path.startswith("https://"):
        return normalized_path
    return f"{base_url}/{normalized_path.lstrip('/')}"


def _capability_enabled(payload: dict[str, Any], key: str) -> bool:
    if bool(payload.get(key)):
        return True
    capabilities = payload.get("capabilities")
    if isinstance(capabilities, dict):
        return bool(capabilities.get(key))
    if isinstance(capabilities, list):
        return key in {str(value) for value in capabilities}
    return False


def _public_capability_summary(payload: dict[str, Any]) -> dict[str, bool]:
    keys = ("identity_conditioning", "multi_reference", "identity_native_local_repair")
    return {key: _capability_enabled(payload, key) for key in keys}
