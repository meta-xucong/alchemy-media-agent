from __future__ import annotations

from pathlib import Path

from app.services.runtime_model_settings import VALID_IMAGE_PROVIDERS


APP_ROOT = Path(__file__).resolve().parents[1] / "app"
FORBIDDEN_APP_MARKERS = [
    "legacy_image_bridge",
    "create_legacy_image_job",
    "legacy_image_api_base",
    "alchemy_1_0_bridge",
    "custom_media_agent_docs",
    ".media_storage",
    "/api/v1",
    "/v1/",
    "v1_thinking",
]


def test_v2_app_has_no_v1_bridge_markers() -> None:
    offenders: list[str] = []
    for path in APP_ROOT.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for marker in FORBIDDEN_APP_MARKERS:
            if marker in text:
                offenders.append(f"{path.relative_to(APP_ROOT)} contains {marker}")

    assert offenders == []


def test_v2_runtime_providers_are_native_only() -> None:
    assert VALID_IMAGE_PROVIDERS == {"auto", "openai_gpt_image", "doubao_image", "gemini_image", "mock_image"}
    assert "alchemy_1_0_bridge" not in VALID_IMAGE_PROVIDERS
    assert not (APP_ROOT / "services" / "legacy_image_bridge.py").exists()
