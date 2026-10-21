"""Existing administrator page, with all HTTP replaced by synthetic fixtures."""
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

STATIC = Path(__file__).resolve().parents[2] / "src_skeleton/app/static"
ORIGIN = "https://alchemy-admin.test"
API = "/v1/admin/render-bridge"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        yield browser
        browser.close()


class AdminFixture:
    def __init__(self, status=200):
        self.status = status
        self.probes = 0
        self.saves = []
        self.unexpected = []
        self.value = {"mode": "disabled", "base_url": "https://bridge.fixture", "workspace": "fixture-workspace",
            "profiles": ["fake-image"], "native_enabled": False, "native_profiles": ["fake-image"],
            "credential_configured": True, "configuration_error": None, "runtime_active": False}

    def route(self, route):
        request = route.request
        url = urlsplit(request.url)
        if f"{url.scheme}://{url.netloc}" != ORIGIN:
            self.unexpected.append(request.url)
            route.abort()
            return
        path = url.path
        if path == "/admin/billing":
            route.fulfill(path=str(STATIC / "billing-admin.html"), content_type="text/html")
        elif path.startswith("/static/") and (STATIC / path.removeprefix("/static/")).is_file():
            suffix = Path(path).suffix
            route.fulfill(path=str(STATIC / path.removeprefix("/static/")), content_type={".js": "application/javascript", ".css": "text/css", ".svg": "image/svg+xml"}.get(suffix, "application/octet-stream"))
        elif path == "/favicon.ico":
            route.fulfill(status=204)
        elif path == API + "/settings":
            if self.status != 200:
                route.fulfill(status=self.status, json={"detail": {"code": "admin_required"}})
                return
            if request.method == "POST":
                assert request.headers["x-alchemy-bridge-admin"] == "1"
                body = request.post_data_json
                assert "token" not in body
                self.saves.append(body)
                self.value.update(body, runtime_active=body["mode"] != "disabled")
            route.fulfill(json=self.value)
        elif path == API + "/probe":
            assert request.method == "POST" and request.headers["x-alchemy-bridge-admin"] == "1"
            self.probes += 1
            route.fulfill(json={"connection": "reachable", "authentication": "accepted", "capabilities": "compatible", "node_readiness": "offline", "profiles": [{"execution_profile_id": "fake-image", "availability": "offline"}], "admission": {"accepting_new_tasks": False, "mode": "draining"}, "real_generation_verified": False})
        elif path == "/api/v2/veyra/billing/settings":
            route.fulfill(json={"rules": [], "persisted": True})
        elif path == "/v1/admin/retention/settings":
            route.fulfill(json={"delete_protected_data": False, "retention_days": 30})
        elif path == "/api/access/admin/keys":
            route.fulfill(json={"summary": {}, "keys": []})
        else:
            self.unexpected.append(f"{request.method} {path}")
            route.abort()


def screenshot(page, name):
    destination = Path(os.getenv("BRIDGE_UI_SCREENSHOT_DIR", "/tmp/render-bridge-admin-screenshots"))
    destination.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(destination / name), full_page=True)


def test_integrated_admin_save_probe_and_mobile_layout(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    fixture = AdminFixture()
    page.route("**/*", fixture.route)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN + "/admin/billing")
    expect(page.locator("#bridgeAdminState")).to_have_text("已停用")
    expect(page.locator("#bridgeAdminProbe")).to_be_disabled()
    expect(page.locator("#bridgeAdminCredential")).to_have_text("已配置 · 不显示密钥")
    assert page.locator("#bridgeAdminForm input[type=password]").count() == 0
    assert fixture.probes == 0
    page.get_by_label("运行模式").select_option("enabled")
    page.get_by_role("button", name="保存桥接设置").click()
    expect(page.locator("#bridgeAdminState")).to_have_text("已启用")
    assert len(fixture.saves) == 1 and fixture.probes == 0
    page.get_by_role("button", name="探测已保存的配置").click()
    expect(page.locator("#bridgeAdminResult")).to_contain_text("HTTP 连接：可连接")
    expect(page.locator("#bridgeAdminResult")).to_contain_text("执行节点：离线")
    expect(page.locator("#bridgeAdminResult")).to_contain_text("真实生图尚未验证")
    screenshot(page, "admin-desktop.png")
    page.set_viewport_size({"width": 390, "height": 844})
    screenshot(page, "admin-mobile.png")
    assert page.locator(".render-bridge-console").evaluate("el => el.scrollWidth <= el.clientWidth + 1")
    page.get_by_label("运行模式").select_option("disabled")
    page.get_by_role("button", name="保存桥接设置").click()
    expect(page.locator("#bridgeAdminProbe")).to_be_disabled()
    expect(page.locator("#bridgeAdminResult")).to_be_hidden()
    assert fixture.probes == 1
    assert not fixture.unexpected and not errors
    page.close()


@pytest.mark.parametrize("status,label", [(401, "未登录"), (403, "非管理员")])
def test_admin_permissions_leave_controls_disabled(browser, status, label):
    page = browser.new_page()
    fixture = AdminFixture(status)
    page.route("**/*", fixture.route)
    page.goto(ORIGIN + "/admin/billing")
    expect(page.locator("#bridgeAdminState")).to_have_text(label)
    expect(page.locator("#bridgeAdminSave")).to_be_disabled()
    expect(page.locator("#bridgeAdminProbe")).to_be_disabled()
    assert not fixture.saves and not fixture.probes and not fixture.unexpected
    page.close()
