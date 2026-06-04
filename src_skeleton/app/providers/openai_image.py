from __future__ import annotations

import asyncio

from app.config import settings
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError, ProviderRateLimitError, ProviderRuntimeError


_openai_image_generation_lock = asyncio.Lock()


class OpenAIGPTImageProvider:
    name = "openai_gpt_image"

    def __init__(self, model: str | None = None):
        self.model = model

    async def capabilities(self) -> ProviderCapabilities:
        configured = bool(settings.openai_api_key)
        return ProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[self._model()],
            operations=["generate"],
            limits={
                "max_batch": 10,
                "formats": ["png", "jpeg", "webp"],
                "sizes": ["1024x1024", "1024x1536", "1536x1024", "auto"],
                "qualities": ["auto", "low", "medium", "high"],
            },
            reason=None if configured else "OPENAI_API_KEY is not configured.",
        )

    async def generate(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not settings.openai_api_key:
            raise ProviderNotConfiguredError("OPENAI_API_KEY is not configured.", provider=self.name)
        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError as exc:
            raise ProviderNotConfiguredError("The openai package is not installed.", provider=self.name) from exc

        plan = request.prompt_plan
        prompt = self._render_prompt(plan)
        client_kwargs = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        client = AsyncOpenAI(**client_kwargs)
        output_count = plan.count
        outputs = []
        # The upstream image gateway may enforce account-level concurrency. Keep
        # image requests serialized in this process so the UI waits in a local
        # queue instead of immediately tripping a provider-side 429.
        async with _openai_image_generation_lock:
            for index in range(output_count):
                outputs.extend(await self._generate_one(client, prompt, plan, index=index))
                if len(outputs) >= output_count:
                    break
        outputs = outputs[:output_count]
        return ImageGenerationResult(
            provider=self.name,
            model=self._model(),
            outputs=outputs,
            raw_response_summary={"output_count": len(outputs), "requests": output_count},
        )

    async def _generate_one(self, client, prompt: str, plan, *, index: int) -> list[dict]:
        max_attempts = 6
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.images.generate(
                    model=self._model(),
                    prompt=prompt,
                    n=1,
                    size=plan.size,
                    quality=plan.quality,
                    output_format=plan.output_format,
                )
                break
            except Exception as exc:
                last_error = exc
                retryable = self._is_retryable_error(exc)
                if attempt >= max_attempts or not retryable:
                    error_cls = ProviderRateLimitError if self._is_concurrency_limit_error(exc) else ProviderRuntimeError
                    raise error_cls(
                        "OpenAI image generation failed.",
                        provider=self.name,
                        detail={
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                            "request_index": index,
                            "attempts": attempt,
                            "retryable": retryable,
                            "upstream_concurrency_limited": self._is_concurrency_limit_error(exc),
                        },
                    ) from exc
                await asyncio.sleep(self._retry_delay_seconds(exc, attempt))
        else:
            raise ProviderRuntimeError(
                "OpenAI image generation failed.",
                provider=self.name,
                detail={"error_type": type(last_error).__name__, "message": str(last_error), "request_index": index},
            )
        outputs: list[dict] = []
        for item in response.data:
            b64_json = getattr(item, "b64_json", None)
            if not b64_json:
                raise ProviderRuntimeError("OpenAI response did not include image bytes.", provider=self.name)
            outputs.append(
                {
                    "b64_json": b64_json,
                    "mime_type": f"image/{plan.output_format}",
                    "format": plan.output_format,
                    "width": self._parse_size(plan.size)[0],
                    "height": self._parse_size(plan.size)[1],
                    "request_index": index,
                }
            )
        return outputs

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        raise ProviderNotConfiguredError(
            "OpenAI image edit requires stored input images or Responses API image context; use mock mode until asset file_id handling is wired.",
            provider=self.name,
        )

    async def estimate_cost(self, request: ImageGenerationRequest) -> CostEstimate:
        return CostEstimate(
            provider=self.name,
            model=self._model(),
            estimated_cost=0.0,
            detail={
                "note": "Use the OpenAI image generation calculator for production cost estimates.",
                "count": request.prompt_plan.count,
                "quality": request.prompt_plan.quality,
                "size": request.prompt_plan.size,
            },
        )

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
        return "\n".join(p for p in parts if p.strip())

    def _parse_size(self, size: str) -> tuple[int | None, int | None]:
        try:
            width, height = size.lower().split("x", 1)
            return int(width), int(height)
        except (AttributeError, ValueError):
            return None, None

    def _is_retryable_error(self, exc: Exception) -> bool:
        status_code = getattr(exc, "status_code", None)
        if status_code in {408, 429, 500, 502, 503, 504}:
            return True
        message = str(exc).lower()
        retryable_markers = [
            "upstream_error",
            "temporarily unavailable",
            "concurrency limit exceeded",
            "rate_limit_error",
            "timeout",
            "timed out",
            "connection error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
        ]
        return any(marker in message for marker in retryable_markers)

    def _is_concurrency_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "concurrency limit exceeded" in message or ("rate_limit_error" in message and "429" in message)

    def _retry_delay_seconds(self, exc: Exception, attempt: int) -> float:
        if self._is_concurrency_limit_error(exc):
            return min(12.0 * attempt, 60.0)
        return 1.5 * attempt

    def _model(self) -> str:
        return self.model or settings.openai_image_model
