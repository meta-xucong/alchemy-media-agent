"""Regression contracts for the V3 home bootstrap performance repair."""

import base64
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore, V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import OutputRef
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
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "301_V3_HOME_BOOTSTRAP_PERFORMANCE_AND_V2_PARITY_SPEC.md"
ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def _service() -> tuple[V3ProjectModeService, str]:
    service = V3ProjectModeService(
        product_service=V3ProductApiService(),
        project_store=InMemoryProjectStore(),
    )
    response = service.create_project({"user_goal": "Create a useful project preview."})
    assert response.project is not None
    return service, response.project.project_id


def test_summary_project_list_does_not_reconcile_jobs_outputs_or_timeline() -> None:
    service, project_id = _service()

    def unexpected(*_args, **_kwargs):
        raise AssertionError("summary catalog must not read the full project history")

    service._memory_summary = unexpected
    service._project_output_items = unexpected
    service._latest_project_job_status = unexpected
    service.project_store.list_timeline = unexpected

    response = service.list_projects(limit=1, view="summary")

    assert [item.project_id for item in response.projects] == [project_id]
    assert response.metadata["view"] == "summary"
    assert response.projects[0].latest_thumbnail_urls == []
    assert response.projects[0].latest_job_status is None


def test_summary_project_list_does_not_dereference_selected_output_records() -> None:
    service, project_id = _service()
    project = service.project_store.get_project(project_id)
    assert project is not None
    project.selected_output_refs = [
        OutputRef(
            output_ref_id="output-ref-summary",
            source_type="generated_output",
            project_id=project_id,
            output_id="v3_output_summary_selected",
            selected_at=project.updated_at,
        )
    ]
    service.project_store.save_project(project)

    def unexpected(*_args, **_kwargs):
        raise AssertionError("summary catalog must not dereference output records")

    service.product_service.output_store.get_output = unexpected

    response = service.list_projects(limit=1, owner_user_id=None, view="summary")

    assert response.projects[0].selected_asset_count == 1


def test_global_output_delivery_and_review_share_one_request_snapshot() -> None:
    project = SimpleNamespace(
        project_id="project_snapshot",
        status="active",
        job_ids=["job_snapshot"],
    )
    calls = {"job": 0, "job_record": 0, "output": 0}
    output_record = SimpleNamespace(output_id="v3_output_snapshot", job_id="job_snapshot")

    class _Product:
        output_store = SimpleNamespace(
            list_by_job=lambda _job_id: calls.__setitem__("output", calls["output"] + 1) or [output_record],
        )

        @staticmethod
        def get_job(_job_id):
            calls["job"] += 1
            return SimpleNamespace(metadata={})

        @staticmethod
        def get_job_record(_job_id):
            calls["job_record"] += 1
            return SimpleNamespace(request=SimpleNamespace(metadata={}))

    service = object.__new__(V3ProjectModeService)
    service.product_service = _Product()
    service.project_store = SimpleNamespace(list_projects=lambda limit: [project])
    service._metadata = lambda: {}
    service._project_visible_to_owner = lambda *_args: True
    delivery_kwargs = []
    review_kwargs = []
    service._project_output_items = lambda *_args, **kwargs: delivery_kwargs.append(kwargs) or []
    service._project_review_output_items = lambda *_args, **kwargs: review_kwargs.append(kwargs) or []

    response = service.list_project_outputs(limit=1, compact=True)

    assert response["items"] == []
    assert response["review_items"] == []
    assert calls == {"job": 1, "job_record": 1, "output": 1}
    assert delivery_kwargs[0]["job_status_by_id"] is review_kwargs[0]["job_status_by_id"]
    assert delivery_kwargs[0]["job_record_by_id"] is review_kwargs[0]["job_record_by_id"]
    assert delivery_kwargs[0]["output_records_by_job"] is review_kwargs[0]["output_records_by_job"]


def test_default_project_list_keeps_full_view_compatibility_metadata() -> None:
    service, _project_id = _service()

    response = service.list_projects(limit=1)

    assert response.metadata["view"] == "full"
    assert response.projects[0].latest_job_status is None


def test_home_preview_is_bounded_delivery_only_and_skips_full_history_paths() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="project_home_preview",
        status="active",
    )
    service.project_store = SimpleNamespace(list_projects=lambda limit: [project])
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_delivery_preview_items = lambda *_args, **_kwargs: [
        {
            "project_id": project.project_id,
            "output_id": "v3_output_preview",
            "created_at": "2026-09-13T00:00:00Z",
        }
    ]
    service._project_output_items = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("home preview must not use the full delivery/history projection")
    )
    service._project_review_output_items = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("home preview must not read review history")
    )
    service._reconcile_project_outputs = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("home preview must not reconcile project history")
    )
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
    )

    assert response["items"][0]["output_id"] == "v3_output_preview"
    assert response["review_items"] == []
    assert response["metadata"]["surface"] == "home_preview"
    assert response["metadata"]["complete"] is False


def test_desktop_home_bootstrap_waits_for_first_page_output_and_images() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    shell = source.split("async function initV3Shell", 1)[1].split(
        "function clearV3PendingUploads", 1
    )[0]
    projects = source.split("async function loadV3Projects", 1)[1].split(
        "async function loadV3History", 1
    )[0]

    assert "&view=summary" in shell
    assert "surface: \"home_preview\"" in shell
    assert "await loadV3ProjectOutputs" in shell
    assert "await waitForV3FirstHomePreviewImage" not in shell
    assert "await waitForV3HomePreviewImages({ blockPage: true });" in shell
    assert "void loadV3ProjectOutputs({" not in shell
    assert shell.index("await loadV3ProjectOutputs") < shell.index("await waitForV3HomePreviewImages")
    assert 'v3State.imageHistoryLoaded = normalizedSurface !== "home_preview"' in source
    assert 'const previewOnly = v3State.imageHistorySurface === "home_preview"' in source
    assert "if ((!group.items.length || previewOnly) && group.projectId)" in source
    assert "&view=summary${cursor}" in projects
    assert "!v3State.loading" in source.split("function openV3Home", 1)[1].split(
        "function openV3ProfessionalWorkspace", 1
    )[0]


def test_mobile_home_bootstrap_waits_for_first_page_output_and_images() -> None:
    source = MOBILE.read_text(encoding="utf-8")
    loader = source.split("async function loadMobileV3Projects", 1)[1].split(
        "function setMobileV3LoadingLayer", 1
    )[0]

    assert "&view=summary${cursor}" in loader
    assert "surface=home_preview" in loader
    assert "await mobileV3Request(`/project-outputs?limit=${mobileV3ProjectPageSize}&compact=true`)" not in loader
    assert "await waitForMobileV3FirstHomePreviewImage()" not in loader
    assert "await mobileV3Request(" in loader
    assert "await waitForMobileV3HomePreviewImages({ blockPage: true });" in loader
    assert loader.index("await mobileV3Request(") < loader.index("await waitForMobileV3HomePreviewImages")
    assert "previewProjectIds" in source
    assert "已有封面 · 点击查看全部" in source


def test_desktop_home_mask_stays_visible_until_slow_first_page_image_settles() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)

            def fulfill_slow_image(route) -> None:
                time.sleep(0.28)
                route.fulfill(
                    status=200,
                    content_type="image/png",
                    body=base64.b64decode(ONE_PIXEL_PNG),
                )

            page.route("http://image.test/home-cover.png", fulfill_slow_image)
            result = page.evaluate(
                """
                async () => {
                  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
                  const project = {
                    project_id: "home-bootstrap-project",
                    title: "Home bootstrap project",
                    user_goal: "Create a useful project preview.",
                    short_summary: "Create a useful project preview.",
                    primary_template_id: "general_template",
                    status: "active",
                    updated_at: "2026-09-14T00:01:00Z",
                    latest_thumbnail_urls: [],
                  };
                  const template = {
                    template_id: "general_template",
                    display_name: "通用创意",
                    project_can_create_jobs: true,
                  };
                  const output = {
                    output_id: "home-bootstrap-output",
                    project_id: project.project_id,
                    delivery_state: "final_delivery",
                    created_at: "2026-09-14T00:02:00Z",
                    thumbnail_url: "http://image.test/home-cover.png",
                  };
                  window.fetch = async (input) => {
                    const url = String(input);
                    if (url.includes("/projects?") && url.includes("view=summary")) {
                      await delay(20);
                      return new Response(JSON.stringify({
                        projects: [project],
                        templates: [template],
                        total: 1,
                        has_more: false,
                        next_cursor: null,
                      }), { status: 200 });
                    }
                    if (url.includes("/project-outputs?") && url.includes("surface=home_preview")) {
                      await delay(20);
                      return new Response(JSON.stringify({ items: [output], review_items: [] }), { status: 200 });
                    }
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  v3State.loaded = false;
                  v3State.loading = false;
                  v3State.projects = [];
                  v3State.projectsLoaded = false;
                  v3State.projectsLoading = false;
                  v3State.templates = [];
                  v3State.templateCatalogStatus = "idle";
                  v3State.imageHistory = [];
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryLoading = false;
                  v3State.imageHistorySurface = "none";
                  v3State.imageHistoryError = "";
                  v3State.projectOutputsRequest = null;
                  v3State.projectOutputsRequestOwner = null;
                  v3State.projectOutputsRequestKey = "";
                  const bootstrap = initV3Shell();
                  await delay(100);
                  const during = {
                    maskHidden: Boolean(document.querySelector("#v3PageLoadingOverlay")?.hidden),
                    imageComplete: Boolean(document.querySelector("img[data-v3-home-thumb='true']")?.complete),
                  };
                  await bootstrap;
                  return {
                    during,
                    maskHidden: Boolean(document.querySelector("#v3PageLoadingOverlay")?.hidden),
                    imageLoaded: Boolean(document.querySelector("img[data-v3-home-thumb='true']")?.naturalWidth),
                  };
                }
                """,
            )
            assert result["during"]["maskHidden"] is False
            assert result["during"]["imageComplete"] is False
            assert result["maskHidden"] is True
            assert result["imageLoaded"] is True
        finally:
            browser.close()


def test_mobile_home_mask_stays_visible_until_slow_first_page_image_settles() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)

            def fulfill_slow_image(route) -> None:
                time.sleep(0.28)
                route.fulfill(
                    status=200,
                    content_type="image/png",
                    body=base64.b64decode(ONE_PIXEL_PNG),
                )

            page.route("http://image.test/mobile-home-cover.png", fulfill_slow_image)
            result = page.evaluate(
                """
                async () => {
                  const delay = (ms) => new Promise((resolve) => window.setTimeout(resolve, ms));
                  const project = {
                    project_id: "mobile-home-bootstrap-project",
                    title: "Mobile home bootstrap project",
                    user_goal: "Create a useful project preview.",
                    short_summary: "Create a useful project preview.",
                    primary_template_id: "general_template",
                    status: "active",
                    updated_at: "2026-09-14T00:01:00Z",
                    latest_thumbnail_urls: [],
                  };
                  const template = {
                    template_id: "general_template",
                    display_name: "通用创意",
                    project_can_create_jobs: true,
                  };
                  const output = {
                    output_id: "mobile-home-bootstrap-output",
                    project_id: project.project_id,
                    delivery_state: "final_delivery",
                    created_at: "2026-09-14T00:02:00Z",
                    thumbnail_url: "http://image.test/mobile-home-cover.png",
                  };
                  window.fetch = async (input) => {
                    const url = String(input);
                    if (url.includes("/projects?") && url.includes("view=summary")) {
                      await delay(20);
                      return new Response(JSON.stringify({
                        projects: [project],
                        templates: [template],
                        total: 1,
                        has_more: false,
                        next_cursor: null,
                      }), { status: 200 });
                    }
                    if (url.includes("/project-outputs?") && url.includes("surface=home_preview")) {
                      await delay(20);
                      return new Response(JSON.stringify({ items: [output], review_items: [] }), { status: 200 });
                    }
                    return new Response(JSON.stringify({}), { status: 200 });
                  };
                  mobileV3State.loaded = false;
                  mobileV3State.loading = false;
                  mobileV3State.projects = [];
                  mobileV3State.projectsNextCursor = null;
                  mobileV3State.projectsHasMore = false;
                  mobileV3State.templates = [];
                  mobileV3State.templatesLoaded = false;
                  mobileV3State.outputs = [];
                  mobileV3State.outputsLoaded = false;
                  mobileV3State.outputsSurface = "none";
                  mobileV3State.outputError = "";
                  const bootstrap = loadMobileV3Projects({ silent: true, force: true });
                  await delay(100);
                  const during = {
                    maskHidden: Boolean(document.querySelector("#mobileV3LoadingLayer")?.hidden),
                    imageComplete: Boolean(document.querySelector("img[data-mobile-v3-home-thumb='true']")?.complete),
                  };
                  await bootstrap;
                  return {
                    during,
                    maskHidden: Boolean(document.querySelector("#mobileV3LoadingLayer")?.hidden),
                    imageLoaded: Boolean(document.querySelector("img[data-mobile-v3-home-thumb='true']")?.naturalWidth),
                  };
                }
                """,
            )
            assert result["during"]["maskHidden"] is False
            assert result["during"]["imageComplete"] is False
            assert result["maskHidden"] is True
            assert result["imageLoaded"] is True
        finally:
            browser.close()


def test_home_output_loader_allows_small_preview_limit_without_global_minimum() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    loader = source.split("async function loadV3ProjectOutputs", 1)[1].split(
        "function clearV3PendingUploads", 1
    )[0]

    assert "surface = \"\"" in loader
    assert 'normalizedSurface === "home_preview" ? 1 : 12' in loader
    assert "surfaceQuery" in loader


def test_desktop_output_request_dedupe_is_scoped_to_semantic_request_key() -> None:
    source = DESKTOP.read_text(encoding="utf-8")
    loader = source.split("async function loadV3ProjectOutputs", 1)[1].split(
        "function clearV3PendingUploads", 1
    )[0]

    assert "projectOutputsRequestKey" in loader
    assert 'normalizedSurface || "full"' in loader
    assert "String(boundedLimit)" in loader
    assert "v3State.projectOutputsRequestKey === requestKey" in loader


def test_output_store_reuses_warm_record_index_and_rechecks_changed_media(tmp_path: Path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_home_cache",
        candidate_id="candidate_home_cache",
        asset_id="asset_home_cache",
        provider="test",
        model="test-model",
        encoded_image=ONE_PIXEL_PNG,
    )
    assert store.list_by_job(record.job_id)

    with patch.object(Path, "read_text", side_effect=AssertionError("warm get_output must use the parsed index")):
        assert store.get_output(record.output_id) is not None

    assert store.file_for_variant(record.output_id, "thumbnail") is not None
    original = Path(record.file_path)
    original.write_bytes(original.read_bytes() + b"changed")
    assert store.file_for_variant(record.output_id, "thumbnail") is None


def test_doc301_freezes_compatibility_and_acceptance_boundaries() -> None:
    doc = DOC.read_text(encoding="utf-8")

    assert "GET /api/v3/creative-agent/projects?view=summary" in doc
    assert "surface=home_preview" in doc
    assert "Existing callers" in doc
    assert "No Brain, Provider, Review, Retry" in doc
    assert "independently audited" in doc
