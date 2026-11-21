from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect, sync_playwright


@pytest.mark.parametrize("surface", ["static", "mobile_static"])
def test_node_reward_balance_button_and_disabled_withdrawal(surface):
    app_dir = Path(__file__).resolve().parents[2] / "src_skeleton" / "app"
    html = (app_dir / surface / "index.html").read_text(encoding="utf-8")
    script = (app_dir / "static" / "node-rewards.js").read_text(encoding="utf-8")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(service_workers="block")
            posted = []
            pending = []
            credited = False

            def route_request(route):
                request = route.request
                path = urlsplit(request.url).path
                if path == "/api/account/node-rewards":
                    route.fulfill(json={
                        "available": True, "totals": {"reward_points": "0.88"}, "nodes": [],
                        "redemption": {
                            "available": True,
                            "redeemable_points": "0.00" if credited else "0.88",
                            "redeemed_points": "0.88" if credited else "0.00",
                        },
                    })
                elif path == "/api/account/node-rewards/redeem" and request.method == "POST":
                    posted.append(request.post_data_json)
                    pending.append(route)
                else:
                    route.abort()

            page.route("**/*", route_request)
            page.route("https://reward-fixture.test/", lambda route: route.fulfill(status=200, body="<!doctype html>"))
            page.goto("https://reward-fixture.test/")
            page.evaluate("""html => {
                const panel = new DOMParser().parseFromString(html, 'text/html').querySelector('[data-node-rewards]');
                panel.hidden = false;
                document.body.append(panel);
                window.refreshVeyraAccount = async () => { window.walletRefreshed = true };
            }""", html)
            page.add_script_tag(content=script)
            page.evaluate("""document.dispatchEvent(new CustomEvent("alchemy:account-view",
                { detail: {view: "node-rewards"} }))""")
            button = page.locator("#nodeRewardsRedeemBtn")
            expect(button).to_be_enabled()
            expect(page.locator("#nodeRewardsRedeemable")).to_have_text("0.88")
            expect(page.get_by_role("button", name="提现（满 10 积分，暂未开放）")).to_be_disabled()
            with page.expect_request("**/api/account/node-rewards/redeem"):
                button.click()
            expect(button).to_be_disabled()
            assert posted == [{}]
            credited = True
            pending.pop().fulfill(json={"credited_points": "0.88"})
            expect(page.locator("#nodeRewardsRedeemable")).to_have_text("0.00")
            expect(page.locator("#nodeRewardsRedeemed")).to_have_text("0.88")
            expect(page.locator("#nodeRewardsNotice")).to_have_text("已转入 0.88 积分。")
            expect(button).to_be_disabled()
            expect(page.locator("#nodeRewardsPoints")).to_have_text("0.88")
            assert page.evaluate("window.walletRefreshed === true")
        finally:
            browser.close()
