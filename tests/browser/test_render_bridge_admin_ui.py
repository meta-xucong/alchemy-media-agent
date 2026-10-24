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
        self.hold_save = False
        self.pending_save = None
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
                if self.hold_save:
                    self.pending_save = route
                    return
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
    # Exercise normal rendering of every independent card before full-page capture.
    # This also handles browser rendering optimizations for offscreen content.
    for card in page.locator(".billing-admin-page > .panel").all():
        card.scroll_into_view_if_needed()
        expect(card).to_be_visible()
    page.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    page.screenshot(path=str(destination / name), full_page=True)



def assert_independent_cards(page, minimum_gap):
    cards = page.locator(".billing-admin-page > .panel")
    expect(cards).to_have_count(4)
    measurements = cards.evaluate_all("""elements => elements.map(el => {
        const box = el.getBoundingClientRect(), style = getComputedStyle(el);
        return { top: box.top, bottom: box.bottom, padding: parseFloat(style.paddingTop),
                 radius: parseFloat(style.borderRadius), overflow: el.scrollWidth > el.clientWidth + 1 };
    })""")
    for previous, current in zip(measurements, measurements[1:]):
        assert current["top"] - previous["bottom"] >= minimum_gap
    assert len({card["padding"] for card in measurements}) == 1
    assert all(card["radius"] >= 14 and not card["overflow"] for card in measurements)
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")

def test_simple_admin_buttons_advanced_settings_and_mobile_layout(browser):
    page = browser.new_page(viewport={"width": 1440, "height": 1100})
    fixture = AdminFixture()
    page.route("**/*", fixture.route)
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(ORIGIN + "/admin/billing")
    expect(page.locator("#bridgeAdminState")).to_have_text("已关闭")
    expect(page.locator("#bridgeAdminUrl")).to_be_hidden()
    expect(page.locator("#bridgeAdminResult")).to_be_hidden()
    expect(page.locator("#bridgeAdminOpen")).to_be_hidden()
    assert "fake-image" not in page.locator(".render-bridge-console").inner_text()
    assert fixture.probes == 0
    page.get_by_role("button", name="检查连接", exact=True).click()
    expect(page.locator("#bridgeAdminHint")).to_contain_text("先点击开启")
    assert fixture.probes == 0
    page.get_by_role("button", name="开启", exact=True).click()
    expect(page.locator("#bridgeAdminState")).to_have_text("已开启，待检查")
    expect(page.locator("#bridgeAdminOpen")).to_have_attribute("href", "/render-bridge-preview")
    expect(page.locator("#bridgeAdminOpen")).to_be_visible()
    assert fixture.saves[0]["mode"] == "enabled" and fixture.saves[0]["profiles"] == ["fake-image"]
    assert fixture.probes == 0
    page.get_by_role("button", name="检查连接", exact=True).click()
    expect(page.locator("#bridgeAdminState")).to_have_text("绘图电脑不在线")
    expect(page.locator("#bridgeAdminHint")).to_contain_text("请打开绘图电脑上的桥接程序")
    expect(page.locator("#bridgeAdminResult")).to_be_hidden()
    assert_independent_cards(page, 24)
    screenshot(page, "admin-desktop.png")
    page.set_viewport_size({"width": 390, "height": 844})
    assert_independent_cards(page, 18)
    screenshot(page, "admin-mobile.png")
    assert page.locator(".render-bridge-console").evaluate("el => el.scrollWidth <= el.clientWidth + 1")
    page.locator("#bridgeAdminAdvanced summary").click()
    expect(page.locator("#bridgeAdminUrl")).to_be_visible()
    expect(page.locator("#bridgeAdminCredential")).to_have_text("已配置 · 不显示密钥")
    assert page.locator("#bridgeAdminForm input[type=password]").count() == 0
    page.get_by_role("button", name="Codex 绘图", exact=True).click()
    expect(page.get_by_role("button", name="Codex 绘图", exact=True)).to_have_attribute("aria-pressed", "true")
    # Unsaved advanced edits cannot silently add a real tool when pausing.
    page.get_by_role("button", name="暂停", exact=True).click()
    expect(page.locator("#bridgeAdminState")).to_have_text("已暂停")
    assert fixture.saves[-1]["mode"] == "draining"
    assert fixture.saves[-1]["profiles"] == ["fake-image"]
    expect(page.locator("#bridgeAdminHint")).to_contain_text("已有任务会继续完成")
    page.get_by_role("button", name="保存高级设置", exact=True).click()
    expect(page.locator("#bridgeAdminHint")).to_contain_text("高级设置已保存")
    page.locator("#bridgeAdminDiagnostics summary").click()
    expect(page.locator("#bridgeAdminResult")).to_be_visible()
    screenshot(page, "admin-advanced-mobile.png")
    page.get_by_role("button", name="关闭", exact=True).click()
    expect(page.locator("#bridgeAdminState")).to_have_text("已关闭")
    expect(page.locator("#bridgeAdminOpen")).to_be_hidden()
    assert fixture.saves[-1]["mode"] == "disabled"
    assert fixture.probes == 1
    assert not fixture.unexpected and not errors
    page.close()


def test_incomplete_setup_offers_plain_language_next_step(browser):
    page = browser.new_page()
    fixture = AdminFixture()
    fixture.value.update(base_url="", workspace="", credential_configured=False)
    page.route("**/*", fixture.route)
    page.goto(ORIGIN + "/admin/billing")
    expect(page.locator("#bridgeAdminState")).to_have_text("还没连接好")
    page.get_by_role("button", name="开启", exact=True).click()
    expect(page.locator("#bridgeAdminHint")).to_have_text("请找管理员完成首次连接，再点击开启。")
    assert not fixture.saves and not fixture.probes
    assert "HTTP" not in page.locator(".render-bridge-console").inner_text()
    screenshot(page, "admin-setup-needed.png")
    page.close()


@pytest.mark.parametrize("status,label", [(401, "请先登录"), (403, "需要管理员权限")])
def test_admin_permissions_leave_controls_disabled(browser, status, label):
    page = browser.new_page()
    fixture = AdminFixture(status)
    page.route("**/*", fixture.route)
    page.goto(ORIGIN + "/admin/billing")
    expect(page.locator("#bridgeAdminState")).to_have_text(label)
    expect(page.locator("#bridgeAdminEnable")).to_be_disabled()
    expect(page.locator("#bridgeAdminProbe")).to_be_disabled()
    expect(page.locator("#bridgeAdminOpen")).to_be_hidden()
    assert not fixture.saves and not fixture.probes and not fixture.unexpected
    page.close()


def test_pending_action_disables_duplicate_clicks(browser):
    page = browser.new_page()
    fixture = AdminFixture()
    fixture.hold_save = True
    page.route("**/*", fixture.route)
    page.goto(ORIGIN + "/admin/billing")
    expect(page.locator("#bridgeAdminState")).to_have_text("已关闭")
    page.get_by_role("button", name="开启", exact=True).click()
    expect(page.locator("#bridgeAdminState")).to_have_text("正在保存…")
    for name in ("开启", "暂停", "关闭", "检查连接"):
        expect(page.get_by_role("button", name=name, exact=True)).to_be_disabled()
    assert len(fixture.saves) == 1
    fixture.pending_save.fulfill(json=fixture.value)
    expect(page.locator("#bridgeAdminState")).to_have_text("已开启，待检查")
    expect(page.get_by_role("button", name="暂停", exact=True)).to_be_enabled()
    page.close()


def test_fallback_toggle_preserves_saved_settings_and_threshold_is_advanced(browser):
    page = browser.new_page(viewport={"width": 390, "height": 844})
    fixture = AdminFixture()
    page.route('**/*', fixture.route)
    page.goto(ORIGIN + '/admin/billing')
    expect(page.locator('#bridgeAdminFallback')).to_be_enabled()
    expect(page.locator('#bridgeAdminFallback')).not_to_be_checked()
    expect(page.locator('#bridgeAdminQueueWait')).to_be_hidden()
    expect(page.locator('.render-bridge-console')).to_contain_text('可能收费')
    page.locator('#bridgeAdminAdvanced summary').click()
    page.locator('#bridgeAdminQueueWait').fill('60')
    page.get_by_role('button', name='Codex 绘图', exact=True).click()
    page.locator('#bridgeAdminFallback').check()
    expect(page.locator('#bridgeAdminHint')).to_contain_text('只影响明确选择此方式的新任务')
    assert fixture.saves[-1]['auto_fallback_enabled'] is True
    assert fixture.saves[-1]['queue_wait_seconds'] == 30
    assert fixture.saves[-1]['profiles'] == ['fake-image']
    assert fixture.saves[-1]['mode'] == 'disabled'
    page.locator('#bridgeAdminQueueWait').fill('60')
    page.get_by_role('button', name='保存高级设置', exact=True).click()
    expect(page.locator('#bridgeAdminHint')).to_contain_text('高级设置已保存')
    assert fixture.saves[-1]['auto_fallback_enabled'] is True
    assert fixture.saves[-1]['queue_wait_seconds'] == 60
    assert_independent_cards(page, 18)
    assert not fixture.probes and not fixture.unexpected
    page.close()


def test_failed_fallback_save_restores_saved_opt_in(browser):
    page = browser.new_page()
    fixture = AdminFixture()
    page.route('**/*', fixture.route)
    page.goto(ORIGIN + '/admin/billing')
    expect(page.locator('#bridgeAdminFallback')).to_be_enabled()
    fixture.status = 403
    page.locator('#bridgeAdminFallback').check()
    expect(page.locator('#bridgeAdminState')).to_have_text('需要管理员权限')
    expect(page.locator('#bridgeAdminFallback')).not_to_be_checked()
    expect(page.locator('#bridgeAdminFallback')).to_be_disabled()
    assert not fixture.saves
    page.close()
