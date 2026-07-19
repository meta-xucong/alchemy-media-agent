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


def test_e23_next_actions_restore_human_recovery_for_blocked_held_and_completed_work() -> None:
    script = APP_JS.read_text(encoding="utf-8")
    actions = _section(script, "function renderV3ProjectNextActions()", "function renderV3BrandMemoryPanel()")

    assert 'els.v3ProjectNextActions.hidden = false;' in actions
    assert '"edit_ecommerce_details"' in actions
    assert '"upload_reference_continue"' in actions
    assert '"start_first_generation"' in actions
    assert '"show_project_results"' in actions
    assert '"return_to_project"' in actions
    assert "生成第一组套图" not in actions


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
