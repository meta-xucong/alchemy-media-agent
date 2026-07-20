"""Static contracts for the Professional Visual Asset browser surface.

The production browser verification is deliberately separate.  These checks
lock the non-negotiable runtime ownership: a Visual Asset Library is not a
project template or an opt-in generation mode, and projects only use an asset
after an explicit binding confirmation. Doc177 owns the compact V3 page layout.
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


def test_doc173_library_is_not_a_template_or_generation_mode() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="v3ProfessionalHomeSurface"' in index
    assert 'id="v3VisualAssetLibraryPanel"' in index
    assert 'id="v3ProjectVisualAssetPanel"' in index
    assert 'id="v3VisualAssetBindingDialog"' in index
    assert 'data-v3-mode=' not in index
    assert "function openV3ProfessionalWorkspace()" in source
    assert 'v3_workspace: v3State.workspaceMode === "professional" ? "professional" : "standard"' in source
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
    upload = _function(source, "v3UploadVisualAssetRoot", "createV3VisualAsset")
    assert "root_source_asset_id: primary.asset_id" in create
    assert 'asset_type: "people"' in create
    assert 'role: "face_reference"' in upload
    assert 'role: "subject_reference"' not in upload
    assert "candidate" not in create
    assert "prompt_hash" not in create
    assert "v3PeopleAssetsPath" not in create
    binding = _function(source, "confirmV3VisualAssetBinding", "clearV3ProjectVisualAssetBinding")
    assert "confirm_binding: true" in binding
    assert "selected_version_id: asset.active_version_id" in binding
    assert "v3ProjectVisualAssetBindingsPath" in binding


def test_doc176_professional_source_selection_is_bounded_visible_and_never_first_file_only() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="v3VisualAssetRootInput"' in index
    visual_input = index[index.index('id="v3VisualAssetRootInput"') - 180:index.index('id="v3VisualAssetRootInput"') + 240]
    assert "multiple" in visual_input
    assert 'id="v3VisualAssetSourceList"' in index
    assert 'id="v3VisualAssetSourceSummary"' in index
    assert 'id="v3VisualAssetSourceFeedback"' in index
    assert "V3_VISUAL_ASSET_MAX_SOURCE_FILES = 2" in source
    assert "handleV3VisualAssetSourceFiles" in source
    assert "handleV3VisualAssetSourceListClick" in source
    assert "isV3VisualAssetImageFile" in source
    assert "visualAssetSourcePreviewUrls" in source
    assert "URL.createObjectURL" in source
    assert "URL.revokeObjectURL" in source
    assert "visualAssetPrimarySourceIndex" in source
    assert "visualAssetSourceFeedback" in source
    assert "最多使用 2 张源图" in source
    create = _function(source, "createV3VisualAsset", "prepareV3VisualAsset")
    assert "visualAssetSourceFiles" in create
    assert "supplementary_source_asset_ids" in create
    assert "v3VisualAssetRootInput?.files?.[0]" not in create
    for selector in (
        ".v3-visual-asset-source-field",
        ".v3-visual-asset-file-drop",
        ".v3-visual-asset-source-actions",
        ".v3-visual-asset-source-feedback",
        ".v3-visual-asset-source-preview",
    ):
        assert selector in css


def test_doc173_asset_lifecycle_and_binding_copy_is_human_readable_and_non_secret() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    handlers = HANDLERS.read_text(encoding="utf-8")

    for text in ("需要建立标准建模", "正在建立标准建模", "等待你确认启用", "已启用，可用于项目"):
        assert text in source or text in index
    assert "上传源图不等于启用" in index
    assert "开始生成后，本次使用的版本会固定在该任务中" in index
    assert "候选" not in index[index.index("id=\"v3VisualAssetLibraryPanel\""):index.index("id=\"v3WorkspaceView\"")]
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
        ".v3-professional-home-surface",
        ".v3-visual-asset-binding-dialog",
        ".v3-project-visual-asset-panel",
    ):
        assert selector in css
    assert "@media (max-width: 720px)" in css
    assert ".v3-visual-asset-actions .button" in css


def test_doc177_professional_home_is_a_compact_hub_and_detail_work_is_on_demand() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    home_start = index.index('id="v3ProfessionalHomeSurface"')
    home_end = index.index('id="v3WorkspaceView"', home_start)
    home = index[home_start:home_end]
    dialog_start = index.index('id="v3VisualAssetLibraryDialog"')
    binding_dialog_start = index.index('id="v3VisualAssetBindingDialog"', dialog_start)
    library_dialog = index[dialog_start:binding_dialog_start]

    assert 'id="v3OpenVisualAssetLibraryBtn"' in home
    assert 'id="v3CreateVisualAssetShortcutBtn"' in home
    assert 'id="v3VisualAssetLibrarySummary"' in home
    assert 'id="v3VisualAssetCreateForm"' not in home
    assert 'id="v3VisualAssetLibraryList"' not in home
    assert 'id="v3VisualAssetCreateForm"' in library_dialog
    assert 'id="v3VisualAssetLibraryList"' in library_dialog
    assert 'id="v3CloseVisualAssetLibraryDialogBtn"' in library_dialog

    assert "function openV3VisualAssetLibraryDialog" in source
    assert "function closeV3VisualAssetLibraryDialog" in source
    assert "function openV3VisualAssetLibraryFromBindingDialog" in source
    assert "openV3VisualAssetLibraryDialog({ focusBuilder: true })" in source
    assert 'id="v3ManageVisualAssetsFromBindingBtn"' in index
    assert ".v3-visual-asset-hub-card" in css
    assert ".v3-visual-asset-library-dialog" in css


def test_doc177_project_asset_card_preserves_explicit_binding_and_management_route() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")

    panel = _function(source, "renderV3ProjectVisualAssetPanel", "openV3VisualAssetBindingDialog")
    assert 'textContent = bindings.length ? "管理视觉资产" : "选择视觉资产"' in panel
    assert "openV3VisualAssetLibraryFromBindingDialog" in source
    assert "v3VisualAssetBindingDialog?.open" in source
    assert "v3VisualAssetLibraryDialog?.open" in source
    assert "不使用视觉资产" in index


def test_doc177_people_asset_submission_explains_missing_fields_inline() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    readiness = _function(source, "v3VisualAssetCreateMissingRequirements", "renderV3VisualAssetCreateReadiness")
    renderer = _function(source, "renderV3VisualAssetCreateReadiness", "clearV3VisualAssetCreateFeedback")
    create = _function(source, "createV3VisualAsset", "prepareV3VisualAsset")

    assert 'id="v3VisualAssetCreateFeedback"' in index
    assert 'aria-describedby="v3VisualAssetCreateFeedback"' in index
    for requirement in ("资产名称", "人物源图", "建模说明", "使用授权确认"):
        assert requirement in readiness
    assert "还需完成：" in renderer
    assert "资料已完整" in renderer
    assert "aria-invalid" in renderer
    assert "v3VisualAssetCreateMissingRequirements" in create
    assert "还差 ${missing.join" in create
    assert "showGlobalToast" not in create
    assert ".v3-visual-asset-create-feedback" in css
    assert '[data-tone="warning"]' in css


def test_doc177_people_asset_creation_is_linear_and_shows_modeling_progress() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="v3VisualAssetWorkflowPanel"' in index
    assert 'role="progressbar"' in index
    assert 'id="v3VisualAssetWorkflowSteps"' in index
    assert 'id="v3VisualAssetWorkflowActivateBtn"' in index
    assert "保存源图并开始标准建模" in index
    assert "visualAssetWorkflowAssetId = createdVisualAssetId" in source
    assert "prepareV3VisualAsset(createdVisualAssetId, { fromWorkflow: true })" in source
    assert "visualAssetWorkflowStage = \"blocked\"" in source
    assert 'asset.lifecycle_status === "preparing"' in source
    assert 'aria-valuetext' in source
    assert 'serverPreparingAsset' in source
    assert "重新开始标准建模" in index
    assert "确认启用这个人物资产" in index
    assert "v3VisualAssetWorkflowActivateBtn.disabled" in source
    assert "resetV3VisualAssetWorkflowForNewDraft" in source
    assert "const activateAction = canActivate" in source
    assert "const prepareAction = canPrepare" in source
    assert 'data-v3-visual-asset-action="activate"' in source
    assert 'const activateAction = canActivate' in source and ': "";' in source
    assert ".v3-visual-asset-workflow-panel" in css
    assert ".v3-visual-asset-workflow-progress.is-running" in css
    assert ".v3-visual-asset-workflow-actions .button" in css
