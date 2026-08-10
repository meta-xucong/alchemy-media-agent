"""Static contracts for Doc261 project reference authority presentation."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "261_V3_PROJECT_REFERENCE_AUTHORITY_AND_CONTINUATION_UX_CONTRACT.md"
DESKTOP_INDEX = ROOT / "src_skeleton" / "app" / "static" / "index.html"
DESKTOP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
DESKTOP_CSS = ROOT / "src_skeleton" / "app" / "static" / "styles.css"
MOBILE_INDEX = ROOT / "src_skeleton" / "app" / "mobile_static" / "index.html"
MOBILE_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
MOBILE_CSS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.css"


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def test_doc261_records_the_source_truth_and_continuation_split() -> None:
    text = DOC.read_text(encoding="utf-8")

    assert "source_type=uploaded" in text
    assert "source_type=generated_selected" in text
    assert "Original input references" in text
    assert "Selected continuation directions" in text
    assert "cannot override uploaded source truth or a bound visual asset" in text


def test_doc261_desktop_groups_uploaded_inputs_and_generated_continuations() -> None:
    index = DESKTOP_INDEX.read_text(encoding="utf-8")
    source = DESKTOP_JS.read_text(encoding="utf-8")
    css = DESKTOP_CSS.read_text(encoding="utf-8")
    source_type = _function(source, "v3ReferenceSourceType", "v3ReferenceContinuationIdentity")
    groups = _function(source, "v3ProjectReferenceGroups", "v3UsefulReferenceItems")
    compatibility = _function(source, "v3UsefulReferenceItems", "v3ReferenceImageCandidates")
    board = _function(source, "renderV3UsefulReferences", "handleV3ReferenceBoardClick")
    output_board = _function(source, "renderV3ProjectOutputBoard", "handleV3ProjectOutputBoardClick")
    snapshot = _function(source, "renderV3ProjectSnapshot", "renderV3ProjectVisualAssetPanel")
    project_summary = _function(source, "v3ProjectSummaryFromProject", "v3ProjectEmptyImageLabel")
    production = _function(source, "renderV3ProductionEntry", "renderV3StepCards")
    scene_stats = _function(source, "v3SceneStats", "renderV3SceneRows")
    brief = _function(source, "renderV3BriefScene", "renderV3ReviewScene")

    assert 'id="v3ProjectReferencePanel"' in index
    assert "本次生成依据与延续方向" in index
    assert "项目成果" in index
    assert 'source_type === "generated_selected"' in source_type
    assert "original_inputs" in groups
    assert "continuation_outputs" in groups
    assert "uploaded_product_digests" in groups
    assert "原始参考图" in board
    assert "已选延续方向" in board
    assert "不再作为生成依据" in board
    assert "取消沿用" in board
    assert "refs.slice(0, 6)" not in board
    assert "items.slice(0, 6)" not in output_board
    assert "reviewItems.slice(0, 24)" not in output_board
    assert "设为延续方向" in source
    assert "从项目成果移除" in source
    assert "不会删除服务器中的图片文件或项目历史" in source
    assert "原始参考图和已选延续方向" in source
    assert "已确认参考" not in source
    assert "if (activeReferences.length) return activeReferences;" in compatibility
    assert ".v3-project-reference-group" in css
    assert "v3ReferenceContentDigest" in source
    assert "uploaded_product_digests" in groups
    assert "referenceGroups.continuation_outputs" in project_summary
    assert "continuationThumbs" in project_summary
    assert "原始参考图" in snapshot
    assert "延续方向" in snapshot
    assert "originalCount" in production
    assert "continuationCount" in production
    assert "referenceGroups.continuation_outputs" in scene_stats
    assert "originalRefs.length" in brief


def test_doc261_mobile_keeps_the_same_reference_groups_visible() -> None:
    index = MOBILE_INDEX.read_text(encoding="utf-8")
    source = MOBILE_JS.read_text(encoding="utf-8")
    css = MOBILE_CSS.read_text(encoding="utf-8")
    source_type = _function(source, "mobileV3ReferenceSourceType", "mobileV3ReferenceContinuationIdentity")
    groups = _function(source, "mobileV3ProjectReferenceGroups", "mobileV3UsefulReferences")
    compatibility = _function(source, "mobileV3UsefulReferences", "mobileV3ReferenceThumb")
    board = _function(source, "renderMobileV3ReferenceBoard", "renderMobileV3Timeline")
    select_output = _function(source, "selectMobileV3OutputItem", "removeMobileV3OutputFromProject")
    remove_output = _function(source, "removeMobileV3OutputFromProject", "removeMobileV3ProjectReference")
    remove_reference = _function(source, "removeMobileV3ProjectReference", "renderMobileV3Timeline")

    assert "本次生成依据与延续方向" in index
    assert 'id="mobileV3ReferenceCount"' in index
    assert 'source_type === "generated_selected"' in source_type
    assert "original_inputs" in groups
    assert "continuation_outputs" in groups
    assert "uploaded_product_digests" in groups
    assert "mobileV3ReferenceContentDigest" in groups
    assert "原始参考图" in board
    assert "已选延续方向" in board
    assert "data-mobile-v3-reference-action" in board
    assert "refs.slice(0, 6)" not in board
    assert "reviewItems.slice(0, 8)" not in source
    assert "processItems.slice(0, 24)" not in source
    assert "if (active.length) return active;" in compatibility
    assert "data-mobile-v3-output-action" in source
    assert "/jobs/${encodeURIComponent(jobId)}/select" in select_output
    assert "/outputs/${encodeURIComponent(outputId)}/unselect" in remove_output
    assert "/references/${encodeURIComponent(referenceId)}/remove" in remove_reference
    assert "不会删除服务器中的图片文件或项目历史" in remove_output
    assert "已确认参考" not in source
    assert ".v3-mobile-reference-group" in css
    assert ".v3-mobile-reference-actions" in css
    assert ".v3-mobile-output-actions" in css


def test_doc261_preserves_visual_assets_and_review_only_separation() -> None:
    desktop_index = DESKTOP_INDEX.read_text(encoding="utf-8")
    desktop_source = DESKTOP_JS.read_text(encoding="utf-8")
    mobile_source = MOBILE_JS.read_text(encoding="utf-8")

    assert 'id="v3ProjectVisualAssetPanel"' in desktop_index
    assert "未通过正式交付的图片，仅供查看，不能设为后续参考" in desktop_source
    assert "这些图片没有进入首页正式预览，也不能设为后续参考。" in mobile_source
