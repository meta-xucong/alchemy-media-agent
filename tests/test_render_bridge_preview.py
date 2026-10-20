"""Wire-only fixture: no Bridge package, real provider, native output or usage."""
import asyncio
import base64
from dataclasses import replace
from io import BytesIO
import json
import time

import httpx
from PIL import Image
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.integrations.render_bridge.client import BridgeClient, BridgeError
from app.integrations.render_bridge.models import PreviewCreate
from app.integrations.render_bridge.routes import install_render_bridge, PREFIX
from app.integrations.render_bridge.service import PreviewService
from app.integrations.render_bridge.settings import BridgeSettings
from app.integrations.render_bridge.store import PreviewStore


def png():
    out = BytesIO()
    Image.new("RGB", (32, 32), "green").save(out, format="PNG")
    return out.getvalue()


class MockBridge:
    def __init__(self):
        self.calls, self.tasks, self.inputs, self.acks = [], {}, {}, []
        self.ready = True
        self.lose_create = False
        self.lose_input = False
        self.outage = False
        self.wrong_hash = False
        self.wrong_binding = False
        self.slow = None
        self.content = png()

    async def __call__(self, request):
        path = request.url.path.removeprefix("/bridge/v1/")
        self.calls.append((request.method, path))
        assert request.headers["authorization"] == "Bearer fixture-secret"
        if self.outage:
            raise httpx.ConnectError("private URL or secret must not leak", request=request)
        if self.slow:
            await self.slow.wait()
        body = json.loads(request.content) if request.content and request.headers.get("content-type") == "application/json" else None
        if path == "capabilities":
            return httpx.Response(200, json={"schema_version": "1", "profiles": [{
                "execution_profile_id": "fake-image", "execution_profile_revision": "1", "operation": "image.generate",
                "limits": {"max_output_bytes": 1048576, "max_image_pixels": 1048576, "max_dimension": 1024}}]})
        if path == "inputs":
            item = self.inputs.setdefault(body["input_key"], {**body, "input_id": f"in_{len(self.inputs)}", "state": "pending"})
            if self.lose_input:
                self.lose_input = False
                raise httpx.ReadError("lost input response", request=request)
            return httpx.Response(200, json=item)
        if path.startswith("inputs/"):
            item = next(item for item in self.inputs.values() if item["input_id"] == path.split("/")[1])
            item["state"] = "ready"
            return httpx.Response(200, json=item)
        if path == "tasks":
            self.tasks.setdefault(body["origin_key"], {"remote_task_id": f"task_{len(self.tasks)}", "origin_key": body["origin_key"],
                "request": body, "attempt_id": "attempt_1", "state": "queued", "receipt_id": None})
            if self.lose_create:
                self.lose_create = False
                raise httpx.ReadError("lost create response", request=request)
            return httpx.Response(200, json=self.tasks[body["origin_key"]])
        if path.startswith("tasks/by-origin/"):
            task = self.tasks.get(path.split("/")[-1])
            return httpx.Response(200, json=task) if task else httpx.Response(404, json={"error": {"code": "not_found"}})
        if path.startswith("tasks/"):
            task = next(item for item in self.tasks.values() if item["remote_task_id"] == path.split("/")[1])
            if path.endswith("/cancel"):
                if not task["receipt_id"]:
                    task["state"] = "canceled"
            elif self.ready:
                task.update(state="artifacts_ready", receipt_id="receipt_1")
            return httpx.Response(200, json=task)
        if path.endswith("/ack"):
            self.acks.append(body)
            return httpx.Response(200, json={"delivery_ack": body["decision"]})
        if path.startswith("receipts/"):
            import hashlib
            task = next(iter(self.tasks.values()))
            return httpx.Response(200, json={"receipt_id": "receipt_1", "task_id": "wrong" if self.wrong_binding else task["remote_task_id"],
                "attempt_id": "attempt_1", "slot_id": "primary", "execution_profile_id": "fake-image",
                "execution_profile_revision": "1", "artifact_id": "artifact_1", "original_sha256": "0"*64 if self.wrong_hash else hashlib.sha256(self.content).hexdigest(),
                "size": len(self.content), "mime_type": "image/png", "dimensions": {"width": 32, "height": 32}, "delivery_ack": "pending"})
        if path == "artifacts/artifact_1/content":
            return httpx.Response(200, content=self.content, headers={"Content-Type": "image/png"})
        raise AssertionError((request.method, path))


def settings(tmp_path, **changes):
    return replace(BridgeSettings(mode="enabled", base_url="https://bridge.test", token="fixture-secret",
                                  workspace="workspace-fixture", storage=tmp_path / "bridge", poll_seconds=3600), **changes)


def payload(**values):
    return {"client_request_id": "request_1", "project_id": "project_1", "prompt": "Test green square", "acknowledge_test_only": True, **values}


def service(tmp_path, mock=None, snapshots=None, **changes):
    mock = mock or MockBridge()
    snapshots = snapshots if snapshots is not None else {("101", "project_1"): {"revision": "rev1"}}
    return PreviewService(settings(tmp_path, **changes), lambda owner, project: snapshots.get((owner, project)),
                          client=BridgeClient("https://bridge.test", "fixture-secret", transport=httpx.MockTransport(mock))), mock


def run(coro):
    return asyncio.run(coro)


async def due(svc, job):
    await svc.local(svc.store.patch, job["id"], {"next_poll_at": 0}, release=True)
    await svc.tick()
    return await svc.local(svc.store.get, job["id"])


def test_default_disabled_never_creates_resources_or_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_URL", "bad invalid")
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_STORAGE", str(tmp_path / "never"))
    monkeypatch.delenv("ALCHEMY_RENDER_BRIDGE_MODE", raising=False)
    config = BridgeSettings.from_env()
    app = FastAPI()
    app.get("/healthz")(lambda: {"ok": True})
    assert install_render_bridge(app, session_user=None, auth_enabled=None, project_snapshot=None) is None
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get(PREFIX + "/status").status_code == 404
        assert client.get("/render-bridge-preview").status_code == 404
    assert config.mode == "disabled" and not (tmp_path / "never").exists()


def test_missing_enabled_config_does_not_stop_host(tmp_path, monkeypatch):
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_MODE", "enabled")
    monkeypatch.delenv("ALCHEMY_RENDER_BRIDGE_TOKEN", raising=False)
    monkeypatch.delenv("ALCHEMY_RENDER_BRIDGE_WORKSPACE", raising=False)
    app = FastAPI()
    app.get("/healthz")(lambda: {"ok": True})
    runtime = install_render_bridge(app, session_user=lambda *_: 101, auth_enabled=lambda: True, project_snapshot=lambda *_: None)
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        response = client.get(PREFIX + "/status")
        assert response.json()["error"] == "bridge_configuration_missing"
        assert client.post(PREFIX + "/tasks", json=payload(), headers={"X-Alchemy-Bridge-Preview": "1"}).status_code == 503
    assert runtime["service"] is None


def test_preview_roundtrip_has_no_native_registration_or_ack(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            assert not mock.calls  # The HTTP create route never waits on Bridge.
            await svc.tick()
            final = await svc.local(svc.store.get, job["id"])
            assert final["state"] == "preview_ready"
            manifest, content = await svc.preview("101", job["id"])
            assert content == png() and manifest["receipt_id"] == "receipt_1"
            assert final["native_registration"] == "not_connected"
            assert final["delivery_ack"] == "pending" and mock.acks == []
            calls = len(mock.calls)
            for _ in range(100):
                assert (await svc.preview("101", job["id"]))[1] == png()
                await svc.tick()
            assert len(mock.calls) == calls
            with svc.store.connection() as db:
                assert db.execute("SELECT COUNT(*) FROM integration_receipts").fetchone()[0] == 1
                assert {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")} == {
                    "integration_jobs", "integration_inputs", "integration_receipts"}
        finally:
            await svc.close()
    run(case())


def test_idempotent_click_and_conflicting_input(tmp_path):
    async def case():
        svc, _ = service(tmp_path)
        try:
            first = await svc.create("101", PreviewCreate(**payload()))
            again = await svc.create("101", PreviewCreate(**payload()))
            assert first["id"] == again["id"] and first["origin_key"] == again["origin_key"]
            with pytest.raises(BridgeError, match="idempotency_conflict"):
                await svc.create("101", PreviewCreate(**payload(prompt="Changed")))
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("lost", ["lose_create", "lose_input"])
def test_lost_response_restarts_same_origin_and_input(tmp_path, lost):
    async def case():
        mock = MockBridge()
        setattr(mock, lost, True)
        svc, _ = service(tmp_path, mock)
        request = payload(references=[{"mime_type": "image/png", "content_base64": base64.b64encode(png()).decode()}])
        job = await svc.create("101", PreviewCreate(**request))
        await svc.tick()
        first = await svc.local(svc.store.get, job["id"])
        assert first["state"] == "remote_unavailable"
        await svc.close()
        svc, _ = service(tmp_path, mock)
        try:
            final = await due(svc, job)
            assert final["state"] == "preview_ready"
            assert len(mock.tasks) == len(mock.inputs) == 1
            assert final["origin_key"] == first["origin_key"]
            if lost == "lose_create":
                assert ("GET", "tasks/by-origin/" + first["origin_key"]) in mock.calls
                assert mock.calls.count(("POST", "tasks")) == 1
        finally:
            await svc.close()
    run(case())


def test_outage_does_not_fallback_or_block_local_api(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        mock.outage = True
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            await svc.tick()
            record, _ = await svc.visible("101", job["id"])
            assert record["state"] == "remote_unavailable" and record["last_error"] == "bridge_unreachable"
            assert "private" not in json.dumps(svc.public(record)) and "secret" not in json.dumps(svc.public(record))
            assert mock.calls == [("GET", "capabilities")]
        finally:
            await svc.close()
    run(case())


def test_slow_bridge_is_independent_and_batch_is_bounded(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        mock.slow = asyncio.Event()
        try:
            jobs = [await svc.create("101", PreviewCreate(**payload(client_request_id=f"req_{i}"))) for i in range(5)]
            task = asyncio.create_task(svc.tick())
            await asyncio.sleep(.02)
            visible = await asyncio.wait_for(svc.visible("101", jobs[0]["id"]), timeout=.3)
            assert visible[0]["id"] == jobs[0]["id"]
            mock.slow.set()
            await task
            assert len(mock.tasks) == 2
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("change", ["owner", "delete", "revision"])
def test_scope_and_revision_change_hides_preview(tmp_path, change):
    async def case():
        snapshots = {("101", "project_1"): {"revision": "rev1"}}
        svc, _ = service(tmp_path, snapshots=snapshots)
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            await svc.tick()
            if change == "revision":
                snapshots[("101", "project_1")] = {"revision": "rev2"}
            else:
                snapshots.clear()
            with pytest.raises(BridgeError):
                await svc.preview("101", job["id"])
            with pytest.raises(BridgeError):
                await svc.visible("202", job["id"])
        finally:
            await svc.close()
    run(case())


def test_cancel_before_submit_never_generates(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            await svc.cancel("101", job["id"])
            await svc.tick()
            assert (await svc.local(svc.store.get, job["id"]))["state"] == "canceled"
            assert mock.calls == []
        finally:
            await svc.close()
    run(case())


def test_cancel_ready_receipt_hides_then_rejects_never_accepts(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            await svc.tick()
            await svc.cancel("101", job["id"])
            with pytest.raises(BridgeError):
                await svc.preview("101", job["id"])
            await svc.tick()
            final = await svc.local(svc.store.get, job["id"])
            assert final["state"] == "canceled"
            assert len(mock.acks) == 1 and mock.acks[0]["decision"] == "rejected"
            assert mock.acks[0]["client_receipt_id"] == final["client_receipt_id"]
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("mismatch", ["wrong_hash", "wrong_binding"])
def test_invalid_receipt_not_previewed(tmp_path, mismatch):
    async def case():
        svc, mock = service(tmp_path)
        setattr(mock, mismatch, True)
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            await svc.tick()
            final = await svc.local(svc.store.get, job["id"])
            assert final["state"] == "protocol_error"
            assert await svc.local(svc.store.receipt, job["id"]) is None
            assert not mock.acks
        finally:
            await svc.close()
    run(case())


def test_draining_recovers_but_rejects_new_tasks(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        job = await svc.create("101", PreviewCreate(**payload()))
        await svc.close()
        svc, _ = service(tmp_path, mock, mode="draining")
        try:
            with pytest.raises(BridgeError, match="bridge_draining"):
                await svc.create("101", PreviewCreate(**payload(client_request_id="new")))
            await svc.tick()
            assert (await svc.local(svc.store.get, job["id"]))["state"] == "preview_ready"
        finally:
            await svc.close()
    run(case())


def make_app(tmp_path, *, auth_enabled=True, allow_local=False):
    app = FastAPI()
    mock = MockBridge()
    def actor(_request, auth):
        if auth != "Bearer session-a":
            raise HTTPException(401)
        return 101
    config = settings(tmp_path, allow_local_preview=allow_local)
    runtime = install_render_bridge(app, session_user=actor, auth_enabled=lambda: auth_enabled,
        project_snapshot=lambda owner, project: {"revision": "r1"} if owner in {"101", "local_preview"} and project == "project_1" else None,
        config=config, client=BridgeClient("https://bridge.test", "fixture-secret", transport=httpx.MockTransport(mock)))
    return app, runtime, mock


def test_routes_auth_same_origin_and_owner_injection(tmp_path):
    app, _, mock = make_app(tmp_path)
    with TestClient(app, base_url="https://ui.test") as client:
        assert client.get(PREFIX + "/status").status_code == 401
        auth = {"Authorization": "Bearer session-a"}
        assert client.get(PREFIX + "/status", headers=auth).status_code == 200
        assert mock.calls == []
        assert client.post(PREFIX + "/tasks", json=payload(), headers=auth).status_code == 403
        write = {**auth, "X-Alchemy-Bridge-Preview": "1", "Origin": "https://ui.test"}
        for origin in ("https://evil.test", "null"):
            assert client.post(PREFIX + "/tasks", json=payload(), headers={**write, "Origin": origin}).status_code == 403
        assert client.post(PREFIX + "/tasks", json=payload(owner="202"), headers=write).status_code == 422
        assert client.post(PREFIX + "/tasks", json=payload(project_id="../other"), headers=write).status_code == 404
        assert client.post(PREFIX + "/tasks", json=payload(project_id="foreign"), headers=write).status_code == 404
        response = client.post(PREFIX + "/tasks", json=payload(), headers=write)
        assert response.status_code == 202, response.text
        assert response.json()["native_registration"] == "not_connected"
        assert response.headers["cache-control"] == "no-store"
        assert client.get("/render-bridge-preview").status_code == 200
        assert "原生登记未接通" in client.get("/render-bridge-preview").text


@pytest.mark.parametrize("local,host,expected", [(False,"127.0.0.1",401),(True,"203.0.113.3",401),(True,"127.0.0.1",200)])
def test_auth_disabled_requires_explicit_loopback_test_mode(tmp_path, local, host, expected):
    app, _, _ = make_app(tmp_path, auth_enabled=False, allow_local=local)
    with TestClient(app, client=(host, 55555)) as client:
        assert client.get(PREFIX + "/status").status_code == expected


def test_budget_and_lease_boundaries(tmp_path):
    async def case():
        svc, _ = service(tmp_path, max_jobs=1)
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            with pytest.raises(BridgeError, match="preview_job_capacity"):
                await svc.create("101", PreviewCreate(**payload(client_request_id="new")))
            first = await svc.local(svc.store.claim_due, 2, time.time())
            assert len(first) == 1
            assert not await svc.local(svc.store.claim_due, 2, time.time())
            assert len(await svc.local(svc.store.claim_due, 2, time.time()+301)) == 1
        finally:
            await svc.close()
    run(case())


def test_host_disabled_existing_api_and_guard_remain_unchanged(monkeypatch):
    import app.main as main
    assert not hasattr(main.app.state, "render_bridge_preview")
    client = TestClient(main.app)
    assert client.get("/healthz").status_code == 200
    assert client.get("/creative-agent-v3").status_code == 200
    assert client.get("/api/v3/creative-agent/scenarios").status_code == 200
    assert client.get(PREFIX + "/status").status_code == 404
    assert client.get("/api/v3/creative-agent/mcp-materializations/anything").status_code == 403


def test_cancel_during_input_preparation_never_submits_remote_task(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        mock.slow = asyncio.Event()
        try:
            job = await svc.create("101", PreviewCreate(**payload()))
            ticking = asyncio.create_task(svc.tick())
            while not mock.calls:
                await asyncio.sleep(.001)
            await svc.cancel("101", job["id"])
            mock.slow.set()
            await ticking
            assert not mock.tasks
            assert (await svc.local(svc.store.get, job["id"]))["state"] == "canceled"
        finally:
            await svc.close()
    run(case())


def test_preview_ui_reuses_session_and_only_lightweight_project_projection():
    from pathlib import Path
    script = (Path(__file__).resolve().parents[1] / "src_skeleton/app/integrations/render_bridge/static/preview.js").read_text(encoding="utf-8")
    assert "projects?limit=100&view=summary" in script
    assert "alchemy_veyra_access_token" in script
    assert "headers.Authorization=`Bearer ${token}`" in script
    assert "authorizedFetch(task.preview_url)" in script
    assert "URL.revokeObjectURL" in script
    assert "localStorage.setItem" not in script


def test_host_snapshot_is_read_only_owned_active_and_content_revisioned(monkeypatch):
    import app.main as main
    from types import SimpleNamespace
    value = {"title": "Before"}
    project = SimpleNamespace(status="active", metadata={"veyra_user_id": 101}, model_dump=lambda **_: dict(value))
    monkeypatch.setattr(main.v3_route_handlers.project_service.project_store, "get_project", lambda _: project)
    monkeypatch.setattr(main.v3_route_handlers.project_service, "get_project", lambda *a, **kw: pytest.fail("must not reconcile"))
    first = main._render_bridge_preview_project_snapshot("101", "project_1")
    assert first and main._render_bridge_preview_project_snapshot("202", "project_1") is None
    value["title"] = "After"
    assert main._render_bridge_preview_project_snapshot("101", "project_1")["revision"] != first["revision"]
    project.status = "archived"
    assert main._render_bridge_preview_project_snapshot("101", "project_1") is None


def test_recovery_does_not_retarget_pending_work_to_another_bridge(tmp_path):
    async def case():
        svc, mock = service(tmp_path)
        job = await svc.create("101", PreviewCreate(**payload()))
        await svc.close()
        svc, _ = service(tmp_path, mock, base_url="https://different-bridge.test")
        try:
            await svc.tick()
            final = await svc.local(svc.store.get, job["id"])
            assert final["state"] == "blocked_scope" and not mock.calls
        finally:
            await svc.close()
    run(case())
