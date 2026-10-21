"""HTTP retry hints schedule durable reconciliation, never sleep or new identities."""
import asyncio
from email.utils import formatdate

import httpx
import pytest

from app.integrations.render_bridge.client import BridgeClient, BridgeError
from app.integrations.render_bridge.models import PreviewCreate
from app.integrations.render_bridge.store import PreviewStore
from test_render_bridge_preview import service, payload, run
from test_render_bridge_native_coordinator import make_service, request


@pytest.mark.parametrize("status", [429, 503])
@pytest.mark.parametrize("header,expected", [
    ("120", 1120), (formatdate(1300, usegmt=True), 1300),
    ("0", 1000), (formatdate(900, usegmt=True), 900),
    (None, None), ("garbage", None), ("-5", None), ("1.5", None),
])
def test_client_parses_retry_after_without_retry_or_sleep(monkeypatch, status, header, expected):
    monkeypatch.setattr("app.integrations.render_bridge.client.time.time", lambda: 1000)
    async def case():
        calls = []
        def transport(req):
            calls.append(req)
            return httpx.Response(status, headers={"Retry-After": header} if header is not None else {},
                                  json={"error": {"code": "temporarily_busy"}})
        client = BridgeClient("https://bridge.test", "fixture", transport=httpx.MockTransport(transport))
        try:
            with pytest.raises(BridgeError) as caught:
                await client.task("task_1")
            assert caught.value.retry_not_before == expected
            assert caught.value.retryable is True
            assert caught.value.code == "temporarily_busy"
            assert len(calls) == 1
        finally:
            await client.close()
    run(case())


@pytest.mark.parametrize("native", [False, True])
@pytest.mark.parametrize("header,delay", [("180", 180), (formatdate(1400, usegmt=True), 400),
                                          ("0", 2), (formatdate(900, usegmt=True), 2),
                                          (None, 2), ("invalid", 2)])
def test_coordinators_persist_deadline_release_worker_and_keep_identity(tmp_path, monkeypatch, native, header, delay):
    now = [1000.0]
    monkeypatch.setattr("app.integrations.render_bridge.client.time.time", lambda: now[0])
    async def case():
        calls = []
        def transport(req):
            calls.append(req.url.path)
            return httpx.Response(503, headers={"Retry-After": header} if header else {},
                                  json={"error": {"code": "busy"}})
        if native:
            svc, gateway, _ = make_service(tmp_path)
            create_request = request()
        else:
            svc, _ = service(tmp_path)
            create_request = PreviewCreate(**payload())
        await svc.client.close()
        svc.client = BridgeClient("https://bridge.test", "fixture", transport=httpx.MockTransport(transport))
        try:
            original = await svc.create("101", create_request)
            await asyncio.wait_for(svc.tick(), timeout=2)
            saved = svc.store.get(original["id"])
            assert saved["next_poll_at"] == 1000 + delay
            assert saved["state"] == "remote_unavailable"
            assert len(calls) == 1
            assert (await svc.create("101", create_request))["id"] == original["id"]
            for key in ("origin_key", "request_key", "binding_id", "client_receipt_id"):
                assert saved[key] == original[key]
            if native:
                for key in ("plan_key", "import_key"):
                    assert saved[key] == original[key]
                assert gateway.create_calls == 0  # Capability admission precedes Brain.
            # A separate store instance models restart: no due claim before the deadline.
            reopened = PreviewStore(svc.settings.storage, max_jobs=svc.settings.max_jobs,
                                    max_bytes=svc.settings.max_storage_bytes)
            assert reopened.claim_due(1, now=1000 + delay - 1) == []
            await svc.tick()
            assert len(calls) == 1
            if delay > 60:
                await svc.cancel("101", original["id"])
                assert svc.store.get(original["id"])["next_poll_at"] == 1000 + delay
                await svc.tick()
                assert len(calls) == 1
            # Lease was released, not held for the server's waiting interval.
            assert len(reopened.claim_due(1, now=1000 + delay)) == 1
        finally:
            await svc.close()
    run(case())
