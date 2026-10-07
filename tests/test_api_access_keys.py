"""Real key lifecycle against original HTTP auth with isolated account fixtures."""
from concurrent.futures import ThreadPoolExecutor
import io
import json
import sqlite3
from types import SimpleNamespace
from urllib.error import HTTPError
import pytest
from fastapi.testclient import TestClient
from app.services.api_keys import ApiKeyStore, KeyAccessError


@pytest.fixture
def native(tmp_path, monkeypatch):
    import app.main as main
    import app.api_access as access
    from app.services.veyra_auth import VeyraAccount, VeyraAuthUnauthorized
    clock = [2000000000.0]
    store = ApiKeyStore(tmp_path / "keys.sqlite3", clock=lambda: clock[0])
    monkeypatch.setattr(access, "key_store", lambda: store)
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", True)
    states = {101: "active", 202: "active", 999: "active"}
    def verify(token):
        if token not in {"session-a", "session-b", "session-admin"}:
            raise VeyraAuthUnauthorized("invalid")
        return {"session-a": 101, "session-b": 202, "session-admin": 999}[token]
    async def account(owner):
        return VeyraAccount(user_id=owner, email=f"user{owner}@example.test",
            role="admin" if owner == 999 else "user", balance=10, status=states[owner])
    monkeypatch.setattr(main, "verify_session_token", verify)
    monkeypatch.setattr(main, "load_account", account)
    calls = []
    def projects(limit, owner, cursor, view):
        calls.append(owner)
        return {"items": [], "owner": owner}
    monkeypatch.setattr(main.v3_route_handlers, "get_projects", projects)
    client = TestClient(main.app, base_url="https://ui.test")
    return SimpleNamespace(client=client, store=store, clock=clock, states=states, main=main, calls=calls)


def headers(token="session-a", *, write=False):
    return {"Authorization": "Bearer " + token, **({"X-Alchemy-UI": "api-access", "Origin": "https://ui.test"} if write else {})}


def create(native, token="session-a", name="Test key"):
    response = native.client.post("/api/access/keys", headers=headers(token, write=True), json={"name": name})
    assert response.status_code == 200, response.text
    return response.json()


def test_complete_key_lifecycle_and_no_plaintext_persistence(native):
    result = create(native)
    key, secret = result["key"], result["secret"]
    assert native.store.resolve(secret)["owner_id"] == 101
    assert secret.encode() not in native.store.path.read_bytes()
    listed = native.client.get("/api/access/keys", headers=headers())
    assert listed.status_code == 200
    assert listed.headers["cache-control"] == "no-store"
    assert secret not in listed.text and "digest" not in listed.text
    response = native.client.get("/api/v3/creative-agent/projects", headers=headers(secret))
    assert response.status_code == 200 and response.json()["owner"] == 101
    assert native.calls == [101]
    item = native.store.list(owner_id=101)["items"][0]
    assert item["request_count"] == 1 and item["last_used_at"]
    revoked = native.client.post(f"/api/access/keys/{key['id']}/revoke", headers=headers(write=True))
    assert revoked.status_code == 200 and revoked.json()["key"]["status"] == "revoked"
    assert native.client.get("/api/v3/creative-agent/projects", headers=headers(secret)).status_code == 401
    assert native.calls == [101]


def test_key_defaults_to_permanent_and_optional_expiry_is_enforced(native):
    permanent = create(native)
    assert permanent["key"]["expires_at"] is None
    assert permanent["key"]["status"] == "active"
    capabilities = native.client.get("/api/access/capabilities", headers=headers()).json()
    assert capabilities["default_lifetime_days"] is None
    assert capabilities["available_lifetime_days"] == [30, 90, 180, 365]
    native.clock[0] += 20 * 365 * 86400
    assert native.store.resolve(permanent["secret"])["owner_id"] == 101

    finite = native.client.post(
        "/api/access/keys",
        headers=headers(write=True),
        json={"name": "Finite", "expires_in_days": 30},
    )
    assert finite.status_code == 200, finite.text
    assert finite.json()["key"]["expires_at"] is not None
    assert finite.json()["key"]["status"] == "active"
    native.clock[0] += 30 * 86400
    assert native.client.get("/api/v3/creative-agent/projects", headers=headers(finite.json()["secret"])).status_code == 401


def test_admin_can_read_and_delete_foreign_v3_projects_but_cannot_archive_them(native, monkeypatch, tmp_path):
    captured = {}

    def projects(limit, owner, cursor, view):
        captured["project_owner"] = owner
        return {"projects": [], "owner": owner}

    def outputs(*args, **kwargs):
        owner = kwargs.get("owner_user_id", args[1] if len(args) > 1 else None)
        captured["output_owner"] = owner
        return {"items": [], "owner": owner}

    monkeypatch.setattr(native.main.v3_route_handlers, "get_projects", projects)
    monkeypatch.setattr(native.main.v3_route_handlers, "get_project_outputs", outputs)
    monkeypatch.setattr(native.main.v3_route_handlers, "get_history", lambda _limit, owner: {"owner": owner})
    history = native.client.get("/api/v3/creative-agent/history", headers=headers("session-admin"))
    assert history.status_code == 200 and history.json()["owner"] is None
    assert native.client.get("/api/v3/creative-agent/projects", headers=headers("session-admin")).status_code == 200
    assert captured["project_owner"] is None
    assert native.client.get("/api/v3/creative-agent/project-outputs", headers=headers("session-admin")).status_code == 200
    assert captured["output_owner"] is None

    monkeypatch.setattr(native.main, "_v3_project_owner_id", lambda _project_id: 101)
    monkeypatch.setattr(native.main.v3_route_handlers, "get_project", lambda project_id, owner_user_id, view: {
        "project": {"project_id": project_id, "job_ids": []},
        "owner_user_id": owner_user_id,
    })
    project = native.client.get("/api/v3/creative-agent/projects/foreign-project", headers=headers("session-admin"))
    assert project.status_code == 200, project.text
    assert project.json()["owner_user_id"] is None
    assert native.client.get("/api/v3/creative-agent/projects/foreign-project", headers=headers("session-b")).status_code == 404
    assert native.client.post("/api/v3/creative-agent/projects/foreign-project/archive", headers=headers("session-admin")).status_code == 404

    deleted = []
    monkeypatch.setattr(native.main.v3_route_handlers, "delete_project", lambda project_id: deleted.append(project_id) or {
        "project_id": project_id, "deleted": True,
    })
    admin_delete = native.client.delete("/api/v3/creative-agent/projects/foreign-project", headers=headers("session-admin"))
    assert admin_delete.status_code == 200, admin_delete.text
    assert admin_delete.json()["deleted"] is True
    assert deleted == ["foreign-project"]
    denied_delete = native.client.delete("/api/v3/creative-agent/projects/foreign-project", headers=headers("session-b"))
    assert denied_delete.status_code == 404
    assert deleted == ["foreign-project"]

    image = tmp_path / "foreign.png"
    image.write_bytes(b"image")
    monkeypatch.setattr(native.main, "_v3_output_owner_id", lambda _output_id: 202)
    monkeypatch.setattr(native.main.v3_output_store, "file_for_variant", lambda *_args: (image, "image/png", "foreign.png"))
    image_response = native.client.get("/api/v3/creative-agent/outputs/foreign-output/preview", headers=headers("session-admin"))
    assert image_response.status_code == 200
    assert image_response.content == b"image"
    assert native.client.get("/api/v3/creative-agent/outputs/foreign-output/preview", headers=headers("session-a")).status_code == 404

    monkeypatch.setattr(native.main, "_v3_uploaded_asset_owner_id", lambda _asset_id: 202)
    monkeypatch.setattr(native.main.v3_route_handlers, "get_upload", lambda asset_id: {"asset_id": asset_id})
    assert native.client.get("/api/v3/creative-agent/uploads/foreign-asset", headers=headers("session-admin")).status_code == 200
    assert native.client.get("/api/v3/creative-agent/uploads/foreign-asset", headers=headers("session-a")).status_code == 404

    monkeypatch.setattr(native.main, "_v3_job_owner_id", lambda _job_id: 202)
    monkeypatch.setattr(native.main.v3_route_handlers, "get_job", lambda job_id: {"job_id": job_id, "metadata": {}})
    assert native.client.get("/api/v3/creative-agent/jobs/foreign-job", headers=headers("session-admin")).status_code == 200
    assert native.client.get("/api/v3/creative-agent/jobs/foreign-job", headers=headers("session-a")).status_code == 404


def test_admin_can_read_foreign_slot_delivery_projections(native, monkeypatch):
    monkeypatch.setattr(native.main, "_v3_project_owner_id", lambda _project_id: 101)
    monkeypatch.setattr(
        native.main.v3_route_handlers,
        "get_project_ecommerce_slot_delivery",
        lambda project_id, job_id, slot_id: {"project_id": project_id, "slot_id": slot_id},
    )
    monkeypatch.setattr(
        native.main.v3_route_handlers,
        "get_project_photography_role_delivery",
        lambda project_id, job_id, role_id: {"project_id": project_id, "role_id": role_id},
    )

    ecommerce = native.client.get(
        "/api/v3/creative-agent/projects/foreign-project/jobs/root-job/ecommerce-slots/hero/delivery",
        headers=headers("session-admin"),
    )
    photography = native.client.get(
        "/api/v3/creative-agent/projects/foreign-project/jobs/root-job/photography-roles/portrait/delivery",
        headers=headers("session-admin"),
    )
    assert ecommerce.status_code == 200, ecommerce.text
    assert photography.status_code == 200, photography.text
    assert native.client.get(
        "/api/v3/creative-agent/projects/foreign-project/jobs/root-job/ecommerce-slots/hero/delivery",
        headers=headers("session-b"),
    ).status_code == 404


def test_admin_can_read_cross_account_visual_asset_library(native, monkeypatch):
    captured = {}
    monkeypatch.setattr(
        native.main.v3_route_handlers,
        "get_visual_assets_for_admin",
        lambda: {"visual_assets": [{"visual_asset_id": "asset-from-another-user"}]},
    )
    monkeypatch.setattr(
        native.main.v3_route_handlers,
        "get_visual_asset_for_admin",
        lambda asset_id: {"visual_asset": {"visual_asset_id": asset_id}},
    )
    monkeypatch.setattr(
        native.main.v3_route_handlers,
        "get_visual_assets",
        lambda owner_scope: captured.update(owner_scope=owner_scope) or {"visual_assets": []},
    )

    admin_list = native.client.get("/api/v3/creative-agent/visual-assets", headers=headers("session-admin"))
    admin_detail = native.client.get(
        "/api/v3/creative-agent/visual-assets/asset-from-another-user",
        headers=headers("session-admin"),
    )
    assert admin_list.status_code == 200
    assert admin_list.json()["visual_assets"][0]["visual_asset_id"] == "asset-from-another-user"
    assert admin_detail.status_code == 200
    assert admin_detail.json()["visual_asset"]["visual_asset_id"] == "asset-from-another-user"

    user_list = native.client.get("/api/v3/creative-agent/visual-assets", headers=headers("session-b"))
    assert user_list.status_code == 200
    assert captured["owner_scope"] == "v3_user_202"


def test_admin_job_read_does_not_start_foreign_auto_generation(native, monkeypatch):
    monkeypatch.setattr(native.main, "_v3_job_owner_id", lambda _job_id: 202)
    monkeypatch.setattr(
        native.main.v3_route_handlers,
        "get_job",
        lambda job_id: {"job_id": job_id, "metadata": {"project_id": "foreign-project"}},
    )
    recovered = []
    monkeypatch.setattr(
        native.main,
        "_recover_v3_planned_auto_generation",
        lambda project_id, status: recovered.append((project_id, status)) or status,
    )

    admin = native.client.get("/api/v3/creative-agent/jobs/foreign-job", headers=headers("session-admin"))
    assert admin.status_code == 200, admin.text
    assert recovered == []

    owner = native.client.get("/api/v3/creative-agent/jobs/foreign-job", headers=headers("session-b"))
    assert owner.status_code == 200, owner.text
    assert len(recovered) == 1


@pytest.mark.parametrize("method,path", [("GET","/api/access/keys"),("POST","/api/access/keys"),
    ("GET","/api/access/admin/keys"),("GET","/v1/admin/retention/settings"),
    ("GET","/api/v3/creative-agent/mcp-materializations/handoff"),
    ("POST","/api/v3/creative-agent/visual-assets"),("POST","/api/v2/veyra/login")])
def test_keys_cannot_manage_credentials_admin_or_handoff(native, method, path):
    key = create(native, "session-admin")["secret"]
    assert native.client.request(method,path,headers=headers(key,write=True),json={}).status_code == 403


def test_old_session_still_calls_product_routes(native):
    assert native.client.get("/api/v3/creative-agent/projects",headers=headers()).json()["owner"] == 101


def test_unified_key_exposes_capabilities_and_allowed_legacy_surfaces(native, monkeypatch):
    key = create(native)["secret"]
    capabilities = native.client.get("/api/access/capabilities", headers=headers(key))
    assert capabilities.status_code == 200
    body = capabilities.json()
    assert body["surfaces"] == ["lab", "v1", "v2", "v3"]
    assert "alchemy_v1_create_image_job" in body["mcp"]["v1"]
    captured = {}

    async def fake_proxy(path, request):
        captured["path"] = path
        captured["user_id"] = request.state.alchemy_api_user_id
        captured["surfaces"] = request.state.alchemy_api_key_surfaces
        from fastapi.responses import JSONResponse
        return JSONResponse({"ok": True})

    monkeypatch.setattr(native.main, "_proxy_v2_request", fake_proxy)
    response = native.client.get("/api/v2/image/history", headers=headers(key))
    assert response.status_code == 200 and response.json() == {"ok": True}
    assert captured == {"path": "image/history", "user_id": 101, "surfaces": ["lab", "v1", "v2", "v3"]}


def test_old_v3_key_row_does_not_gain_new_surfaces(native):
    old_token = "alk_v3_" + "A" * 43
    import hashlib
    with native.store._db() as db:
        db.execute(
            "INSERT INTO access_keys (id,owner_id,name,digest,masked,created_at,expires_at) VALUES (?,?,?,?,?,?,?)",
            ("key_old", 101, "old", hashlib.sha256(old_token.encode()).hexdigest(), "alk_v3_A...AAAA", native.clock[0], native.clock[0] + 86400),
        )
    assert native.store.resolve(old_token)["surfaces"] == ["v3"]
    assert native.client.get("/api/access/capabilities", headers=headers(old_token)).json()["surfaces"] == ["v3"]
    assert native.client.get("/api/lab/modules", headers=headers(old_token)).status_code == 403


@pytest.mark.parametrize("token", ["bad", "", "session-expired"])
def test_bad_session_cannot_create_keys(native, token):
    response = native.client.post("/api/access/keys", headers=headers(token,write=True),json={})
    assert response.status_code == 401
    assert native.store.list(owner_id=None)["total"] == 0


def test_foreign_key_and_admin_boundaries(native):
    result = create(native)
    assert native.client.get("/api/access/keys",headers=headers("session-b")).json()["items"] == []
    assert native.client.get("/api/access/admin/keys",headers=headers()).status_code == 403
    assert native.client.post(f"/api/access/keys/{result['key']['id']}/revoke",headers=headers("session-b",write=True)).status_code == 404
    admin = native.client.get("/api/access/admin/keys",headers=headers("session-admin"))
    assert admin.status_code == 200 and result["secret"] not in admin.text
    assert admin.json()["items"][0]["owner_id"] == 101
    revoked = native.client.post(f"/api/access/admin/keys/{result['key']['id']}/revoke", headers=headers("session-admin",write=True))
    assert revoked.status_code == 200
    assert native.client.get("/api/v3/creative-agent/projects",headers=headers(result["secret"])).status_code == 401


def test_inactive_account_and_expiry_are_enforced(native):
    result = native.client.post(
        "/api/access/keys",
        headers=headers(write=True),
        json={"name": "Expires", "expires_in_days": 90},
    ).json()
    native.states[101] = "disabled"
    assert native.client.get("/api/v3/creative-agent/projects",headers=headers(result["secret"])).status_code == 403
    assert native.client.post("/api/access/keys",headers=headers(write=True),json={}).status_code == 403
    native.states[101] = "active"
    native.clock[0] += 90*86400
    assert native.client.get("/api/v3/creative-agent/projects",headers=headers(result["secret"])).status_code == 401
    assert native.store.list(owner_id=101)["items"][0]["status"] == "expired"


def test_disabled_login_never_turns_key_into_anonymous_access(native, monkeypatch):
    key = create(native)["secret"]
    monkeypatch.setattr(native.main.settings,"veyra_auth_enabled",False)
    assert native.client.get("/api/v3/creative-agent/projects",headers=headers(key)).status_code == 503
    assert native.client.post("/api/access/keys",headers=headers(write=True),json={}).status_code == 503
    assert native.calls == []


@pytest.mark.parametrize("origin", ["https://evil.test", "null", "https://ui.test.evil.test"])
def test_cross_origin_cannot_create_or_revoke(native, origin):
    auth = headers(write=True); auth["Origin"] = origin
    assert native.client.post("/api/access/keys",headers=auth,json={}).status_code == 403
    assert native.store.list(owner_id=None)["total"] == 0


def test_cookie_session_management_requires_ui_write_header(native):
    native.client.cookies.set(native.main.settings.veyra_session_cookie_name,"session-a")
    assert native.client.post("/api/access/keys",json={}).status_code == 403
    assert native.client.post("/api/access/keys",headers={"X-Alchemy-UI":"api-access","Origin":"https://ui.test"},json={}).status_code == 200


def test_keys_do_not_grant_other_accounts_jobs(native, monkeypatch):
    key = create(native)["secret"]
    monkeypatch.setattr(native.main.v3_route_handlers.service, "get_job_record",
        lambda job_id: SimpleNamespace(request=SimpleNamespace(metadata={"veyra_user_id":202})))
    assert native.client.get("/api/v3/creative-agent/jobs/job_foreign",headers=headers(key)).status_code == 404


def test_key_limit_is_transactional(native):
    def attempt(_):
        try: native.store.create(101,"Concurrent"); return True
        except KeyAccessError as exc: assert exc.code == "active_key_limit"; return False
    native.store.list(owner_id=101)
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt,range(12))) == 5
    assert native.store.list(owner_id=101)["summary"]["active"] == 5


def test_revocation_checked_after_account_lookup(native):
    result = create(native)
    identity = native.store.resolve(result["secret"])
    native.store.revoke(identity["id"],owner_id=101,actor_id=101)
    with pytest.raises(KeyAccessError): native.store.record_use(identity["id"])


@pytest.mark.parametrize("body", [{"owner_id":202},{"name":"x"*51},{"name":"bad\nname"},{"name":1},{"expires_in_days":45}])
def test_creation_does_not_accept_owner_or_invalid_names(native, body):
    assert native.client.post("/api/access/keys",headers=headers(write=True),json=body).status_code in {400,422}
    assert native.store.list(owner_id=None)["total"] == 0


def test_admin_search_is_literal_and_paginated(native):
    create(native, name="100%_name")
    create(native,"session-b",name="another")
    result = native.client.get("/api/access/admin/keys?q=%25_",headers=headers("session-admin"))
    assert result.status_code == 200, result.text
    assert result.json()["total"] == 1
    assert native.client.get("/api/access/admin/keys?q=202",headers=headers("session-admin")).json()["total"] == 1


def test_mcp_adapter_uses_new_key_without_login_or_billing_fork(native):
    from services.alchemy_codex_local_adapter.product_tools import ProductTools
    key = create(native)["secret"]
    class Opener:
        def open(self, request, timeout):
            response = native.client.request(request.method,request.full_url,headers=dict(request.header_items()),content=request.data)
            if response.status_code >= 400:
                raise HTTPError(request.full_url,response.status_code,"test",response.headers,io.BytesIO(response.content))
            return io.BytesIO(response.content)
    tools = ProductTools("https://ui.test",key,opener=Opener())
    # A real authenticated HTTP call, not a key-shaped test session.
    tools._request("GET","/projects?view=summary")
    assert native.calls == [101]


def test_storage_failure_returns_safe_message(native, monkeypatch):
    import app.api_access as access
    class Broken:
        def list(self, **kwargs): raise sqlite3.OperationalError("private-db-path")
    monkeypatch.setattr(access,"key_store",lambda:Broken())
    result = native.client.get("/api/access/keys",headers=headers())
    assert result.status_code == 503 and "private-db-path" not in result.text


def test_key_and_session_use_identical_existing_async_generation_entry(native, monkeypatch):
    key=create(native)["secret"]
    seen=[]
    monkeypatch.setattr(native.main,"_v3_project_owner_id",lambda project_id:101)
    monkeypatch.setattr(native.main.v3_route_handlers,"begin_project_planning_operation",
        lambda project_id,payload:{"operation_id":"operation_same","state":"planning"})
    monkeypatch.setattr(native.main,"_start_v3_project_planning_background",
        lambda project_id,operation,payload,auto: seen.append((project_id,operation,payload,auto)) or True)
    body={"user_input":"One silver product photo", "metadata":{"veyra_user_id":202},
          "auto_generate":{"quality_mode":"standard","metadata":{"require_real_images":True}}}
    for credential in ["session-a",key]:
        response=native.client.post("/api/v3/creative-agent/projects/project_owned/jobs",headers=headers(credential),json=body)
        assert response.status_code==200
        assert response.json()["metadata"]["current_operation"]["operation_id"]=="operation_same"
    assert len(seen)==2 and seen[0]==seen[1]
    assert seen[0][2]["metadata"]["veyra_user_id"]==101
    assert seen[0][3]["metadata"]["veyra_user_id"]==101


def test_invalid_key_never_falls_back_to_valid_cookie(native):
    native.client.cookies.set(native.main.settings.veyra_session_cookie_name,"session-a")
    response=native.client.get("/api/v3/creative-agent/projects",headers=headers("alk_v3_"+"A"*43))
    assert response.status_code==401 and native.calls==[]


def test_account_bridge_failure_does_not_allow_key_through(native,monkeypatch):
    from app.services.veyra_auth import VeyraAuthError
    key=create(native)["secret"]
    async def unavailable(owner): raise VeyraAuthError("private bridge address")
    monkeypatch.setattr(native.main,"load_account",unavailable)
    response=native.client.get("/api/v3/creative-agent/projects",headers=headers(key))
    assert response.status_code==502
    assert native.calls==[] and "private bridge" not in response.text
