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


def test_professional_asset_package_is_not_implicitly_imported_by_standard_runtime() -> None:
    standard_sources = [
        path
        for path in APP_ROOT.rglob("*.py")
        if "visual_assets" not in path.parts and "__pycache__" not in path.parts
    ]
    assert all("visual_assets" not in path.read_text(encoding="utf-8") for path in standard_sources)


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
