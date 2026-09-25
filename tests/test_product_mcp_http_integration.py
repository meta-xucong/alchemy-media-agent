"""MCP -> existing FastAPI routes; isolated native stores, no paid providers."""
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.parse import urlsplit

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image

from services.alchemy_codex_local_adapter.product_tools import API, ProductTools, ProductToolError, _compact


class NativeOpener:
    def __init__(self, client):
        self.client, self.calls = client, []

    def open(self, request, timeout):
        self.calls.append(request)
        url = urlsplit(request.full_url)
        response = self.client.request(request.method, url.path + ("?" + url.query if url.query else ""),
            content=request.data, headers=dict(request.header_items()), follow_redirects=False)
        if response.status_code >= 300:
            raise HTTPError(request.full_url, response.status_code, "HTTP error", response.headers, io.BytesIO(response.content))
        return io.BytesIO(response.content)


@pytest.fixture
def native(tmp_path, monkeypatch):
    for key, folder in [("ALCHEMY_V3_JOB_DIR", "jobs"), ("ALCHEMY_V3_PROJECT_DIR", "projects"),
                        ("ALCHEMY_V3_OUTPUT_DIR", "outputs"), ("ALCHEMY_V3_UPLOAD_DIR", "uploads")]:
        monkeypatch.setenv(key, str(tmp_path / folder))
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "false")
    import app.main as main
    from app.config import settings
    from alchemy_creative_agent_3_0.tests.test_v3_post_generation_vision_review import _service
    from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
    from alchemy_creative_agent_3_0.tests.test_v3_product_api_minimal_ux import _install_local_pixel_review_fixture
    service = _service(tmp_path)
    _install_local_pixel_review_fixture(service, tmp_path)
    handlers = V3ProductRouteHandlers(service=service)
    monkeypatch.setattr(main, "v3_route_handlers", handlers)
    monkeypatch.setattr(main, "v3_output_store", service.output_store)
    monkeypatch.setattr(settings, "veyra_auth_enabled", True)
    def verify(token):
        if token not in {"session-a", "session-b"}:
            raise HTTPException(401, detail={"code": "session_invalid"})
        return 101 if token == "session-a" else 202
    monkeypatch.setattr(main, "verify_session_token", verify)
    pending = []
    # Queue boundary is observed, never dispatched to a real worker/provider.
    monkeypatch.setattr(main, "_start_v3_project_planning_background", lambda *args: pending.append(args) or True)
    http = TestClient(main.app)
    opener = NativeOpener(http)
    return SimpleNamespace(main=main, service=service, handlers=handlers, http=http, opener=opener,
        tools=ProductTools("https://testserver", "session-a", opener=opener), pending=pending, tmp=tmp_path)


def test_native_upload_project_and_planning_roundtrip(native):
    path = native.tmp / "reference.png"
    Image.new("RGB", (32, 32), (80, 110, 140)).save(path)
    asset = native.tools.call("alchemy_upload_asset", {"file_path": str(path), "role": "product_reference"})
    assert asset["status"] == "ready"
    assert native.service.get_uploaded_asset(asset["asset_id"]).veyra_user_id == 101
    created = native.tools.call("alchemy_create_project", {"user_goal": "Clean silver product photo", "uploaded_asset_ids": [asset["asset_id"]]})
    project_id = created["project"]["project_id"]
    assert native.handlers.project_service.project_store.get_project(project_id).metadata["veyra_user_id"] == 101
    response = native.tools.call("alchemy_create_generation", {"project_id": project_id,
        "user_input": "Clean product photo, no people.", "uploaded_asset_ids": [asset["asset_id"]], "requested_image_count": 1})
    assert response["status"] == "planning" and response["job_id"] == ""
    operation_id = response["metadata"]["current_operation"]["operation_id"]
    assert operation_id
    assert len(native.pending) == 1
    args = native.pending[0]
    assert args[0] == project_id and args[1] == operation_id
    assert args[2]["metadata"]["veyra_user_id"] == 101
    assert args[3]["metadata"]["veyra_user_id"] == 101
    assert args[3]["quality_mode"] == "standard"
    status = native.tools.call("alchemy_get_generation", {"project_id": project_id})
    raw = native.http.get(API + f"/projects/{project_id}", headers={"Authorization": "Bearer session-a"}).json()
    assert status == {**_compact(raw), "project_id": project_id}
    assert operation_id in json.dumps(status)
    assert not any(req.full_url.endswith("/generate") for req in native.opener.calls)
    assert len(native.pending) == 1


@pytest.mark.parametrize("token,expected", [("session-b", 404), ("expired", 401)])
def test_native_account_checks_reject_other_owner_and_expired_session(native, token, expected):
    project = native.tools.call("alchemy_create_project", {"user_goal": "Owned project"})["project"]
    other = ProductTools("https://testserver", token, opener=native.opener)
    with pytest.raises(ProductToolError) as error:
        other.call("alchemy_get_generation", {"project_id": project["project_id"]})
    assert error.value.http_status == expected
    with pytest.raises(ProductToolError) as error:
        other.call("alchemy_create_generation", {"project_id": project["project_id"], "user_input": "No access"})
    assert error.value.http_status == expected
    assert not native.pending


def test_native_upload_foreign_reference_is_denied_before_task_start(native):
    path = native.tmp / "source.png"
    Image.new("RGB", (32, 32)).save(path)
    source = native.tools.call("alchemy_upload_asset", {"file_path": str(path)})
    other = ProductTools("https://testserver", "session-b", opener=native.opener)
    with pytest.raises(ProductToolError) as error:
        other.call("alchemy_create_project", {"user_goal": "foreign reference", "uploaded_asset_ids": [source["asset_id"]]})
    assert error.value.http_status == 404
    assert not native.pending


def test_list_and_selection_keep_native_review_facts_and_exact_binding(native, monkeypatch):
    project_id = native.tools.call("alchemy_create_project", {"user_goal": "Owned project"})["project"]["project_id"]
    rows = {"items": [{"project_id": project_id, "job_id": "job1", "output_id": "good",
        "download_url": API + "/outputs/good/download", "metadata": {"public_delivery_state": "ready"}}],
        "review_items": [{"project_id": project_id, "job_id": "job1", "output_id": "held",
            "metadata": {"review_status": "manual_review", "quality_failure": False}}],
        "project_output_counts": {project_id: 1}, "project_review_counts": {project_id: 1}}
    calls = []
    def list_outputs(limit, owner_id, compact, selected_project, surface, ids):
        assert owner_id == 101 and selected_project == project_id
        return rows
    monkeypatch.setattr(native.handlers, "get_project_outputs", list_outputs)
    listed = native.tools.call("alchemy_list_outputs", {"project_id": project_id})
    assert listed["items"] == rows["items"]
    assert listed["review_items"] == rows["review_items"]
    def select(p, j, payload):
        calls.append((p, j, payload))
        return {"job_id": j, "status": "generated", "metadata": {"selection_held": True, "hold_reason": "output_unavailable"}}
    monkeypatch.setattr(native.handlers, "post_project_job_select", select)
    selected = native.tools.call("alchemy_select_outputs", {"project_id": project_id, "job_id": "job1", "selected_output_ids": ["held"]})
    assert selected["metadata"]["selection_held"] is True
    assert calls == [(project_id, "job1", {"selected_output_ids": ["held"]})]
    assert not native.pending


def test_write_transport_uses_same_web_request_and_never_touches_billing_in_adapter(native):
    project_id = native.tools.call("alchemy_create_project", {"user_goal": "Billing route parity"})["project"]["project_id"]
    args = {"project_id": project_id, "user_input": "Exact instruction", "quality_mode": "strict",
            "requested_image_count": 2, "requested_image_size": "1024x1024"}
    native.tools.call("alchemy_create_generation", args)
    request = native.opener.calls[-1]
    assert request.method == "POST" and request.full_url.endswith(f"/projects/{project_id}/jobs")
    assert json.loads(request.data)["auto_generate"]["quality_mode"] == "strict"
    assert len(native.pending) == 1
    assert native.pending[0][3]["metadata"]["veyra_user_id"] == 101
    # The backend owns billing; this observes the identical dispatch boundary,
    # not a claim of a live balance debit or settlement test.
    import services.alchemy_codex_local_adapter.product_tools as module
    assert not any(term in module.__dict__ for term in ("debit_balance", "V3BalanceAdapter", "GenerationRouter"))


def test_controlled_native_job_review_outputs_and_selection_flow(native, monkeypatch):
    from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter, MockGenerationProvider
    from alchemy_creative_agent_3_0.app.llm_brain.adapter import V3LLMBrainAdapter
    from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
    provider = MockGenerationProvider()
    calls = []
    original_generate = provider.generate
    def generate(request):
        # A metadata-only mock cannot stand in for pixel delivery. Materialize
        # deterministic pixels in the isolated native output store, just as a
        # Provider would; the existing shared review still decides delivery.
        import base64
        calls.append(request)
        response = original_generate(request)
        pixels = io.BytesIO()
        Image.new("RGB", (32, 32), (80, 100, 130)).save(pixels, format="PNG")
        candidates = []
        for candidate in response.candidates:
            record = native.service.output_store.save_base64_output(
                job_id=request.metadata["job_id"], candidate_id=candidate.candidate_id,
                asset_id=candidate.asset_id, provider="offline_pixel_fixture", model="fixture",
                encoded_image=base64.b64encode(pixels.getvalue()).decode("ascii"),
                metadata={"project_id": request.metadata["project_id"],
                          "veyra_user_id": request.metadata["veyra_user_id"]})
            candidates.append(candidate.model_copy(update={"is_mock": False, "uri": record.download_url,
                "metadata": {**candidate.metadata, "output_id": record.output_id,
                    "download_url": record.download_url, "preview_url": record.preview_url}}))
        return response.model_copy(update={"candidates": candidates})
    monkeypatch.setattr(provider, "generate", generate)
    native.service.scenario_runtime.generation_router = GenerationRouter(provider=provider)
    native.service.scenario_runtime.llm_brain_adapter = V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    # Execute the existing worker inline; retain its typed continuation,
    # ownership, metadata sanitation and review boundary rather than bypassing it.
    monkeypatch.setattr(native.main, "_v3_generation_executor", SimpleNamespace(
        submit=lambda function, *args: function(*args)))
    project_id = native.tools.call("alchemy_create_project", {"user_goal": "A neutral product photograph, no people"})["project"]["project_id"]
    created = native.tools.call("alchemy_create_generation", {"project_id": project_id,
        "user_input": "A neutral product photograph, no people", "requested_image_count": 1})
    assert created["metadata"]["current_operation"]["operation_id"]
    native.main._run_v3_project_planning_background(*native.pending.pop())
    project = native.tools.call("alchemy_get_generation", {"project_id": project_id})
    job_id = project["project"]["job_ids"][-1]
    job = native.tools.call("alchemy_get_generation", {"job_id": job_id})
    assert job["status"] == "generated", job
    outputs = native.tools.call("alchemy_list_outputs", {"project_id": project_id})
    ids = [item["output_id"] for item in outputs["items"]]
    assert len(ids) == 1, {"final_delivery": job.get("metadata", {}).get("final_delivery"),
        "review": job.get("metadata", {}).get("post_generation_review"), "outputs": outputs,
        "records": [{"id": r.output_id, "owner": r.metadata.get("veyra_user_id")} for r in native.service.output_store.list_by_job(job_id)]}
    selected = native.tools.call("alchemy_select_outputs", {"project_id": project_id,
        "job_id": job_id, "selected_output_ids": ids})
    assert not selected.get("metadata", {}).get("selection_held"), selected
    assert len(calls) == 1
    before = len(calls)
    native.tools.call("alchemy_get_generation", {"job_id": job_id})
    native.tools.call("alchemy_list_outputs", {"project_id": project_id})
    assert len(calls) == before
    for item in outputs["items"]:
        response = native.http.get(item["download_url"], headers={"Authorization": "Bearer session-a"})
        assert response.status_code == 200 and response.content
    assert not any(request.full_url.endswith("/generate") for request in native.opener.calls)
