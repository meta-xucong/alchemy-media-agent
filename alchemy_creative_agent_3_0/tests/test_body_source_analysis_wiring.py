"""Red tests for default Body source-analysis provider wiring."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.adapter import V3LLMBrainAdapter  # noqa: F401
from alchemy_creative_agent_3_0.app.product_api import service as service_module
from alchemy_creative_agent_3_0.app.product_api import body_cross_view_review_provider as cross_view_module
from alchemy_creative_agent_3_0.app.product_api.body_cross_view_review_provider import (
    OpenAICompatibleBodyCrossViewReviewProvider,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets import body_proportion_evidence_profile as profile_module
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    OpenAICompatibleBodySourceAnalysisProvider,
)


def test_factory_reads_existing_lab_vision_config_only_when_complete(monkeypatch) -> None:
    values = {
        "api_key": "configured",
        "base_url": "https://vision.example/v1",
        "model": "body-vision-model",
    }
    monkeypatch.setattr(
        profile_module,
        "_lab_vision_enabled",
        lambda: True,
    )
    monkeypatch.setattr(profile_module, "_lab_vision_setting", values.get)

    provider = profile_module.create_configured_body_source_analysis_provider()

    assert isinstance(provider, OpenAICompatibleBodySourceAnalysisProvider)
    assert provider.api_key == "configured"
    assert provider.base_url == "https://vision.example/v1"
    assert provider.model == "body-vision-model"


@pytest.mark.parametrize("missing", ["api_key", "base_url", "model"])
def test_factory_missing_any_lab_vision_setting_stays_unconfigured(
    monkeypatch,
    missing: str,
) -> None:
    values = {
        "api_key": "configured",
        "base_url": "https://vision.example/v1",
        "model": "body-vision-model",
    }
    values[missing] = None
    monkeypatch.setattr(profile_module, "_lab_vision_enabled", lambda: True)
    monkeypatch.setattr(profile_module, "_lab_vision_setting", values.get)

    assert profile_module.create_configured_body_source_analysis_provider() is None


def test_default_product_api_and_runtime_share_the_same_wired_analyzer(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(
        service_module,
        "create_configured_body_source_analysis_provider",
        lambda: sentinel,
    )

    service = V3ProductApiService()

    assert service.body_proportion_source_analyzer is sentinel
    assert service.scenario_runtime.body_proportion_source_analyzer is sentinel


def test_default_product_api_wires_cross_view_reviewer_from_lab_vision_config(monkeypatch) -> None:
    values = {
        "api_key": "configured",
        "base_url": "https://vision.example/v1",
        "model": "body-vision-model",
    }
    monkeypatch.setattr(cross_view_module, "_lab_vision_enabled", lambda: True)
    monkeypatch.setattr(cross_view_module, "_lab_vision_setting", values.get)

    service = V3ProductApiService(body_proportion_source_analyzer=object())

    assert isinstance(
        service.body_cross_view_review_provider,
        OpenAICompatibleBodyCrossViewReviewProvider,
    )
    assert service.body_cross_view_review_provider.output_store is service.output_store
    assert service.body_cross_view_review_provider.api_key == "configured"
    assert service.body_cross_view_review_provider.base_url == "https://vision.example/v1"
    assert service.body_cross_view_review_provider.model == "body-vision-model"


def test_explicit_analyzer_injection_is_not_replaced_by_factory(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(
        service_module,
        "create_configured_body_source_analysis_provider",
        lambda: pytest.fail("factory must not replace explicit injection"),
    )

    service = V3ProductApiService(body_proportion_source_analyzer=sentinel)

    assert service.body_proportion_source_analyzer is sentinel
    assert service.scenario_runtime.body_proportion_source_analyzer is sentinel


@pytest.mark.parametrize("source_mode", ["ordinary", "inference_first"])
def test_wired_analyzer_does_not_cross_mode_boundary(monkeypatch, source_mode: str) -> None:
    provider = object()
    runtime = ScenarioRuntime(body_proportion_source_analyzer=provider)
    monkeypatch.setattr(runtime, "_is_professional_mode_selected", lambda _request: True)
    metadata = {
        "professional_character_card_body_refresh_source_mode": source_mode,
        "professional_character_card_stage": "body_silhouette",
        "professional_character_card_slot": "body.front_full",
    }

    assert runtime._body_proportion_profile_for_brain(  # noqa: SLF001
        SimpleNamespace(metadata=metadata),
        stage="plan",
    ) is None
