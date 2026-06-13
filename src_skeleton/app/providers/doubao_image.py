from __future__ import annotations

import asyncio
import base64
from typing import Any

import httpx

from app.config import settings
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError, ProviderRuntimeError


_doubao_image_generation_lock = asyncio.Lock()


class DoubaoImageProvider:
    name = "doubao_image"

    async def capabilities(self) -> ProviderCapabilities:
        configured = bool(settings.doubao_image_api_key)
        return ProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.doubao_image_model],
            operations=["generate"],
            advanced_asset_roles=[],
            model_capabilities=[
                {
                    "id": settings.doubao_image_model,
                    "capabilities": ["text_to_image"],
                    "advanced_asset_roles": [],
                }
            ],
            limits={
                "max_batch": 4,
                "formats": ["png"],
                "sizes": ["1024x1024", "1024x1536", "1536x1024"],
                "supports_reference_images": False,
                "supports_image_edit": False,
            },
            reason=None if configured else "DOUBAO_IMAGE_API_KEY is not configured.",
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not settings.doubao_image_api_key:
            raise ProviderNotConfiguredError("DOUBAO_IMAGE_API_KEY is not configured.", provider=self.name)
        asset_plan = request.asset_plan or (request.prompt_plan.variables.get("asset_plan") if request.prompt_plan.variables else None)
        if _requires_provider_images(asset_plan):
            raise ProviderRuntimeError(
                "Doubao image generation currently supports text-to-image only; use GPT Image 2 for uploaded reference images.",
                provider=self.name,
                detail={"requires_image_reference": True, "requested_model": settings.doubao_image_model},
            )

        outputs: list[dict[str, Any]] = []
        prompt = _prompt(request.prompt_plan)
        count = max(1, min(int(request.prompt_plan.count or 1), 4))
        async with _doubao_image_generation_lock:
            for index in range(count):
                outputs.extend(await self._generate_one(prompt, request.prompt_plan, index=index))
                if len(outputs) >= count:
                    break
        return ImageGenerationResult(
            provider=self.name,
            model=settings.doubao_image_model,
            outputs=outputs[:count],
            raw_response_summary={
                "output_count": min(len(outputs), count),
                "requests": count,
                "api_style": "openai_images_generations",
                "supports_reference_images": False,
            },
        )

    async def _generate_one(self, prompt: str, plan, *, index: int) -> list[dict[str, Any]]:
        payload = {
            "model": settings.doubao_image_model,
            "prompt": prompt,
            "response_format": "b64_json",
        }
        size = _size(plan.size)
        if size:
            payload["size"] = size
        headers = {
            "Authorization": f"Bearer {settings.doubao_image_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(300.0, connect=30.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(_images_url(), headers=headers, json=payload)
        if response.status_code >= 400:
            raise ProviderRuntimeError(
                "Doubao image generation returned an error.",
                provider=self.name,
                detail={"status_code": response.status_code, "body": response.text[:1200], "request_index": index},
            )
        try:
            data = response.json()
        except ValueError as exc:
            raise ProviderRuntimeError(
                "Doubao image generation returned non-JSON response.",
                provider=self.name,
                detail={"body": response.text[:500], "request_index": index},
            ) from exc
        outputs = _outputs_from_response(data, plan, index=index)
        if not outputs:
            raise ProviderRuntimeError(
                "Doubao image response did not include image bytes.",
                provider=self.name,
                detail={"response_keys": sorted(data.keys())[:12], "request_index": index},
            )
        return outputs

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise ProviderRuntimeError(
            "Doubao image edit is not enabled; use GPT Image 2 for image edits.",
            provider=self.name,
            detail={"supports_image_edit": False},
        )

    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate:
        return CostEstimate(
            provider=self.name,
            model=settings.doubao_image_model,
            estimated_cost=0.0,
            detail={"note": "Use sub2api/Volcengine Ark billing for production cost estimates."},
        )


def _images_url() -> str:
    base = (settings.doubao_image_base_url or "https://aiself.vip/v1").rstrip("/")
    return f"{base}/images/generations"


def _prompt(plan) -> str:
    generation_prompt = plan.variables.get("generation_prompt") if getattr(plan, "variables", None) else None
    if generation_prompt:
        return str(generation_prompt)
    return "\n".join(
        part
        for part in [
            f"Main subject: {plan.main_subject}",
            f"Scene: {plan.scene or ''}",
            f"Style: {plan.style or ''}",
            f"Composition: {plan.composition or ''}",
            f"Brand constraints: {', '.join(plan.brand_constraints)}",
            f"Required text: {plan.text}",
            f"Avoid: {', '.join(plan.negative_constraints)}",
        ]
        if part.strip()
    )


def _size(value: str | None) -> str | None:
    if not value or str(value).strip().lower() in {"auto", "default"}:
        return None
    if "x" in str(value):
        return str(value)
    mapping = {
        "1:1": "1024x1024",
        "2:3": "1024x1536",
        "3:2": "1536x1024",
        "3:4": "1024x1536",
        "4:3": "1536x1024",
        "9:16": "1024x1536",
        "16:9": "1536x1024",
    }
    return mapping.get(str(value))


def _outputs_from_response(data: dict[str, Any], plan, *, index: int) -> list[dict[str, Any]]:
    outputs: list[dict[str, Any]] = []
    for item in data.get("data", []) or []:
        if not isinstance(item, dict):
            continue
        encoded = item.get("b64_json")
        if not encoded and isinstance(item.get("url"), str) and item["url"].startswith("data:image/"):
            encoded = item["url"].split(",", 1)[-1]
        if not encoded:
            continue
        fmt = _format(plan.output_format)
        width, height = _dimensions(item.get("size") or plan.size)
        outputs.append(
            {
                "b64_json": _normalize_b64(encoded),
                "mime_type": f"image/{fmt}",
                "format": fmt,
                "width": width,
                "height": height,
                "request_index": index,
                "api_operation": "images.generate",
            }
        )
    return outputs


def _format(value: str | None) -> str:
    value = str(value or "png").lower()
    return value if value in {"png", "jpeg", "webp"} else "png"


def _dimensions(value: str | None) -> tuple[int | None, int | None]:
    try:
        width, height = str(value or "").lower().split("x", 1)
        return int(width), int(height)
    except (AttributeError, ValueError):
        return None, None


def _normalize_b64(value: str) -> str:
    if value.startswith("data:image/"):
        return value.split(",", 1)[-1]
    # Validate enough to catch upstream error strings without logging content.
    try:
        base64.b64decode(value, validate=False)
    except Exception:
        return value
    return value


def _requires_provider_images(asset_plan: dict[str, Any] | None) -> bool:
    if not isinstance(asset_plan, dict):
        return False
    provider_input_plan = asset_plan.get("provider_input_plan") or {}
    return bool(
        provider_input_plan.get("reference_image_count")
        or provider_input_plan.get("requires_image_reference")
        or provider_input_plan.get("operation") in {"image_edit_with_reference_images", "image_edit_with_mask"}
    )
