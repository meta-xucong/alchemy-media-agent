from __future__ import annotations

import asyncio

from app.config import Settings
from app.providers.images.registry import get_v2_image_provider
import app.providers.images.registry as registry
import app.providers.images.openai_gpt_image_2 as openai_provider
import app.providers.images.doubao_image as doubao_provider
import app.providers.images.gemini_image as gemini_provider
from app.services import generation as generation_service
from app.schemas import CreateImageJobRequest, ImagePromptPlan


def test_v2_defaults_do_not_hide_live_provider_failures_with_mock_output() -> None:
    settings = Settings()

    assert settings.allow_mock_fallback is False


def test_mock_provider_remains_an_explicit_test_choice() -> None:
    settings = Settings(allow_mock_fallback=True)

    assert settings.allow_mock_fallback is True


def test_auto_provider_without_live_configuration_fails_closed(monkeypatch) -> None:
    runtime_settings = Settings(
        image_generation_provider="auto",
        allow_mock_fallback=False,
        openai_api_key=None,
        doubao_image_api_key=None,
        gemini_api_key=None,
    )
    monkeypatch.setattr(registry, "settings", runtime_settings)
    monkeypatch.setattr(generation_service, "settings", runtime_settings)
    monkeypatch.setattr(openai_provider, "settings", runtime_settings)
    monkeypatch.setattr(doubao_provider, "settings", runtime_settings)
    monkeypatch.setattr(gemini_provider, "settings", runtime_settings)

    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(plan_id="plan_no_live", mode="smart_enhance", prompt="A clean product image."),
        provider_hint="auto",
    )
    job = asyncio.run(generation_service.create_image_job(request, job_id="job_no_live"))

    assert job.status == "failed"
    assert job.outputs == []
    assert job.provider_id == "v2_provider_selection"
    assert job.error["error_code"] == "provider_not_configured"


def test_explicit_mock_provider_remains_available_for_tests(monkeypatch) -> None:
    monkeypatch.setattr(registry, "settings", Settings(allow_mock_fallback=False))

    provider = asyncio.run(get_v2_image_provider("mock_image"))

    assert provider.name == "mock_image"
