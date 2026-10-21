"""Bounded V3 trial browser checks; every HTTP request is intercepted.

The host tests serve the shipped index.html and unchanged app.js. They suspend
only app.js's unrelated authenticated DOMContentLoaded bootstrap, call its real
bindControls(), and seed the project state. This checks the actual host button
and project-dismissal wiring, not login, project loading, or a full V3 bootstrap.
The separately named controller tests use a minimal document with the shipped
trial JS/CSS, so controller coverage cannot be mistaken for host integration.
No server, provider, Bridge process, real account, or native output is used.
"""
from __future__ import annotations

from contextlib import contextmanager
from io import BytesIO
import json
import mimetypes
import os
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from PIL import Image
from playwright.sync_api import Browser, Page, Route, expect, sync_playwright


STATIC = Path(__file__).resolve().parents[2] / "src_skeleton/app/static"
ORIGIN = "https://alchemy-v3-trial.test"
API = "/api/integrations/render-bridge/v1/native"
SESSION = "synthetic-v3-trial-session-not-a-real-credential"
DIALOG = ".v3-bridge-trial"
FIELD = '[data-bridge="%s"]'
PROJECT_A = "fixture-project-a"
PROJECT_B = "fixture-project-b"

# Do not replace app.js or copy its event handler into a lookalike fixture.
# Its declarations, real DOM lookups, and bindControls() execute unchanged.
PAUSE_LEGACY_BOOTSTRAP = """
(() => {
  const add = document.addEventListener.bind(document);
  document.addEventListener = (type, callback, options) => {
    if (type === 'DOMContentLoaded' && typeof callback === 'function'
        && callback.toString().includes('hydratePortalHomeLink()')
        && callback.toString().includes('bindControls()')) {
      window.__trialFixturePausedLegacyBootstrap = true;
      return;
    }
    return add(type, callback, options);
  };
})();
"""


class TrialFixture:
    def __init__(self) -> None:
        self.status = {"available": True, "mode": "enabled", "profiles": [
            "fake-image", "codex-image", "midjourney-manual", "unapproved-profile"]}
        self.failures: dict[str, int] = {}
        self.references = {
            PROJECT_A: [{"asset_id": f"source-{suffix}", "label": f"Project A original {suffix}"}
                        for suffix in ("a", "b", "c")],
            PROJECT_B: [{"asset_id": "source-other", "label": "Project B original"}],
        }
        self.tasks: dict[str, dict] = {}
        self.creates: list[dict] = []
        self.requests: list[tuple[str, str]] = []
        self.assets: set[str] = set()
        self.unexpected: list[str] = []
        self.hold_references_for: str | None = None
        self.pending_references: Route | None = None
        self.hold_submit = False
        self.pending_submit: Route | None = None
        self.preview_reads = 0
        self.hold_preview = False
        self.pending_preview: Route | None = None
        image = BytesIO()
        Image.new("RGB", (32, 32), "green").save(image, format="PNG")
        self.png = image.getvalue()

    def task(self, key: str, project_id: str = PROJECT_A, **changes) -> dict:
        return {"integration_job_id": key, "project_id": project_id,
                "profile_id": "codex-image", "state": "queued", "size": "1024x1024",
                "output_format": "png", "native_registration": "pending",
                "test_fixture": False, **changes}

    def route(self, route: Route) -> None:
        request = route.request
        url = urlsplit(request.url)
        path, method = url.path, request.method
        self.requests.append((method, path))
        if f"{url.scheme}://{url.netloc}" != ORIGIN:
            self.unexpected.append(f"{method} {request.url}")
            route.abort()
            return
        if method == "GET" and path == "/creative-agent-v3":
            route.fulfill(path=str(STATIC / "index.html"), content_type="text/html")
            return
        if method == "GET" and path == "/bridge-controller-fixture":
            route.fulfill(content_type="text/html", body="""<!doctype html>
                <html lang="zh-CN"><meta charset="utf-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Isolated trial controller fixture, not the V3 host</title>
                <link rel="stylesheet" href="/static/v3-bridge-trial.css">
                <script src="/static/v3-bridge-trial.js" defer></script><body></body></html>""")
            return
        if method == "GET" and path.startswith("/static/"):
            asset = (STATIC / path.removeprefix("/static/")).resolve()
            if asset.is_relative_to(STATIC) and asset.is_file():
                self.assets.add(asset.name)
                route.fulfill(path=str(asset), content_type=mimetypes.guess_type(asset.name)[0]
                              or "application/octet-stream")
                return
        if method == "GET" and path == "/favicon.ico":
            route.fulfill(status=204)
            return
        if method == "GET" and path == "/api/v3/creative-agent/outputs/synthetic-native-registration/preview":
            assert request.headers.get("authorization") == f"Bearer {SESSION}"
            self.preview_reads += 1
            if self.hold_preview:
                self.pending_preview = route
            else:
                route.fulfill(content_type="image/png", body=self.png)
            return
        if path.startswith(API + "/"):
            assert request.headers.get("authorization") == f"Bearer {SESSION}"
            if path in self.failures:
                route.fulfill(status=self.failures[path], json={"detail": {"code": "fixture_denied"}})
                return
            if method == "GET" and path == API + "/status":
                route.fulfill(json=self.status)
                return
            if method == "GET" and path in {API + "/references", API + "/tasks"}:
                query = parse_qs(url.query)
                assert set(query) == {"project_id"}
                project_id = query["project_id"][0]
                assert project_id in self.references
                if path.endswith("/references"):
                    if project_id == self.hold_references_for:
                        self.pending_references = route
                    else:
                        route.fulfill(json={"references": self.references[project_id]})
                else:
                    # Include other-project tasks to verify the controller's scope guard.
                    route.fulfill(json={"tasks": list(self.tasks.values())})
                return
            if method == "POST" and path == API + "/tasks":
                assert request.headers["x-alchemy-bridge-preview"] == "1"
                assert request.headers["content-type"] == "application/json"
                body = request.post_data_json
                self.creates.append(body)
                task = self.tasks.setdefault(body["client_request_id"], self.task(
                    body["client_request_id"], body["project_id"], profile_id=body["profile_id"],
                    size=body["size"], output_format=body["output_format"],
                    test_fixture=body["profile_id"] == "fake-image"))
                if self.hold_submit:
                    self.pending_submit = route
                else:
                    route.fulfill(status=202, json=task)
                return
        # No fallback to a server. Select, export, generation, provider, account,
        # upload and all other unapproved paths fail the fixture.
        self.unexpected.append(f"{method} {request.url}")
        route.abort()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@contextmanager
def trial_page(browser: Browser, *, host: bool = False, ignore_abort: bool = False):
    fixture = TrialFixture()
    context = browser.new_context(service_workers="block", viewport={"width": 1440, "height": 1100})
    context.route("**/*", fixture.route)
    context.add_init_script(f"localStorage.setItem('alchemy_veyra_access_token', {json.dumps(SESSION)});")
    context.add_init_script("""(() => {
      window.__trialBlobCreated = []; window.__trialBlobRevoked = [];
      const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
      URL.createObjectURL = blob => { const url = create(blob); window.__trialBlobCreated.push(url); return url; };
      URL.revokeObjectURL = url => { window.__trialBlobRevoked.push(url); return revoke(url); };
    })();""")
    if host:
        context.add_init_script(PAUSE_LEGACY_BOOTSTRAP)
    if ignore_abort:
        # A transport delivering after cancellation must still fail the epoch
        # check. Requests still go through the same synthetic HTTP interceptor.
        context.add_init_script("""(() => { const fetch = window.fetch.bind(window);
            window.fetch = (url, options = {}) => fetch(url, {...options, signal: undefined});
        })();""")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN + ("/creative-agent-v3" if host else "/bridge-controller-fixture"))
    try:
        yield page, fixture
        assert errors == []
        assert fixture.unexpected == []
    finally:
        context.close()


def field(page: Page, name: str):
    return page.locator(DIALOG).locator(FIELD % name)


def expect_settings_disabled(page: Page) -> None:
    # CI 39554386105: Playwright's actionability matcher does not classify the
    # fieldset container itself as disabled. Check its native property and the
    # actual controls affected by inherited fieldset disabling instead.
    expect(field(page, "settings")).to_have_js_property("disabled", True)
    for name in ("prompt", "ack", "format"):
        expect(field(page, name)).to_be_disabled()
    shapes = page.locator(f'{DIALOG} input[name="bridge-size"]')
    expect(shapes).to_have_count(3)
    for shape in shapes.all():
        expect(shape).to_be_disabled()
    for profile in page.locator(f'{DIALOG} input[name="bridge-profile"]').all():
        expect(profile).to_be_disabled()


def open_controller(page: Page, *, project_id: str = PROJECT_A, eligible: bool = True,
                    prompt: str = "Synthetic single image, no external generation.") -> None:
    page.evaluate("input => window.AlchemyBridgeTrial.open(input)", {
        "projectId": project_id, "title": f"Synthetic {project_id}",
        "eligible": eligible, "prompt": prompt})
    expect(page.locator(DIALOG)).to_be_visible()


def ready(page: Page) -> None:
    expect(field(page, "start")).to_be_enabled()
    expect(field(page, "tasks")).to_contain_text("还没有试用记录")


def submit(page: Page) -> None:
    field(page, "ack").check()
    with page.expect_response(lambda response: response.url == ORIGIN + API + "/tasks"
                              and response.request.method == "POST"):
        field(page, "start").click()
    expect(field(page, "start")).to_be_enabled()


def expand_options(page: Page) -> None:
    page.locator(f'{DIALOG} form details > summary').click()


def seed_host(page: Page) -> dict:
    assert page.evaluate("window.__trialFixturePausedLegacyBootstrap === true")
    return page.evaluate("""() => {
      bindControls();
      const project = {project_id: 'fixture-project-a', title: 'Synthetic bridge project',
        status: 'active', primary_template_id: 'general_template',
        metadata: {v3_workspace: 'standard'}};
      Object.assign(v3State, {view: 'workspace', workspaceMode: 'standard', currentProject: project,
        generationCount: 4, selectedSize: '1536x1024', selectedVariationMode: 'delivery_suite',
        uploadedAssets: [{asset_id: 'host-only-reference'}],
        files: [{name: 'not-uploaded.png'}]});
      document.body.dataset.activeModule = 'v3';
      els.panels.forEach(panel => {
        panel.hidden = panel.dataset.panel !== 'v3';
        panel.classList.toggle('active', !panel.hidden);
      });
      renderV3ViewState();
      // The host's project loader is out of scope; reveal its actual composer.
      els.v3ProjectSubpage.hidden = false;
      els.v3PromptInput.value = 'Only this host prompt may enter the independent trial.';
      els.v3CountInput.value = '4';
      return {prompt: els.v3PromptInput.value, count: v3State.generationCount,
        size: v3State.selectedSize, mode: v3State.selectedVariationMode,
        references: v3State.uploadedAssets, files: v3State.files};
    }""")


def screenshot(page: Page, filename: str, *, scroll_to_top: bool = True) -> None:
    destination = Path(os.getenv("BRIDGE_UI_SCREENSHOT_DIR", "/tmp/render-bridge-admin-screenshots"))
    destination.mkdir(parents=True, exist_ok=True)
    if scroll_to_top:
        page.locator(DIALOG).evaluate("dialog => dialog.scrollTop = 0")
    assert page.locator(DIALOG).evaluate("""dialog => {
      const box = dialog.getBoundingClientRect();
      return box.left >= 0 && box.right <= innerWidth + 1
        && box.top >= 0 && box.bottom <= innerHeight + 1
        && dialog.scrollWidth <= dialog.clientWidth + 1;
    }""")
    page.screenshot(path=str(destination / filename), full_page=False)


def test_host_shipped_button_open_close_preserves_original_controls_and_layout(browser: Browser) -> None:
    with trial_page(browser, host=True) as (page, fixture):
        original = seed_host(page)
        assert {"app.js", "v3-bridge-trial.js", "styles.css", "v3-bridge-trial.css"} <= fixture.assets
        expect(page.locator("#v3BridgeTrialBtn")).to_be_visible()
        expect(page.locator("#v3CreateJobBtn")).to_be_visible()
        page.locator("#v3BridgeTrialBtn").click()
        ready(page)
        expect(field(page, "prompt")).to_have_value(original["prompt"])
        expect(field(page, "project")).to_have_text("Synthetic bridge project")
        expect(page.locator(f'{DIALOG} input[name="bridge-size"]:checked')).to_have_value("1024x1024")
        expect(field(page, "references").locator("input:checked")).to_have_count(0)
        screenshot(page, "v3-trial-host-desktop.png")
        page.set_viewport_size({"width": 390, "height": 844})
        screenshot(page, "v3-trial-host-mobile.png")
        # Only the trial's narrow layout is under test, not the legacy shell's
        # mobile navigation. Restore desktop before returning to its composer.
        page.set_viewport_size({"width": 1440, "height": 1100})
        field(page, "close").click()
        expect(page.locator(DIALOG)).not_to_be_visible()
        assert page.evaluate("""() => ({prompt: els.v3PromptInput.value,
          count: v3State.generationCount, size: v3State.selectedSize,
          mode: v3State.selectedVariationMode, references: v3State.uploadedAssets,
          files: v3State.files})""") == original
        page.locator("#v3BridgeTrialBtn").click()
        ready(page)
        page.keyboard.press("Escape")
        expect(page.locator(DIALOG)).not_to_be_visible()
        assert fixture.creates == []


def test_host_real_project_render_hook_closes_old_trial(browser: Browser) -> None:
    with trial_page(browser, host=True) as (page, fixture):
        seed_host(page)
        page.locator("#v3BridgeTrialBtn").click()
        ready(page)
        page.evaluate("""() => {
          v3State.currentProject = {...v3State.currentProject, project_id: 'fixture-project-b',
            title: 'Synthetic second project'};
          renderV3ProjectDetail();
        }""")
        expect(page.locator(DIALOG)).not_to_be_visible()
        expect(field(page, "tasks")).to_be_empty()
        page.locator("#v3BridgeTrialBtn").click()
        ready(page)
        expect(field(page, "project")).to_have_text("Synthetic second project")
        expect(field(page, "references")).to_contain_text("Project B original")
        assert fixture.creates == []


@pytest.mark.parametrize("change", [
    {"view": "home"}, {"status": "archived"},
    {"template": "ecommerce_template"}, {"workspace": "professional"}, {"missing": True},
])
def test_host_ineligible_project_cannot_submit(browser: Browser, change: dict) -> None:
    with trial_page(browser, host=True) as (page, fixture):
        seed_host(page)
        page.evaluate("""change => {
          if (change.view) v3State.view = change.view;
          if (change.status) v3State.currentProject.status = change.status;
          if (change.template) v3State.currentProject.primary_template_id = change.template;
          if (change.workspace) v3State.currentProject.metadata.v3_workspace = change.workspace;
          if (change.missing) v3State.currentProject = null;
        }""", change)
        page.locator("#v3BridgeTrialBtn").click()
        expect(field(page, "start")).to_be_disabled()
        expect(field(page, "notice")).to_contain_text("标准工作区")
        field(page, "refresh").click()
        expect(field(page, "start")).to_be_disabled()
        assert not any(path.startswith(API) for _, path in fixture.requests)


@pytest.mark.parametrize("next_token", ["another-synthetic-session", ""])
def test_host_same_tab_session_change_immediately_closes_trial(browser: Browser, next_token: str) -> None:
    with trial_page(browser, host=True) as (page, fixture):
        seed_host(page)
        page.locator("#v3BridgeTrialBtn").click()
        ready(page)
        page.evaluate("token => setVeyraToken(token)", next_token)
        expect(page.locator(DIALOG)).not_to_be_visible()
        expect(field(page, "project")).to_be_empty()
        expect(field(page, "prompt")).to_have_value("")
        assert fixture.creates == []


def test_host_submit_carries_only_prompt_not_original_generation_options(browser: Browser) -> None:
    with trial_page(browser, host=True) as (page, fixture):
        original = seed_host(page)
        page.locator("#v3BridgeTrialBtn").click()
        ready(page)
        submit(page)
        body = fixture.creates[0]
        assert body["user_input"] == original["prompt"]
        assert body["uploaded_asset_ids"] == []
        assert body["size"] == "1024x1024"
        assert not ({"count", "generation_count", "variation_mode", "input_fidelity", "quality"} & body.keys())
        assert page.evaluate("v3State.generationCount") == original["count"]
        assert page.evaluate("v3State.selectedSize") == original["size"]
        assert page.evaluate("v3State.selectedVariationMode") == original["mode"]
        assert page.evaluate("v3State.uploadedAssets") == original["references"]
        assert [(method, path) for method, path in fixture.requests if method != "GET"] == [("POST", API + "/tasks")]


def test_controller_repeat_submit_reload_reuses_key_and_only_approved_fields(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        open_controller(page)
        ready(page)
        expect(page.locator(f'{DIALOG} input[name="bridge-profile"]')).to_have_count(3)
        assert set(page.locator(f'{DIALOG} input[name="bridge-size"]').evaluate_all(
            "inputs => inputs.map(input => input.value)")) == {"1024x1024", "1024x768", "768x1024"}
        assert field(page, "format").locator("option").evaluate_all(
            "options => options.map(option => option.value)") == ["png", "jpeg"]
        expect(page.locator(f'{DIALOG} input[type="number"], {DIALOG} input[type="range"]')).to_have_count(0)
        for attempt in range(3):
            if attempt == 2:
                page.reload()
                open_controller(page)
                expect(field(page, "start")).to_be_enabled()
            if attempt != 1:
                expand_options(page)
                field(page, "references").locator('input[value="source-b"]').check()
                field(page, "references").locator('input[value="source-a"]').check()
                field(page, "references").locator('input[value="source-c"]').click()
                expect(field(page, "references").locator('input[value="source-c"]')).not_to_be_checked()
                page.locator(f'{DIALOG} input[name="bridge-profile"][value="codex-image"]').check()
                page.locator(f'{DIALOG} input[name="bridge-size"][value="768x1024"]').check()
                field(page, "format").select_option("jpeg")
            submit(page)
            expect(page.locator(f"{DIALOG} .bridge-task")).to_have_count(1)
        assert len(fixture.creates) == 3
        assert fixture.creates[0] == fixture.creates[1] == fixture.creates[2]
        body = fixture.creates[0]
        assert set(body) == {"project_id", "user_input", "uploaded_asset_ids", "profile_id", "size",
                             "output_format", "acknowledge_native_development", "client_request_id"}
        assert body["project_id"] == PROJECT_A and body["uploaded_asset_ids"] == ["source-b", "source-a"]
        assert body["size"] == "768x1024" and body["output_format"] == "jpeg"
        assert body["profile_id"] == "codex-image" and body["acknowledge_native_development"] is True
        assert body["client_request_id"] and len(fixture.tasks) == 1
        storage = page.evaluate("JSON.stringify(Object.entries(sessionStorage))")
        assert body["user_input"] not in storage and SESSION not in storage and "source-b" not in storage


def test_controller_pending_submit_blocks_duplicate_and_changed_content_gets_new_key(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        open_controller(page)
        ready(page)
        fixture.hold_submit = True
        field(page, "ack").check()
        with page.expect_request(lambda request: request.url == ORIGIN + API + "/tasks"
                                 and request.method == "POST"):
            field(page, "start").click()
        expect(field(page, "start")).to_be_disabled()
        expect_settings_disabled(page)
        field(page, "form").evaluate("form => form.dispatchEvent(new Event('submit', {cancelable: true}))")
        assert len(fixture.creates) == 1 and fixture.pending_submit is not None
        fixture.pending_submit.fulfill(status=202, json=next(iter(fixture.tasks.values())))
        fixture.hold_submit = False
        expect(field(page, "start")).to_be_enabled()
        field(page, "prompt").fill("A different synthetic image request.")
        submit(page)
        assert fixture.creates[0]["client_request_id"] != fixture.creates[1]["client_request_id"]


@pytest.mark.parametrize("status,failed_path,http_status,message", [
    ({"available": False, "mode": "disabled"}, None, None, "尚未准备好"),
    ({"mode": "draining"}, None, None, "暂停接收新任务"),
    ({"profiles": []}, None, None, "没有可用的制作方式"),
    ({}, "/status", 404, "管理员可能尚未开启"),
    ({}, "/status", 401, "请先登录"),
    ({}, "/status", 403, "请先登录"),
    ({}, "/references", 403, "请先登录"),
    ({}, "/tasks", 403, "请先登录"),
])
def test_controller_unavailable_missing_draining_or_auth_denied_stays_disabled(
    browser: Browser, status: dict, failed_path: str | None, http_status: int | None, message: str,
) -> None:
    with trial_page(browser) as (page, fixture):
        fixture.status.update(status)
        if failed_path:
            fixture.failures[API + failed_path] = http_status
        open_controller(page)
        expect(field(page, "notice")).to_contain_text(message)
        expect(field(page, "start")).to_be_disabled()
        expect_settings_disabled(page)
        assert fixture.creates == []


def test_controller_manual_reference_refusal_and_reference_order(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        open_controller(page)
        ready(page)
        expand_options(page)
        field(page, "references").locator('input[value="source-a"]').check()
        page.locator(f'{DIALOG} input[name="bridge-profile"][value="midjourney-manual"]').check()
        field(page, "ack").check()
        field(page, "start").click()
        expect(field(page, "notice")).to_contain_text("人工交回不支持参考图")
        assert fixture.creates == []
        expect(field(page, "references").locator('input[value="source-a"]')).to_be_checked()
        field(page, "references").locator('input[value="source-a"]').uncheck()
        submit(page)
        assert fixture.creates[0]["profile_id"] == "midjourney-manual"
        assert fixture.creates[0]["uploaded_asset_ids"] == []


def test_controller_project_switch_rejects_late_old_project_response(browser: Browser) -> None:
    with trial_page(browser, ignore_abort=True) as (page, fixture):
        fixture.hold_references_for = PROJECT_A
        with page.expect_request(lambda request: request.url.endswith("/references?project_id=" + PROJECT_A)):
            open_controller(page)
        expect(field(page, "start")).to_be_disabled()
        assert fixture.pending_references is not None
        page.evaluate("project => window.AlchemyBridgeTrial.syncProject(project)", PROJECT_B)
        expect(page.locator(DIALOG)).not_to_be_visible()
        open_controller(page, project_id=PROJECT_B)
        ready(page)
        expect(field(page, "references")).to_contain_text("Project B original")
        with page.expect_response(lambda response: response.url.endswith("/references?project_id=" + PROJECT_A)) as old:
            fixture.pending_references.fulfill(json={"references": fixture.references[PROJECT_A]})
        old.value.finished()
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        expect(field(page, "references")).not_to_contain_text("Project A original")
        expect(field(page, "references").locator('input[value="source-other"]')).to_be_attached()
        submit(page)
        assert fixture.creates[0]["project_id"] == PROJECT_B


def test_controller_live_review_pending_never_adds_select_export_or_reference_actions(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        page.clock.install()
        fixture.tasks["review-task"] = fixture.task("review-task", state="registered",
            native_registration="registered", review_pending=True, review_status="finalizing",
            native_registration_ref="synthetic-native-registration")
        fixture.tasks["other-task"] = fixture.task("other-task", PROJECT_B, state="failed")
        open_controller(page)
        expect(page.locator(f"{DIALOG} .bridge-task")).to_have_count(1)
        expect(field(page, "tasks")).to_contain_text("图片已登记，审核处理中")
        expect(field(page, "tasks")).to_contain_text("不会自动选中、导出或设为后续参考")
        expect(field(page, "tasks").get_by_role("button", name="查看审核图片", exact=True)).to_be_visible()
        expect(field(page, "tasks").locator("button")).to_have_count(1)
        expect(field(page, "tasks").locator("a, img")).to_have_count(0)
        assert fixture.preview_reads == 0
        fixture.tasks["review-task"].update(review_pending=False, review_status="generated")
        page.clock.fast_forward(5000)
        expect(field(page, "tasks")).to_contain_text("已完成审核流程")
        expect(field(page, "tasks")).not_to_contain_text("审核处理中")
        expect(field(page, "tasks")).to_contain_text("不代表正式交付")
        expect(field(page, "tasks").locator("button")).to_have_count(1)
        expect(field(page, "tasks").locator("a, img")).to_have_count(0)
        assert not any(method != "GET" for method, _ in fixture.requests)


def test_controller_preview_requires_authenticated_fetch_and_revokes_blob_on_close(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        fixture.tasks["review-task"] = fixture.task("review-task", state="registered",
            native_registration="registered", review_pending=True, review_status="finalizing",
            native_registration_ref="synthetic-native-registration")
        open_controller(page)
        view = field(page, "tasks").get_by_role("button", name="查看审核图片", exact=True)
        expect(view).to_be_visible()
        assert fixture.preview_reads == 0
        view.click()
        image = field(page, "tasks").locator("img")
        expect(image).to_be_visible()
        page.wait_for_function("document.querySelector('.bridge-review-preview img')?.naturalWidth === 32")
        assert image.get_attribute("src").startswith("blob:")
        assert fixture.preview_reads == 1
        expect(field(page, "tasks").locator("a")).to_have_count(0)
        expect(field(page, "tasks")).to_contain_text("仅供审核，不是正式作品")
        page.set_viewport_size({"width": 390, "height": 844})
        image.scroll_into_view_if_needed()
        screenshot(page, "v3-trial-review-mobile.png", scroll_to_top=False)
        field(page, "refresh").click()
        expect(image).to_be_visible()
        assert fixture.preview_reads == 1  # Reuse the authorized blob, not another request.
        created = page.evaluate("window.__trialBlobCreated")
        assert len(created) == 1
        field(page, "close").click()
        expect(page.locator(DIALOG)).not_to_be_visible()
        expect(field(page, "tasks")).to_be_empty()
        assert page.evaluate("window.__trialBlobRevoked") == created
        assert not any(method != "GET" for method, _ in fixture.requests)


def test_controller_late_preview_after_project_switch_cannot_create_blob_or_leak_image(browser: Browser) -> None:
    with trial_page(browser, ignore_abort=True) as (page, fixture):
        fixture.hold_preview = True
        fixture.tasks["review-task"] = fixture.task("review-task", state="registered",
            native_registration="registered", native_registration_ref="synthetic-native-registration")
        open_controller(page)
        with page.expect_request(lambda request: request.url.endswith("/synthetic-native-registration/preview")):
            field(page, "tasks").get_by_role("button", name="查看审核图片", exact=True).click()
        expect(field(page, "tasks")).to_contain_text("正在读取审核图片")
        assert fixture.pending_preview is not None
        page.evaluate("project => window.AlchemyBridgeTrial.syncProject(project)", PROJECT_B)
        open_controller(page, project_id=PROJECT_B)
        ready(page)
        with page.expect_response(lambda response: response.url.endswith("/synthetic-native-registration/preview")) as old:
            fixture.pending_preview.fulfill(content_type="image/png", body=fixture.png)
        old.value.finished()
        page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
        expect(field(page, "tasks").locator("img")).to_have_count(0)
        assert page.evaluate("window.__trialBlobCreated") == []
        expect(field(page, "project")).to_contain_text(PROJECT_B)


def test_controller_lost_reference_clears_selection_and_requires_new_acknowledgment(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        open_controller(page)
        ready(page)
        expand_options(page)
        field(page, "references").locator('input[value="source-a"]').check()
        field(page, "ack").check()
        fixture.references[PROJECT_A] = [item for item in fixture.references[PROJECT_A]
                                         if item["asset_id"] != "source-a"]
        field(page, "refresh").click()
        expect(field(page, "notice")).to_contain_text("已取消选择")
        expect(field(page, "references").locator("input:checked")).to_have_count(0)
        expect(field(page, "ack")).not_to_be_checked()
        field(page, "start").click()
        assert fixture.creates == []
        submit(page)
        assert fixture.creates[0]["uploaded_asset_ids"] == []


def test_controller_lost_profile_has_no_silent_fallback_and_requires_choice_and_ack(browser: Browser) -> None:
    with trial_page(browser) as (page, fixture):
        open_controller(page)
        ready(page)
        page.locator(f'{DIALOG} input[name="bridge-profile"][value="codex-image"]').check()
        field(page, "ack").check()
        fixture.status["profiles"] = ["fake-image", "midjourney-manual"]
        field(page, "refresh").click()
        expect(field(page, "notice")).to_contain_text("先前的制作方式已不可用")
        expect(page.locator(f'{DIALOG} input[name="bridge-profile"]:checked')).to_have_count(0)
        expect(field(page, "ack")).not_to_be_checked()
        field(page, "start").click()
        assert fixture.creates == []
        field(page, "ack").check()
        field(page, "start").click()
        assert fixture.creates == []
        page.locator(f'{DIALOG} input[name="bridge-profile"][value="fake-image"]').check()
        submit(page)
        assert fixture.creates[0]["profile_id"] == "fake-image"


@pytest.mark.parametrize("event", ["popstate", "pagehide", "account-change"])
def test_controller_navigation_or_account_change_closes_and_clears_private_view(browser: Browser, event: str) -> None:
    with trial_page(browser) as (page, fixture):
        open_controller(page)
        ready(page)
        if event == "account-change":
            page.evaluate("""() => {
              localStorage.setItem('alchemy_veyra_access_token', 'another-synthetic-session');
              dispatchEvent(new StorageEvent('storage', {key: 'alchemy_veyra_access_token'}));
            }""")
        else:
            page.evaluate("name => dispatchEvent(new Event(name))", event)
        expect(page.locator(DIALOG)).not_to_be_visible()
        expect(field(page, "prompt")).to_have_value("")
        expect(field(page, "references")).to_be_empty()
        expect(field(page, "tasks")).to_be_empty()
        assert fixture.creates == []
