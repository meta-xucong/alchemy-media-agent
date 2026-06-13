from __future__ import annotations

import asyncio
import pytest
import httpx
from fastapi.testclient import TestClient

from app.config import settings
import app.services.veyra_auth as veyra_auth_module
from app.main import app
from app.schemas import CreateImageJobRequest, ImagePromptPlan
import app.services.generation as generation_service
from app.services.veyra_billing_settings import reset_billing_settings_cache
from app.services.veyra_auth import (
    VeyraAuthDisabled,
    VeyraAuthMisconfigured,
    VeyraInsufficientBalance,
    VeyraSub2APIClient,
    VeyraInsufficientBalance,
    VeyraDebitResult,
    issue_session_token,
    verify_session_token,
)


def test_veyra_client_fails_closed_when_disabled() -> None:
    object.__setattr__(settings, "veyra_auth_enabled", False)
    client = VeyraSub2APIClient(base_url="http://sub2api.test", internal_token="secret")

    with pytest.raises(VeyraAuthDisabled):
        client.ensure_enabled()


def test_veyra_client_requires_internal_token_when_enabled() -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", None)
    client = VeyraSub2APIClient(base_url="http://sub2api.test", internal_token=None)

    with pytest.raises(VeyraAuthMisconfigured):
        client.ensure_enabled()


def test_veyra_session_token_round_trip() -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)

    token = issue_session_token(42)

    assert verify_session_token(token) == 42


def test_veyra_http_402_maps_to_insufficient_balance() -> None:
    response = httpx.Response(402, json={"code": 402, "message": "Insufficient balance"})
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")

    with pytest.raises(VeyraInsufficientBalance):
        # Private helper is intentionally exercised here to keep the test network-free.
        from app.services.veyra_auth import _checked_json

        _checked_json(response)


def test_veyra_login_route_disabled() -> None:
    object.__setattr__(settings, "veyra_auth_enabled", False)
    client = TestClient(app)

    response = client.post("/api/v2/veyra/login", json={"ticket": "ticket-1"})

    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "veyra_auth_disabled"


def test_veyra_optional_routes_degrade_when_auth_disabled(tmp_path) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", False)
    object.__setattr__(settings, "image_history_path", tmp_path / "history.jsonl")
    object.__setattr__(settings, "veyra_usage_path", tmp_path / "usage.jsonl")
    settings.image_history_path.write_text(_history_line("out_legacy", None) + "\n", encoding="utf-8")
    settings.veyra_usage_path.write_text(
        '{"user_id":42,"amount":1.5,"balance_after":8.5,"idempotency_key":"a","reference_id":"job_1","created_at":"2026-06-11T00:00:00Z"}\n',
        encoding="utf-8",
    )
    client = TestClient(app)

    policy = client.get("/api/v2/veyra/auth-policy")
    history = client.get("/api/v2/veyra/history?limit=10")
    usage = client.get("/api/v2/veyra/usage?limit=10")
    session_cookie = client.post("/api/v2/veyra/session-cookie")
    me = client.get("/api/v2/veyra/me")

    assert policy.status_code == 200
    assert policy.json()["enabled"] is False
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["output_id"] == "out_legacy"
    assert usage.status_code == 200
    assert usage.json() == {"items": [], "total": 0}
    assert session_cookie.status_code == 200
    assert session_cookie.json()["auth_enabled"] is False
    assert me.status_code == 401
    assert me.json()["detail"]["error_code"] == "veyra_auth_disabled"


def test_veyra_login_and_me_routes(monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "veyra_session_cookie_secure", False)

    async def fake_exchange(self, ticket: str):
        assert ticket == "ticket-1"
        return {"user_id": 42, "intent": "alchemy"}

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="user@example.com", balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "exchange_login_ticket", fake_exchange)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)

    login = client.post("/api/v2/veyra/login", json={"ticket": "ticket-1"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    assert "alchemy_veyra_session" in login.cookies

    me = client.get("/api/v2/veyra/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["user"]["user_id"] == 42
    assert me.json()["user"]["balance"] == 9.5

    cookie_client = TestClient(app)
    synced = cookie_client.post("/api/v2/veyra/session-cookie", headers={"Authorization": f"Bearer {token}"})
    assert synced.status_code == 200
    assert synced.json()["user_id"] == 42
    assert "alchemy_veyra_session" in synced.cookies
    synced_cookie_me = cookie_client.get("/api/v2/veyra/me")
    assert synced_cookie_me.status_code == 200
    assert synced_cookie_me.json()["user"]["user_id"] == 42

    cookie_me = client.get("/api/v2/veyra/me")
    assert cookie_me.status_code == 200
    assert cookie_me.json()["user"]["user_id"] == 42

    logout = client.post("/api/v2/veyra/logout")
    assert logout.status_code == 200
    after_logout = client.get("/api/v2/veyra/me")
    assert after_logout.status_code == 401


def test_veyra_billing_settings_require_admin(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "data_dir", tmp_path)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_generation_charge_amount", 0.25)
    reset_billing_settings_cache()

    async def fake_account(self, user_id: int):
        role = "admin" if user_id == 42 else "user"
        return veyra_auth_module.VeyraAccount(user_id=user_id, email=f"{user_id}@example.com", role=role, balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)
    admin_token = issue_session_token(42)
    user_token = issue_session_token(77)

    rejected = client.post(
        "/api/v2/veyra/billing/settings",
        json={"enabled": False, "charge_amount": 0.1},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert rejected.status_code == 403

    updated = client.post(
        "/api/v2/veyra/billing/settings",
        json={"enabled": False, "charge_amount": 0.1},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False
    assert updated.json()["charge_amount"] == 0.1

    loaded = client.get("/api/v2/veyra/billing/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert loaded.status_code == 200
    assert loaded.json()["persisted"] is True


def test_veyra_billing_settings_support_versioned_rules(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "data_dir", tmp_path)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_generation_charge_amount", 0.25)
    reset_billing_settings_cache()

    async def fake_account(self, user_id: int):
        return veyra_auth_module.VeyraAccount(user_id=user_id, email="admin@example.com", role="admin", balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)
    admin_token = issue_session_token(42)

    updated = client.post(
        "/api/v2/veyra/billing/settings",
        json={
            "rules": [
                {"key": "alchemy:v1", "enabled": True, "charge_amount": 0.15},
                {"key": "alchemy:v2", "enabled": True, "charge_amount": 0.35},
                {"key": "alchemy:v3", "label": "Future Agent", "enabled": False, "charge_amount": 1.25},
            ]
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert updated.status_code == 200
    by_key = {item["key"]: item for item in updated.json()["rules"]}
    assert by_key["alchemy:v1"]["charge_amount"] == 0.15
    assert by_key["alchemy:v2"]["charge_amount"] == 0.35
    assert by_key["alchemy:v3"]["enabled"] is False

    public_v1 = client.get("/api/v2/veyra/billing/settings/public?rule_key=alchemy:v1")
    assert public_v1.status_code == 200
    assert public_v1.json()["charge_amount"] == 0.15


def test_veyra_history_filters_by_session_user(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "image_history_path", tmp_path / "history.jsonl")
    settings.image_history_path.write_text(
        "\n".join(
            [
                _history_line("out_1", 42),
                _history_line("out_2", 77),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    async def fake_account(self, user_id: int):
        return veyra_auth_module.VeyraAccount(user_id=user_id, email=f"{user_id}@example.com", role="user", balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)
    token = issue_session_token(42)

    all_history = client.get("/api/v2/image/history")
    own_history = client.get("/api/v2/veyra/history", headers={"Authorization": f"Bearer {token}"})

    assert all_history.status_code == 401
    assert own_history.status_code == 200
    assert own_history.json()["total"] == 1
    assert own_history.json()["items"][0]["output_id"] == "out_1"


def test_veyra_history_allows_legacy_public_for_signed_in_user(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "image_history_path", tmp_path / "history.jsonl")
    settings.image_history_path.write_text(
        "\n".join(
            [
                _history_line("out_1", 42),
                _history_line("out_2", 77),
                _history_line("out_legacy", None),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    async def fake_account(self, user_id: int):
        return veyra_auth_module.VeyraAccount(user_id=user_id, email=f"{user_id}@example.com", role="user", balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)
    token = issue_session_token(42)

    own_history = client.get("/api/v2/image/history", headers={"Authorization": f"Bearer {token}"})

    assert own_history.status_code == 200
    ids = {item["output_id"] for item in own_history.json()["items"]}
    assert ids == {"out_1", "out_legacy"}
    legacy = next(item for item in own_history.json()["items"] if item["output_id"] == "out_legacy")
    assert legacy["veyra_legacy_public"] is True
    assert legacy["record_label"] == "旧版生图记录"
    assert legacy["metadata"]["record_label"] == "旧版生图记录"
    assert legacy["can_delete"] is False
    own = next(item for item in own_history.json()["items"] if item["output_id"] == "out_1")
    assert own["can_delete"] is True


def test_veyra_history_admin_can_see_all_users(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "image_history_path", tmp_path / "history.jsonl")
    settings.image_history_path.write_text(
        "\n".join(
            [
                _history_line("out_1", 42),
                _history_line("out_2", 77),
                _history_line("out_legacy", None),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    async def fake_account(self, user_id: int):
        return veyra_auth_module.VeyraAccount(user_id=user_id, email="admin@example.com", role="admin", balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)
    token = issue_session_token(1)

    all_history = client.get("/api/v2/image/history", headers={"Authorization": f"Bearer {token}"})

    assert all_history.status_code == 200
    assert all_history.json()["total"] == 3
    assert {item["output_id"]: item["can_delete"] for item in all_history.json()["items"]} == {
        "out_1": True,
        "out_2": True,
        "out_legacy": True,
    }


def test_veyra_history_delete_permissions_enforced(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "image_history_path", tmp_path / "history.jsonl")
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    settings.image_history_path.write_text(
        "\n".join(
            [
                _history_line("out_1", 42),
                _history_line("out_legacy", None),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    async def fake_account(self, user_id: int):
        role = "admin" if user_id == 1 else "user"
        return veyra_auth_module.VeyraAccount(user_id=user_id, email=f"{user_id}@example.com", role=role, balance=9.5, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    client = TestClient(app)
    user_token = issue_session_token(42)
    admin_token = issue_session_token(1)

    public_delete = client.delete("/api/v2/image/history/out_legacy", headers={"Authorization": f"Bearer {user_token}"})
    own_delete = client.delete("/api/v2/image/history/out_1", headers={"Authorization": f"Bearer {user_token}"})
    admin_delete = client.delete("/api/v2/image/history/out_legacy", headers={"Authorization": f"Bearer {admin_token}"})

    assert public_delete.status_code == 403
    assert own_delete.status_code == 200
    assert admin_delete.status_code == 200
    assert settings.image_history_path.read_text(encoding="utf-8").strip() == ""


def test_veyra_usage_filters_by_session_user(tmp_path) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "veyra_usage_path", tmp_path / "usage.jsonl")
    settings.veyra_usage_path.write_text(
        "\n".join(
            [
                '{"user_id":42,"amount":1.5,"balance_after":8.5,"idempotency_key":"a","reference_id":"job_1","created_at":"2026-06-11T00:00:00Z"}',
                '{"user_id":77,"amount":2.5,"balance_after":5.5,"idempotency_key":"b","reference_id":"job_2","created_at":"2026-06-11T00:00:01Z"}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    client = TestClient(app)
    token = issue_session_token(42)

    response = client.get("/api/v2/veyra/usage", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["items"][0]["reference_id"] == "job_1"


def test_veyra_generation_billing_success_records_usage(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_generation_charge_amount", 1.25)
    object.__setattr__(settings, "veyra_usage_path", tmp_path / "usage.jsonl")
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    object.__setattr__(settings, "data_dir", tmp_path)
    reset_billing_settings_cache()

    async def fake_debit(self, *, user_id: int, amount: float, idempotency_key: str, source: str = "alchemy", reference_id: str = ""):
        assert user_id == 42
        assert amount == 1.25
        assert reference_id == "job_bill"
        return VeyraDebitResult(
            user_id=user_id,
            amount=amount,
            balance_after=8.75,
            idempotency_key=idempotency_key,
            replayed=False,
        )

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="user@example.com", balance=10.0, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(plan_id="plan_bill", mode="smart_enhance", prompt="Create a clean product image."),
        provider_hint="mock_image",
        veyra_user_id=42,
    )

    job = asyncio.run(generation_service.create_image_job(request, job_id="job_bill"))

    assert job.status == "completed"
    assert job.outputs[0].metadata["veyra_billing"]["amount"] == 1.25
    assert settings.veyra_usage_path.exists()
    assert "job_bill" in settings.veyra_usage_path.read_text(encoding="utf-8")


def test_veyra_creative_run_requires_session_when_enabled() -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    client = TestClient(app)

    response = client.post("/api/v2/creative/runs", json={"user_prompt": "Create a clean product image."})

    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "veyra_session_required"


def test_veyra_creative_run_session_triggers_billing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "veyra_generation_charge_amount", 0.75)
    object.__setattr__(settings, "veyra_usage_path", tmp_path / "usage.jsonl")
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    object.__setattr__(settings, "claude_orchestrator_enabled", False)
    object.__setattr__(settings, "data_dir", tmp_path)
    reset_billing_settings_cache()

    async def fake_debit(self, *, user_id: int, amount: float, idempotency_key: str, source: str = "alchemy", reference_id: str = ""):
        assert user_id == 42
        assert amount == 0.75
        assert idempotency_key.startswith("alchemy:v2:image:job_")
        assert source == "alchemy:v2"
        assert reference_id.startswith("job_")
        return VeyraDebitResult(
            user_id=user_id,
            amount=amount,
            balance_after=6.25,
            idempotency_key=idempotency_key,
            replayed=False,
        )

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="user@example.com", balance=10.0, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    client = TestClient(app)
    token = issue_session_token(42)

    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a clean product image.", "output": {"provider_hint": "mock_image"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "completed"
    output = run["generation_jobs"][0]["outputs"][0]
    assert output["metadata"]["veyra_user_id"] == 42
    assert output["metadata"]["veyra_billing"]["amount"] == 0.75
    assert "reference_id" not in output["metadata"]["veyra_billing"]
    assert settings.veyra_usage_path.exists()
    assert '"user_id":42' in settings.veyra_usage_path.read_text(encoding="utf-8")


def test_veyra_creative_run_billing_can_be_disabled(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", False)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "veyra_generation_charge_amount", 0.75)
    object.__setattr__(settings, "veyra_usage_path", tmp_path / "usage.jsonl")
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    object.__setattr__(settings, "claude_orchestrator_enabled", False)
    object.__setattr__(settings, "data_dir", tmp_path)
    reset_billing_settings_cache()
    called = False

    async def fake_debit(self, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    client = TestClient(app)
    token = issue_session_token(42)

    response = client.post(
        "/api/v2/creative/runs",
        json={"user_prompt": "Create a clean product image.", "output": {"provider_hint": "mock_image"}},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 202
    assert response.json()["status"] == "completed"
    assert called is False


def test_veyra_direct_image_job_ignores_client_supplied_user_when_disabled(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", False)
    object.__setattr__(settings, "veyra_generation_charge_amount", 5.0)
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    object.__setattr__(settings, "data_dir", tmp_path)
    reset_billing_settings_cache()
    called = False

    async def fake_debit(self, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("billing should not run when Veyra auth is disabled")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    client = TestClient(app)

    response = client.post(
        "/api/v2/image/jobs",
        json={
            "provider_hint": "mock_image",
            "veyra_user_id": 999,
            "prompt_plan": {
                "plan_id": "plan_direct",
                "mode": "smart_enhance",
                "prompt": "Create a clean product image.",
            },
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert body["outputs"][0]["metadata"]["veyra_user_id"] is None
    assert called is False


def test_veyra_direct_image_job_uses_session_user_not_client_user(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_session_secret", "session-secret")
    object.__setattr__(settings, "veyra_session_ttl_seconds", 3600)
    object.__setattr__(settings, "veyra_generation_charge_amount", 1.0)
    object.__setattr__(settings, "veyra_usage_path", tmp_path / "usage.jsonl")
    object.__setattr__(settings, "storage_dir", tmp_path / "storage")
    object.__setattr__(settings, "image_generation_provider", "mock_image")
    object.__setattr__(settings, "data_dir", tmp_path)
    reset_billing_settings_cache()

    async def fake_debit(self, *, user_id: int, amount: float, idempotency_key: str, source: str = "alchemy", reference_id: str = ""):
        assert user_id == 42
        return VeyraDebitResult(
            user_id=user_id,
            amount=amount,
            balance_after=4.0,
            idempotency_key=idempotency_key,
            replayed=False,
        )

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="user@example.com", balance=10.0, status="active")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    client = TestClient(app)
    token = issue_session_token(42)

    response = client.post(
        "/api/v2/image/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider_hint": "mock_image",
            "veyra_user_id": 999,
            "prompt_plan": {
                "plan_id": "plan_direct",
                "mode": "smart_enhance",
                "prompt": "Create a clean product image.",
            },
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "completed"
    assert body["outputs"][0]["metadata"]["veyra_user_id"] == 42


def test_veyra_generation_billing_insufficient_balance_stops_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_generation_charge_amount", 99.0)
    reset_billing_settings_cache()

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="user@example.com", balance=1.0, status="active")

    async def fake_debit(self, **kwargs):
        raise AssertionError("debit should not run when balance precheck fails")

    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(plan_id="plan_low", mode="smart_enhance", prompt="Create a clean product image."),
        provider_hint="mock_image",
        veyra_user_id=42,
    )

    job = asyncio.run(generation_service.create_image_job(request, job_id="job_low"))

    assert job.status == "failed"
    assert job.provider_id == "mock_image"
    assert job.outputs == []
    assert job.error["error_code"] == "veyra_insufficient_balance"
    assert job.error["provider"] == "veyra_billing"
    assert "账户余额不足" in job.error["message"]
    assert job.error["detail"]["reason"] == "user_balance_insufficient"
    assert job.error["retryable"] is False


def test_veyra_generation_provider_failure_does_not_debit(monkeypatch: pytest.MonkeyPatch) -> None:
    object.__setattr__(settings, "veyra_auth_enabled", True)
    object.__setattr__(settings, "veyra_billing_enabled", True)
    object.__setattr__(settings, "veyra_internal_token", "bridge-secret")
    object.__setattr__(settings, "veyra_generation_charge_amount", 1.0)
    object.__setattr__(settings, "allow_mock_fallback", False)
    reset_billing_settings_cache()

    class FailingProvider:
        name = "mock_image"

        async def generate(self, request):
            raise generation_service.V2ImageProviderError("provider failed", provider="mock_image")

    async def fake_get_provider(provider_hint: str | None = None):
        return FailingProvider()

    async def fake_account(self, user_id: int):
        assert user_id == 42
        return veyra_auth_module.VeyraAccount(user_id=42, email="user@example.com", balance=10.0, status="active")

    async def fake_debit(self, **kwargs):
        raise AssertionError("debit should not run when provider generation fails")

    monkeypatch.setattr(generation_service, "get_v2_image_provider", fake_get_provider)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "account", fake_account)
    monkeypatch.setattr(veyra_auth_module.VeyraSub2APIClient, "debit", fake_debit)
    request = CreateImageJobRequest(
        prompt_plan=ImagePromptPlan(plan_id="plan_provider_fail", mode="smart_enhance", prompt="Create a clean product image."),
        provider_hint="mock_image",
        veyra_user_id=42,
    )

    job = asyncio.run(generation_service.create_image_job(request, job_id="job_provider_fail"))

    assert job.status == "failed"
    assert job.outputs == []
    assert job.error["error_code"] == "provider_error"


def _history_line(output_id: str, user_id: int | None) -> str:
    import json

    payload = {
        "output_id": output_id,
        "job_id": "job_" + output_id,
        "run_id": "run_" + output_id,
        "status": "completed",
        "provider_id": "mock_image",
        "model": "mock-image-v2-native",
        "prompt": "prompt",
        "url": "/api/v2/outputs/" + output_id + "/download",
        "metadata": {"native_v2_storage": True, **({"veyra_user_id": user_id} if user_id is not None else {})},
        "created_at": "2026-06-11T00:00:00Z",
        "updated_at": "2026-06-11T00:00:00Z",
    }
    return json.dumps(payload)
