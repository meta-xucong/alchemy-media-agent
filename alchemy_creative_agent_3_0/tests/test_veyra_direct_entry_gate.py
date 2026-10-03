"""Regression coverage for unauthenticated direct Alchemy entry points."""

from fastapi.testclient import TestClient


def test_unauthenticated_alchemy_entry_goes_to_login_with_target_callback(monkeypatch) -> None:
    from app import main as app_main

    monkeypatch.setattr(app_main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(app_main.settings, "veyra_require_ui_auth", True)
    monkeypatch.setattr(app_main.settings, "veyra_login_base_url", "https://aiself.vip")

    response = TestClient(app_main.app).get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == (
        "https://aiself.vip/login?redirect=%2F_veyra%2Freturn%3Ftarget%3Dalchemy"
    )


def test_unauthenticated_v3_and_mobile_entries_keep_distinct_return_targets(monkeypatch) -> None:
    from app import main as app_main

    monkeypatch.setattr(app_main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(app_main.settings, "veyra_require_ui_auth", True)
    monkeypatch.setattr(app_main.settings, "veyra_login_base_url", "https://aiself.vip")

    client = TestClient(app_main.app)
    v3 = client.get("/creative-agent-v3?workspace=professional", follow_redirects=False)
    mobile = client.get("/h5", follow_redirects=False)

    assert v3.headers["location"] == (
        "https://aiself.vip/login?redirect=%2F_veyra%2Freturn%3Ftarget%3Dalchemy-v3"
    )
    assert mobile.headers["location"] == (
        "https://aiself.vip/login?redirect=%2F_veyra%2Freturn%3Ftarget%3Dalchemy-mobile"
    )


def test_v2_generation_entry_is_an_alchemy_bootstrap_not_a_sub2api_redirect(monkeypatch) -> None:
    from app import main as app_main

    monkeypatch.setattr(app_main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(app_main.settings, "veyra_require_ui_auth", True)
    client = TestClient(app_main.app)

    response = client.get("/go/v2", follow_redirects=False)

    assert response.status_code == 200
    assert "/static/v2-entry.js?v=" in response.text
    assert "/dashboard" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-security-policy"] == (
        "default-src 'none'; script-src 'self'; base-uri 'none'; frame-ancestors 'none'"
    )

    entry_script = client.get("/static/v2-entry.js")
    assert entry_script.status_code == 200
    assert 'sessionStorage.setItem(pendingModuleRouteKey, "v2")' in entry_script.text
    assert '"/h5?tab=v2" : "/?tab=v2"' in entry_script.text
