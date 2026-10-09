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
from fastapi.testclient import TestClient
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
    duplicate_job_id = "job_delete_retry_duplicate"
    duplicate_job = GenerationJob(
        id=duplicate_job_id,
        session_id="session_delete_retry_duplicate",
        job_type="image",
        status=JobStatus.ready,
        trace_id="trace_delete_retry_duplicate",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        outputs=[GenerationOutput(
            id=output_id,
            job_id=duplicate_job_id,
            url=f"/v1/outputs/{output_id}/download",
            metadata={},
        )],
    )
    repository.jobs[duplicate_job_id] = duplicate_job
    duplicate_path = media_store.output_path(
        job_id=duplicate_job_id,
        output_id=output_id,
        output_format="png",
    )
    duplicate_path.parent.mkdir(parents=True, exist_ok=True)
    duplicate_path.write_bytes(b"duplicate private image")
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
    stored_job = repository.get_job("job_delete_atomicity")
    assert stored_job.outputs[0].metadata["veyra_user_id"] == 41
    assert repository.get_job(duplicate_job_id).outputs[0].metadata["veyra_user_id"] == 41

    client = TestClient(main.app)
    non_owner_history = client.get(
        "/v1/image/history?limit=10",
        headers={"Authorization": f"Bearer {_issue_user_token(77)}"},
    )
    assert output_id not in {item["id"] for item in non_owner_history.json()["items"]}

    with pytest.raises(HTTPException) as non_owner:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {_issue_user_token(77)}"))

    assert non_owner.value.status_code == 403
    assert repository.get_output(output_id) is not None

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))
    assert result["ok"] is True
    assert result["removed_repository_output"] is True
    assert repository.get_output(output_id) is None
    assert not duplicate_path.exists()
    assert repository.get_job(duplicate_job_id).outputs == []
    assert list_favorite_ids(veyra_user_id=41, output_ids=[output_id]) == set()
    assert media_store.list_history_records(limit=10) == []
    events = repository.list_events("session_delete_atomicity")
    assert [event["event"] for event in events] == ["generation.output.deleted"]
    assert events[0]["data"]["output_id"] == output_id


def test_v1_history_only_delete_can_retry_after_file_is_gone(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    token = _enable_user_auth(monkeypatch)
    output_id = "out_delete_history_only_retry"
    job_id = "job_delete_history_only_retry"
    output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"image")
    media_store.save_history_record(
        {
            "id": output_id,
            "job_id": job_id,
            "veyra_user_id": 41,
            "url": f"/v1/outputs/{output_id}/download",
            "format": "png",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    set_favorite(output_id, True, veyra_user_id=41)

    original_delete_favorite = main.delete_favorite
    failed_once = False

    def fail_favorite_once(requested_output_id):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
        return original_delete_favorite(requested_output_id)

    monkeypatch.setattr(main, "delete_favorite", fail_favorite_once)
    with pytest.raises(HTTPException) as first_attempt:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert first_attempt.value.status_code == 503
    assert not output_path.exists()
    assert repository.get_output(output_id) is None
    assert list(media_store.iter_history_records(limit=10, include_missing=True))[0]["id"] == output_id
    assert main._v1_output_owner_id(output_id) == 41
    with pytest.raises(HTTPException) as non_owner_during_retry:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {_issue_user_token(77)}"))
    assert non_owner_during_retry.value.status_code == 403

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))
    assert result["ok"] is True
    assert result["removed_history_records"] == 1
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []
    assert list_favorite_ids(veyra_user_id=41, output_ids=[output_id]) == set()


def test_v1_delete_cleans_legacy_duplicate_job_and_file(tmp_path, monkeypatch):
    output_id, canonical_path = _seed_output(tmp_path, monkeypatch)
    token = _enable_user_auth(monkeypatch)
    duplicate_job_id = "job_delete_legacy_duplicate"
    duplicate_job = GenerationJob(
        id=duplicate_job_id,
        session_id="session_delete_legacy_duplicate",
        job_type="image",
        status=JobStatus.ready,
        trace_id="trace_delete_legacy_duplicate",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        outputs=[GenerationOutput(
            id=output_id,
            job_id=duplicate_job_id,
            url=f"/v1/outputs/{output_id}/download",
            metadata={},
        )],
    )
    # Simulate a legacy persisted duplicate that predates save_job's owner merge.
    repository.jobs[duplicate_job_id] = duplicate_job
    duplicate_path = media_store.output_path(
        job_id=duplicate_job_id,
        output_id=output_id,
        output_format="png",
    )
    duplicate_path.parent.mkdir(parents=True, exist_ok=True)
    duplicate_path.write_bytes(b"duplicate private image")

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert result["ok"] is True
    assert not canonical_path.exists()
    assert not duplicate_path.exists()
    assert repository.get_output(output_id) is None
    assert repository.get_job(duplicate_job_id).outputs == []
    response = TestClient(main.app).get(
        f"/v1/outputs/{output_id}/download",
        headers={"Authorization": f"Bearer {_issue_user_token(77)}"},
    )
    assert response.status_code != 200


def test_v1_history_only_delete_removes_legacy_job_projection(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    token = _enable_user_auth(monkeypatch)
    output_id = "out_history_only_job_duplicate"
    job_id = "job_history_only_job_duplicate"
    job = GenerationJob(
        id=job_id,
        session_id="session_history_only_job_duplicate",
        job_type="image",
        status=JobStatus.ready,
        trace_id="trace_history_only_job_duplicate",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        outputs=[GenerationOutput(
            id=output_id,
            job_id=job_id,
            url=f"/v1/outputs/{output_id}/download",
            metadata={},
        )],
    )
    repository.jobs[job_id] = job
    output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"private legacy image")
    media_store.save_history_record({
        "id": output_id,
        "job_id": job_id,
        "veyra_user_id": 41,
        "url": f"/v1/outputs/{output_id}/download",
        "format": "png",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert result["ok"] is True
    assert not output_path.exists()
    assert repository.get_output(output_id) is None
    assert repository.get_job(job_id).outputs == []
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []


def test_v1_history_owner_stays_authoritative_if_legacy_job_cleanup_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    owner_token = _enable_user_auth(monkeypatch)
    output_id = "out_history_owner_cleanup_order"
    job_id = "job_history_owner_cleanup_order"
    job = GenerationJob(
        id=job_id,
        session_id="session_history_owner_cleanup_order",
        job_type="image",
        status=JobStatus.ready,
        trace_id="trace_history_owner_cleanup_order",
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        outputs=[GenerationOutput(
            id=output_id,
            job_id=job_id,
            url=f"/v1/outputs/{output_id}/download",
            metadata={"veyra_user_id": 77},
        )],
    )
    repository.jobs[job_id] = job
    output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"private history-owned image")
    media_store.save_history_record({
        "id": output_id,
        "job_id": job_id,
        "veyra_user_id": 41,
        "url": f"/v1/outputs/{output_id}/download",
        "format": "png",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    original_delete_output = repository.delete_output_with_event
    failed_once = False

    def fail_repository_cleanup_once(requested_output_id):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
        return original_delete_output(requested_output_id)

    monkeypatch.setattr(repository, "delete_output_with_event", fail_repository_cleanup_once)
    with pytest.raises(HTTPException) as failed_owner_delete:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {owner_token}"))
    assert failed_owner_delete.value.status_code == 503

    with pytest.raises(HTTPException) as wrong_owner_retry:
        asyncio.run(main.delete_image_history_item(
            output_id,
            _request(),
            f"Bearer {_issue_user_token(77)}",
        ))
    assert wrong_owner_retry.value.status_code in {403, 404}
    assert main._v1_output_owner_id(output_id) == 41

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {owner_token}"))
    assert result["ok"] is True
    assert repository.get_job(job_id).outputs == []
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []


def test_v1_history_delete_retry_succeeds_after_jsonl_replace_and_sqlite_busy(tmp_path, monkeypatch):
    from app.storage import local as local_module

    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    token = _enable_user_auth(monkeypatch)
    output_id = "out_delete_jsonl_retry"
    job_id = "job_delete_jsonl_retry"
    output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"image")
    media_store.save_history_record(
        {
            "id": output_id,
            "job_id": job_id,
            "veyra_user_id": 41,
            "url": f"/v1/outputs/{output_id}/download",
            "format": "png",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    set_favorite(output_id, True, veyra_user_id=41)

    original_delete = media_store.delete_history_record
    original_connect = local_module.connect
    failed_once = False

    def fail_sqlite_delete_once(requested_output_id: str) -> int:
        nonlocal failed_once
        if failed_once:
            return original_delete(requested_output_id)
        failed_once = True
        connect_calls = 0

        def fail_second_local_connection(path):
            nonlocal connect_calls
            connect_calls += 1
            if connect_calls == 2:
                raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
            return original_connect(path)

        monkeypatch.setattr(local_module, "connect", fail_second_local_connection)
        try:
            return original_delete(requested_output_id)
        finally:
            monkeypatch.setattr(local_module, "connect", original_connect)

    monkeypatch.setattr(media_store, "delete_history_record", fail_sqlite_delete_once)
    with pytest.raises(HTTPException) as first_attempt:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert first_attempt.value.status_code == 503
    assert not output_path.exists()
    assert list(media_store.iter_history_records(limit=10, include_missing=True))[0]["id"] == output_id

    with pytest.raises(HTTPException) as non_owner_retry:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {_issue_user_token(77)}"))
    assert non_owner_retry.value.status_code == 403

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))
    assert result["ok"] is True
    assert result["removed_history_records"] == 1
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []
    assert list_favorite_ids(veyra_user_id=41, output_ids=[output_id]) == set()
