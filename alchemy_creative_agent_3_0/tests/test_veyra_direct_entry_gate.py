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
