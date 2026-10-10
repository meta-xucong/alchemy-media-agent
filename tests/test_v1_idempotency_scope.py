from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

from app import main
from app.repositories import repository
from app.schemas import GenerationJob, GenerationOutput, JobStatus, ProviderError, Session
from app.services import image_service
from app.storage import media_store


def _token(user_id: int) -> str:
    now = int(time.time())
    payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": user_id, "iat": now, "exp": now + 3600}, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(b"idempotency-scope-test-secret", payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{payload}.{signature}"


def _enable_auth(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main.settings, "veyra_session_secret", "idempotency-scope-test-secret")

    async def load_account(user_id: int):
        role = "admin" if user_id == 99 else "user"
        return type("Account", (), {"user_id": user_id, "role": role})()

    monkeypatch.setattr(main, "load_account", load_account)


def test_image_job_idempotency_key_is_scoped_to_authorized_session(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    _enable_auth(monkeypatch)
    runner_calls = []

    async def skip_provider_run(job_id, request, *, edit=False):
        runner_calls.append(job_id)

    monkeypatch.setattr(main, "run_submitted_image_job", skip_provider_run)
    client = TestClient(main.app)
    owner_headers = {"Authorization": f"Bearer {_token(41)}"}
    other_headers = {"Authorization": f"Bearer {_token(77)}"}

    session_a = client.post("/v1/sessions", json={"project_id": "idempotency_a"}, headers=owner_headers).json()["id"]
    session_a2 = client.post("/v1/sessions", json={"project_id": "idempotency_a2"}, headers=owner_headers).json()["id"]
    session_b = client.post("/v1/sessions", json={"project_id": "idempotency_b"}, headers=other_headers).json()["id"]

    def create(session_id: str, headers: dict[str, str], key: str, prompt: str):
        return client.post(
            "/v1/image/jobs",
            json={"session_id": session_id, "prompt": prompt, "count": 1, "idempotency_key": key},
            headers=headers,
        )

    first_a = create(session_a, owner_headers, "shared-key", "private prompt A")
    first_b = create(session_b, other_headers, "shared-key", "private prompt B")
    replay_a = create(session_a, owner_headers, "shared-key", "private prompt A")
    same_owner_other_session = create(session_a2, owner_headers, "shared-key", "private prompt A2")

    assert first_a.status_code == first_b.status_code == replay_a.status_code == same_owner_other_session.status_code == 200
    assert first_a.json()["id"] != first_b.json()["id"]
    assert replay_a.json()["id"] == first_a.json()["id"]
    assert same_owner_other_session.json()["id"] not in {first_a.json()["id"], first_b.json()["id"]}
    assert first_b.json()["session_id"] == session_b
    assert "private prompt A" not in first_b.text

    legacy_a = create(session_a, owner_headers, "legacy-global-key", "legacy private prompt A")
    legacy_b = create(session_b, other_headers, "legacy-global-key", "legacy private prompt B")
    legacy_replay_a = create(session_a, owner_headers, "legacy-global-key", "legacy private prompt A")

    assert legacy_a.status_code == legacy_b.status_code == legacy_replay_a.status_code == 200
    assert legacy_a.json()["id"] != legacy_b.json()["id"]
    assert legacy_replay_a.json()["id"] == legacy_a.json()["id"]
    assert legacy_replay_a.json()["session_id"] == session_a
    assert len(repository.list_jobs()) == 5
    assert len(runner_calls) == 5


@pytest.mark.parametrize("entrypoint", ["submit", "create"])
@pytest.mark.parametrize("failure", ["asset_error", "rejected"])
def test_failed_or_rejected_image_job_idempotency_is_session_scoped(tmp_path, monkeypatch, entrypoint, failure):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    now = "2026-10-10T00:00:00Z"
    for session_id in ("session_failure_a", "session_failure_b"):
        repository.save_session(Session(
            id=session_id,
            project_id=session_id,
            created_at=now,
            veyra_user_id=41,
        ))

    if failure == "rejected":
        monkeypatch.setattr(
            image_service,
            "check_generation_prompt",
            lambda _prompt: ProviderError(code="prompt_rejected", message="Rejected for test."),
        )

    submit = image_service.submit_image_job if entrypoint == "submit" else image_service.create_image_job

    def invoke(session_id: str):
        args = {
            "session_id": session_id,
            "prompt": "safe test prompt",
            "idempotency_key": "same-failed-key",
            "veyra_user_id": 41,
        }
        if failure == "asset_error":
            args.update(asset_mode="advanced", asset_ids=["conflicting-asset"])
        return asyncio.run(submit(**args))

    first_a = invoke("session_failure_a")
    repeat_a = invoke("session_failure_a")
    first_b = invoke("session_failure_b")
    repeat_a_after_global_index_overwrite = invoke("session_failure_a")
    jobs = [item.job if hasattr(item, "job") else item for item in (first_a, repeat_a, first_b, repeat_a_after_global_index_overwrite)]

    assert jobs[0].status == (JobStatus.failed if failure == "asset_error" else JobStatus.rejected)
    assert jobs[1].id == jobs[0].id
    assert jobs[2].id != jobs[0].id
    assert jobs[3].id == jobs[0].id
    assert len(repository.list_jobs()) == 2


def test_background_provider_failure_keeps_session_scoped_idempotency(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    now = "2026-10-10T00:00:00Z"
    for session_id in ("session_provider_failure_a", "session_provider_failure_b"):
        repository.save_session(Session(
            id=session_id,
            project_id=session_id,
            created_at=now,
            veyra_user_id=41,
        ))

    prepared = asyncio.run(image_service.submit_image_job(
        session_id="session_provider_failure_a",
        prompt="safe provider failure test",
        idempotency_key="provider-failed-key",
        veyra_user_id=41,
    ))
    assert prepared.request is not None

    async def raise_provider(job, request, provider, *, edit):
        raise RuntimeError("simulated provider failure")

    monkeypatch.setattr(image_service, "_try_image_provider", raise_provider)
    failed = asyncio.run(image_service.run_submitted_image_job(
        prepared.job.id,
        prepared.request,
        edit=prepared.edit,
    ))
    assert failed is not None and failed.status == JobStatus.failed

    same_session_retry = asyncio.run(image_service.submit_image_job(
        session_id="session_provider_failure_a",
        prompt="safe provider failure test",
        idempotency_key="provider-failed-key",
        veyra_user_id=41,
    ))
    other_session_request = asyncio.run(image_service.submit_image_job(
        session_id="session_provider_failure_b",
        prompt="safe provider failure test",
        idempotency_key="provider-failed-key",
        veyra_user_id=41,
    ))

    assert same_session_retry.job.id == prepared.job.id
    assert same_session_retry.job.status == JobStatus.failed
    assert other_session_request.job.id != prepared.job.id
    assert len(repository.list_jobs()) == 2
