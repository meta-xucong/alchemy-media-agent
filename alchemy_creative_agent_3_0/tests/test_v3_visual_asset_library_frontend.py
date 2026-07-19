"""Static contracts for the Doc173 library-first V3 browser surface.

The production browser verification is deliberately separate.  These checks
lock the non-negotiable information architecture: a Visual Asset Library is
not a project template or an opt-in generation mode, and projects only use an
asset after an explicit binding confirmation.
"""

from pathlib import Path

from alchemy_creative_agent_3_0.app.app_shell.routes import get_route_contracts


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
STYLES_CSS = ROOT / "src_skeleton" / "app" / "static" / "styles.css"
HANDLERS = ROOT / "alchemy_creative_agent_3_0" / "app" / "product_api" / "route_handlers.py"


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def test_doc173_library_is_an_explicit_peer_of_projects_not_a_project_mode() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="v3OpenVisualAssetLibraryBtn"' in index
    assert 'id="v3VisualAssetLibraryView"' in index
    assert 'id="v3ProjectVisualAssetPanel"' in index
    assert 'id="v3VisualAssetBindingDialog"' in index
    assert 'data-v3-mode=' not in index
    assert "function openV3VisualAssetLibrary()" in source
    assert 'v3State.view = "visual_asset_library"' in source
    assert "professional_mode:" not in _function(source, "createV3Project", "renderV3Projects")
    assert "v3State.professionalMode" not in source[: source.index("async function openV3Project")]


def test_doc173_uses_library_and_binding_routes_not_legacy_project_asset_writes() -> None:
    routes = get_route_contracts()
    assert routes["visual_assets"] == "/api/v3/creative-agent/visual-assets"
    assert routes["project_visual_asset_bindings"].endswith("/visual-asset-bindings")

    source = APP_JS.read_text(encoding="utf-8")
    library = _function(source, "v3VisualAssetsPath", "v3VisualAssetPath")
    assert "/visual-assets" in library
    create = _function(source, "createV3VisualAsset", "prepareV3VisualAsset")
    assert "root_source_asset_id: ready.asset_id" in create
    assert 'asset_type: "people"' in create
    assert "candidate" not in create
    assert "prompt_hash" not in create
    assert "v3PeopleAssetsPath" not in create
    binding = _function(source, "confirmV3VisualAssetBinding", "clearV3ProjectVisualAssetBinding")
    assert "confirm_binding: true" in binding
    assert "selected_version_id: asset.active_version_id" in binding
    assert "v3ProjectVisualAssetBindingsPath" in binding


def test_doc173_asset_lifecycle_and_binding_copy_is_human_readable_and_non_secret() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    handlers = HANDLERS.read_text(encoding="utf-8")

    for text in ("需要建立标准建模", "正在建立标准建模", "等待你确认启用", "已启用，可用于项目"):
        assert text in source or text in index
    assert "上传源图不等于启用" in index
    assert "开始生成后，本次使用的版本会固定在该任务中" in index
    assert "候选" not in index[index.index("id=\"v3VisualAssetLibraryView\""):index.index("id=\"v3WorkspaceView\"")]
    helper_start = handlers.index("def _visual_asset_public_record")
    helper_end = handlers.index("    @staticmethod\n    def _project_visual_asset_binding_public_record", helper_start)
    helper = handlers[helper_start:helper_end]
    assert '"version_id"' in helper
    assert '"anchor_views"' in helper
    assert "root_source_asset_id" not in helper
    assert '"prompt"' not in helper.lower()
    assert '"provider"' not in helper.lower()


def test_doc173_project_binding_is_explicit_and_never_silent_fallback() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    panel = _function(source, "renderV3ProjectVisualAssetPanel", "openV3VisualAssetBindingDialog")
    create_job = _function(source, "createV3Job", "renderV3Job")

    assert "visual_asset_library" in source
    assert "视觉资产：未使用" in panel
    assert "系统不会悄悄改用普通参考" in panel
    assert "projectVisualAssetBindingState === \"blocked\"" in create_job
    assert "选择其他已启用资产" in create_job
    assert "professional_mode" not in create_job


def test_doc173_new_surface_is_responsive_and_does_not_reintroduce_template_fallback() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert "v3DefaultTemplateCards" not in source
    assert "templateCatalogStatus" in source
    for selector in (
        ".v3-visual-asset-library-view",
        ".v3-visual-asset-binding-dialog",
        ".v3-project-visual-asset-panel",
    ):
        assert selector in css
    assert "@media (max-width: 720px)" in css
    assert ".v3-visual-asset-actions .button" in css
