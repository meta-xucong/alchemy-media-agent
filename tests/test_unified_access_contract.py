from __future__ import annotations

import io
import json
import time
import asyncio
from pathlib import Path

from PIL import Image
from starlette.requests import Request

from services.alchemy_access_bridge import build_access_headers
from services.alchemy_codex_local_adapter.versioned_tools import VERSIONED_TOOL_NAMES, VersionedTools
from custom_media_agent_2_0.app.services.access_bridge import verify_access_headers


def test_v1_proxy_replaces_api_key_with_v2_bridge_headers(monkeypatch):
    import app.main as gateway

    class Response:
        content = b'{"ok":true}'
        status_code = 200
        headers = {"content-type": "application/json"}

    captured = {}

    class Client:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def request(self, method, url, **kwargs):
            captured.update(method=method, url=url, headers=kwargs["headers"])
            return Response()

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    monkeypatch.setenv("ALCHEMY_ACCESS_BRIDGE_SECRET", "bridge-test-secret")
    monkeypatch.setattr(gateway.httpx, "AsyncClient", Client)
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v2/provider-capabilities",
            "query_string": b"",
            "headers": [(b"authorization", b"Bearer alk_live_test")],
            "client": ("127.0.0.1", 8017),
            "server": ("127.0.0.1", 8017),
            "scheme": "http",
        },
        receive,
    )
    request.state.alchemy_api_user_id = 42
    request.state.alchemy_api_key_surfaces = ["lab", "v1", "v2", "v3"]

    response = asyncio.run(gateway._proxy_v2_request("provider-capabilities", request))

    assert response.status_code == 200
    assert captured["url"] == "http://127.0.0.1:8020/api/v2/provider-capabilities"
    assert "authorization" not in {str(key).lower() for key in captured["headers"]}
    assert verify_access_headers(
        captured["headers"],
        method="GET",
        path="/api/v2/provider-capabilities",
        secret="bridge-test-secret",
    )["user_id"] == 42


def test_gateway_and_independent_v2_bridge_share_signature_contract():
    issued_at = int(time.time())
    headers = build_access_headers(
        user_id=42,
        surfaces=["v3", "v2", "lab", "v1"],
        method="GET",
        path="/api/v2/image/history",
        secret="bridge-test-secret",
        request_id="req-test",
        issued_at=issued_at,
        nonce="nonce-test",
    )
    assert verify_access_headers(headers, method="GET", path="/api/v2/image/history", secret="bridge-test-secret", now=issued_at) == {
        "user_id": 42,
        "surfaces": ["lab", "v1", "v2", "v3"],
        "request_id": "req-test",
    }
    tampered = {**headers, "X-Alchemy-Access-User": "43"}
    assert verify_access_headers(tampered, method="GET", path="/api/v2/image/history", secret="bridge-test-secret", now=issued_at) is None
    assert verify_access_headers(headers, method="GET", path="/api/v2/image/history", secret="bridge-test-secret", now=issued_at + 91) is None


def test_versioned_mcp_surface_is_additive_and_has_no_business_imports():
    expected = {
        "alchemy_list_capabilities",
        "alchemy_v1_create_session", "alchemy_v1_upload_asset", "alchemy_v1_create_image_job", "alchemy_v1_get_image_job", "alchemy_v1_list_history", "alchemy_v1_revise_image",
        "alchemy_v2_create_creative_run", "alchemy_v2_get_creative_run", "alchemy_v2_upload_asset", "alchemy_v2_create_image_job", "alchemy_v2_get_image_job", "alchemy_v2_list_history", "alchemy_v2_search_cases", "alchemy_v2_get_case",
        "alchemy_lab_list_modules", "alchemy_lab_list_styles", "alchemy_lab_search_styles", "alchemy_lab_upload_reference", "alchemy_lab_create_session", "alchemy_lab_get_session", "alchemy_lab_list_history", "alchemy_lab_update_favorites",
    }
    assert VERSIONED_TOOL_NAMES == expected
    adapter = VersionedTools.__module__
    assert adapter == "services.alchemy_codex_local_adapter.versioned_tools"


def test_versioned_mcp_adapter_uses_existing_http_routes_without_retrying(tmp_path: Path):
    class Opener:
        def __init__(self):
            self.calls = []
            self.replies = [
                {"id": "session_1", "project_id": "project_1"},
                {"run_id": "run_1", "status": "queued"},
                {"styles": []},
            ]

        def open(self, request, timeout):
            self.calls.append(request)
            return io.BytesIO(json.dumps(self.replies.pop(0)).encode("utf-8"))

    opener = Opener()
    client = VersionedTools("https://alchemy.example", "alk_live_test", opener=opener)
    assert client.call("alchemy_v1_create_session", {"project_id": "project_1"})["id"] == "session_1"
    assert client.call("alchemy_v2_create_creative_run", {"user_prompt": "one image"})["run_id"] == "run_1"
    assert client.call("alchemy_lab_search_styles", {"query": "chrome"}) == {"styles": []}
    assert [request.method for request in opener.calls] == ["POST", "POST", "POST"]
    assert opener.calls[0].full_url == "https://alchemy.example/v1/sessions"
    assert opener.calls[1].full_url == "https://alchemy.example/api/v2/creative/runs"
    assert json.loads(opener.calls[1].data)["user_prompt"] == "one image"
    assert json.loads(opener.calls[2].data) == {"query_text": "chrome"}

    image_path = tmp_path / "ref.png"
    Image.new("RGB", (2, 2), color=(255, 255, 255)).save(image_path)
    upload_opener = Opener()
    upload_opener.replies = [{"asset_id": "asset_1"}, {"asset_id": "asset_1", "status": "uploaded"}, {"asset_id": "asset_1", "status": "ready"}]
    upload_client = VersionedTools("https://alchemy.example", "alk_live_test", opener=upload_opener)
    assert upload_client.call("alchemy_v1_upload_asset", {"file_path": str(image_path), "user_confirmed_rights": True, "role": "subject_reference"})["status"] == "ready"
    assert json.loads(upload_opener.calls[0].data)["declared_role"] == "subject_reference"
    assert [request.method for request in upload_opener.calls] == ["POST", "PUT", "POST"]
