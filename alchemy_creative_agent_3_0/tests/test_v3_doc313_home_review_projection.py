"""Regression contracts for honest V3 home review-only image projection."""

from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.project_mode import V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc311_legacy_project_output_projection import (
    _service_with_legacy_output,
)


ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "alchemy_creative_agent_3_0" / "app" / "project_mode" / "service.py"
DESKTOP = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"
DOC = ROOT / "alchemy_creative_agent_3_0" / "docs" / "313_V3_HOME_REVIEW_PROJECTION_REPAIR_SPEC.md"


def test_home_snapshot_is_lazy_and_marks_index_overflow_incomplete() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(project_id="overflow-project", job_ids=[])
    records = [
        SimpleNamespace(
            output_id=f"output-{index}",
            job_id=f"job-{index}",
            metadata={"project_id": project.project_id},
        )
        for index in range(4097)
    ]
    calls: list[str] = []
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: records[:limit],
        ),
        get_job=lambda job_id: calls.append(f"job:{job_id}") or None,
        get_job_record=lambda job_id: calls.append(f"record:{job_id}") or None,
    )

    snapshot = service._project_output_read_snapshot(
        [project],
        use_project_index=True,
        prefetch_job_state=False,
        project_index_limit=4096,
    )

    assert snapshot["project_index_complete"][project.project_id] is False
    assert len(snapshot["records_by_project"][project.project_id]) == 4097
    assert calls == []


def test_home_preview_skips_exact_counts_when_job_state_budget_is_exceeded() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="budget-project",
        status="active",
        job_ids=[f"job-{index}" for index in range(65)],
    )
    records = [
        SimpleNamespace(
            output_id=f"output-{index}",
            job_id=f"job-{index}",
            created_at=f"2026-09-14T00:{index:02d}:00Z",
            metadata={"project_id": project.project_id},
        )
        for index in range(65)
    ]
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: [project],
        list_projects=lambda limit: [project],
    )
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: records[:limit],
        ),
        get_job=lambda _job_id: None,
        get_job_record=lambda _job_id: None,
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_visible_output_count = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("over-budget home project must keep the exact count unknown")
    )
    preview_limits: list[int | None] = []
    service._project_delivery_preview_items = lambda _project, **kwargs: (
        preview_limits.append(kwargs.get("candidate_job_limit")) or []
    )
    service._project_legacy_history_items = lambda *_args, **_kwargs: []
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["project_output_counts"] == {}
    assert response["project_review_counts"] == {}
    assert preview_limits == [64]


def test_home_history_adapter_is_bounded_and_count_stays_unknown_over_budget() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="history-budget-project",
        status="active",
        job_ids=[f"job-{index}" for index in range(1000)],
    )
    records = [
        SimpleNamespace(
            output_id=f"output-{index}",
            job_id=f"job-{index}",
            created_at=f"2026-09-14T00:{index // 60:02d}:{index % 60:02d}Z",
            thumbnail_url=f"http://image.test/{index}.png",
            metadata={"project_id": project.project_id},
        )
        for index in range(1000)
    ]
    history_candidate_ids: list[str] = []
    preview_candidate_ids: list[str] = []
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: [project],
        list_projects=lambda limit: [project],
    )
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: records[:limit],
            list_by_job=lambda _job_id: [],
        ),
        get_job=lambda _job_id: None,
        get_job_record=lambda _job_id: None,
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_delivery_preview_items = (
        lambda _project, **kwargs: preview_candidate_ids.extend(kwargs["home_candidate_job_ids"]) or []
    )

    def capture_history_project(_project, _records, **kwargs):
        history_candidate_ids.extend(kwargs["candidate_job_ids"])
        return SimpleNamespace(job_ids=list(kwargs["candidate_job_ids"]))

    service._project_home_review_projection_project = capture_history_project
    service._project_legacy_history_items = lambda *_args, **_kwargs: []
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert history_candidate_ids == project.job_ids[-64:]
    assert preview_candidate_ids == list(reversed(history_candidate_ids))
    assert response["project_history_counts"] == {}
    assert response["project_output_counts"] == {}
    assert response["project_review_counts"] == {}


def test_home_output_only_history_is_bounded_and_count_stays_unknown_over_budget() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="output-only-history-budget-project",
        status="active",
        job_ids=[],
    )
    project.model_copy = lambda *, update, deep=False: SimpleNamespace(
        project_id=project.project_id,
        job_ids=list(update["job_ids"]),
        selected_output_states=[],
    )
    records = [
        SimpleNamespace(
            output_id=f"output-{index}",
            job_id=f"job-{index}",
            created_at=f"2026-09-14T00:{index // 60:02d}:{index % 60:02d}Z",
            thumbnail_url=f"http://image.test/{index}.png",
            metadata={"project_id": project.project_id},
        )
        for index in range(100)
    ]
    history_record_count: list[int] = []
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: [project],
        list_projects=lambda limit: [project],
    )
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: records[:limit],
            list_by_job=lambda _job_id: [],
        ),
        get_job=lambda _job_id: None,
        get_job_record=lambda _job_id: None,
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_delivery_preview_items = lambda *_args, **_kwargs: []
    service._project_legacy_history_items = (
        lambda _project, **kwargs: history_record_count.append(len(kwargs["project_records"])) or []
    )
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert history_record_count == [64]
    assert response["project_output_counts"] == {}
    assert response["project_history_counts"] == {}


def test_home_omits_count_maps_when_a_candidate_job_read_fails() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="job-read-failure-project",
        status="active",
        job_ids=["job-unavailable"],
        selected_output_states=[],
    )
    project.model_copy = lambda *, update, deep=False: SimpleNamespace(
        project_id=project.project_id,
        job_ids=list(update["job_ids"]),
        selected_output_states=[],
    )
    record = SimpleNamespace(
        output_id="output-unavailable",
        job_id="job-unavailable",
        created_at="2026-09-14T00:00:00Z",
        metadata={"project_id": project.project_id},
    )
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: [project],
        list_projects=lambda limit: [project],
    )

    def unavailable_job(_job_id):
        raise RuntimeError("job store unavailable")

    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: [record],
            list_by_job=lambda _job_id: [record],
        ),
        get_job=unavailable_job,
        get_job_record=lambda _job_id: None,
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_home_review_projection_project = (
        lambda _project, _project_records, **kwargs: SimpleNamespace(
            job_ids=list(kwargs["candidate_job_ids"]),
        )
    )
    service._project_legacy_history_items = lambda *_args, **_kwargs: []
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["items"] == []
    assert response["history_items"] == []
    assert response["project_output_counts"] == {}
    assert response["project_review_counts"] == {}
    assert response["project_history_counts"] == {}


def test_home_preview_falls_back_to_declared_job_outputs_when_project_link_is_missing() -> None:
    service = object.__new__(V3ProjectModeService)
    project = SimpleNamespace(
        project_id="legacy-job-link-project",
        status="active",
        job_ids=["job-legacy-link"],
    )
    record = SimpleNamespace(
        output_id="legacy-output-1",
        job_id="job-legacy-link",
        created_at="2026-09-14T00:00:00Z",
        thumbnail_url="http://image.test/legacy.png",
        preview_url="http://image.test/legacy.png",
        download_url="http://image.test/legacy.png",
        metadata={"veyra_user_id": 7},
    )
    list_by_job_calls: list[str] = []
    service.project_store = SimpleNamespace(
        list_all_projects=lambda: [project],
        list_projects=lambda limit: [project],
    )
    service.product_service = SimpleNamespace(
        output_store=SimpleNamespace(
            list_by_project=lambda _project_id, limit: [],
            list_by_job=lambda job_id: list_by_job_calls.append(job_id) or [record],
        ),
        get_job=lambda _job_id: None,
        get_job_record=lambda _job_id: None,
    )
    service._project_visible_to_owner = lambda _project, _owner: True
    service._project_visible_output_count = lambda _project, **kwargs: (
        0 if any(item is record for item in kwargs["project_records"]) else -1
    )
    service._project_delivery_preview_items = lambda _project, **kwargs: (
        [] if any(item is record for item in kwargs["project_records"]) else ["missing"]
    )
    service._project_home_review_projection_project = (
        lambda _project, _project_records, **kwargs: SimpleNamespace(
            job_ids=list(kwargs["candidate_job_ids"]),
        )
    )
    service._project_review_output_items = lambda _project, **_kwargs: [
        {
            "project_id": project.project_id,
            "output_id": record.output_id,
            "job_id": record.job_id,
            "thumbnail_url": record.thumbnail_url,
            "preview_url": record.preview_url,
            "created_at": record.created_at,
            "metadata": {},
        }
    ]
    service._project_legacy_history_items = lambda *_args, **_kwargs: []
    service._metadata = lambda: {"service": "test"}

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert list_by_job_calls == [record.job_id]
    assert response["project_output_counts"] == {project.project_id: 0}
    assert response["project_review_counts"] == {project.project_id: 1}
    assert response["project_review_preview_items"][0]["output_id"] == record.output_id


def test_home_declared_job_fallback_preserves_real_review_classification(tmp_path: Path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = output_store.save_base64_output(
        job_id="job-real-legacy-review",
        candidate_id="candidate-real-legacy-review",
        asset_id="asset-real-legacy-review",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        ),
        output_id="v3_output_00000000000000000002",
        metadata={"veyra_user_id": 7},
    )
    status = SimpleNamespace(
        job_id=record.job_id,
        status=ProductJobStatusValue.BLOCKED,
        metadata={"specialized_execution_summary": {"final_delivery_withheld": True}},
    )
    job_record = SimpleNamespace(request=SimpleNamespace(metadata={}))
    product_service = SimpleNamespace(
        output_store=output_store,
        get_job=lambda _job_id: status,
        get_job_record=lambda _job_id: job_record,
    )
    project_store = InMemoryProjectStore()
    service = V3ProjectModeService(product_service=product_service, project_store=project_store)
    project = ProjectRecord(
        project_id="project-real-legacy-review",
        title="Legacy review fallback",
        user_goal="Keep the old review image discoverable.",
        short_summary="Keep the old review image discoverable.",
        job_ids=[record.job_id],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
        metadata={"veyra_user_id": 7},
    )
    project_store.save_project(project)

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["items"] == []
    assert response["history_items"] == []
    assert response["project_output_counts"] == {project.project_id: 0}
    assert response["project_review_counts"] == {project.project_id: 1}
    assert response["project_review_preview_items"][0]["output_id"] == record.output_id


def test_home_preview_reports_review_count_and_safe_cover_without_formal_promotion(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(tmp_path)
    project.job_ids = [record.job_id]
    service.project_store.save_project(project)

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["items"] == []
    assert response["review_items"] == []
    assert response["history_items"] == []
    assert response["project_output_counts"] == {project.project_id: 0}
    assert response["project_review_counts"] == {project.project_id: 1}
    previews = response["project_review_preview_items"]
    assert [item["output_id"] for item in previews] == [record.output_id]
    assert previews[0]["project_id"] == project.project_id
    assert previews[0]["review_only"] is True
    assert previews[0]["metadata"]["home_review_preview"] is True
    assert previews[0]["thumbnail_url"] == record.thumbnail_url


def test_home_preview_keeps_formal_and_review_count_maps_independent(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(tmp_path, closed=True)
    project.job_ids = [record.job_id]
    service.project_store.save_project(project)

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["project_output_counts"] == {project.project_id: 1}
    assert response["project_review_counts"] == {project.project_id: 0}
    assert response["project_review_preview_items"] == []
    assert [item["output_id"] for item in response["items"]] == [record.output_id]


def test_desktop_home_labels_review_only_count_and_renders_review_cover() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "desktop-review-home",
                    title: "Review home project",
                    user_goal: "Keep the review image discoverable.",
                    short_summary: "Keep the review image discoverable.",
                    primary_template_id: "general_template",
                    status: "active",
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    review_output_count: 6,
                    review_output_count_known: true,
                    history_output_count: 0,
                    history_output_count_known: true,
                    latest_thumbnail_urls: [],
                    latest_review_thumbnail_urls: ["http://image.test/review-home.png"],
                    job_count: 1,
                    updated_at: "2026-09-14T00:00:00Z",
                  };
                  v3State.workspaceMode = "standard";
                  v3State.projects = [project];
                  v3State.projectRenderLimit = 4;
                  v3State.projectsHasMore = false;
                  v3State.projectsLoading = false;
                  v3State.imageHistory = [];
                  v3State.imageHistorySurface = "home_preview";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  renderV3Projects();
                  renderV3History();
                  return {
                    historyText: document.querySelector("#v3HistoryList")?.textContent || "",
                    imageSources: [...document.querySelectorAll("#v3HistoryList img")].map((item) => item.src),
                  };
                }
                """,
            )
            assert "6 张待复核图片" in result["historyText"]
            assert any("review-home.png" in source for source in result["imageSources"])
            assert "0 张图片" not in result["historyText"]
        finally:
            browser.close()


def test_mobile_home_labels_review_only_count_and_renders_review_cover() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            result = page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "mobile-review-home",
                    title: "Mobile review home project",
                    user_goal: "Keep the review image discoverable.",
                    short_summary: "Keep the review image discoverable.",
                    primary_template_id: "general_template",
                    status: "active",
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    review_output_count: 5,
                    review_output_count_known: true,
                    history_output_count: 0,
                    history_output_count_known: true,
                    latest_thumbnail_urls: [],
                    latest_review_thumbnail_urls: ["http://image.test/mobile-review-home.png"],
                    job_count: 1,
                    updated_at: "2026-09-14T00:00:00Z",
                  };
                  mobileV3State.workspaceMode = "standard";
                  mobileV3State.projects = [project];
                  mobileV3State.projectRenderLimit = 4;
                  mobileV3State.projectsHasMore = false;
                  mobileV3State.projectsLoading = false;
                  mobileV3State.outputs = [];
                  mobileV3State.outputsLoaded = true;
                  mobileV3State.outputsSurface = "home_preview";
                  mobileV3State.outputError = "";
                  mobileV3State.previewProjectIds = new Set();
                  renderMobileV3ProjectCards();
                  return {
                    text: document.querySelector("#mobileV3ProjectGrid")?.textContent || "",
                    imageSources: [...document.querySelectorAll("#mobileV3ProjectGrid img")].map((item) => item.src),
                  };
                }
                """,
            )
            assert "5 张待复核图片" in result["text"]
            assert any("mobile-review-home.png" in source for source in result["imageSources"])
            assert "0 张图片" not in result["text"]
        finally:
            browser.close()


def test_home_review_cache_clears_stale_cover_and_accepts_new_cover() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop_page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            desktop_result = desktop_page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "desktop-review-cache",
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    history_output_count: 0,
                    history_output_count_known: true,
                    latest_thumbnail_urls: ["http://image.test/stale-formal.png"],
                    latest_review_thumbnail_urls: ["http://image.test/stale.png"],
                    review_output_count: 4,
                    review_output_count_known: true,
                  };
                  v3State.projects = [project];
                  const preProjection = v3ProjectThumbnailItem(project);
                  syncV3HomeProjectProjection({
                    projectIds: ["desktop-review-cache"],
                    formalCounts: {},
                    historyCounts: {},
                    reviewCounts: {},
                    displayItems: [],
                    reviewPreviewItems: [],
                  });
                  const cleared = v3State.projects[0].latest_review_thumbnail_urls;
                  v3State.imageHistoryError = "home timeout";
                  v3State.imageHistoryError = "";
                  markV3HomePreviewStale(["desktop-review-cache"]);
                  const staleLabel = v3ProjectImageCountText(v3State.projects[0]);
                  syncV3HomeProjectProjection({
                    projectIds: ["desktop-review-cache"],
                    formalCounts: { "desktop-review-cache": 0 },
                    historyCounts: { "desktop-review-cache": 0 },
                    reviewCounts: { "desktop-review-cache": 2 },
                    displayItems: [],
                    reviewPreviewItems: [
                      {
                        project_id: "desktop-review-cache",
                        thumbnail_url: "http://image.test/current.png",
                      },
                    ],
                  });
                  return {
                    cleared,
                    current: v3State.projects[0].latest_review_thumbnail_urls,
                    count: v3State.projects[0].review_output_count,
                    staleLabel,
                    preProjection: {
                      url: preProjection?.thumbnail_url,
                      reviewOnly: preProjection?.review_only,
                    },
                  };
                }
                """,
            )
            mobile_page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            mobile_result = mobile_page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "mobile-review-cache",
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    history_output_count: 0,
                    history_output_count_known: true,
                    latest_thumbnail_urls: ["http://image.test/stale-formal.png"],
                    latest_review_thumbnail_urls: ["http://image.test/stale.png"],
                    review_output_count: 4,
                    review_output_count_known: true,
                  };
                  mobileV3State.projects = [project];
                  const preProjection = mobileV3ProjectThumbnailItem(project);
                  syncMobileV3HomeProjectProjection({
                    projectIds: ["mobile-review-cache"],
                    formalCounts: {},
                    historyCounts: {},
                    reviewCounts: {},
                    displayItems: [],
                    reviewPreviewItems: [],
                  });
                  const cleared = mobileV3State.projects[0].latest_review_thumbnail_urls;
                  mobileV3State.outputError = "";
                  markMobileV3HomePreviewStale(["mobile-review-cache"]);
                  const staleLabel = mobileV3ProjectImageCountLabel({
                    project: mobileV3State.projects[0],
                    reviewCount: 4,
                  });
                  syncMobileV3HomeProjectProjection({
                    projectIds: ["mobile-review-cache"],
                    formalCounts: { "mobile-review-cache": 0 },
                    historyCounts: { "mobile-review-cache": 0 },
                    reviewCounts: { "mobile-review-cache": 2 },
                    displayItems: [],
                    reviewPreviewItems: [
                      {
                        project_id: "mobile-review-cache",
                        thumbnail_url: "http://image.test/current.png",
                      },
                    ],
                  });
                  return {
                    cleared,
                    current: mobileV3State.projects[0].latest_review_thumbnail_urls,
                    count: mobileV3State.projects[0].review_output_count,
                    staleLabel,
                    preProjection: {
                      url: preProjection?.thumbnail_url,
                      reviewOnly: preProjection?.review_only,
                    },
                  };
                }
                """,
            )
            assert desktop_result == {
                "cleared": [],
                "current": ["http://image.test/current.png"],
                "count": 2,
                "staleLabel": "图片暂时无法读取",
                "preProjection": {
                    "url": "http://image.test/stale.png",
                    "reviewOnly": True,
                },
            }
            assert mobile_result == desktop_result
        finally:
            browser.close()


def test_home_projection_does_not_restore_stale_nested_counts_or_preview_counts() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop_page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            desktop_result = desktop_page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "desktop-direct-count-authority",
                    visible_output_count: 0,
                    visible_output_count_known: false,
                    history_output_count: 0,
                    history_output_count_known: false,
                    review_output_count: 0,
                    review_output_count_known: false,
                    memory_summary: {
                      visible_output_count: 12,
                      visible_output_count_known: true,
                      history_output_count: 4,
                      history_output_count_known: true,
                      review_output_count: 8,
                      review_output_count_known: true,
                    },
                    job_count: 1,
                  };
                  v3State.imageHistorySurface = "home_preview";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  const homeText = v3ProjectImageCountText(project);
                  const groupText = v3ProjectImageCountLabel({
                    project,
                    formalCount: 1,
                    items: [{ project_id: project.project_id }],
                  });
                  v3State.imageHistorySurface = "full";
                  v3State.imageHistoryLoaded = true;
                  const fullText = v3ProjectImageCountLabel({
                    project,
                    formalCount: 1,
                    historyCount: 2,
                    reviewCount: 3,
                    items: [{ project_id: project.project_id }],
                  });
                  return {
                    formalKnown: v3ProjectVisibleOutputCountKnown(project),
                    formalText: homeText,
                    fullText,
                    groupText,
                  };
                }
                """,
            )
            mobile_page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            mobile_result = mobile_page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "mobile-direct-count-authority",
                    visible_output_count: 0,
                    visible_output_count_known: false,
                    history_output_count: 0,
                    history_output_count_known: false,
                    review_output_count: 0,
                    review_output_count_known: false,
                    memory_summary: {
                      visible_output_count: 12,
                      visible_output_count_known: true,
                      history_output_count: 4,
                      history_output_count_known: true,
                      review_output_count: 8,
                      review_output_count_known: true,
                    },
                    job_count: 1,
                  };
                  mobileV3State.outputsSurface = "home_preview";
                  mobileV3State.outputsLoaded = false;
                  mobileV3State.outputError = "";
                  const homeText = mobileV3ProjectImageCountLabel({
                    project,
                    formalCount: 1,
                    items: [{ project_id: project.project_id }],
                  });
                  mobileV3State.outputsSurface = "full";
                  mobileV3State.outputsLoaded = true;
                  const fullText = mobileV3ProjectImageCountLabel({
                    project,
                    formalCount: 1,
                    historyCount: 2,
                    reviewCount: 3,
                    items: [{ project_id: project.project_id }],
                  });
                  return {
                    formalKnown: mobileV3ProjectVisibleOutputCountKnown(project),
                    formalText: homeText,
                    fullText,
                  };
                }
                """,
            )
            assert desktop_result == {
                "formalKnown": False,
                "formalText": "图片数量未同步",
                "fullText": "图片数量未同步",
                "groupText": "封面预览 · 数量同步中",
            }
            assert mobile_result == {
                "formalKnown": False,
                "formalText": "图片数量未同步",
                "fullText": "图片数量未同步",
            }
        finally:
            browser.close()


def test_home_review_projection_contract_is_documented_and_isolated() -> None:
    service_source = SERVICE.read_text(encoding="utf-8")
    desktop_source = DESKTOP.read_text(encoding="utf-8")
    mobile_source = MOBILE.read_text(encoding="utf-8")
    doc = DOC.read_text(encoding="utf-8")

    assert "project_review_counts" in service_source
    assert "project_review_preview_items" in service_source
    assert "prefetch_job_state=False" in service_source
    assert "include_declared_job_output_fallback=True" in service_source
    assert "_HOME_PREVIEW_MAX_JOB_STATES" in service_source
    assert "_project_home_bounded_candidate_job_ids" in service_source
    assert "project_index_limit" in service_source
    assert "syncV3HomeProjectReviewCounts" in desktop_source
    assert "syncV3HomeProjectProjection" in desktop_source
    assert "latest_review_thumbnail_urls" in desktop_source
    assert "syncMobileV3HomeProjectReviewCounts" in mobile_source
    assert "syncMobileV3HomeProjectProjection" in mobile_source
    assert "latest_review_thumbnail_urls" in mobile_source
    assert "formal delivery" in doc
    assert "review-only" in doc
    assert "continuation" in doc
