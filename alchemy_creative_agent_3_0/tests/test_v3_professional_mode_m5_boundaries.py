from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
ALCHEMY_ROOT = REPO_ROOT / "alchemy_creative_agent_3_0"
APP_ROOT = ALCHEMY_ROOT / "app"
ASSET_ROOT = APP_ROOT / "visual_assets"


def _source_text(root: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


def test_professional_asset_package_has_no_independent_renderer_or_secret_transport() -> None:
    source = _source_text(ASSET_ROOT).lower()
    forbidden = (
        "api.openai.com",
        "openai_api_key",
        "aiself",
        "auth.json",
        "subprocess",
        "requests.",
        "face_swap",
        "font",
        "ocr",
    )

    assert all(token not in source for token in forbidden)


def test_standard_runtime_does_not_lookup_professional_assets_without_explicit_mode() -> None:
    # The mainline seam intentionally imports the typed package. The
    # isolation contract is behavioral: an ordinary Standard request must not
    # consult a People Asset or carry Professional metadata.
    from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime

    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create a simple landscape image.",
            "scenario_selection": {"scenario_id": "general_creative"},
        }
    )

    assert result.status.value == "planned"
    assert "professional_mode" not in result.metadata
    assert "professional_mode_execution" not in result.metadata


def test_m5_real_pixel_claim_requires_external_provider_evidence() -> None:
    handoff = (
        ALCHEMY_ROOT
        / "docs"
        / "visual_assets"
        / "PROFESSIONAL_MODE_IMPLEMENTATION_STATUS_AND_M5_HANDOFF.md"
    ).read_text(encoding="utf-8")

    assert "real-pixel" in handoff.lower()
    assert "no production claim" in handoff.lower()
    assert "blocked" in handoff.lower()
