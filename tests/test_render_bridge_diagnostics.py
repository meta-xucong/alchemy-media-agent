"""Read-only diagnostics use bounded wire data, not task or renderer authority."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
import httpx
import pytest

from app.integrations.render_bridge.client import BridgeClient
from app.integrations.render_bridge.routes import PREFIX, install_render_bridge
from app.integrations.render_bridge.settings import BridgeSettings


WRITE = {"X-Alchemy-Bridge-Preview": "1"}


def capabilities():
    return {"schema_version": "1", "profiles": [{
        "execution_profile_id": "codex-image", "execution_profile_revision": "1",
        "operation": "image.generate", "execution_mode": "automatic",
        "validation": "local_validation_pending", "production_verified": False,
        "parameter_contract": {
            "schema_version": "1", "accepted_parameters": ["width", "height", "seed"],
            "required_parameters": ["width", "height"], "dimension_semantics": "exact_output_match",
            "executor_control": "text_instruction_only", "seed_semantics": "text_instruction_only",
            "reference_semantics": "local_image_input_unverified",
            "unsupported_parameters": ["quality", "output_format", "input_fidelity"],
        },
    }]}


def report():
    return {"schema_version": "1", "kind": "render_bridge_doctor",
        "producer": {"name": "alchemy-render-bridge", "version": "0.1.0a1"},
        "outcome": "attention", "profiles": ["codex-image"], "real_generation_verified": False,
        "login_verified": False, "checks": [{"id": "codex_acceptance", "status": "attention",
            "evidence": "operator_declaration", "code": "local_acceptance_not_observed",
            "next_step": "Complete local image capability acceptance; declarations are not measurements."}]}


def application(tmp_path, *, upstream=None, owner=101, config=None):
    app = FastAPI()
    calls = []

    async def respond(request):
        calls.append((request.method, request.url.path))
        assert request.method == "GET" and request.url.path == "/bridge/v1/capabilities"
        assert str(request.url).startswith("https://configured.test/")
        assert request.headers["authorization"] == "Bearer test-private-token"
        if isinstance(upstream, Exception):
            raise upstream
        return httpx.Response(200, json=upstream if upstream is not None else capabilities())

    config = config or BridgeSettings(mode="enabled", base_url="https://configured.test",
        token="test-private-token", workspace="fixture", storage=tmp_path / "bridge", poll_seconds=3600)
    runtime = install_render_bridge(app, session_user=lambda *_: owner, auth_enabled=lambda: True,
        project_snapshot=lambda *_: pytest.fail("diagnostics consulted a project"), config=config,
        client=BridgeClient(config.base_url, config.token, transport=httpx.MockTransport(respond)))
    return app, runtime, calls


def test_load_is_local_only_and_explicit_http_checks_never_authorize(tmp_path):
    app, runtime, calls = application(tmp_path)
    with TestClient(app) as client:
        local = client.get(PREFIX + "/diagnostics")
        assert local.status_code == 200
        value = local.json()
        assert value["source"] == "alchemy_server_configuration"
        assert value["native_profiles"] == ["fake-image"]
        assert value["local_cli"]["status"] == "not_checked"
        assert value["native_real_profile_support"] and not value["real_generation_verified"]
        assert value["native_real_profile_scope"] == "development_review_only"
        assert calls == []
        for _ in range(3):
            response = client.get(PREFIX + "/diagnostics/server", params={"url": "https://ignored.test"})
            assert response.status_code == 200
            result = response.json()
            assert result["connection"] == "ok" and result["source"] == "configured_bridge_http"
            assert result["profiles"][0]["parameter_contract"]["executor_control"] == "text_instruction_only"
            assert not result["real_generation_verified"] and result["native_real_profile_support"]
            assert result["local_cli"]["status"] == "not_checked"
            assert "test-private-token" not in response.text
        assert calls == [("GET", "/bridge/v1/capabilities")] * 3
        with runtime["service"].store.connection() as db:
            for table in ("integration_jobs", "integration_inputs", "integration_receipts"):
                assert db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_older_v1_server_and_unknown_fields_do_not_invent_support(tmp_path):
    value = capabilities()
    item = value["profiles"][0]
    item.pop("parameter_contract")
    item["private_future_field"] = {"token": "do-not-reflect"}
    value["profiles"].append({"execution_profile_id": "future-renderer"})
    app, _, _ = application(tmp_path, upstream=value)
    with TestClient(app) as client:
        response = client.get(PREFIX + "/diagnostics/server")
        assert response.json()["connection"] == "ok"
        assert len(response.json()["profiles"]) == 1
        assert response.json()["profiles"][0]["parameter_contract"] is None
        assert response.json()["profiles"][0]["parameter_contract_state"] == "unavailable"
        assert "do-not-reflect" not in response.text


@pytest.mark.parametrize("change", ["version", "malformed", "outage", "unknown_error"])
def test_server_errors_are_bounded_and_do_not_leak(tmp_path, change):
    value = capabilities()
    if change == "version":
        value["schema_version"] = "2"
    elif change == "malformed":
        value["profiles"] = {"token": "do-not-reflect"}
    elif change == "outage":
        value = httpx.ConnectError("private endpoint and do-not-reflect")
    elif change == "unknown_error":
        value = {"error": {"code": "do-not-reflect"}}
    app, _, _ = application(tmp_path, upstream=value)
    with TestClient(app) as client:
        response = client.get(PREFIX + "/diagnostics/server")
        assert response.status_code == 200
        assert response.json()["connection"] in {"incompatible", "unavailable"}
        assert response.json()["profiles"] == []
        assert "do-not-reflect" not in response.text


def test_unknown_descriptor_version_is_not_advertised_as_support(tmp_path):
    value = capabilities()
    value["profiles"][0]["parameter_contract"]["schema_version"] = "2"
    app, _, _ = application(tmp_path, upstream=value)
    with TestClient(app) as client:
        result = client.get(PREFIX + "/diagnostics/server").json()
        assert result["connection"] == "ok"
        assert result["profiles"][0]["parameter_contract"] is None
        assert result["profiles"][0]["parameter_contract_state"] == "unsupported_or_invalid"


def test_import_is_unverified_projection_not_persistence_or_authority(tmp_path):
    app, runtime, calls = application(tmp_path)
    value = report()
    value["unknown_credential_field"] = "must-be-dropped"
    value["checks"][0]["unknown_field"] = "must-be-dropped"
    value["producer"]["local_path"] = "must-be-dropped"
    with TestClient(app) as client:
        before = list((tmp_path / "bridge").rglob("*"))
        for _ in range(2):
            response = client.post(PREFIX + "/diagnostics/report", json=value, headers=WRITE)
            assert response.status_code == 200
            result = response.json()
            assert result["source"] == "user_imported_local_report"
            assert result["verified_by_server"] is False and result["authorization_effect"] == "none"
            assert result["report"] == report()
            assert "must-be-dropped" not in response.text
        assert calls == []
        assert list((tmp_path / "bridge").rglob("*")) == before
        assert runtime["service"].settings.profiles == ("fake-image",)
        with runtime["service"].store.connection() as db:
            assert db.execute("SELECT COUNT(*) FROM integration_jobs").fetchone()[0] == 0


@pytest.mark.parametrize("change", ["version", "claims_real", "claims_login", "unknown_profile", "too_many_checks", "duplicate_id", "invalid_evidence"])
def test_invalid_report_cannot_be_accepted(tmp_path, change):
    value = report()
    if change == "version":
        value["schema_version"] = "2"
    elif change == "claims_real":
        value["real_generation_verified"] = True
    elif change == "claims_login":
        value["login_verified"] = True
    elif change == "unknown_profile":
        value["profiles"] = ["future-renderer"]
    elif change == "too_many_checks":
        value["checks"] *= 33
    elif change == "duplicate_id":
        value["checks"] *= 2
    elif change == "invalid_evidence":
        value["checks"][0]["evidence"] = "verified_by_server"
    app, _, calls = application(tmp_path)
    with TestClient(app) as client:
        response = client.post(PREFIX + "/diagnostics/report", json=value, headers=WRITE)
        assert response.status_code == 422
        assert response.json() == {"detail": {"code": "invalid_doctor_report"}}
        assert calls == []


def test_report_size_json_and_same_origin_guards(tmp_path):
    app, _, calls = application(tmp_path)
    with TestClient(app) as client:
        assert client.post(PREFIX + "/diagnostics/report", json=report()).status_code == 403
        assert client.post(PREFIX + "/diagnostics/report", json=report(), headers={**WRITE, "Origin": "https://other.test"}).status_code == 403
        response = client.post(PREFIX + "/diagnostics/report", content=b"x" * 65537, headers=WRITE)
        assert response.status_code == 413
        assert client.post(PREFIX + "/diagnostics/report", content="not-json", headers=WRITE).status_code == 422
        assert calls == []


def test_diagnostics_requires_session_and_disabled_mount_is_absent(tmp_path):
    app, _, calls = application(tmp_path, owner=None)
    with TestClient(app) as client:
        assert client.get(PREFIX + "/diagnostics").status_code == 401
        assert client.get(PREFIX + "/diagnostics/server").status_code == 401
        assert client.post(PREFIX + "/diagnostics/report", json=report(), headers=WRITE).status_code == 401
        assert calls == []
    app = FastAPI()
    assert install_render_bridge(app, session_user=None, auth_enabled=None, project_snapshot=None,
                                 config=BridgeSettings()) is None
    with TestClient(app) as client:
        assert client.get(PREFIX + "/diagnostics").status_code == 404
        assert client.get(PREFIX + "/diagnostics/server").status_code == 404
        assert client.post(PREFIX + "/diagnostics/report", json=report(), headers=WRITE).status_code == 404
        assert client.get("/render-bridge-diagnostics").status_code == 404
    assert not (tmp_path / "never-created").exists()


def test_missing_config_remains_explainable_without_outbound_request(tmp_path):
    config = BridgeSettings(mode="enabled", base_url="https://configured.test",
        config_error="bridge_configuration_missing", storage=tmp_path / "never-created")
    app, _, calls = application(tmp_path, config=config)
    with TestClient(app) as client:
        local = client.get(PREFIX + "/diagnostics").json()
        assert local["configuration_error"] == "bridge_configuration_missing"
        response = client.get(PREFIX + "/diagnostics/server")
        assert response.json()["code"] == "bridge_not_available"
        assert response.json()["connection"] == "unavailable"
        assert calls == []
        assert not config.storage.exists()


def test_image_option_descriptor_is_projection_not_runtime_authorization(tmp_path):
    from test_render_bridge_profile_options import descriptor
    value = capabilities()
    contract = descriptor()
    contract['unknown_secret'] = 'never-reflect'
    value['profiles'][0]['image_options_contract'] = contract
    app, runtime, calls = application(tmp_path, upstream=value)
    with TestClient(app) as client:
        response = client.get(PREFIX + '/diagnostics/server')
        item = response.json()['profiles'][0]
        assert item['image_options_contract'] == descriptor()
        assert item['image_options_contract_state'] == 'available'
        assert 'never-reflect' not in response.text
        assert runtime['service'].settings.native_profiles == ('fake-image',)
        assert calls == [('GET','/bridge/v1/capabilities')]
