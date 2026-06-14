from __future__ import annotations

import asyncio
import math
import re
import time
from collections import deque
from contextlib import ExitStack
from email.utils import parsedate_to_datetime
from typing import Any

from app.config import settings
from app.providers.images.base import (
    V2ImageProviderCapabilities,
    V2ImageProviderNotConfiguredError,
    V2ImageProviderOutput,
    V2ImageProviderRateLimitError,
    V2ImageProviderRequest,
    V2ImageProviderResult,
    V2ImageProviderRuntimeError,
)
from app.providers.images.response_payloads import outputs_from_image_response
from app.services.uploaded_assets import uploaded_asset_path


_openai_generation_lock = asyncio.Lock()
_OPENAI_TRANSIENT_MAX_ATTEMPTS = 3
_OPENAI_TRANSIENT_BASE_DELAY_SECONDS = 1.5


class _V2OpenAIImageRateLimiter:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._request_times: deque[float] = deque()
        self._output_times: deque[float] = deque()
        self._cooldown_until = 0.0
        self._cooldown_reason = ""

    async def acquire(self, *, output_units: int, model: str, trace_id: str | None = None) -> dict[str, Any]:
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
                        "output_units": output_units,
                    }
            if deadline is not None and time.monotonic() + wait_seconds > deadline:
                raise V2ImageProviderRateLimitError(
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


_openai_image_rate_limiter = _V2OpenAIImageRateLimiter()


class V2OpenAIGPTImage2Provider:
    name = "openai_gpt_image"

    async def capabilities(self) -> V2ImageProviderCapabilities:
        configured = bool(settings.openai_api_key)
        return V2ImageProviderCapabilities(
            provider=self.name,
            configured=configured,
            models=[settings.openai_image_model],
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
                "max_batch": 8,
                "max_reference_images": 5,
                "local_max_requests_per_minute": settings.openai_image_local_max_requests_per_minute,
                "local_max_outputs_per_minute": settings.openai_image_local_max_outputs_per_minute,
                "local_queue_timeout_seconds": settings.openai_image_local_queue_timeout_seconds,
                "upstream_cooldown_seconds": settings.openai_image_upstream_cooldown_seconds,
                "max_retry_after_seconds": settings.openai_image_max_retry_after_seconds,
            },
            reason=None if configured else "V2_OPENAI_API_KEY is not configured.",
        )

    async def generate(self, request: V2ImageProviderRequest) -> V2ImageProviderResult:
        if not settings.openai_api_key:
            raise V2ImageProviderNotConfiguredError("V2_OPENAI_API_KEY is not configured.", provider=self.name)
        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError as exc:
            raise V2ImageProviderNotConfiguredError("The openai package is not installed.", provider=self.name) from exc

        client_kwargs: dict[str, Any] = {"api_key": settings.openai_api_key}
        if settings.openai_base_url:
            client_kwargs["base_url"] = settings.openai_base_url
        client = AsyncOpenAI(**client_kwargs)
        reference_paths = _reference_paths(request)
        count = _count(request.prompt_plan)
        outputs: list[V2ImageProviderOutput] = []
        async with _openai_generation_lock:
            for index in range(count):
                if reference_paths:
                    outputs.extend(await self._generate_one_with_references(client, request, reference_paths, index=index))
                else:
                    outputs.extend(await self._generate_one(client, request, index=index))
                if len(outputs) >= count:
                    break
        return V2ImageProviderResult(
            provider=self.name,
            model=settings.openai_image_model,
            outputs=outputs[:count],
            raw_response_summary={
                "output_count": min(len(outputs), count),
                "native_v2": True,
                "reference_image_count": len(reference_paths),
            },
        )

    async def _generate_one(self, client, request: V2ImageProviderRequest, *, index: int) -> list[V2ImageProviderOutput]:
        plan = request.prompt_plan
        rate_guard = None
        try:
            rate_guard = await _openai_image_rate_limiter.acquire(
                output_units=1,
                model=settings.openai_image_model,
                trace_id=request.run_id,
            )
            kwargs = _openai_image_kwargs(plan)
            response = await _call_openai_image_operation(
                lambda: client.images.generate(
                    model=settings.openai_image_model,
                    prompt=_prompt(plan),
                    n=1,
                    timeout=settings.openai_image_timeout_seconds,
                    **kwargs,
                )
            )
        except V2ImageProviderRateLimitError:
            raise
        except Exception as exc:
            if _is_image_quota_limit(exc):
                retry_after = _retry_after_seconds_from_exception(exc)
                cooldown = _openai_image_rate_limiter.note_upstream_image_quota_limit(
                    retry_after_seconds=retry_after,
                    reason=str(exc),
                )
                raise V2ImageProviderRateLimitError(
                    "OpenAI image quota is rate limited; local cooldown is active.",
                    provider=self.name,
                    detail={
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:1000],
                        "operation": "images.generate",
                        "request_index": index,
                        "rate_limit_scope": "openai_image_input_images_per_minute",
                        "retry_after_seconds": cooldown,
                        "upstream_retry_after_seconds": retry_after,
                        "local_rate_guard": rate_guard,
                    },
                ) from exc
            raise _openai_error(exc, provider=self.name, operation="images.generate", index=index) from exc
        return await _outputs_from_openai_response(response, plan, index=index, operation="images.generate", reference_count=0)

    async def _generate_one_with_references(
        self,
        client,
        request: V2ImageProviderRequest,
        reference_paths: list,
        *,
        index: int,
    ) -> list[V2ImageProviderOutput]:
        plan = request.prompt_plan
        rate_guard = None
        try:
            rate_guard = await _openai_image_rate_limiter.acquire(
                output_units=max(1, len(reference_paths)),
                model=settings.openai_image_model,
                trace_id=request.run_id,
            )
            with ExitStack() as stack:
                image_files = [stack.enter_context(path.open("rb")) for path in reference_paths]
                kwargs = _openai_image_kwargs(plan)
                async def edit_operation():
                    for image_file in image_files:
                        image_file.seek(0)
                    return await client.images.edit(
                        model=settings.openai_image_model,
                        image=image_files,
                        prompt=_prompt(plan),
                        n=1,
                        timeout=settings.openai_image_timeout_seconds,
                        **kwargs,
                    )

                response = await _call_openai_image_operation(
                    edit_operation
                )
        except V2ImageProviderRateLimitError:
            raise
        except Exception as exc:
            if _is_image_quota_limit(exc):
                retry_after = _retry_after_seconds_from_exception(exc)
                cooldown = _openai_image_rate_limiter.note_upstream_image_quota_limit(
                    retry_after_seconds=retry_after,
                    reason=str(exc),
                )
                raise V2ImageProviderRateLimitError(
                    "OpenAI image quota is rate limited; local cooldown is active.",
                    provider=self.name,
                    detail={
                        "error_type": type(exc).__name__,
                        "message": str(exc)[:1000],
                        "operation": "images.edit",
                        "request_index": index,
                        "rate_limit_scope": "openai_image_input_images_per_minute",
                        "retry_after_seconds": cooldown,
                        "upstream_retry_after_seconds": retry_after,
                        "local_rate_guard": rate_guard,
                        "reference_image_count": len(reference_paths),
                    },
                ) from exc
            raise _openai_error(exc, provider=self.name, operation="images.edit", index=index) from exc
        return await _outputs_from_openai_response(
            response,
            plan,
            index=index,
            operation="images.edit",
            reference_count=len(reference_paths),
        )


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
                provider="openai_gpt_image",
                detail={"asset_id": image.asset_id, "role": image.role},
            )
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


async def _outputs_from_openai_response(response, plan, *, index: int, operation: str, reference_count: int) -> list[V2ImageProviderOutput]:
    fmt = _output_format(plan)
    return await outputs_from_image_response(
        response,
        plan,
        provider="openai_gpt_image",
        missing_message="OpenAI image response did not include image bytes.",
        index=index,
        operation=operation,
        reference_count=reference_count,
        default_format=fmt,
        default_mime_type=f"image/{fmt}",
        url_timeout_seconds=settings.openai_image_timeout_seconds,
    )


def _openai_error(exc: Exception, *, provider: str, operation: str, index: int):
    message = str(exc)
    retryable = _is_retryable_openai_error(exc)
    detail = {
        "error_type": type(exc).__name__,
        "message": message[:1000],
        "operation": operation,
        "request_index": index,
        "retryable": retryable,
    }
    if _is_rate_limit(exc):
        return V2ImageProviderRateLimitError("OpenAI image request is rate limited.", provider=provider, detail=detail)
    return V2ImageProviderRuntimeError(
        "OpenAI image request failed.",
        provider=provider,
        detail=detail,
        retryable=retryable,
    )


async def _call_openai_image_operation(operation):
    last_error: Exception | None = None
    timeout = max(1.0, float(settings.openai_image_timeout_seconds))
    for attempt in range(1, _OPENAI_TRANSIENT_MAX_ATTEMPTS + 1):
        try:
            return await asyncio.wait_for(operation(), timeout=timeout)
        except TimeoutError as exc:
            last_error = exc
            if attempt >= _OPENAI_TRANSIENT_MAX_ATTEMPTS:
                raise
            await asyncio.sleep(_openai_transient_retry_delay(attempt, exc))
        except Exception as exc:
            last_error = exc
            if _is_image_quota_limit(exc):
                raise
            if attempt >= _OPENAI_TRANSIENT_MAX_ATTEMPTS or not _is_retryable_openai_error(exc):
                raise
            await asyncio.sleep(_openai_transient_retry_delay(attempt, exc))
    if last_error:
        raise last_error
    raise RuntimeError("OpenAI image operation did not run.")


def _openai_transient_retry_delay(attempt: int, exc: Exception) -> float:
    retry_after = _retry_after_seconds_from_exception(exc)
    if retry_after is not None:
        return min(max(retry_after, 0.5), 8.0)
    return min(_OPENAI_TRANSIENT_BASE_DELAY_SECONDS * attempt, 6.0)


def _is_retryable_openai_error(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code in {408, 409, 425, 429, 500, 502, 503, 504}:
        return True
    message = str(exc).lower()
    retryable_markers = [
        "502 bad gateway",
        "503 service unavailable",
        "504 gateway timeout",
        "bad gateway",
        "gateway timeout",
        "internal server error",
        "server error",
        "temporarily unavailable",
        "connection reset",
        "connection aborted",
        "timeout",
        "timed out",
    ]
    return any(marker in message for marker in retryable_markers)


def _is_rate_limit(exc: Exception) -> bool:
    status_code = getattr(exc, "status_code", None)
    if status_code == 429:
        return True
    message = str(exc).lower()
    return "rate limit" in message or "input-images per min" in message or "input images per min" in message


def _is_image_quota_limit(exc: Exception) -> bool:
    message = str(exc).lower()
    markers = [
        "input-images per min",
        "input images per min",
        "rate limit reached for gpt-image",
        "rate limit reached for gpt_image",
        "gpt-image-2-codex",
    ]
    return any(marker in message for marker in markers)


def _retry_after_seconds_from_exception(exc: Exception) -> float | None:
    headers = _headers_from_exception(exc)
    retry_after = None
    if headers:
        try:
            retry_after = headers.get("retry-after") or headers.get("Retry-After")
        except AttributeError:
            retry_after = None
    parsed = _parse_retry_after(retry_after)
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


def _headers_from_exception(exc: Exception):
    response = getattr(exc, "response", None)
    headers = getattr(response, "headers", None)
    if headers:
        return headers
    return getattr(exc, "headers", None)


def _parse_retry_after(value) -> float | None:
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


def _prompt(plan) -> str:
    return str(plan.user_variables.get("generation_prompt") or plan.prompt)


def _count(plan) -> int:
    try:
        value = int(plan.provider_parameters.get("count", 1))
    except Exception:
        value = 1
    return max(1, min(value, 8))


def _openai_image_kwargs(plan) -> dict[str, str]:
    kwargs = {
        "quality": _quality(plan),
        "output_format": _output_format(plan),
    }
    size = _size(plan)
    if size:
        kwargs["size"] = size
    return kwargs


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


def _dimensions(plan) -> tuple[int | None, int | None]:
    try:
        size = _size(plan)
        if not size:
            return None, None
        width, height = size.lower().split("x", 1)
        return int(width), int(height)
    except (AttributeError, ValueError):
        return None, None


def _quality(plan) -> str:
    quality = str((plan.provider_parameters or {}).get("quality") or "high")
    return quality if quality in {"auto", "low", "medium", "high"} else "high"


def _output_format(plan) -> str:
    fmt = str((plan.provider_parameters or {}).get("output_format") or "png").lower()
    return fmt if fmt in {"png", "jpeg", "webp"} else "png"
