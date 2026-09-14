"""Regression contracts for synchronized V3 home project image counts."""

from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "alchemy_creative_agent_3_0" / "app" / "project_mode" / "service.py"
CONTRACTS = ROOT / "alchemy_creative_agent_3_0" / "app" / "project_mode" / "contracts.py"
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "310_V3_HOME_PROJECT_IMAGE_COUNT_SYNC_REPAIR_SPEC.md"


def test_summary_marks_count_unknown_but_full_summary_marks_count_known() -> None:
    service = V3ProjectModeService(
        product_service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )
    project = service.create_project({"user_goal": "Create a countable project."}).project
    assert project is not None

    summary = service.list_projects(limit=1, view="summary").projects[0]
    assert summary.visible_output_count == 0
    assert summary.visible_output_count_known is False

    full_summary = service._memory_summary(project)
    assert full_summary.visible_output_count == 0
    assert full_summary.visible_output_count_known is True


def test_home_preview_returns_counts_for_all_evaluated_requested_projects() -> None:
    service = object.__new__(V3ProjectModeService)
    projects = [
        SimpleNamespace(project_id="count-zero", status="active", updated_at="2026-09-14T00:02:00Z"),
        SimpleNamespace(project_id="count-four", status="active", updated_at="2026-09-14T00:01:00Z"),
    ]
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: list(projects),
        list_projects=lambda limit: list(projects),
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_output_read_snapshot = lambda *_args, **_kwargs: {
        "records_by_project": {project.project_id: [] for project in projects},
        "records_by_job": {},
        "job_status_by_id": {},
        "job_record_by_id": {},
    }
    service._project_visible_output_count = lambda project, **_kwargs: (
        0 if project.project_id == "count-zero" else 4
    )
    service._project_delivery_preview_items = lambda project, **_kwargs: (
        [{"project_id": project.project_id, "output_id": f"output-{project.project_id}"}]
        if project.project_id == "count-four"
        else []
    )
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=2,
        compact=True,
        surface="home_preview",
        project_ids=["count-zero", "count-four"],
    )

    assert response["project_output_counts"] == {"count-zero": 0, "count-four": 4}
    assert [item["project_id"] for item in response["items"]] == ["count-four"]


def test_home_preview_does_not_turn_index_read_failure_into_zero() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(project_id="index-failure", status="active", updated_at="2026-09-14T00:02:00Z")
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: [project],
        list_projects=lambda limit: [project],
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_output_read_snapshot = lambda *_args, **_kwargs: {
        "records_by_project": {project.project_id: []},
        "records_by_job": {},
        "job_status_by_id": {},
        "job_record_by_id": {},
        "project_index_complete": {project.project_id: False},
    }

    def unexpected_call(*_args, **_kwargs):
        raise AssertionError("an unreadable project index must stay unknown")

    service._project_visible_output_count = unexpected_call
    service._project_delivery_preview_items = lambda *_args, **_kwargs: []
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["project_output_counts"] == {}
    assert response["items"] == []


def test_count_helper_reuses_project_delivery_projection() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(project_id="count-project", job_ids=["job-1"])
    record = SimpleNamespace(output_id="output-1", job_id="job-1")
    observed = []
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: [record],
        )
    )

    def delivery_projection(candidate, **kwargs):
        observed.append((candidate, kwargs))
        return [{"output_id": "output-1"}, {"output_id": "output-2"}]

    service._project_output_items = delivery_projection

    assert service._project_visible_output_count(project) == 2
    assert observed[0][0] is project
    assert observed[0][1]["compact"] is True


def test_desktop_home_count_projection_renders_numeric_count_and_known_zero() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                () => {
                  const base = (project_id, title) => ({
                    project_id,
                    title,
                    user_goal: title,
                    short_summary: title,
                    primary_template_id: "general_template",
                    status: "active",
                    job_count: 1,
                    selected_asset_count: 0,
                    updated_at: "2026-09-14T00:01:00Z",
                    latest_thumbnail_urls: [],
                  });
                  v3State.workspaceMode = "standard";
                  v3State.projects = [base("count-four", "Four images"), base("count-zero", "No images")];
                  v3State.projectRenderLimit = 4;
                  v3State.projectsHasMore = false;
                  v3State.projectsLoading = false;
                  v3State.imageHistory = [{
                    project_id: "count-four",
                    output_id: "output-four",
                    delivery_state: "final_delivery",
                    created_at: "2026-09-14T00:02:00Z",
                    thumbnail_url: "http://image.test/four.png",
                  }];
                  v3State.imageHistorySurface = "home_preview";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  syncV3HomeProjectCounts({"count-four": 4, "count-zero": 0});
                  renderV3Projects();
                  renderV3History();
                  return {
                    projectLabel: v3ProjectImageCountText(v3State.projects[0]),
                    history: document.querySelector("#v3HistoryList")?.textContent || "",
                  };
                }
                """,
            )
            assert result["projectLabel"] == "4 张图片"
            assert "4 张图片" in result["history"]
            assert "0 张图片" in result["history"]
            assert "封面预览" not in result["history"]
        finally:
            browser.close()


def test_mobile_home_count_projection_renders_numeric_count_and_known_zero() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            result = page.evaluate(
                """
                () => {
                  const base = (project_id, title) => ({
                    project_id,
                    title,
                    user_goal: title,
                    short_summary: title,
                    primary_template_id: "general_template",
                    status: "active",
                    job_count: 1,
                    updated_at: "2026-09-14T00:01:00Z",
                    latest_thumbnail_urls: [],
                  });
                  mobileV3State.workspaceMode = "standard";
                  mobileV3State.projects = [base("mobile-four", "Four images"), base("mobile-zero", "No images")];
                  mobileV3State.projectRenderLimit = 4;
                  mobileV3State.projectsHasMore = false;
                  mobileV3State.outputs = [{
                    project_id: "mobile-four",
                    output_id: "mobile-output-four",
                    delivery_state: "final_delivery",
                    created_at: "2026-09-14T00:02:00Z",
                    thumbnail_url: "http://image.test/mobile-four.png",
                  }];
                  mobileV3State.outputsLoaded = true;
                  mobileV3State.outputsSurface = "home_preview";
                  mobileV3State.outputError = "";
                  mobileV3State.previewProjectIds = new Set(["mobile-four"]);
                  syncMobileV3HomeProjectCounts({"mobile-four": 4, "mobile-zero": 0});
                  renderMobileV3ProjectCards();
                  return document.querySelector("#mobileV3ProjectGrid")?.textContent || "";
                }
                """,
            )
            assert "4 张图片" in result
            assert "0 张图片" in result
            assert "已有封面 · 数量同步中" not in result
        finally:
            browser.close()


def test_count_contract_and_cache_guard_are_present() -> None:
    service_source = SERVICE.read_text(encoding="utf-8")
    contracts_source = CONTRACTS.read_text(encoding="utf-8")
    desktop_source = DESKTOP.read_text(encoding="utf-8")
    mobile_source = MOBILE.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")

    assert "visible_output_count_known" in contracts_source
    assert "project_output_counts" in service_source
    assert "_project_visible_output_count" in service_source
    assert "syncV3HomeProjectCounts" in desktop_source
    assert "syncMobileV3HomeProjectCounts" in mobile_source
    assert "数量同步中" in desktop_source and "数量同步中" in mobile_source
    assert "does not change Brain" in doc
