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


def test_summary_view_does_not_resolve_jobs_or_verify_continuity_source() -> None:
    service, project = _service()

    def unexpected(*_args, **_kwargs):
        pytest.fail("summary view must not load Jobs or verify continuity image bytes")

    service._continuity_state = unexpected
    service._continuity_output = unexpected
    service._current_job_direct_reference_ids = unexpected

    response = service.get_project(project.project_id, owner_user_id=7, view="summary")

    assert response.project is not None
    assert response.metadata["continuity_anchor"]["project_id"] == project.project_id


def test_summary_view_projects_active_anchor_without_reading_source_output() -> None:
    service, project = _service()
    bindings = service._anchor_bindings()
    bindings.resolve_output = lambda *_args: {
        "job_id": "anchor-job",
        "candidate_id": "anchor-candidate",
        "asset_id": "anchor-asset",
        "source_asset_id": "anchor-asset",
        "content_sha256": "a" * 64,
    }
    current_version = bindings.state(project.project_id, verify_source=False)["version"]
    bindings.change(
        project.project_id,
        output_id="anchor-output",
        expected_version=current_version,
        expected_job_id="anchor-job",
    )

    def unexpected(*_args, **_kwargs):
        pytest.fail("summary view must not resolve or hash the continuity source image")

    bindings.resolve_output = unexpected
    service._continuity_state = unexpected
    service._current_job_direct_reference_ids = unexpected

    response = service.get_project(project.project_id, owner_user_id=7, view="summary")

    assert response.metadata["continuity_anchor"]["state"] == "active"
    assert response.metadata["continuity_anchor"]["active_continuity_anchor"]["output_id"] == "anchor-output"


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
        gate_calls.append((list(reversed(candidate.job_ids)), limit))
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


def test_project_summary_and_preview_reads_do_not_block_the_api_event_loop() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src_skeleton" / "app" / "main.py").read_text(encoding="utf-8")
    outputs_start = source.index("async def v3_project_outputs_endpoint(")
    outputs_end = source.index("@app.post(\"/api/v3/creative-agent/projects\")", outputs_start)
    project_start = source.index("async def v3_get_project_endpoint(")
    project_end = source.index("@app.get(\"/api/v3/creative-agent/projects/{project_id}/planning-operations", project_start)
    outputs_endpoint = source[outputs_start:outputs_end]
    project_endpoint = source[project_start:project_end]

    assert 'in {"home_preview", "delivery_preview"}' in outputs_endpoint
    assert "return await _run_v3_handler_threaded(" in outputs_endpoint
    assert '== "summary"' in project_endpoint
    assert "response = await _run_v3_handler_threaded(" in project_endpoint


def test_v3_job_planning_runs_outside_the_api_event_loop() -> None:
    root = Path(__file__).resolve().parents[2]
    source = (root / "src_skeleton" / "app" / "main.py").read_text(encoding="utf-8")
    start = source.index("async def v3_create_job_endpoint(")
    end = source.index('@app.get("/api/v3/creative-agent/jobs/{job_id}")', start)
    endpoint = source[start:end]

    assert "return await _run_v3_handler_threaded(v3_route_handlers.post_jobs, payload)" in endpoint
    assert "return _run_v3_handler(v3_route_handlers.post_jobs, payload)" not in endpoint


def test_desktop_releases_project_mask_after_summary_while_history_is_slow() -> None:
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
                  const projectPayload = {
                    project,
                    templates: [template],
                    metadata: { project_detail_view: "summary", project_outputs: [], review_items: [] },
                  };
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
                    currentProjectId: v3State.currentProject?.project_id || "",
                    opening: Boolean(v3State.projectOpening),
                    backgroundRequests: requests.filter(({ url }) =>
                      url.includes("/timeline") || url.includes("surface=delivery_preview") || url.includes("/visual-asset-bindings") ||
                      (url.includes("/projects/progressive-project") && !url.includes("view=summary"))
                    ).length,
                    backgroundTimelineRequests: requests.filter(({ url }) => url.includes("/timeline")).length,
                    backgroundFullOutputRequests: requests.filter(({ url }) =>
                      url.includes("/project-outputs") && !url.includes("surface=delivery_preview")
                    ).length,
                  };
                  return releaseSnapshot;
                }
                """,
                {"project": project, "template": template, "preview": preview},
            )
            assert result["maskHidden"] is True
            assert result["currentProjectId"] == project["project_id"]
            assert result["opening"] is False
            assert result["backgroundRequests"] >= 2
            assert result["backgroundTimelineRequests"] >= 1
        finally:
            browser.close()


def test_desktop_opens_project_before_preview_finishes() -> None:
    project = {
        "project_id": "summary-before-preview",
        "title": "Summary before preview",
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

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                async ({ project, template }) => {
                  let releasePreview;
                  const previewGate = new Promise(resolve => { releasePreview = resolve; });
                  const requests = [];
                  const projectPayload = { project, templates: [template], metadata: {} };
                  window.fetch = async input => {
                    const url = String(input);
                    requests.push(url);
                    if (url.includes("view=summary")) {
                      return new Response(JSON.stringify(projectPayload), { status: 200 });
                    }
                    if (url.includes("surface=delivery_preview")) {
                      await previewGate;
                      return new Response(JSON.stringify({ items: [], review_items: [] }), { status: 200 });
                    }
                    if (url.includes("/timeline")) return new Response(JSON.stringify({ items: [] }), { status: 200 });
                    return new Response(JSON.stringify({ items: [], review_items: [] }), { status: 200 });
                  };
                  v3State.projects = [project];
                  v3State.templates = [template];
                  v3State.templateCatalogStatus = "ready";
                  v3State.currentProject = null;
                  v3State.currentJob = null;
                  v3State.projectOpening = false;
                  const started = performance.now();
                  const opening = openV3Project(project.project_id);
                  const returnedBeforePreview = await Promise.race([
                    opening.then(() => true),
                    new Promise(resolve => window.setTimeout(() => resolve(false), 1000)),
                  ]);
                  const snapshot = {
                    returnedBeforePreview,
                    currentProjectId: v3State.currentProject?.project_id || "",
                    opening: Boolean(v3State.projectOpening),
                    maskHidden: Boolean(document.querySelector("#v3PageLoadingOverlay")?.hidden),
                    elapsedMs: performance.now() - started,
                    previewRequested: requests.some(url => url.includes("surface=delivery_preview")),
                  };
                  const fullItems = [
                    { output_id: "full-output-1", project_id: project.project_id },
                    { output_id: "full-output-2", project_id: project.project_id },
                  ];
                  const reviewItems = [{ output_id: "review-output", project_id: project.project_id }];
                  syncV3ProjectOutputsFromList(fullItems, project.project_id, reviewItems);
                  releasePreview();
                  await new Promise(resolve => window.setTimeout(resolve, 0));
                  return {
                    ...snapshot,
                    outputs: v3State.projectOutputs.map(item => item.output_id),
                    reviewOutputs: v3State.projectReviewOutputs.map(item => item.output_id),
                    outputSurface: v3State.projectOutputsSurface,
                  };
                }
                """,
                {"project": project, "template": template},
            )
            assert result["returnedBeforePreview"] is True
            assert result["currentProjectId"] == project["project_id"]
            assert result["opening"] is False
            assert result["maskHidden"] is True
            assert result["elapsedMs"] < 1000
            assert result["previewRequested"] is True
            assert result["outputs"] == ["full-output-1", "full-output-2"]
            assert result["reviewOutputs"] == ["review-output"]
            assert result["outputSurface"] == "full"
        finally:
            browser.close()


def test_summary_refresh_does_not_clear_full_project_outputs_or_review() -> None:
    project = {
        "project_id": "summary-refresh-project",
        "title": "Summary refresh project",
        "user_goal": "Keep loaded results.",
        "short_summary": "Keep loaded results.",
        "primary_template_id": "general_template",
        "job_ids": [],
        "reference_assets": [],
        "metadata": {},
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                ({ project }) => {
                  const fullItems = [{ output_id: "full-output", project_id: project.project_id }];
                  const reviewItems = [{ output_id: "review-output", project_id: project.project_id }];
                  v3State.currentProject = project;
                  v3State.projectOutputs = fullItems;
                  v3State.projectReviewOutputs = reviewItems;
                  v3State.projectOutputsSurface = "full";
                  syncV3ProjectOutputsFromPayload({
                    metadata: {
                      project_detail_view: "summary",
                      project_outputs: [],
                      review_items: [],
                    },
                  });
                  return {
                    outputs: v3State.projectOutputs.map(item => item.output_id),
                    reviewOutputs: v3State.projectReviewOutputs.map(item => item.output_id),
                    surface: v3State.projectOutputsSurface,
                  };
                }
                """,
                {"project": project},
            )
            assert result["outputs"] == ["full-output"]
            assert result["reviewOutputs"] == ["review-output"]
            assert result["surface"] == "full"
        finally:
            browser.close()


def test_failed_project_switch_restores_previous_detail_owner() -> None:
    project_a = {
        "project_id": "preserved-project-a",
        "title": "Project A",
        "user_goal": "Keep this project open.",
        "short_summary": "Keep this project open.",
        "primary_template_id": "general_template",
        "job_ids": ["existing-job"],
        "reference_assets": [],
        "metadata": {},
    }

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                async ({ projectA }) => {
                  let releaseJob;
                  const jobGate = new Promise(resolve => { releaseJob = resolve; });
                  const requests = [];
                  window.fetch = async (input, init = {}) => {
                    const url = String(input);
                    const method = String(init.method || "GET").toUpperCase();
                    requests.push({ url, method });
                    if (url.includes("/projects/unavailable-project?view=summary")) {
                      return new Response(JSON.stringify({ detail: "unavailable" }), { status: 503 });
                    }
                    if (url.includes("/jobs/existing-job")) {
                      await jobGate;
                      return new Response(JSON.stringify({ job_id: "existing-job", status: "failed" }), { status: 200 });
                    }
                    if (url.includes("/timeline")) return new Response(JSON.stringify({ items: [] }), { status: 200 });
                    if (url.includes("/project-outputs")) return new Response(JSON.stringify({ items: [], review_items: [] }), { status: 200 });
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  v3State.currentProject = projectA;
                  v3State.currentJob = null;
                  v3State.projectOpening = false;
                  v3State.view = "workspace";
                  const controllerA = new AbortController();
                  v3State.projectDetailAbortController = controllerA;
                  v3State.projectDetailProjectId = projectA.project_id;
                  v3State.projectDetailEpoch = 7;
                  v3State.templates = [{ template_id: "general_template", project_can_create_jobs: true }];
                  v3State.templateCatalogStatus = "ready";
                  v3State.selectedTemplate = "general_template";
                  v3State.selectedScenario = "general_creative";
                  await openV3Project("unavailable-project");
                  const whileRestoring = {
                    currentProjectId: v3State.currentProject?.project_id || "",
                    detailProjectId: v3State.projectDetailProjectId,
                    controllerLive: Boolean(v3State.projectDetailAbortController && !v3State.projectDetailAbortController.signal.aborted),
                    previousControllerAborted: controllerA.signal.aborted,
                    view: v3State.view,
                    workspaceVisible: document.querySelector("#v3WorkspaceView")?.hidden === false,
                    opening: Boolean(v3State.projectOpening),
                    loading: Boolean(v3State.loading),
                    createDisabled: Boolean(document.querySelector("#v3CreateJobBtn")?.disabled),
                    jobGetPending: requests.some(item => item.url.includes("/jobs/existing-job") && item.method === "GET"),
                    generatePosts: requests.filter(item => item.method === "POST" && item.url.includes("/generate")).length,
                  };
                  releaseJob();
                  await new Promise(resolve => window.setTimeout(resolve, 20));
                  return {
                    ...whileRestoring,
                    loadingAfterJobRead: Boolean(v3State.loading),
                    createDisabledAfterJobRead: Boolean(document.querySelector("#v3CreateJobBtn")?.disabled),
                  };
                }
                """,
                {"projectA": project_a},
            )
            assert result["currentProjectId"] == project_a["project_id"]
            assert result["detailProjectId"] == project_a["project_id"]
            assert result["controllerLive"] is True
            assert result["previousControllerAborted"] is True
            assert result["view"] == "workspace"
            assert result["workspaceVisible"] is True
            assert result["opening"] is False
            assert result["loading"] is True
            assert result["createDisabled"] is True
            assert result["jobGetPending"] is True
            assert result["generatePosts"] == 0
            assert result["loadingAfterJobRead"] is False
            assert result["createDisabledAfterJobRead"] is False
        finally:
            browser.close()


def test_desktop_first_open_failure_returns_to_project_home() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                async () => {
                  window.fetch = async () => new Response(JSON.stringify({ detail: { code: "unavailable" } }), { status: 503 });
                  v3State.currentProject = null;
                  v3State.projectOpening = false;
                  v3State.view = "home";
                  await openV3Project("unavailable-project");
                  return {
                    view: v3State.view,
                    currentProjectId: v3State.currentProject?.project_id || "",
                    opening: Boolean(v3State.projectOpening),
                    workspaceVisible: document.querySelector("#v3WorkspaceView")?.hidden === false,
                    homeVisible: document.querySelector("#v3HomeView")?.hidden === false,
                    explicitHome: Boolean(v3State.explicitHome),
                  };
                }
                """,
            )
            assert result["view"] == "home"
            assert result["currentProjectId"] == ""
            assert result["opening"] is False
            assert result["workspaceVisible"] is False
            assert result["homeVisible"] is True
            assert result["explicitHome"] is True
        finally:
            browser.close()


def test_desktop_home_preview_does_not_swallow_scoped_history_request() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            requests = page.evaluate(
                """
                async () => {
                  const requests = [];
                  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
                  window.fetch = async (input) => {
                    const url = String(input);
                    requests.push(url);
                    await delay(url.includes("surface=home_preview") ? 160 : 20);
                    return new Response(JSON.stringify({ items: [], review_items: [] }), { status: 200 });
                  };
                  v3State.currentProject = null;
                  v3State.imageHistoryLoading = false;
                  v3State.projectOutputsRequest = null;
                  v3State.projectOutputsRequestOwner = null;
                  v3State.projectOutputsRequestKey = "";
                  const homePreview = loadV3ProjectOutputs({
                    force: true,
                    limit: 1,
                    surface: "home_preview",
                  });
                  await delay(10);
                  const scopedHistory = loadV3ProjectOutputs({
                    force: true,
                    limit: 120,
                    projectId: "race-project",
                  });
                  await Promise.all([homePreview, scopedHistory]);
                  return requests;
                }
                """,
            )
            assert len(requests) == 2
            assert any("surface=home_preview" in url and "project_id=" not in url for url in requests)
            assert any("project_id=race-project" in url and "surface=home_preview" not in url for url in requests)
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
                  // A causal barrier proves that preview release does not
                  // wait for history, independent of a busy CI machine's clock.
                  const historyGate = new Promise(resolve => { window.__releaseMobileHistory = resolve; });
                  window.__mobileHistoryCompleted = 0;
                  window.__mobileHistoryPending = 0;
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
                    if (isFullProject || isTimeline || isOutputs) {
                      window.__mobileHistoryPending++;
                      await historyGate;
                      window.__mobileHistoryCompleted++;
                    }
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
                  historyCompleted: window.__mobileHistoryCompleted,
                  historyPending: window.__mobileHistoryPending,
                  backgroundRequests: window.__mobileProgressiveRequests.filter(({ url }) =>
                    url.includes("/timeline") || url.includes("/project-outputs") || url.includes("/projects/mobile-progressive-project")
                  ).length,
                  firstPreviewCount: document.querySelectorAll("img[data-mobile-v3-project-first-preview='true']").length,
                })
                """
            )
            assert result["firstPreviewCount"] == 1
            assert result["backgroundRequests"] >= 3
            assert result["historyPending"] >= 1
            assert result["historyCompleted"] == 0
            page.evaluate("window.__releaseMobileHistory()")
        finally:
            browser.close()
