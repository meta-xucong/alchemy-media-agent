"""Account-center UI regression coverage for the desktop and H5 entry points."""

import json
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright

from test_api_access_keys import native

EVIDENCE = Path(os.environ.get("ACCOUNT_CENTER_TEST_EVIDENCE", ".pytest_cache/account-center-ui"))


@pytest.fixture(scope="module")
def account_browser():
    with sync_playwright() as playwright:
        executable = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        browser = playwright.chromium.launch(**({"executable_path": str(executable)} if executable.exists() else {}))
        yield browser
        browser.close()


@pytest.mark.parametrize("mobile", [False, True])
def test_account_center_opens_and_contains_api_mcp(native, account_browser, mobile):
    page = account_browser.new_page(viewport={"width": 390 if mobile else 1280, "height": 960})
    page.add_init_script("localStorage.setItem('alchemy_veyra_access_token','session-a');")
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def route_handler(route):
        request = route.request
        parsed = urlsplit(request.url)
        assert parsed.hostname == "ui.test"
        path = parsed.path + ("?" + parsed.query if parsed.query else "")
        if parsed.path.startswith("/api/v2/"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"items": [], "rules": []}))
            return
        result = native.client.request(
            request.method,
            path,
            headers=request.all_headers(),
            content=request.post_data,
        )
        route.fulfill(
            status=result.status_code,
            body=result.content,
            headers={key: value for key, value in result.headers.items() if key.lower() not in {"content-length", "content-encoding"}},
        )

    page.route("**/*", route_handler)
    try:
        page.goto("https://ui.test/h5" if mobile else "https://ui.test/?desktop=1")
        opener = "#mobileHeaderAccountBtn" if mobile else "#headerAccountBtn"
        page.locator(opener).click()
        if mobile:
            expect(page.locator('[data-mobile-view="account"]')).to_be_visible()
        else:
            expect(page.locator("#accountCenterTitle")).to_be_visible()
            expect(page.locator("#accountOverviewPanel")).to_be_visible()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f"{'h5' if mobile else 'desktop'}-account-overview.png"), full_page=True)

        page.locator("#accountOpenAccessBtn").click()
        expect(page.locator("#accountAccessPanel")).to_be_visible()
        expect(page.locator("#accountAccessState")).to_have_text("已接入")
        expect(page.locator("#accountAccessCreateBtn")).to_be_enabled()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
        page.screenshot(path=str(EVIDENCE / f"{'h5' if mobile else 'desktop'}-api-mcp.png"), full_page=True)

        page.locator("#accountAccessKeyForm").evaluate("form => form.requestSubmit()")
        expect(page.locator("#accountAccessSecretDialog")).to_be_visible()
        secret = page.locator("#accountAccessSecretInput").input_value()
        assert secret.startswith("alk_")
        page.locator("[data-account-access-copy-api]").click()
        api_example = page.locator("#accountAccessManualCopy").input_value()
        assert "/api/v3/creative-agent/projects" in api_example
        assert "/jobs" in api_example
        page.locator("[data-account-access-copy-mcp]").click()
        mcp = json.loads(page.locator("#accountAccessManualCopy").input_value())
        assert mcp["env"]["ALCHEMY_PRODUCT_API_BASE_URL"] == "https://ui.test"
        assert mcp["env"]["ALCHEMY_PRODUCT_SESSION_TOKEN"] == secret
        page.locator("[data-account-access-close-secret]").first.click()
        expect(page.locator("#accountAccessSecretDialog")).not_to_be_visible()
        assert page.locator("#accountAccessSecretInput").input_value() == ""
        assert secret not in page.content()
        assert not errors, errors
    finally:
        page.close()


@pytest.mark.parametrize("mobile", [False, True])
def test_home_only_exposes_account_center_api_mcp_entry(native, account_browser, mobile):
    page = account_browser.new_page(viewport={"width": 390 if mobile else 1280, "height": 900})
    page.add_init_script("localStorage.setItem('alchemy_veyra_access_token','session-a');")

    def route_handler(route):
        request = route.request
        parsed = urlsplit(request.url)
        assert parsed.hostname == "ui.test"
        path = parsed.path + ("?" + parsed.query if parsed.query else "")
        if parsed.path.startswith("/api/v2/"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"items": [], "rules": []}))
            return
        result = native.client.request(request.method, path, headers=request.all_headers(), content=request.post_data)
        route.fulfill(status=result.status_code, body=result.content, headers={key: value for key, value in result.headers.items() if key.lower() not in {"content-length", "content-encoding"}})

    page.route("**/*", route_handler)
    try:
        page.goto("https://ui.test/h5" if mobile else "https://ui.test/?desktop=1")
        expect(page.locator("a[data-account-open='access']")).to_have_count(0)
        page.locator("#mobileHeaderAccountBtn" if mobile else "#headerAccountBtn").click()
        page.locator("#accountOpenAccessBtn").click()
        if mobile:
            expect(page.locator('[data-mobile-view="account"]')).to_be_visible()
        else:
            expect(page.locator("#accountCenterTitle")).to_be_visible()
        expect(page.locator("#accountAccessPanel")).to_be_visible()
        expect(page.locator("#accountAccessState")).to_have_text("已接入")
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
    finally:
        page.close()


@pytest.mark.parametrize("mobile", [False, True])
def test_account_access_accepts_existing_session_cookie(native, account_browser, mobile):
    page = account_browser.new_page(viewport={"width": 390 if mobile else 1280, "height": 900})
    page.context.add_cookies([{"name": "alchemy_veyra_session", "value": "session-a", "domain": "ui.test", "path": "/"}])

    def route_handler(route):
        request = route.request
        parsed = urlsplit(request.url)
        assert parsed.hostname == "ui.test"
        path = parsed.path + ("?" + parsed.query if parsed.query else "")
        if parsed.path.startswith("/api/v2/"):
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"items": [], "rules": []}))
            return
        result = native.client.request(request.method, path, headers=request.all_headers(), content=request.post_data)
        route.fulfill(status=result.status_code, body=result.content, headers={key: value for key, value in result.headers.items() if key.lower() not in {"content-length", "content-encoding"}})

    page.route("**/*", route_handler)
    try:
        page.goto("https://ui.test/h5" if mobile else "https://ui.test/?desktop=1")
        page.locator("#mobileHeaderAccountBtn" if mobile else "#headerAccountBtn").click()
        page.locator("#accountOpenAccessBtn").click()
        expect(page.locator("#accountAccessState")).to_have_text("已接入")
        expect(page.locator("#accountAccessCreateBtn")).to_be_enabled()
    finally:
        page.close()
