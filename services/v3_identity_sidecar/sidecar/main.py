from __future__ import annotations

import base64
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import secrets
from tempfile import TemporaryDirectory
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from .backends import ComfyUIIdentityBackend, IdentityBackend, SidecarBackendError, SidecarBackendUnavailable
from .config import SidecarSettings, settings as default_settings
from .contracts import BackendGenerationResult, IdentityGenerationManifest
from .coordinator import RequestCoordinator


def create_app(
    config: SidecarSettings | None = None,
    *,
    backend: IdentityBackend | None = None,
) -> FastAPI:
    active_config = config or default_settings
    active_backend = backend or _create_backend(active_config)
    coordinator = RequestCoordinator(
        concurrency=active_config.max_concurrency,
        ttl_seconds=active_config.idempotency_ttl_seconds,
        max_entries=active_config.idempotency_max_entries,
    )
    app = FastAPI(title="Alchemy V3 Identity Sidecar", version="0.1.0")
    app.state.config = active_config
    app.state.backend = active_backend
    app.state.coordinator = coordinator

    @app.middleware("http")
    async def reject_oversized_request_body(request: Request, call_next):  # noqa: ANN001
        if request.url.path == "/v1/identity/generate":
            raw_length = request.headers.get("content-length")
            if raw_length:
                try:
                    content_length = int(raw_length)
                except ValueError:
                    return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
                request_limit = (
                    active_config.max_total_upload_bytes
                    + active_config.max_prompt_chars * 4
                    + 512 * 1024
                )
                if content_length > request_limit:
                    return JSONResponse(status_code=413, content={"detail": "Request body exceeds the configured limit."})
        return await call_next(request)

    async def authorize(request: Request) -> None:
        if not active_config.api_key:
            return
        header = request.headers.get("authorization") or ""
        expected = f"Bearer {active_config.api_key}"
        if not secrets.compare_digest(header, expected):
            raise HTTPException(status_code=401, detail="Invalid identity sidecar credentials.")

    @app.exception_handler(SidecarBackendUnavailable)
    async def backend_unavailable_handler(_request: Request, exc: SidecarBackendUnavailable) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": {
                    "code": "identity_backend_unavailable",
                    "message": str(exc),
                    "retryable": True,
                    "detail": _public_detail(exc.detail),
                }
            },
        )

    @app.exception_handler(SidecarBackendError)
    async def backend_error_handler(_request: Request, exc: SidecarBackendError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "identity_backend_error",
                    "message": str(exc),
                    "retryable": bool(exc.retryable),
                    "detail": _public_detail(exc.detail),
                }
            },
        )

    @app.exception_handler(Exception)
    async def unexpected_error_handler(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "identity_sidecar_internal_error",
                    "message": "Identity sidecar encountered an internal error.",
                    "retryable": False,
                }
            },
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, Any]:
        return {"status": "ok", "service": active_config.service_name, "contract_version": active_config.contract_version}

    @app.get("/v1/capabilities", dependencies=[Depends(authorize)])
    async def capabilities() -> dict[str, Any]:
        state = await active_backend.capabilities()
        return {
            "status": "ok" if state.configured and state.healthy else "degraded",
            "provider": state.provider,
            "model": state.model,
            "backend": state.backend,
            "capabilities": {
                "identity_conditioning": state.identity_conditioning,
                "multi_reference": state.multi_reference,
                "identity_native_local_repair": state.identity_native_local_repair,
            },
            "limits": {"max_reference_images": state.max_reference_images, "max_batch": 1},
            "reason": state.reason,
            "metadata": _public_detail(state.metadata),
        }

    @app.post("/v1/identity/generate", dependencies=[Depends(authorize)])
    async def generate(request: Request) -> dict[str, Any]:
        form = await request.form()
        _validate_multipart_cardinality(form)
        manifest = _parse_manifest(form.get("manifest"), active_config)
        reference_uploads = _reference_uploads(form, manifest, active_config)
        canvas_upload, mask_upload = _repair_uploads(form, manifest)
        allowed_fields = {"manifest", *[item.field for item in manifest.reference_manifest]}
        if manifest.repair.active:
            allowed_fields.update({manifest.repair.canvas_field or "canvas", manifest.repair.mask_field or "mask"})
        unexpected_files = sorted(
            key for key, value in form.multi_items() if isinstance(value, UploadFile) and key not in allowed_fields
        )
        if unexpected_files:
            raise HTTPException(status_code=400, detail=f"Unexpected upload fields: {', '.join(unexpected_files)}")

        with TemporaryDirectory(prefix="alchemy_identity_sidecar_") as temp_root:
            root = Path(temp_root)
            total_bytes = 0
            reference_paths: list[Path] = []
            fingerprints: list[str] = []
            for index, upload in enumerate(reference_uploads):
                path, size, fingerprint = await _save_validated_upload(
                    upload,
                    root / f"reference_{index}",
                    active_config,
                )
                total_bytes += size
                reference_paths.append(path)
                fingerprints.append(fingerprint)
            canvas_path = None
            mask_path = None
            if canvas_upload is not None:
                canvas_path, size, fingerprint = await _save_validated_upload(
                    canvas_upload,
                    root / "canvas",
                    active_config,
                )
                total_bytes += size
                fingerprints.append(fingerprint)
            if mask_upload is not None:
                mask_path, size, fingerprint = await _save_validated_upload(
                    mask_upload,
                    root / "mask",
                    active_config,
                    allow_alpha=True,
                )
                total_bytes += size
                fingerprints.append(fingerprint)
            if total_bytes > active_config.max_total_upload_bytes:
                raise HTTPException(status_code=413, detail="Total identity upload size exceeds the configured limit.")

            request_key = _request_key(manifest, fingerprints)

            async def operation() -> dict[str, Any]:
                result = await active_backend.generate(
                    manifest,
                    reference_paths,
                    canvas=canvas_path,
                    mask=mask_path,
                )
                return _generation_response(result, manifest, active_config)

            return await coordinator.execute(request_key, operation)

    return app


def _create_backend(config: SidecarSettings) -> IdentityBackend:
    if config.backend == "comfyui":
        return ComfyUIIdentityBackend(config)
    raise RuntimeError(f"Unsupported identity sidecar backend: {config.backend}")


def _parse_manifest(raw: Any, config: SidecarSettings) -> IdentityGenerationManifest:
    if not isinstance(raw, str) or not raw.strip():
        raise HTTPException(status_code=400, detail="Multipart field 'manifest' is required.")
    try:
        payload = json.loads(raw)
        manifest = IdentityGenerationManifest.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid Doc98 manifest: {str(exc)[:500]}") from exc
    if len(manifest.prompt) > config.max_prompt_chars:
        raise HTTPException(status_code=413, detail="Identity prompt exceeds the configured character limit.")
    if manifest.backend_family not in {"custom", config.provider_family}:
        raise HTTPException(status_code=409, detail="Requested identity backend family does not match this sidecar.")
    if manifest.model not in {"identity-native", config.model_name}:
        raise HTTPException(status_code=409, detail="Requested identity model does not match this sidecar.")
    return manifest


def _validate_multipart_cardinality(form: Any) -> None:
    counts: dict[str, int] = {}
    for key, _value in form.multi_items():
        counts[str(key)] = counts.get(str(key), 0) + 1
    duplicates = sorted(key for key, count in counts.items() if count > 1)
    if duplicates:
        raise HTTPException(status_code=400, detail=f"Multipart fields must be unique: {', '.join(duplicates)}")


def _reference_uploads(
    form: Any,
    manifest: IdentityGenerationManifest,
    config: SidecarSettings,
) -> list[UploadFile]:
    if len(manifest.reference_manifest) > config.max_references:
        raise HTTPException(status_code=413, detail="Reference count exceeds the configured limit.")
    fields = [item.field for item in manifest.reference_manifest]
    if len(fields) != len(set(fields)):
        raise HTTPException(status_code=400, detail="Reference manifest fields must be unique.")
    uploads: list[UploadFile] = []
    for field in fields:
        value = form.get(field)
        if not isinstance(value, UploadFile):
            raise HTTPException(status_code=400, detail=f"Missing identity reference upload: {field}")
        uploads.append(value)
    return uploads


def _repair_uploads(
    form: Any,
    manifest: IdentityGenerationManifest,
) -> tuple[UploadFile | None, UploadFile | None]:
    if not manifest.repair.active:
        return None, None
    canvas_field = manifest.repair.canvas_field or "canvas"
    mask_field = manifest.repair.mask_field or "mask"
    canvas = form.get(canvas_field)
    mask = form.get(mask_field)
    if not isinstance(canvas, UploadFile) or not isinstance(mask, UploadFile):
        raise HTTPException(status_code=400, detail="Active identity repair requires canvas and mask uploads.")
    return canvas, mask


async def _save_validated_upload(
    upload: UploadFile,
    target_without_suffix: Path,
    config: SidecarSettings,
    *,
    allow_alpha: bool = False,
) -> tuple[Path, int, str]:
    content = bytearray()
    while True:
        chunk = await upload.read(64 * 1024)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > config.max_file_bytes:
            raise HTTPException(status_code=413, detail=f"Upload exceeds file limit: {upload.filename or 'image'}")
    if not content:
        raise HTTPException(status_code=400, detail=f"Upload is empty: {upload.filename or 'image'}")
    raw = bytes(content)
    try:
        with Image.open(BytesIO(raw)) as image:
            detected_format = str(image.format or "").upper()
            image.verify()
        with Image.open(BytesIO(raw)) as image:
            if image.width < 32 or image.height < 32:
                raise ValueError("image dimensions are too small")
            if not allow_alpha and image.mode not in {"RGB", "RGBA", "L", "P"}:
                raise ValueError("unsupported image color mode")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Upload is not a valid image: {upload.filename or 'image'}") from exc
    suffix_by_format = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}
    suffix = suffix_by_format.get(detected_format)
    if suffix is None:
        raise HTTPException(status_code=415, detail=f"Unsupported image format: {detected_format or 'unknown'}")
    path = target_without_suffix.with_suffix(suffix)
    path.write_bytes(raw)
    return path, len(raw), sha256(raw).hexdigest()


def _request_key(manifest: IdentityGenerationManifest, fingerprints: list[str]) -> str:
    payload = manifest.model_dump(mode="json")
    payload["reference_fingerprints"] = fingerprints
    digest = sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    prefix = manifest.idempotency_key or manifest.trace_id or uuid4().hex
    return f"{prefix}:{digest}"


def _generation_response(
    result: BackendGenerationResult,
    manifest: IdentityGenerationManifest,
    config: SidecarSettings,
) -> dict[str, Any]:
    outputs = [
        {
            "b64_json": base64.b64encode(image.content).decode("ascii"),
            "mime_type": image.mime_type,
            "format": _format_from_mime(image.mime_type, manifest.output_format),
            "width": image.width,
            "height": image.height,
        }
        for image in result.images
    ]
    if not outputs:
        raise SidecarBackendError("Identity backend returned no images.")
    return {
        "provider": result.provider or config.provider_family,
        "model": result.model or config.model_name,
        "outputs": outputs[:1],
        "metadata": {
            "contract_version": config.contract_version,
            "backend": config.backend,
            "reference_count": len(manifest.reference_manifest),
            "repair_active": manifest.repair.active,
            "idempotent": bool(manifest.idempotency_key),
            **_public_detail(result.metadata),
        },
    }


def _format_from_mime(mime_type: str, fallback: str) -> str:
    normalized = str(mime_type or "").lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return "jpeg"
    if "webp" in normalized:
        return "webp"
    if "png" in normalized:
        return "png"
    return fallback


def _public_detail(value: dict[str, Any]) -> dict[str, Any]:
    denied = {"api_key", "authorization", "token", "secret", "raw_embedding", "embedding"}
    return {
        str(key): item
        for key, item in dict(value or {}).items()
        if str(key).lower() not in denied and _json_safe(item)
    }


def _json_safe(value: Any) -> bool:
    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False


app = create_app()
