"""Coordinator contract tests; native business authority is an explicit double."""
import asyncio
from dataclasses import replace
from io import BytesIO
import hashlib
from types import SimpleNamespace

import httpx
from PIL import Image
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.integrations.render_bridge.client import BridgeClient, BridgeError
from app.integrations.render_bridge.native_service import NativeBridgeService, NativeTaskCreate
from app.integrations.render_bridge.routes import install_render_bridge, PREFIX
from test_render_bridge_preview import MockBridge, settings, run, due


class NativeMockBridge(MockBridge):
    def __init__(self):
        super().__init__()
        output = BytesIO()
        Image.new("RGB", (1024, 1024), "green").save(output, format="PNG")
        self.content = output.getvalue()
        self.lose_ack = False

    async def __call__(self, request):
        response = await super().__call__(request)
        if "/receipts/" in request.url.path and not request.url.path.endswith("/ack"):
            payload = response.json()
            payload["dimensions"] = {"width": 1024, "height": 1024}
            return httpx.Response(200, json=payload)
        if request.url.path.endswith("/ack") and self.lose_ack:
            self.lose_ack = False
            raise httpx.ReadError("ack response lost", request=request)
        return response


class NativeGatewayDouble:
    def __init__(self):
        self.plans, self.registrations = {}, {}
        self.create_calls, self.register_calls, self.cancel_calls = 0, 0, 0
        self.lose_plan = False
        self.lose_register = False
        self.unknown_register = False
        self.canceled = False
        self.revision = "freeze_1"

    def create_plan(self, actor, project, user_input, plan_key):
        self.create_calls += 1
        result = {"status": "planned", "target": {"project_id": project, "job_id": "native_job_1", "asset_id": "asset_1"}, "plan_key": plan_key}
        self.plans[plan_key] = result
        if self.lose_plan:
            self.lose_plan = False
            raise RuntimeError("response lost after planning")
        return result

    def plan_status(self, actor, project, plan_key):
        return self.plans.get(plan_key, {"status": "plan_unknown"})

    def prepare(self, actor, target, *, execution_profile_id):
        assert actor == 101 and execution_profile_id == "fake-image"
        if self.canceled:
            raise ValueError("canceled")
        return {"frozen_request_id": self.revision, "target_revision": "target_r1",
                "prompt": "Exact approved canonical prompt", "prompt_sha256": "1"*64,
                "references": [], "image_options": {"size": "1024x1024", "quality": "auto", "output_format": "png"},
                "execution_profile_id": "fake-image", "execution_profile_revision": "1", "test_fixture": True, "submission_ready": True}

    def registration_status(self, actor, target, *, import_key):
        if self.unknown_register:
            return {"status": "import_unknown", "retry_safe": False}
        return self.registrations.get(import_key, {"status": "not_registered", "retry_safe": True})

    def register_receipt(self, actor, target, **values):
        self.register_calls += 1
        assert not self.canceled
        assert values["frozen_request_id"] == self.revision
        assert values["execution_profile_id"] == "fake-image"
        assert hashlib.sha256(values["artifact_bytes"]).hexdigest() == values["original_sha256"]
        result = {"status": "registered", "native_registration_ref": "native_output_1",
                  "original_sha256": values["original_sha256"], "normalized_sha256": values["original_sha256"],
                  "review_status": "test_review_only", "formal_delivery": False,
                  "billing": {"mode": "v3_zero_credit_stub", "charged": False}, "execution_audit_count": 1}
        self.registrations[values["import_key"]] = result
        if self.lose_register:
            self.lose_register = False
            raise RuntimeError("response lost after native commit")
        return result

    def cancel_target(self, actor, target):
        self.cancel_calls += 1
        if self.registrations:
            return {"status": "already_registered"}
        self.canceled = True
        return {"status": "canceled"}


def make_service(tmp_path, gateway=None, bridge=None):
    gateway, bridge = gateway or NativeGatewayDouble(), bridge or NativeMockBridge()
    svc = NativeBridgeService(settings(tmp_path, native_enabled=True),
        lambda owner, project: {"revision": "project_revision"} if owner == "101" and project == "project_1" else None,
        gateway, client=BridgeClient("https://bridge.test", "fixture-secret", transport=httpx.MockTransport(bridge)),
        target_factory=SimpleNamespace)
    return svc, gateway, bridge


def request(**values):
    return NativeTaskCreate(**{"client_request_id": "native_request_1", "project_id": "project_1",
        "user_input": "A user request, not an already frozen prompt", "acknowledge_synthetic_native_test": True, **values})


def test_native_chain_uses_frozen_prompt_and_confirms_before_accepted(tmp_path):
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        try:
            job = await svc.create("101", request())
            assert gateway.create_calls == 0 and not bridge.calls
            assert (await svc.create("101", request()))["id"] == job["id"]
            await svc.tick()
            final = await svc.local(svc.store.get, job["id"])
            assert final["state"] == "registered", final
            assert gateway.create_calls == gateway.register_calls == 1
            assert next(iter(bridge.tasks.values()))["request"]["prompt"] == "Exact approved canonical prompt"
            assert next(iter(bridge.tasks.values()))["request"]["parameters"] == {"width": 1024, "height": 1024, "seed": 0}
            assert bridge.acks == [{"client_receipt_id": final["client_receipt_id"], "decision": "accepted", "reason_code": "native_registered",
                "original_hash": final["native_outcome"]["original_sha256"], "normalized_hash": final["native_outcome"]["normalized_sha256"],
                "native_registration_ref": "native_output_1"}]
            public = svc.public(final)
            assert public["formal_delivery"] is False and public["billing"]["charged"] is False
            assert public["test_fixture"] is True and public["real_tool_verified"] is False
            for _ in range(100):
                await svc.tick()
            assert gateway.register_calls == 1 and len(bridge.acks) == 1
        finally:
            await svc.close()
    run(case())


@pytest.mark.parametrize("lost", ["plan", "register", "ack"])
def test_unknown_responses_recover_without_new_plan_render_or_import(tmp_path, lost):
    async def case():
        gateway, bridge = NativeGatewayDouble(), NativeMockBridge()
        if lost == "ack": bridge.lose_ack = True
        elif lost == "plan": gateway.lose_plan = True
        else: gateway.lose_register = True
        svc, _, _ = make_service(tmp_path, gateway, bridge)
        job = await svc.create("101", request())
        await svc.tick()
        assert (await svc.local(svc.store.get, job["id"]))["state"] == "remote_unavailable"
        await svc.close()
        svc, _, _ = make_service(tmp_path, gateway, bridge)
        try:
            final = await due(svc, job)
            assert final["state"] == "registered", final
            assert gateway.create_calls == gateway.register_calls == 1
            assert len(bridge.tasks) == 1
            if lost == "ack":
                assert len(bridge.acks) == 2 and bridge.acks[0] == bridge.acks[1]
        finally:
            await svc.close()
    run(case())


def test_unconfirmed_import_never_acknowledges_or_reimports(tmp_path):
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        gateway.unknown_register = True
        try:
            job = await svc.create("101", request())
            await svc.tick()
            for _ in range(3):
                final = await due(svc, job)
            assert final["state"] == "import_unknown"
            assert gateway.register_calls == 0 and not bridge.acks
            assert len(bridge.tasks) == 1
        finally:
            await svc.close()
    run(case())


def test_cancel_before_plan_or_after_remote_submit_preserves_native_boundary(tmp_path):
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        bridge.ready = False
        try:
            before = await svc.create("101", request())
            await svc.cancel("101", before["id"])
            await svc.tick()
            assert gateway.create_calls == 0 and not bridge.calls
            after = await svc.create("101", request(client_request_id="after"))
            await svc.tick()
            assert len(bridge.tasks) == 1
            await svc.cancel("101", after["id"])
            await svc.tick()
            final = await svc.local(svc.store.get, after["id"])
            assert final["state"] == "canceled"
            assert gateway.cancel_calls == 1 and gateway.register_calls == 0
            assert all(ack["decision"] != "accepted" for ack in bridge.acks)
        finally:
            await svc.close()
    run(case())


def test_changed_native_freeze_does_not_submit_or_register(tmp_path):
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        bridge.ready = False
        try:
            job = await svc.create("101", request())
            await svc.tick()
            gateway.revision = "freeze_2"
            final = await due(svc, job)
            assert final["state"] == "blocked_revision"
            assert gateway.register_calls == 0 and not bridge.acks
        finally:
            await svc.close()
    run(case())


def test_native_route_is_separately_disabled_and_forbids_local_unauthenticated_mode(tmp_path):
    app = FastAPI()
    config = settings(tmp_path)
    install_render_bridge(app, session_user=lambda *_: 101, auth_enabled=lambda: True,
                          project_snapshot=lambda *_: {"revision": "r1"}, config=config)
    with TestClient(app) as client:
        assert client.get(PREFIX + "/native/status").status_code == 404
    app = FastAPI()
    config = settings(tmp_path / "local", native_enabled=True, allow_local_preview=True)
    install_render_bridge(app, session_user=lambda *_: None, auth_enabled=lambda: False,
                          project_snapshot=lambda *_: {"revision": "r1"}, config=config,
                          native_gateway_factory=lambda _: NativeGatewayDouble())
    with TestClient(app, client=("127.0.0.1", 1234)) as client:
        assert client.get(PREFIX + "/native/status").status_code == 403


def test_native_route_rejects_browser_owner_profile_and_options(tmp_path):
    app = FastAPI()
    install_render_bridge(app, session_user=lambda *_: 101, auth_enabled=lambda: True,
                          project_snapshot=lambda *_: {"revision": "r1"},
                          config=settings(tmp_path, native_enabled=True),
                          native_gateway_factory=lambda _: NativeGatewayDouble())
    with TestClient(app) as client:
        headers = {"X-Alchemy-Bridge-Preview": "1"}
        body = request().model_dump()
        for invalid in ({"owner": 202}, {"profile_id": "codex-image"}, {"image_options": {}}, {"prompt": "bypass Brain"}):
            assert client.post(PREFIX+"/native/tasks", json={**body, **invalid}, headers=headers).status_code == 422
        response = client.post(PREFIX+"/native/tasks", json=body, headers=headers)
        assert response.status_code == 202, response.text
        assert response.json()["native_registration"] == "pending"
        assert client.get("/render-bridge-native-test").status_code == 200


def test_native_rejection_is_terminal_and_never_accepted(tmp_path):
    async def case():
        svc, gateway, bridge = make_service(tmp_path)
        gateway.registration_status = lambda *a, **kw: {"status": "rejected", "reason_code": "native_target_changed", "retry_safe": False}
        try:
            job = await svc.create("101", request())
            await svc.tick()
            final = await svc.local(svc.store.get, job["id"])
            assert final["state"] == "rejected" and final["delivery_ack"] == "rejected"
            assert gateway.register_calls == 0
            assert [ack["decision"] for ack in bridge.acks] == ["rejected"]
            await svc.tick()
            assert len(bridge.acks) == 1
        finally:
            await svc.close()
    run(case())
