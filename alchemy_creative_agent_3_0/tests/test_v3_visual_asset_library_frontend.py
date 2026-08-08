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
FRONTEND_VERSION = "20260808-v3-professional-continue-native-recovery"


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


def test_doc247_character_card_slot_status_labels_are_formal_proof_aware() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    helper_start = source.index("function v3CharacterCardStatusLabel")
    helper_end = source.index("function v3CharacterCardAssetFailureMessage", helper_start)
    helper = source[helper_start:helper_end]

    assert 'String(status || "empty") === "winner_selected"' in helper
    assert 'return v3CharacterCardProofVerified(proofRecord) ? "已完成" : "待确认";' in helper
    assert 'active: "已完成"' in helper
    assert 'empty: "尚未建立"' in helper
    assert 'blocked: "需要重新处理"' in helper
    assert '}[status] || "等待处理";' in helper
    assert f"app.js?v={FRONTEND_VERSION}" in index
    assert f"styles.css?v={FRONTEND_VERSION}" in index


def test_doc247_character_card_ui_excludes_auxiliary_25_degree_face_references() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    module_start = source.index("const v3CharacterCardModuleMeta")
    module_end = source.index("function v3CharacterCardForAsset", module_start)
    module_meta = source[module_start:module_end]
    face_start = module_meta.index("face_identity:")
    expression_start = module_meta.index("expression_set:", face_start)
    face_meta = module_meta[face_start:expression_start]

    assert '"face.front"' in face_meta
    assert '"face.front_three_quarter"' in face_meta
    assert '"face.profile"' in face_meta
    assert '"face.reverse_three_quarter"' in face_meta
    assert '"face.rear_head"' in face_meta
    assert "左前45°" in face_meta
    assert "右前45°" in face_meta
    assert "face.left_front_25" not in face_meta
    assert "face.right_front_25" not in face_meta
    assert "左前25°" not in face_meta
    assert "右前25°" not in face_meta


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
    assert f"styles.css?v={FRONTEND_VERSION}" in index


def test_doc177_project_asset_card_preserves_explicit_binding_and_management_route() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")

    panel = _function(source, "renderV3ProjectVisualAssetPanel", "openV3VisualAssetBindingDialog")
    assert 'textContent = bindings.length ? "管理视觉资产" : "选择视觉资产"' in panel
    assert "openV3VisualAssetLibraryFromBindingDialog" in source
    assert "v3VisualAssetBindingDialog?.open" in source
    assert "v3VisualAssetLibraryDialog?.open" in source
    assert "不使用视觉资产" in index


def test_doc258_visual_asset_library_uses_parallel_asset_cards_not_scroll_pile() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    dialog_start = index.index('id="v3VisualAssetLibraryDialog"')
    binding_dialog_start = index.index('id="v3VisualAssetBindingDialog"', dialog_start)
    library_dialog = index[dialog_start:binding_dialog_start]

    assert 'id="v3VisualAssetLibraryCards"' in library_dialog
    assert "v3-visual-asset-existing-section" in library_dialog
    assert "v3-visual-asset-create-card" in library_dialog
    assert 'data-v3-visual-asset-action="toggle-existing-assets"' in library_dialog
    assert "visualAssetLibraryExistingOpen" in source
    assert "visualAssetLibraryExpandedAssetId" in source
    assert 'data-v3-visual-asset-action="toggle-asset-details"' in source
    assert "v3VisualAssetLibraryCards.hidden = cardOpen" in source
    assert "els.v3CharacterCardWorkspace?.scrollIntoView" not in source
    home = _function(source, "openV3Home", "openV3ProfessionalWorkspace")
    assert 'updateV3Notice("正在后台同步最近项目。", "info")' in home
    assert "waitForV3HomePreviewImages({ blockPage: false })" in home
    assert 'setV3PageLoading(true, "正在同步最近项目"' not in home
    assert "function waitForV3HomePreviewImages({ blockPage = true } = {})" in source
    assert ".v3-visual-asset-library-cards" in css
    assert "grid-template-columns: minmax(320px, 1.05fr) minmax(320px, 0.95fr)" in css
    assert ".v3-visual-asset-library-dialog [hidden]" in css
    assert "display: none !important" in css


def test_doc258_visual_asset_library_hides_archived_cases_from_active_list() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    renderer = _function(source, "renderV3VisualAssetLibrary", "loadV3ProjectVisualAssetBindings")

    assert 'asset?.lifecycle_status !== "archived"' in renderer
    assert "archivedCount" in renderer
    assert "测试/作废资产已归档" in renderer
    assert "visibleAssets.map" in renderer
    assert "assets.map" not in renderer


def test_doc258_lightbox_is_top_layer_dialog_with_close_state_sync() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")
    opener = _function(source, "openImageLightbox", "closeImageLightbox")
    closer = _function(source, "closeImageLightbox", "renderLightboxActions")

    assert '<dialog id="imageLightbox"' in index
    assert "<section id=\"imageLightbox\"" not in index
    assert "els.imageLightbox.showModal()" in opener
    assert "els.imageLightbox.close()" in closer
    assert 'els.imageLightbox.addEventListener("cancel"' in source
    assert ".image-lightbox::backdrop" in css
    assert "z-index: 1200" in css
    assert "releaseV3ScrollLockIfNoModal()" in closer


def test_doc258_friendly_error_sanitizes_public_ui_diagnostics() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    helper_start = source.index("function containsPrivateDiagnostic")
    helper_end = source.index("function jobErrorMessage", helper_start)
    helper = source[helper_start:helper_end]

    assert "function publicSafeErrorText" in helper
    assert 'const publicErrorFallbackMessage = "暂时无法完成，请刷新后重试。"' in source
    for forbidden in ("job_", "mcp_handoff_", "v3_output_", "sha256", "provider", "payload", "prompt", "traceback"):
        assert forbidden in helper
    assert "return publicSafeErrorText(detail?.message || detail?.code || parsed.message || error.message);" in helper


def test_doc258_expression_slots_render_as_uniform_four_card_grid() -> None:
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert '.v3-character-card-module[data-v3-character-card-module="expression_set"] .v3-character-card-slots' in css
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in css
    assert "aspect-ratio: 2 / 3" in css
    assert "object-fit: cover" in css


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
    assert "保存源图并打开人物角色卡" in index
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


def test_doc180_character_card_is_the_single_professional_preparation_surface() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    index = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLES_CSS.read_text(encoding="utf-8")

    assert 'id="v3CharacterCardWorkspace"' in index
    assert 'id="v3CharacterCardModules"' in index
    assert 'id="v3CharacterCardRunAllBtn"' in index
    assert 'id="v3CharacterCardBodyControls"' in index
    assert "const v3CharacterCardModuleOrder = [\"face_identity\", \"expression_set\", \"body_silhouette\"]" in source
    for module in ("face_identity", "expression_set", "body_silhouette"):
        assert f'"{module}"' in source
    for slot in (
        "face.front",
        "face.front_three_quarter",
        "face.profile",
        "face.reverse_three_quarter",
        "face.rear_head",
        "expression.neutral",
        "expression.laugh",
        "expression.anger",
        "expression.sad",
        "body.front_full",
        "body.side_full",
        "body.rear_full",
    ):
        assert slot in source
    assert '["face.front_three_quarter", "左前45°"]' in source
    assert '["face.reverse_three_quarter", "右前45°"]' in source
    assert "正面、左前45°、右前45°和侧面90°等固定参考" in source
    assert 'body: { stage: "body_silhouette"' not in source
    assert 'character-card/prepare' in source
    assert 'character-card/activate' in source
    activate = _function(source, "activateV3CharacterCardModule", "runNextV3CharacterCardModule")
    assert 'body: { module, confirm_activation: true }' in activate
    assert "activateV3VisualAsset(assetId)" not in activate
    assert "function startV3CharacterCardRunAll" in source
    assert "function openV3CharacterCard" in source
    assert "function closeV3CharacterCard" in source
    assert ".v3-character-card-workspace" in css
    assert ".v3-character-card-slot-placeholder" in css
    assert "v3State.characterCardRunAll" in source


def test_doc233_frontend_prepares_next_missing_expression_slot_from_partial_state() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert "function v3CharacterCardNextExpressionSlot" in source
    assert "const expression = v3CharacterCardNextExpressionSlot(card);" in source
    assert "payload.expression = expression;" in source
    assert '["expression.laugh", "laugh"]' in source
    assert '["expression.anger", "anger"]' in source
    assert '["expression.sad", "sad"]' in source
    assert 'preparedStatus === "partial"' in source
    assert "preparedCard?.last_failed_module === module" in source
    assert "&& !failed" in source


def test_doc180_character_card_media_projection_is_server_owned_and_non_secret() -> None:
    handlers = HANDLERS.read_text(encoding="utf-8")
    assert '"preview_url"' in handlers
    assert '"download_url"' in handlers
    helper_start = handlers.index("def _visual_asset_public_record")
    helper_end = handlers.index("    @staticmethod\n    def _project_visual_asset_binding_public_record", helper_start)
    helper = handlers[helper_start:helper_end]
    for forbidden in ('"prompt"', '"provider"', '"source_path"', '"candidate"', '"review_body"'):
        assert forbidden not in helper.lower()


def test_doc193_people_asset_public_projection_hides_current_mcp_handoff_on_card() -> None:
    handlers = HANDLERS.read_text(encoding="utf-8")
    helper_start = handlers.index("def _people_asset_public_record")
    helper_end = handlers.index("    def post_project_people_asset_prepare", helper_start)
    helper = handlers[helper_start:helper_end]

    assert "pending_mcp_handoff_ids" not in helper


def test_doc177_linear_failure_projection_distinguishes_brain_unavailable_from_quality_failure() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    handlers = HANDLERS.read_text(encoding="utf-8")

    assert "function v3VisualAssetPreparationFailureMessage" in source
    assert "remote_brain_unavailable" in source
    assert "preparedAsset?.lifecycle_status === \"blocked\"" in source
    assert '"failure_code"' in handlers
