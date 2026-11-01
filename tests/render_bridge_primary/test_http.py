"""Transport tests use strict wire responses, never a real Bridge or provider."""
import asyncio
import json
import httpx
from unittest.mock import Mock

from render_bridge_primary import PrimaryTransport
from render_bridge_primary.http import BridgeClient
from test_core import request, settings, Client


def test_both_alchemy_clients_accept_an_explicit_ca_without_proxy_env(monkeypatch):
    from app.integrations.render_bridge.client import BridgeClient as V1BridgeClient

    ca_bundle = "C:/test/bridge-ca.pem"
    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_CA_BUNDLE", ca_bundle)

    for client_class in (BridgeClient, V1BridgeClient):
        captured = {}

        def make_client(**kwargs):
            captured.update(kwargs)
            return Mock()

        monkeypatch.setattr(client_class.__module__ + ".httpx.AsyncClient", make_client)
        client_class("https://bridge.invalid", "fixture")
        assert captured["verify"] == ca_bundle
        assert captured["trust_env"] is False


def test_both_alchemy_clients_keep_system_ca_validation_by_default(monkeypatch):
    from app.integrations.render_bridge.client import BridgeClient as V1BridgeClient

    monkeypatch.delenv("ALCHEMY_RENDER_BRIDGE_CA_BUNDLE", raising=False)
    for client_class in (BridgeClient, V1BridgeClient):
        captured = {}

        def make_client(**kwargs):
            captured.update(kwargs)
            return Mock()

        monkeypatch.setattr(client_class.__module__ + ".httpx.AsyncClient", make_client)
        client_class("https://bridge.invalid", "fixture")
        assert captured["verify"] is True
        assert captured["trust_env"] is False


def test_lost_http_create_response_and_exact_origin_recovery(tmp_path):
    calls=[]; task={}
    async def handler(req):
        calls.append((req.method,req.url.path))
        if req.url.path.endswith('/capabilities'):
            return httpx.Response(200,json=await Client().capabilities())
        if req.method=='POST':
            payload=json.loads(req.content)
            task.update(remote_task_id='task_1',origin_key=payload['origin_key'],request=payload,state='queued',receipt_id=None)
            raise httpx.ReadTimeout('fixture response loss')
        return httpx.Response(200,json=task)
    async def run():
        client=BridgeClient('http://bridge.invalid','fixture',transport=httpx.MockTransport(handler))
        async with PrimaryTransport(settings(tmp_path),client=client) as transport:
            assert (await transport.resolve(request())).state=='bridge_submission_unknown'
            assert (await transport.resolve(request())).state=='queued'
    asyncio.run(run())
    assert sum(method=='POST' for method,path in calls)==1
    assert calls[-1][1].endswith('/tasks/by-origin/rb_'+request().key)


def test_unstructured_429_is_not_nonadmission(tmp_path):
    async def handler(req):
        if req.method=='GET': return httpx.Response(200,json=await Client().capabilities())
        return httpx.Response(429,text='proxy throttled')
    async def run():
        client=BridgeClient('http://bridge.invalid','fixture',transport=httpx.MockTransport(handler))
        async with PrimaryTransport(settings(tmp_path),client=client) as transport:
            result=await transport.resolve(request())
            assert result.route=='bridge' and result.state=='bridge_submission_unknown'
    asyncio.run(run())
