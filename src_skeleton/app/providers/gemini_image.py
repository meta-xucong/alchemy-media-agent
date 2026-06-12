from __future__ import annotations

import asyncio
import base64
import math
import mimetypes
from urllib.parse import quote
from typing import Any

import httpx

from app.config import settings
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError, ProviderRuntimeError
from app.services.asset_planning import reference_image_paths


_gemini_image_generation_lock = asyncio.Lock()


class GeminiImageProvider:
    name = "gemini_image"

    async def capabilities(self) -> ProviderCapabilities:
        configured = bool(settings.gemini_image_api_key) and settings.gemini_image_generation_enabled
        reason = None
        if not settings.gemini_image_generation_enabled:
            reason = "Gemini image generation is temporarily disabled."
        elif not settings.gemini_image_api_key:
            reason = "GEMINI_IMAGE_API_KEY or GEMINI_API_KEY is not configured."
        return ProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.gemini_image_model],
            operations=["generate", "image_reference"],
            advanced_asset_roles=[
                "style_reference",
                "subject_reference",
                "logo_overlay",
                "background_reference",
                "composition_reference",
            ],
            model_capabilities=[
                {
                    "id": settings.gemini_image_model,
                    "capabilities": ["text_to_image", "image_reference"],
                    "advanced_asset_roles": [
                        "style_reference",
                        "subject_reference",
                        "logo_overlay",
                        "background_reference",
                        "composition_reference",
                    ],
                }
            ],
            limits={
                "max_batch": 4,
                "max_reference_images": 3,
                "formats": ["png", "jpeg", "webp"],
                "aspect_ratios": ["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"],
                "image_sizes": ["1K", "2K", "4K"],
                "api_key_configured": bool(settings.gemini_image_api_key),
                "base_url_configured": bool(settings.gemini_image_base_url),
                "temporarily_disabled": not settings.gemini_image_generation_enabled,
            },
            reason=reason,
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not settings.gemini_image_generation_enabled:
            raise ProviderNotConfiguredError("Gemini image generation is temporarily disabled.", provider=self.name)
        if not settings.gemini_image_api_key:
            raise ProviderNotConfiguredError("GEMINI_IMAGE_API_KEY or GEMINI_API_KEY is not configured.", provider=self.name)
        plan = request.prompt_plan
        prompt = self._render_prompt(plan)
        asset_plan = request.asset_plan or (plan.variables.get("asset_plan") if getattr(plan, "variables", None) else None)
        reference_paths = reference_image_paths(asset_plan, max_images=3)
        outputs: list[dict[str, Any]] = []
        request_count = max(1, min(plan.count, 4))
        async with _gemini_image_generation_lock:
            for index in range(request_count):
                outputs.extend(await self._generate_one(prompt, plan, reference_paths, index=index))
                if len(outputs) >= request_count:
                    break
        outputs = outputs[:request_count]
        return ImageGenerationResult(
            provider=self.name,
            model=settings.gemini_image_model,
            outputs=outputs,
            raw_response_summary={"output_count": len(outputs), "requests": request_count, "api_style": "gemini_generate_content"},
        )

    async def _generate_one(self, prompt: str, plan, reference_paths: list | None = None, *, index: int) -> list[dict[str, Any]]:
        payload = self._payload(prompt, plan, reference_paths or [])
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": settings.gemini_image_api_key or "",
        }
        timeout = httpx.Timeout(300.0, connect=30.0)
        attempts: list[dict[str, Any]] = []
        data: dict[str, Any] | None = None
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response: httpx.Response | None = None
            for url, model in self._generate_content_candidates():
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
            else:
                response = None
        if response is None or data is None:
            raise ProviderRuntimeError(
                "Gemini image generation request failed.",
                provider=self.name,
                detail={"request_index": index, "attempts": attempts[-4:]},
            )
        if response.status_code >= 400:
            raise ProviderRuntimeError(
                "Gemini image generation returned an error.",
                provider=self.name,
                detail={"status_code": response.status_code, "body": response.text[:1200], "request_index": index, "attempts": attempts[-4:]},
            )
        outputs = self._extract_outputs(data, plan, index=index)
        if not outputs:
            raise ProviderRuntimeError(
                "Gemini response did not include image bytes.",
                provider=self.name,
                detail={"request_index": index, "response_keys": sorted(data.keys())[:12]},
            )
        return outputs

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise ProviderNotConfiguredError(
            "Gemini image edit requires passing stored input images into generateContent; text-to-image is wired first.",
            provider=self.name,
        )

    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate:
        return CostEstimate(
            provider=self.name,
            model=settings.gemini_image_model,
            estimated_cost=0.0,
            detail={
                "note": "Use Gemini API image pricing for production cost estimates.",
                "count": request.prompt_plan.count,
                "quality": request.prompt_plan.quality,
                "size": request.prompt_plan.size,
            },
        )

    def _generate_content_candidates(self) -> list[tuple[str, str]]:
        roots = self._api_roots()
        models = self._model_candidates(settings.gemini_image_model)
        encoded_key = quote(settings.gemini_image_api_key or "", safe="")
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

    def _api_roots(self) -> list[str]:
        configured = settings.gemini_image_base_url
        if not configured:
            return ["https://generativelanguage.googleapis.com/v1"]
        base_url = configured.rstrip("/")
        roots = [base_url]
        if not (base_url.endswith("/v1") or base_url.endswith("/v1beta")):
            if "generativelanguage.googleapis.com" in base_url:
                roots.append(f"{base_url}/v1")
                roots.append(f"{base_url}/v1beta")
            else:
                roots.append(f"{base_url}/v1beta")
                roots.append(f"{base_url}/v1")
        return roots

    def _model_candidates(self, model: str) -> list[str]:
        models = [model]
        if model == "gemini-3-pro-image-preview":
            models.append("gemini-3-pro-image")
        elif model == "gemini-3-pro-image":
            models.append("gemini-3-pro-image-preview")
        return models

    def _payload(self, prompt: str, plan, reference_paths: list) -> dict[str, Any]:
        aspect_ratio = self._aspect_ratio(plan.size)
        image_config: dict[str, Any] = {}
        if aspect_ratio:
            image_config["aspectRatio"] = aspect_ratio
        if self._supports_image_size(settings.gemini_image_model):
            image_config["imageSize"] = self._image_size(plan.quality)
        parts: list[dict[str, Any]] = [{"text": prompt}]
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

    def _extract_outputs(self, data: dict[str, Any], plan, *, index: int) -> list[dict[str, Any]]:
        openai_outputs = self._extract_openai_style_outputs(data, plan, index=index)
        if openai_outputs:
            return openai_outputs
        outputs: list[dict[str, Any]] = []
        for candidate in data.get("candidates", []) or []:
            content = candidate.get("content", {}) if isinstance(candidate, dict) else {}
            for part in content.get("parts", []) or []:
                inline_data = part.get("inlineData") or part.get("inline_data") if isinstance(part, dict) else None
                if not inline_data:
                    continue
                encoded = inline_data.get("data")
                if not encoded:
                    continue
                mime_type = inline_data.get("mimeType") or inline_data.get("mime_type") or f"image/{plan.output_format}"
                output_format = self._format_from_mime(mime_type, plan.output_format)
                width, height = self._dimensions_for_plan(plan)
                outputs.append(
                    {
                        "b64_json": encoded,
                        "mime_type": mime_type,
                        "format": output_format,
                        "width": width,
                        "height": height,
                        "request_index": index,
                    }
                )
        return outputs

    def _extract_openai_style_outputs(self, data: dict[str, Any], plan, *, index: int) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        for item in data.get("data", []) or []:
            if not isinstance(item, dict):
                continue
            encoded = item.get("b64_json")
            if not encoded and isinstance(item.get("url"), str) and item["url"].startswith("data:image/"):
                encoded = item["url"].split(",", 1)[-1]
            if not encoded:
                continue
            mime_type = item.get("mime_type") or item.get("mimeType") or f"image/{plan.output_format}"
            output_format = self._format_from_mime(mime_type, item.get("format") or plan.output_format)
            outputs.append(
                {
                    "b64_json": encoded,
                    "mime_type": mime_type,
                    "format": output_format,
                    "width": item.get("width") or self._dimensions_for_plan(plan)[0],
                    "height": item.get("height") or self._dimensions_for_plan(plan)[1],
                    "request_index": index,
                }
            )
        return outputs

    def _render_prompt(self, plan) -> str:
        generation_prompt = plan.variables.get("generation_prompt") if getattr(plan, "variables", None) else None
        if generation_prompt:
            return generation_prompt
        parts = [
            f"Main subject: {plan.main_subject}",
            f"Scene: {plan.scene or ''}",
            f"Style: {plan.style or ''}",
            f"Composition: {plan.composition or ''}",
            f"Brand constraints: {', '.join(plan.brand_constraints)}",
            f"Required text: {plan.text}",
            f"Avoid: {', '.join(plan.negative_constraints)}",
        ]
        return "\n".join(part for part in parts if part.strip())

    def _aspect_ratio(self, size: str | None) -> str | None:
        if not size or size == "auto":
            return None
        if ":" in size:
            return size
        try:
            width_text, height_text = size.lower().split("x", 1)
            width = int(width_text)
            height = int(height_text)
        except (AttributeError, ValueError):
            return None
        if width <= 0 or height <= 0:
            return None
        divisor = math.gcd(width, height)
        return f"{width // divisor}:{height // divisor}"

    def _dimensions_for_plan(self, plan) -> tuple[int | None, int | None]:
        if not plan.size or plan.size == "auto" or "x" not in plan.size:
            return None, None
        try:
            width_text, height_text = plan.size.lower().split("x", 1)
            return int(width_text), int(height_text)
        except (AttributeError, ValueError):
            return None, None

    def _image_size(self, quality: str) -> str:
        if quality == "low":
            return "1K"
        if quality == "medium":
            return "1K"
        return "2K"

    def _supports_image_size(self, model: str) -> bool:
        normalized = model.lower()
        return normalized.startswith("gemini-3") or "3-pro-image" in normalized

    def _format_from_mime(self, mime_type: str, fallback: str) -> str:
        normalized = mime_type.lower()
        if "jpeg" in normalized or "jpg" in normalized:
            return "jpeg"
        if "webp" in normalized:
            return "webp"
        if "png" in normalized:
            return "png"
        return fallback if fallback in {"png", "jpeg", "webp"} else "png"
