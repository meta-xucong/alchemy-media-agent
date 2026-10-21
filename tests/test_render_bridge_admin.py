"""Administrator control plane uses fixture transports, never real credentials."""
import json
from dataclasses import replace

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
import httpx
import pytest

from app.integrations.render_bridge.admin import install_render_bridge_admin
from app.integrations.render_bridge.client import BridgeClient
from app.integrations.render_bridge.models import PreviewCreate
from app.integrations.render_bridge.service import PreviewService
from app.integrations.render_bridge.settings import BridgeSettings
from test_render_bridge_preview import payload

BASE = "/v1/admin/render-bridge"
HEADERS = {"X-Alchemy-Bridge-Admin": "1", "Authorization": "Bearer fixture-admin"}
SECRET = "synthetic-secret-never-display"


def fixture(tmp_path, *, upstream=None, baseline=None):
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
    baseline = baseline or BridgeSettings(mode="disabled", base_url="https://bridge.test", token=SECRET,
        workspace="fixture-workspace", storage=tmp_path / "bridge", poll_seconds=3600)
    app = FastAPI()
    app.get("/healthz")(lambda: {"ok": True})
    controller = install_render_bridge_admin(app, baseline=baseline, admin_resolver=admin,
        session_user=lambda *_: 1, auth_enabled=lambda: True,
        project_snapshot=lambda *_: {"revision": "fixture-revision"}, client_factory=factory)
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
    assert (controller.path.parent / "integration.sqlite3").exists()
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
