from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.config import settings
from app.providers.registry import ProviderRegistry
from alchemy_creative_agent_3_0.app.generation_router.providers import (
    ProductionImageGenerationProvider,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    IdentityRepairStrategyRouter,
    SubjectContinuityAssetPackage,
)


ROOT = Path(__file__).resolve().parents[2]


def test_doc100_production_registry_and_runtime_have_no_identity_sidecar() -> None:
    registry = ProviderRegistry()
    assert "identity_native_sidecar" not in registry.image_providers

    runtime_files = [
        ROOT / "alchemy_creative_agent_3_0/app/generation_router/providers.py",
        ROOT / "alchemy_creative_agent_3_0/app/product_api/service.py",
        ROOT / "src_skeleton/app/config.py",
        ROOT / "src_skeleton/app/providers/registry.py",
    ]
    for path in runtime_files:
        assert "identity_native_sidecar" not in path.read_text(encoding="utf-8")


def test_doc100_v3_uses_openai_gpt_image_even_when_another_default_is_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", "test-gpt-image-2-key")
    monkeypatch.setattr(settings, "default_image_provider", "gemini_image")
    monkeypatch.setattr(settings, "gemini_image_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "gemini_image_generation_enabled", True)
    provider = ProductionImageGenerationProvider(output_store=object())

    assert provider._select_provider([]) == "openai_gpt_image"  # noqa: SLF001
    assert provider._select_provider([{"file_path": "reference.png"}]) == "openai_gpt_image"  # noqa: SLF001
    assert provider._app_provider("openai_gpt_image")._model() == "gpt-image-2"  # noqa: SLF001
    with pytest.raises(ValueError, match="requires GPT Image 2"):
        provider._app_provider("gemini_image")  # noqa: SLF001


def test_doc100_missing_gpt_image_2_configuration_does_not_fall_back(monkeypatch) -> None:
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "lab_openai_api_key", None)
    monkeypatch.setattr(settings, "default_image_provider", "gemini_image")
    monkeypatch.setattr(settings, "gemini_image_api_key", "test-gemini-key")
    monkeypatch.setattr(settings, "gemini_image_generation_enabled", True)
    provider = ProductionImageGenerationProvider(output_store=object())

    with pytest.raises(ValueError, match="sole production renderer"):
        provider._select_provider([])  # noqa: SLF001


def test_doc100_stale_sidecar_capability_cannot_unlock_local_pixel_repair() -> None:
    package = SubjectContinuityAssetPackage(
        package_id="package_doc100",
        project_id="project_doc100",
        job_id="job_doc100",
        applies=True,
        subject_type="character",
        uploaded_root_truth_ids=["uploaded_root"],
        provider_candidate_ids=["uploaded_root"],
        root_truth_preserved=True,
    )
    plan = IdentityRepairStrategyRouter().build(
        project_id="project_doc100",
        job_id="job_doc100",
        package=package,
        metadata={
            "identity_native_local_repair": True,
            "allow_generic_face_local_repair": True,
            "provider_capabilities": {"identity_native_local_repair": True},
        },
    )

    assert plan.strategy == "regenerate_from_ranked_identity_pack"
    assert plan.allow_face_local_repair is False
    assert plan.metadata["sole_renderer"] == "gpt-image-2"


@pytest.mark.parametrize(
    ("quality_mode", "expected"),
    [("standard", 1), ("strict", 2), ("explore", 0)],
)
def test_doc100_quality_rerender_budgets_remain_bounded(quality_mode: str, expected: int) -> None:
    service = object.__new__(V3ProductApiService)
    request = SimpleNamespace(metadata={}, quality_mode=quality_mode)
    assert service._visual_auto_retry_max_attempts(request) == expected  # noqa: SLF001
