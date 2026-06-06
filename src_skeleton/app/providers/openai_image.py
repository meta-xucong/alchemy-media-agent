from __future__ import annotations

import asyncio
import math
import re
import time
from contextlib import ExitStack
from collections import deque
from email.utils import parsedate_to_datetime

from app.config import settings
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError, ProviderRateLimitError, ProviderRuntimeError
from app.services.asset_planning import reference_image_paths


_openai_image_generation_lock = asyncio.Lock()


class _OpenAIImageRateLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._request_times: deque[float] = deque()
        self._output_times: deque[float] = deque()
        self._cooldown_until = 0.0
        self._cooldown_reason = ""

    async def acquire(self, *, output_units: int, model: str, trace_id: str | None = None) -> dict:
        output_units = max(1, int(output_units))
        timeout = max(0.0, float(settings.openai_image_local_queue_timeout_seconds))
        deadline = time.monotonic() + timeout if timeout else None
        total_wait = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                self._prune(now)
                wait_seconds, reason = self._wait_seconds(now, output_units)
                if wait_seconds <= 0:
                    self._request_times.append(now)
                    for _ in range(output_units):
                        self._output_times.append(now)
                    return {
                        "local_wait_seconds": round(total_wait, 3),
                        "local_requests_per_minute": self._request_limit(),
                        "local_outputs_per_minute": self._output_limit(output_units),
                    }
            if deadline is not None and time.monotonic() + wait_seconds > deadline:
                raise ProviderRateLimitError(
                    "OpenAI image local rate guard is cooling down.",
                    provider="openai_gpt_image",
                    detail={
                        "rate_limit_scope": reason,
                        "model": model,
                        "trace_id": trace_id,
                        "retry_after_seconds": math.ceil(wait_seconds),
                        "local_queue_timeout_seconds": timeout,
                        "cooldown_reason": self._cooldown_reason,
                    },
                )
            sleep_for = min(max(wait_seconds, 0.1), 15.0)
            total_wait += sleep_for
            await asyncio.sleep(sleep_for)

    def note_upstream_image_quota_limit(self, *, retry_after_seconds: float | None, reason: str) -> int:
        fallback_cooldown = max(1.0, float(settings.openai_image_upstream_cooldown_seconds))
        requested = retry_after_seconds if retry_after_seconds and retry_after_seconds > 0 else fallback_cooldown
        cooldown = min(max(requested, fallback_cooldown), max(1.0, float(settings.openai_image_max_retry_after_seconds)))
        now = time.monotonic()
        self._cooldown_until = max(self._cooldown_until, now + cooldown)
        self._cooldown_reason = reason[:500]
        return math.ceil(cooldown)

    def reset(self) -> None:
        self._request_times.clear()
        self._output_times.clear()
        self._cooldown_until = 0.0
        self._cooldown_reason = ""

    def _wait_seconds(self, now: float, output_units: int) -> tuple[float, str]:
        wait_seconds = 0.0
        reason = "local_openai_image_rate_limit"
        if self._cooldown_until > now:
            wait_seconds = max(wait_seconds, self._cooldown_until - now)
            reason = "upstream_openai_image_rate_limit_cooldown"
        request_limit = self._request_limit()
        if len(self._request_times) >= request_limit:
            wait_seconds = max(wait_seconds, 60.0 - (now - self._request_times[0]))
            reason = "local_openai_image_requests_per_minute"
        output_limit = self._output_limit(output_units)
        if len(self._output_times) + output_units > output_limit:
            wait_seconds = max(wait_seconds, 60.0 - (now - self._output_times[0]))
            reason = "local_openai_image_outputs_per_minute"
        return max(0.0, wait_seconds), reason

    def _prune(self, now: float) -> None:
        threshold = now - 60.0
        while self._request_times and self._request_times[0] <= threshold:
            self._request_times.popleft()
        while self._output_times and self._output_times[0] <= threshold:
            self._output_times.popleft()

    def _request_limit(self) -> int:
        return max(1, int(settings.openai_image_local_max_requests_per_minute))

    def _output_limit(self, output_units: int) -> int:
        return max(output_units, int(settings.openai_image_local_max_outputs_per_minute))


_openai_image_rate_limiter = _OpenAIImageRateLimiter()


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
            operations=["generate", "image_reference"],
            advanced_asset_roles=[
                "style_reference",
                "subject_reference",
                "logo_overlay",
                "portrait_identity",
                "background_reference",
                "composition_reference",
            ],
            model_capabilities=[
                {
                    "id": self._model(),
                    "capabilities": ["text_to_image", "image_reference"],
                    "advanced_asset_roles": [
                        "style_reference",
                        "subject_reference",
                        "logo_overlay",
                        "portrait_identity",
                        "background_reference",
                        "composition_reference",
                    ],
                }
            ],
            limits={
                "max_batch": 10,
                "max_reference_images": 5,
                "formats": ["png", "jpeg", "webp"],
                "sizes": ["1024x1024", "1024x1536", "1536x1024", "auto"],
                "qualities": ["auto", "low", "medium", "high"],
                "local_max_requests_per_minute": settings.openai_image_local_max_requests_per_minute,
                "local_max_outputs_per_minute": settings.openai_image_local_max_outputs_per_minute,
                "local_queue_timeout_seconds": settings.openai_image_local_queue_timeout_seconds,
                "upstream_cooldown_seconds": settings.openai_image_upstream_cooldown_seconds,
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
        asset_plan = request.asset_plan or (plan.variables.get("asset_plan") if getattr(plan, "variables", None) else None)
        reference_paths = reference_image_paths(asset_plan, max_images=5)
        # The upstream image gateway may enforce account-level concurrency. Keep
        # image requests serialized in this process so the UI waits in a local
        # queue instead of immediately tripping a provider-side 429.
        async with _openai_image_generation_lock:
            for index in range(output_count):
                if reference_paths:
                    outputs.extend(await self._generate_one_with_references(client, prompt, plan, reference_paths, index=index))
                else:
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
                rate_guard = await _openai_image_rate_limiter.acquire(
                    output_units=1,
                    model=self._model(),
                )
                response = await client.images.generate(
                    model=self._model(),
                    prompt=prompt,
                    n=1,
                    size=plan.size,
                    quality=plan.quality,
                    output_format=plan.output_format,
                )
                break
            except ProviderRateLimitError:
                raise
            except Exception as exc:
                last_error = exc
                if self._is_image_quota_limit_error(exc):
                    retry_after = self._retry_after_seconds_from_exception(exc)
                    cooldown = _openai_image_rate_limiter.note_upstream_image_quota_limit(
                        retry_after_seconds=retry_after,
                        reason=str(exc),
                    )
                    raise ProviderRateLimitError(
                        "OpenAI image quota is rate limited; local cooldown is active.",
                        provider=self.name,
                        detail={
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                            "request_index": index,
                            "attempts": attempt,
                            "retryable": True,
                            "rate_limit_scope": "openai_image_input_images_per_minute",
                            "retry_after_seconds": cooldown,
                            "upstream_retry_after_seconds": retry_after,
                            "local_rate_guard": rate_guard,
                        },
                    ) from exc
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
                            "upstream_image_quota_limited": self._is_image_quota_limit_error(exc),
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

    async def _generate_one_with_references(self, client, prompt: str, plan, reference_paths: list, *, index: int) -> list[dict]:
        max_attempts = 6
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            rate_guard = None
            try:
                # OpenAI image rate limits count input images separately for
                # reference/edit requests. Use the existing local guard with at
                # least the number of input images as the consumed unit.
                rate_guard = await _openai_image_rate_limiter.acquire(
                    output_units=max(1, len(reference_paths)),
                    model=self._model(),
                )
                with ExitStack() as stack:
                    image_files = [stack.enter_context(path.open("rb")) for path in reference_paths]
                    response = await client.images.edit(
                        model=self._model(),
                        image=image_files,
                        prompt=prompt,
                        n=1,
                        size=plan.size,
                        quality=plan.quality,
                        output_format=plan.output_format,
                    )
                break
            except ProviderRateLimitError:
                raise
            except Exception as exc:
                last_error = exc
                if self._is_image_quota_limit_error(exc):
                    retry_after = self._retry_after_seconds_from_exception(exc)
                    cooldown = _openai_image_rate_limiter.note_upstream_image_quota_limit(
                        retry_after_seconds=retry_after,
                        reason=str(exc),
                    )
                    raise ProviderRateLimitError(
                        "OpenAI image quota is rate limited; local cooldown is active.",
                        provider=self.name,
                        detail={
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                            "request_index": index,
                            "attempts": attempt,
                            "retryable": True,
                            "rate_limit_scope": "openai_image_input_images_per_minute",
                            "retry_after_seconds": cooldown,
                            "upstream_retry_after_seconds": retry_after,
                            "local_rate_guard": rate_guard,
                            "reference_image_count": len(reference_paths),
                        },
                    ) from exc
                retryable = self._is_retryable_error(exc)
                if attempt >= max_attempts or not retryable:
                    error_cls = ProviderRateLimitError if self._is_concurrency_limit_error(exc) else ProviderRuntimeError
                    raise error_cls(
                        "OpenAI image reference generation failed.",
                        provider=self.name,
                        detail={
                            "error_type": type(exc).__name__,
                            "message": str(exc),
                            "request_index": index,
                            "attempts": attempt,
                            "retryable": retryable,
                            "reference_image_count": len(reference_paths),
                            "upstream_concurrency_limited": self._is_concurrency_limit_error(exc),
                            "upstream_image_quota_limited": self._is_image_quota_limit_error(exc),
                        },
                    ) from exc
                await asyncio.sleep(self._retry_delay_seconds(exc, attempt))
        else:
            raise ProviderRuntimeError(
                "OpenAI image reference generation failed.",
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
                    "reference_image_count": len(reference_paths),
                    "api_operation": "images.edit",
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
            "rate limit reached",
            "input-images per min",
            "input images per min",
        ]
        return any(marker in message for marker in retryable_markers)

    def _is_concurrency_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        return "concurrency limit exceeded" in message or ("rate_limit_error" in message and "429" in message)

    def _is_image_quota_limit_error(self, exc: Exception) -> bool:
        message = str(exc).lower()
        markers = [
            "input-images per min",
            "input images per min",
            "rate limit reached for gpt-image",
            "rate limit reached for gpt_image",
            "gpt-image-2-codex",
        ]
        return any(marker in message for marker in markers)

    def _retry_delay_seconds(self, exc: Exception, attempt: int) -> float:
        if self._is_image_quota_limit_error(exc):
            retry_after = self._retry_after_seconds_from_exception(exc)
            if retry_after is not None:
                return min(retry_after, settings.openai_image_max_retry_after_seconds)
            return min(settings.openai_image_upstream_cooldown_seconds, settings.openai_image_max_retry_after_seconds)
        if self._is_concurrency_limit_error(exc):
            return min(12.0 * attempt, 60.0)
        return 1.5 * attempt

    def _retry_after_seconds_from_exception(self, exc: Exception) -> float | None:
        headers = self._headers_from_exception(exc)
        retry_after = None
        if headers:
            try:
                retry_after = headers.get("retry-after") or headers.get("Retry-After")
            except AttributeError:
                retry_after = None
        parsed = self._parse_retry_after(retry_after)
        if parsed is not None:
            return parsed
        message = str(exc)
        for pattern in [
            r"retry[- ]after[:= ]+([0-9]+(?:\.[0-9]+)?)",
            r"try again in ([0-9]+(?:\.[0-9]+)?)s",
            r"try again in ([0-9]+(?:\.[0-9]+)?) seconds",
        ]:
            match = re.search(pattern, message, flags=re.IGNORECASE)
            if match:
                return max(0.0, float(match.group(1)))
        return None

    def _headers_from_exception(self, exc: Exception):
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if headers:
            return headers
        return getattr(exc, "headers", None)

    def _parse_retry_after(self, value) -> float | None:
        if value is None:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return max(0.0, float(raw))
        except ValueError:
            pass
        try:
            parsed = parsedate_to_datetime(raw)
        except (TypeError, ValueError):
            return None
        return max(0.0, parsed.timestamp() - time.time())

    def _model(self) -> str:
        return self.model or settings.openai_image_model
