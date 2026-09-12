"""Regression contracts for the local V3 project-surface repair."""

from pathlib import Path

from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
DESKTOP_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
DESKTOP_CSS = ROOT / "src_skeleton" / "app" / "static" / "styles.css"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "300_V3_LOCAL_PROJECT_PAGING_AND_STANDARD_WORKSPACE_SURFACE_REPAIR_SPEC.md"


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def _project(workspace: str) -> ProjectRecord:
    return ProjectRecord(
        project_id=f"project-{workspace}",
        title="Project",
        user_goal="goal",
        short_summary="summary",
        created_at="2026-09-12T00:00:00+00:00",
        updated_at="2026-09-12T00:00:00+00:00",
        metadata={"v3_workspace": workspace},
    )


def test_project_summary_projects_only_safe_workspace_metadata() -> None:
    service = object.__new__(V3ProjectModeService)
    service._selected_output_state_map = lambda _project: {}
    service._style_chips = lambda _project: []
    service._scenario_id_for_template = lambda _template_id: "general_creative"
    service._template_label = lambda _template_id: "通用模板"

    professional = service._lightweight_memory_summary(_project("professional"))
    standard = service._lightweight_memory_summary(_project("unexpected"))

    assert professional.metadata == {"v3_workspace": "professional"}
    assert standard.metadata == {"v3_workspace": "standard"}


def test_desktop_standard_project_entry_hides_asset_surface_during_and_after_loading() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    index = DESKTOP_HTML.read_text(encoding="utf-8")
    styles = DESKTOP_CSS.read_text(encoding="utf-8")
    view_state = _function(source, "renderV3ViewState", "v3ScenarioCanCreate")
    opening = _function(source, "openV3Project", "syncV3ProjectDetailInBackground")
    panel = _function(source, "renderV3ProjectVisualAssetPanel", "bindV3ContinueProfessionalProjectButton")

    assert 'id="v3ProjectVisualAssetPanel"' in index
    assert 'id="v3ProjectVisualAssetPanel" class="v3-project-visual-asset-panel" aria-label="本项目的视觉资产" hidden' in index
    assert "renderV3ProjectVisualAssetPanel();" in view_state
    assert "v3State.currentProject = null;" in opening
    assert "renderV3ViewState();" in opening
    assert "closeV3VisualAssetBindingDialog();" in opening
    assert "closeV3VisualAssetLibraryDialog();" in opening
    assert "professionalSurface" in panel
    assert "const shouldShow = Boolean(project?.project_id && professionalProject && professionalSurface);" in panel
    assert "panel.hidden = !shouldShow;" in panel
    assert 'if (v3State.workspaceMode !== "professional") return;' in source
    assert ".v3-project-visual-asset-panel[hidden]" in styles
    assert "display: none !important;" in styles


def test_workspace_filtered_lists_keep_pagination_when_a_page_has_no_visible_items() -> None:
    desktop = DESKTOP.read_text(encoding="utf-8")
    mobile = MOBILE.read_text(encoding="utf-8")
    desktop_projects = _function(desktop, "renderV3Projects", "renderV3History")
    desktop_history = _function(desktop, "renderV3History", "renderV3HeroHistory")
    mobile_projects = _function(mobile, "renderMobileV3ProjectCards", "handleMobileV3Click")

    assert "items.length === 0 && !v3State.projectsHasMore" in desktop_projects
    assert "v3State.projectsHasMore || items.length > v3State.projectRenderLimit" in desktop_projects
    assert "groups.length === 0 && !v3State.projectsHasMore" in desktop_history
    assert "v3State.projectsHasMore || groups.length > visibleGroups.length" in desktop_history
    assert "groups.length === 0 && !mobileV3State.projectsHasMore" in mobile_projects
    assert "mobileV3State.projectsHasMore || groups.length > visibleGroups.length" in mobile_projects


def test_load_more_expands_cached_items_and_resets_loading_button_state() -> None:
    desktop = DESKTOP.read_text(encoding="utf-8")
    mobile = MOBILE.read_text(encoding="utf-8")
    desktop_loader = _function(desktop, "loadV3Projects", "loadV3History")
    desktop_window = _function(desktop, "expandV3ProjectRenderWindow", "v3ProjectTime")
    mobile_loader = _function(mobile, "loadMobileV3Projects", "setMobileV3LoadingLayer")
    mobile_window = _function(mobile, "expandMobileV3ProjectRenderWindow", "mobileV3ProjectWithResponseMetadata")

    assert "expandV3ProjectRenderWindow()" in desktop_loader
    assert "v3State.projectsLoadingMore = false;" in desktop
    assert "renderV3History();" in desktop_loader
    assert "renderV3HeroHistory();" in desktop
    assert "loadedHistoryCount = v3ProjectImageGroups().length" in desktop_window

    assert "expandMobileV3ProjectRenderWindow()" in mobile_loader
    assert "mobileV3State.projectsLoadingMore = false;" in mobile
    assert "renderMobileV3ProjectCards();" in mobile_loader
    assert "loadedHistoryCount = mobileV3ProjectGroupsFromProjects().length" in mobile_window


def test_load_more_can_expand_cached_items_before_initial_request_guard() -> None:
    desktop = DESKTOP.read_text(encoding="utf-8")
    mobile = MOBILE.read_text(encoding="utf-8")
    desktop_loader_start = desktop.index("async function loadV3Projects")
    desktop_guard = desktop.index("if (v3State.projectsLoading || v3State.projectsLoadingMore)", desktop_loader_start)
    desktop_expand = desktop.index("expandV3ProjectRenderWindow()", desktop_loader_start)
    mobile_loader_start = mobile.index("async function loadMobileV3Projects")
    mobile_guard = mobile.index("if (mobileV3State.loading || mobileV3State.projectsLoadingMore)", mobile_loader_start)
    mobile_expand = mobile.index("expandMobileV3ProjectRenderWindow()", mobile_loader_start)

    assert desktop_expand < desktop_guard
    assert mobile_expand < mobile_guard
    assert "项目仍在同步，请稍后再加载更多。" in desktop
    assert "项目仍在同步，请稍后再加载更多。" in mobile


def test_desktop_does_not_load_project_asset_bindings_for_standard_projects() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    background = _function(source, "syncV3ProjectDetailInBackground", "renderV3ProjectOpeningState")
    summary = _function(source, "v3ProjectSummaryFromProject", "v3ProjectEmptyImageLabel")

    assert "const visualAssetTask" in background
    assert "v3ProjectUsesProfessionalWorkspace(v3State.currentProject)" in background
    assert "Promise.resolve([])" in background
    assert "project.memory_summary?.project_id" in summary
    assert 'metadata: { v3_workspace: v3ProjectWorkspace(project) }' in summary

    create = _function(source, "createV3Project", "renderV3Projects")
    bindings = _function(source, "loadV3ProjectVisualAssetBindings", "v3AssetNameForBinding")
    assert 'if (v3State.workspaceMode === "professional") {' in create
    assert 'v3State.workspaceMode !== "professional"' in bindings


def test_mobile_asset_surfaces_are_professional_only() -> None:
    source = MOBILE.read_text(encoding="utf-8")
    library = _function(source, "openMobileV3VisualAssetLibrary", "openMobileV3VisualAssetCreate")
    create = _function(source, "openMobileV3VisualAssetCreate", "openMobileV3VisualAssetDetail")
    detail = _function(source, "openMobileV3VisualAssetDetail", "mobileV3CharacterCardModuleAction")

    assert library.count('mobileV3State.workspaceMode !== "professional"') == 1
    assert create.count('mobileV3State.workspaceMode !== "professional"') == 1
    assert detail.count('mobileV3State.workspaceMode !== "professional"') == 1


def test_mobile_project_lists_and_opened_projects_use_persisted_workspace_truth() -> None:
    source = MOBILE.read_text(encoding="utf-8")
    detail = _function(source, "openMobileV3ProjectDetail", "mobileV3InvalidateProjectDetail")
    refresh = _function(source, "refreshMobileV3ProjectDetail", "renderMobileV3ProjectOutputs")
    groups = _function(source, "mobileV3ProjectGroupsFromProjects", "mobileV3VisibleProjects")

    assert "function mobileV3ProjectUsesProfessionalWorkspace(project)" in source
    assert "setMobileV3WorkspaceMode(" in detail
    assert "setMobileV3WorkspaceMode(" in refresh
    assert "mobileV3ProjectUsesProfessionalWorkspace(project) === professional" in groups
    assert "mobileV3ProjectCountLabel" in source
    assert "projectsPayload.total" in source
    assert "data-mobile-v3-load-more-projects" in source


def test_doc300_records_the_two_authoritative_boundaries() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "`total`" in doc
    assert "metadata.v3_workspace" in doc
    assert "must never expose the project visual-asset" in doc
    assert "does not increase the page size" in doc
