"""Doc174 contracts for the V3 Standard / Professional workspace split.

These are source-level browser contracts.  They deliberately protect the
information architecture without prescribing any local prompt construction or
specialized generation path.
"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
APP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
INDEX_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
DOC173 = ROOT / "alchemy_creative_agent_3_0" / "docs" / "173_V3_VISUAL_ASSET_LIBRARY_FIRST_PROFESSIONAL_WORKSPACE_RECONSTRUCTION_SPEC.md"
DOC174 = ROOT / "alchemy_creative_agent_3_0" / "docs" / "174_V3_STANDARD_AND_PROFESSIONAL_WORKSPACE_NAVIGATION_SPEC.md"


def _function(source: str, name: str, next_name: str) -> str:
    start = source.index(f"function {name}")
    end = source.index(f"function {next_name}", start)
    return source[start:end]


def test_doc174_replaces_only_doc173_frontend_navigation_authority() -> None:
    doc173 = DOC173.read_text(encoding="utf-8")
    doc174 = DOC174.read_text(encoding="utf-8")

    assert "Doc174" in doc173
    assert "VisualAssetBindingSet" in doc174
    assert "Provider" in doc174


def test_doc174_v3_title_menu_exposes_explicit_standard_and_professional_entries() -> None:
    index = INDEX_HTML.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")

    assert 'id="v3WorkspaceMenu"' in index
    assert 'id="v3WorkspaceMenuBtn"' in index
    assert 'data-v3-workspace-entry="standard"' in index
    assert 'data-v3-workspace-entry="professional"' in index
    assert "function setV3WorkspaceMode(" in source
    assert "function setV3WorkspaceMenuOpen(" in source
    assert '"standard"' in source
    assert '"professional"' in source


def test_doc174_keeps_standard_surface_free_of_visual_asset_controls() -> None:
    index = INDEX_HTML.read_text(encoding="utf-8")

    standard_start = index.index('id="v3StandardHomeSurface"')
    standard_end = index.index('id="v3ProfessionalHomeSurface"', standard_start)
    standard = index[standard_start:standard_end]
    assert 'class="v3-standard-home-surface"' in standard
    assert "v3VisualAssetLibrary" not in standard
    assert 'id="v3VisualAssetLibraryPanel"' not in standard
    assert "视觉资产库" not in standard
    assert 'id="v3ProjectVisualAssetPanel"' not in standard


def test_doc174_professional_surface_owns_library_then_project_hub_slot() -> None:
    index = INDEX_HTML.read_text(encoding="utf-8")

    professional_start = index.index('id="v3ProfessionalHomeSurface"')
    workspace_start = index.index('id="v3WorkspaceView"', professional_start)
    professional = index[professional_start:workspace_start]
    assert 'id="v3VisualAssetLibraryPanel"' in professional
    assert 'id="v3ProfessionalProjectHubSlot"' in professional
    assert professional.index('id="v3VisualAssetLibraryPanel"') < professional.index('id="v3ProfessionalProjectHubSlot"')


def test_doc174_only_professional_projects_offer_project_asset_binding() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    panel = _function(source, "renderV3ProjectVisualAssetPanel", "openV3VisualAssetBindingDialog")
    create = _function(source, "createV3Project", "renderV3Projects")

    assert "v3ProjectUsesProfessionalWorkspace" in panel
    assert "v3_workspace:" in create
    assert 'v3State.workspaceMode === "professional"' in create
    assert "professional_mode:" not in create
    assert "people_asset_id" not in create


def test_doc174_project_lists_and_opened_projects_restore_workspace_truth() -> None:
    source = APP_JS.read_text(encoding="utf-8")
    render = _function(source, "renderV3Projects", "handleV3ProjectClick")
    open_project = _function(source, "openV3Project", "renderV3ProjectOpeningState")

    assert "v3ProjectUsesProfessionalWorkspace" in render
    assert "setV3WorkspaceMode" in open_project
    assert "workspaceMode" in source


def test_doc174_workspace_route_links_preserve_the_selected_workspace() -> None:
    source = APP_JS.read_text(encoding="utf-8")

    assert 'const v3HomeHref = professional ? "/creative-agent-v3?workspace=professional"' in source
    assert 'document.querySelectorAll("[data-v3-route-link]")' in source
    assert 'v3VisualAssetLibraryPanel: document.querySelector("#v3VisualAssetLibraryPanel")' in source
    assert "els.v3VisualAssetLibraryPanel.hidden = !professional" in source
