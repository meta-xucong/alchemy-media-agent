from __future__ import annotations

import asyncio
import base64
import inspect
import math
import re
import threading
import time
from contextlib import ExitStack
from collections import deque
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlparse

import httpx

from app.config import openai_sdk_client_kwargs, settings
from app.schemas import CostEstimate, ImageGenerationRequest, ImageGenerationResult
from app.providers.base import ProviderCapabilities, ProviderNotConfiguredError, ProviderRateLimitError, ProviderRuntimeError
from app.services.asset_planning import reference_image_paths
from app.services.provider_reference import prepare_provider_reference_image, prepare_provider_reference_images
from app.storage import media_store


class _CrossLoopAsyncLock:
    def __init__(self) -> None:
        self._lock = threading.Lock()

    async def __aenter__(self):
        await asyncio.to_thread(self._lock.acquire)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()
        return False


_openai_image_generation_lock = _CrossLoopAsyncLock()


class _ImageEditCapabilityCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._states: dict[str, tuple[str, float, str | None]] = {}

    def state(self, key: str) -> tuple[str, str | None]:
        now = time.monotonic()
        ttl = max(60.0, float(settings.openai_image_input_fidelity_cache_ttl_seconds))
        with self._lock:
            state, checked_at, reason = self._states.get(key, ("unknown", 0.0, None))
            if state == "unsupported" and now - checked_at >= ttl:
                self._states.pop(key, None)
                return "unknown", None
            return state, reason

    def note(self, key: str, state: str, reason: str | None = None) -> None:
        with self._lock:
            self._states[key] = (state, time.monotonic(), reason)

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


_image_edit_capability_cache = _ImageEditCapabilityCache()


class _OpenAIImageRateLimiter:
    def __init__(self) -> None:
        self._lock = _CrossLoopAsyncLock()
        self._request_times: deque[float] = deque()
        self._output_times: deque[float] = deque()
        self._cooldown_until = 0.0
        self._cooldown_reason = ""
        self._edit_cooldown_until = 0.0
        self._edit_cooldown_reason = ""

    async def acquire(
        self,
        *,
        output_units: int,
        model: str,
        trace_id: str | None = None,
        operation: str = "generate",
    ) -> dict:
        output_units = max(1, int(output_units))
        timeout = max(0.0, float(settings.openai_image_local_queue_timeout_seconds))
        deadline = time.monotonic() + timeout if timeout else None
        total_wait = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                self._prune(now)
                wait_seconds, reason = self._wait_seconds(now, output_units, operation=operation)
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
                        "image_edit_cooldown_reason": self._edit_cooldown_reason,
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

    def note_transient_image_edit_failure(self, *, retry_after_seconds: float | None, reason: str) -> int:
        configured = max(0.0, float(settings.openai_image_edit_transient_cooldown_seconds))
        requested = retry_after_seconds if retry_after_seconds and retry_after_seconds > 0 else configured
        cooldown = min(max(0.0, requested), max(0.0, float(settings.openai_image_max_retry_after_seconds)))
        now = time.monotonic()
        self._edit_cooldown_until = max(self._edit_cooldown_until, now + cooldown)
        self._edit_cooldown_reason = reason[:500]
        return math.ceil(cooldown)

    def note_image_edit_success(self) -> None:
        self._edit_cooldown_until = 0.0
        self._edit_cooldown_reason = ""

    def reset(self) -> None:
        self._request_times.clear()
        self._output_times.clear()
        self._cooldown_until = 0.0
        self._cooldown_reason = ""
        self._edit_cooldown_until = 0.0
        self._edit_cooldown_reason = ""

    def _wait_seconds(self, now: float, output_units: int, *, operation: str) -> tuple[float, str]:
        wait_seconds = 0.0
        reason = "local_openai_image_rate_limit"
        if self._cooldown_until > now:
            wait_seconds = max(wait_seconds, self._cooldown_until - now)
            reason = "upstream_openai_image_rate_limit_cooldown"
        if operation == "image_edit" and self._edit_cooldown_until > now:
            wait_seconds = max(wait_seconds, self._edit_cooldown_until - now)
            reason = "upstream_openai_image_edit_transient_cooldown"
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
            operations=["generate", "edit", "image_reference", "image_edit"],
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
                    "capabilities": ["text_to_image", "image_reference", "image_edit"],
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
                "sizes": ["auto", "1024x1024", "1024x1536", "1536x1024", "custom_dimensions"],
                "custom_size": {
                    "min_width": 1024,
                    "min_height": 1024,
                    "max_width": 3840,
                    "max_height": 3840,
                },
                "qualities": ["auto", "low", "medium", "high"],
                "local_max_requests_per_minute": settings.openai_image_local_max_requests_per_minute,
                "local_max_outputs_per_minute": settings.openai_image_local_max_outputs_per_minute,
                "local_queue_timeout_seconds": settings.openai_image_local_queue_timeout_seconds,
                "upstream_cooldown_seconds": settings.openai_image_upstream_cooldown_seconds,
                "request_timeout_seconds": settings.openai_image_request_timeout_seconds,
                "image_edit_request_timeout_seconds": settings.openai_image_edit_request_timeout_seconds,
                "image_edit_transient_cooldown_seconds": settings.openai_image_edit_transient_cooldown_seconds,
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
        output_count = plan.count
        outputs = []
        asset_plan = request.asset_plan or (plan.variables.get("asset_plan") if getattr(plan, "variables", None) else None)
        reference_paths = reference_image_paths(asset_plan, max_images=settings.max_asset_upload_count)
        repair_canvas = self._identity_repair_canvas_path(plan)
        if repair_canvas is not None:
            reference_paths = [repair_canvas, *reference_paths]
        reference_paths = self._provider_reference_paths(reference_paths)
        repair_mask = self._identity_repair_mask_path(plan)
        client = AsyncOpenAI(
            **openai_sdk_client_kwargs(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=self._client_timeout_seconds(image_edit=bool(reference_paths)),
            )
        )
        # The upstream image gateway may enforce account-level concurrency. Keep
        # image requests serialized in this process so the UI waits in a local
        # queue instead of immediately tripping a provider-side 429.
        try:
            async with _openai_image_generation_lock:
                for index in range(output_count):
                    if reference_paths:
                        outputs.extend(
                            await self._generate_one_with_references(
                                client,
                                prompt,
                                plan,
                                reference_paths,
                                index=index,
                                mask_path=repair_mask,
                            )
                        )
                    else:
                        outputs.extend(await self._generate_one(client, prompt, plan, index=index))
                    if len(outputs) >= output_count:
                        break
        finally:
            await self._close_async_client(client)
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
                    operation="generate",
                )
                kwargs = self._image_kwargs(plan)
                response = await self._call_with_timeout(
                    client.images.generate(
                        model=self._model(),
                        prompt=prompt,
                        n=1,
                        **kwargs,
                    ),
                    image_edit=False,
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
        return self._outputs_from_response(response, plan, request_index=index)

    async def _generate_one_with_references(
        self,
        client,
        prompt: str,
        plan,
        reference_paths: list,
        *,
        index: int,
        mask_path=None,
    ) -> list[dict]:
        max_attempts = 6
        last_error: Exception | None = None
        transient_retry_count = 0
        requested_fidelity = self._requested_input_fidelity(plan)
        capability_key = self._input_fidelity_capability_key()
        support_state, cached_reason = _image_edit_capability_cache.state(capability_key)
        applied_fidelity = requested_fidelity if support_state != "unsupported" else None
        fidelity_fallback_reason = cached_reason if applied_fidelity is None and requested_fidelity else None
        operation_timeout = self._client_timeout_seconds(image_edit=True)
        operation_deadline = time.monotonic() + operation_timeout
        for attempt in range(1, max_attempts + 1):
            rate_guard = None
            try:
                remaining_timeout = operation_deadline - time.monotonic()
                if remaining_timeout <= 0:
                    raise TimeoutError(f"OpenAI image edit operation exceeded {operation_timeout:.1f}s")
                # OpenAI image rate limits count input images separately for
                # reference/edit requests. Use the existing local guard with at
                # least the number of input images as the consumed unit.
                rate_guard = await _openai_image_rate_limiter.acquire(
                    output_units=max(1, len(reference_paths)),
                    model=self._model(),
                    operation="image_edit",
                )
                remaining_timeout = operation_deadline - time.monotonic()
                if remaining_timeout <= 0:
                    raise TimeoutError(f"OpenAI image edit operation exceeded {operation_timeout:.1f}s")
                with ExitStack() as stack:
                    image_files = [stack.enter_context(path.open("rb")) for path in reference_paths]
                    kwargs = self._image_kwargs(plan)
                    if applied_fidelity:
                        kwargs["input_fidelity"] = applied_fidelity
                    if mask_path is not None:
                        kwargs["mask"] = stack.enter_context(mask_path.open("rb"))
                    response = await self._call_with_timeout(
                        client.images.edit(
                            model=self._model(),
                            image=image_files,
                            prompt=prompt,
                            n=1,
                            **kwargs,
                        ),
                        image_edit=True,
                        timeout_seconds=max(0.1, remaining_timeout),
                    )
                _openai_image_rate_limiter.note_image_edit_success()
                break
            except ProviderRateLimitError:
                raise
            except Exception as exc:
                last_error = exc
                if applied_fidelity and self._is_input_fidelity_unsupported_error(exc):
                    fidelity_fallback_reason = str(exc)[:240]
                    _image_edit_capability_cache.note(
                        capability_key,
                        "unsupported",
                        fidelity_fallback_reason,
                    )
                    applied_fidelity = None
                    continue
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
                transient_image_edit = self._is_transient_image_edit_error(exc)
                operation_timeout_exhausted = isinstance(exc, (asyncio.TimeoutError, TimeoutError)) and time.monotonic() >= operation_deadline
                retryable = (self._is_retryable_error(exc) or transient_image_edit) and not operation_timeout_exhausted
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
                            "transient_image_edit_failure": transient_image_edit,
                            "operation_timeout_exhausted": operation_timeout_exhausted,
                            "operation_timeout_seconds": operation_timeout,
                            "reference_image_count": len(reference_paths),
                            "upstream_concurrency_limited": self._is_concurrency_limit_error(exc),
                            "upstream_image_quota_limited": self._is_image_quota_limit_error(exc),
                            "status_code": self._status_code_from_exception(exc),
                            "gateway_base_url": self._is_openai_compatible_gateway(),
                        },
                    ) from exc
                if transient_image_edit:
                    transient_retry_count += 1
                    retry_after = self._retry_after_seconds_from_exception(exc)
                    _openai_image_rate_limiter.note_transient_image_edit_failure(
                        retry_after_seconds=retry_after,
                        reason=str(exc),
                    )
                    continue
                await asyncio.sleep(self._retry_delay_seconds(exc, attempt))
        else:
            raise ProviderRuntimeError(
                "OpenAI image reference generation failed.",
                provider=self.name,
                detail={"error_type": type(last_error).__name__, "message": str(last_error), "request_index": index},
            )
        if applied_fidelity:
            _image_edit_capability_cache.note(capability_key, "supported")
            support_state = "supported"
        else:
            support_state, cached_reason = _image_edit_capability_cache.state(capability_key)
            fidelity_fallback_reason = fidelity_fallback_reason or cached_reason
        outputs = self._outputs_from_response(response, plan, request_index=index)
        for output in outputs:
            output["reference_image_count"] = len(reference_paths)
            output["api_operation"] = "images.edit"
            output["image_edit_transient_retries"] = transient_retry_count
            output["input_fidelity_requested"] = requested_fidelity
            output["input_fidelity_applied"] = applied_fidelity
            output["input_fidelity_support_state"] = support_state
            output["input_fidelity_fallback_reason"] = fidelity_fallback_reason
            output["identity_local_repair"] = mask_path is not None
        return outputs

    def _requested_input_fidelity(self, plan) -> str | None:
        variables = getattr(plan, "variables", None)
        value = variables.get("input_fidelity") if isinstance(variables, dict) else None
        normalized = str(value or "").strip().lower()
        return normalized if normalized in {"high", "low"} else None

    def _input_fidelity_capability_key(self) -> str:
        return "|".join(
            [
                str(settings.openai_base_url or "https://api.openai.com/v1").rstrip("/").lower(),
                self.name,
                self._model().lower(),
            ]
        )

    def _is_input_fidelity_unsupported_error(self, exc: Exception) -> bool:
        if self._status_code_from_exception(exc) != 400:
            return False
        message = str(exc).lower().replace("-", "_")
        if "input_fidelity" not in message and "input fidelity" not in message:
            return False
        markers = (
            "unsupported",
            "not supported",
            "unknown parameter",
            "unrecognized",
            "unexpected",
            "extra_forbidden",
            "not permitted",
        )
        return any(marker in message for marker in markers)

    def _identity_repair_canvas_path(self, plan):
        variables = getattr(plan, "variables", None)
        value = variables.get("identity_repair_canvas_path") if isinstance(variables, dict) else None
        if not value:
            return None
        from pathlib import Path

        path = Path(str(value))
        return path if path.exists() and path.is_file() else None

    def _identity_repair_mask_path(self, plan):
        variables = getattr(plan, "variables", None)
        value = variables.get("identity_repair_mask_path") if isinstance(variables, dict) else None
        if not value:
            return None
        from pathlib import Path

        path = Path(str(value))
        return path if path.exists() and path.is_file() else None

    async def edit(self, request: ImageGenerationRequest) -> ImageGenerationResult:
        if not settings.openai_api_key:
            raise ProviderNotConfiguredError("OPENAI_API_KEY is not configured.", provider=self.name)
        if not request.source_output_id:
            raise ProviderRuntimeError(
                "OpenAI image edit requires a stored source output image.",
                provider=self.name,
                detail={"missing": "source_output_id"},
            )
        source = media_store.find_output_file(request.source_output_id)
        if not source:
            raise ProviderRuntimeError(
                "OpenAI image edit source file was not found.",
                provider=self.name,
                detail={"source_output_id": request.source_output_id},
            )
        source_path, source_format, source_job_id = source
        try:
            from openai import AsyncOpenAI
        except ModuleNotFoundError as exc:
            raise ProviderNotConfiguredError("The openai package is not installed.", provider=self.name) from exc

        client = AsyncOpenAI(
            **openai_sdk_client_kwargs(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                timeout=self._client_timeout_seconds(image_edit=True),
            )
        )
        plan = request.prompt_plan
        prompt = self._render_prompt(plan)
        try:
            async with _openai_image_generation_lock:
                outputs = await self._generate_one_with_references(client, prompt, plan, [source_path], index=0)
        finally:
            await self._close_async_client(client)
        outputs = outputs[:1]
        return ImageGenerationResult(
            provider=self.name,
            model=self._model(),
            outputs=outputs,
            raw_response_summary={
                "output_count": len(outputs),
                "requests": 1,
                "api_style": "images.edit",
                "source_output_id": request.source_output_id,
                "source_job_id": source_job_id,
                "source_output_format": source_format,
                "reference_image_count": 1,
            },
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

    def _image_kwargs(self, plan) -> dict[str, str]:
        kwargs = {
            "quality": plan.quality,
            "output_format": plan.output_format,
        }
        if plan.size:
            kwargs["size"] = plan.size
        return kwargs

    def _outputs_from_response(self, response, plan, *, request_index: int) -> list[dict]:
        outputs: list[dict] = []
        width, height = self._parse_size(plan.size)
        for item in getattr(response, "data", []) or []:
            item_data = item if isinstance(item, dict) else {}
            if not item_data and hasattr(item, "model_dump"):
                item_data = item.model_dump(exclude_none=True) or {}
            b64_json = getattr(item, "b64_json", None) or item_data.get("b64_json")
            source = "b64_json"
            if not b64_json:
                url = getattr(item, "url", None) or item_data.get("url")
                if url:
                    b64_json = self._download_url_as_b64(str(url))
                    source = "url"
            if not b64_json:
                keys = sorted(item_data.keys())
                raise ProviderRuntimeError(
                    "OpenAI response did not include image bytes.",
                    provider=self.name,
                    detail={"response_item_keys": keys, "request_index": request_index},
                )
            outputs.append(
                {
                    "b64_json": b64_json,
                    "mime_type": f"image/{plan.output_format}",
                    "format": plan.output_format,
                    "width": width,
                    "height": height,
                    "request_index": request_index,
                    "api_response_source": source,
                }
            )
        return outputs

    def _download_url_as_b64(self, url: str) -> str:
        normalized_url = str(url or "").strip()
        data_url_prefix = "data:image/"
        if normalized_url.lower().startswith(data_url_prefix):
            try:
                _, encoded = normalized_url.split(",", 1)
            except ValueError as exc:
                raise ProviderRuntimeError(
                    "OpenAI image data URL was malformed.",
                    provider=self.name,
                    detail={"url_present": True},
                ) from exc
            return encoded.strip()
        request_url = self._absolute_image_url(normalized_url)
        headers = self._download_headers_for_url(request_url)
        max_attempts = 3
        last_error: Exception | None = None
        content_type = ""
        content = b""
        for attempt in range(1, max_attempts + 1):
            try:
                timeout = httpx.Timeout(240.0, connect=20.0, read=240.0, write=30.0, pool=30.0)
                with httpx.Client(timeout=timeout, follow_redirects=True) as client:
                    response = client.get(request_url, headers=headers) if headers else client.get(request_url)
                    response.raise_for_status()
                    content_type = str(response.headers.get("content-type") or "").lower()
                    content = response.content
                break
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break
                time.sleep(float(attempt * 2))
            except Exception as exc:
                last_error = exc
                break
        if last_error is not None and not content:
            raise ProviderRuntimeError(
                "OpenAI image URL could not be downloaded.",
                provider=self.name,
                detail={
                    "error_type": type(last_error).__name__,
                    "message": str(last_error)[:500],
                    "attempts": max_attempts,
                    "read_timeout_seconds": 240,
                },
            ) from last_error
        if not content:
            raise ProviderRuntimeError(
                "OpenAI image URL returned empty content.",
                provider=self.name,
                detail={"url_present": True},
            )
        if content_type and not (content_type.startswith("image/") or "octet-stream" in content_type):
            raise ProviderRuntimeError(
                "OpenAI image URL returned non-image content.",
                provider=self.name,
                detail={"content_type": content_type[:120]},
            )
        if len(content) > 64 * 1024 * 1024:
            raise ProviderRuntimeError(
                "OpenAI image URL returned an unexpectedly large file.",
                provider=self.name,
                detail={"size_bytes": len(content)},
            )
        return base64.b64encode(content).decode("ascii")

    def _absolute_image_url(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme in {"http", "https"}:
            return url
        base_url = str(settings.openai_base_url or "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
        parsed_base = urlparse(base_url)
        if url.startswith("/") and parsed_base.scheme and parsed_base.netloc:
            return f"{parsed_base.scheme}://{parsed_base.netloc}{url}"
        return urljoin(base_url.rstrip("/") + "/", url)

    def _download_headers_for_url(self, url: str) -> dict[str, str]:
        if not settings.openai_api_key:
            return {}
        parsed_url = urlparse(url)
        base_url = str(settings.openai_base_url or "https://api.openai.com/v1").strip() or "https://api.openai.com/v1"
        parsed_base = urlparse(base_url)
        if parsed_url.netloc and parsed_base.netloc and parsed_url.netloc.lower() == parsed_base.netloc.lower():
            return {"Authorization": f"Bearer {settings.openai_api_key}"}
        return {}

    def _is_retryable_error(self, exc: Exception) -> bool:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return True
        status_code = self._status_code_from_exception(exc)
        if status_code in {408, 429, 500, 502, 503, 504}:
            return True
        message = str(exc).lower()
        retryable_markers = [
            "bad_response_status_code",
            "openai_error",
            "upstream_error",
            "upstream_text_reply",
            "temporarily unavailable",
            "concurrency limit exceeded",
            "rate_limit_error",
            "timeout",
            "timed out",
            "connection error",
            "bad gateway",
            "service unavailable",
            "gateway timeout",
            "gateway time-out",
            "504 gateway time-out",
            "nginx/",
            "rate limit reached",
            "input-images per min",
            "input images per min",
        ]
        return any(marker in message for marker in retryable_markers)

    def _is_transient_image_edit_error(self, exc: Exception) -> bool:
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
            return True
        status_code = self._status_code_from_exception(exc)
        message = str(exc).lower()
        if status_code in {408, 429, 500, 502, 503, 504}:
            return True
        if status_code == 403:
            return self._is_openai_compatible_gateway() or any(
                marker in message
                for marker in [
                    "upstream",
                    "provider",
                    "account",
                    "schedulable",
                    "aicodexvip",
                    "aiai",
                    "404token",
                    "temporarily",
                    "cooldown",
                ]
            )
        return any(
            marker in message
            for marker in [
                "bad_response_status_code",
                "openai_error",
                "internal_server_error",
                "upstream_error",
                "upstream 403",
                "upstream 500",
                "transport",
                "connection error",
                "timeout",
                "timed out",
                "gateway time-out",
                "504 gateway time-out",
                "nginx/",
            ]
        )

    def _status_code_from_exception(self, exc: Exception) -> int | None:
        status_code = getattr(exc, "status_code", None)
        if status_code is not None:
            try:
                return int(status_code)
            except (TypeError, ValueError):
                return None
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        try:
            return int(status_code) if status_code is not None else None
        except (TypeError, ValueError):
            return None

    def _is_openai_compatible_gateway(self) -> bool:
        base_url = str(settings.openai_base_url or "").strip().lower()
        if not base_url:
            return False
        parsed = urlparse(base_url)
        host = parsed.netloc.lower()
        if not host:
            return False
        return host not in {"api.openai.com", "api.openai.com:443"}

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

    def _client_timeout_seconds(self, *, image_edit: bool) -> float:
        value = (
            settings.openai_image_edit_request_timeout_seconds
            if image_edit
            else settings.openai_image_request_timeout_seconds
        )
        return max(30.0, float(value))

    async def _call_with_timeout(self, awaitable, *, image_edit: bool, timeout_seconds: float | None = None):
        timeout = self._client_timeout_seconds(image_edit=image_edit) if timeout_seconds is None else timeout_seconds
        return await asyncio.wait_for(awaitable, timeout=timeout)

    async def _close_async_client(self, client) -> None:
        for method_name in ("close", "aclose"):
            close = getattr(client, method_name, None)
            if close is None:
                continue
            result = close()
            if inspect.isawaitable(result):
                await result
            return

    def _provider_reference_paths(self, reference_paths: list) -> list:
        return prepare_provider_reference_images(reference_paths)

    def _provider_reference_path(self, path):
        return prepare_provider_reference_image(path)

    def _model(self) -> str:
        return self.model or settings.openai_image_model
