from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from app import main
from app.repositories import repository
from app.schemas import Session
from app.services import session_service
from app.storage import media_store


def _token(user_id: int) -> str:
    now = int(time.time())
    payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": user_id, "iat": now, "exp": now + 3600}, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(b"session-owner-test-secret", payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{payload}.{signature}"


def _enable_auth(monkeypatch) -> None:
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main.settings, "veyra_session_secret", "session-owner-test-secret")

    async def load_account(user_id: int):
        role = "admin" if user_id == 99 else "user"
        return type("Account", (), {"user_id": user_id, "role": role})()

    monkeypatch.setattr(main, "load_account", load_account)


def test_v1_session_owner_is_server_assigned_and_enforced_for_sse_and_writes(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    _enable_auth(monkeypatch)
    client = TestClient(main.app)
    owner_headers = {"Authorization": f"Bearer {_token(41)}"}
    other_headers = {"Authorization": f"Bearer {_token(77)}"}

    created = client.post(
        "/v1/sessions",
        json={"project_id": "session_owner", "veyra_user_id": 77},
        headers=owner_headers,
    )
    assert created.status_code == 200
    session_id = created.json()["id"]
    assert created.json()["veyra_user_id"] == 41
    assert repository.get_session(session_id).veyra_user_id == 41
    repository.append_event(session_id, "private.test", {"value": "owner-only"})

    assert client.get(f"/v1/sessions/{session_id}/events", headers=owner_headers).status_code == 200
    denied_sse = client.get(f"/v1/sessions/{session_id}/events", headers=other_headers)
    assert denied_sse.status_code == 404

    image_job_kwargs = {}

    async def capture_owned_image_job(**kwargs):
        image_job_kwargs.update(kwargs)
        return SimpleNamespace(id="job_owned_message")

    monkeypatch.setattr(session_service, "create_image_job", capture_owned_image_job)
    owned_message = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "create an image", "target": "image"},
        headers=owner_headers,
    )
    assert owned_message.status_code == 200
    assert image_job_kwargs["veyra_user_id"] == 41

    message_called = False

    async def unexpected_handle_message(*args, **kwargs):
        nonlocal message_called
        message_called = True
        raise AssertionError("foreign session message must be rejected before message handling")

    monkeypatch.setattr(main, "handle_message", unexpected_handle_message)
    denied_message = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"text": "hello", "target": "auto"},
        headers=other_headers,
    )
    assert denied_message.status_code == 404
    assert not message_called

    submit_called = False

    async def unexpected_submit(*args, **kwargs):
        nonlocal submit_called
        submit_called = True
        raise AssertionError("foreign session image job must be rejected before submission")

    monkeypatch.setattr(main, "submit_image_job", unexpected_submit)
    denied_job = client.post(
        "/v1/image/jobs",
        json={"session_id": session_id, "prompt": "test", "count": 1},
        headers=other_headers,
    )
    assert denied_job.status_code == 404
    assert not submit_called
    assert repository.list_jobs() == []
    assert repository.list_events(session_id) == [
        {"event": "private.test", "data": {"value": "owner-only"}}
    ]


def test_v1_legacy_ownerless_session_is_admin_read_only_and_auth_off_stays_compatible(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    _enable_auth(monkeypatch)
    legacy = Session(id="ses_legacy_ownerless", project_id="legacy", created_at="2026-01-01T00:00:00Z")
    repository.save_session(legacy)
    repository.append_event(legacy.id, "legacy.test", {"value": "private-transcript"})
    client = TestClient(main.app)

    user_response = client.get(
        f"/v1/sessions/{legacy.id}/events",
        headers={"Authorization": f"Bearer {_token(77)}"},
    )
    admin_response = client.get(
        f"/v1/sessions/{legacy.id}/events",
        headers={"Authorization": f"Bearer {_token(99)}"},
    )
    assert user_response.status_code == 404
    assert admin_response.status_code == 200
    admin_write = client.post(
        f"/v1/sessions/{legacy.id}/messages",
        json={"text": "hello", "target": "auto"},
        headers={"Authorization": f"Bearer {_token(99)}"},
    )
    assert admin_write.status_code == 404

    monkeypatch.setattr(main.settings, "veyra_auth_enabled", False)
    local_response = client.get(f"/v1/sessions/{legacy.id}/events")
    assert local_response.status_code == 200
    local_write = client.post(
        "/v1/sessions/session_without_owner/messages",
        json={"text": "hello", "target": "auto"},
    )
    assert local_write.status_code == 200


def test_v1_ownerless_public_image_history_remains_visible_when_legacy_session_is_private_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    _enable_auth(monkeypatch)
    legacy = Session(id="ses_legacy_public_history", project_id="legacy", created_at="2026-01-01T00:00:00Z")
    repository.save_session(legacy)
    output_id = "out_public_legacy_session"
    output_path = media_store.output_path(job_id="job_public_legacy_session", output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"public-image")
    media_store.save_history_record({
        "id": output_id,
        "job_id": "job_public_legacy_session",
        "session_id": legacy.id,
        "url": f"/v1/outputs/{output_id}/download",
        "format": "png",
        "created_at": "2026-01-01T00:00:00Z",
    })
    client = TestClient(main.app)

    public_history = client.get(
        f"/v1/image/history?session_id={legacy.id}&limit=10",
        headers={"Authorization": f"Bearer {_token(77)}"},
    )
    legacy_events = client.get(
        f"/v1/sessions/{legacy.id}/events",
        headers={"Authorization": f"Bearer {_token(77)}"},
    )

    assert public_history.status_code == 200
    assert output_id in {item["id"] for item in public_history.json()["items"]}
    assert legacy_events.status_code == 404


def test_v1_session_owner_cannot_be_cleared_or_reassigned(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    session = Session(
        id="ses_owner_immutable",
        project_id="project",
        created_at="2026-01-01T00:00:00Z",
        veyra_user_id=41,
    )
    repository.save_session(session)

    repository.save_session(session.model_copy(update={"veyra_user_id": None}))
    assert repository.get_session(session.id).veyra_user_id == 41

    with pytest.raises(ValueError, match="owner"):
        repository.save_session(session.model_copy(update={"veyra_user_id": 77}))

    legacy = Session(id="ses_legacy_immutable", project_id="legacy", created_at="2026-01-01T00:00:00Z")
    repository.save_session(legacy)
    with pytest.raises(ValueError, match="owner"):
        repository.save_session(legacy.model_copy(update={"veyra_user_id": 41}))
