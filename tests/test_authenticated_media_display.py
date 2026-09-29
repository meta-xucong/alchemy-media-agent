"""Browser contract tests for protected generated-media display.

These tests load the shipped desktop/mobile scripts and exercise the actual
image loader in a browser.  The server side is represented by route fixtures:
protected media requires the current bearer token and cookie, while an
external public image must not receive either credential.
"""

from __future__ import annotations

import base64
from pathlib import Path
import re
import pytest
from playwright.sync_api import Browser, Page, Route, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = [
    ROOT / "src_skeleton" / "app" / "static" / "app.js",
    ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js",
]

_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "YAAAAAYAAjCB0C8AAAAASUVORK5CYII="
)


@pytest.fixture(scope="module")
def browser() -> Browser:
    with sync_playwright() as playwright:
        executable = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        instance = playwright.chromium.launch(
            **({"executable_path": str(executable)} if executable.exists() else {})
        )
        yield instance
        instance.close()


def _open_harness(browser: Browser, script: Path) -> tuple[Page, list[dict[str, str]]]:
    page = browser.new_page()
    requests: list[dict[str, str]] = []

    def route_handler(route: Route) -> None:
        request = route.request
        url = request.url
        headers = {str(key).lower(): str(value) for key, value in request.headers.items()}
        requests.append({"url": url, "authorization": headers.get("authorization", ""), "cookie": headers.get("cookie", "")})
        if url.endswith("/harness"):
            route.fulfill(
                status=200,
                content_type="text/html",
                body="<html><body><img id='media' alt='test' /></body></html>",
            )
            return
        if url.endswith("/missing/preview"):
            route.fulfill(status=401, content_type="application/json", body='{"detail":"unauthorized"}')
            return
        if "/api/v3/creative-agent/outputs/secure/preview" in url:
            assert headers.get("authorization") == "Bearer test-session-token"
            assert "alchemy_veyra_session=cookie-session" in headers.get("cookie", "")
            route.fulfill(status=200, content_type="image/png", body=_PNG)
            return
        if url == "https://cdn.test/public.png":
            assert "authorization" not in headers
            assert "alchemy_veyra_session" not in headers.get("cookie", "")
            route.fulfill(status=200, content_type="image/png", body=_PNG)
            return
        route.abort()

    page.route("**/*", route_handler)
    page.add_init_script("localStorage.setItem('alchemy_veyra_access_token', 'test-session-token');")
    page.context.add_cookies(
        [{"name": "alchemy_veyra_session", "value": "cookie-session", "domain": "ui.test", "path": "/"}]
    )
    page.goto("https://ui.test/harness", wait_until="domcontentloaded")
    page.add_script_tag(content=script.read_text(encoding="utf-8"))
    return page, requests


@pytest.mark.parametrize("script", SCRIPTS, ids=["desktop", "mobile"])
def test_protected_media_uses_authenticated_blob_preview(browser: Browser, script: Path) -> None:
    page, requests = _open_harness(browser, script)
    try:
        page.evaluate(
            """(url) => bindImageWithFallback(document.getElementById('media'), [url])""",
            "/api/v3/creative-agent/outputs/secure/preview",
        )
        page.wait_for_function(
            """() => {
                const image = document.getElementById('media');
                return image.complete && image.naturalWidth > 0 && image.src.startsWith('blob:');
            }"""
        )
        media_request = next(item for item in requests if "/secure/preview" in item["url"])
        assert media_request["authorization"] == "Bearer test-session-token"
        assert "alchemy_veyra_session=cookie-session" in media_request["cookie"]
        assert page.locator("#media").evaluate("image => image.dataset.authenticatedObjectUrl.startsWith('blob:')")
    finally:
        page.close()


@pytest.mark.parametrize("script", SCRIPTS, ids=["desktop", "mobile"])
def test_media_loader_falls_back_after_protected_candidate_failure(browser: Browser, script: Path) -> None:
    page, _requests = _open_harness(browser, script)
    try:
        page.evaluate(
            """(urls) => bindImageWithFallback(document.getElementById('media'), urls)""",
            ["/api/v3/creative-agent/outputs/missing/preview", "/api/v3/creative-agent/outputs/secure/preview"],
        )
        page.wait_for_function(
            """() => {
                const image = document.getElementById('media');
                return image.complete && image.naturalWidth > 0 && image.dataset.fallbackIndex === '1';
            }"""
        )
        assert page.locator("#media").evaluate("image => image.src.startsWith('blob:')")
        assert not page.locator("#media").evaluate("image => image.classList.contains('image-load-failed')")
    finally:
        page.close()


@pytest.mark.parametrize("script", SCRIPTS, ids=["desktop", "mobile"])
def test_external_public_media_does_not_receive_user_credentials(browser: Browser, script: Path) -> None:
    page, requests = _open_harness(browser, script)
    try:
        page.evaluate(
            """(url) => bindImageWithFallback(document.getElementById('media'), [url])""",
            "https://cdn.test/public.png",
        )
        page.wait_for_function("() => document.getElementById('media').naturalWidth > 0")
        public_request = next(item for item in requests if item["url"] == "https://cdn.test/public.png")
        assert public_request["authorization"] == ""
        assert "alchemy_veyra_session" not in public_request["cookie"]
        assert not page.locator("#media").evaluate("image => image.src.startsWith('blob:')")
    finally:
        page.close()


@pytest.mark.parametrize("script", SCRIPTS, ids=["desktop", "mobile"])
def test_media_scripts_keep_auth_loader_contract(script: Path) -> None:
    source = script.read_text(encoding="utf-8")
    assert "function mediaUrlNeedsAuthenticatedFetch" in source
    assert "credentials: \"include\"" in source
    assert "Authorization: `Bearer ${token}`" in source
    assert "URL.createObjectURL(blob)" in source
    assert "URL.revokeObjectURL" in source
    assert "if (!/^\\/(?:api|v1)(?:\\/|$)/.test(parsed.pathname))" in source


@pytest.mark.parametrize("script", SCRIPTS, ids=["desktop", "mobile"])
def test_render_entrypoints_do_not_write_protected_urls_as_inline_src(script: Path) -> None:
    """Guard every shipped renderer against the pre-loader request race.

    A protected URL must first enter bindImageWithFallback(), which performs
    the credentialed fetch and assigns only a Blob URL to the image.  Keeping
    a raw /api or /v1 URL in an inline src would make the browser issue an
    unauthenticated request before the loader can attach credentials.
    """

    source = script.read_text(encoding="utf-8")
    protected_inline_src = re.compile(
        r"src\s*=\s*[\"']?\$\{[^}]*\b(?:previewUrl|thumb|fullImageUrl|displayUrl|preview_url|thumbnail_url|imageUrl|url)\b[^}]*\}[\"']?",
        re.IGNORECASE,
    )
    assert not protected_inline_src.search(source)

    # These are the high-risk output/history surfaces identified by the
    # audit.  Each must route its image through the shared loader.
    renderers = (
        (
            "renderV3History",
            "renderV3ProjectHistoryGrid",
            "renderGallery",
            "renderHistory",
            "renderFavoritePicker",
            "renderRevisionSelection",
        )
        if script.name == "app.js"
        else (
            "renderMobileV3ProjectCards",
            "renderMobileV3ProjectGallery",
            "renderMobileV3ProjectOutputs",
            "renderGallery",
            "renderHistory",
            "renderFavoritePicker",
            "renderRevisionSelection",
        )
    )
    for renderer in renderers:
        assert renderer in source
    assert source.count("bindImageWithFallback") >= 8

    if script.name == "mobile.js":
        assert "[v2ApiBase, v2MediaDisplayBase, mobileV3ApiBase]" in source
