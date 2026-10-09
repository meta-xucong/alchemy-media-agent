from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app import main
from app.repositories import repository
from app.repositories.sqlite_calls import SQLiteStorageBusy, sqlite_calls
from app.schemas import GenerationJob, GenerationOutput, JobStatus
from app.services.favorites import list_favorite_ids, set_favorite
from app.storage import media_store


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": "DELETE",
            "scheme": "http",
            "path": "/v1/image/history/out_delete_atomicity",
            "raw_path": b"/v1/image/history/out_delete_atomicity",
            "query_string": b"",
            "headers": [],
            "server": ("testserver", 80),
            "client": ("testclient", 123),
        }
    )


def _seed_output(tmp_path, monkeypatch, *, repository_owner: bool = True) -> tuple[str, object]:
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    output_id = "out_delete_atomicity"
    job_id = "job_delete_atomicity"
    now = datetime.now(timezone.utc).isoformat()
    output = GenerationOutput(
        id=output_id,
        job_id=job_id,
        url=f"/v1/outputs/{output_id}/download",
        thumbnail_url=f"/v1/outputs/{output_id}/thumbnail",
        preview_url=f"/v1/outputs/{output_id}/preview",
        metadata={"veyra_user_id": 41} if repository_owner else {},
    )
    job = GenerationJob(
        id=job_id,
        session_id="session_delete_atomicity",
        job_type="image",
        status=JobStatus.ready,
        trace_id="trace_delete_atomicity",
        created_at=now,
        updated_at=now,
        outputs=[output],
    )
    repository.save_job(job)
    output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"image")
    for path in (media_store.thumbnail_path(output_id), media_store.preview_path(output_id)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"derived")
    media_store.save_history_record(
        {
            "id": output_id,
            "job_id": job_id,
            "veyra_user_id": 41,
            "url": output.url,
            "format": "png",
            "created_at": now,
        }
    )
    set_favorite(output_id, True, veyra_user_id=41)
    return output_id, output_path


def _issue_user_token(user_id: int) -> str:
    now = int(time.time())
    payload = base64.urlsafe_b64encode(
        json.dumps({"user_id": user_id, "iat": now, "exp": now + 3600}, separators=(",", ":"), sort_keys=True).encode()
    ).decode().rstrip("=")
    signature = base64.urlsafe_b64encode(
        hmac.new(b"history-delete-test-secret", payload.encode(), hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{payload}.{signature}"


def _enable_user_auth(monkeypatch) -> str:
    monkeypatch.setattr(main.settings, "veyra_auth_enabled", True)
    monkeypatch.setattr(main.settings, "veyra_session_secret", "history-delete-test-secret")

    async def load_account(user_id: int):
        return type("Account", (), {"user_id": user_id, "role": "user"})()

    monkeypatch.setattr(main, "load_account", load_account)
    return _issue_user_token(41)


def test_v1_delete_capacity_rejection_happens_before_any_cleanup(tmp_path, monkeypatch):
    output_id, output_path = _seed_output(tmp_path, monkeypatch, repository_owner=False)
    token = _enable_user_auth(monkeypatch)
    original_run = sqlite_calls.run
    rejected = False

    async def reject_delete_bundle(function, *args, **kwargs):
        nonlocal rejected
        if getattr(function, "__name__", "") == "_delete_v1_history_output_bundle":
            rejected = True
            raise SQLiteStorageBusy("SQLite worker capacity is busy.", capacity_full=True)
        return await original_run(function, *args, **kwargs)

    monkeypatch.setattr(sqlite_calls, "run", reject_delete_bundle)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert captured.value.status_code == 503
    assert rejected
    assert repository.get_output(output_id) is not None
    assert output_path.exists()
    assert media_store.thumbnail_path(output_id).exists()
    assert media_store.preview_path(output_id).exists()
    assert list_favorite_ids(veyra_user_id=41, output_ids=[output_id]) == {output_id}
    assert [row["id"] for row in media_store.list_history_records(limit=10)] == [output_id]


def test_v1_delete_mid_cleanup_failure_keeps_owner_anchor_for_retry(tmp_path, monkeypatch):
    output_id, output_path = _seed_output(tmp_path, monkeypatch, repository_owner=False)
    token = _enable_user_auth(monkeypatch)
    original_delete_output = repository.delete_output_with_event
    failed_once = False

    def fail_final_transaction_once(requested_output_id):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
        return original_delete_output(requested_output_id)

    monkeypatch.setattr(repository, "delete_output_with_event", fail_final_transaction_once)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert captured.value.status_code == 503
    assert repository.get_output(output_id) is not None
    assert not output_path.exists()
    assert media_store.list_history_records(limit=10) == []
    assert main._v1_output_owner_id(output_id) == 41

    with pytest.raises(HTTPException) as non_owner:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {_issue_user_token(77)}"))

    assert non_owner.value.status_code == 403
    assert repository.get_output(output_id) is not None

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))
    assert result["ok"] is True
    assert result["removed_repository_output"] is True
    assert repository.get_output(output_id) is None
    assert list_favorite_ids(veyra_user_id=41, output_ids=[output_id]) == set()
    assert media_store.list_history_records(limit=10) == []
    events = repository.list_events("session_delete_atomicity")
    assert [event["event"] for event in events] == ["generation.output.deleted"]
    assert events[0]["data"]["output_id"] == output_id
