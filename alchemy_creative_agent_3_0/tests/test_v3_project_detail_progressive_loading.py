from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)


_ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def _project(project_id: str = "project_progressive") -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        title="Progressive project",
        user_goal="Create a useful project preview.",
        short_summary="Create a useful project preview.",
        job_ids=["job_old", "job_new"],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-01T00:01:00+00:00",
        metadata={"veyra_user_id": 7},
    )


def _service() -> tuple[V3ProjectModeService, ProjectRecord]:
    service = V3ProjectModeService(
        product_service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )
    project = service.create_project({"user_goal": "Create a useful project preview."}).project
    assert project is not None
    return service, project


def test_summary_view_skips_reconciliation_and_full_context() -> None:
    service, project = _service()

    def unexpected(*_args, **_kwargs):
        pytest.fail("summary view must not scan or reconcile the full project history")

    service._reconcile_project_outputs = unexpected
    service._ensure_project_product_reference_integrity = unexpected
    service._build_context = unexpected
    service._memory_summary = unexpected

    response = service.get_project(project.project_id, owner_user_id=7, view="summary")

    assert response.project is not None
    assert response.context is None
    assert response.metadata["project_detail_view"] == "summary"
    assert response.metadata["project_outputs"] == []
    assert response.metadata["project_outputs_complete"] is False
    assert response.project.memory_summary is not None
    assert response.project.memory_summary.job_count == 0


def test_delivery_preview_surface_skips_reconciliation_and_review_items() -> None:
    service, project = _service()

    service._reconcile_project_outputs = lambda *_args, **_kwargs: pytest.fail(
        "delivery preview must not reconcile project history"
    )

    response = service.list_project_outputs(
        limit=80,
        owner_user_id=None,
        compact=True,
        project_id=project.project_id,
        surface="delivery_preview",
    )

    assert response["items"] == []
    assert response["review_items"] == []
    assert response["limit"] == 1
    assert response["metadata"]["surface"] == "delivery_preview"
    assert response["metadata"]["complete"] is False


def test_delivery_preview_uses_project_index_and_passes_only_newest_jobs_to_existing_gate() -> None:
    service = object.__new__(V3ProjectModeService)
    project = _project()
    records = [
        SimpleNamespace(job_id="foreign", created_at="2026-09-01T00:10:00+00:00"),
        SimpleNamespace(job_id="job_old", created_at="2026-09-01T00:11:00+00:00"),
        SimpleNamespace(job_id="job_new", created_at="2026-09-01T00:12:00+00:00"),
        SimpleNamespace(job_id="job_new", created_at="2026-09-01T00:13:00+00:00"),
    ]
    index_calls: list[tuple[str, int]] = []
    gate_calls: list[tuple[list[str], int]] = []

    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda project_id, limit: (
                index_calls.append((project_id, limit)) or records
            )
        )
    )
    service._project_output_items = lambda candidate, *, limit, owner_user_id, compact: (
        gate_calls.append((list(candidate.job_ids), limit))
        or [{"output_id": "v3_output_preview"}]
    )

    result = service._project_delivery_preview_items(
        project,
        limit=10,
        owner_user_id=7,
        compact=True,
    )

    assert result == [{"output_id": "v3_output_preview"}]
    assert index_calls == [(project.project_id, 256)]
    assert gate_calls == [(["job_new", "job_old"], 1)]


def test_output_store_project_index_is_bounded_and_separate_from_job_index(tmp_path: Path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    first = store.save_base64_output(
        job_id="job_a",
        candidate_id="candidate_a",
        asset_id="asset_a",
        provider="test",
        model="test-model",
        encoded_image=_ONE_PIXEL_PNG,
        metadata={"project_id": "project_a"},
    )
    second = store.save_base64_output(
        job_id="job_b",
        candidate_id="candidate_b",
        asset_id="asset_b",
        provider="test",
        model="test-model",
        encoded_image=_ONE_PIXEL_PNG,
        metadata={"project_id": "project_a"},
    )
    store.save_base64_output(
        job_id="job_c",
        candidate_id="candidate_c",
        asset_id="asset_c",
        provider="test",
        model="test-model",
        encoded_image=_ONE_PIXEL_PNG,
        metadata={"project_id": "project_other"},
    )

    indexed = store.list_by_project("project_a", limit=1)

    assert len(indexed) == 1
    assert indexed[0].output_id in {first.output_id, second.output_id}
    assert all(record.metadata.get("project_id") == "project_a" for record in store.list_by_project("project_a"))
    assert store.list_by_project("project_missing") == []


def test_desktop_and_mobile_use_summary_preview_and_background_detail_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    desktop = (root / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    mobile = (root / "src_skeleton" / "app" / "mobile_static" / "mobile.js").read_text(encoding="utf-8")
    spec = (root / "alchemy_creative_agent_3_0" / "docs" / "100_V3_PROJECT_DETAIL_PROGRESSIVE_LOADING_SPEC.md").read_text(encoding="utf-8")

    assert "?view=summary" in desktop
    assert "surface=delivery_preview" in desktop
    assert "syncV3ProjectDetailInBackground" in desktop
    assert "data-v3-project-first-preview" in desktop
    assert "?view=summary" in mobile
    assert "surface=delivery_preview" in mobile
    assert "syncMobileV3ProjectDetailFull" in mobile
    assert "data-mobile-v3-project-first-preview" in mobile
    assert "The existing full project response remains the default compatibility path." in spec


def test_desktop_releases_project_mask_after_first_preview_while_history_is_slow() -> None:
    project = {
        "project_id": "progressive-project",
        "title": "Progressive project",
        "user_goal": "Create a useful project preview.",
        "short_summary": "Create a useful project preview.",
        "primary_template_id": "general_template",
        "job_ids": [],
        "reference_assets": [],
        "metadata": {},
    }
    template = {
        "template_id": "general_template",
        "display_name": "通用创意",
        "project_can_create_jobs": True,
    }
    preview = {
        "output_id": "preview-output",
        "project_id": "progressive-project",
        "job_id": "preview-job",
        "delivery_state": "final_delivery",
        "created_at": "2026-09-01T00:02:00+00:00",
        "thumbnail_url": "data:image/png;base64," + _ONE_PIXEL_PNG,
        "preview_url": "data:image/png;base64," + _ONE_PIXEL_PNG,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                async ({ project, template, preview }) => {
                  const requests = [];
                  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
                  const projectPayload = { project, templates: [template], metadata: {} };
                  const outputsPayload = { items: [preview], review_items: [] };
                  window.fetch = async (input, init = {}) => {
                    const url = String(input);
                    const method = String(init.method || "GET").toUpperCase();
                    requests.push({ url, method });
                    const isSummary = url.includes("/projects/progressive-project?view=summary");
                    const isPreview = url.includes("/project-outputs") && url.includes("surface=delivery_preview");
                    const isFullProject = url.includes("/projects/progressive-project") && !url.includes("/timeline") && !isSummary;
                    const isTimeline = url.includes("/projects/progressive-project/timeline");
                    const isOutputs = url.includes("/project-outputs") && !isPreview;
                    const isBindings = url.includes("/visual-asset-bindings");
                    if (isSummary || isPreview) await delay(35);
                    if (isFullProject || isTimeline || isOutputs || isBindings) await delay(420);
                    if (isSummary) return new Response(JSON.stringify(projectPayload), { status: 200 });
                    if (isPreview || isOutputs) return new Response(JSON.stringify(outputsPayload), { status: 200 });
                    if (isTimeline) return new Response(JSON.stringify({ items: [] }), { status: 200 });
                    if (isBindings) return new Response(JSON.stringify({ bindings: [], state: "empty" }), { status: 200 });
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  v3State.projects = [project];
                  v3State.templates = [template];
                  v3State.templateCatalogStatus = "ready";
                  v3State.currentProject = null;
                  v3State.currentJob = null;
                  v3State.projectOpening = false;
                  const started = performance.now();
                  await openV3Project(project.project_id);
                  const released = performance.now() - started;
                  const mask = document.querySelector("#v3PageLoadingOverlay");
                  const releaseSnapshot = {
                    releasedMs: released,
                    maskHidden: Boolean(mask?.hidden),
                    firstPreviewCount: document.querySelectorAll("img[data-v3-project-first-preview='true']").length,
                    opening: Boolean(v3State.projectOpening),
                    backgroundRequests: requests.filter(({ url }) =>
                      url.includes("/timeline") || url.includes("surface=delivery_preview") || url.includes("/visual-asset-bindings") ||
                      (url.includes("/projects/progressive-project") && !url.includes("view=summary"))
                    ).length,
                  };
                  const legacyStarted = performance.now();
                  await Promise.all([
                    request("/api/v3/creative-agent/projects/progressive-project"),
                    request("/api/v3/creative-agent/projects/progressive-project/timeline"),
                    request("/api/v3/creative-agent/project-outputs?limit=80&compact=true&project_id=progressive-project"),
                    request("/api/v3/creative-agent/projects/progressive-project/visual-asset-bindings"),
                  ]);
                  return { ...releaseSnapshot, legacyMs: performance.now() - legacyStarted };
                }
                """,
                {"project": project, "template": template, "preview": preview},
            )
            assert result["maskHidden"] is True
            assert result["firstPreviewCount"] == 1
            assert result["opening"] is False
            assert result["backgroundRequests"] >= 3
            assert result["releasedMs"] < result["legacyMs"] * 0.5
        finally:
            browser.close()


def test_mobile_releases_project_mask_after_first_preview_while_history_is_slow() -> None:
    project = {
        "project_id": "mobile-progressive-project",
        "title": "Mobile progressive project",
        "user_goal": "Create a useful project preview.",
        "short_summary": "Create a useful project preview.",
        "primary_template_id": "general_template",
        "job_ids": [],
        "reference_assets": [],
        "metadata": {},
    }
    template = {
        "template_id": "general_template",
        "display_name": "通用创意",
        "project_can_create_jobs": True,
    }
    preview = {
        "output_id": "mobile-preview-output",
        "project_id": "mobile-progressive-project",
        "job_id": "mobile-preview-job",
        "delivery_state": "final_delivery",
        "created_at": "2026-09-01T00:02:00+00:00",
        "thumbnail_url": "data:image/png;base64," + _ONE_PIXEL_PNG,
        "preview_url": "data:image/png;base64," + _ONE_PIXEL_PNG,
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, template, preview }) => {
                  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
                  const requests = [];
                  const projectPayload = { project, templates: [template], metadata: {} };
                  const outputsPayload = { items: [preview], review_items: [] };
                  window.fetch = async (input, init = {}) => {
                    const url = String(input);
                    const method = String(init.method || "GET").toUpperCase();
                    requests.push({ url, method });
                    const isSummary = url.includes("/projects/mobile-progressive-project?view=summary");
                    const isFullProject = url.includes("/projects/mobile-progressive-project") && !url.includes("/timeline") && !isSummary;
                    const isTimeline = url.includes("/projects/mobile-progressive-project/timeline");
                    const isPreview = url.includes("/project-outputs") && url.includes("surface=delivery_preview");
                    const isOutputs = url.includes("/project-outputs") && !isPreview;
                    if (isSummary || isPreview) await delay(35);
                    if (isFullProject || isTimeline || isOutputs) await delay(420);
                    if (isSummary) return new Response(JSON.stringify(projectPayload), { status: 200 });
                    if (isPreview || isOutputs) return new Response(JSON.stringify(outputsPayload), { status: 200 });
                    if (isTimeline) return new Response(JSON.stringify({ items: [] }), { status: 200 });
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  mobileV3State.projects = [project];
                  mobileV3State.currentProject = null;
                  mobileV3State.currentJob = null;
                  window.__mobileProgressiveRequests = requests;
                  window.__mobileProgressiveStarted = performance.now();
                  openMobileV3ProjectDetail(project);
                }
                """,
                {"project": project, "template": template, "preview": preview},
            )
            page.wait_for_function(
                "document.querySelector('#mobileV3LoadingLayer')?.hidden === true && "
                "document.querySelector(\"img[data-mobile-v3-project-first-preview='true']\") !== null",
                timeout=3000,
            )
            result = page.evaluate(
                """
                () => ({
                  releasedMs: performance.now() - window.__mobileProgressiveStarted,
                  backgroundRequests: window.__mobileProgressiveRequests.filter(({ url }) =>
                    url.includes("/timeline") || url.includes("/project-outputs") || url.includes("/projects/mobile-progressive-project")
                  ).length,
                  firstPreviewCount: document.querySelectorAll("img[data-mobile-v3-project-first-preview='true']").length,
                })
                """
            )
            assert result["firstPreviewCount"] == 1
            assert result["backgroundRequests"] >= 3
            assert result["releasedMs"] < 220
        finally:
            browser.close()
