from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import json
import time
from threading import Event, Thread

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

    def fail_final_transaction_once(requested_output_id, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
        return original_delete_output(requested_output_id, **kwargs)

    monkeypatch.setattr(repository, "delete_output_with_event", fail_final_transaction_once)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert captured.value.status_code == 503
    assert repository.get_output(output_id) is not None
    assert not output_path.exists()
    assert media_store.list_history_records(limit=10) == []
    assert main._v1_output_owner_id(output_id) == 41
    stored_job = repository.get_job("job_delete_atomicity")
    assert "veyra_user_id" not in stored_job.outputs[0].metadata
    assert "veyra_user_id" not in repository.get_job(duplicate_job_id).outputs[0].metadata

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
    # The canonical row is ownerless and no Job copy explicitly identifies the
    # private owner, so deletion succeeds without publishing the ID to an
    # unverified legacy session.
    assert events == []


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
            metadata={},
        )],
    )
    repository.jobs[job_id] = job
    stale_job_id = "job_history_owner_cleanup_stale_copy"
    stale_job = job.model_copy(
        update={
            "id": stale_job_id,
            "session_id": "session_history_owner_cleanup_stale_copy",
            "outputs": [
                job.outputs[0].model_copy(
                    update={
                        "job_id": stale_job_id,
                        "metadata": {"veyra_user_id": 77},
                    }
                )
            ],
        }
    )
    repository.jobs[stale_job_id] = stale_job
    matching_owner_job_id = "job_history_owner_cleanup_authority"
    matching_owner_job = job.model_copy(
        update={
            "id": matching_owner_job_id,
            "session_id": "session_history_owner_cleanup_authority",
            "outputs": [
                job.outputs[0].model_copy(
                    update={
                        "job_id": matching_owner_job_id,
                        "metadata": {"veyra_user_id": 41},
                    }
                )
            ],
        }
    )
    repository.jobs[matching_owner_job_id] = matching_owner_job
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

    def fail_repository_cleanup_once(requested_output_id, **kwargs):
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
        return original_delete_output(requested_output_id, **kwargs)

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
    assert repository.get_job(stale_job_id).outputs == []
    assert repository.get_job(matching_owner_job_id).outputs == []
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []
    private_session_events = repository.list_events("session_history_owner_cleanup_authority")
    assert [event["event"] for event in private_session_events] == ["generation.output.deleted"]
    assert private_session_events[0]["data"] == {
        "output_id": output_id,
        "job_id": matching_owner_job_id,
    }
    assert repository.list_events("session_history_owner_cleanup_order") == []
    assert repository.list_events("session_history_owner_cleanup_stale_copy") == []


def test_v1_canonical_ownerless_output_routes_delete_event_to_matching_owner_session(tmp_path, monkeypatch):
    output_id, _output_path = _seed_output(tmp_path, monkeypatch, repository_owner=False)
    token = _enable_user_auth(monkeypatch)
    canonical_job = repository.get_job("job_delete_atomicity")

    stale_job_id = "job_canonical_ownerless_stale_copy"
    stale_job = canonical_job.model_copy(
        update={
            "id": stale_job_id,
            "session_id": "session_canonical_ownerless_stale_copy",
            "outputs": [
                canonical_job.outputs[0].model_copy(
                    update={"job_id": stale_job_id, "metadata": {"veyra_user_id": 77}}
                )
            ],
        }
    )
    repository.jobs[stale_job_id] = stale_job

    matching_job_id = "job_canonical_ownerless_matching_owner"
    matching_job = canonical_job.model_copy(
        update={
            "id": matching_job_id,
            "session_id": "session_canonical_ownerless_matching_owner",
            "outputs": [
                canonical_job.outputs[0].model_copy(
                    update={"job_id": matching_job_id, "metadata": {"veyra_user_id": 41}}
                )
            ],
        }
    )
    repository.jobs[matching_job_id] = matching_job

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert result["ok"] is True
    assert repository.get_output(output_id) is None
    assert repository.get_job("job_delete_atomicity").outputs == []
    assert repository.get_job(stale_job_id).outputs == []
    assert repository.get_job(matching_job_id).outputs == []
    matching_events = repository.list_events("session_canonical_ownerless_matching_owner")
    assert [event["event"] for event in matching_events] == ["generation.output.deleted"]
    assert matching_events[0]["data"] == {"output_id": output_id, "job_id": matching_job_id}
    assert repository.list_events("session_delete_atomicity") == []
    assert repository.list_events("session_canonical_ownerless_stale_copy") == []


def test_v1_canonical_explicit_owner_does_not_emit_to_stale_job_session(tmp_path, monkeypatch):
    output_id, _output_path = _seed_output(tmp_path, monkeypatch, repository_owner=True)
    token = _enable_user_auth(monkeypatch)
    canonical_job = repository.get_job("job_delete_atomicity")
    repository.jobs[canonical_job.id] = canonical_job.model_copy(
        update={
            "outputs": [
                canonical_job.outputs[0].model_copy(
                    update={"metadata": {"veyra_user_id": 77}}
                )
            ]
        }
    )

    matching_job_id = "job_canonical_explicit_matching_owner"
    matching_job = canonical_job.model_copy(
        update={
            "id": matching_job_id,
            "session_id": "session_canonical_explicit_matching_owner",
            "outputs": [
                canonical_job.outputs[0].model_copy(
                    update={"job_id": matching_job_id, "metadata": {"veyra_user_id": 41}}
                )
            ],
        }
    )
    repository.jobs[matching_job_id] = matching_job

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert result["ok"] is True
    assert repository.get_output(output_id) is None
    assert repository.list_events("session_delete_atomicity") == []
    assert repository.list_events("session_canonical_explicit_matching_owner") == []


def test_v1_canonical_private_output_does_not_emit_to_ownerless_job_session(tmp_path, monkeypatch):
    output_id, _output_path = _seed_output(tmp_path, monkeypatch, repository_owner=True)
    token = _enable_user_auth(monkeypatch)
    canonical_job = repository.get_job("job_delete_atomicity")
    repository.jobs[canonical_job.id] = canonical_job.model_copy(
        update={
            "outputs": [canonical_job.outputs[0].model_copy(update={"metadata": {}})]
        }
    )

    matching_job_id = "job_canonical_private_explicit_matching_owner"
    matching_job = canonical_job.model_copy(
        update={
            "id": matching_job_id,
            "session_id": "session_canonical_private_explicit_matching_owner",
            "outputs": [
                canonical_job.outputs[0].model_copy(
                    update={"job_id": matching_job_id, "metadata": {"veyra_user_id": 41}}
                )
            ],
        }
    )
    repository.jobs[matching_job_id] = matching_job

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert result["ok"] is True
    assert repository.get_output(output_id) is None
    assert repository.get_job(canonical_job.id).outputs == []
    assert repository.get_job(matching_job_id).outputs == []
    # The canonical Job copy is ownerless, so its session is not proved to
    # belong to canonical owner 41. The current contract suppresses this
    # auxiliary event instead of rerouting it to a duplicate Job session.
    assert repository.list_events(canonical_job.session_id) == []
    assert repository.list_events("session_canonical_private_explicit_matching_owner") == []


def test_v1_canonical_private_output_emits_only_to_explicitly_matching_job_session(tmp_path, monkeypatch):
    output_id, _output_path = _seed_output(tmp_path, monkeypatch, repository_owner=True)
    token = _enable_user_auth(monkeypatch)
    canonical_job = repository.get_job("job_delete_atomicity")

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {token}"))

    assert result["ok"] is True
    events = repository.list_events(canonical_job.session_id)
    assert [event["event"] for event in events] == ["generation.output.deleted"]
    assert events[0]["data"] == {"output_id": output_id, "job_id": canonical_job.id}


def test_v1_delete_keeps_canonical_owner_when_stale_history_cleanup_hits_busy(tmp_path, monkeypatch):
    from app.storage import local as local_module

    output_id, _output_path = _seed_output(tmp_path, monkeypatch, repository_owner=True)
    owner_token = _enable_user_auth(monkeypatch)
    media_store.save_history_record({
        "id": output_id,
        "job_id": "job_delete_atomicity",
        "veyra_user_id": 77,
        "url": f"/v1/outputs/{output_id}/download",
        "format": "png",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    assert main._v1_output_owner_state(output_id) == (41, False)

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
    with pytest.raises(HTTPException) as failed_attempt:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {owner_token}"))
    assert failed_attempt.value.status_code == 503
    assert repository.get_output(output_id) is not None
    assert main._v1_output_owner_state(output_id) == (41, False)

    with pytest.raises(HTTPException) as stale_history_owner:
        asyncio.run(main.delete_image_history_item(
            output_id,
            _request(),
            f"Bearer {_issue_user_token(77)}",
        ))
    assert stale_history_owner.value.status_code == 403

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {owner_token}"))
    assert result["ok"] is True
    assert repository.get_output(output_id) is None
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []


def test_v1_job_only_owner_remains_retryable_when_ownerless_history_cleanup_hits_busy(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    repository.reset()
    owner_token = _enable_user_auth(monkeypatch)
    output_id = "out_job_only_owner_busy_retry"
    job_id = "job_job_only_owner_busy_retry"
    now = datetime.now(timezone.utc).isoformat()
    job = GenerationJob(
        id=job_id,
        session_id="session_job_only_owner_busy_retry",
        job_type="image",
        status=JobStatus.ready,
        trace_id="trace_job_only_owner_busy_retry",
        created_at=now,
        updated_at=now,
        outputs=[GenerationOutput(
            id=output_id,
            job_id=job_id,
            url=f"/v1/outputs/{output_id}/download",
            format="png",
            metadata={"veyra_user_id": 41},
        )],
    )
    # Preserve the pre-canonical legacy shape: owner exists only in Job.outputs,
    # while a separate ownerless manifest must not be mistaken for an owner anchor.
    repository.jobs[job_id] = job
    ownerless_duplicate_job = GenerationJob(
        id="job_job_only_ownerless_duplicate",
        session_id="session_job_only_ownerless_duplicate",
        job_type="image",
        status="ready",
        trace_id="trace_job_only_ownerless_duplicate",
        created_at=now,
        updated_at=now,
        outputs=[GenerationOutput(
            id=output_id,
            job_id="job_job_only_ownerless_duplicate",
            url=f"/v1/outputs/{output_id}/download",
            format="png",
            metadata={},
        )],
    )
    repository.jobs[ownerless_duplicate_job.id] = ownerless_duplicate_job
    output_path = media_store.output_path(job_id=job_id, output_id=output_id, output_format="png")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"legacy private image")
    media_store.save_history_record({
        "id": output_id,
        "job_id": job_id,
        "url": f"/v1/outputs/{output_id}/download",
        "format": "png",
        "created_at": now,
    })
    original_delete_history = media_store.delete_history_record
    failed_once = False

    def fail_history_delete_once(requested_output_id: str) -> int:
        nonlocal failed_once
        if not failed_once:
            failed_once = True
            raise SQLiteStorageBusy("SQLite database is busy; retry shortly.")
        return original_delete_history(requested_output_id)

    monkeypatch.setattr(media_store, "delete_history_record", fail_history_delete_once)
    with pytest.raises(HTTPException) as failed_attempt:
        asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {owner_token}"))
    assert failed_attempt.value.status_code == 503
    assert repository.get_job(job_id) is not None
    assert main._v1_output_owner_state(output_id) == (41, False)
    with pytest.raises(HTTPException) as wrong_owner_retry:
        asyncio.run(main.delete_image_history_item(
            output_id,
            _request(),
            f"Bearer {_issue_user_token(77)}",
        ))
    assert wrong_owner_retry.value.status_code == 403

    result = asyncio.run(main.delete_image_history_item(output_id, _request(), f"Bearer {owner_token}"))
    assert result["ok"] is True
    assert result["removed_repository_output"] is True
    assert repository.get_job(job_id).outputs == []
    assert repository.get_job(ownerless_duplicate_job.id).outputs == []
    assert list(media_store.iter_history_records(limit=10, include_missing=True)) == []
    events = repository.list_events("session_job_only_owner_busy_retry")
    assert [event["event"] for event in events] == ["generation.output.deleted"]
    assert events[0]["data"] == {"output_id": output_id, "job_id": job_id}
    assert repository.list_events("session_job_only_ownerless_duplicate") == []


def test_v1_delete_does_not_remove_unrelated_empty_job_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    output_id = "out_remove_one_job_directory"
    target_path = media_store.output_path(
        job_id="job_delete_target",
        output_id=output_id,
        output_format="png",
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(b"target")
    active_job_directory = media_store.generated_root / "job_active_before_first_write"
    active_job_directory.mkdir(parents=True)

    assert media_store.delete_output_file(
        output_id=output_id,
        job_id="job_delete_target",
        output_format="png",
    ) is True
    assert not target_path.exists()
    assert target_path.parent.is_dir()
    assert active_job_directory.is_dir()
    active_output = active_job_directory / "out_active.png"
    active_output.write_bytes(b"active generation output")
    assert active_output.read_bytes() == b"active generation output"


def test_v1_delete_does_not_remove_shared_directory_while_output_write_is_paused(tmp_path, monkeypatch):
    from pathlib import Path

    monkeypatch.setattr(media_store, "root", tmp_path)
    job_id = "job_shared_active_write"
    target_id = "out_delete_shared_directory"
    writing_id = "out_write_shared_directory"
    target_path = media_store.output_path(job_id=job_id, output_id=target_id, output_format="png")
    writing_path = media_store.output_path(job_id=job_id, output_id=writing_id, output_format="png")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(b"target")
    monkeypatch.setattr(media_store, "ensure_thumbnail", lambda **_kwargs: None)
    monkeypatch.setattr(media_store, "ensure_preview", lambda **_kwargs: None)

    original_write_bytes = Path.write_bytes
    write_paused = Event()
    resume_write = Event()
    writer_errors: list[BaseException] = []

    def pause_before_active_write(path: Path, content: bytes) -> int:
        if path == writing_path:
            write_paused.set()
            if not resume_write.wait(timeout=5):
                raise TimeoutError("test did not resume the active output write")
        return original_write_bytes(path, content)

    monkeypatch.setattr(Path, "write_bytes", pause_before_active_write)

    def write_output() -> None:
        try:
            media_store.save_base64_output(
                job_id=job_id,
                output_id=writing_id,
                b64_json="bmV3IG91dHB1dA==",
                output_format="png",
            )
        except BaseException as exc:
            writer_errors.append(exc)

    writer = Thread(target=write_output)
    writer.start()
    try:
        assert write_paused.wait(timeout=5)
        assert media_store.delete_output_file(
            output_id=target_id,
            job_id=job_id,
            output_format="png",
        ) is True
    finally:
        resume_write.set()
        writer.join(timeout=5)

    assert not writer.is_alive()
    assert writer_errors == []
    assert writing_path.read_bytes() == b"new output"


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
