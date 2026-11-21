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
            unbound = False

            def route_request(route):
                nonlocal unbound
                request = route.request
                path = urlsplit(request.url).path
                if path == "/api/account/node-rewards":
                    route.fulfill(json={
                        "available": True, "totals": {"reward_points": "0.88"},
                        "nodes": [{
                            "pool_id": "pool_1", "node_id": "node_1", "executor_instance": "executor_1",
                            "binding_status": "unbound" if unbound else "active",
                            "binding_revision": 1, "reward_points": "0.88", "successful_images": 44,
                        }],
                        "redemption": {
                            "available": True,
                            "redeemable_points": "0.00" if credited else "0.88",
                            "redeemed_points": "0.88" if credited else "0.00",
                        },
                    })
                elif path == "/api/account/node-rewards/redeem" and request.method == "POST":
                    posted.append(request.post_data_json)
                    pending.append(route)
                elif path == "/api/account/node-rewards/receipts":
                    route.fulfill(json={"items": [{
                        "created_at": "2026-11-21T10:19:00Z", "amount": "0.88", "balance_after": "346.63383546",
                    }], "next_before_redeemed_images": None})
                elif path == "/api/account/node-rewards/unbind" and request.method == "POST":
                    assert request.post_data_json == {
                        "pool_id": "pool_1", "node_id": "node_1", "executor_instance": "executor_1",
                        "binding_revision": 1,
                    }
                    unbound = True
                    route.fulfill(json={"status": "unbound"})
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
            expect(page.locator(".node-rewards-policy")).to_contain_text("奖励积分可转入账户余额")
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
            page.get_by_text("转入记录", exact=True).click()
            expect(page.locator("#nodeRewardsReceiptList")).to_contain_text("入账后余额 346.63383546")
            page.on("dialog", lambda dialog: dialog.accept())
            page.get_by_role("button", name="解绑节点").click()
            expect(page.locator("#nodeRewardsNotice")).to_have_text("已解绑，历史奖励已保留。")
            expect(page.get_by_text("已解绑", exact=True)).to_be_visible()
            expect(page.locator("#nodeRewardsPoints")).to_have_text("0.88")
        finally:
            browser.close()
