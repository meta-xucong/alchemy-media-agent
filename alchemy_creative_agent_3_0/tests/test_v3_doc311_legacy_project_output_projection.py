"""Regression contracts for legacy V3 project output discovery."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.contracts import ProjectRecord
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)


_ONE_PIXEL_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _project(project_id: str, *, owner_user_id: int = 7) -> ProjectRecord:
    return ProjectRecord(
        project_id=project_id,
        title="Legacy project output projection",
        user_goal="Keep the existing project images visible.",
        short_summary="Keep the existing project images visible.",
        job_ids=[],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
        metadata={"veyra_user_id": owner_user_id},
    )


def _service_with_legacy_output(
    tmp_path: Path,
    *,
    project_id: str = "project_legacy_output",
    output_owner_user_id: int | None = 7,
    closed: bool = False,
) -> tuple[V3ProjectModeService, ProjectRecord, object]:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    metadata = {"project_id": project_id, "requested_image_count": 1}
    if output_owner_user_id is not None:
        metadata["veyra_user_id"] = output_owner_user_id
    record = output_store.save_base64_output(
        job_id="job_legacy_output",
        candidate_id="candidate_legacy_output",
        asset_id="asset_legacy_output",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000001",
        metadata=metadata,
    )
    if closed:
        envelope = {
            "execution_fingerprint": "fingerprint_fixture",
            "envelope_id": "envelope_fixture",
            "resolved_constraint_ledger": {
                "ledger_id": "ledger_fixture",
                "provider_projection": {
                    "capability_projection": {"effective_variation_mode": "delivery_suite"}
                },
            },
        }
        output_store.update_metadata(record.output_id, {"capability_execution_envelope": envelope})
        output_store.save_job_closure(
            record.job_id,
            {
                "schema_version": "v3_output_delivery_closure_v1",
                "job_id": record.job_id,
                "status": "complete",
                "review_evidence_receipt_status": "complete",
                "final_delivery_status": "ready",
                "automatic_delivery_available": True,
                "eligible_output_ids": [record.output_id],
                "execution_fingerprint": "fingerprint_fixture",
                "envelope_id": "envelope_fixture",
                "ledger_id": "ledger_fixture",
                "outputs": [
                    {
                        "output_id": record.output_id,
                        "asset_id": record.asset_id,
                        "candidate_id": record.candidate_id,
                        "content_sha256": record.metadata["content_sha256"],
                    }
                ],
            },
        )
    product_service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    project_store = InMemoryProjectStore()
    service = V3ProjectModeService(product_service=product_service, project_store=project_store)
    project = _project(project_id)
    project_store.save_project(project)
    return service, project, record


def test_legacy_indexed_output_is_projected_to_history_without_job_ids(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(tmp_path)

    response = service.list_project_outputs(project_id=project.project_id, compact=True)

    assert response["items"] == []
    assert response["review_items"] == []
    assert len(response["history_items"]) == 1
    history_item = response["history_items"][0]
    assert history_item["output_id"] == record.output_id
    assert history_item["project_id"] == project.project_id
    assert history_item["history_only"] is True
    assert history_item["delivery_state"] == "history_only"
    assert history_item["metadata"]["history_only"] is True
    assert project.job_ids == []


def test_legacy_indexed_output_with_complete_closure_uses_formal_gate(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(tmp_path, closed=True)

    response = service.list_project_outputs(project_id=project.project_id, compact=True)

    assert [item["output_id"] for item in response["items"]] == [record.output_id]
    assert response["history_items"] == []
    assert response["items"][0]["delivery_state"] == "final_delivery"
    assert project.job_ids == []


def test_legacy_history_count_is_separate_from_formal_count_on_home_preview(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(tmp_path)

    response = service.list_project_outputs(
        limit=1,
        compact=True,
        surface="home_preview",
        project_ids=[project.project_id],
    )

    assert response["items"] == []
    assert [item["output_id"] for item in response["history_items"]] == [record.output_id]
    assert response["project_output_counts"] == {project.project_id: 0}
    assert response["project_history_counts"] == {project.project_id: 1}


def test_legacy_history_respects_project_and_output_owner_boundary(tmp_path: Path) -> None:
    service, project, _record = _service_with_legacy_output(
        tmp_path,
        output_owner_user_id=99,
    )

    response = service.list_project_outputs(
        project_id=project.project_id,
        owner_user_id=7,
        compact=True,
    )

    assert response["items"] == []
    assert response["history_items"] == []


def test_ownerless_legacy_output_inherits_exact_owned_project_visibility(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(
        tmp_path,
        output_owner_user_id=None,
    )

    owned = service.list_project_outputs(
        project_id=project.project_id,
        owner_user_id=7,
        compact=True,
    )
    foreign = service.list_project_outputs(
        project_id=project.project_id,
        owner_user_id=99,
        compact=True,
    )

    assert [item["output_id"] for item in owned["history_items"]] == [record.output_id]
    assert foreign["items"] == []
    assert foreign["history_items"] == []


def test_ownerless_closed_legacy_output_can_reuse_formal_gate_for_owned_project(tmp_path: Path) -> None:
    service, project, record = _service_with_legacy_output(
        tmp_path,
        output_owner_user_id=None,
        closed=True,
    )

    response = service.list_project_outputs(
        project_id=project.project_id,
        owner_user_id=7,
        compact=True,
    )

    assert [item["output_id"] for item in response["items"]] == [record.output_id]
    assert response["history_items"] == []


def test_ownerless_legacy_job_and_output_can_use_exact_owned_project_scope(tmp_path: Path) -> None:
    project_id = "project_ownerless_legacy_scope"
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = output_store.save_base64_output(
        job_id="job_ownerless_legacy_scope",
        candidate_id="candidate_ownerless_legacy_scope",
        asset_id="asset_ownerless_legacy_scope",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000004",
        metadata={"project_id": project_id},
    )
    product_service = SimpleNamespace(
        get_job=lambda job_id: SimpleNamespace(metadata={}, status="generated"),
        get_job_record=lambda job_id: SimpleNamespace(
            request=SimpleNamespace(metadata={}),
        ),
        output_store=output_store,
    )
    project_store = InMemoryProjectStore()
    service = V3ProjectModeService(product_service=product_service, project_store=project_store)
    project = ProjectRecord(
        project_id=project_id,
        title="Ownerless legacy scope",
        user_goal="Keep the owned legacy image visible.",
        short_summary="Keep the owned legacy image visible.",
        job_ids=[record.job_id],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
        metadata={"veyra_user_id": 7},
    )
    project_store.save_project(project)
    service._selected_output_state_map = lambda value: {}
    service._job_delivery_is_settled = lambda value: True
    service._public_output_review_projection = lambda *args: {}
    service._review_projection_allows_project_delivery = lambda value: True
    service._canonical_final_delivery_output_ids = lambda value: set()
    service._delivery_annotations_for_records = lambda records, **_kwargs: {
        item.output_id: {"delivery_state": "final_delivery"}
        for item in records
    }
    service._output_item_from_record = lambda project, item, state, **kwargs: {
        "output_id": item.output_id,
        "project_id": project.project_id,
    }

    items = service._project_output_items(project, owner_user_id=7)

    assert items == [{"output_id": record.output_id, "project_id": project.project_id}]


def test_project_scoped_read_snapshots_only_output_jobs_and_reuses_job_state(tmp_path: Path) -> None:
    project_id = "project_scoped_snapshot"
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = output_store.save_base64_output(
        job_id="job_with_output",
        candidate_id="candidate_scoped_snapshot",
        asset_id="asset_scoped_snapshot",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000005",
        metadata={"project_id": project_id},
    )
    job_calls: list[str] = []
    job_record_calls: list[str] = []
    product_service = SimpleNamespace(
        output_store=output_store,
        get_job=lambda job_id: (
            job_calls.append(job_id)
            or SimpleNamespace(metadata={})
        ),
        get_job_record=lambda job_id: (
            job_record_calls.append(job_id)
            or SimpleNamespace(request=SimpleNamespace(metadata={}))
        ),
    )
    project_store = InMemoryProjectStore()
    service = V3ProjectModeService(product_service=product_service, project_store=project_store)
    project = ProjectRecord(
        project_id=project_id,
        title="Scoped snapshot",
        user_goal="Keep the existing image readable.",
        short_summary="Keep the existing image readable.",
        job_ids=[record.job_id, "job_without_output"],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
        metadata={"veyra_user_id": 7},
    )
    project_store.save_project(project)
    service._reconcile_project_outputs = lambda *_args, **_kwargs: False
    service._job_delivery_is_settled = lambda _status: True
    service._selected_output_state_map = lambda _project: {}
    service._public_output_review_projection = lambda *_args: {}
    service._review_projection_allows_project_delivery = lambda _projection: True
    service._canonical_final_delivery_output_ids = lambda _status: set()
    service._delivery_annotations_for_records = lambda records, **_kwargs: {
        item.output_id: {"delivery_state": "final_delivery"}
        for item in records
    }
    service._output_item_from_record = lambda project, item, state, **_kwargs: {
        "output_id": item.output_id,
        "project_id": project.project_id,
        "created_at": item.created_at,
    }

    response = service.list_project_outputs(
        project_id=project_id,
        owner_user_id=7,
        compact=True,
    )

    assert [item["output_id"] for item in response["items"]] == [record.output_id]
    assert response["review_items"] == []
    assert response["history_items"] == []
    assert job_calls == [record.job_id]
    assert job_record_calls == [record.job_id]


def test_explicit_project_job_recovery_remains_review_only(tmp_path: Path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = output_store.save_base64_output(
        job_id="job_explicit_recovery",
        candidate_id="candidate_explicit_recovery",
        asset_id="asset_explicit_recovery",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000002",
        metadata={"project_id": "project_explicit_recovery", "requested_image_count": 1},
    )
    product_service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    project_store = InMemoryProjectStore()
    service = V3ProjectModeService(product_service=product_service, project_store=project_store)
    project = ProjectRecord(
        project_id="project_explicit_recovery",
        title="Explicit recovery project",
        user_goal="Keep recovery review-only.",
        short_summary="Keep recovery review-only.",
        job_ids=[record.job_id],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
    )
    project_store.save_project(project)

    response = service.list_project_outputs(project_id=project.project_id, compact=True)

    assert response["items"] == []
    assert response["history_items"] == []
    assert [item["output_id"] for item in response["review_items"]] == [record.output_id]


def test_partial_project_job_membership_keeps_undeclared_output_in_history(tmp_path: Path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = output_store.save_base64_output(
        job_id="job_orphaned_from_project",
        candidate_id="candidate_orphaned_from_project",
        asset_id="asset_orphaned_from_project",
        provider="fixture_provider",
        model="fixture_model",
        encoded_image=_ONE_PIXEL_PNG,
        output_id="v3_output_00000000000000000003",
        metadata={"project_id": "project_partial_membership", "requested_image_count": 1},
    )
    product_service = V3ProductApiService(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
    project_store = InMemoryProjectStore()
    service = V3ProjectModeService(product_service=product_service, project_store=project_store)
    project = ProjectRecord(
        project_id="project_partial_membership",
        title="Partial membership project",
        user_goal="Keep undeclared historical pixels visible.",
        short_summary="Keep undeclared historical pixels visible.",
        job_ids=["job_still_declared"],
        created_at="2026-09-01T00:00:00+00:00",
        updated_at="2026-09-14T00:00:00+00:00",
    )
    project_store.save_project(project)

    response = service.list_project_outputs(project_id=project.project_id, compact=True)

    assert response["items"] == []
    assert response["review_items"] == []
    assert [item["output_id"] for item in response["history_items"]] == [record.output_id]
    assert response["history_items"][0]["history_only"] is True


def test_desktop_history_projection_renders_media_without_formal_delivery_leak() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "desktop-legacy-project",
                    title: "Legacy desktop project",
                    user_goal: "Keep the old image visible.",
                    short_summary: "Keep the old image visible.",
                    primary_template_id: "general_template",
                    status: "active",
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    history_output_count: 1,
                    history_output_count_known: true,
                    job_count: 0,
                    updated_at: "2026-09-14T00:00:00Z",
                    latest_thumbnail_urls: [],
                  };
                  const history = {
                    project_id: project.project_id,
                    output_id: "legacy-desktop-output",
                    history_only: true,
                    delivery_state: "history_only",
                    created_at: "2026-09-14T00:01:00Z",
                    thumbnail_url: "http://image.test/legacy-desktop.png",
                    preview_url: "http://image.test/legacy-desktop.png",
                    metadata: { history_only: true, legacy_history_only: true },
                  };
                  v3State.workspaceMode = "standard";
                  v3State.projects = [project];
                  v3State.imageHistory = [history];
                  v3State.imageHistorySurface = "home_preview";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  renderV3History();
                  return {
                    text: document.querySelector("#v3HistoryList")?.textContent || "",
                    image: document.querySelector("#v3HistoryList img")?.getAttribute("src") || "",
                    formalCount: v3DeliveryDisplayItems(v3State.imageHistory).length,
                    historyCount: v3HistoryDisplayItems(v3State.imageHistory).length,
                  };
                }
                """,
            )
            assert "1 张历史图片" in result["text"]
            assert result["image"] == "http://image.test/legacy-desktop.png"
            assert result["formalCount"] == 0
            assert result["historyCount"] == 1
        finally:
            browser.close()


def test_desktop_home_loader_consumes_history_projection() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                () => {
                  window.fetch = async () => new Response(JSON.stringify({
                    items: [],
                    review_items: [],
                    history_items: [{
                      project_id: "desktop-loader-project",
                      output_id: "desktop-loader-output",
                      history_only: true,
                      delivery_state: "history_only",
                      created_at: "2026-09-14T00:01:00Z",
                      thumbnail_url: "http://image.test/desktop-loader.png",
                      preview_url: "http://image.test/desktop-loader.png",
                      metadata: { history_only: true, legacy_history_only: true },
                    }],
                    project_output_counts: { "desktop-loader-project": 0 },
                    project_history_counts: { "desktop-loader-project": 1 },
                  }), { status: 200, headers: { "Content-Type": "application/json" } });
                }
                """,
            )
            result = page.evaluate(
                """
                async () => {
                  const project = {
                    project_id: "desktop-loader-project",
                    title: "Desktop loader project",
                    user_goal: "Keep the old image visible.",
                    short_summary: "Keep the old image visible.",
                    primary_template_id: "general_template",
                    status: "active",
                    visible_output_count: 0,
                    visible_output_count_known: false,
                    history_output_count: 0,
                    history_output_count_known: false,
                    job_count: 0,
                    updated_at: "2026-09-14T00:00:00Z",
                    latest_thumbnail_urls: [],
                  };
                  v3State.projects = [project];
                  v3State.imageHistory = [];
                  v3State.imageHistorySurface = "none";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  await loadV3ProjectOutputs({
                    force: true,
                    limit: 1,
                    surface: "home_preview",
                    projectIds: [project.project_id],
                  });
                  renderV3History();
                  return {
                    text: document.querySelector("#v3HistoryList")?.textContent || "",
                    image: document.querySelector("#v3HistoryList img")?.getAttribute("src") || "",
                    historyCount: v3ProjectHistoryOutputCount(v3State.projects[0]),
                  };
                }
                """,
            )
            assert "1 张历史图片" in result["text"]
            assert result["image"] == "http://image.test/desktop-loader.png"
            assert result["historyCount"] == 1
        finally:
            browser.close()


def test_desktop_explicit_history_modal_reveals_project_review_pixels() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            result = page.evaluate(
                """
                async () => {
                  const project = {
                    project_id: "desktop-review-project",
                    title: "Legacy review project",
                    user_goal: "Keep the review image inspectable.",
                    short_summary: "Keep the review image inspectable.",
                    primary_template_id: "general_template",
                    status: "active",
                    job_ids: ["desktop-review-job"],
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    history_output_count: 0,
                    history_output_count_known: true,
                    job_count: 1,
                    updated_at: "2026-09-14T00:00:00Z",
                    latest_thumbnail_urls: [],
                  };
                  const review = {
                    output_id: "desktop-review-output",
                    project_id: project.project_id,
                    job_id: "desktop-review-job",
                    thumbnail_url: "http://image.test/desktop-review.png",
                    preview_url: "http://image.test/desktop-review.png",
                    delivery_state: "review_only",
                    review_only: true,
                    review_reason: "保留供复核",
                    metadata: { review_only: true },
                  };
                  window.fetch = async (input) => {
                    const url = String(input);
                    if (/\\/project-outputs/.test(url)) {
                      return new Response(JSON.stringify({ items: [], review_items: [review], history_items: [] }), {
                        status: 200,
                        headers: { "Content-Type": "application/json" },
                      });
                    }
                    return new Response(JSON.stringify({}), {
                      status: 200,
                      headers: { "Content-Type": "application/json" },
                    });
                  };
                  v3State.workspaceMode = "standard";
                  v3State.projects = [project];
                  v3State.imageHistory = [];
                  v3State.imageHistorySurface = "home_preview";
                  v3State.imageHistoryLoaded = false;
                  v3State.imageHistoryError = "";
                  v3State.projectOutputs = [];
                  v3State.projectReviewOutputs = [];
                  renderV3History();
                  const homeImageCount = document.querySelectorAll("#v3HistoryList img").length;
                  openV3ProjectHistoryModal(project.project_id);
                  await new Promise((resolve) => window.setTimeout(resolve, 120));
                  return {
                    homeImageCount,
                    modalImage: document.querySelector("#v3ProjectHistoryGrid img")?.getAttribute("src") || "",
                    modalText: document.querySelector("#v3ProjectHistoryCount")?.textContent || "",
                    modalCards: document.querySelectorAll("#v3ProjectHistoryGrid .v3-project-history-image-card").length,
                  };
                }
                """,
            )
            assert result["homeImageCount"] == 0
            assert result["modalImage"] == "http://image.test/desktop-review.png"
            assert result["modalCards"] == 1
            assert result["modalText"] == "1 张待复核图片"
        finally:
            browser.close()


def test_mobile_history_projection_renders_media_without_formal_result_actions() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            result = page.evaluate(
                """
                () => {
                  const project = {
                    project_id: "mobile-legacy-project",
                    title: "Legacy mobile project",
                    user_goal: "Keep the old image visible.",
                    short_summary: "Keep the old image visible.",
                    primary_template_id: "general_template",
                    status: "active",
                    visible_output_count: 0,
                    visible_output_count_known: true,
                    history_output_count: 1,
                    history_output_count_known: true,
                    job_count: 0,
                    updated_at: "2026-09-14T00:00:00Z",
                    latest_thumbnail_urls: [],
                  };
                  const history = {
                    project_id: project.project_id,
                    output_id: "legacy-mobile-output",
                    history_only: true,
                    delivery_state: "history_only",
                    created_at: "2026-09-14T00:01:00Z",
                    thumbnail_url: "http://image.test/legacy-mobile.png",
                    preview_url: "http://image.test/legacy-mobile.png",
                    metadata: { history_only: true, legacy_history_only: true },
                  };
                  mobileV3State.workspaceMode = "standard";
                  mobileV3State.projects = [project];
                  mobileV3State.outputs = [history];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  mobileV3State.outputsSurface = "home_preview";
                  mobileV3State.outputError = "";
                  mobileV3State.previewProjectIds = new Set([project.project_id]);
                  renderMobileV3ProjectCards();
                  mobileV3State.currentProject = project;
                  renderMobileV3ProjectOutputs(project);
                  return {
                    cardText: document.querySelector("#mobileV3ProjectGrid")?.textContent || "",
                    detailText: document.querySelector("#mobileV3OutputGrid")?.textContent || "",
                    image: document.querySelector("#mobileV3ProjectGrid img")?.getAttribute("src") || "",
                    formalCount: mobileV3FinalOutputsForProject(project.project_id).length,
                    selectionButtons: document.querySelectorAll("[data-mobile-v3-output-action]").length,
                  };
                }
                """,
            )
            assert "1 张历史图片" in result["cardText"]
            assert "历史图片 1 张" in result["detailText"]
            assert result["image"] == "http://image.test/legacy-mobile.png"
            assert result["formalCount"] == 0
            assert result["selectionButtons"] == 0
        finally:
            browser.close()


def test_mobile_home_loader_consumes_history_projection() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                () => {
                  window.fetch = async () => new Response(JSON.stringify({
                    items: [],
                    review_items: [],
                    history_items: [{
                      project_id: "mobile-loader-project",
                      output_id: "mobile-loader-output",
                      history_only: true,
                      delivery_state: "history_only",
                      created_at: "2026-09-14T00:01:00Z",
                      thumbnail_url: "http://image.test/mobile-loader.png",
                      preview_url: "http://image.test/mobile-loader.png",
                      metadata: { history_only: true, legacy_history_only: true },
                    }],
                    project_output_counts: { "mobile-loader-project": 0 },
                    project_history_counts: { "mobile-loader-project": 1 },
                  }), { status: 200, headers: { "Content-Type": "application/json" } });
                }
                """,
            )
            result = page.evaluate(
                """
                async () => {
                  const project = {
                    project_id: "mobile-loader-project",
                    title: "Mobile loader project",
                    user_goal: "Keep the old image visible.",
                    short_summary: "Keep the old image visible.",
                    primary_template_id: "general_template",
                    status: "active",
                    visible_output_count: 0,
                    visible_output_count_known: false,
                    history_output_count: 0,
                    history_output_count_known: false,
                    job_count: 0,
                    updated_at: "2026-09-14T00:00:00Z",
                    latest_thumbnail_urls: [],
                  };
                  mobileV3State.projects = [project];
                  mobileV3State.outputs = [];
                  mobileV3State.outputsLoaded = false;
                  mobileV3State.outputsSurface = "none";
                  mobileV3State.outputError = "";
                  mobileV3State.previewProjectIds = new Set();
                  await loadMobileV3HomePreviews([project.project_id]);
                  renderMobileV3ProjectCards();
                  return {
                    text: document.querySelector("#mobileV3ProjectGrid")?.textContent || "",
                    image: document.querySelector("#mobileV3ProjectGrid img")?.getAttribute("src") || "",
                    historyCount: mobileV3ProjectHistoryOutputCount(mobileV3State.projects[0]),
                  };
                }
                """,
            )
            assert "1 张历史图片" in result["text"]
            assert result["image"] == "http://image.test/mobile-loader.png"
            assert result["historyCount"] == 1
        finally:
            browser.close()
