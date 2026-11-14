"""Administrator control plane uses fixture transports, never real credentials."""
import asyncio
import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
import pytest

from app.integrations.render_bridge.admin import AdminSettingsUpdate, install_render_bridge_admin
from app.integrations.render_bridge.client import BridgeClient, BridgeError, BridgeRewardClient
from app.integrations.render_bridge.models import PreviewCreate
from app.integrations.render_bridge.service import PreviewService
from app.integrations.render_bridge.settings import BridgeSettings
from test_render_bridge_preview import payload

BASE = "/v1/admin/render-bridge"
HEADERS = {"X-Alchemy-Bridge-Admin": "1", "Authorization": "Bearer fixture-admin"}
SECRET = "synthetic-secret-never-display"


@pytest.fixture(autouse=True)
def neutral_control_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG", str(tmp_path / "neutral-control" / "control.json"))
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_PRIMARY_STATE_ROOT", str(tmp_path / "neutral-ledgers"))


def fixture(tmp_path, *, upstream=None, baseline=None, reward_factory=None, account_loader=None):
    calls = []
    constructed = []
    def respond(request):
        calls.append((request.method, str(request.url)))
        assert request.method == "GET" and request.url.path == "/bridge/v1/capabilities"
        assert request.headers["authorization"] == "Bearer " + SECRET
        if isinstance(upstream, Exception):
            raise upstream
        return upstream if upstream is not None else httpx.Response(200, json={"schema_version": "1", "profiles": []})
    def factory(base, token):
        constructed.append((base, bool(token)))
        return BridgeClient(base, token, transport=httpx.MockTransport(respond))
    def admin(request, authorization):
        if not authorization:
            raise HTTPException(401)
        if authorization != "Bearer fixture-admin":
            raise HTTPException(403)
        return {"user_id": 7, "is_admin": True}
    baseline = baseline or BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        workspace="fixture-workspace", storage=tmp_path / "bridge", poll_seconds=3600)
    app = FastAPI()
    app.get("/healthz")(lambda: {"ok": True})
    controller = install_render_bridge_admin(app, baseline=baseline, admin_resolver=admin,
        session_user=lambda _request, authorization: (
            int(authorization.removeprefix("Bearer account-"))
            if authorization.startswith("Bearer account-") else 1
        ), auth_enabled=lambda: True,
        project_snapshot=lambda *_: {"revision": "fixture-revision"}, client_factory=factory,
        reward_client_factory=reward_factory or BridgeRewardClient,
        account_loader=account_loader or (lambda user_id: SimpleNamespace(user_id=user_id, status="active")))
    return app, controller, calls, constructed


def settings(**changes):
    return {"mode": "enabled", "base_url": "https://bridge.test", "workspace": "fixture-workspace",
            "profiles": ["fake-image"], "native_enabled": False, "native_profiles": ["fake-image"], **changes}


def test_disabled_control_plane_is_local_and_masked(tmp_path):
    app, controller, calls, constructed = fixture(tmp_path)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get(BASE + "/settings", headers=HEADERS)
        assert response.status_code == 200
        assert SECRET not in response.text
        assert response.json()["credential_configured"] is True
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/api/integrations/render-bridge/v1/status").status_code == 404
        assert client.post(BASE + "/probe", headers=HEADERS).json()["code"] == "bridge_disabled"
    assert not calls and not constructed
    assert not controller.path.parent.exists()


@pytest.mark.parametrize("method,path", [("GET", "/settings"), ("POST", "/settings"), ("POST", "/probe")])
def test_admin_authority_required(tmp_path, method, path):
    app, _, calls, _ = fixture(tmp_path)
    with TestClient(app) as client:
        assert client.request(method, BASE + path).status_code == 401
        assert client.request(method, BASE + path, headers={"Authorization": "Bearer ordinary-user"}).status_code == 403
    assert not calls


def test_reward_metrics_are_admin_only_and_sanitize_bridge_projection(tmp_path):
    calls = []

    class FakeRewardClient:
        async def nodes(self):
            return {"tracking": "since_schema_v5_activation", "tracking_since": "2026-11-12T00:00:00Z",
                "truncated": False, "nodes": [{"pool_id": "pool_fixture", "pool_name": "fixture",
                "node_id": "node_fixture", "executor_instance": "executor_fixture", "provider_ref": "account-17",
                "node_state": "active", "liveness": "online", "heartbeat_age_seconds": 4,
                "profiles": ["fake-image", "private-profile"],
                "current_execution": {"state": "running", "profile": "fake-image",
                                      "started_at": "2026-11-12T00:01:00Z", "task_id": "private-task"},
                "metrics": {"total_started": 3, "succeeded": 1, "failed": 0, "rewardable_images": 2, "private_counter": 999},
                "private_field": SECRET}]}

        async def close(self):
            return None

    def reward_factory(base_url, token):
        calls.append((base_url, token))
        return FakeRewardClient()

    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        reward_read_token="dedicated-reward-reader", workspace="fixture-workspace",
        storage=tmp_path / "bridge")
    app, _, _, _ = fixture(tmp_path, baseline=baseline, reward_factory=reward_factory)
    with TestClient(app) as client:
        assert client.get(BASE + "/rewards").status_code == 401
        response = client.get(BASE + "/rewards", headers=HEADERS)
        assert response.status_code == 200, response.text
        value = response.json()
        assert value["available"] is True
        assert value["nodes"][0]["metrics"] == {"total_started": 3, "succeeded": 1, "failed": 0, "rewardable_images": 2}
        assert value["nodes"][0]["provider_ref"] == "account-17"
        assert value["reward_account_stats_available"] is True
        assert value["reward_totals"] == {"complete": True, "bound_nodes": 0,
            "reward_images": 0, "reward_points": "0.00", "historical_images": 0,
            "historical_points": "0.00", "historical_periods": 0, "pending_nodes": 0}
        assert value["nodes"][0]["reward_account_bound"] is False
        assert value["nodes"][0]["reward_points"] == "0.00"
        assert value["nodes"][0]["profiles"] == ["fake-image"]
        assert "task_id" not in value["nodes"][0]["current_execution"]
        assert "private_field" not in response.text and "private-task" not in response.text
        assert SECRET not in response.text and "dedicated-reward-reader" not in response.text
        assert response.headers["cache-control"] == "no-store"
        app.state.node_reward_account_store.bind_node(17, pool_id="pool_fixture", node_id="node_fixture",
            executor_instance="executor_fixture", baseline_images=1)
        credited = client.get(BASE + "/rewards", headers=HEADERS).json()
        assert credited["nodes"][0]["reward_account_bound"] is True
        assert credited["nodes"][0]["reward_images"] == 1
        assert credited["nodes"][0]["reward_points"] == "0.02"
        assert credited["reward_totals"] == {"complete": True, "bound_nodes": 1,
            "reward_images": 1, "reward_points": "0.02", "historical_images": 0,
            "historical_points": "0.00", "historical_periods": 0, "pending_nodes": 0}
        assert "user_id" not in credited["nodes"][0]
    assert calls == [("https://bridge.test", "dedicated-reward-reader"),
                     ("https://bridge.test", "dedicated-reward-reader")]


def test_admin_binding_correction_preserves_each_account_and_guards_stale_requests(tmp_path):
    nodes = [{"pool_id": "pool_fixture", "pool_name": "fixture",
        "node_id": "node_fixture", "executor_instance": "executor_fixture",
        "provider_ref": None, "node_state": "active", "liveness": "online",
        "heartbeat_age_seconds": 4, "profiles": ["fake-image"], "current_execution": None,
        "metrics": {"total_started": 8, "succeeded": 4, "failed": 0,
                    "rewardable_images": 6}}]

    class FakeRewardClient:
        async def nodes(self):
            return {"tracking_since": "2026-11-12T00:00:00Z", "truncated": False,
                    "nodes": nodes}

        async def close(self):
            return None

    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        reward_read_token="dedicated-reward-reader", workspace="fixture-workspace",
        storage=tmp_path / "bridge")
    app, _, _, _ = fixture(tmp_path, baseline=baseline,
        reward_factory=lambda *_: FakeRewardClient())
    store = app.state.node_reward_account_store
    store.bind_node(17, pool_id="pool_fixture", node_id="node_fixture",
                    executor_instance="executor_fixture", baseline_images=3)
    correction = {"pool_id": "pool_fixture", "node_id": "node_fixture",
        "executor_instance": "executor_fixture", "expected_user_id": 17,
        "expected_revision": 1, "new_user_id": 23}
    write_headers = {**HEADERS, "Origin": "http://testserver"}

    with TestClient(app) as client:
        assert client.post(BASE + "/rewards/bindings/correct", json=correction).status_code == 401
        foreign_origin = client.post(BASE + "/rewards/bindings/correct",
            headers={**write_headers, "Origin": "https://other.test"}, json=correction)
        assert foreign_origin.status_code == 403

        transferred = client.post(BASE + "/rewards/bindings/correct",
                                  headers=write_headers, json=correction)
        assert transferred.status_code == 200, transferred.text
        assert transferred.json() == {"status": "corrected", "revision": 2,
            "former_images": 3, "reward_points": "0.06", "node_id": "node_fixture",
            "image_boundary": 6}
        stale = client.post(BASE + "/rewards/bindings/correct",
                            headers=write_headers, json=correction)
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "node_reward_binding_stale"

        nodes[0]["metrics"]["rewardable_images"] = 8
        old_account = client.get("/api/account/node-rewards",
            headers={"Authorization": "Bearer account-17"}).json()
        assert old_account["totals"] == {"bound_nodes": 0,
            "successful_images": 3, "reward_points": "0.06"}
        assert old_account["nodes"][0]["binding_status"] == "corrected"
        assert old_account["nodes"][0]["successful_images"] == 3

        new_account = client.get("/api/account/node-rewards",
            headers={"Authorization": "Bearer account-23"}).json()
        assert new_account["totals"] == {"bound_nodes": 1,
            "successful_images": 2, "reward_points": "0.04"}
        assert new_account["nodes"][0]["successful_images"] == 2

        admin_value = client.get(BASE + "/rewards", headers=HEADERS).json()
        assert admin_value["nodes"][0]["reward_account_user_id"] == 23
        assert admin_value["nodes"][0]["binding_revision"] == 2
        assert admin_value["nodes"][0]["historical_reward_images"] == 3
        assert admin_value["reward_totals"] == {"complete": True, "bound_nodes": 1,
            "reward_images": 5, "reward_points": "0.10", "historical_images": 3,
            "historical_points": "0.06", "historical_periods": 1, "pending_nodes": 0}

    history = store.list_all_binding_history()
    assert len(history) == 1 and history[0]["corrected_by_admin_user_id"] == 7


@pytest.mark.parametrize("metrics,expected_code,expected_status", [
    ({"available": True, "truncated": True, "nodes": []}, "reward_metrics_incomplete", 503),
    ({"available": True, "truncated": False, "nodes": []}, "reward_node_not_found", 404),
    ({"available": True, "truncated": False, "nodes": [
      {"pool_id": "pool_fixture", "node_id": "node_fixture",
       "executor_instance": "executor_fixture", "metrics": {"rewardable_images": 6}},
      {"pool_id": "pool_fixture", "node_id": "node_fixture",
       "executor_instance": "executor_fixture", "metrics": {"rewardable_images": 6}},
    ]}, "reward_node_ambiguous", 409),
    ({"available": True, "truncated": False, "nodes": [{"pool_id": "pool_fixture",
      "node_id": "node_fixture", "executor_instance": "executor_fixture",
      "metrics": {"rewardable_images": -1}}]}, "reward_image_count_unavailable", 503),
    ({"available": True, "truncated": False, "nodes": [{"pool_id": "pool_fixture",
      "node_id": "node_fixture", "executor_instance": "executor_fixture",
      "metrics": {"rewardable_images": 2}}]}, "node_reward_metrics_regressed", 409),
])
def test_admin_binding_correction_fails_closed_without_complete_image_count(
        tmp_path, metrics, expected_code, expected_status):
    class FakeRewardClient:
        async def nodes(self):
            return metrics

        async def close(self):
            return None

    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        reward_read_token="dedicated-reward-reader", workspace="fixture-workspace",
        storage=tmp_path / "bridge")
    app, _, _, _ = fixture(tmp_path, baseline=baseline,
        reward_factory=lambda *_: FakeRewardClient())
    store = app.state.node_reward_account_store
    store.bind_node(17, pool_id="pool_fixture", node_id="node_fixture",
                    executor_instance="executor_fixture", baseline_images=3)
    correction = {"pool_id": "pool_fixture", "node_id": "node_fixture",
        "executor_instance": "executor_fixture", "expected_user_id": 17,
        "expected_revision": 1, "new_user_id": 23}

    with TestClient(app) as client:
        response = client.post(BASE + "/rewards/bindings/correct",
            headers={**HEADERS, "Origin": "http://testserver"}, json=correction)
        assert response.status_code == expected_status
        assert response.json()["detail"]["code"] == expected_code

    assert store.list_all_bindings()[0]["user_id"] == 17
    assert store.list_all_bindings()[0]["binding_revision"] == 1
    assert store.list_all_binding_history() == []


def test_admin_binding_correction_rejects_inactive_destination_account(tmp_path):
    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        reward_read_token="dedicated-reward-reader", workspace="fixture-workspace",
        storage=tmp_path / "bridge")
    app, _, _, _ = fixture(tmp_path, baseline=baseline,
        account_loader=lambda user_id: SimpleNamespace(user_id=user_id, status="disabled"))
    store = app.state.node_reward_account_store
    store.bind_node(17, pool_id="pool_fixture", node_id="node_fixture",
                    executor_instance="executor_fixture", baseline_images=3)
    correction = {"pool_id": "pool_fixture", "node_id": "node_fixture",
        "executor_instance": "executor_fixture", "expected_user_id": 17,
        "expected_revision": 1, "new_user_id": 23}

    with TestClient(app) as client:
        response = client.post(BASE + "/rewards/bindings/correct",
            headers={**HEADERS, "Origin": "http://testserver"}, json=correction)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "reward_destination_account_unavailable"
    assert store.list_all_bindings()[0]["user_id"] == 17
    assert store.list_all_bindings()[0]["binding_revision"] == 1
    assert store.list_all_binding_history() == []


def test_admin_binding_correction_rejects_missing_legacy_baseline_without_writes(tmp_path):
    class FakeRewardClient:
        async def nodes(self):
            return {"available": True, "truncated": False, "nodes": [{
                "pool_id": "pool_fixture", "node_id": "node_fixture",
                "executor_instance": "executor_fixture",
                "metrics": {"rewardable_images": 6}}]}

        async def close(self):
            return None

    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        reward_read_token="dedicated-reward-reader", workspace="fixture-workspace",
        storage=tmp_path / "bridge")
    app, _, _, _ = fixture(tmp_path, baseline=baseline,
        reward_factory=lambda *_: FakeRewardClient())
    store = app.state.node_reward_account_store
    store.bind_node(17, pool_id="pool_fixture", node_id="node_fixture",
                    executor_instance="executor_fixture", baseline_images=3)
    with store._connect() as con:
        con.execute("UPDATE node_reward_node_bindings SET baseline_images=NULL "
                    "WHERE pool_id=? AND node_id=? AND executor_instance=?",
                    ("pool_fixture", "node_fixture", "executor_fixture"))
    correction = {"pool_id": "pool_fixture", "node_id": "node_fixture",
        "executor_instance": "executor_fixture", "expected_user_id": 17,
        "expected_revision": 1, "new_user_id": 23}

    with TestClient(app) as client:
        response = client.post(BASE + "/rewards/bindings/correct",
            headers={**HEADERS, "Origin": "http://testserver"}, json=correction)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "node_reward_baseline_unavailable"
    binding = store.list_all_bindings()[0]
    assert binding["user_id"] == 17 and binding["binding_revision"] == 1
    assert binding["baseline_images"] is None
    assert store.list_all_binding_history() == []


def test_mutation_and_probe_require_same_origin_guard(tmp_path):
    app, _, calls, _ = fixture(tmp_path)
    with TestClient(app) as client:
        for path in ("/settings", "/probe"):
            assert client.post(BASE + path, headers={"Authorization": HEADERS["Authorization"]}, json=settings()).status_code == 403
            assert client.post(BASE + path, headers={**HEADERS, "Origin": "https://other.test"}, json=settings()).status_code == 403
    assert not calls


def test_enable_drain_disable_restart_and_explicit_probe(tmp_path):
    app, controller, calls, _ = fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings())
        assert response.status_code == 200, response.text
        assert response.json()["runtime_active"] is True
        assert not calls
        assert client.get("/api/integrations/render-bridge/v1/status").json()["mode"] == "enabled"
        probe = client.post(BASE + "/probe", headers=HEADERS).json()
        assert probe["connection"] == "reachable" and probe["authentication"] == "accepted"
        assert probe["node_readiness"] == "unknown" and probe["real_generation_verified"] is False
        assert len(calls) == 1
        old = controller.application.state.render_bridge_preview["service"]
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(mode="draining"))
        assert response.status_code == 200 and old.worker.done()
        assert client.get("/api/integrations/render-bridge/v1/status").json()["mode"] == "draining"
        assert client.post(BASE + "/settings", headers=HEADERS, json=settings(mode="disabled")).status_code == 200
        assert controller.application is None
        assert client.get("/api/integrations/render-bridge/v1/status").status_code == 404
    persisted = controller.path.read_text()
    assert SECRET not in persisted and '"token"' not in persisted
    assert (controller.config.storage / "integration.sqlite3").exists()
    app, _, calls, constructed = fixture(tmp_path)
    with TestClient(app) as client:
        assert client.get(BASE + "/settings", headers=HEADERS).json()["persisted"] is True
    assert not calls and not constructed


def test_pending_jobs_block_scope_change_but_not_pause(tmp_path):
    app, controller, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        assert client.post(BASE + "/settings", headers=HEADERS, json=settings()).status_code == 200
        svc = controller.application.state.render_bridge_preview["service"]
        client.portal.call(svc.create, "1", PreviewCreate(**payload()))
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(workspace="different"))
        assert response.status_code == 409
        assert client.post(BASE + "/settings", headers=HEADERS, json=settings(mode="disabled")).status_code == 200
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(mode="disabled", native_enabled=True))
        assert response.status_code == 409
        assert controller.pending_count() == 1


@pytest.mark.parametrize("changes,code", [
    ({"base_url": "https://wrong.test"}, "credential_endpoint_mismatch"),
    ({"base_url": "https://user:secret@bridge.test"}, "invalid_bridge_url"),
    ({"base_url": "http://bridge.test"}, "invalid_bridge_url"),
    ({"profiles": ["fake-image", "fake-image"]}, "invalid_profiles"),
    ({"profiles": ["fake-image"], "native_enabled": True, "native_profiles": ["codex-image"]}, "invalid_native_profiles"),
])
def test_invalid_settings_do_not_activate_or_persist(tmp_path, changes, code):
    app, controller, calls, constructed = fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(**changes))
        assert response.status_code == 422 and response.json()["detail"]["code"] == code
    assert not calls and not constructed and not controller.path.exists()


def test_docker_desktop_host_relay_requires_loopback_opt_in(monkeypatch):
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_MODE", "enabled")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_URL", "http://host.docker.internal:8798")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_TOKEN", "fixture")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", "workspace")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_PROFILES", "codex-image")
    monkeypatch.delenv("ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK", raising=False)
    assert BridgeSettings.from_env().config_error == "invalid_bridge_url"
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK", "true")
    assert BridgeSettings.from_env().config_error is None


def test_admin_accepts_docker_desktop_host_relay_only_with_loopback_opt_in(tmp_path, monkeypatch):
    baseline = BridgeSettings(mode="disabled", base_url="http://host.docker.internal:8798",
                              token=SECRET, workspace="fixture-workspace", storage=tmp_path / "bridge")
    _, controller, _, _ = fixture(tmp_path, baseline=baseline)
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_URL", "http://host.docker.internal:8798")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", "fixture-workspace")
    monkeypatch.delenv("ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK", raising=False)
    with pytest.raises(ValueError, match="invalid_bridge_url"):
        controller.validate(AdminSettingsUpdate.model_validate(settings(base_url="http://host.docker.internal:8798")))
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_ALLOW_HTTP_LOOPBACK", "true")
    assert controller.validate(AdminSettingsUpdate.model_validate(settings(base_url="http://host.docker.internal:8798"))).base_url == "http://host.docker.internal:8798"
    with pytest.raises(ValueError, match="invalid_bridge_url"):
        controller.validate(AdminSettingsUpdate.model_validate(settings(base_url="http://host.docker.internal:bad")))


@pytest.mark.parametrize("upstream,expected", [
    (httpx.Response(401, json={"error": {"code": "no_access"}}), ("reachable", "rejected", "not_checked")),
    (httpx.Response(200, json={"schema_version": "999", "profiles": []}), ("reachable", "accepted", "incompatible")),
    (httpx.ConnectError("secret upstream text"), ("unavailable", "not_checked", "not_checked")),
])
def test_probe_distinguishes_auth_protocol_and_connection(tmp_path, upstream, expected):
    app, _, _, _ = fixture(tmp_path, upstream=upstream)
    with TestClient(app) as client:
        client.post(BASE + "/settings", headers=HEADERS, json=settings())
        response = client.post(BASE + "/probe", headers=HEADERS)
        value = response.json()
        assert tuple(value[k] for k in ("connection", "authentication", "capabilities")) == expected
        assert SECRET not in response.text and "secret upstream text" not in response.text
        assert value["real_generation_verified"] is False


def test_advertised_node_readiness_is_separate_evidence(tmp_path):
    upstream = httpx.Response(200, json={"schema_version": "1", "profiles": [],
        "node_status": {"state": "offline", "real_generation_verified": True, "secret": SECRET},
        "admission": {"accepting_new_tasks": False, "mode": "draining"}})
    app, _, _, _ = fixture(tmp_path, upstream=upstream)
    with TestClient(app) as client:
        client.post(BASE + "/settings", headers=HEADERS, json=settings())
        response = client.post(BASE + "/probe", headers=HEADERS)
        assert response.json()["connection"] == "reachable"
        assert response.json()["node_readiness"] == "offline"
        assert response.json()["admission"]["accepting_new_tasks"] is False
        assert response.json()["real_generation_verified"] is False
        assert SECRET not in response.text


def test_bad_saved_settings_fail_closed(tmp_path):
    app, controller, calls, constructed = fixture(tmp_path)
    controller.path.parent.mkdir()
    controller.path.write_text("not json")
    with TestClient(app) as client:
        value = client.get(BASE + "/settings", headers=HEADERS).json()
        assert value["mode"] == "disabled" and value["configuration_error"] == "invalid_saved_bridge_settings"
    assert not calls and not constructed


def test_initialization_failure_is_reported_without_breaking_host(tmp_path):
    app, controller, calls, _ = fixture(tmp_path)
    with TestClient(app) as client:
        def broken(*args):
            raise OSError("private filesystem info")
        controller.client_factory = broken
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings())
        assert response.status_code == 200
        assert response.json()["runtime_active"] is False
        assert response.json()["configuration_error"] == "bridge_initialization_failed"
        assert "private filesystem" not in response.text
        assert client.get("/healthz").status_code == 200
        assert client.post(BASE + "/settings", headers=HEADERS, json=settings(mode="disabled")).status_code == 200
    assert not calls


def test_native_page_actual_path_is_dispatched(tmp_path):
    app, _, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        assert client.get("/render-bridge-native-test").status_code == 404
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(native_enabled=True))
        assert response.status_code == 200
        assert client.get("/render-bridge-native-test").status_code == 200
        assert client.get("/render-bridge-native-test/assets/native.js").status_code == 200


def test_attention_projection_uses_curated_messages_and_legacy_support():
    from app.integrations.render_bridge.attention import attention_projection
    detail = attention_projection({"action_required_detail": {"code": "insufficient_disk", "message": SECRET}})
    assert detail["code"] == "insufficient_disk" and SECRET not in detail["message"]
    assert attention_projection({"action_required": "import_original"})["code"] == "import_original"
    assert attention_projection({"action_required_detail": {"code": "unknown", "message": SECRET}}) is None
    assert attention_projection({"action_required_detail": {"code": []}}) is None


def test_reward_claim_lookup_uses_fixed_path_and_digest_header():
    digest = "a" * 64
    calls = []

    def respond(request):
        calls.append(request)
        return httpx.Response(200, json={"pool_id": "pool_1", "node_id": "node_1",
            "executor_instance": "executor_1", "node_state": "active",
            "rewardable_images": 4, "pool_name": "Fixture"})

    client = BridgeRewardClient("https://bridge.test", "reward-reader",
                                transport=httpx.MockTransport(respond))
    try:
        value = asyncio.run(client.claim_approval(digest))
    finally:
        asyncio.run(client.close())
    assert value["node_id"] == "node_1"
    assert len(calls) == 1
    request = calls[0]
    assert request.method == "GET"
    assert request.url.path == "/bridge/rewards/v1/claim-approval"
    assert request.url.query == b""
    assert request.headers["x-reward-claim-digest"] == digest
    assert request.headers["authorization"] == "Bearer reward-reader"
    assert request.content == b""


def test_reward_claim_lookup_rejects_malformed_digest_without_request():
    calls = []
    client = BridgeRewardClient("https://bridge.test", "reward-reader",
                                transport=httpx.MockTransport(lambda request: calls.append(request)))
    try:
        with pytest.raises(BridgeError):
            asyncio.run(client.claim_approval("bad-digest"))
    finally:
        asyncio.run(client.close())
    assert calls == []


def test_reward_claim_approval_uses_reader_credential_and_whitelists_fields(tmp_path):
    digest = "b" * 64
    calls = []

    class FakeRewardClient:
        async def claim_approval(self, supplied_digest):
            calls.append((supplied_digest,))
            return {"pool_id": "pool_1", "node_id": "node_1",
                "executor_instance": "executor_1", "node_state": "active",
                "rewardable_images": 8, "pool_name": "Fixture",
                "private_field": "must-not-escape"}

        async def close(self):
            return None

    def factory(base_url, token):
        calls.append((base_url, token))
        return FakeRewardClient()

    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test",
        token="control-secret", reward_read_token="reader-secret",
        workspace="fixture-workspace", storage=tmp_path / "bridge")
    app, controller, _, _ = fixture(tmp_path, baseline=baseline, reward_factory=factory)
    result = asyncio.run(controller.reward_claim_approval(digest))
    assert calls[0] == ("https://bridge.test", "reader-secret")
    assert calls[1] == (digest,)
    assert result == {"available": True, "pool_id": "pool_1", "node_id": "node_1",
        "executor_instance": "executor_1", "node_state": "active",
        "rewardable_images": 8, "pool_name": "Fixture"}
    assert "control-secret" not in repr(calls)
    assert "reader-secret" not in repr(result)
    assert "must-not-escape" not in repr(result)


def test_attention_projection_includes_codex_timeout_but_not_remote_text():
    from app.integrations.render_bridge.attention import attention_projection

    projected = attention_projection({"action_required_detail": {
        "code": "codex_turn_timed_out", "message": "untrusted remote text",
    }})
    assert projected["code"] == "codex_turn_timed_out"
    assert "600 秒" in projected["message"]
    assert "untrusted remote text" not in projected["message"]


def test_invalid_additive_readiness_does_not_break_legacy_probe(tmp_path):
    upstream = httpx.Response(200, json={"schema_version": "1", "profiles": [],
        "node_status": {"state": []}, "admission": {"accepting_new_tasks": True, "mode": []}})
    app, _, _, _ = fixture(tmp_path, upstream=upstream)
    with TestClient(app) as client:
        client.post(BASE + "/settings", headers=HEADERS, json=settings())
        response = client.post(BASE + "/probe", headers=HEADERS)
        assert response.status_code == 200
        assert response.json()["node_readiness"] == "unknown"
        assert response.json()["admission"] is None


def test_settings_validation_never_echoes_submitted_secret(tmp_path):
    app, _, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(token=SECRET))
        assert response.status_code == 422 and SECRET not in response.text


def test_invalid_environment_url_does_not_expose_embedded_credentials(tmp_path):
    baseline = BridgeSettings(mode="disabled", base_url="https://user:private@bridge.test", token=SECRET,
                              storage=tmp_path / "bridge", config_error="invalid_bridge_url")
    app, _, _, constructed = fixture(tmp_path, baseline=baseline)
    with TestClient(app) as client:
        response = client.get(BASE + "/settings", headers=HEADERS)
        assert response.json()["base_url"] == "" and "private" not in response.text
    assert not constructed


def test_fallback_defaults_and_persistence_are_opt_in(tmp_path):
    app, controller, calls, _ = fixture(tmp_path)
    with TestClient(app) as client:
        value = client.get(BASE + '/settings', headers=HEADERS).json()
        assert value['auto_fallback_enabled'] is False
        assert value['queue_wait_seconds'] == 30
        response = client.post(BASE + '/settings', headers=HEADERS,
            json=settings(mode='disabled', auto_fallback_enabled=True, queue_wait_seconds=45))
        assert response.status_code == 200
        assert response.json()['auto_fallback_enabled'] is True
        assert response.json()['queue_wait_seconds'] == 45
    app, controller, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        value = client.get(BASE + '/settings', headers=HEADERS).json()
        assert value['auto_fallback_enabled'] is True and value['queue_wait_seconds'] == 45
        # Older callers cannot opt requests into cloud generation by omission.
        value = client.post(BASE + '/settings', headers=HEADERS, json=settings(mode='disabled')).json()
        assert value['auto_fallback_enabled'] is False and value['queue_wait_seconds'] == 30
    assert not calls


@pytest.mark.parametrize('changes', [
    {'queue_wait_seconds': 0}, {'queue_wait_seconds': 3601}, {'queue_wait_seconds': 2.5},
    {'queue_wait_seconds': True}, {'queue_wait_seconds': '30'}, {'auto_fallback_enabled': 'true'},
])
def test_fallback_settings_strictly_validate(tmp_path, changes):
    app, controller, calls, _ = fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(BASE + '/settings', headers=HEADERS, json=settings(**changes))
        assert response.status_code == 422
    assert not controller.path.exists() and not calls


def test_primary_control_is_neutral_and_legacy_config_migrates(tmp_path):
    app, controller, calls, _ = fixture(tmp_path)
    controller.legacy_path.parent.mkdir(parents=True)
    controller.legacy_path.write_text(json.dumps(settings(profiles=["codex-image"])), encoding="utf-8")
    with TestClient(app) as client:
        state = client.get(BASE + "/settings", headers=HEADERS).json()
        assert state["primary_routing_active"] is True
        assert state["primary_routing_policy"] == "bridge_primary_nonadmission_only_v1"
        assert controller.path != controller.legacy_path
        value = json.loads(controller.path.read_text(encoding="utf-8"))
        assert value["mode"] == "enabled" and value["profiles"] == ["codex-image"]
        assert value["schema_version"] == "1"
        assert value["profile"] == "codex-image"
        assert SECRET not in controller.path.read_text(encoding="utf-8")
    assert not calls


def test_fake_only_settings_do_not_activate_product_codex(tmp_path):
    app, _, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        state = client.post(BASE + "/settings", headers=HEADERS, json=settings()).json()
        assert state["primary_routing_active"] is False


def test_primary_pending_blocks_scope_change_but_allows_pause(tmp_path, monkeypatch):
    import app.integrations.render_bridge.admin as admin
    app, _, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        assert client.post(BASE + "/settings", headers=HEADERS, json=settings()).status_code == 200
        monkeypatch.setattr(admin, "primary_pending_count", lambda _: 1)
        refused = client.post(BASE + "/settings", headers=HEADERS, json=settings(profiles=["codex-image"]))
        assert refused.status_code == 409
        paused = client.post(BASE + "/settings", headers=HEADERS, json=settings(mode="draining"))
        assert paused.status_code == 200
        assert paused.json()["primary_routing_active"] is False


def test_invalid_neutral_control_does_not_restore_old_enabled_settings(tmp_path):
    app, controller, calls, constructed = fixture(tmp_path)
    controller.legacy_path.parent.mkdir(parents=True)
    controller.legacy_path.write_text(json.dumps(settings(profiles=["codex-image"])), encoding="utf-8")
    controller.path.parent.mkdir(parents=True)
    controller.path.write_text('{"schema_version":"unknown"}', encoding="utf-8")
    with TestClient(app) as client:
        state = client.get(BASE + "/settings", headers=HEADERS).json()
        assert state["mode"] == "disabled"
        assert state["primary_routing_active"] is False
        assert state["configuration_error"] == "invalid_saved_bridge_settings"
    assert not calls and not constructed


def test_enabled_environment_publishes_neutral_control_without_token(tmp_path):
    baseline = BridgeSettings(mode="enabled", base_url="https://bridge.test", token=SECRET,
        workspace="fixture-workspace", storage=tmp_path / "bridge", profiles=("codex-image",), poll_seconds=3600)
    app, controller, _, _ = fixture(tmp_path, baseline=baseline)
    with TestClient(app):
        value = json.loads(controller.path.read_text(encoding="utf-8"))
        assert value["mode"] == "enabled" and value["profiles"] == ["codex-image"]
        assert "token" not in value and SECRET not in controller.path.read_text(encoding="utf-8")


def test_admin_workspace_matches_neutral_credential_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", "fixture-workspace")
    app, controller, _, _ = fixture(tmp_path)
    with TestClient(app) as client:
        response = client.post(BASE + "/settings", headers=HEADERS, json=settings(workspace="different-workspace"))
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "credential_workspace_mismatch"
        assert not controller.path.exists()


def test_disabled_mode_still_reconciles_owned_primary_ack_and_cancel_intents(tmp_path, monkeypatch):
    import asyncio
    import app.integrations.render_bridge.admin as admin
    app, controller, _, _ = fixture(tmp_path)
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_TOKEN", SECRET)
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_URL", "https://bridge.test")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", "fixture-workspace")
    admin.state_root().mkdir(parents=True)
    controller._write_control(settings(mode="disabled", profiles=["codex-image"]))
    observed = []
    class MaintenanceOnly:
        def __init__(self, config):
            assert config.enabled is False
            self.product = config.state_dir.name
        async def reconcile_pending(self, *, limit):
            observed.append((self.product, limit))
        async def close(self):
            pass
    monkeypatch.setattr(admin, "PrimaryTransport", MaintenanceOnly)
    monkeypatch.setattr(admin, "primary_pending_count", lambda _: 1)
    asyncio.run(controller.maintain_primary_once())
    assert observed == [(name, 32) for name in ("v1", "lab", "v2", "v3")]


def test_no_primary_state_means_no_maintenance_transport(tmp_path, monkeypatch):
    import asyncio
    import app.integrations.render_bridge.admin as admin
    _, controller, _, _ = fixture(tmp_path)
    monkeypatch.setattr(admin, "PrimaryTransport", lambda _: pytest.fail("unexpected transport"))
    asyncio.run(controller.maintain_primary_once())


def test_account_node_binding_waits_for_bridge_approval_and_uses_proved_identity(tmp_path):
    approval = {"confirmed": False}
    digests = []

    def reward_response(request):
        assert request.method == "GET"
        assert request.url.path == "/bridge/rewards/v1/claim-approval"
        digest = request.headers["x-reward-claim-digest"]
        assert len(digest) == 64
        digests.append(digest)
        if not approval["confirmed"]:
            return httpx.Response(404, json={"error": {"code": "claim_approval_not_found"}})
        return httpx.Response(200, json={
            "pool_id": "pool_proved",
            "node_id": "node_proved",
            "executor_instance": "executor_proved",
            "node_state": "active",
            "rewardable_images": 7,
            "pool_name": "Proved node",
        })

    def reward_factory(base_url, token):
        assert base_url == "https://bridge.test"
        assert token == "dedicated-reward-reader"
        return BridgeRewardClient(base_url, token,
                                  transport=httpx.MockTransport(reward_response))

    baseline = BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        reward_read_token="dedicated-reward-reader", workspace="fixture-workspace",
        storage=tmp_path / "bridge")
    app, _, _, _ = fixture(tmp_path, baseline=baseline, reward_factory=reward_factory)
    headers = {"Authorization": "Bearer fixture-account", "Origin": "http://testserver",
               "X-Alchemy-UI": "node-rewards"}
    with TestClient(app) as client:
        created = client.post("/api/account/node-rewards/claims", headers=headers, json={})
        assert created.status_code == 200, created.text
        assert "node_id" not in created.json()
        challenge = created.json()["challenge"]
        digest = hashlib.sha256(challenge.encode("ascii")).hexdigest()

        waiting = client.post("/api/account/node-rewards/bindings", headers=headers,
                              json={"challenge": challenge})
        assert waiting.status_code == 503
        assert waiting.json()["detail"]["code"] == "node_reward_claim_unverified"
        assert app.state.node_reward_account_store.list_all_bindings() == []

        approval["confirmed"] = True
        bound = client.post("/api/account/node-rewards/bindings", headers=headers,
                            json={"challenge": challenge})
        assert bound.status_code == 200, bound.text
        assert bound.json()["node_id"] == "node_proved"
        assert digests == [digest, digest]
        binding = app.state.node_reward_account_store.list_all_bindings()[0]
        assert (binding["pool_id"], binding["node_id"], binding["executor_instance"],
                binding["baseline_images"]) == (
            "pool_proved", "node_proved", "executor_proved", 7)
