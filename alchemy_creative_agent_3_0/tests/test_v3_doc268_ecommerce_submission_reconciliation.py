"""Phase 0 red contracts for Doc268 E-Commerce submission reconciliation.

These tests use in-process Product/Project handlers and the real desktop/mobile
browser scripts with a mocked local transport. They never call Provider, MCP,
ImageGen, VPS, or a live project/job.
"""

from __future__ import annotations

from playwright.sync_api import sync_playwright

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
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import _add_product_references


PROJECT_ID = "doc268-project"
STALE_JOB_ID = "job-770-stale"
FRESH_JOB_ID = "job-e75-fresh"
FRESH_PROVIDER_FAILURE_CODE = "image_edit_invalid_request_unattributed"


def _payload(*, idempotency_key: str = "") -> dict:
    return {
        "template_id": "ecommerce_template",
        "user_input": "Create one faithful product-primary presentation.",
        "metadata": {"idempotency_key": idempotency_key},
    }


def _browser_project(*, job_ids: list[str]) -> dict:
    return {
        "project_id": PROJECT_ID,
        "user_goal": "Create one faithful product-primary presentation.",
        "short_summary": "Create one faithful product-primary presentation.",
        "primary_template_id": "ecommerce_template",
        "job_ids": job_ids,
        "reference_assets": [
            {
                "reference_id": "doc268-product-original",
                "asset_ref_id": "doc268-product-original",
                "source_type": "uploaded",
                "use_policy": "product",
                "status": "active",
            }
        ],
        "metadata": {
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {"items": [{"asset_ref_id": "doc268-product-original"}]},
                    "locked_person_identity": {"items": []},
                    "selected_continuation_directions": {"items": []},
                    "generated_and_review_history": {
                        "delivered_outputs": [],
                        "review_withheld_outputs": [],
                        "failed_attempts": [{"job_id": STALE_JOB_ID, "state": "failed_no_delivery"}],
                    },
                },
            },
            "current_operation": {
                "job_id": FRESH_JOB_ID,
                "state": "failed_no_delivery",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "start_first_generation"}],
            },
        },
    }


def _stale_terminal_job() -> dict:
    return {
        "job_id": STALE_JOB_ID,
        "status": "blocked",
        "warnings": ["background_generation_request_invalid"],
        "candidates": [],
        "metadata": {"project_id": PROJECT_ID, "project_outputs": []},
    }


def _stale_project_output() -> dict:
    return {
        "output_id": "doc268-historical-output",
        "job_id": STALE_JOB_ID,
        "thumbnail_url": "https://example.invalid/doc268-history.png",
        "preview_url": "https://example.invalid/doc268-history.png",
        "delivery_state": "final_delivery",
        "metadata": {"job_id": STALE_JOB_ID},
    }


def _fresh_provider_policy_block() -> dict:
    return {
        "job_id": FRESH_JOB_ID,
        "status": "blocked",
        "warnings": [FRESH_PROVIDER_FAILURE_CODE],
        "metadata": {"project_outputs": []},
    }


def _fresh_terminal_job(status: str, *, needs_input: bool = False) -> dict:
    job = {
        "job_id": FRESH_JOB_ID,
        "status": status,
        "warnings": [FRESH_PROVIDER_FAILURE_CODE],
        "metadata": {"project_outputs": []},
    }
    if needs_input:
        job["metadata"]["current_operation"] = {
            "state": "needs_input",
            "terminal": True,
            "pending": False,
        }
    return job


def _install_browser_transport(page, *, project: dict, fresh: dict | None = None) -> None:  # noqa: ANN001
    page.evaluate(
        """
        ({ project, stale, staleOutput, fresh }) => {
          window.__doc268Requests = [];
          window.__doc268Project = project;
          window.fetch = async (input, init = {}) => {
            const url = String(input);
            const method = String(init.method || "GET").toUpperCase();
            const rawBody = init.body ? JSON.stringify(init.body) : "";
            window.__doc268Requests.push({ url, method, rawBody });
            let body = {};
            if (method === "POST" && /\\/projects\\/doc268-project\\/jobs$/.test(url)) {
              body = fresh;
            } else if (/\\/projects\\/doc268-project\\/timeline$/.test(url)) {
              body = { items: [{ item_type: "job_generated", job_id: stale.job_id }] };
            } else if (/\\/project-outputs/.test(url)) {
              body = { items: [staleOutput], review_items: [] };
            } else if (/\\/projects\\/doc268-project$/.test(url)) {
              body = { project: window.__doc268Project };
            } else if (new RegExp(`/jobs/${stale.job_id}$`).test(url)) {
              body = stale;
            } else if (new RegExp(`/jobs/${fresh.job_id}$`).test(url)) {
              body = fresh;
            }
            return new Response(JSON.stringify(body), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          };
        }
        """,
        {
            "project": project,
            "stale": _stale_terminal_job(),
            "staleOutput": _stale_project_output(),
            "fresh": fresh or _fresh_provider_policy_block(),
        },
    )


def test_doc268_blank_legacy_idempotency_returns_a_new_same_project_job_not_historical_terminal(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename="doc268-product.png",
        color=(95, 130, 165),
    )
    _add_product_references(handlers, project["project_id"], [product_id])

    historical = handlers.post_project_job(project["project_id"], _payload(idempotency_key="legacy-terminal-command"))
    historical_record = handlers.service.get_job_record(historical["job_id"])
    assert historical_record is not None
    handlers.mark_project_job_generation_worker_failed(
        project["project_id"],
        historical["job_id"],
        background_attempt_id="doc268-historical-terminal",
        failure_code="background_generation_request_invalid",
    )
    fresh = handlers.post_project_job(project["project_id"], _payload(idempotency_key=""))

    assert fresh["job_id"] != historical["job_id"]
    assert handlers.get_project(project["project_id"])["project"]["job_ids"] == [
        historical["job_id"],
        fresh["job_id"],
    ]


def test_doc268_desktop_keeps_exact_fresh_receipt_over_stale_timeline_and_closes_progress() -> None:
    project = _browser_project(job_ids=[STALE_JOB_ID, FRESH_JOB_ID])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            _install_browser_transport(page, project=project)
            page.evaluate(
                """
                (project) => {
                  v3State.currentProject = project;
                  v3State.currentJob = null;
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  v3State.projectOutputs = [];
                  v3State.projectReviewOutputs = [];
                  renderV3ScenarioState();
                }
                """,
                project,
            )

            page.evaluate("async () => { await createV3Job(); }")

            request_body = page.evaluate("window.__doc268Requests.find((item) => item.method === 'POST').rawBody")
            assert "idempotency_key" not in request_body
            assert page.evaluate("v3State.currentJob.job_id") == FRESH_JOB_ID
            assert page.evaluate("v3State.loading === false") is True
            assert page.evaluate("v3State.progressStageKey") == "failed"
            assert page.evaluate(
                "v3State.progressTimer === null && v3State.recoverPollTimer === null && v3State.recoverPollAttempt === 0"
            ) is True
            assert page.locator("#v3SummaryTitle").inner_text() == "生成已停止"
            assert page.evaluate("v3State.currentJob.warnings[0]") == FRESH_PROVIDER_FAILURE_CODE
            progress_text = " ".join(
                [
                    page.locator("#v3SummaryIntro").inner_text(),
                    page.locator("#v3CapabilityList").inner_text(),
                    page.locator("#v3SummaryPill").inner_text(),
                    page.locator("#v3CreateJobBtn").inner_text(),
                    page.locator("#v3ProjectNextActions").inner_text(),
                ]
            )
            assert all(term not in progress_text for term in ("正在准备生成", "准备", "生成图片", "核对结果", "进行中"))
            terminal_public_text = " ".join(
                [
                    page.locator("#v3ResultBoard").inner_text(),
                    page.locator("#v3NoticeBar").inner_text(),
                    page.locator("#v3ProjectNextActions").inner_text(),
                ]
            )
            assert page.locator("#v3NoticeBar").inner_text().strip()
            assert all(
                value not in terminal_public_text
                for value in (FRESH_PROVIDER_FAILURE_CODE, STALE_JOB_ID, FRESH_JOB_ID, "output-", "/", "sha256")
            )
            assert page.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 1
            page.wait_for_timeout(50)
            assert page.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 1
        finally:
            browser.close()


def test_doc268_desktop_post_terminal_receipts_never_enter_recovery() -> None:
    project = _browser_project(job_ids=[STALE_JOB_ID, FRESH_JOB_ID])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            for status in ("failed", "not_found"):
                page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
                _install_browser_transport(page, project=project, fresh=_fresh_terminal_job(status))
                page.evaluate(
                    """
                    (project) => {
                      v3State.currentProject = project;
                      v3State.currentJob = null;
                      v3State.selectedScenario = "ecommerce";
                      v3State.templateCatalogStatus = "ready";
                      v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                      renderV3ScenarioState();
                    }
                    """,
                    project,
                )
                page.evaluate("async () => { await createV3Job(); }")

                assert page.evaluate("v3State.currentJob.job_id") == FRESH_JOB_ID
                assert page.evaluate("v3State.currentJob.status") == status
                assert page.evaluate("v3State.loading === false && v3State.progressStageKey === 'failed'") is True
                assert page.evaluate(
                    "v3State.progressTimer === null && v3State.recoverPollTimer === null && v3State.recoverPollAttempt === 0"
                ) is True
                assert page.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 1
                assert page.evaluate(
                    "window.__doc268Requests.filter((item) => /\\/jobs\\/job-e75-fresh$/.test(item.url)).length"
                ) == 0
                terminal_text = " ".join(
                    [
                        page.locator("#v3SummaryIntro").inner_text(),
                        page.locator("#v3CreateJobBtn").inner_text(),
                        page.locator("#v3ProjectNextActions").inner_text(),
                    ]
                )
                assert all(term not in terminal_text for term in ("正在准备生成", "准备生成", "生成图片", "核对结果", "进行中"))
                page.close()
        finally:
            browser.close()


def test_doc268_needs_input_receipt_stays_exact_until_deliberate_project_change() -> None:
    project = _browser_project(job_ids=[STALE_JOB_ID, FRESH_JOB_ID])
    needs_input = _fresh_terminal_job("blocked", needs_input=True)
    other_project = {**project, "project_id": "doc268-other-project", "job_ids": [STALE_JOB_ID]}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            _install_browser_transport(desktop, project=project, fresh=needs_input)
            desktop.evaluate(
                """
                (project) => {
                  v3State.currentProject = project;
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                }
                """,
                project,
            )
            desktop.evaluate("async () => { await createV3Job(); await refreshV3CurrentProject({ silent: true }); }")
            assert desktop.evaluate("v3State.currentJob.job_id") == FRESH_JOB_ID
            assert desktop.evaluate("v3State.ecommerceSubmissionReceipt.jobId") == FRESH_JOB_ID
            assert desktop.evaluate("window.__doc268Requests.filter((item) => /\\/jobs\\/job-e75-fresh$/.test(item.url)).length") == 0
            desktop.evaluate("openV3Project('doc268-other-project').catch(() => {})")
            assert desktop.evaluate("v3State.ecommerceSubmissionReceipt === null") is True

            mobile = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            _install_browser_transport(mobile, project=project, fresh=needs_input)
            mobile.evaluate(
                """
                (project) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.selectedTemplate = "ecommerce_template";
                }
                """,
                project,
            )
            mobile.evaluate("async () => { await generateMobileV3Job(); }")
            assert mobile.evaluate("mobileV3State.currentJob.job_id") == FRESH_JOB_ID
            assert mobile.evaluate("mobileV3State.ecommerceSubmissionReceipt.jobId") == FRESH_JOB_ID
            assert mobile.evaluate("window.__doc268Requests.filter((item) => /\\/jobs\\/job-e75-fresh$/.test(item.url)).length") == 0
            mobile.evaluate("(project) => { openMobileV3ProjectDetail(project); }", other_project)
            assert mobile.evaluate("mobileV3State.ecommerceSubmissionReceipt === null") is True
        finally:
            browser.close()


def test_doc268_mobile_terminal_receipt_retires_delayed_recovery_progress() -> None:
    project = _browser_project(job_ids=[FRESH_JOB_ID])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            _install_browser_transport(page, project=project)
            page.evaluate(
                """
                ({ project }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = project;
                  mobileV3State.currentJob = { job_id: 'job-e75-fresh', status: 'planned', metadata: {} };
                  mobileV3State.ecommerceSubmissionReceipt = { projectId: project.project_id, jobId: 'job-e75-fresh' };
                  mobileV3State.selectedTemplate = 'ecommerce_template';
                  window.__doc268Recovery = mobileV3StartEcommerceRecovery(project.project_id, 'job-e75-fresh');
                  window.__doc268RecoveryPromise = recoverMobileV3GeneratedJob(project.project_id, 'job-e75-fresh', {
                    initialJob: mobileV3State.currentJob,
                    recoveryReceipt: window.__doc268Recovery,
                  });
                  mobileV3SettleEcommerceTerminalReceipt({ job_id: 'job-e75-fresh', status: 'blocked', metadata: {} });
                }
                """,
                {"project": project},
            )
            page.evaluate("async () => { await window.__doc268RecoveryPromise; }")
            assert page.locator("#mobileV3ProgressTitle").inner_text() == "需重试"
            assert page.locator("#mobileV3ProgressElapsed").inner_text() == "已结束"
            assert "刷新结果" not in page.locator("#mobileV3ProgressDetail").inner_text()
        finally:
            browser.close()


def test_doc268_ecommerce_submit_errors_keep_raw_transport_diagnostics_out_of_the_dom() -> None:
    project = _browser_project(job_ids=[STALE_JOB_ID])
    project["metadata"]["ecommerce_project_view"]["groups"]["generated_and_review_history"]["delivered_outputs"] = [
        {"output_id": "doc268-delivered-history", "job_id": STALE_JOB_ID, "state": "delivered"},
    ]
    raw_detail = "private-provider-path /tmp/image_edit_invalid_request_unattributed sha256:abc"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            desktop = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            _install_browser_transport(desktop, project=project)
            desktop.evaluate(
                """
                (project) => {
                  v3State.currentProject = project;
                  v3State.currentJob = {
                    job_id: 'job-770-stale',
                    status: 'blocked',
                    warnings: ['old-provider-secret /old/internal/path sha256:old'],
                    metadata: { project_id: project.project_id, project_outputs: [] },
                  };
                  v3State.selectedScenario = 'ecommerce';
                  v3State.templateCatalogStatus = 'ready';
                  v3State.templates = [{ template_id: 'ecommerce_template', project_can_create_jobs: true }];
                  window.fetch = async () => { throw new Error('private-provider-path /tmp/image_edit_invalid_request_unattributed sha256:abc'); };
                }
                """,
                project,
            )
            desktop.evaluate("async () => { await createV3Job(); }")
            assert raw_detail not in desktop.locator("body").inner_text()
            assert "old-provider-secret" not in desktop.locator("body").inner_text()
            assert "/old/internal/path" not in desktop.locator("body").inner_text()
            assert desktop.evaluate(
                "v3State.currentProject.metadata.ecommerce_project_view.groups.generated_and_review_history.delivered_outputs[0].output_id"
            ) == "doc268-delivered-history"
            assert "doc268-delivered-history" not in desktop.locator("body").inner_text()
            assert desktop.evaluate("v3State.currentJob === null") is True
            assert desktop.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 0
            assert desktop.evaluate("v3State.ecommerceSubmissionDiagnostic.includes('private-provider-path')") is True

            mobile = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            _install_browser_transport(mobile, project=project)
            mobile.evaluate(
                """
                (project) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = project;
                  mobileV3State.currentJob = {
                    job_id: 'job-770-stale',
                    status: 'blocked',
                    warnings: ['old-provider-secret /old/internal/path sha256:old'],
                    metadata: { project_id: project.project_id, project_outputs: [] },
                  };
                  mobileV3State.selectedTemplate = 'ecommerce_template';
                  window.fetch = async () => { throw new Error('private-provider-path /tmp/image_edit_invalid_request_unattributed sha256:abc'); };
                }
                """,
                project,
            )
            mobile.evaluate("async () => { await generateMobileV3Job(); }")
            assert raw_detail not in mobile.locator("body").inner_text()
            assert "old-provider-secret" not in mobile.locator("body").inner_text()
            assert "/old/internal/path" not in mobile.locator("body").inner_text()
            assert mobile.evaluate(
                "mobileV3State.currentProject.metadata.ecommerce_project_view.groups.generated_and_review_history.delivered_outputs[0].output_id"
            ) == "doc268-delivered-history"
            assert "doc268-delivered-history" not in mobile.locator("body").inner_text()
            assert mobile.evaluate("mobileV3State.currentJob === null") is True
            assert mobile.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 0
            assert mobile.evaluate("mobileV3State.ecommerceSubmissionDiagnostic.includes('private-provider-path')") is True
        finally:
            browser.close()


def test_doc268_mobile_project_refresh_keeps_the_explicit_receipt_not_an_older_job() -> None:
    # This is a deliberately stale public project snapshot that arrives after
    # the tab already knows FRESH_JOB_ID. Normal durable project ordering still
    # appends a newly created job as the last entry.
    project = _browser_project(job_ids=[STALE_JOB_ID])
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            _install_browser_transport(page, project=project)
            page.evaluate(
                """
                ({ project, fresh }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = fresh;
                  mobileV3State.ecommerceSubmissionReceipt = { projectId: project.project_id, jobId: fresh.job_id };
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                }
                """,
                {"project": project, "fresh": _fresh_provider_policy_block()},
            )

            page.evaluate(f"async () => {{ await refreshMobileV3ProjectDetail('{PROJECT_ID}'); }}")

            assert page.evaluate("mobileV3State.currentJob.job_id") == FRESH_JOB_ID
            assert page.evaluate("mobileV3State.busy === false") is True
            assert page.locator("#mobileV3ProgressTitle").inner_text() == "需重试"
            assert page.locator("#mobileV3ProgressElapsed").inner_text() == "已结束"
            mobile_status_text = " ".join(
                [
                    page.locator("#mobileV3ProgressDetail").inner_text(),
                    page.locator("#mobileV3GenerateBtn").inner_text(),
                    page.locator("#mobileV3ProjectCurrentOperation").inner_text(),
                ]
            )
            assert all(term not in mobile_status_text for term in ("正在准备生成", "理解需求", "生成图片", "刷新结果", "进行中"))
            mobile_public_text = " ".join(
                [
                    page.locator("#mobileV3ProjectCurrentOperation").inner_text(),
                    page.locator("#mobileV3ProgressDetail").inner_text(),
                ]
            )
            assert all(
                value not in mobile_public_text
                for value in (FRESH_PROVIDER_FAILURE_CODE, STALE_JOB_ID, FRESH_JOB_ID, "output-", "/", "sha256")
            )
            assert page.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 0
            page.wait_for_timeout(50)
            assert page.evaluate("window.__doc268Requests.filter((item) => item.method === 'POST').length") == 0
        finally:
            browser.close()
