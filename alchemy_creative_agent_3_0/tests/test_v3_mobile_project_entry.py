from __future__ import annotations

from playwright.sync_api import sync_playwright

from alchemy_creative_agent_3_0.tests.test_v3_doc263_ecommerce_ui_recovery_browser import (
    MOBILE_HTML,
    MOBILE_JS,
    _browser_page,
)


def _project(project_id: str = "mobile-entry-project", *, template_id: str | None = "general_template") -> dict:
    project = {
        "project_id": project_id,
        "title": "手机项目入口回归",
        "user_goal": "验证手机版项目可以打开",
        "short_summary": "验证手机版项目可以打开",
        "status": "active",
        "job_ids": [],
        "latest_thumbnail_urls": [],
    }
    if template_id:
        project["primary_template_id"] = template_id
    return project


def _ready_mobile_page(browser, project: dict | None = None):
    page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
    page.evaluate(
        """(project) => {
          ensureMobileLayers();
          setupMobileV3Adapter();
          mobileV3State.workspaceMode = "standard";
          mobileV3State.projects = [project];
          mobileV3State.loaded = true;
          mobileV3State.templatesLoaded = true;
          mobileV3State.templates = [];
          mobileV3State.projectsLoadError = "";
          mobileV3State.outputs = [];
          mobileV3State.outputsLoaded = true;
          mobileV3State.outputsSurface = "home_preview";
          mobileV3State.outputError = "";
          mobileV3State.previewProjectIds = new Set();
          renderMobileV3ProjectCards();
        }""",
        project or _project(),
    )
    return page


def test_project_list_is_interactive_while_home_preview_request_is_pending() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _browser_page(browser, html_path=MOBILE_HTML, script_path=MOBILE_JS)
            page.evaluate(
                """() => {
                  ensureMobileLayers();
                  setupMobileV3Adapter();
                  mobileV3State.workspaceMode = "standard";
                  mobileV3State.projects = [];
                  mobileV3State.loaded = false;
                  mobileV3State.loading = false;
                  mobileV3State.projectsLoadingMore = false;
                  mobileV3State.outputs = [];
                  mobileV3State.outputsLoaded = false;
                  mobileV3State.outputsSurface = "none";
                  mobileV3State.reviewOutputs = [];
                  const project = {
                    project_id: "mobile-entry-project",
                    title: "可交互的项目",
                    short_summary: "先进入项目主页",
                    user_goal: "确认项目入口不会被预览请求锁住",
                    primary_template_id: "general_template",
                    status: "active",
                    job_ids: [],
                    latest_thumbnail_urls: [],
                  };
                  window.__homePreviewPending = false;
                  window.__releaseHomePreview = null;
                  window.__detailRequestPending = false;
                  window.__releaseDetailRequest = null;
                  window.fetch = async (input) => {
                    const url = String(input);
                    let body = {};
                    if (url.includes("/projects?") && !url.includes("project_id=")) {
                      body = {
                        projects: [project],
                        templates: [{ template_id: "general_template", project_can_create_jobs: true }],
                        total: 1,
                        has_more: false,
                        next_cursor: null,
                      };
                    } else if (url.includes("surface=home_preview")) {
                      window.__homePreviewPending = true;
                      return await new Promise((resolve) => {
                        window.__releaseHomePreview = () => resolve(new Response(JSON.stringify({ items: [] }), { status: 200 }));
                      });
                    } else if (url.includes("surface=delivery_preview")) {
                      body = { items: [], history_items: [] };
                    } else if (url.includes("/projects/mobile-entry-project/timeline")) {
                      body = { items: [] };
                    } else if (url.includes("/projects/mobile-entry-project")) {
                      if (url.includes("?view=summary")) {
                        window.__detailRequestPending = true;
                        return await new Promise((resolve) => {
                          window.__releaseDetailRequest = () => resolve(new Response(JSON.stringify({ project }), { status: 200 }));
                        });
                      }
                      body = { project };
                    }
                    return new Response(JSON.stringify(body), { status: 200 });
                  };
                  window.__homeLoadPromise = loadMobileV3Projects({ silent: true });
                }""",
            )
            page.wait_for_function("window.__homePreviewPending === true")

            assert page.locator("#mobileV3LoadingLayer").evaluate("(node) => node.hidden")
            assert not page.locator("body").evaluate("(node) => node.classList.contains('v3-mobile-loading-active')")
            page.locator("[data-mobile-v3-open-project-detail]").click()
            assert page.locator("body").get_attribute("data-mobile-active-surface") == "v3-project-detail"
            page.wait_for_function("window.__detailRequestPending === true")
            assert not page.locator("#mobileV3LoadingLayer").evaluate("(node) => node.hidden")

            page.evaluate("window.__releaseHomePreview?.()")
            page.evaluate("async () => await window.__homeLoadPromise")
            assert not page.locator("#mobileV3LoadingLayer").evaluate("(node) => node.hidden")
            page.evaluate("window.__releaseDetailRequest?.()")
            page.wait_for_function("document.querySelector('#mobileV3LoadingLayer').hidden === true")
        finally:
            browser.close()


def test_project_card_copy_opens_detail_and_cover_keeps_gallery_preview() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _ready_mobile_page(browser)

            page.locator("[data-mobile-v3-open-project-detail]").click()
            assert page.locator("body").get_attribute("data-mobile-active-surface") == "v3-project-detail"

            page.evaluate(
                """() => {
                  const missing = document.createElement("button");
                  missing.type = "button";
                  missing.dataset.mobileV3OpenProjectDetail = "deleted-project";
                  document.querySelector("#mobileV3ProjectGrid").appendChild(missing);
                }"""
            )
            page.locator('[data-mobile-v3-open-project-detail="deleted-project"]').click()
            assert "刷新项目列表" in page.locator("#mobileV3Notice").inner_text()

            page.evaluate("closeMobileSurface({ silent: true, fromHistory: true })")
            page.locator(".v3-mobile-project-preview[data-mobile-v3-open-project]").click()
            assert page.locator("body").get_attribute("data-mobile-active-surface") == "v3-gallery"

            page.locator("#mobileV3OpenProjectBtn").click()
            assert page.locator("body").get_attribute("data-mobile-active-surface") == "v3-project-detail"

            page.evaluate("closeMobileSurface({ silent: true, fromHistory: true })")
            page.locator('button[data-mobile-v3-workspace="professional"]').click()
            assert page.evaluate("mobileV3State.workspaceMode") == "professional"
        finally:
            browser.close()


def test_unknown_template_opens_read_only_detail_and_never_reuses_previous_template() -> None:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = _ready_mobile_page(browser, _project("mobile-unknown-template", template_id=None))
            page.evaluate(
                """() => {
                  mobileV3State.selectedTemplate = "ecommerce_template";
                  window.fetch = async (input) => {
                    const url = String(input);
                    let body = {};
                    if (url.includes("/projects/mobile-unknown-template")) {
                      body = { project: {
                        project_id: "mobile-unknown-template",
                        title: "缺少模板的项目",
                        user_goal: "只读查看",
                        short_summary: "只读查看",
                        status: "active",
                        job_ids: [],
                        latest_thumbnail_urls: [],
                      } };
                    } else if (url.includes("/project-outputs")) {
                      body = { items: [], history_items: [], review_items: [] };
                    } else if (url.includes("/timeline")) {
                      body = { items: [] };
                    }
                    return new Response(JSON.stringify(body), { status: 200 });
                  };
                }""",
            )

            page.locator("[data-mobile-v3-open-project-detail]").click()
            assert page.locator("body").get_attribute("data-mobile-active-surface") == "v3-project-detail"
            compose = page.locator('#mobileV3ProjectDetail [data-mobile-open="v3-compose"]')
            assert compose.is_disabled()
            assert "项目类型待确认" in compose.inner_text()

            page.evaluate("async () => await generateMobileV3Job()")
            assert "不能继续生成" in page.locator("#mobileV3Notice").inner_text()
            assert not page.evaluate("mobileV3State.busy")
        finally:
            browser.close()
