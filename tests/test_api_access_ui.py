"""Isolated Chrome UI tests using real key HTTP routes, not production accounts."""
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import pytest
from playwright.sync_api import sync_playwright, expect
from test_api_access_keys import native, create, headers

EVIDENCE = Path(os.environ.get("API_ACCESS_TEST_EVIDENCE", ".pytest_cache/api-access-ui"))


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        executable = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
        instance = playwright.chromium.launch(**({"executable_path":str(executable)} if executable.exists() else {}))
        yield instance
        instance.close()


def open_ui(native, browser, *, admin=False, width=1280, token=None, failure=None):
    page = browser.new_page(viewport={"width":width,"height":960})
    token = token if token is not None else ("session-admin" if admin else "session-a")
    page.add_init_script("localStorage.setItem('alchemy_veyra_access_token',"+json.dumps(token)+");")
    calls, errors = [], []
    page.on("pageerror", lambda error:errors.append(str(error)))
    def route_handler(route):
        req=route.request; parsed=urlsplit(req.url)
        assert parsed.hostname == "ui.test", "Unexpected external network request"
        path=parsed.path+("?"+parsed.query if parsed.query else "")
        calls.append((req.method,parsed.path))
        if failure and failure(route,page): return
        if parsed.path.startswith("/api/v2/"):
            route.fulfill(status=200,content_type="application/json",body='{"rules":[]}'); return
        result=native.client.request(req.method,path,headers=req.all_headers(),content=req.post_data)
        route.fulfill(status=result.status_code,body=result.content,
            headers={k:v for k,v in result.headers.items() if k.lower() not in {"content-length","content-encoding"}})
    page.route("**/*",route_handler)
    page.goto("https://ui.test"+("/admin/api-access" if admin else "/api-access"))
    return page,calls,errors


@pytest.mark.parametrize("width",[1280,390])
def test_user_create_native_copy_revoke_and_responsive_layout(native,browser,width):
    page,calls,errors=open_ui(native,browser,width=width)
    try:
        expect(page.locator("#createKeyButton")).to_be_enabled()
        expect(page.locator("#keyList .access-key")).to_have_count(0)
        page.evaluate("document.getElementById('createKeyForm').requestSubmit(); document.getElementById('createKeyForm').requestSubmit();")
        expect(page.locator("#secretDialog")).to_be_visible()
        secret=page.locator("#newSecret").input_value()
        assert secret.startswith("alk_v3_")
        assert len([x for x in calls if x==("POST","/api/access/keys")])==1
        page.click("#copySecret")
        assert page.locator("#manualCopy").input_value()==secret
        assert page.locator("#manualCopy").evaluate("e=>e.selectionEnd-e.selectionStart")==len(secret)
        page.locator("#secretDialog details summary").click()
        page.click("#copyMcp")
        config=json.loads(page.locator("#manualCopy").input_value())
        assert config["env"]["ALCHEMY_PRODUCT_SESSION_TOKEN"]==secret
        assert config["env"]["ALCHEMY_PRODUCT_API_BASE_URL"]=="https://ui.test"
        page.click("#closeSecret")
        expect(page.locator("#secretDialog")).not_to_be_visible()
        assert page.locator("#newSecret").input_value()==""
        assert page.evaluate("JSON.stringify(localStorage)").find(secret)==-1
        assert page.evaluate("JSON.stringify(sessionStorage)").find(secret)==-1
        expect(page.locator(".access-key")).to_have_count(1)
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(EVIDENCE/f"user-{width}.png"),full_page=True)
        page.locator(".access-key button").click()
        page.click("#cancelRevoke")
        assert native.store.list(owner_id=101)["summary"]["active"]==1
        page.locator(".access-key button").click(); page.click("#confirmRevoke")
        expect(page.locator(".access-key .revoked")).to_be_visible()
        assert native.client.get("/api/v3/creative-agent/projects",headers=headers(secret)).status_code==401
        assert not errors,errors
    finally: page.close()


@pytest.mark.parametrize("width",[1280,390])
def test_admin_listing_search_revoke_and_no_plaintext(native,browser,width):
    result=create(native,name="<img src=x onerror=alert(1)>")
    create(native,"session-b","Another")
    page,calls,errors=open_ui(native,browser,admin=True,width=width)
    try:
        expect(page.locator(".access-key")).to_have_count(2)
        expect(page.locator("#createPanel")).not_to_be_visible()
        assert page.locator("#keyList img").count()==0
        assert result["secret"] not in page.content()
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth+1")
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(EVIDENCE/f"admin-{width}.png"),full_page=True)
        page.fill("#keySearch","101"); page.locator("#adminSearch").evaluate("f=>f.requestSubmit()")
        expect(page.locator(".access-key")).to_have_count(1)
        page.locator(".access-key button").click();page.click("#confirmRevoke")
        expect(page.locator(".access-key .revoked")).to_be_visible()
        assert native.store.list(owner_id=101)["summary"]["active"]==0
        assert not errors,errors
    finally:page.close()


def test_expired_login_blocks_creation_with_clear_login_action(native,browser):
    page,_,errors=open_ui(native,browser,token="expired")
    try:
        expect(page.locator("#loginLink")).to_be_visible()
        expect(page.locator("#createKeyButton")).to_be_disabled()
        assert native.store.list(owner_id=None)["total"]==0
        assert not errors
    finally:page.close()


def test_user_cannot_open_admin_data(native,browser):
    create(native,"session-b")
    page,_,errors=open_ui(native,browser,admin=True,token="session-a")
    try:
        expect(page.locator("#accessAlert")).to_be_visible()
        expect(page.locator("#adminSummary")).not_to_be_visible()
        assert page.locator(".access-key").count()==0
        assert not errors
    finally:page.close()


def test_create_failure_is_not_retried_or_shown_as_success(native,browser):
    def failure(route,page):
        if route.request.method=="POST" and urlsplit(route.request.url).path=="/api/access/keys":
            route.fulfill(status=503,content_type="application/json",body='{"detail":{"code":"key_service_unavailable"}}');return True
    page,calls,errors=open_ui(native,browser,failure=failure)
    try:
        expect(page.locator("#createKeyButton")).to_be_enabled();page.click("#createKeyButton")
        expect(page.locator("#accessAlert")).to_be_visible()
        expect(page.locator("#secretDialog")).not_to_be_visible()
        assert len([x for x in calls if x==("POST","/api/access/keys")])==1
        assert native.store.list(owner_id=None)["total"]==0
        assert not errors
    finally:page.close()


@pytest.mark.parametrize("navigation",[False,True])
def test_switch_account_while_creating_does_not_reveal_previous_secret(native,browser,navigation):
    def switch(route,page):
        if route.request.method=="POST" and urlsplit(route.request.url).path=="/api/access/keys":
            if navigation:
                page.evaluate("window.dispatchEvent(new PageTransitionEvent('pagehide'));")
            else:
                page.evaluate("localStorage.removeItem('alchemy_veyra_access_token'); window.dispatchEvent(new StorageEvent('storage',{key:'alchemy_veyra_access_token'}));")
        return False
    page,calls,errors=open_ui(native,browser,failure=switch)
    try:
        expect(page.locator("#createKeyButton")).to_be_enabled();page.click("#createKeyButton")
        if not navigation:
            expect(page.locator("#loginLink")).to_be_visible()
        expect(page.locator("#createKeyButton")).to_be_disabled()
        expect(page.locator("#secretDialog")).not_to_be_visible()
        assert page.locator("#newSecret").input_value()==""
        assert not errors
    finally:page.close()


def test_admin_billing_page_contains_live_key_overview(native,browser):
    create(native)
    page,_,errors=open_ui(native,browser,admin=True)
    try:
        page.goto("https://ui.test/admin/billing")
        expect(page.locator("#apiAdminOverview .access-stat")).to_have_count(3)
        assert page.locator('a[href="/admin/api-access"]').count()==1
        EVIDENCE.mkdir(parents=True,exist_ok=True)
        page.screenshot(path=str(EVIDENCE/"billing-overview.png"),full_page=True)
        assert not errors
    finally:page.close()


@pytest.mark.parametrize("mobile,width",[(True,320),(True,390),(False,1280)])
def test_existing_header_entry_fits_without_loading_business_scripts(browser,mobile,width):
    root=Path(__file__).resolve().parents[1]/"src_skeleton/app"
    folder=root/("mobile_static" if mobile else "static")
    html=(folder/"index.html").read_text(encoding="utf-8")
    header=html[html.index('<header class="lux-header">'):html.index("</header>")+len("</header>")]
    css=(folder/("mobile.css" if mobile else "styles.css")).read_text(encoding="utf-8")
    page=browser.new_page(viewport={"width":width,"height":900})
    page.route("**/*",lambda route:route.abort())
    try:
        page.set_content('<html><head><meta charset="utf-8"><style>'+css+'</style></head><body><div class="app-shell">'+header+'</div></body></html>')
        link=page.locator('a[href="/api-access"]')
        expect(link).to_be_visible()
        box=link.bounding_box()
        assert box["x"]>=0 and box["x"]+box["width"]<=width
        assert page.evaluate("document.documentElement.scrollWidth<=innerWidth+1")
    finally:page.close()
