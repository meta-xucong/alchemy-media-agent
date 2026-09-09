from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
DESKTOP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
DESKTOP_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
MOBILE_HTML = ROOT / "src_skeleton" / "app" / "mobile_static" / "index.html"

CANONICAL_MODES = (
    "auto",
    "selection_candidates",
    "delivery_suite",
    "creative_exploration",
    "format_layout_adaptation",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _function_body(source: str, name: str) -> str:
    start = source.index(f"function {name}")
    next_function = source.find("\nfunction ", start + 1)
    return source[start:] if next_function < 0 else source[start:next_function]


def test_desktop_and_mobile_expose_only_canonical_general_mode_controls() -> None:
    desktop_html = _read(DESKTOP_HTML)
    mobile_html = _read(MOBILE_HTML)
    desktop_js = _read(DESKTOP_JS)
    mobile_js = _read(MOBILE_JS)

    for mode in CANONICAL_MODES:
        assert f'data-v3-variation-mode="{mode}"' in desktop_html
        assert f'data-mobile-v3-mode="{mode}"' in mobile_html
        assert mode in desktop_js
        assert mode in mobile_js

    assert 'data-mobile-v3-mode="similar_options"' not in mobile_html
    assert 'data-mobile-v3-mode="suite_expansion"' not in mobile_html
    assert 'data-mobile-v3-mode="layout_adaptation"' not in mobile_html
    assert "MOBILE_V3_VARIATION_MODE_ALIASES" in mobile_js
    assert "mobileV3CanonicalVariationMode" in mobile_js


def test_doc59_auto_detection_priority_and_ambiguous_multi_image_contract() -> None:
    desktop = _function_body(_read(DESKTOP_JS), "inferV3VariationMode")
    mobile = _function_body(_read(MOBILE_JS), "mobileV3InferVariationMode")

    for source in (desktop, mobile):
        assert "requestedCount" in source
        assert "hasReference" in source
        assert "selectedSize" in source
        assert re.search(r"尺寸.*画幅.*比例.*版式", source)
        assert re.search(r"探索.*不同方向.*不同概念.*尝试新风格", source)
        assert re.search(r"沿这个方向做一组图|系列|套图", source)
        assert re.search(r"(?:requestedCount|count)[^\n]*> 1", source)
        assert "selection_candidates" in source
        assert source.index("creative_exploration") < source.index("delivery_suite")


def test_project_preferences_restore_without_general_ecommerce_leakage() -> None:
    desktop = _read(DESKTOP_JS)
    mobile = _read(MOBILE_JS)

    for source in (desktop, mobile):
        assert "generation_preferences" in source
        assert re.search(r"apply.*GenerationPreferences", source, re.IGNORECASE)
        assert "requested_image_count" in source
        assert "photography_reference_role" in source
        assert "scene_domain" in source

    desktop_restore = _function_body(desktop, "applyV3GenerationPreferences")
    mobile_restore = _function_body(mobile, "applyMobileV3GenerationPreferences")
    for source in (desktop_restore, mobile_restore):
        assert "general_variation_mode" in source
        assert "photography" in source
        assert "requested_count" in source
        assert "ecommerce" not in source.lower()


def test_continuation_preserves_count_and_current_mode_intent() -> None:
    desktop = _read(DESKTOP_JS)
    continuation = _function_body(desktop, "setV3ContinuationGenerationDefaults")
    action_region = desktop[desktop.index('action === "continue_same_style"') :]

    assert "v3State.generationCount" in continuation
    assert "supported.includes(1) ? 1" not in continuation
    assert "保持这个项目已选图片的风格" not in action_region
    assert "els.v3PromptInput.value.trim()" in action_region


def test_mobile_photography_keeps_reference_reshoot_and_canonical_metadata() -> None:
    mobile_html = _read(MOBILE_HTML)
    mobile_js = _read(MOBILE_JS)

    assert 'data-mobile-v3-photography-mode="reference_reshoot"' in mobile_html
    assert 'data-mobile-v3-photography-mode="professional_set"' in mobile_html
    assert "reference_reshoot" in mobile_js
    assert "selected_mode_id" in mobile_js
    assert "selected_preset_id" in mobile_js
    assert "photography_reference_role" in mobile_js
    assert "hasPhotographyReference ? mobileV3State.selectedPhotographyReferenceRole" in mobile_js


def test_desktop_photography_reference_gate_has_both_new_and_saved_reference_inputs() -> None:
    desktop = _read(DESKTOP_JS)
    payload = _function_body(desktop, "buildV3JobPayload")
    assert "const hasUploadedReference = uploadedAssets.length > 0" in payload
    assert "hasUploadedReference || existingPhotographyReferences.length > 0" in payload


def test_frontends_do_not_boot_with_an_ecommerce_only_count_contract() -> None:
    desktop_html = _read(DESKTOP_HTML)
    mobile_html = _read(MOBILE_HTML)
    mobile_js = _read(MOBILE_JS)
    assert '<option value="2" selected>2 张</option>' in desktop_html
    assert '<option value="3">3 张</option>' in desktop_html
    assert '<option value="7">7 张</option>' not in desktop_html
    assert '<option value="2" selected>2</option>' in mobile_html
    assert '<option value="3">3</option>' in mobile_html
    assert '<option value="7">7</option>' not in mobile_html
    assert "legacyVariationMode" in mobile_js
    assert "project?.metadata?.effective_variation_mode" in mobile_js


def test_desktop_repaint_reapplies_restored_mode_before_count_projection() -> None:
    desktop = _read(DESKTOP_JS)
    render = _function_body(desktop, "renderV3ScenarioState")
    assert render.index('setV3VariationMode(v3State.selectedVariationMode || "auto")') < render.index("setV3Preset")
    assert "els.v3CountInput.value = String(v3State.generationCount)" in render
