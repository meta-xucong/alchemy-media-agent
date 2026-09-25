"""Adapter-only contract tests; no credentials, model calls or live services."""
import base64
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest
from PIL import Image

from services.alchemy_codex_local_adapter import product_tools as tools
from services.alchemy_codex_local_adapter import mcp_server


class Opener:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def open(self, request, timeout):
        self.calls.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(reply if isinstance(reply, bytes) else json.dumps(reply).encode())


def client(*responses):
    opener = Opener(*responses)
    return tools.ProductTools("https://alchemy.example", "session-test", opener=opener), opener


def body(request):
    return json.loads(request.data)


def image_file(tmp_path):
    path = tmp_path / "reference.png"
    Image.new("RGB", (20, 20)).save(path)
    return path


def test_six_tools_append_without_changing_legacy_names():
    assert [item["name"] for item in mcp_server.TOOL_SCHEMAS[:5]] == [
        "prepare_shared_mcp_materialization", "submit_shared_mcp_materialization",
        "prepare_native_imagegen_plan", "prepare_frozen_specialized_native_imagegen_plan",
        "prepare_frozen_professional_native_imagegen_plan"]
    assert [item["name"] for item in mcp_server.TOOL_SCHEMAS[5:11]] == [item["name"] for item in tools.PRODUCT_TOOL_SCHEMAS]
    assert len(mcp_server.TOOL_SCHEMAS) == 34
    assert len(tools.PRODUCT_TOOL_NAMES) == 6
    assert {item["name"] for item in mcp_server.TOOL_SCHEMAS[11:]} == {
        "alchemy_list_capabilities",
        "alchemy_v1_create_session", "alchemy_v1_upload_asset", "alchemy_v1_create_image_job", "alchemy_v1_get_image_job", "alchemy_v1_list_history", "alchemy_v1_revise_image",
        "alchemy_v2_create_creative_run", "alchemy_v2_get_creative_run", "alchemy_v2_upload_asset", "alchemy_v2_create_image_job", "alchemy_v2_get_image_job", "alchemy_v2_list_history", "alchemy_v2_search_cases", "alchemy_v2_get_case",
        "alchemy_lab_list_modules", "alchemy_lab_list_styles", "alchemy_lab_search_styles", "alchemy_lab_upload_reference", "alchemy_lab_create_session", "alchemy_lab_get_session", "alchemy_lab_list_history", "alchemy_lab_update_favorites",
    }


@pytest.mark.parametrize("url", ["", "http://example.test", "https://user:pass@example.test", "https://a.test/?token=s",
    "https://a.test/#secret", "https://a.test/api/v3", "file:///tmp", "https://a.test:bad", "https://a.test\n"])
def test_unsafe_configuration_is_rejected_before_network(url):
    with pytest.raises(tools.ProductToolError):
        tools.ProductTools(url, "session-test")


@pytest.mark.parametrize("token", ["", "Bearer something", "secret\r\nOther: header"])
def test_session_never_falls_back_to_anonymous(token):
    with pytest.raises(tools.ProductToolError, match="product_session_required"):
        tools.ProductTools("http://127.0.0.1:8017", token)


@pytest.mark.parametrize("extra", ["provider", "model", "metadata", "owner_id", "veyra_user_id", "base_url", "session_token", "handoff_id"])
def test_model_arguments_cannot_change_authority(extra):
    c, opener = client()
    with pytest.raises(tools.ProductToolError, match="invalid_arguments"):
        c.call("alchemy_create_generation", {"project_id": "p1", "user_input": "product", extra: "forged"})
    assert not opener.calls


@pytest.mark.parametrize("args", [None, [], "text", {"project_id": "../admin"}, {"project_id": "x?admin=true"},
    {"project_id": "a", "job_id": "b"}, {}])
def test_query_is_one_original_id_without_path_injection(args):
    c, opener = client()
    with pytest.raises(tools.ProductToolError):
        c.call("alchemy_get_generation", args)
    assert not opener.calls


@pytest.mark.parametrize("count", [True, "2", 0, 17, 1.5])
def test_generation_does_not_coerce_counts(count):
    c, opener = client()
    with pytest.raises(tools.ProductToolError):
        c.call("alchemy_create_generation", {"project_id": "p1", "user_input": "test", "requested_image_count": count})
    assert not opener.calls


def test_creation_matches_web_auto_generate_and_preserves_user_text():
    response = {"job_id": "", "status": "planning", "metadata": {
        "current_operation": {"operation_id": "op1", "state": "planning", "terminal": False}}}
    c, opener = client(response)
    prompt = "  Silver jar\nNo QR. Preserve the user's line breaks.  "
    result = c.call("alchemy_create_generation", {"project_id": "p1", "user_input": prompt,
        "uploaded_asset_ids": ["asset1"], "requested_image_count": 2, "requested_image_size": "1024x1024"})
    assert len(opener.calls) == 1
    request = opener.calls[0]
    assert request.full_url == "https://alchemy.example/api/v3/creative-agent/projects/p1/jobs"
    assert request.get_header("Authorization") == "Bearer session-test"
    assert body(request) == {"user_input": prompt, "template_id": "general_template", "uploaded_asset_ids": ["asset1"],
        "use_project_context": True, "metadata": {"require_real_images": True, "requested_image_count": 2, "requested_image_size": "1024x1024"},
        "auto_generate": {"quality_mode": "standard", "metadata": {"require_real_images": True, "requested_image_count": 2, "requested_image_size": "1024x1024"}}}
    assert result == {**response, "project_id": "p1"}


@pytest.mark.parametrize("operation,args,url", [
    ("alchemy_create_project", {"user_goal": "goal"}, "/projects"),
    ("alchemy_get_generation", {"project_id": "p1"}, "/projects/p1"),
    ("alchemy_get_generation", {"job_id": "job1"}, "/jobs/job1"),
    ("alchemy_list_outputs", {"project_id": "p1"}, "/project-outputs?project_id=p1&compact=true&limit=60"),
    ("alchemy_select_outputs", {"project_id": "p1", "job_id": "job1", "selected_output_ids": ["out1"]}, "/projects/p1/jobs/job1/select"),
])
def test_each_tool_calls_only_its_existing_endpoint(operation, args, url):
    c, opener = client({"status": "generated", "metadata": {"selection_held": True, "hold_reason": "output_unavailable"}})
    result = c.call(operation, args)
    assert len(opener.calls) == 1
    assert opener.calls[0].full_url == "https://alchemy.example" + tools.API + url
    assert result["status"] == "generated"
    assert result["metadata"]["selection_held"] is True
    if operation == "alchemy_select_outputs":
        assert body(opener.calls[0]) == {"selected_output_ids": ["out1"]}


@pytest.mark.parametrize("error", [TimeoutError("token secret"), URLError("connection failure"), IncompleteRead(b"truncated"), b"invalid json"])
def test_write_uncertainty_never_retries_or_leaks_exception(error):
    c, opener = client(error)
    with pytest.raises(tools.ProductToolError) as caught:
        c.call("alchemy_create_generation", {"project_id": "p1", "user_input": "test"})
    diagnostic = caught.value.as_dict()
    assert diagnostic["automatic_retry"] is False
    assert diagnostic["outcome_unknown"] is True
    assert diagnostic["project_id"] == "p1"
    assert "token secret" not in json.dumps(diagnostic)
    assert len(opener.calls) == 1


@pytest.mark.parametrize("status", [401, 403, 404, 429, 500, 302, 307])
def test_http_errors_preserve_status_not_private_body_or_redirect(status):
    error = HTTPError("https://alchemy.example", status, "secret", {"Location": "https://attacker.test"},
        io.BytesIO(b'{"detail":{"code":"original_error","message":"session-test /private/path"}}'))
    c, opener = client(error)
    with pytest.raises(tools.ProductToolError) as caught:
        c.call("alchemy_get_generation", {"job_id": "job1"})
    assert caught.value.http_status == status
    assert caught.value.code == "original_error"
    assert "session-test" not in json.dumps(caught.value.as_dict())
    assert len(opener.calls) == 1
    assert tools._NoRedirect().redirect_request(None, None, status, None, {}, "https://attacker.test") is None


def test_upload_uses_original_three_step_flow_and_not_a_server_path(tmp_path):
    path = image_file(tmp_path)
    c, opener = client({"asset_id": "asset1", "status": "upload_requested"},
        {"asset_id": "asset1", "status": "stored"}, {"asset_id": "asset1", "status": "ready"})
    result = c.call("alchemy_upload_asset", {"file_path": str(path), "role": "product_reference"})
    assert result["status"] == "ready"
    assert [r.method for r in opener.calls] == ["POST", "PUT", "POST"]
    assert [r.full_url.split(tools.API)[1] for r in opener.calls] == ["/uploads", "/uploads/asset1/content", "/uploads/asset1/complete"]
    assert body(opener.calls[0]) == {"filename": path.name, "mime_type": "image/png", "size_bytes": path.stat().st_size, "role": "product_reference"}
    assert base64.b64decode(body(opener.calls[1])["content_base64"]) == path.read_bytes()
    assert str(tmp_path) not in "".join(str(body(r)) for r in opener.calls)


def test_upload_failure_returns_known_id_without_recreating(tmp_path):
    c, opener = client({"asset_id": "asset1", "status": "upload_requested"}, TimeoutError())
    with pytest.raises(tools.ProductToolError) as caught:
        c.call("alchemy_upload_asset", {"file_path": str(image_file(tmp_path))})
    assert caught.value.as_dict()["asset_id"] == "asset1"
    assert len(opener.calls) == 2


def test_upload_does_not_advance_a_failed_business_record(tmp_path):
    c, opener = client({"asset_id": "asset1", "status": "upload_requested"}, {"asset_id": "asset1", "status": "failed"})
    assert c.call("alchemy_upload_asset", {"file_path": str(image_file(tmp_path))})["status"] == "failed"
    assert len(opener.calls) == 2


@pytest.mark.parametrize("kind", ["relative", "not_image", "missing", "too_large"])
def test_upload_rejects_unsafe_file_before_http(tmp_path, monkeypatch, kind):
    path = image_file(tmp_path)
    if kind == "relative": path = Path("reference.png")
    if kind == "not_image": path.write_bytes(b"password-file-not-an-image")
    if kind == "missing": path.unlink()
    if kind == "too_large": monkeypatch.setattr(tools, "MAX_UPLOAD_BYTES", 1)
    c, opener = client()
    with pytest.raises(tools.ProductToolError):
        c.call("alchemy_upload_asset", {"file_path": str(path)})
    assert not opener.calls


def test_compact_keeps_review_and_delivery_facts_without_rejudging():
    data = {"status": "generated", "items": [{"output_id": "good", "recommendation": "accept",
        "download_url": tools.API + "/outputs/good/download", "file_path": "/private/file"}],
        "review_items": [{"output_id": "held", "review_status": "manual_review"}],
        "project_output_counts": {"p1": 1}, "project_review_counts": {"p1": 1},
        "metadata": {"final_delivery": {"final_delivery_status": "ready", "partial_delivery": True},
                     "recommended_output_ids": ["good"], "raw_prompt": "private", "api_key": "secret"}}
    result = tools._compact(data)
    assert result["review_items"] == data["review_items"]
    assert result["items"][0]["recommendation"] == "accept"
    assert result["metadata"]["final_delivery"] == data["metadata"]["final_delivery"]
    assert result["project_output_counts"] == {"p1": 1}
    assert "secret" not in json.dumps(result) and "private" not in json.dumps(result)
    assert "download_url" not in tools._compact({"download_url": "https://evil.test/?token=s"})


def test_mcp_dispatch_uses_environment_not_argument_credentials(monkeypatch):
    c, opener = client({"job_id": "job1", "status": "finalizing"})
    monkeypatch.setattr(mcp_server.ProductTools, "from_environment", lambda: c)
    response = mcp_server.dispatch(None, {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {
        "name": "alchemy_get_generation", "arguments": {"job_id": "job1"}}})
    assert json.loads(response["result"]["content"][0]["text"]) == {"job_id": "job1", "status": "finalizing"}
    assert len(opener.calls) == 1


def test_stdio_registration_and_bad_configuration_do_not_break_old_tools(tmp_path):
    root = Path(__file__).resolve().parents[1]
    requests = [{"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "alchemy_get_generation", "arguments": {"job_id": "job1"}}}]
    env = {**os.environ, "ALCHEMY_PRODUCT_API_BASE_URL": "https://alchemy.example", "ALCHEMY_PRODUCT_SESSION_TOKEN": "",
           "ALCHEMY_CODEX_LOCAL_REPO_ROOT": str(root)}
    completed = subprocess.run([sys.executable, "-m", "services.alchemy_codex_local_adapter.mcp_server"], cwd=root,
        env=env, input="\n".join(json.dumps(r) for r in requests)+"\n", text=True, encoding="utf-8", capture_output=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    replies = [json.loads(line) for line in completed.stdout.splitlines()]
    assert len(replies[0]["result"]["tools"]) == 34
    assert replies[1]["result"]["isError"] is True
    assert json.loads(replies[1]["result"]["content"][0]["text"])["code"] == "product_session_required"


def test_unstructured_errors_and_internal_response_contracts_do_not_escape():
    result = tools._compact({"status": "failed", "error": "password /private/path", "metadata": {
        "next_actions": [{"id": "review_project_request"}],
        "final_prompt": "private prompt", "handoff": {"nonce": "secret"}}})
    assert result == {"status": "failed", "metadata": {"next_actions": [{"id": "review_project_request"}]}}


def test_plugin_forwards_only_configured_session_and_keeps_existing_launcher():
    root = Path(__file__).resolve().parents[1]
    config = json.loads((root / "plugins/alchemy-codex-local-mode/.mcp.json").read_text(encoding="utf-8"))
    server = config["mcpServers"]["alchemy_local_mode"]
    assert server["command"] == "python"
    assert server["args"] == ["scripts/start_mcp.py", "--enable-native-imagegen"]
    assert {"ALCHEMY_PRODUCT_API_BASE_URL", "ALCHEMY_PRODUCT_SESSION_TOKEN"} <= set(server["env_vars"])
    assert all(isinstance(value, str) for value in server["env_vars"])


def test_product_adapter_has_no_business_backend_dependencies():
    import ast
    import inspect
    tree = ast.parse(inspect.getsource(tools))
    imported = {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert imported <= {"__future__", "http", "pathlib", "typing", "urllib"}
    assert "V3ProductApiService" not in inspect.getsource(tools)
