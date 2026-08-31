"""E23 browser-surface and request-boundary regression contracts.

These checks deliberately inspect the public V3 source surface.  They protect
the E-Commerce beginner flow without adding a second planner, provider, review
or delivery implementation.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
MOBILE_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
MOBILE_HTML = ROOT / "src_skeleton" / "app" / "mobile_static" / "index.html"


def _section(source: str, start: str, end: str) -> str:
    after_start = source.split(start, 1)[1]
    return after_start.split(end, 1)[0]


def test_e23_ecommerce_new_task_surface_keeps_the_default_path_simple() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    ecommerce = _section(html, '<div id="v3EcommerceFields"', '<section id="v3PhotographerProfileFields"')

    assert 'id="v3EcommerceAdvanced"' in ecommerce
    assert ecommerce.index('id="v3EcommerceAdvanced"') < ecommerce.index('id="v3EcommercePlatformInput"')
    assert 'id="v3EcommerceSellingPointsInput"' in ecommerce
    assert "店铺视觉感受不会当作商品卖点或宣传承诺" in ecommerce
    for legacy_control in ("v3EcommerceSuiteScopeInput", "v3EcommerceOverlayCopyInput", "data-v3-preset-scope=\"ecommerce\""):
        assert legacy_control not in ecommerce


def test_e23_ecommerce_catalog_compatibility_copy_does_not_render_legacy_server_description() -> None:
    script = APP_JS.read_text(encoding="utf-8")

    assert "function v3TemplateDisplayDescription(template)" in script
    assert 'template?.template_id === "ecommerce_template"' in script
    assert "每张图片都按本次需求单独整理" in script
    assert "v3TemplateDisplayDescription(template)" in _section(script, "function renderV3HomeTemplateChooser", "function renderV3SelectedBrandMemoryBar")


def test_e23_ecommerce_count_control_projects_the_exact_shared_contract() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    script = APP_JS.read_text(encoding="utf-8")
    count_control = _section(html, '<label class="v3-setting-control v3-count-control"', '<div class="v3-setting-control v3-aspect-control">')

    assert '<select id="v3CountInput"' in count_control
    assert 'type="range"' not in count_control
    assert [f'<option value="{count}"' in count_control for count in (1, 2, 4, 7)] == [True, True, True, True]
    assert "const v3EcommerceExactCountContract = Object.freeze([1, 2, 4, 7]);" in script
    assert "不支持时会明确提示，不会少生成" in script
    assert "return Math.max(1, Math.min(4, number));" not in script


def test_e23_count_projection_does_not_depend_on_or_enrich_catalog_fallback_cards() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    projection = _section(script, "function v3DeclaredGenerationCounts", "function v3BoundedGenerationCount")
    assert "v3LoadedTemplateById(templateId)" in projection
    assert "v3TemplateById(templateId)" not in projection
    assert "function v3DefaultTemplateCards" not in script
    assert "generation_count_contract: [1, 2, 4, 7]" not in script


def test_e23_mobile_ecommerce_count_control_preserves_exact_n_without_general_clamping() -> None:
    html = MOBILE_HTML.read_text(encoding="utf-8")
    script = MOBILE_JS.read_text(encoding="utf-8")
    count_control = _section(html, '<span>生成数量 <strong id="mobileV3CountValue">', '</label>')
    bounded = _section(script, "function mobileV3BoundedCount", "function syncMobileV3GenerationCountControl")
    supported = _section(script, "function mobileV3SupportedGenerationCounts", "function mobileV3BoundedCount")
    job_payload = _section(script, "function buildMobileV3JobPayload", "function mobileV3SizeLabel")

    assert '<select id="mobileV3CountInput"' in count_control
    assert 'type="range"' not in count_control
    assert [f'<option value="{count}"' in count_control for count in (1, 2, 4, 7)] == [True, True, True, True]
    assert "const mobileV3EcommerceExactCountContract = Object.freeze([1, 2, 4, 7]);" in script
    assert 'templateId === "ecommerce_template"' in supported
    assert 'templateId === "photographer_template"' in supported
    assert 'mobileV3State.selectedPreset === "professional_set" ? [3] : [1]' in supported
    assert "Math.max(1, Math.min(4" not in bounded
    assert 'throw new Error(`当前模板支持 ${supported.join("、")} 张，请重新选择。`);' in bounded
    assert "请确认数量后再提交。" in script
    assert "mobileV3BoundedCount(" in job_payload


def test_e23_visual_tone_and_confirmed_selling_points_have_separate_payload_fields() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    profile = _section(script, "function v3EcommerceProfilePatch()", "function v3BoundedGenerationCount(")
    payload = _section(script, "function buildV3JobPayload(", "async function createV3Job()")

    assert "v3EcommerceSellingPointsInput" in profile
    assert "core_selling_points: sellingPoints" in profile
    assert "v3BrandToneInput" not in profile
    assert "visual_tone: brandTone || undefined" in payload


def test_e23_result_board_only_renders_final_images_without_legacy_recipe_or_slot_titles() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    board = _section(script, "function renderV3ResultBoard(job)", "function v3OutputImageCandidates(item)")

    assert "job?.ecommerce?.image_recipes" not in board
    assert "metadata.ecommerce_slot" not in board
    assert "item.slot" not in board
    assert "? `图片 ${index + 1}`" in board
    assert "v3DeliveryDisplayItems(visibleItems)" in board
    assert "需要确认" in board
    assert "重新加载图片" in board


def test_e23_result_board_hydrates_same_job_project_delivery_when_job_snapshot_has_no_items() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    board = _section(script, "function renderV3ResultBoard(job)", "function v3OutputImageCandidates(item)")
    current_items = _section(script, "function v3CurrentJobImageItems", "function v3ReviewCertification")
    stored_items = _section(script, "function v3StoredProjectOutputItems", "function v3StoredProjectReviewOutputItems")

    assert "const persistedItems = v3ProjectOutputsForJob(job?.job_id);" in board
    assert "const hasPersistedDelivery = persistedItems.some((item) => v3OutputVisibleInProject(item));" in board
    assert "!v3JobDeliverySettled(job) && !hasPersistedDelivery" in board
    assert "const persisted = v3ProjectOutputsForJob(job?.job_id);" in current_items
    assert "item?.metadata?.project_id" in stored_items


def test_e23_continuation_selection_does_not_promote_raw_job_candidates_to_delivery() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    helper = _section(script, "function v3AuthoritativeJobDeliveryItems", "function v3ReviewCertification")
    board = _section(script, "function renderV3ResultBoard(job)", "function v3OutputImageCandidates(item)")
    current_items = _section(script, "function v3CurrentJobImageItems", "function v3ReviewCertification")

    assert "return persisted.length" in helper
    assert "? persisted" in helper
    assert "const deliveryItems = v3AuthoritativeJobDeliveryItems(source, persisted);" in current_items
    assert "const deliveryItems = v3AuthoritativeJobDeliveryItems(rawItems, persistedItems);" in board
    assert "const combined = [...source, ...persisted];" not in current_items
    assert "const visibleItems = [...rawItems, ...persistedItems]" not in board


def test_v3_project_opening_without_current_job_keeps_result_board_renderable() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    current_items = _section(script, "function v3CurrentJobImageItems", "function v3ReviewCertification")

    assert "if (!job) return [];" in current_items


def test_v3_output_download_uses_authenticated_binary_fetch_instead_of_bare_link() -> None:
    desktop = APP_JS.read_text(encoding="utf-8")
    mobile = MOBILE_JS.read_text(encoding="utf-8")
    desktop_download = _section(desktop, "async function downloadV3Output", "async function loadV2TemplateBootstrap")
    desktop_result_board = _section(desktop, "function renderV3ResultBoard(job)", "function v3OutputImageCandidates(item)")
    mobile_download = _section(mobile, "async function downloadImageFile", "function showDownloadStartHint")

    assert "data-v3-download-url" in desktop_result_board
    assert "target=\"_blank\"" not in desktop_result_board
    assert "return downloadImageFile(url, \"\", button);" in desktop_download
    assert 'credentials: "include"' in mobile_download
    assert "getVeyraToken()" in mobile_download
    assert "URL.createObjectURL(blob)" in mobile_download
    assert "handleVeyraUnauthorized()" in mobile_download


def test_e23_next_actions_restore_human_recovery_for_blocked_held_and_completed_work() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    actions = _section(script, "function renderV3ProjectNextActions()", "function renderV3BrandMemoryPanel()")

    assert 'els.v3ProjectNextActions.hidden = false;' in actions
    assert "v3ProjectCurrentOperation(project)" in actions
    assert "operation?.state === \"failed_no_delivery\"" in actions
    assert '"edit_ecommerce_details"' in actions
    assert '"upload_reference_continue"' in actions
    assert '"start_first_generation"' in actions
    assert '"show_project_results"' in actions
    assert '"return_to_project"' in actions
    assert "生成第一组套图" not in actions


def test_e23_ecommerce_project_reference_surface_consumes_server_view() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    payload_sync = _section(script, "function syncV3ProjectResponseMetadata", "function syncV3ProjectOutputsFromPayload")
    groups = _section(script, "function v3ProjectReferenceGroups", "function v3UsefulReferenceItems")
    renderer = _section(script, "function renderV3EcommerceProjectViewReferences", "async function handleV3ReferenceBoardClick")

    assert "ecommerce_project_view" in payload_sync
    assert "current_operation" in payload_sync
    assert "v3EcommerceProjectReferenceGroups(project)" in groups
    assert "if (ecommerceGroups) return ecommerceGroups;" in groups
    assert "v3EcommerceProjectView(project)" in renderer
    assert "renderV3EcommerceProjectViewReferences(project, ecommerceView)" in renderer
    assert "original_product_inputs" in renderer
    assert "locked_person_identity" in renderer
    assert "selected_continuation_directions" in renderer
    assert "generated_and_review_history" in renderer
    assert "项目成片不会进入原始商品图" in renderer


def test_e23_mobile_ecommerce_reference_surface_consumes_server_view() -> None:
    script = MOBILE_JS.read_text(encoding="utf-8")
    metadata_sync = _section(script, "function mobileV3ProjectWithResponseMetadata", "async function loadMobileV3Projects")
    groups = _section(script, "function mobileV3ProjectReferenceGroups", "function mobileV3UsefulReferences")
    renderer = _section(script, "function renderMobileV3EcommerceProjectViewReferences", "async function selectMobileV3OutputItem")

    assert "ecommerce_project_view" in metadata_sync
    assert "mobileV3EcommerceProjectReferenceGroups(project)" in groups
    assert "if (ecommerceGroups) return ecommerceGroups;" in groups
    assert "renderMobileV3EcommerceProjectViewReferences(project, ecommerceView)" in renderer
    assert "original_product_inputs" in renderer
    assert "locked_person_identity" in renderer
    assert "selected_continuation_directions" in renderer
    assert "generated_and_review_history" in renderer
    assert "项目成片不会进入原始商品图" in renderer


def test_e23_local_product_truth_binding_failure_has_actionable_browser_copy() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    failure_section = _section(script, "function v3EcommerceFailureMessage", "function v3RemoteCreativeBrainFailureMessage")

    assert "ecommerce_product_truth_pool_mismatch" in failure_section
    assert r"\u5c1a\u672a\u53d1\u9001\u751f\u56fe\u8bf7\u6c42" in failure_section
    assert "provider_unavailable" not in failure_section.split("ecommerce_product_truth_pool_mismatch", 1)[0]


def test_e23_ecommerce_copy_does_not_promise_a_fixed_listing_suite() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    home_function = _section(script, "function v3HomeTemplateCopy", "function selectV3HomeTemplate")
    workspace_function = _section(script, "function v3ScenarioWorkspaceCopy", "function setV3Scenario")
    workflow_function = _section(script, "function renderV3ProjectWorkflow", "function v3WorkflowArtifact")

    assert "适合商品主图、卖点图、详情页配图和上架套图" not in home_function
    assert "生成清爽高级的电商主图和详情页套图" not in home_function
    assert "继续做一组夏季新品电商套图" not in workspace_function
    assert "套图正在准备" not in workspace_function
    assert "主图、卖点图、场景图、细节图和信任图" not in workflow_function
    assert "规划套图" not in workflow_function
    assert "生成第一组电商图片" not in script
    assert "继续生成电商图片" not in script
