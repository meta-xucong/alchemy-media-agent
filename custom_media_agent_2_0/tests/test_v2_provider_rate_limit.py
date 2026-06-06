from __future__ import annotations

import asyncio

import pytest

from app.config import settings
from app.providers.images import openai_gpt_image_2 as openai_provider_module
from app.providers.images.base import V2ImageProviderRateLimitError, V2ImageProviderRequest
from app.providers.images.registry import get_v2_image_provider
from app.schemas import ImagePromptPlan


def _request() -> V2ImageProviderRequest:
    return V2ImageProviderRequest(
        run_id="run_rate_limit_test",
        prompt_plan=ImagePromptPlan(
            plan_id="plan_rate_limit_test",
            mode="smart_enhance",
            prompt="Minimal product poster.",
            provider_parameters={"count": 1},
        ),
    )


def test_v2_openai_provider_capabilities_include_local_rate_guard() -> None:
    provider = asyncio.run(get_v2_image_provider("openai_gpt_image"))

    caps = asyncio.run(provider.capabilities())

    assert caps.limits["local_max_requests_per_minute"] == settings.openai_image_local_max_requests_per_minute
    assert caps.limits["local_max_outputs_per_minute"] == settings.openai_image_local_max_outputs_per_minute
    assert caps.limits["local_queue_timeout_seconds"] == settings.openai_image_local_queue_timeout_seconds
    assert caps.limits["upstream_cooldown_seconds"] == settings.openai_image_upstream_cooldown_seconds


def test_v2_openai_provider_cools_down_after_image_quota_limit() -> None:
    provider = asyncio.run(get_v2_image_provider("openai_gpt_image"))
    attempts = 0
    original_queue_timeout = settings.openai_image_local_queue_timeout_seconds
    object.__setattr__(settings, "openai_image_local_queue_timeout_seconds", 0.01)

    class QuotaResponse:
        headers = {"Retry-After": "120"}

    class QuotaError(Exception):
        status_code = 429
        response = QuotaResponse()

    class QuotaImages:
        async def generate(self, **kwargs):
            nonlocal attempts
            attempts += 1
            raise QuotaError("Rate limit reached for gpt-image-2-codex on input-images per min: Limit 4000")

    class SuccessImages:
        async def generate(self, **kwargs):
            raise AssertionError("OpenAI SDK should not be called during local cooldown.")

    class QuotaClient:
        images = QuotaImages()

    class SuccessClient:
        images = SuccessImages()

    try:
        with pytest.raises(V2ImageProviderRateLimitError) as first:
            asyncio.run(provider._generate_one(QuotaClient(), _request(), index=0))
        assert attempts == 1
        assert first.value.detail["rate_limit_scope"] == "openai_image_input_images_per_minute"
        assert first.value.detail["retry_after_seconds"] == 120

        with pytest.raises(V2ImageProviderRateLimitError) as second:
            asyncio.run(provider._generate_one(SuccessClient(), _request(), index=0))
        assert second.value.detail["rate_limit_scope"] == "upstream_openai_image_rate_limit_cooldown"
    finally:
        openai_provider_module._openai_image_rate_limiter.reset()
        object.__setattr__(settings, "openai_image_local_queue_timeout_seconds", original_queue_timeout)
