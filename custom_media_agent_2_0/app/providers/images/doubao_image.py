from __future__ import annotations

from typing import Any

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


class V2DoubaoImageProvider:
    name = "doubao_image"

    async def capabilities(self) -> V2ImageProviderCapabilities:
        configured = bool(settings.doubao_image_api_key)
        return V2ImageProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.doubao_image_model],
            operations=["generate"],
            input_roles=[],
            limits={
                "max_batch": 4,
                "supports_reference_images": False,
                "supports_image_edit": False,
                "api_style": "openai_images_generations",
            },
            reason=None if configured else "V2_DOUBAO_IMAGE_API_KEY or DOUBAO_IMAGE_API_KEY is not configured.",
        )

    async def generate(self, request: V2ImageProviderRequest) -> V2ImageProviderResult:
        if not settings.doubao_image_api_key:
            raise V2ImageProviderNotConfiguredError(
                "V2_DOUBAO_IMAGE_API_KEY or DOUBAO_IMAGE_API_KEY is not configured.",
                provider=self.name,
            )
        if _requires_provider_images(request):
            raise V2ImageProviderRuntimeError(
                "Doubao image generation currently supports text-to-image only; use GPT Image 2 for uploaded reference images.",
                provider=self.name,
                detail={
                    "reference_image_count": len([image for image in request.input_images if image.provider_input_required]),
                    "requested_model": settings.doubao_image_model,
                },
            )
        count = _count(request.prompt_plan)
        outputs: list[V2ImageProviderOutput] = []
        for index in range(count):
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
                "reference_image_count": 0,
                "supports_reference_images": False,
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
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
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
        outputs = _outputs_from_response(data, plan, index=index)
        if not outputs:
            raise V2ImageProviderRuntimeError(
                "Doubao image response did not include image bytes.",
                provider=self.name,
                detail={"response_keys": sorted(data.keys())[:12], "request_index": index},
            )
        return outputs


def _images_url() -> str:
    base = (settings.doubao_image_base_url or "https://aiself.vip/v1").rstrip("/")
    return f"{base}/images/generations"


def _requires_provider_images(request: V2ImageProviderRequest) -> bool:
    return any(image.provider_input_required for image in request.input_images)


def _count(plan) -> int:
    try:
        value = int(plan.provider_parameters.get("count", 1))
    except Exception:
        value = 1
    return max(1, min(value, 4))


def _size(plan) -> str | None:
    params = plan.provider_parameters or {}
    size = params.get("size") or params.get("aspect_ratio")
    if not size or str(size).strip().lower() in {"auto", "default"}:
        return None
    if isinstance(size, str) and "x" in size:
        return size
    mapping = {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "3:2": "1536x1024",
        "3:4": "1024x1536",
        "4:3": "1536x1024",
        "9:16": "1024x1536",
        "16:9": "1536x1024",
    }
    return mapping.get(str(size))


def _outputs_from_response(data: dict[str, Any], plan, *, index: int) -> list[V2ImageProviderOutput]:
    outputs: list[V2ImageProviderOutput] = []
    for item in data.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        encoded = item.get("b64_json")
        if not encoded and isinstance(item.get("url"), str) and item["url"].startswith("data:image/"):
            encoded = item["url"].split(",", 1)[-1]
        if not encoded:
            continue
        width, height = _dimensions(item.get("size") or _size(plan))
        outputs.append(
            V2ImageProviderOutput(
                b64_json=encoded,
                mime_type="image/png",
                format="png",
                width=width,
                height=height,
                metadata={
                    "request_index": index,
                    "api_operation": "images.generate",
                    "reference_image_count": 0,
                },
            )
        )
    return outputs


def _dimensions(value: str | None) -> tuple[int | None, int | None]:
    try:
        width, height = str(value or "").lower().split("x", 1)
        return int(width), int(height)
    except (AttributeError, ValueError):
        return None, None
