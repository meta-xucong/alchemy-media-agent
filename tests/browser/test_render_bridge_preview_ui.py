"""Small shipped-preview UI checks; every HTTP request is synthetic/intercepted.

No app server, Bridge package, provider, native job, or real account is used.
Run separately from the contract tests after installing Playwright Chromium.
"""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image
import pytest
from playwright.sync_api import Browser, Page, Route, expect, sync_playwright


STATIC = Path(__file__).resolve().parents[2] / "src_skeleton/app/integrations/render_bridge/static"
ORIGIN = "https://render-bridge.test"
API = "/api/integrations/render-bridge/v1"
SESSION = "synthetic-preview-session-not-a-real-credential"


class PreviewFixture:
    def __init__(self) -> None:
        self.creates: list[dict] = []
        self.tasks: dict[str, dict] = {}
        self.canceled: list[str] = []
        self.unexpected: list[str] = []
        self.preview_reads = 0
        image = BytesIO()
        Image.new("RGB", (32, 32), "green").save(image, format="PNG")
        self.png = image.getvalue()

    def task(self, key: str, *, ready: bool = False) -> dict:
        return {
            "integration_job_id": key,
            "project_id": "fixture-project",
            "profile_id": "fake-image",
            "created_at": "2026-01-01T00:00:00Z",
            "state": "preview_ready" if ready else "queued",
            "preview_url": f"{API}/tasks/{key}/preview" if ready else None,
            "native_registration": "not_connected",
            "delivery_ack": "pending",
        }

    def route(self, route: Route) -> None:
        request = route.request
        url = urlsplit(request.url)
        path, method = url.path, request.method
        if f"{url.scheme}://{url.netloc}" != ORIGIN:
            self.unexpected.append(f"{method} {request.url}")
            route.abort()
            return
        assets = {
            "/render-bridge-preview": ("index.html", "text/html"),
            "/render-bridge-preview/assets/preview.js": ("preview.js", "application/javascript"),
            "/render-bridge-preview/assets/preview.css": ("preview.css", "text/css"),
        }
        if method == "GET" and path in assets:
            filename, content_type = assets[path]
            route.fulfill(path=str(STATIC / filename), content_type=content_type)
            return
        if method == "GET" and path == "/favicon.ico":
            route.fulfill(status=204)
            return
        if method == "GET" and path == "/creative-agent-v3":
            # Only navigation is under test, not the original application's UI.
            route.fulfill(content_type="text/html", body="<title>Original V3 route fixture</title>")
            return
        if request.headers.get("authorization") != f"Bearer {SESSION}":
            self.unexpected.append(f"Missing synthetic session: {method} {path}")
            route.fulfill(status=401, json={"detail": {"code": "unauthorized"}})
            return
        if method == "GET" and path == f"{API}/status":
            route.fulfill(json={"mode": "enabled", "available": True, "profiles": ["fake-image"]})
        elif method == "GET" and path == "/api/v3/creative-agent/projects":
            route.fulfill(json={"projects": [{"project_id": "fixture-project", "title": "Synthetic project"}]})
        elif method == "GET" and path == f"{API}/tasks":
            assert url.query == "project_id=fixture-project"
            route.fulfill(json={"tasks": list(self.tasks.values())})
        elif method == "POST" and path == f"{API}/tasks":
            assert request.headers["x-alchemy-bridge-preview"] == "1"
            payload = request.post_data_json
            self.creates.append(payload)
            key = payload["client_request_id"]
            task = self.tasks.setdefault(key, self.task(key))
            route.fulfill(status=202, json=task)
        elif method == "GET" and path == f"{API}/tasks/ready-task/preview":
            assert self.tasks["ready-task"]["state"] == "preview_ready"
            self.preview_reads += 1
            route.fulfill(content_type="image/png", body=self.png)
        elif method == "POST" and path == f"{API}/tasks/ready-task/cancel":
            assert request.headers["x-alchemy-bridge-preview"] == "1"
            self.canceled.append("ready-task")
            task = self.tasks["ready-task"]
            task.update(state="canceled", preview_url=None)
            route.fulfill(json=task)
        else:
            self.unexpected.append(f"{method} {request.url}")
            route.abort()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


@pytest.fixture
def preview(browser: Browser):
    fixture = PreviewFixture()
    context = browser.new_context(service_workers="block")
    context.route("**/*", fixture.route)
    # Exercise the shipped existing-session compatibility, without native login.
    context.add_init_script(f"localStorage.setItem('alchemy_veyra_access_token', {json.dumps(SESSION)});")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        yield page, fixture
        assert errors == []
        assert fixture.unexpected == []
    finally:
        context.close()


def open_preview(page: Page) -> None:
    page.goto(f"{ORIGIN}/render-bridge-preview")
    expect(page.locator("#project option[value='fixture-project']")).to_be_attached()
    expect(page.locator("#submit")).to_be_enabled()
    page.select_option("#project", "fixture-project")


def test_create_and_repeat_click_reuse_client_request_id(preview) -> None:
    page, fixture = preview
    open_preview(page)
    page.fill("#prompt", "Synthetic green square, no provider or native acceptance.")
    page.check("#acknowledge")
    for _ in range(2):
        with page.expect_response(lambda response: response.url == f"{ORIGIN}{API}/tasks"
                                  and response.request.method == "POST"):
            page.click("#submit")
        expect(page.locator("#submit")).to_be_enabled()
        expect(page.locator(".task")).to_have_count(1)
    assert len(fixture.creates) == 2
    assert fixture.creates[0] == fixture.creates[1]
    assert fixture.creates[0]["client_request_id"]
    assert fixture.creates[0]["acknowledge_test_only"] is True
    assert len(fixture.tasks) == 1
    assert fixture.preview_reads == 0


def test_preview_cancel_hides_image_and_original_link_navigates(preview) -> None:
    page, fixture = preview
    fixture.tasks["ready-task"] = fixture.task("ready-task", ready=True)
    open_preview(page)
    image = page.locator(".task img")
    expect(image).to_be_visible()
    page.wait_for_function(
        "document.querySelector('.task img')?.complete"
        " && document.querySelector('.task img')?.naturalWidth === 32"
    )
    reads_before_cancel = fixture.preview_reads
    assert reads_before_cancel >= 1
    page.locator(".task button").click()
    expect(image).to_have_count(0)
    expect(page.locator(".task button")).to_have_count(0)
    assert fixture.canceled == ["ready-task"]
    page.click("#refresh")
    expect(image).to_have_count(0)
    original_link = page.locator("nav a[href='/creative-agent-v3']")
    expect(original_link).to_be_visible()
    expect(page.locator("nav a[href='/render-bridge-diagnostics']")).to_be_visible()
    original_link.click()
    expect(page).to_have_url(f"{ORIGIN}/creative-agent-v3")
    page.go_back()
    expect(page).to_have_url(f"{ORIGIN}/render-bridge-preview")
    expect(page.locator("#project option[value='fixture-project']")).to_be_attached()
    page.select_option("#project", "fixture-project")
    page.click("#refresh")
    expect(page.locator(".task")).to_have_count(1)
    expect(image).to_have_count(0)
    assert fixture.preview_reads == reads_before_cancel


class NativeReferenceFixture(PreviewFixture):
    def route(self, route: Route) -> None:
        request = route.request
        path = urlsplit(request.url).path
        native_api = API + "/native"
        if request.method == "GET" and path in {
            "/render-bridge-native-test", "/render-bridge-native-test/assets/native.js"
        }:
            filename = "native.js" if path.endswith(".js") else "native.html"
            route.fulfill(path=str(STATIC / filename), content_type="application/javascript" if filename.endswith(".js") else "text/html")
            return
        if path.startswith(native_api) or path == "/api/v3/creative-agent/projects":
            assert request.headers.get("authorization") == f"Bearer {SESSION}"
            if path == native_api + "/status":
                route.fulfill(json={"available": True, "mode": "enabled", "profiles": getattr(self, "profiles", ["fake-image"])})
            elif path == "/api/v3/creative-agent/projects":
                route.fulfill(json={"projects": [{"project_id": "fixture-project", "title": "References"},
                                                 {"project_id": "empty-project", "title": "No references"}]})
            elif path == native_api + "/references":
                empty = "empty-project" in request.url
                route.fulfill(json={"references": [] if empty else [
                    {"asset_id": "source-a", "label": "Blue original", "size_bytes": 1000},
                    {"asset_id": "source-b", "label": "Red original", "size_bytes": 2000}]})
            elif path == native_api + "/tasks" and request.method == "GET":
                route.fulfill(json={"tasks": list(self.tasks.values())})
            elif path == native_api + "/tasks" and request.method == "POST":
                assert request.headers["x-alchemy-bridge-preview"] == "1"
                payload = request.post_data_json
                self.creates.append(payload)
                key = payload["client_request_id"]
                task = self.tasks.setdefault(key, {**self.task(key), "size": payload["size"],
                    "reference_count": len(payload["uploaded_asset_ids"]), "native_registration": "pending",
                    "profile_id": payload.get("profile_id", "fake-image"), "output_format": payload.get("output_format", "png"),
                    "test_fixture": payload.get("profile_id", "fake-image") == "fake-image"})
                route.fulfill(status=202, json=task)
            else:
                self.unexpected.append(f"{request.method} {path}")
                route.abort()
            return
        super().route(route)


def test_native_reference_order_size_replay_and_project_change(browser: Browser) -> None:
    fixture = NativeReferenceFixture()
    context = browser.new_context(service_workers="block")
    context.route("**/*", fixture.route)
    context.add_init_script(f"localStorage.setItem('alchemy_veyra_access_token', {json.dumps(SESSION)});")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(ORIGIN + "/render-bridge-native-test")
        expect(page.locator("nav a[href='/render-bridge-diagnostics']")).to_be_visible()
        expect(page.locator("#project option[value='fixture-project']")).to_be_attached()
        expect(page.locator("#submit")).to_be_disabled()
        page.select_option("#project", "fixture-project")
        expect(page.locator("#reference-1 option[value='source-a']")).to_be_attached()
        expect(page.locator("#submit")).to_be_enabled()
        page.select_option("#reference-1", "source-b")
        page.select_option("#reference-2", "source-a")
        page.select_option("#size", "1024x768")
        page.fill("#user-input", "Synthetic input transport test.")
        page.check("#acknowledge")
        for _ in range(2):
            with page.expect_response(lambda response: response.url == ORIGIN + API + "/native/tasks"
                                      and response.request.method == "POST"):
                page.click("#submit")
            expect(page.locator("#submit")).to_be_enabled()
        assert fixture.creates[0] == fixture.creates[1]
        assert fixture.creates[0]["uploaded_asset_ids"] == ["source-b", "source-a"]
        assert fixture.creates[0]["size"] == "1024x768"
        page.select_option("#size", "768x1024")
        with page.expect_response(lambda response: response.url == ORIGIN + API + "/native/tasks"
                                  and response.request.method == "POST"):
            page.click("#submit")
        assert fixture.creates[-1]["client_request_id"] != fixture.creates[0]["client_request_id"]
        assert fixture.creates[-1]["size"] == "768x1024"
        page.select_option("#project", "empty-project")
        expect(page.locator("#reference-1 option")).to_have_count(1)
        expect(page.locator("#reference-2 option")).to_have_count(1)
        expect(page.locator("#reference-1")).to_have_value("")
        expect(page.locator("#reference-2")).to_have_value("")
        assert errors == [] and fixture.unexpected == []
    finally:
        context.close()


def test_native_explicit_profile_format_and_manual_reference_refusal(browser: Browser) -> None:
    fixture = NativeReferenceFixture()
    fixture.profiles = ["fake-image", "codex-image", "midjourney-manual"]
    context = browser.new_context(service_workers="block")
    context.route("**/*", fixture.route)
    context.add_init_script(f"localStorage.setItem('alchemy_veyra_access_token', {json.dumps(SESSION)});")
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(ORIGIN + "/render-bridge-native-test")
        expect(page.locator("#profile option")).to_have_count(3)
        expect(page.locator("#profile")).to_have_value("fake-image")
        expect(page.locator("body")).to_contain_text("产物验证，不是原生参数控制")
        page.select_option("#project", "fixture-project")
        expect(page.locator("#submit")).to_be_enabled()
        page.select_option("#reference-1", "source-a")
        page.select_option("#profile", "midjourney-manual")
        page.fill("#user-input", "Explicit offline protocol fixture.")
        page.check("#acknowledge")
        page.click("#submit")
        expect(page.locator("#notice")).to_contain_text("manual 配置不支持参考图")
        assert fixture.creates == []
        expect(page.locator("#reference-1")).to_have_value("source-a")
        page.select_option("#profile", "codex-image")
        page.select_option("#format", "jpeg")
        with page.expect_response(lambda response: response.url == ORIGIN + API + "/native/tasks"
                                  and response.request.method == "POST"):
            page.click("#submit")
        payload = fixture.creates[0]
        assert payload["profile_id"] == "codex-image" and payload["output_format"] == "jpeg"
        assert payload["acknowledge_native_development"] and not payload["acknowledge_synthetic_native_test"]
        expect(page.locator("#tasks")).to_contain_text("真实工具未验收")
        assert errors == [] and fixture.unexpected == []
    finally:
        context.close()


class DiagnosticsFixture:
    """Every diagnostics read/import is synthetic; no task API is permitted."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []
        self.imports: list[str] = []
        self.unexpected: list[str] = []
        self.server_reads = 0
        self.report_error: str | None = None
        self.server = {
            "schema_version": "1",
            "source": "configured_bridge_http",
            "connection": "ok",
            "code": None,
            "profiles": [{
                "execution_profile_id": "fake-image",
                "execution_profile_revision": "fixture-v1",
                "execution_mode": "automatic",
                "validation": "synthetic_only",
                "production_verified": False,
                "parameter_contract": {
                    "schema_version": "1",
                    "accepted_parameters": ["width", "height", "seed"],
                    "required_parameters": [],
                    "dimension_semantics": "exact_output_match",
                    "seed_semantics": "accepted_not_applied",
                    "executor_control": "deterministic_fixture",
                    "reference_semantics": "hash_checked_not_conditioning",
                    "unsupported_parameters": ["quality", "output_format", "input_fidelity"],
                },
            }, {
                "execution_profile_id": "legacy-profile",
                "execution_profile_revision": "old",
                "execution_mode": "unverified",
                "validation": "unverified",
                "production_verified": False,
                # Older servers may omit parameter_contract entirely.
            }],
            "native_real_profile_support": False,
            "local_cli": {"status": "not_checked"},
            "real_generation_verified": False,
        }

    def route(self, route: Route) -> None:
        request = route.request
        url = urlsplit(request.url)
        path, method = url.path, request.method
        self.requests.append((method, path))
        if f"{url.scheme}://{url.netloc}" != ORIGIN:
            self.unexpected.append(f"{method} {request.url}")
            route.abort()
            return
        assets = {
            "/render-bridge-diagnostics": ("diagnostics.html", "text/html"),
            "/render-bridge-diagnostics/assets/diagnostics.js": ("diagnostics.js", "application/javascript"),
            "/render-bridge-preview/assets/preview.css": ("preview.css", "text/css"),
        }
        if method == "GET" and path in assets:
            filename, content_type = assets[path]
            route.fulfill(path=str(STATIC / filename), content_type=content_type)
            return
        if method == "GET" and path == "/favicon.ico":
            route.fulfill(status=204)
            return
        assert request.headers.get("authorization") == f"Bearer {SESSION}"
        if method == "GET" and path == API + "/diagnostics":
            route.fulfill(json={
                "schema_version": "1", "source": "alchemy_server_configuration",
                "mode": "disabled", "configured_profiles": ["fake-image", "codex-image"],
                "native_enabled": False, "native_profiles": ["fake-image"],
                "native_real_profile_support": False,
                "local_cli": {"status": "not_checked", "reason": "browser_cannot_probe_remote_agent"},
                "real_generation_verified": False, "formal_delivery": False,
                "configuration_error": None,
            })
        elif method == "GET" and path == API + "/diagnostics/server":
            self.server_reads += 1
            route.fulfill(json=self.server)
        elif method == "POST" and path == API + "/diagnostics/report":
            assert request.headers["x-alchemy-bridge-preview"] == "1"
            assert request.headers["content-type"] == "application/json"
            self.imports.append(request.post_data)
            if self.report_error:
                route.fulfill(status=422, json={"detail": {"code": self.report_error}})
            else:
                route.fulfill(json={
                    "schema_version": "1", "source": "user_imported_local_report",
                    "verified_by_server": False, "authorization_effect": "none",
                    "report": request.post_data_json,
                })
        else:
            self.unexpected.append(f"{method} {request.url}")
            route.abort()


@pytest.fixture
def diagnostics(browser: Browser):
    fixture = DiagnosticsFixture()
    context = browser.new_context(service_workers="block")
    context.route("**/*", fixture.route)
    context.add_init_script(f"localStorage.setItem('alchemy_veyra_access_token', {json.dumps(SESSION)});")
    page = context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    try:
        page.goto(ORIGIN + "/render-bridge-diagnostics")
        expect(page.locator("#configuration")).to_contain_text("codex-image")
        yield page, fixture
        assert errors == []
        assert fixture.unexpected == []
        assert all(method != "POST" or path == API + "/diagnostics/report"
                   for method, path in fixture.requests)
        assert not any("/tasks" in path for _, path in fixture.requests)
    finally:
        context.close()


def local_doctor_report() -> dict:
    return {
        "schema_version": "1", "kind": "render_bridge_doctor",
        "producer": {"name": "alchemy-render-bridge", "version": "0.1.0a1"},
        "outcome": "attention", "profiles": ["fake-image", "codex-image"],
        "checks": [{
            "id": "codex-cli", "status": "attention", "evidence": "local_probe",
            "code": "cli_not_found", "next_step": "Install the CLI on the actual agent machine.",
        }],
        "real_generation_verified": False, "login_verified": False,
    }


def submit_report_file(page: Page, contents: str | bytes) -> None:
    page.locator("#report-file").set_input_files({
        "name": "doctor-report.json", "mimeType": "application/json",
        "buffer": contents.encode("utf-8") if isinstance(contents, str) else contents,
    })
    page.click("#import-report")


def test_diagnostics_separates_config_from_explicit_http_probe(diagnostics) -> None:
    page, fixture = diagnostics
    expect(page.locator("#configuration")).to_contain_text("本地 CLI：未检查")
    expect(page.locator("#configuration-heading + p")).to_contain_text("Alchemy 配置")
    expect(page.locator("#server-status")).to_have_text("尚未检查。")
    assert fixture.server_reads == 0
    assert fixture.imports == []
    page.click("#check-server")
    expect(page.locator("#server-status")).to_contain_text("HTTP 连接正常")
    expect(page.locator("#server-status")).to_contain_text("本地 CLI、登录与真实生成未验证")
    expect(page.locator("#server-profiles")).to_contain_text("接受参数：width、height、seed")
    expect(page.locator("#server-profiles")).to_contain_text("参考图语义：hash_checked_not_conditioning")
    expect(page.locator("#server-profiles")).to_contain_text("参数合同不可用")
    expect(page.locator("#server-profiles")).to_contain_text("这不代表没有能力")
    expect(page.locator("#check-server")).to_be_enabled()
    assert fixture.server_reads == 1
    page.click("#check-server")
    expect(page.locator("#check-server")).to_be_enabled()
    assert fixture.server_reads == 2
    expect(page.locator("#server-profiles .task")).to_have_count(2)


@pytest.mark.parametrize("outcome", ["attention", "invalid"])
def test_diagnostics_import_shows_untrusted_evidence_and_next_steps(diagnostics, outcome) -> None:
    page, fixture = diagnostics
    report = local_doctor_report()
    report["outcome"] = outcome
    report["checks"].append({
        "id": "operator", "status": "not_checked", "evidence": "operator_declaration",
        "code": "not_verified", "next_step": '<img src="https://invalid.test/tracker" onerror="alert(1)">',
    })
    original = json.dumps(report, indent=2) + "\n"
    submit_report_file(page, original)
    expect(page.locator("#report-status")).to_contain_text("已导入自述证据")
    expect(page.locator("#report-status")).to_contain_text("未授权执行配置")
    expect(page.locator("#report-result")).to_contain_text("Install the CLI on the actual agent machine.")
    expect(page.locator("#report-result")).to_contain_text("无法确认来源或新鲜度")
    expect(page.locator("#report-result")).to_contain_text('<img src="https://invalid.test/tracker"')
    expect(page.locator("#report-result img")).to_have_count(0)
    expect(page.locator("#report-file")).to_have_value("")
    assert fixture.imports == [original]
    assert fixture.server_reads == 0
    assert page.evaluate("Object.keys(localStorage)") == ["alchemy_veyra_access_token"]
    assert page.evaluate("Object.keys(sessionStorage)") == []


@pytest.mark.parametrize(("contents", "expected"), [
    ("{ broken json", "报告不是有效 JSON，未发送"),
    (json.dumps({"schema_version": "99", "kind": "render_bridge_doctor"}), "不支持此报告版本"),
    (" " * (64 * 1024 + 1), "报告超过 64 KiB，未发送"),
], ids=["invalid-json", "unknown-version", "oversize"])
def test_diagnostics_rejects_invalid_and_oversize_report_without_post(diagnostics, contents, expected) -> None:
    page, fixture = diagnostics
    submit_report_file(page, contents)
    expect(page.locator("#report-status")).to_contain_text(expected)
    expect(page.locator("#import-report")).to_be_enabled()
    expect(page.locator("#report-file")).to_have_value("")
    expect(page.locator("#report-result")).to_be_empty()
    assert fixture.imports == []
    assert fixture.server_reads == 0


def test_diagnostics_reports_unavailable_server_and_rejected_import(diagnostics) -> None:
    page, fixture = diagnostics
    fixture.server.update(connection="unavailable", code="bridge_unavailable", profiles=[])
    page.click("#check-server")
    expect(page.locator("#server-status")).to_contain_text("HTTP 服务不可达（bridge_unavailable）")
    expect(page.locator("#server-profiles")).to_contain_text("本次未取得执行配置能力")
    fixture.report_error = "invalid_doctor_report"
    submit_report_file(page, json.dumps(local_doctor_report()))
    expect(page.locator("#report-status")).to_contain_text("invalid_doctor_report")
    expect(page.locator("#report-result")).to_be_empty()
    expect(page.locator("#import-report")).to_be_enabled()
