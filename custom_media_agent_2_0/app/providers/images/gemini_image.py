from __future__ import annotations

import asyncio
import base64
import math
import mimetypes
from typing import Any
from urllib.parse import quote

import httpx

from app.config import settings
from app.providers.images.base import (
    V2ImageProviderCapabilities,
    V2ImageProviderNotConfiguredError,
    V2ImageProviderOutput,
    V2ImageProviderRequest,
    V2ImageProviderResult,
    V2ImageProviderRuntimeError,
)
from app.services.uploaded_assets import uploaded_asset_path


_gemini_generation_lock = asyncio.Lock()


class V2GeminiImageProvider:
    name = "gemini_image"

    async def capabilities(self) -> V2ImageProviderCapabilities:
        model_supports_images = _supports_image_generation_model(settings.gemini_image_model)
        configured = bool(settings.gemini_api_key) and model_supports_images
        return V2ImageProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.gemini_image_model],
            operations=["generate", "image_reference"],
            input_roles=[
                "style_reference",
                "subject_reference",
                "logo_reference",
                "face_reference",
                "background_reference",
                "composition_reference",
                "color_reference",
            ],
            limits={"max_batch": 4, "max_reference_images": 3},
            reason=_gemini_configuration_reason(has_key=bool(settings.gemini_api_key), model_supports_images=model_supports_images),
        )

    async def generate(self, request: V2ImageProviderRequest) -> V2ImageProviderResult:
        if not settings.gemini_api_key:
            raise V2ImageProviderNotConfiguredError("V2_GEMINI_API_KEY is not configured.", provider=self.name)
        if not _supports_image_generation_model(settings.gemini_image_model):
            raise V2ImageProviderNotConfiguredError(
                f"{settings.gemini_image_model} appears to support text output only. Configure an image-capable Gemini model.",
                provider=self.name,
            )
        count = _count(request.prompt_plan)
        reference_paths = _reference_paths(request)
        outputs: list[V2ImageProviderOutput] = []
        async with _gemini_generation_lock:
            for index in range(count):
                outputs.extend(await self._generate_one(request, reference_paths, index=index))
                if len(outputs) >= count:
                    break
        return V2ImageProviderResult(
            provider=self.name,
            model=settings.gemini_image_model,
            outputs=outputs[:count],
            raw_response_summary={
                "output_count": min(len(outputs), count),
                "native_v2": True,
                "api_style": "gemini_generate_content",
                "reference_image_count": len(reference_paths),
            },
        )

    async def _generate_one(self, request: V2ImageProviderRequest, reference_paths: list, *, index: int) -> list[V2ImageProviderOutput]:
        payload = _payload(request, reference_paths)
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_api_key or "",
        }
        timeout = httpx.Timeout(settings.gemini_image_timeout_seconds, connect=30.0)
        attempts: list[dict[str, Any]] = []
        data: dict[str, Any] | None = None
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response: httpx.Response | None = None
            for url, model in _generate_content_candidates():
                try:
                    response = await client.post(url, headers=headers, json=payload)
                except httpx.HTTPError as exc:
                    attempts.append({"model": model, "error_type": type(exc).__name__, "message": str(exc)[:300]})
                    continue
                if response.status_code < 400:
                    try:
                        data = response.json()
                    except ValueError:
                        attempts.append({"model": model, "status_code": response.status_code, "body": response.text[:500], "error_type": "non_json_response"})
                        continue
                    break
                attempts.append({"model": model, "status_code": response.status_code, "body": response.text[:500]})
                if response.status_code not in {400, 404}:
                    break
        if response is None or data is None or response.status_code >= 400:
            raise V2ImageProviderRuntimeError(
                "Gemini image generation failed.",
                provider=self.name,
                detail={"request_index": index, "attempts": attempts[-4:]},
            )
        outputs = _extract_outputs(data, request.prompt_plan, index=index, reference_count=len(reference_paths))
        if not outputs:
            raise V2ImageProviderRuntimeError(
                "Gemini response did not include image bytes.",
                provider=self.name,
                detail={"request_index": index, "response_keys": sorted(data.keys())[:12]},
            )
        return outputs


def _reference_paths(request: V2ImageProviderRequest) -> list:
    paths = []
    seen: set[str] = set()
    for image in request.input_images[:3]:
        if not image.provider_input_required:
            continue
        path = uploaded_asset_path(image.asset_id)
        if not path or not path.exists():
            raise V2ImageProviderRuntimeError(
                "Required V2 input image file is missing.",
                provider="gemini_image",
                detail={"asset_id": image.asset_id, "role": image.role},
            )
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def _generate_content_candidates() -> list[tuple[str, str]]:
    roots = _api_roots()
    models = _model_candidates(settings.gemini_image_model)
    encoded_key = quote(settings.gemini_api_key or "", safe="")
    candidates: list[tuple[str, str]] = []
    seen: set[str] = set()
    for root in roots:
        for model in models:
            url = f"{root}/models/{model}:generateContent"
            if encoded_key:
                url = f"{url}?key={encoded_key}"
            if url in seen:
                continue
            seen.add(url)
            candidates.append((url, model))
    return candidates


def _api_roots() -> list[str]:
    configured = settings.gemini_base_url
    if not configured:
        return ["https://generativelanguage.googleapis.com/v1beta"]
    base_url = configured.rstrip("/")
    roots = [base_url]
    if not (base_url.endswith("/v1") or base_url.endswith("/v1beta")):
        roots.append(f"{base_url}/v1beta")
        roots.append(f"{base_url}/v1")
    return roots


def _model_candidates(model: str) -> list[str]:
    models = [model]
    if model == "gemini-3-pro-image-preview":
        models.append("gemini-3-pro-image")
    elif model == "gemini-3-pro-image":
        models.append("gemini-3-pro-image-preview")
    return models


def _supports_image_generation_model(model: str) -> bool:
    normalized = (model or "").strip().lower()
    return "image" in normalized or "imagen" in normalized


def _gemini_configuration_reason(*, has_key: bool, model_supports_images: bool) -> str | None:
    if not has_key:
        return "V2_GEMINI_API_KEY is not configured."
    if not model_supports_images:
        return "Configured Gemini model appears to support text output only; use an image-capable Gemini model."
    return None


def _payload(request: V2ImageProviderRequest, reference_paths: list) -> dict[str, Any]:
    plan = request.prompt_plan
    aspect_ratio = _aspect_ratio(plan)
    image_config: dict[str, Any] = {}
    if aspect_ratio:
        image_config["aspectRatio"] = aspect_ratio
    if _supports_image_size(settings.gemini_image_model):
        image_config["imageSize"] = "2K" if _quality(plan) == "high" else "1K"
    parts: list[dict[str, Any]] = [{"text": str(plan.user_variables.get("generation_prompt") or plan.prompt)}]
    for path in reference_paths:
        mime_type = mimetypes.guess_type(str(path))[0] or "image/png"
        parts.append(
            {
                "inlineData": {
                    "mimeType": mime_type,
                    "data": base64.b64encode(path.read_bytes()).decode("ascii"),
                }
            }
        )
    return {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["Image"],
            "responseFormat": {"image": image_config},
        },
    }


def _extract_outputs(data: dict[str, Any], plan, *, index: int, reference_count: int) -> list[V2ImageProviderOutput]:
    outputs = _extract_openai_style_outputs(data, plan, index=index, reference_count=reference_count)
    if outputs:
        return outputs
    parsed: list[V2ImageProviderOutput] = []
    for candidate in data.get("candidates", []) or []:
        content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
        for part in content.get("parts", []) or []:
            inline_data = (part.get("inlineData") or part.get("inline_data")) if isinstance(part, dict) else None
            if not inline_data:
                continue
            encoded = inline_data.get("data")
            if not encoded:
                continue
            mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or "image/png"
            fmt = _format_from_mime(mime_type)
            width, height = _dimensions(plan)
            parsed.append(
                V2ImageProviderOutput(
                    b64_json=encoded,
                    mime_type=mime_type,
                    format=fmt,
                    width=width,
                    height=height,
                    metadata={
                        "request_index": index,
                        "api_operation": "generateContent",
                        "reference_image_count": reference_count,
                    },
                )
            )
    return parsed


def _extract_openai_style_outputs(data: dict[str, Any], plan, *, index: int, reference_count: int) -> list[V2ImageProviderOutput]:
    outputs: list[V2ImageProviderOutput] = []
    for item in data.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        encoded = item.get("b64_json")
        if not encoded and isinstance(item.get("url"), str) and item["url"].startswith("data:image/"):
            encoded = item["url"].split(",", 1)[-1]
        if not encoded:
            continue
        mime_type = item.get("mime_type") or item.get("mimeType") or "image/png"
        width, height = _dimensions(plan)
        outputs.append(
            V2ImageProviderOutput(
                b64_json=encoded,
                mime_type=mime_type,
                format=_format_from_mime(mime_type),
                width=item.get("width") or width,
                height=item.get("height") or height,
                metadata={
                    "request_index": index,
                    "api_operation": "generateContent",
                    "reference_image_count": reference_count,
                },
            )
        )
    return outputs


def _count(plan) -> int:
    try:
        value = int(plan.provider_parameters.get("count", 1))
    except Exception:
        value = 1
    return max(1, min(value, 4))


def _quality(plan) -> str:
    value = str((plan.provider_parameters or {}).get("quality") or "high")
    return value if value in {"auto", "low", "medium", "high"} else "high"


def _aspect_ratio(plan) -> str | None:
    size = (plan.provider_parameters or {}).get("size") or (plan.provider_parameters or {}).get("aspect_ratio")
    if not size or str(size).strip().lower() in {"auto", "default"}:
        return None
    if isinstance(size, str) and ":" in size:
        return size
    if isinstance(size, str) and "x" in size:
        try:
            width_text, height_text = size.lower().split("x", 1)
            width = int(width_text)
            height = int(height_text)
            divisor = math.gcd(width, height)
            return f"{width // divisor}:{height // divisor}"
        except (ValueError, AttributeError):
            return None
    return None


def _dimensions(plan) -> tuple[int | None, int | None]:
    size = (plan.provider_parameters or {}).get("size") or (plan.provider_parameters or {}).get("aspect_ratio")
    if not isinstance(size, str) or "x" not in size:
        return None, None
    try:
        width, height = size.lower().split("x", 1)
        return int(width), int(height)
    except (ValueError, AttributeError):
        return None, None


def _supports_image_size(model: str) -> bool:
    normalized = model.lower()
    return normalized.startswith("gemini-3") or "3-pro-image" in normalized


def _format_from_mime(mime_type: str) -> str:
    normalized = mime_type.lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return "jpeg"
    if "webp" in normalized:
        return "webp"
    return "png"
