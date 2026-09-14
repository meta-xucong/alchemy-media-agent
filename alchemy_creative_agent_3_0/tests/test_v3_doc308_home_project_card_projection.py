import inspect
from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.project_mode import V3ProjectModeService
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)


ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
MAIN = ROOT / "src_skeleton" / "app" / "main.py"
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "308_V3_HOME_PROJECT_CARD_PROJECTION_REPAIR_SPEC.md"


def _project(project_id: str, *, updated_at: str) -> SimpleNamespace:
    return SimpleNamespace(project_id=project_id, status="active", updated_at=updated_at)


def _preview_service(projects: list[SimpleNamespace]) -> V3ProjectModeService:
    service = object.__new__(V3ProjectModeService)
    service.project_store = SimpleNamespace(
        list_projects=lambda limit: list(projects),
        list_all_projects=lambda: list(projects),
    )
    service._project_visible_to_owner = lambda project, _owner: project.project_id != "hidden"
    service._project_output_read_snapshot = lambda *_args, **_kwargs: {
        "records_by_project": {},
        "records_by_job": {},
        "job_status_by_id": {},
        "job_record_by_id": {},
    }
    service._project_delivery_preview_items = lambda project, **_kwargs: [
        {
            "project_id": project.project_id,
            "output_id": f"output-{project.project_id}",
            "created_at": project.updated_at,
            "thumbnail_url": f"http://image.test/{project.project_id}.png",
        }
    ]
    service._metadata = lambda: {"service": "test"}
    return service


def test_scoped_home_preview_returns_only_requested_visible_projects() -> None:
    projects = [
        _project("outside-page", updated_at="2026-09-14T00:03:00Z"),
        _project("page-project", updated_at="2026-09-14T00:02:00Z"),
        _project("hidden", updated_at="2026-09-14T00:01:00Z"),
    ]
    service = _preview_service(projects)

    response = service.list_project_outputs(
        limit=9,
        owner_user_id=7,
        compact=True,
        surface="home_preview",
        project_ids=["page-project", "hidden", "missing"],
    )

    assert [item["project_id"] for item in response["items"]] == ["page-project"]
    assert response["metadata"]["surface"] == "home_preview"
    assert response["metadata"]["complete"] is False


def test_empty_explicit_home_preview_scope_does_not_fall_back_to_global_scan() -> None:
    service = _preview_service([_project("outside-page", updated_at="2026-09-14T00:03:00Z")])

    response = service.list_project_outputs(
        limit=9,
        compact=True,
        surface="home_preview",
        project_ids=[],
    )

    assert response["items"] == []


def test_omitted_home_preview_scope_keeps_global_compatibility() -> None:
    service = _preview_service([
        _project("first", updated_at="2026-09-14T00:03:00Z"),
        _project("second", updated_at="2026-09-14T00:02:00Z"),
    ])

    response = service.list_project_outputs(limit=2, compact=True, surface="home_preview")

    assert {item["project_id"] for item in response["items"]} == {"first", "second"}


def test_route_handler_exposes_additive_project_id_scope() -> None:
    parameters = inspect.signature(V3ProductRouteHandlers.get_project_outputs).parameters
    assert "project_ids" in parameters
    route = MAIN.read_text(encoding="utf-8")
    assert "project_ids: str | None = None" in route
    assert "str(project_ids).split(\",\")" in route
    assert "requested_project_ids" in route


def test_desktop_contract_scopes_and_appends_home_previews() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    loader = source.split("async function loadV3ProjectOutputs", 1)[1].split(
        "function clearV3PendingUploads", 1
    )[0]
    projects = source.split("async function loadV3Projects", 1)[1].split(
        "async function loadV3History", 1
    )[0]

    assert "projectIds = null" in loader
    assert "appendHomePreview" in loader
    assert "project_ids=" in loader
    assert "mergeV3HomePreviewItems" in loader
    assert "projectIds: firstPageProjectIds" in source
    assert "projectIds: previewProjectIds" in projects
    assert "appendHomePreview: requestingMore" in projects
    assert "image count" not in source.lower()
    assert "图片数量未同步" in source


def test_mobile_contract_scopes_and_appends_home_previews() -> None:
    source = MOBILE.read_text(encoding="utf-8")
    loader = source.split("async function loadMobileV3Projects", 1)[1].split(
        "function setMobileV3LoadingLayer", 1
    )[0]

    assert "project_ids=" in source
    assert "loadMobileV3HomePreviews" in loader
    assert "append" in loader
    assert "mergeMobileV3ProjectItems" in source
    assert "图片数量未同步" in source


def test_cache_covers_survive_empty_lightweight_summaries_and_preview_url_is_displayable() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                () => ({
                  merged: mergeV3ProjectItems(
                    [{ project_id: "p1", latest_thumbnail_urls: [], visible_output_count: 0 }],
                    [{ project_id: "p1", latest_thumbnail_urls: ["http://image.test/cached.png"], visible_output_count: 4 }],
                  )[0],
                  previewUrl: v3OutputStrictThumbImageUrl({ preview_url: "http://image.test/preview.png" }),
                })
                """,
            )
            assert result["merged"]["latest_thumbnail_urls"] == ["http://image.test/cached.png"]
            assert result["previewUrl"] == "http://image.test/preview.png"
        finally:
            browser.close()


def test_desktop_load_more_requests_only_new_project_previews_and_keeps_old_cover() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                async () => {
                  const requests = [];
                  const existing = Array.from({ length: 9 }, (_, index) => ({
                    project_id: `old-${index}`,
                    status: "active",
                    title: `Old ${index}`,
                    user_goal: "goal",
                    short_summary: "summary",
                    primary_template_id: "general_template",
                    updated_at: `2026-09-14T00:${String(20 - index).padStart(2, "0")}:00Z`,
                    latest_thumbnail_urls: index === 0 ? ["http://image.test/old.png"] : [],
                  }));
                  const incoming = {
                    project_id: "new-page-project",
                    status: "active",
                    title: "New page",
                    user_goal: "goal",
                    short_summary: "summary",
                    primary_template_id: "general_template",
                    updated_at: "2026-09-13T00:01:00Z",
                    latest_thumbnail_urls: [],
                  };
                  window.fetch = async (input) => {
                    const url = String(input);
                    requests.push(url);
                    if (url.includes("/projects?")) {
                      return new Response(JSON.stringify({
                        projects: [incoming], templates: [], total: 10, has_more: false, next_cursor: null,
                      }), { status: 200 });
                    }
                    if (url.includes("surface=home_preview")) {
                      return new Response(JSON.stringify({ items: [{
                        project_id: "new-page-project",
                        output_id: "new-output",
                        delivery_state: "final_delivery",
                        created_at: "2026-09-13T00:02:00Z",
                        thumbnail_url: "http://image.test/new.png",
                      }], review_items: [] }), { status: 200 });
                    }
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  v3State.workspaceMode = "standard";
                  v3State.projects = existing;
                  v3State.projectsLoaded = true;
                  v3State.projectsLoading = false;
                  v3State.projectsLoadingMore = false;
                  v3State.projectsHasMore = true;
                  v3State.projectsNextCursor = "cursor-old";
                  v3State.projectsTotal = 10;
                  v3State.projectRenderLimit = 9;
                  v3State.imageHistory = [{
                    project_id: "old-0",
                    output_id: "old-output",
                    delivery_state: "final_delivery",
                    created_at: "2026-09-14T00:20:00Z",
                    thumbnail_url: "http://image.test/old.png",
                  }];
                  v3State.imageHistorySurface = "home_preview";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  v3State.projectOutputsRequest = null;
                  v3State.projectOutputsRequestOwner = null;
                  v3State.projectOutputsRequestKey = "";
                  await loadV3Projects({ silent: true, loadMore: true });
                  return {
                    previewRequest: requests.find((url) => url.includes("surface=home_preview")) || "",
                    projects: v3State.projects.map((item) => item.project_id),
                    outputIds: v3State.imageHistory.map((item) => item.output_id),
                  };
                }
                """,
            )
            assert "project_ids=new-page-project" in result["previewRequest"]
            assert "old-output" in result["outputIds"]
            assert "new-output" in result["outputIds"]
            assert "new-page-project" in result["projects"]
        finally:
            browser.close()


def test_mobile_load_more_requests_only_new_project_previews_and_keeps_old_cover() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            result = page.evaluate(
                """
                async () => {
                  const requests = [];
                  const existing = Array.from({ length: 4 }, (_, index) => ({
                    project_id: `mobile-old-${index}`,
                    status: "active",
                    title: `Old ${index}`,
                    user_goal: "goal",
                    short_summary: "summary",
                    primary_template_id: "general_template",
                    updated_at: `2026-09-14T00:${String(20 - index).padStart(2, "0")}:00Z`,
                    latest_thumbnail_urls: index === 0 ? ["http://image.test/mobile-old.png"] : [],
                  }));
                  const incoming = {
                    project_id: "mobile-new-page-project",
                    status: "active",
                    title: "New page",
                    user_goal: "goal",
                    short_summary: "summary",
                    primary_template_id: "general_template",
                    updated_at: "2026-09-13T00:01:00Z",
                    latest_thumbnail_urls: [],
                  };
                  window.fetch = async (input) => {
                    const url = String(input);
                    requests.push(url);
                    if (url.includes("/projects?")) {
                      return new Response(JSON.stringify({
                        projects: [incoming], templates: [], total: 5, has_more: false, next_cursor: null,
                      }), { status: 200 });
                    }
                    if (url.includes("surface=home_preview")) {
                      return new Response(JSON.stringify({ items: [{
                        project_id: "mobile-new-page-project",
                        output_id: "mobile-new-output",
                        delivery_state: "final_delivery",
                        created_at: "2026-09-13T00:02:00Z",
                        thumbnail_url: "http://image.test/mobile-new.png",
                      }], review_items: [] }), { status: 200 });
                    }
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  mobileV3State.workspaceMode = "standard";
                  mobileV3State.projects = existing;
                  mobileV3State.loaded = true;
                  mobileV3State.loading = false;
                  mobileV3State.projectsLoadingMore = false;
                  mobileV3State.projectsHasMore = true;
                  mobileV3State.projectsNextCursor = "mobile-cursor-old";
                  mobileV3State.projectsTotal = 5;
                  mobileV3State.projectRenderLimit = 4;
                  mobileV3State.outputs = [{
                    project_id: "mobile-old-0",
                    output_id: "mobile-old-output",
                    delivery_state: "final_delivery",
                    created_at: "2026-09-14T00:20:00Z",
                    thumbnail_url: "http://image.test/mobile-old.png",
                  }];
                  mobileV3State.outputsLoaded = true;
                  mobileV3State.outputsSurface = "home_preview";
                  mobileV3State.outputError = "";
                  mobileV3State.previewProjectIds = new Set(["mobile-old-0"]);
                  await loadMobileV3Projects({ silent: true, loadMore: true });
                  return {
                    previewRequest: requests.find((url) => url.includes("surface=home_preview")) || "",
                    projects: mobileV3State.projects.map((item) => item.project_id),
                    outputIds: mobileV3State.outputs.map((item) => item.output_id),
                  };
                }
                """,
            )
            assert "project_ids=mobile-new-page-project" in result["previewRequest"]
            assert "mobile-old-output" in result["outputIds"]
            assert "mobile-new-output" in result["outputIds"]
            assert "mobile-new-page-project" in result["projects"]
        finally:
            browser.close()


def test_doc308_freezes_scope_count_cache_and_delivery_boundaries() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "project_ids" in doc
    assert "`0 张` state" in doc
    assert "does not change Brain, Provider" in doc
    assert "independent read-only audit" in doc
    assert "GitHub" in doc and "VPS" in doc
