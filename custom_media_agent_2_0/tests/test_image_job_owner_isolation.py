"""Account-bound job projection and recovery; no live SSO or renderer."""
from datetime import datetime, timezone
import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.repositories import repository
from app.schemas import ImageJob, ImageOutput, ImagePromptPlan, CreateImageJobRequest
from app.services import render_bridge_primary as bridge, generation
from app.services.access_bridge import _canonical
from app.services.veyra_auth import issue_session_token


@pytest.fixture(autouse=True)
def isolated_auth(monkeypatch):
    original = vars(settings).copy()
    for key, value in {"veyra_auth_enabled": True, "veyra_session_secret": "offline-test-session",
                       "veyra_internal_token": "offline-test-internal",
                       "alchemy_access_bridge_secret": "offline-test-access"}.items():
        object.__setattr__(settings, key, value)
    monkeypatch.setattr(bridge, "load_frozen", lambda *args, **kwargs: None)
    try:
        yield
    finally:
        for key, value in original.items():
            object.__setattr__(settings, key, value)


def job(owner=17, output_owners=(), status="running"):
    now = datetime.now(timezone.utc)
    return ImageJob(veyra_user_id=owner, job_id="private-job", status=status,
        provider_id="mock", model="offline", created_at=now, updated_at=now,
        prompt_plan=ImagePromptPlan(plan_id="p", mode="smart_enhance", prompt="private prompt"),
        outputs=[ImageOutput(output_id=f"o{i}", job_id="private-job", url=f"/private/{i}",
            metadata={"veyra_user_id": value}, created_at=now) for i, value in enumerate(output_owners)])


def headers(user):
    return {"Authorization": "Bearer " + issue_session_token(user)}


def signed_headers(user, path, surfaces=("v2",)):
    issued = int(time.time())
    signature = hmac.new(b"offline-test-access", _canonical(user, surfaces, "req", issued, "nonce", "GET", path), hashlib.sha256).hexdigest()
    return {"X-Alchemy-Access-User": str(user), "X-Alchemy-Access-Surfaces": ",".join(surfaces),
        "X-Alchemy-Access-Request": "req", "X-Alchemy-Access-Issued": str(issued),
        "X-Alchemy-Access-Nonce": "nonce", "X-Alchemy-Access-Signature": signature}


@pytest.mark.parametrize("status", ["running", "failed", "completed", "cancelled", "queued"])
def test_persisted_owner_controls_job_detail(status):
    repository.save_image_job(job(status=status))
    client = TestClient(main.app)
    path = "/api/v2/image/jobs/private-job"
    assert repository.get_image_job("private-job").veyra_user_id == 17
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers(17)).status_code == 200
    response = client.get(path, headers=headers(22))
    assert response.status_code == 404
    assert "private prompt" not in response.text


@pytest.mark.parametrize("owners,allowed", [((17,), True), (("17", "17"), True),
    ((17, 22), False), ((True,), False), ((17.0,), False), (("unknown",), False), ((), False)])
def test_legacy_output_owner_must_be_consistent(owners, allowed):
    repository.save_image_job(job(owner=None, output_owners=owners))
    client = TestClient(main.app)
    assert client.get("/api/v2/image/jobs/private-job", headers=headers(17)).status_code == (200 if allowed else 404)


@pytest.mark.parametrize("frozen_owner,allowed", [(17, True), (22, False), (None, False), (True, False)])
def test_frozen_owner_shared_by_read_resume_cancel(monkeypatch, frozen_owner, allowed):
    repository.save_image_job(job())
    record = {"request": {"veyra_user_id": frozen_owner}, "queue_task_id": None}
    monkeypatch.setattr(bridge, "load_frozen", lambda *args, **kwargs: record)
    client = TestClient(main.app)
    path = "/api/v2/image/jobs/private-job"
    assert client.get(path, headers=headers(17)).status_code == (200 if allowed else 404)
    for suffix in ("resume", "cancel"):
        # Foreign accounts cannot reach mutation or even queue/record parsing.
        assert client.post(path + "/" + suffix, headers=headers(31)).status_code == 404
        if not allowed:
            assert client.post(path + "/" + suffix, headers=headers(17)).status_code == 404


def test_legacy_frozen_owner_allows_read_without_output(monkeypatch):
    repository.save_image_job(job(owner=None))
    monkeypatch.setattr(bridge, "load_frozen", lambda *args: {"request": {"veyra_user_id": 17}})
    assert TestClient(main.app).get("/api/v2/image/jobs/private-job", headers=headers(17)).status_code == 200


def test_auth_disabled_legacy_local_behavior():
    object.__setattr__(settings, "veyra_auth_enabled", False)
    repository.save_image_job(job(owner=None))
    assert TestClient(main.app).get("/api/v2/image/jobs/private-job").status_code == 200


def test_signed_access_identity_cannot_read_other_owner():
    repository.save_image_job(job())
    path = "/api/v2/image/jobs/private-job"
    client = TestClient(main.app)
    assert client.get(path, headers=signed_headers(17, path)).status_code == 200
    assert client.get(path, headers=signed_headers(22, path)).status_code == 404
    forged = signed_headers(17, path)
    forged["X-Alchemy-Access-User"] = "22"
    assert client.get(path, headers=forged).status_code == 401
    assert client.get(path, headers=signed_headers(17, path, ("v1",))).status_code == 401


def test_client_claim_and_admin_label_do_not_override_owner(monkeypatch):
    repository.save_image_job(job())
    # This route intentionally has no administrator impersonation exception.
    client = TestClient(main.app)
    response = client.get("/api/v2/image/jobs/private-job?veyra_user_id=17&is_admin=true", headers=headers(22))
    assert response.status_code == 404
    request = main.Request({"type": "http", "method": "POST", "path": "/api/v2/image/jobs",
        "headers": [], "query_string": b""})
    body = CreateImageJobRequest(veyra_user_id=17, prompt_plan=job().prompt_plan)
    verified = main._image_job_with_veyra_user(body, request, headers(22)["Authorization"])
    assert verified.veyra_user_id == 22


def test_failed_and_prepared_job_preserve_authenticated_owner(monkeypatch):
    import asyncio
    from app.providers.images import V2ImageProviderError
    request = CreateImageJobRequest(veyra_user_id=17, prompt_plan=job().prompt_plan, provider_hint="mock_image")
    failed = generation._failed_job(request, provider_id="offline", error=V2ImageProviderError("offline"),
        job_id="failed", created_at=datetime.now(timezone.utc))
    assert failed.veyra_user_id == 17
    monkeypatch.setattr(bridge, "enabled", lambda: False)
    prepared = asyncio.run(generation.create_running_image_job(request))
    assert prepared.veyra_user_id == 17


def test_completed_mock_and_balance_failed_constructors_preserve_owner():
    from app.providers.images.base import V2ImageProviderResult
    from app.schemas import CreateCreativeRunRequest
    from app.services.queue_worker import _veyra_balance_failed_run
    request = CreateImageJobRequest(veyra_user_id=17, prompt_plan=job().prompt_plan)
    completed = generation._job_from_result(request,
        V2ImageProviderResult(provider="mock_image", model="offline", outputs=[]),
        job_id="mock-completed", created_at=datetime.now(timezone.utc))
    assert completed.veyra_user_id == 17
    failed_run = _veyra_balance_failed_run(CreateCreativeRunRequest(user_prompt="private", veyra_user_id=17), "r")
    assert failed_run.generation_jobs[0].veyra_user_id == 17


def test_job_schema_rejects_coerced_owner():
    from pydantic import ValidationError
    for invalid in (True, 17.0, "17", 0, -1):
        with pytest.raises(ValidationError):
            job(owner=invalid)


@pytest.mark.parametrize("record", [{"request": []}, {}, {"request": {"veyra_user_id": "9" * 5000}}])
def test_malformed_frozen_identity_is_not_an_owner(record):
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as raised:
        main._require_image_job_owner(job(), 17, frozen_record=record)
    assert raised.value.status_code == 404
