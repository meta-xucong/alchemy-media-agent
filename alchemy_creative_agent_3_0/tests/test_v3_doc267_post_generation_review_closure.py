"""Phase 0 red contracts for Doc267 Professional E-Commerce review closure.

The suite uses local stores, public Product/Project APIs, Playwright DOMs, and
deterministic in-process doubles only. It must not contact Provider, MCP,
ImageGen, VPS, or create a real project/job outside the test process.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

from app import main as app_main
from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    VisualInspectionReport,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import (
    OutputQualityReviewMerger,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_evidence import (
    ExactReviewEvidenceResolver,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc260_review_evidence_plan import (
    _create_general_job,
    _png_base64,
    _service,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    DESKTOP_HTML,
    DESKTOP_JS,
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _CapturingMockGenerationProvider,
    _add_product_references,
    _bind_locked_person_identity,
    _job_payload,
)


class _PostPixelFinalizationError(ValueError):
    code = "post_generation_review_finalization_failed"
    v3_status_code = 409


class _BackgroundGenerationHandlerDouble:
    """Drive the real worker with a local Project Mode handler and typed fault."""

    def __init__(self, handlers, failure: Exception) -> None:  # noqa: ANN001
        self.handlers = handlers
        self.failure = failure
        self.failure_codes: list[str] = []

    def post_project_job_generate(self, *_args, **_kwargs):  # noqa: ANN002, ANN003
        raise self.failure

    def mark_project_job_generation_worker_failed(self, project_id, job_id, *, background_attempt_id, failure_code):  # noqa: ANN001
        self.failure_codes.append(failure_code)
        return self.handlers.mark_project_job_generation_worker_failed(
            project_id,
            job_id,
            background_attempt_id=background_attempt_id,
            failure_code=failure_code,
        )


def _ecommerce_job_with_persisted_pixel(tmp_path):
    handlers, catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename="doc267-product.png",
        color=(105, 145, 175),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    created = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[product_id], key="doc267-post-pixel-finalization"),
    )
    attempt_id = "doc267-finalization-attempt"
    handlers.mark_project_job_generating(
        project["project_id"],
        created["job_id"],
        background_attempt_id=attempt_id,
    )
    output = handlers.service.output_store.save_base64_output(
        job_id=created["job_id"],
        candidate_id="doc267-persisted-pixel-candidate",
        asset_id="asset_6428fd41d9",
        provider="local-test-double",
        model="local-test-double",
        encoded_image=_png_base64(),
        metadata={
            "final_delivery": {
                "delivery_gate_applies": True,
                "final_delivery_status": "withheld_manual_confirmation",
                "automatic_delivery_available": False,
                "manual_confirmation_required": True,
            }
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    return handlers, catalog, project, record, output, attempt_id


def _closed_review_receipt(handlers, record):
    persisted = handlers.service.job_store.get(record.job_id)
    assert persisted is not None
    receipt = persisted.request.metadata["post_generation_review_closure"]
    assert receipt["schema_version"] == "doc267_post_generation_review_closure_v1"
    assert receipt["state"] == "review_withheld_finalization_failed"
    assert receipt["job_id"] == record.job_id
    assert receipt["automatic_delivery_available"] is False
    assert receipt["manual_confirmation_required"] is True
    return receipt


def _run_background_failure(monkeypatch, *, handlers, project_id: str, job_id: str, attempt_id: str, failure: Exception):
    worker_handler = _BackgroundGenerationHandlerDouble(handlers, failure)
    monkeypatch.setattr(app_main, "v3_route_handlers", worker_handler)
    app_main._run_v3_project_generation_background(project_id, job_id, {}, attempt_id)
    return worker_handler


def test_doc267_reason_dedupe_keeps_three_valid_person_evidence_sources() -> None:
    entries = [
        {
            "source_id": f"face-output-{index}",
            "state": "available",
            "source_type": "selected_output",
            "reason": "person_identity_source_job_binding",
        }
        for index in range(3)
    ]

    channel = ExactReviewEvidenceResolver._channel(  # noqa: SLF001
        "person_identity",
        requested=True,
        entries=entries,
        missing_required=False,
    )

    assert channel.evidence_state == "available"
    assert channel.evidence_ids == ("face-output-0", "face-output-1", "face-output-2")
    assert channel.reason_codes == ("review_evidence_person_identity_source_job_binding",)


def test_doc267_worker_closes_persisted_pixel_finalization_failure_not_request_invalid(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, record, output, attempt_id = _ecommerce_job_with_persisted_pixel(tmp_path)
    worker = _run_background_failure(
        monkeypatch,
        handlers=handlers,
        project_id=project["project_id"],
        job_id=record.job_id,
        attempt_id=attempt_id,
        failure=_PostPixelFinalizationError("review assembly failed after persisted pixels"),
    )
    status = handlers.get_job(record.job_id)
    receipt = _closed_review_receipt(handlers, record)

    assert worker.failure_codes == ["post_generation_review_finalization_failed"]
    assert status["metadata"]["generation_lifecycle_failure"]["failure_code"] == "post_generation_review_finalization_failed"
    assert receipt["output_ids"] == [output.output_id]
    assert receipt["history_only"] is True
    assert "background_generation_request_invalid" not in " ".join(status["warnings"])


def test_doc267_persisted_pixel_closure_cannot_spend_retry_or_deliver(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, record, _output, attempt_id = _ecommerce_job_with_persisted_pixel(tmp_path)
    _run_background_failure(
        monkeypatch,
        handlers=handlers,
        project_id=project["project_id"],
        job_id=record.job_id,
        attempt_id=attempt_id,
        failure=_PostPixelFinalizationError("inspection failed after persisted pixels"),
    )
    receipt = _closed_review_receipt(handlers, record)

    assert receipt["real_pixel_review"] is False
    assert receipt["refine_budget_consumed"] == 0
    assert receipt["reject_recommendation_created"] is False
    assert receipt["automatic_delivery_available"] is False


def test_doc267_closed_or_uncertified_package_has_only_non_consuming_manual_review() -> None:
    resolution = GeneratedOutputResolution(
        resolution_id="doc267-resolution",
        project_id="doc267-project",
        job_id="doc267-job",
        candidate_id="doc267-candidate",
        asset_id="asset_6428fd41d9",
        output_id="output-doc267",
        status="ready",
    )
    inspection = VisualInspectionReport(
        inspection_id="doc267-metadata-only-inspection",
        project_id="doc267-project",
        job_id="doc267-job",
        candidate_id="doc267-candidate",
        asset_id="asset_6428fd41d9",
        output_id="output-doc267",
        mode="metadata_only",
        status="fail_retryable",
        verification_state="unverified",
        retryable=True,
        detected_issues=[{"code": "metadata_only_unverified", "retryable": True}],
    )

    package = OutputQualityReviewMerger().build_package(
        job_id="doc267-job",
        project_id="doc267-project",
        resolutions=[resolution],
        inspections=[inspection],
        review_evidence_receipt_status="closed",
        review_evidence_receipt_errors=("review_finalization_failed",),
        max_attempts=2,
    )

    assert package.auto_retry_decisions == []
    assert package.recommended_output_ids == []
    assert package.hidden_output_ids == []
    assert package.real_review_signal_package is None
    assert package.metadata["review_disposition"] == "manual_review_only"


def test_doc267_background_taxonomy_keeps_invalid_v3_request_for_predispatch_only(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, record, _output, attempt_id = _ecommerce_job_with_persisted_pixel(tmp_path)
    worker = _run_background_failure(
        monkeypatch,
        handlers=handlers,
        project_id=project["project_id"],
        job_id=record.job_id,
        attempt_id=attempt_id,
        failure=ValueError("public request validation failed before dispatch"),
    )
    status = handlers.get_job(record.job_id)
    assert worker.failure_codes == ["background_generation_request_invalid"]
    assert status["metadata"]["generation_lifecycle_failure"]["failure_code"] == "background_generation_request_invalid"


def test_doc267_unrelated_runtime_error_remains_generic_worker_failure(tmp_path, monkeypatch) -> None:
    handlers, _catalog, project, record, _output, attempt_id = _ecommerce_job_with_persisted_pixel(tmp_path)
    worker = _run_background_failure(
        monkeypatch,
        handlers=handlers,
        project_id=project["project_id"],
        job_id=record.job_id,
        attempt_id=attempt_id,
        failure=RuntimeError("unrelated local defect"),
    )
    status = handlers.get_job(record.job_id)
    persisted = handlers.service.job_store.get(record.job_id)

    assert worker.failure_codes == ["background_generation_worker_error"]
    assert status["metadata"]["generation_lifecycle_failure"]["failure_code"] == "background_generation_worker_error"
    assert persisted is not None
    assert "post_generation_review_closure" not in persisted.request.metadata


def test_doc267_locked_people_identity_overrides_generic_false_and_is_deduplicated(tmp_path) -> None:
    handlers, catalog = _handlers(tmp_path)
    provider = _CapturingMockGenerationProvider()
    handlers.service.scenario_runtime.generation_router = GenerationRouter(provider=provider)
    project = _project(handlers)
    product_ids = [
        _ready_product_upload(handlers, filename=f"product-{index}.png", color=(80 + index * 20, 130, 165))
        for index in range(4)
    ]
    _add_product_references(handlers, project["project_id"], product_ids)
    identity_output_ids = _bind_locked_person_identity(handlers, catalog, project_id=project["project_id"])
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc267-locked-identity")
    payload["metadata"].update(
        {
            "requested_image_count": 1,
            "advanced_reference_controls": {"preserve_person_identity": False},
        }
    )
    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.planning_result is not None
    handlers.post_project_job_generate(project["project_id"], record.job_id)
    assert len(provider.requests) == 1

    metadata = record.request.metadata
    anchors = metadata["professional_anchor_reference_assets"]
    projection = metadata["professional_ecommerce_physical_product_projections"]["1"]
    provider_request = provider.requests[0]
    physical_assets = ProductionImageGenerationProvider()._reference_assets(provider_request)  # noqa: SLF001
    physical_identity_ids = [item.get("output_id") for item in physical_assets if item.get("role") == "face_reference"]
    physical_product_ids = [item.get("asset_id") for item in physical_assets if item.get("role") == "product_reference"]
    assert metadata["advanced_reference_controls"]["preserve_person_identity"] is True
    assert [item["output_id"] for item in anchors] == identity_output_ids
    assert len({item["output_id"] for item in anchors}) == len(identity_output_ids)
    assert physical_identity_ids == identity_output_ids
    assert len(physical_identity_ids) == len(set(physical_identity_ids))
    assert len(physical_identity_ids) <= provider_request.metadata["provider_reference_budget"]["max_identity_sources"]
    assert physical_product_ids == projection["selected_product_asset_ids"]
    assert len(physical_product_ids) == len(set(physical_product_ids))
    assert set(product_ids) - set(physical_product_ids)
    assert all(item["asset_id"] not in product_ids for item in anchors)


def test_doc267_ecommerce_n1_keeps_product_primary_and_lifestyle_is_explicit(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(handlers, filename="n1-product.png", color=(110, 145, 170))
    _add_product_references(handlers, project["project_id"], [product_id])
    payload = _job_payload(uploaded_asset_ids=[product_id], key="doc267-n1-product-primary")
    payload["metadata"]["requested_image_count"] = 1
    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None and record.planning_result is not None

    deliverable = record.planning_result.metadata["template_deliverable_plan"]["deliverables"][0]
    assert deliverable["metadata"]["product_truth_selection_role"] == "product_primary_presentation"
    assert deliverable["metadata"]["product_truth_selection_role"] != "lifestyle_interaction"


def _review_withheld_project() -> dict:
    return {
        "project_id": "doc267-project",
        "primary_template_id": "ecommerce_template",
        "job_ids": ["doc267-stale-planned-job"],
        "latest_job_status": "planned",
        "metadata": {
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {"items": []},
                    "locked_person_identity": {"items": []},
                    "selected_continuation_directions": {"items": []},
                    "generated_and_review_history": {
                        "delivered_outputs": [],
                        "review_withheld_outputs": [{"output_id": "asset_6428fd41d9", "review_only": True}],
                        "failed_attempts": [],
                    },
                },
            },
            "current_operation": {
                "state": "review_withheld_finalization_failed",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_generation_history"}],
            },
        },
    }


def test_doc267_public_project_projection_prefers_closed_review_operation_over_stale_generation(tmp_path) -> None:
    handlers, _catalog, project, record, output, _attempt_id = _ecommerce_job_with_persisted_pixel(tmp_path)
    record.status = ProductJobStatusValue.GENERATING
    record.request.metadata = {
        **dict(record.request.metadata),
        "final_delivery": {
            "delivery_gate_applies": True,
            "final_delivery_status": "withheld_manual_confirmation",
            "automatic_delivery_available": False,
            "manual_confirmation_required": True,
        },
        "post_generation_review_closure": {
            "schema_version": "doc267_post_generation_review_closure_v1",
            "state": "review_withheld_finalization_failed",
            "job_id": record.job_id,
            "output_ids": [output.output_id],
            "history_only": True,
            "manual_confirmation_required": True,
            "automatic_delivery_available": False,
        },
    }
    handlers.service.job_store.save(record)

    public_project = handlers.get_project(project["project_id"])
    operation = public_project["metadata"]["current_operation"]
    history = public_project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]

    assert operation == {
        "job_id": record.job_id,
        "state": "review_withheld_finalization_failed",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_history"}],
    }
    assert "generating" not in str(operation).lower()
    assert [item["output_id"] for item in history["review_withheld_outputs"]] == [output.output_id]


def test_doc267_desktop_and_mobile_render_one_terminal_review_operation_without_post() -> None:
    project = _review_withheld_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            desktop.evaluate(
                """
                (project) => {
                  window.__doc263ServerProject = project;
                  v3State.currentProject = project;
                  v3State.currentJob = { job_id: "doc267-stale-planned-job", status: "planned", warnings: [] };
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                  renderV3ProjectDetail();
                }
                """,
                project,
            )
            desktop.evaluate(
                """
                () => {
                  document.querySelector("#v3ProjectOutputBoard").scrollIntoView = () => {
                    document.body.dataset.doc267HistoryOpened = "desktop";
                  };
                }
                """
            )
            assert desktop.locator("[data-v3-project-action='review_generation_history']").count() == 1
            assert desktop.locator("[data-v3-project-action='start_first_generation']").count() == 0
            assert "准备生成" not in desktop.locator("#v3ProjectNextActions").inner_text()
            assert "生成中" not in desktop.locator("#v3ProjectNextActions").inner_text()
            desktop.locator("[data-v3-project-action='review_generation_history']").click()
            assert desktop.evaluate("document.body.dataset.doc267HistoryOpened") == "desktop"
            assert desktop.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0

            mobile = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            mobile.evaluate(
                """
                (project) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = { job_id: "doc267-stale-planned-job", status: "planned", warnings: [] };
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                project,
            )
            mobile.evaluate(
                """
                () => {
                  document.querySelector("#mobileV3ReferenceBoard").scrollIntoView = () => {
                    document.body.dataset.doc267HistoryOpened = "mobile";
                  };
                }
                """
            )
            assert mobile.locator("[data-mobile-v3-project-action='review_generation_history']").count() == 1
            assert mobile.locator("[data-mobile-v3-project-action='continue_recovery']").count() == 0
            assert "准备中" not in mobile.locator("#mobileV3ProgressElapsed").inner_text()
            assert "进行中" not in mobile.locator("#mobileV3ProgressElapsed").inner_text()
            mobile.locator("[data-mobile-v3-project-action='review_generation_history']").click()
            assert mobile.evaluate("document.body.dataset.doc267HistoryOpened") == "mobile"
            assert mobile.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()
