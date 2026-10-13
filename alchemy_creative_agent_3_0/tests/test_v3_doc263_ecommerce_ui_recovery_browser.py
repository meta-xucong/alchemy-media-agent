"""Doc263 browser contracts for E-Commerce recovery projections.

The test loads the real desktop and mobile HTML/JS in Chromium, with only the
local API transport mocked. It intentionally never starts a server or provider.
"""

from __future__ import annotations

import re
from pathlib import Path

from playwright.sync_api import Browser, Page, sync_playwright


ROOT = Path(__file__).resolve().parents[2]
DESKTOP_HTML = ROOT / "src_skeleton" / "app" / "static" / "index.html"
DESKTOP_JS = ROOT / "src_skeleton" / "app" / "static" / "app.js"
MOBILE_HTML = ROOT / "src_skeleton" / "app" / "mobile_static" / "index.html"
MOBILE_JS = ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js"


def _inline_shell(path: Path) -> str:
    return re.sub(r"<script\b[^>]*\bsrc=[^>]*></script>", "", path.read_text(encoding="utf-8"), flags=re.IGNORECASE)


_MOCK_FETCH = """
window.__doc263Requests = [];
window.fetch = async (input, init = {}) => {
  const url = String(input);
  const method = String(init.method || "GET").toUpperCase();
  window.__doc263Requests.push({ url, method });
  const project = window.__doc263ServerProject || {};
  let body = {};
  if (method === "POST" && /\\/projects\\/doc263-project\\/jobs$/.test(url)) {
    body = window.__doc263CreateJobResponse || { job_id: "doc263-new-job", status: "blocked", metadata: { project_outputs: [] } };
  } else if (/\\/projects\\/doc263-project\\/timeline/.test(url)) {
    body = { items: [] };
  } else if (/\\/project-outputs/.test(url)) {
    body = { items: [], review_items: [] };
  } else if (/\\/jobs\\/doc263-new-job/.test(url)) {
    body = { job_id: "doc263-new-job", status: "blocked", metadata: { project_outputs: [] } };
  } else if (/\\/projects\\/doc263-project$/.test(url)) {
    body = { project };
  }
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
};
"""


def _browser_page(browser: Browser, *, html_path: Path, script_path: Path) -> Page:
    page = browser.new_page()
    page.set_content(_inline_shell(html_path))
    page.add_script_tag(content=script_path.read_text(encoding="utf-8"))
    page.evaluate(_MOCK_FETCH)
    # The normal product route opens just one surface at a time. The browser
    # contract drives the same controls directly, so make the test shell's
    # otherwise hidden project panes visible to real Playwright clicks.
    page.evaluate("document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; })")
    return page


def _ecommerce_project() -> dict:
    return {
        "project_id": "doc263-project",
        "user_goal": "Show the same product faithfully.",
        "short_summary": "Show the same product faithfully.",
        "primary_template_id": "ecommerce_template",
        "job_ids": ["doc263-blocked-job"],
        "reference_assets": [
            {
                "reference_id": "canonical-product-reference",
                "asset_ref_id": "original-product",
                "source_type": "uploaded",
                "use_policy": "product",
                "status": "active",
            }
        ],
        # The server excludes withheld images from the homepage projection.
        "latest_thumbnail_urls": [],
        "metadata": {
            "ecommerce_project_view": {
                "schema_version": "doc263_ecommerce_project_view_v1",
                "groups": {
                    "original_product_inputs": {
                        "items": [{"asset_ref_id": "original-product", "label": "Canonical product original"}]
                    },
                    "locked_person_identity": {
                        "items": [{"visual_asset_id": "face-asset", "asset_type": "people"}]
                    },
                    "selected_continuation_directions": {
                        "items": [{"output_id": "selected-output", "job_id": "prior-job", "label": "Selected direction"}]
                    },
                    "generated_and_review_history": {
                        "delivered_outputs": [],
                        "review_withheld_outputs": [{"output_id": "withheld-review", "label": "Review-only image"}],
                        "failed_attempts": [{"job_id": "doc263-blocked-job", "state": "failed_no_delivery"}],
                    },
                },
            },
            "current_operation": {
                "state": "failed_no_delivery",
                "pending": False,
                "next_actions": [{"action": "continue"}],
            },
        },
    }


def _withheld_review_output() -> dict:
    return {
        "output_id": "withheld-review",
        "project_id": "doc263-project",
        "thumbnail_url": "https://example.invalid/withheld.png",
        "preview_url": "https://example.invalid/withheld.png",
        "delivery_state": "review_withheld",
        "review_reason": "Needs manual review.",
        "metadata": {
            "final_delivery": {
                "delivery_gate_applies": True,
                "automatic_delivery_available": False,
            }
        },
    }


def _needs_input_job() -> dict:
    return {
        "job_id": "doc263-needs-input-job",
        "status": "blocked",
        # Real Doc264 pre-planning closures can return without a scenario
        # object; the server-owned operation/template metadata is authoritative.
        "scenario": None,
        "warnings": [],
        "metadata": {
            "project_id": "doc263-project",
            "template_id": "ecommerce_template",
            "project_outputs": [],
            "current_operation": {
                "state": "needs_input",
                "terminal": True,
                "pending": False,
                "next_actions": [{"id": "review_product_inputs"}],
            },
        },
    }


def _needs_input_project() -> dict:
    project = _ecommerce_project()
    project["metadata"]["current_operation"] = {
        "state": "needs_input",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_product_inputs"}],
    }
    return project


def _doc265_continuation_reference_project() -> dict:
    project = _ecommerce_project()
    project["job_ids"] = ["doc265-stale-planned-job"]
    project["latest_job_status"] = "planned"
    project["metadata"]["current_operation"] = {
        "state": "continuation_reference_unavailable",
        "terminal": True,
        "pending": False,
        "channel": "selected_continuation_directions",
        "next_actions": [{"id": "review_selected_references"}],
    }
    return project


def test_doc263_desktop_recovery_is_deliberate_and_uses_exact_server_projection() -> None:
    project = _ecommerce_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project, reviewOutput }) => {
                  window.__doc263ServerProject = project;
                  v3State.currentProject = project;
                  v3State.currentJob = { job_id: "doc263-blocked-job", status: "blocked", warnings: [] };
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  v3State.projectOutputs = [];
                  v3State.projectReviewOutputs = [reviewOutput];
                  document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                  document.querySelector("#v3CreateJobBtn").addEventListener("click", createV3Job);
                  renderV3UsefulReferences();
                  renderV3ProjectOutputBoard();
                  renderV3ProjectNextActions();
                }
                """,
                {"project": project, "reviewOutput": _withheld_review_output()},
            )

            assert page.locator("#v3UsefulReferenceBoard .v3-project-reference-group").count() == 4
            assert page.locator("#v3UsefulReferenceBoard").inner_text().count("Canonical product original") == 1
            assert "复核记录 1 张" in page.locator("#v3ProjectOutputBoard").inner_text()
            assert page.locator("img[data-v3-home-thumb='true']").count() == 0

            page.locator("[data-v3-project-action='start_first_generation']").click()
            assert page.locator("#v3ProjectSubpage").evaluate("(node) => !node.hidden") is True
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0

            page.locator("#v3CreateJobBtn").click()
            page.wait_for_function("window.__doc263Requests.filter((item) => item.method === 'POST').length === 1")
            assert page.evaluate(
                "window.__doc263Requests.filter((item) => item.method === 'POST')[0].url.endsWith('/projects/doc263-project/jobs')"
            )

            assert page.evaluate(
                """
                () => {
                  const stale = {
                    ...v3State.currentProject,
                    metadata: {
                      ...v3State.currentProject.metadata,
                      current_operation: { state: "failed_no_delivery" },
                    },
                  };
                  v3State.currentProject = stale;
                  syncV3ProjectResponseMetadata({
                    metadata: { ecommerce_project_view: stale.metadata.ecommerce_project_view },
                  });
                  return !Object.prototype.hasOwnProperty.call(v3State.currentProject.metadata, "current_operation");
                }
                """
            )
        finally:
            browser.close()


def test_doc265_desktop_continuation_reference_terminal_wins_over_stale_planned_job() -> None:
    project = _doc265_continuation_reference_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project }) => {
                  window.__doc263ServerProject = project;
                  v3State.currentProject = project;
                  v3State.currentJob = {
                    job_id: "doc265-stale-planned-job",
                    status: "planned",
                    metadata: { template_id: "ecommerce_template" },
                    warnings: [],
                  };
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  document.querySelector("#v3ProjectNextActions").addEventListener("click", handleV3ProjectActionClick);
                  renderV3ProjectDetail();
                  document.querySelectorAll('[hidden]').forEach((node) => { node.hidden = false; });
                }
                """,
                {"project": project},
            )

            action_text = page.locator("#v3ProjectNextActions").inner_text()
            assert "已选延续方向需要确认" in action_text
            assert "检查延续方向" in action_text
            assert "商品原图需要重新确认" not in action_text
            assert "准备生成商品图片" not in action_text
            assert "重新尝试一次" not in action_text
            assert page.locator("[data-v3-project-action='review_continuation_references']").count() == 1
            assert page.locator("[data-v3-project-action='start_first_generation']").count() == 0

            page.locator("[data-v3-project-action='review_continuation_references']").click()

            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
            assert "请在已选延续方向或生成与复核历史中重新确认可用成片" in page.locator("#v3NoticeBar").inner_text()
        finally:
            browser.close()


def test_doc263_desktop_needs_input_is_specific_and_does_not_offer_blind_retry() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  v3State.currentProject = project;
                  v3State.currentJob = null;
                  v3State.selectedScenario = "ecommerce";
                  v3State.templateCatalogStatus = "ready";
                  v3State.templates = [{ template_id: "ecommerce_template", project_can_create_jobs: true }];
                  document.querySelector("#v3CreateJobBtn").addEventListener("click", createV3Job);
                }
                """,
                {"project": project, "created": created},
            )

            page.locator("#v3CreateJobBtn").click()
            page.wait_for_function("window.__doc263Requests.filter((item) => item.method === 'POST').length === 1")
            page.wait_for_function("document.body.innerText.includes('商品原图需要重新确认')")

            assert "当前生成暂时受阻，请检查输入后再试。" not in page.locator("body").inner_text()
            assert page.evaluate(
                "window.__doc263Requests.filter((item) => /\\/jobs\\/doc263-needs-input-job$/.test(item.url)).length"
            ) == 0
        finally:
            browser.close()


def test_doc265_mobile_continuation_reference_terminal_wins_over_stale_planned_job() -> None:
    project = _doc265_continuation_reference_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = {
                    job_id: "doc265-stale-planned-job",
                    status: "planned",
                    metadata: { template_id: "ecommerce_template" },
                    warnings: [],
                  };
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  renderMobileV3ReferenceBoard(project);
                  renderMobileV3ProjectCards();
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                {"project": project},
            )

            operation_text = page.locator("#mobileV3ProjectCurrentOperation").inner_text()
            assert "已选延续方向需要确认" in operation_text
            assert "检查延续方向" in operation_text
            assert "商品原图需要重新确认" not in operation_text
            assert "准备中" not in page.locator("#mobileV3ProgressElapsed").inner_text()
            assert "进行中" not in page.locator("#mobileV3ProgressElapsed").inner_text()
            assert page.locator("#mobileV3ProgressTitle").inner_text() == "需重试"
            assert page.locator("[data-mobile-v3-project-action='review_continuation_references']").count() == 1
            assert page.locator("[data-mobile-v3-project-action='continue_recovery']").count() == 0
            assert page.locator("#mobileV3GenerateBtn").is_disabled() is False

            page.locator("[data-mobile-v3-project-action='review_continuation_references']").click()

            assert page.evaluate("document.body.dataset.mobileActiveSurface") == "v3-project-detail"
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0
            assert "已选延续方向需要重新确认" in page.locator("#mobileV3ProgressDetail").inner_text()
            assert "商品原图需要重新确认" not in page.locator("#mobileV3ProgressDetail").inner_text()
        finally:
            browser.close()


def test_doc263_mobile_recovery_is_deliberate_and_does_not_leave_preparing_state() -> None:
    project = _ecommerce_project()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, reviewOutput }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = { job_id: "doc263-blocked-job", status: "blocked", warnings: [] };
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [reviewOutput];
                  mobileV3State.outputsLoaded = true;
                  document.querySelector("#mobileV3GenerateBtn").addEventListener("click", generateMobileV3Job);
                  renderMobileV3ReferenceBoard(project);
                  renderMobileV3ProjectOutputs(project);
                  renderMobileV3ProjectCards();
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-project-detail");
                }
                """,
                {"project": project, "reviewOutput": _withheld_review_output()},
            )

            assert page.locator("#mobileV3ReferenceBoard .v3-mobile-reference-group").count() == 4
            assert page.locator("#mobileV3ReferenceBoard").inner_text().count("Canonical product original") == 1
            assert "复核图 1" in page.locator("#mobileV3OutputGrid").inner_text()
            assert page.locator("img[data-mobile-v3-home-thumb='true']").count() == 0
            assert page.locator("#mobileV3ProjectCurrentOperation").inner_text()
            assert page.locator("[data-mobile-v3-project-action='continue_recovery']").count() == 1
            assert page.locator("#mobileV3GenerateBtn").is_disabled() is False

            page.locator("[data-mobile-v3-project-action='continue_recovery']").click()
            assert page.evaluate("document.body.dataset.mobileActiveSurface") == "v3-compose"
            assert page.evaluate("window.__doc263Requests.filter((item) => item.method === 'POST').length") == 0

            page.locator("#mobileV3GenerateBtn").click()
            page.wait_for_function("window.__doc263Requests.filter((item) => item.method === 'POST').length === 1")

            assert page.evaluate(
                """
                () => {
                  const stale = {
                    ...mobileV3State.currentProject,
                    metadata: {
                      ...mobileV3State.currentProject.metadata,
                      current_operation: { state: "failed_no_delivery" },
                    },
                  };
                  const next = mobileV3ProjectWithResponseMetadata(
                    stale,
                    { metadata: { ecommerce_project_view: stale.metadata.ecommerce_project_view } },
                  );
                  return !Object.prototype.hasOwnProperty.call(next.metadata, "current_operation");
                }
                """
            )
        finally:
            browser.close()


def test_doc263_mobile_needs_input_stops_before_job_polling_and_opens_review_path() -> None:
    project = _needs_input_project()
    created = _needs_input_job()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, created }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  window.__doc263ServerProject = project;
                  window.__doc263CreateJobResponse = created;
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = null;
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [];
                  mobileV3State.outputsLoaded = true;
                  document.querySelector("#mobileV3GenerateBtn").addEventListener("click", generateMobileV3Job);
                  renderMobileV3ProjectCurrentOperation(project);
                  openMobileSurface("v3-compose");
                }
                """,
                {"project": project, "created": created},
            )

            assert "商品原图需要重新确认" in page.locator("#mobileV3ProjectCurrentOperation").inner_text()

            page.locator("#mobileV3GenerateBtn").click()
            page.wait_for_function("window.__doc263Requests.filter((item) => item.method === 'POST').length === 1")
            page.wait_for_timeout(1400)

            assert page.evaluate(
                "window.__doc263Requests.filter((item) => /\\/jobs\\/doc263-needs-input-job$/.test(item.url)).length"
            ) == 0
            assert "商品原图需要重新确认" in page.locator("body").inner_text()
            assert page.locator("#mobileV3GenerateBtn").is_disabled() is False
        finally:
            browser.close()


def test_doc_review_only_generated_images_are_visible_without_delivery_promotion() -> None:
    project = _ecommerce_project()
    review_output = {
        **_withheld_review_output(),
        "job_id": "doc-review-job",
        "candidate_id": "doc-review-candidate",
        "asset_id": "doc-review-asset",
        "thumbnail_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        "preview_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    }
    fail_final_output = {
        **review_output,
        "output_id": "fail-final-output",
        "job_id": "doc-fail-final-job",
        "candidate_id": "fail-final-candidate",
        "delivery_state": "fail_final",
        "review_reason": "Certified quality review failed.",
    }
    foreign_project_output = {**review_output, "output_id": "foreign-project-output", "candidate_id": "foreign-project-candidate", "project_id": "another-project", "title": "FOREIGN PROJECT IMAGE SHOULD NOT APPEAR"}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=DESKTOP_HTML, script_path=DESKTOP_JS)
            page.evaluate(
                """
                ({ project, reviewOutput, failFinalOutput, foreignProjectOutput }) => {
                  v3State.currentProject = project;
                  v3State.currentJob = {
                    job_id: "doc-review-job",
                    status: "blocked",
                    candidates: [{
                      job_id: "doc-review-job",
                      candidate_id: "doc-review-candidate",
                      asset_id: "doc-review-asset",
                      output_id: "withheld-review",
                    }, {
                      job_id: "doc-review-job",
                      candidate_id: "cross-field-collision",
                    }],
                    metadata: {
                      final_delivery: { delivery_gate_applies: true, automatic_delivery_available: false },
                      post_generation_review: {
                        review_output_ids: ["withheld-review", "fail-final-output"],
                        review_reason: "evidence_incomplete",
                        evidence_state: "incomplete",
                        quality_assessment: "needs_manual_review",
                        quality_failure: false,
                      },
                    },
                  };
                  v3State.projectOutputs = [];
                  v3State.projectReviewOutputs = [reviewOutput, failFinalOutput, foreignProjectOutput];
                  window.__evidenceIncompleteHoldLabel = v3JobFinalDeliveryHoldLabel(v3State.currentJob);
                  window.__qualityFailureHoldLabel = v3JobFinalDeliveryHoldLabel({
                    metadata: { post_generation_review: { quality_failure: true } },
                  });
                  window.__reviewMergeCollisionCount = mergeV3ReviewImageSources(
                    [{ output_id: "cross-field-collision", job_id: "job-a" }],
                    [{ candidate_id: "cross-field-collision", job_id: "job-a" }],
                  ).length;
                  renderV3ProjectOutputBoard();
                  renderV3ResultBoard(v3State.currentJob);
                }
                """,
                {"project": project, "reviewOutput": review_output, "failFinalOutput": fail_final_output, "foreignProjectOutput": foreign_project_output},
            )

            details = page.locator("#v3ProjectOutputBoard details.v3-review-output-details")
            assert details.count() == 1
            assert details.evaluate("node => node.open") is True
            assert "仅供复核 · 未进入正式交付" in details.inner_text()
            assert details.locator("img").count() == 2
            assert page.evaluate("window.__reviewMergeCollisionCount") == 2
            assert page.evaluate("window.__evidenceIncompleteHoldLabel") == "审核证据需确认"
            assert page.evaluate("window.__qualityFailureHoldLabel") == "视觉问题需处理"
            assert "FOREIGN PROJECT IMAGE SHOULD NOT APPEAR" not in details.inner_text()
            assert details.locator("[data-v3-output-action='select']").count() == 0
            assert page.locator("#v3ResultBoard .v3-review-only-card img").count() == 1
            assert page.locator("#v3ProjectOutputBoard .v3-project-output-tile").count() == 0
            assert "已生成，但没有进入正式交付" in page.locator("#v3ResultBoard").inner_text()

            page.evaluate(
                """
                ({ project, failFinalOutput }) => {
                  v3State.currentProject = project;
                  v3State.projectReviewOutputs = [failFinalOutput];
                  v3State.projectOutputs = [];
                  v3State.currentJob = {
                    job_id: "doc-fail-final-job",
                    status: "generated",
                    candidates: [{
                      job_id: "doc-fail-final-job",
                      candidate_id: failFinalOutput.candidate_id,
                      output_id: failFinalOutput.output_id,
                    }],
                    metadata: {
                      final_delivery: { delivery_gate_applies: true, automatic_delivery_available: false },
                      post_generation_review: {
                        quality_failure: true,
                        hidden_output_ids: [failFinalOutput.output_id],
                        review_reason: "quality_failure",
                        user_visible_summary: ["Certified quality review failed."],
                      },
                    },
                  };
                  renderV3ResultBoard(v3State.currentJob);
                }
                """,
                {"project": project, "failFinalOutput": fail_final_output},
            )
            failure_board = page.locator("#v3ResultBoard")
            assert "视觉问题需处理" in failure_board.inner_text()
            assert "自动质量审查未通过" in failure_board.inner_text()
            assert "审核证据需确认" not in failure_board.inner_text()
            assert failure_board.locator(".v3-review-only-card img").count() == 1
            assert failure_board.locator(".v3-result-card:not(.v3-review-only-card) [data-v3-preview]").count() == 0

            page.evaluate(
                """
                ({ project, reviewOutput }) => {
                  project.metadata.current_operation = {
                    state: "review_withheld_finalization_failed",
                    terminal: true,
                    pending: false,
                    next_actions: [],
                  };
                  v3State.currentProject = project;
                  v3State.projectOutputs = [{
                    job_id: "doc-review-job",
                    output_id: "must-not-be-formal",
                    project_id: project.project_id,
                    thumbnail_url: reviewOutput.thumbnail_url,
                    delivery_state: "final_delivery",
                  }];
                  v3State.projectReviewOutputs = [reviewOutput];
                  v3State.currentJob = {
                    job_id: "doc-review-job",
                    status: "generated",
                    candidates: [{
                      job_id: "doc-review-job",
                      candidate_id: "doc-review-candidate",
                      output_id: reviewOutput.output_id,
                    }],
                    metadata: {
                      final_delivery: { delivery_gate_applies: true, automatic_delivery_available: true },
                      post_generation_review: { review_output_ids: [reviewOutput.output_id] },
                    },
                  };
                  renderV3ResultBoard(v3State.currentJob);
                }
                """,
                {"project": project, "reviewOutput": review_output},
            )
            finalization_board = page.locator("#v3ResultBoard")
            assert "审核未闭环，图片保留在复核区" in finalization_board.inner_text()
            assert finalization_board.locator(".v3-review-only-card img").count() == 1
            assert finalization_board.locator("[data-v3-preview]").count() == 0
            assert page.evaluate("v3State.resultItems.length") == 0
        finally:
            browser.close()


def test_doc_mobile_review_only_images_survive_finalization_hold_and_gallery() -> None:
    project = _ecommerce_project()
    project["metadata"]["current_operation"] = {
        "state": "review_withheld_finalization_failed",
        "terminal": True,
        "pending": False,
        "next_actions": [],
    }
    review_output = {
        **_withheld_review_output(),
        "job_id": "doc-review-job",
        "candidate_id": "doc-review-candidate",
        "asset_id": "doc-review-asset",
        "thumbnail_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
        "preview_url": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
    }
    fail_final_output = {
        **review_output,
        "output_id": "fail-final-output",
        "job_id": "doc-fail-final-job",
        "candidate_id": "fail-final-candidate",
        "delivery_state": "fail_final",
        "review_reason": "Certified quality review failed.",
    }
    foreign_project_output = {**review_output, "output_id": "foreign-project-output", "candidate_id": "foreign-project-candidate", "project_id": "another-project", "title": "FOREIGN PROJECT IMAGE SHOULD NOT APPEAR"}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """
                ({ project, reviewOutput, failFinalOutput, foreignProjectOutput }) => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.currentProject = project;
                  mobileV3State.projects = [project];
                  mobileV3State.currentJob = {
                    job_id: "doc-review-job",
                    status: "generated",
                    candidates: [{
                      job_id: "doc-review-job",
                      candidate_id: "doc-review-candidate",
                      asset_id: "doc-review-asset",
                      output_id: "withheld-review",
                    }, {
                      job_id: "doc-review-job",
                      candidate_id: "cross-field-collision",
                    }],
                    metadata: {
                      final_delivery: { delivery_gate_applies: true, automatic_delivery_available: false },
                      post_generation_review: {
                        review_output_ids: ["withheld-review", "fail-final-output"],
                        review_reason: "evidence_incomplete",
                        evidence_state: "incomplete",
                        quality_assessment: "needs_manual_review",
                        quality_failure: false,
                      },
                    },
                  };
                  mobileV3State.outputs = [];
                  mobileV3State.reviewOutputs = [reviewOutput, failFinalOutput, foreignProjectOutput];
                  mobileV3State.outputsLoaded = true;
                  window.__reviewMergeCollisionCount = mergeMobileV3ReviewImageSources(
                    [{ output_id: "cross-field-collision", job_id: "job-a" }],
                    [{ candidate_id: "cross-field-collision", job_id: "job-a" }],
                  ).length;
                  renderMobileV3ProjectOutputs(project);
                  renderMobileV3ProjectGallery(project);
                }
                """,
                {"project": project, "reviewOutput": review_output, "failFinalOutput": fail_final_output, "foreignProjectOutput": foreign_project_output},
            )

            output_grid = page.locator("#mobileV3OutputGrid")
            assert "图片保留在复核区" in output_grid.inner_text()
            assert "审核证据需确认" in output_grid.inner_text()
            assert "尚未证明图片质量不合格" in output_grid.inner_text()
            assert "FOREIGN PROJECT IMAGE SHOULD NOT APPEAR" not in output_grid.inner_text()
            assert output_grid.locator(".v3-mobile-output-card.review-only img").count() == 2
            assert page.evaluate("window.__reviewMergeCollisionCount") == 2
            gallery = page.locator("#mobileV3GalleryGrid")
            assert gallery.locator("button.review-only img").count() == 2
            assert "复核图 · 非交付" in gallery.locator(".v3-mobile-gallery-review-badge").inner_text()
            assert "复核图 1" in gallery.locator("button.review-only").first.get_attribute("innerHTML")

            page.evaluate(
                """
                ({ project, failOutput }) => {
                  project.metadata.current_operation.state = "failed_no_delivery";
                  mobileV3State.currentProject = project;
                  mobileV3State.currentJob = {
                    job_id: "doc-fail-final-job",
                    status: "generated",
                    candidates: [{ job_id: "doc-fail-final-job", candidate_id: failOutput.candidate_id, output_id: failOutput.output_id }],
                    metadata: {
                      project_id: project.project_id,
                      final_delivery: { delivery_gate_applies: true, automatic_delivery_available: false },
                      post_generation_review: {
                        quality_failure: true,
                        hidden_output_ids: [failOutput.output_id],
                        review_reason: "quality_failure",
                        user_visible_summary: ["Certified quality review failed."],
                      },
                    },
                  };
                  mobileV3State.reviewOutputs = [failOutput];
                  mobileV3State.outputs = [];
                  renderMobileV3ProjectOutputs(project);
                }
                """,
                {"project": project, "failOutput": fail_final_output},
            )
            failure_grid = page.locator("#mobileV3OutputGrid")
            assert "视觉问题需处理" in failure_grid.inner_text()
            assert "自动审核发现需要处理的视觉问题" in failure_grid.inner_text()
            assert "审核证据不完整" not in failure_grid.inner_text()
            assert "审核未闭环" not in failure_grid.inner_text()
            assert failure_grid.locator(".v3-mobile-output-card.review-only img").count() == 1
            assert failure_grid.locator(".v3-mobile-output-card:not(.review-only)").count() == 0
        finally:
            browser.close()
