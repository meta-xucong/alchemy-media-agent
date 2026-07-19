"""Offline contract checks for the Professional Mode V3 browser surface.

These tests intentionally inspect the static client instead of pretending a
browser/API run succeeded. A real service-backed four-viewport browser run is
reported separately when the controlled service is available.
"""

from pathlib import Path

from alchemy_creative_agent_3_0.app.app_shell.routes import get_route_contracts


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
STYLES_CSS = ROOT / "src_skeleton" / "app" / "static" / "styles.css"
HANDLERS = ROOT / "alchemy_creative_agent_3_0" / "app" / "product_api" / "route_handlers.py"


def test_professional_mode_is_explicit_and_standard_is_the_default() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")

    assert 'professionalMode: "standard"' in source
    assert 'data-v3-mode="professional"' in index
    assert 'data-v3-mode="standard"' in index
    assert 'v3State.professionalMode === "professional"' in source
    assert "v3ProfessionalModeSelected()" in source
    # No keyword-based mode switch is allowed; the only mode mutation is the
    # explicit data-v3-mode control (plus server project readback).
    assert "includes(\"人物\")" not in source
    assert "includes(\"人脸\")" not in source


def test_people_asset_routes_and_public_contract_are_present() -> None:
    routes = get_route_contracts()
    assert routes["project_people_assets"] == "/api/v3/creative-agent/projects/{project_id}/people-assets"
    assert routes["project_people_asset"] == "/api/v3/creative-agent/projects/{project_id}/people-assets/{people_asset_id}"
    assert routes["prepare_project_people_asset"].endswith("/prepare")
    assert routes["activate_project_people_asset"].endswith("/activate")
    source = APP_JS.read_text(encoding="utf-8")
    for suffix in ("/people-assets", "/prepare", "/activate"):
        assert suffix in source
    assert "body: {}" in source


def test_create_and_activation_payloads_keep_server_owned_evidence_boundaries() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    create_start = source.index("async function createV3PeopleAsset")
    prepare_start = source.index("async function prepareV3PeopleAsset")
    create_block = source[create_start:prepare_start]
    assert "root_source_asset_id: ready.asset_id" in create_block
    assert "preparation_intent: intent" in create_block
    assert "pack_version_id" not in create_block
    assert "candidate" not in create_block
    assert "reference_path" not in create_block

    activate_start = source.index("async function activateV3PeopleAsset")
    handler_start = source.index("function handleV3PeopleAssetAction")
    activate_block = source[activate_start:handler_start]
    assert "confirm_activation: true" in activate_block
    assert "pack_version_id: packVersionId" in activate_block


def test_professional_lifecycle_uses_human_error_projection_and_no_internal_error_toast() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    assert "function v3ProfessionalErrorMessage" in source
    assert "HTML gateway page" in source
    assert "项目已保留，请稍后刷新再试" in source
    assert "v3ProfessionalErrorMessage(error)" in source
    assert 'v3State.professionalMode === "professional"' in source
    professional_start = source.index("function v3ProfessionalErrorMessage")
    professional_end = source.index("function v3PeopleAssetViewLabel")
    error_block = source[professional_start:professional_end]
    assert "error?.message" in error_block
    assert "innerHTML" not in error_block


def test_standard_verticals_do_not_receive_people_asset_semantics() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    assert 'general_template' in source
    assert 'ecommerce_template' in source
    assert 'photographer_template' in source
    assert 'professional_mode: v3State.professionalMode === "professional"' in source
    assert 'v3ProfessionalAssetPanel' in source
    # The panel is hidden unless explicit Professional state and a project are
    # both present; ordinary scenario rendering has no automatic activation.
    assert 'const visible = Boolean(panel && v3ProfessionalModeSelected() && v3State.currentProject?.project_id);' in source


def test_refresh_projection_is_status_only_and_does_not_expose_prompt_or_candidates() -> None:
    source = HANDLERS.read_text(encoding="utf-8")
    helper_start = source.index("def _people_asset_public_record")
    helper_end = source.index("    def post_project_people_asset_prepare", helper_start)
    helper = source[helper_start:helper_end]
    assert "latest_preparation" in helper
    assert '"anchor_views"' in helper
    assert "pack_snapshot" in helper
    assert '"candidate' not in helper
    assert '"prompt' not in helper.lower()
    assert '"provider' not in helper.lower()


def test_responsive_professional_surface_has_non_hover_mobile_controls() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")
    assert ".v3-mode-chooser" in css
    assert ".v3-professional-asset-panel" in css
    assert "@media (max-width: 720px)" in css
    assert ".v3-professional-asset-actions .button { width: 100%; }" in css
    assert "cursor: pointer" in css
