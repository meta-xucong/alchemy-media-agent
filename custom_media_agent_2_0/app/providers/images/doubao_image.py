from __future__ import annotations

from copy import copy
from contextlib import ExitStack
from typing import Any

import httpx

from app.config import settings
from app.providers.images.claim_fenced_http import claim_fenced_async_client
from app.providers.images.base import (
    V2ImageProviderCapabilities,
    V2ImageProviderNotConfiguredError,
    V2ImageProviderOutput,
    V2ImageProviderRequest,
    V2ImageProviderResult,
    V2ImageProviderRuntimeError,
)
from app.providers.images.response_payloads import outputs_from_image_response
from app.services.uploaded_assets import uploaded_asset_path
from app.services.canvas_intent import exact_canvas_size, resolve_prompt_canvas


class V2DoubaoImageProvider:
    name = "doubao_image"

    async def capabilities(self) -> V2ImageProviderCapabilities:
        configured = bool(settings.doubao_image_api_key)
        return V2ImageProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.doubao_image_model],
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
            limits={
                "max_batch": 4,
                "supports_reference_images": True,
                "supports_image_edit": True,
                "api_style": "openai_images_generations",
                **_canvas_capabilities(),
            },
            reason=None if configured else "V2_DOUBAO_IMAGE_API_KEY or DOUBAO_IMAGE_API_KEY is not configured.",
        )

    async def generate(self, request: V2ImageProviderRequest) -> V2ImageProviderResult:
        if not settings.doubao_image_api_key:
            raise V2ImageProviderNotConfiguredError(
                "V2_DOUBAO_IMAGE_API_KEY or DOUBAO_IMAGE_API_KEY is not configured.",
                provider=self.name,
            )
        reference_paths = _reference_paths(request)
        count = _count(request.prompt_plan)
        outputs: list[V2ImageProviderOutput] = []
        for index in range(count):
            if reference_paths:
                outputs.extend(await self._generate_one_with_references(request, reference_paths, index=index))
            else:
                outputs.extend(await self._generate_one(request, index=index))
            if len(outputs) >= count:
                break
        return V2ImageProviderResult(
            provider=self.name,
            model=settings.doubao_image_model,
            outputs=outputs[:count],
            raw_response_summary={
                "output_count": min(len(outputs), count),
                "native_v2": True,
                "api_style": "openai_images_generations",
                "reference_image_count": len(reference_paths),
                "supports_reference_images": True,
            },
        )

    async def _generate_one(self, request: V2ImageProviderRequest, *, index: int) -> list[V2ImageProviderOutput]:
        plan = request.prompt_plan
        payload: dict[str, Any] = {
            "model": settings.doubao_image_model,
            "prompt": str(plan.user_variables.get("generation_prompt") or plan.prompt),
            "response_format": "b64_json",
        }
        size = _size(plan)
        if size:
            payload["size"] = size
        headers = {
            "Authorization": f"Bearer {settings.doubao_image_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(settings.doubao_image_timeout_seconds, connect=30.0)
        async with claim_fenced_async_client(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(_images_url(), headers=headers, json=payload)
        if response.status_code >= 400:
            raise V2ImageProviderRuntimeError(
                "Doubao image generation returned an error.",
                provider=self.name,
                detail={"status_code": response.status_code, "body": response.text[:1200], "request_index": index},
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise V2ImageProviderRuntimeError(
                "Doubao image generation returned non-JSON response.",
                provider=self.name,
                detail={"body": response.text[:500], "request_index": index},
            ) from exc
        return await _outputs_from_response(data, plan, index=index, operation="images.generate", reference_count=0)

    async def _generate_one_with_references(
        self,
        request: V2ImageProviderRequest,
        reference_paths: list,
        *,
        index: int,
    ) -> list[V2ImageProviderOutput]:
        plan = request.prompt_plan
        data: dict[str, Any] = {
            "model": settings.doubao_image_model,
            "prompt": str(plan.user_variables.get("generation_prompt") or plan.prompt),
            "response_format": "b64_json",
            "n": "1",
        }
        size = _size(plan)
        if size:
            data["size"] = size
        headers = {"Authorization": f"Bearer {settings.doubao_image_api_key}"}
        timeout = httpx.Timeout(settings.doubao_image_timeout_seconds, connect=30.0)
        with ExitStack() as stack:
            files = [
                ("image", (path.name, stack.enter_context(path.open("rb")), _mime_for_path(path)))
                for path in reference_paths
            ]
            async with claim_fenced_async_client(timeout=timeout, follow_redirects=True) as client:
                response = await client.post(_image_edits_url(), headers=headers, data=data, files=files)
        if response.status_code >= 400:
            raise V2ImageProviderRuntimeError(
                "Doubao image edit returned an error.",
                provider=self.name,
                detail={
                    "status_code": response.status_code,
                    "body": response.text[:1200],
                    "request_index": index,
                    "reference_image_count": len(reference_paths),
                },
            )
        try:
            payload = response.json()
        except ValueError as exc:
            raise V2ImageProviderRuntimeError(
                "Doubao image edit returned non-JSON response.",
                provider=self.name,
                detail={"body": response.text[:500], "request_index": index, "reference_image_count": len(reference_paths)},
            ) from exc
        return await _outputs_from_response(
            payload,
            plan,
            index=index,
            operation="images.edit",
            reference_count=len(reference_paths),
        )


def _images_url() -> str:
    base = (settings.doubao_image_base_url or "https://aiself.vip/v1").rstrip("/")
    return f"{base}/images/generations"


def _image_edits_url() -> str:
    base = (settings.doubao_image_base_url or "https://aiself.vip/v1").rstrip("/")
    return f"{base}/images/edits"


def _reference_paths(request: V2ImageProviderRequest) -> list:
    paths = []
    seen: set[str] = set()
    for image in request.input_images[: settings.max_uploaded_asset_count]:
        if not image.provider_input_required:
            continue
        path = uploaded_asset_path(image.asset_id)
        if not path or not path.exists():
            raise V2ImageProviderRuntimeError(
                "Required V2 input image file is missing.",
                provider="doubao_image",
                detail={"asset_id": image.asset_id, "role": image.role},
            )
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def _count(plan) -> int:
    try:
        value = int(plan.provider_parameters.get("count", 1))
    except Exception:
        value = 1
    return max(1, min(value, 4))


_STANDARD_CANVASES = ("1024x1024", "1024x1536", "1536x1024")


def _supports_seedream4_canvas() -> bool:
    return str(settings.doubao_image_model or "").strip() == "doubao-seedream-4-0-250828"


def _canvas_capabilities() -> dict[str, Any]:
    if not _supports_seedream4_canvas():
        return {"sizes": list(_STANDARD_CANVASES), "unsupported_size_policy": "omit_native_default"}
    return {
        "sizes": ["1K", "2K", "4K", "custom_dimensions"],
        "custom_size": {"min_pixels": 921600, "max_pixels": 16777216, "min_aspect_ratio": 1 / 16, "max_aspect_ratio": 16},
        "native_default_size": "2048x2048",
        "unsupported_size_policy": "omit_native_default",
    }


def _size(plan) -> str | None:
    params = plan.provider_parameters or {}
    value = params.get("size") or params.get("aspect_ratio")
    text = str(value or "").strip().lower().replace(" ", "").replace("×", "x")
    if text in {"", "auto", "default"}:
        return None
    if _supports_seedream4_canvas() and text in {"1k", "2k", "4k"}:
        return text.upper()
    if ":" in text:
        ratio = resolve_prompt_canvas(text)
        if not ratio or ":" not in ratio:
            return None
        text = exact_canvas_size(ratio)
    if not _supports_seedream4_canvas():
        return text if text in _STANDARD_CANVASES else None
    width, height = _dimensions(text)
    if not width or not height or min(width, height) <= 0:
        return None
    if not 921600 <= width * height <= 16777216 or max(width, height) > 16 * min(width, height):
        return None
    return f"{width}x{height}"


async def _outputs_from_response(
    data: dict[str, Any],
    plan,
    *,
    index: int,
    operation: str,
    reference_count: int,
) -> list[V2ImageProviderOutput]:
    # Response dimensions may fall back only to the effective wire canvas,
    # never to an unsupported request that was omitted. Keep the frozen plan
    # and prompt untouched.
    response_plan = copy(plan)
    response_plan.provider_parameters = {"size": _size(plan)}
    return await outputs_from_image_response(
        data,
        response_plan,
        provider="doubao_image",
        missing_message="Doubao image response did not include image bytes.",
        index=index,
        operation=operation,
        reference_count=reference_count,
        default_format="png",
        default_mime_type="image/png",
        url_timeout_seconds=settings.doubao_image_timeout_seconds,
    )


def _dimensions(value: str | None) -> tuple[int | None, int | None]:
    try:
        width, height = str(value or "").lower().split("x", 1)
        return int(width), int(height)
    except (AttributeError, ValueError):
        return None, None


def _mime_for_path(path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    return "image/png"
