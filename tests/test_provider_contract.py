import asyncio
import json
import sys
from types import SimpleNamespace

import pytest

from app.providers.base import ProviderRateLimitError
from app.providers.registry import registry
from app.schemas import ImageGenerationRequest, ImagePromptPlan
from app.config import settings
from app.services.work_intensity import apply_work_intensity


def test_openai_image_provider_capabilities():
    caps = asyncio.run(registry.image("openai_gpt_image").capabilities())
    assert caps.provider == "openai_gpt_image"
    assert "generate" in caps.operations
    assert caps.models == ["gpt-image-2"]
    assert caps.limits["qualities"] == ["auto", "low", "medium", "high"]


def test_openai_image_provider_cost_uses_runtime_model():
    estimate = asyncio.run(
        registry.image("openai_gpt_image").estimate_cost(
            ImageGenerationRequest(prompt_plan=ImagePromptPlan(main_subject="咖啡海报", count=1))
        )
    )
    assert estimate.provider == "openai_gpt_image"
    assert estimate.model == "gpt-image-2"


def test_openai_image_provider_detects_concurrency_limit():
    provider = registry.image("openai_gpt_image")
    exc = Exception("Error code: 429 - {'error': {'message': 'Concurrency limit exceeded for account, please retry later', 'type': 'rate_limit_error'}}")

    assert provider._is_retryable_error(exc) is True
    assert provider._is_concurrency_limit_error(exc) is True
    assert provider._retry_delay_seconds(exc, 3) == 36.0


def test_openai_image_provider_passes_quality_to_sdk_call():
    provider = registry.image("openai_gpt_image")
    captured = {}

    class CapturingImages:
        async def generate(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class CapturingClient:
        images = CapturingImages()

    asyncio.run(
        provider._generate_one(
            CapturingClient(),
            "prompt",
            ImagePromptPlan(main_subject="咖啡海报", count=1, quality="low"),
            index=0,
        )
    )

    assert captured["quality"] == "low"
    assert captured["model"] == "gpt-image-2"


def test_work_intensity_llm_planner_passes_reasoning_effort(monkeypatch):
    captured = {}
    original_key = settings.openai_api_key
    original_base_url = settings.openai_base_url
    original_model = settings.default_llm_model
    original_openai_llm_model = settings.openai_llm_model
    original_enabled = settings.llm_prompt_planning_enabled

    class FakeResponses:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "main_subject": "精品咖啡海报",
                        "scene": "安静的精品咖啡馆",
                        "style": "高级商业摄影",
                        "composition": "竖版主视觉",
                        "brand_constraints": ["premium tone"],
                        "negative_constraints": ["avoid clutter"],
                        "text": {"required": False, "language": "zh-CN"},
                        "generation_prompt": "LLM refined premium coffee poster prompt",
                        "planning_notes": ["checked composition"],
                    }
                )
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    try:
        settings.openai_api_key = "sk-test-planner"
        settings.openai_base_url = "https://example.test/v1"
        settings.default_llm_model = "gpt-5.5-test"
        settings.openai_llm_model = "gpt-5.5-test"
        settings.llm_prompt_planning_enabled = True
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeClient))

        plan, summary = asyncio.run(
            apply_work_intensity(
                ImagePromptPlan(main_subject="生成 1 张精品咖啡海报", count=1),
                original_prompt="生成 1 张精品咖啡海报",
                work_intensity="atelier",
                provider_preference="openai_gpt_image",
            )
        )
    finally:
        settings.openai_api_key = original_key
        settings.openai_base_url = original_base_url
        settings.default_llm_model = original_model
        settings.openai_llm_model = original_openai_llm_model
        settings.llm_prompt_planning_enabled = original_enabled

    assert captured["reasoning"]["effort"] == "high"
    assert captured["model"] == "gpt-5.5-test"
    assert summary["planner"] == "llm"
    assert summary["llm_used"] is True
    assert plan.variables["planner"] == "llm"
    assert plan.variables["generation_prompt"] == "LLM refined premium coffee poster prompt"


def test_work_intensity_uses_backup_llm_when_primary_fails(monkeypatch):
    captured = {}
    original_key = settings.openai_api_key
    original_base_url = settings.openai_base_url
    original_model = settings.default_llm_model
    original_provider = settings.default_llm_provider
    original_backup_provider = settings.backup_llm_provider
    original_backup_model = settings.backup_llm_model
    original_openai_llm_model = settings.openai_llm_model
    original_kimi_llm_model = settings.kimi_llm_model
    original_anthropic_base_url = settings.anthropic_base_url
    original_anthropic_api_key = settings.anthropic_api_key
    original_anthropic_auth_token = settings.anthropic_auth_token
    original_enabled = settings.llm_prompt_planning_enabled

    class FailingResponses:
        async def create(self, **kwargs):
            raise RuntimeError("primary planner unavailable")

    class FailingClient:
        def __init__(self, **kwargs):
            self.responses = FailingResponses()

    class FakeHTTPResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "main_subject": "备用规划咖啡海报",
                                "scene": "明亮咖啡吧台",
                                "style": "日系清爽商业摄影",
                                "composition": "手机竖屏主视觉",
                                "brand_constraints": ["fresh tone"],
                                "negative_constraints": ["avoid clutter"],
                                "text": {"required": False, "language": "zh-CN"},
                                "generation_prompt": "Kimi backup refined coffee poster prompt",
                                "planning_notes": ["backup checked composition"],
                            }
                        ),
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["header_names"] = sorted(headers)
            captured["payload"] = json
            return FakeHTTPResponse()

    try:
        settings.openai_api_key = "sk-primary-test"
        settings.openai_base_url = "https://primary.example.test/v1"
        settings.default_llm_provider = "openai"
        settings.default_llm_model = "gpt-5.5-test"
        settings.openai_llm_model = "gpt-5.5-test"
        settings.backup_llm_provider = "anthropic"
        settings.backup_llm_model = "kimi-for-coding-test"
        settings.kimi_llm_model = "kimi-for-coding-test"
        settings.anthropic_base_url = "https://backup.example.test"
        settings.anthropic_api_key = None
        settings.anthropic_auth_token = "sk-backup-test"
        settings.llm_prompt_planning_enabled = True
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FailingClient))
        monkeypatch.setattr("app.services.work_intensity.httpx.AsyncClient", FakeAsyncClient)

        plan, summary = asyncio.run(
            apply_work_intensity(
                ImagePromptPlan(main_subject="生成 1 张精品咖啡海报", count=1),
                original_prompt="生成 1 张精品咖啡海报",
                work_intensity="studio",
                provider_preference="openai_gpt_image",
            )
        )
    finally:
        settings.openai_api_key = original_key
        settings.openai_base_url = original_base_url
        settings.default_llm_model = original_model
        settings.default_llm_provider = original_provider
        settings.backup_llm_provider = original_backup_provider
        settings.backup_llm_model = original_backup_model
        settings.openai_llm_model = original_openai_llm_model
        settings.kimi_llm_model = original_kimi_llm_model
        settings.anthropic_base_url = original_anthropic_base_url
        settings.anthropic_api_key = original_anthropic_api_key
        settings.anthropic_auth_token = original_anthropic_auth_token
        settings.llm_prompt_planning_enabled = original_enabled

    assert captured["url"] == "https://backup.example.test/v1/messages"
    assert captured["payload"]["model"] == "kimi-for-coding-test"
    assert "authorization" in captured["header_names"]
    assert "x-api-key" in captured["header_names"]
    assert summary["planner"] == "llm"
    assert summary["llm_used"] is True
    assert summary["llm_provider"] == "anthropic"
    assert summary["llm_model"] == "kimi-for-coding-test"
    assert summary["fallback_used"] is True
    assert plan.variables["llm_provider"] == "anthropic"
    assert plan.variables["llm_model"] == "kimi-for-coding-test"
    assert plan.variables["generation_prompt"] == "Kimi backup refined coffee poster prompt"


def test_openai_image_provider_raises_retryable_rate_limit_after_retries(monkeypatch):
    provider = registry.image("openai_gpt_image")
    attempts = 0

    class FailingImages:
        async def generate(self, **kwargs):
            nonlocal attempts
            attempts += 1
            raise Exception("Error code: 429 - {'error': {'message': 'Concurrency limit exceeded for account, please retry later', 'type': 'rate_limit_error'}}")

    class FailingClient:
        images = FailingImages()

    async def no_sleep(seconds):
        return None

    monkeypatch.setattr("app.providers.openai_image.asyncio.sleep", no_sleep)

    with pytest.raises(ProviderRateLimitError) as raised:
        asyncio.run(
            provider._generate_one(
                FailingClient(),
                "prompt",
                ImagePromptPlan(main_subject="咖啡海报", count=1),
                index=0,
            )
        )

    assert attempts == 6
    assert raised.value.retryable is True
    assert raised.value.detail["upstream_concurrency_limited"] is True


def test_mock_image_provider_contract():
    provider = registry.image("mock_image")
    caps = asyncio.run(provider.capabilities())
    assert caps.configured is True
    assert caps.is_mock is True

    result = asyncio.run(
        provider.generate(
            ImageGenerationRequest(
                prompt_plan=ImagePromptPlan(main_subject="生成 2 张咖啡海报", count=2, size="1024x1536")
            )
        )
    )

    assert result.provider == "mock_image"
    assert result.model == "mock-image-v1"
    assert len(result.outputs) == 2
    assert "b64_json" in result.outputs[0]


def test_default_image_selection_falls_back_to_mock_when_openai_unconfigured():
    provider = asyncio.run(registry.select_image())
    assert provider.name == "mock_image"
