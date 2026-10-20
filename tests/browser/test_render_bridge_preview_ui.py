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
    expect(page.locator("nav a")).to_have_attribute("href", "/creative-agent-v3")
    page.locator("nav a").click()
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
                route.fulfill(json={"available": True, "mode": "enabled"})
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
                    "reference_count": len(payload["uploaded_asset_ids"]), "native_registration": "pending"})
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
