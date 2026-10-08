from __future__ import annotations

import asyncio
import multiprocessing
import os
import sqlite3
import threading
import time
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.services.generation_capacity import GenerationCapacityExceeded, generation_capacity
from app.services import generation_capacity as capacity_module
from app.services.generation_capacity import run_with_generation_capacity
from app.services import history_scan_capacity as history_scan_module
from app.main import app as v1_app
import app.main as main_module
from app.main import _read_limited_request_body, _require_output_visible, delete_image_history_item, favorite_image_history_item
from app.config import settings
import app.services.alchemy_lab as alchemy_lab
import app.services.image_service as image_service
from app.repositories import repository
from app.schemas import FavoriteImageRequest, JobStatus, ProviderError
from app.main import media_store


def test_v1_history_scan_admission_is_bounded_and_holds_slot_after_cancel(monkeypatch) -> None:
    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    started = threading.Event()
    finish = threading.Event()

    def slow_scan() -> str:
        started.set()
        finish.wait(5)
        return "done"

    async def exercise() -> None:
        first = asyncio.create_task(history_scan_module.run_history_scan(slow_scan))
        assert await asyncio.to_thread(started.wait, 2)
        with pytest.raises(HTTPException) as full:
            await history_scan_module.run_history_scan(lambda: "unexpected")
        assert full.value.status_code == 429
        assert full.value.detail["retryable"] is True
        first.cancel()
        await asyncio.sleep(0.03)
        with pytest.raises(HTTPException):
            await history_scan_module.run_history_scan(lambda: "unexpected")
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await history_scan_module.run_history_scan(lambda: "available") == "available"

    asyncio.run(exercise())


def test_v1_repo_miss_permission_and_favorite_history_fallback_use_scan_capacity(monkeypatch) -> None:
    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr("app.main.settings", settings.model_copy(update={"veyra_auth_enabled": False}))
    monkeypatch.setattr(repository, "get_output", lambda _output_id: None)
    monkeypatch.setattr(
        "app.main.set_favorite",
        lambda output_id, favorite, veyra_user_id=None: {
            "output_id": output_id,
            "favorite": favorite,
            "veyra_user_id": veyra_user_id,
        },
    )
    request = Request({"type": "http", "method": "PUT", "path": "/v1/image/history/out_repo_miss/favorite", "headers": []})
    calls = 0
    started = threading.Event()
    finish = threading.Event()
    records = [{"id": "out_repo_miss", "veyra_user_id": 17}]

    def list_records(*, limit=10000, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            started.set()
            finish.wait(5)
        return records[:limit]

    monkeypatch.setattr(media_store, "list_history_records", list_records)

    async def exercise() -> None:
        owner_lookup = asyncio.create_task(_require_output_visible(request, "out_repo_miss"))
        assert await asyncio.to_thread(started.wait, 2)
        with pytest.raises(HTTPException) as full:
            await history_scan_module.run_history_scan(lambda: None)
        assert full.value.status_code == 429 and full.value.detail["retryable"] is True
        finish.set()
        owner = await owner_lookup
        assert owner["owner_id"] == 17
        favorite = await favorite_image_history_item("out_repo_miss", FavoriteImageRequest(), request)
        assert favorite == {"output_id": "out_repo_miss", "favorite": True, "veyra_user_id": None}
        assert calls >= 3

    asyncio.run(exercise())


def test_v1_history_delete_rejection_precedes_all_mutations(monkeypatch) -> None:
    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr("app.main._require_output_visible", _async_public_output_v1)
    request = Request({"type": "http", "method": "DELETE", "path": "/v1/image/history/out_busy", "headers": []})
    before = {"repository_output": True, "history_record": True, "original": True, "thumbnail": True, "preview": True}
    after = dict(before)

    def simulate_delete(_output_id: str):
        after.update({key: False for key in after})
        return {"ok": True}

    monkeypatch.setattr("app.main._delete_v1_image_history_item_sync", simulate_delete)

    async def exercise() -> None:
        slot = history_scan_module._slots
        assert slot.acquire(blocking=False)
        try:
            with pytest.raises(HTTPException) as full:
                await delete_image_history_item("out_busy", request)
            assert full.value.status_code == 429 and full.value.detail["retryable"] is True
            assert after == before
        finally:
            slot.release()

    asyncio.run(exercise())


async def _async_public_output_v1(*_args, **_kwargs):
    return {"authenticated": False, "user_id": None, "is_admin": False, "owner_id": None}


def _hold_generation_slot(root: str, acquired, release) -> None:
    with generation_capacity(Path(root), limit=1, lease_ttl_seconds=0.5):
        acquired.set()
        release.wait(10)


def _crash_with_generation_slot(root: str, acquired) -> None:
    with generation_capacity(Path(root), limit=1, lease_ttl_seconds=0.5):
        acquired.set()
        os._exit(0)


def test_v1_generation_capacity_is_cross_process_and_released_on_exit(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    release = context.Event()
    process = context.Process(target=_hold_generation_slot, args=(str(tmp_path), acquired, release))
    process.start()
    try:
        assert acquired.wait(10)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path, limit=1, lease_ttl_seconds=0.5):
                pass
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0
    with generation_capacity(tmp_path, limit=1):
        pass


def test_v1_heartbeat_keeps_long_running_slot_active(tmp_path: Path) -> None:
    with generation_capacity(tmp_path, limit=1, lease_ttl_seconds=0.2):
        time.sleep(0.35)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path, limit=1, lease_ttl_seconds=0.2):
                pass


def test_v1_crash_lease_waits_for_timeout_before_reuse(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    process = context.Process(target=_crash_with_generation_slot, args=(str(tmp_path), acquired))
    process.start()
    assert acquired.wait(10)
    process.join(10)
    assert process.exitcode == 0
    with pytest.raises(GenerationCapacityExceeded):
        with generation_capacity(tmp_path, lease_ttl_seconds=0.5):
            pass
    time.sleep(0.55)
    with generation_capacity(tmp_path, lease_ttl_seconds=0.5):
        pass


def test_v1_heartbeat_retries_transient_database_error_without_releasing_slot(tmp_path: Path, monkeypatch) -> None:
    original_connect = capacity_module._connect
    calls = 0

    def fail_one_heartbeat(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("temporary heartbeat failure")
        return original_connect(path)

    monkeypatch.setattr(capacity_module, "_connect", fail_one_heartbeat)
    with generation_capacity(tmp_path, lease_ttl_seconds=0.6):
        time.sleep(0.4)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path, lease_ttl_seconds=0.6):
                pass


def test_v1_cancellation_keeps_slot_until_provider_thread_finishes(tmp_path: Path) -> None:
    started = threading.Event()
    finish_provider = threading.Event()

    def fake_blocking_provider() -> str:
        started.set()
        finish_provider.wait(10)
        return "done"

    async def provider_operation() -> str:
        return await asyncio.to_thread(fake_blocking_provider)

    async def exercise() -> None:
        task = asyncio.create_task(
            run_with_generation_capacity(
                provider_operation,
                root=tmp_path,
                lease_ttl_seconds=1,
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path, lease_ttl_seconds=1):
                pass
        finish_provider.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        with generation_capacity(tmp_path, lease_ttl_seconds=1):
            pass

    asyncio.run(exercise())


def test_v1_async_admission_keeps_loop_responsive_during_sqlite_write_lock(tmp_path: Path, monkeypatch) -> None:
    with generation_capacity(tmp_path):
        pass
    database_path = tmp_path / ".v1-resource-admission.sqlite3"
    lock_connection = sqlite3.connect(database_path, timeout=5, isolation_level=None, check_same_thread=False)
    lock_connection.execute("BEGIN IMMEDIATE")
    reserve_started = threading.Event()
    original_reserve = capacity_module._reserve

    def observed_reserve(*args, **kwargs):
        reserve_started.set()
        return original_reserve(*args, **kwargs)

    monkeypatch.setattr(capacity_module, "_reserve", observed_reserve)
    calls = 0

    async def provider() -> str:
        nonlocal calls
        calls += 1
        return "fake-complete"

    async def exercise() -> None:
        admission = asyncio.create_task(
            run_with_generation_capacity(provider, root=tmp_path, limit=1, lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(reserve_started.wait, 2)
        loop_ticked = asyncio.Event()
        asyncio.get_running_loop().call_soon(loop_ticked.set)
        await asyncio.wait_for(loop_ticked.wait(), timeout=1)
        lock_connection.rollback()
        assert await admission == "fake-complete"

    try:
        asyncio.run(exercise())
    finally:
        lock_connection.close()
    assert calls == 1


def test_v1_cancellation_during_acquire_releases_late_lease(tmp_path: Path, monkeypatch) -> None:
    acquire_started = threading.Event()
    continue_acquire = threading.Event()
    original_reserve = capacity_module._reserve

    def held_reserve(*args, **kwargs):
        acquire_started.set()
        assert continue_acquire.wait(3)
        return original_reserve(*args, **kwargs)

    monkeypatch.setattr(capacity_module, "_reserve", held_reserve)
    provider_calls = 0

    async def provider() -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "unexpected"

    async def exercise() -> None:
        task = asyncio.create_task(
            run_with_generation_capacity(provider, root=tmp_path, limit=1, lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(acquire_started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        continue_acquire.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert provider_calls == 0
    with capacity_module._database(tmp_path / ".v1-resource-admission.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM resource_leases").fetchone()[0] == 0


def test_v1_cancellation_during_cleanup_waits_for_release(tmp_path: Path, monkeypatch) -> None:
    cleanup_started = threading.Event()
    continue_cleanup = threading.Event()
    original_release = capacity_module.GenerationLease._release_sync
    provider_calls = 0

    def held_release(lease):
        cleanup_started.set()
        assert continue_cleanup.wait(3)
        return original_release(lease)

    monkeypatch.setattr(capacity_module.GenerationLease, "_release_sync", held_release)

    async def provider() -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "created-once"

    async def exercise() -> None:
        task = asyncio.create_task(
            run_with_generation_capacity(provider, root=tmp_path, limit=1, lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(cleanup_started.wait, 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        continue_cleanup.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(exercise())
    assert provider_calls == 1
    with capacity_module._database(tmp_path / ".v1-resource-admission.sqlite3") as connection:
        assert connection.execute("SELECT COUNT(*) FROM resource_leases").fetchone()[0] == 0


def test_v1_successful_provider_is_not_retried_when_lease_cleanup_fails(tmp_path: Path, monkeypatch) -> None:
    provider_calls = 0

    def failed_cleanup(_lease):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(capacity_module.GenerationLease, "_release_sync", failed_cleanup)

    async def provider() -> str:
        nonlocal provider_calls
        provider_calls += 1
        return "created-once"

    result = asyncio.run(run_with_generation_capacity(provider, root=tmp_path, limit=1, lease_ttl_seconds=10))
    assert result == "created-once"
    assert provider_calls == 1


def test_v1_cleanup_waits_for_bounded_database_permit_without_blocking_loop(tmp_path: Path, monkeypatch) -> None:
    class Gate:
        def __init__(self):
            self.semaphore = threading.BoundedSemaphore(1)
            self.blocked = False
            self.waiting = threading.Event()

        def acquire(self, blocking=False):
            if self.blocked:
                self.waiting.set()
                return False
            return self.semaphore.acquire(blocking=blocking)

        def release(self):
            self.semaphore.release()

    gate = Gate()
    monkeypatch.setattr(capacity_module, "_ASYNC_DB_SLOTS", gate)

    async def provider() -> str:
        gate.blocked = True
        return "created-once"

    async def exercise() -> str:
        task = asyncio.create_task(
            run_with_generation_capacity(provider, root=tmp_path, limit=1, lease_ttl_seconds=10)
        )
        assert await asyncio.to_thread(gate.waiting.wait, 2)
        gate.blocked = False
        return await task

    assert asyncio.run(exercise()) == "created-once"


def test_v1_async_sqlite_offload_is_bounded_and_permit_survives_cancellation(monkeypatch) -> None:
    monkeypatch.setattr(capacity_module, "_ASYNC_DB_SLOTS", threading.BoundedSemaphore(1))
    worker_started = threading.Event()
    finish_worker = threading.Event()

    def blocking_operation() -> str:
        worker_started.set()
        assert finish_worker.wait(3)
        return "done"

    async def exercise() -> None:
        first = asyncio.create_task(capacity_module.run_sqlite_async(blocking_operation))
        assert await asyncio.to_thread(worker_started.wait, 2)
        with pytest.raises(capacity_module.GenerationCapacityStorageBusy):
            await capacity_module.run_sqlite_async(lambda: "should-not-run")
        first.cancel()
        await asyncio.sleep(0)
        with pytest.raises(capacity_module.GenerationCapacityStorageBusy):
            await capacity_module.run_sqlite_async(lambda: "permit-was-released-too-early")
        finish_worker.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await capacity_module.run_sqlite_async(lambda: "available") == "available"

    asyncio.run(exercise())


def test_v1_session_image_capacity_is_retryable_and_does_not_block_chat_or_video(tmp_path: Path, monkeypatch) -> None:
    repository.reset()
    monkeypatch.setattr(media_store, "root", tmp_path)
    monkeypatch.setattr(image_service.settings, "llm_prompt_planning_enabled", False)
    provider_calls = 0

    async def unexpected_provider_call(*_args, **_kwargs):
        nonlocal provider_calls
        provider_calls += 1
        raise AssertionError("capacity rejection must happen before provider execution")

    monkeypatch.setattr(image_service, "_run_image_request", unexpected_provider_call)
    client = TestClient(v1_app, raise_server_exceptions=False)
    created = client.post("/v1/sessions", json={"project_id": "resource-guard", "title": "Capacity"})
    assert created.status_code == 200
    session_id = created.json()["id"]
    before_jobs = repository.list_jobs(job_type="image", session_id=session_id)

    with generation_capacity(tmp_path, limit=1):
        image = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"target": "image", "text": "Make a simple image", "preferences": {"count": 1}},
        )
        assert image.status_code == 429
        assert image.headers["retry-after"] == "5"
        assert image.json()["detail"]["code"] == "generation_capacity"
        assert image.json()["detail"]["retryable"] is True
        assert repository.list_jobs(job_type="image", session_id=session_id) == before_jobs
        assert provider_calls == 0

        chat = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"target": "auto", "text": "Hello", "preferences": {}},
        )
        video = client.post(
            f"/v1/sessions/{session_id}/messages",
            json={"target": "video", "text": "Create a video", "preferences": {}},
        )
        assert chat.status_code == 200 and chat.json()["job_ids"] == []
        assert video.status_code == 200 and video.json()["job_ids"] == []
        assert provider_calls == 0

    slots = threading.BoundedSemaphore(1)
    assert slots.acquire(blocking=False)
    monkeypatch.setattr(capacity_module, "_ASYNC_DB_SLOTS", slots)
    busy = client.post(
        f"/v1/sessions/{session_id}/messages",
        json={"target": "image", "text": "Make a simple image", "preferences": {"count": 1}},
    )
    assert busy.status_code == 503
    assert busy.headers["retry-after"] == "5"
    assert busy.json()["detail"]["code"] == "local_database_busy"
    assert busy.json()["detail"]["retryable"] is True
    assert repository.list_jobs(job_type="image", session_id=session_id) == before_jobs
    assert provider_calls == 0
    slots.release()

    repository.reset()


def test_v1_provider_timeout_does_not_prove_remote_work_stopped(tmp_path: Path) -> None:
    remote_still_running = threading.Event()
    finish_remote = threading.Event()

    def fake_remote_operation() -> None:
        remote_still_running.set()
        finish_remote.wait(10)

    async def provider_client_timeout() -> None:
        asyncio.create_task(asyncio.to_thread(fake_remote_operation))
        while not remote_still_running.is_set():
            await asyncio.sleep(0.01)
        raise TimeoutError("client deadline elapsed")

    async def exercise() -> None:
        with pytest.raises(TimeoutError):
            await run_with_generation_capacity(provider_client_timeout, root=tmp_path, lease_ttl_seconds=1)
        assert remote_still_running.is_set()
        # The local provider coroutine ended, while the fake remote work remains
        # unobservable. This demonstrates why the lease is not a remote cap.
        with generation_capacity(tmp_path, lease_ttl_seconds=1):
            pass
        finish_remote.set()

    asyncio.run(exercise())


def _request_with_body(body: bytes, *, content_length: str | None = None) -> Request:
    headers = []
    if content_length is not None:
        headers.append((b"content-length", content_length.encode("ascii")))
    sent = False

    async def receive():
        nonlocal sent
        if sent:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "PUT", "path": "/upload", "headers": headers}
    return Request(scope, receive)


def test_v1_limited_body_rejects_oversized_declared_length_before_read() -> None:
    request = _request_with_body(b"ignored", content_length="9")
    with pytest.raises(HTTPException) as error:
        asyncio.run(_read_limited_request_body(request, 8))
    assert error.value.status_code == 413
    assert error.value.detail["code"] == "asset_too_large"


def test_v1_limited_body_rejects_chunked_overflow() -> None:
    request = _request_with_body(b"123456789")
    with pytest.raises(HTTPException) as error:
        asyncio.run(_read_limited_request_body(request, 8))
    assert error.value.status_code == 413


def test_v1_limited_body_accepts_boundary_size() -> None:
    request = _request_with_body(b"12345678", content_length="8")
    assert asyncio.run(_read_limited_request_body(request, 8)) == b"12345678"


def test_lab_limits_active_sessions_and_releases_slot_on_completion(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(alchemy_lab.media_store, "root", tmp_path)
    release = asyncio.Event()

    async def hold_session(*args, **kwargs):
        await release.wait()

    monkeypatch.setattr(alchemy_lab, "_run_exploration_session_guarded", hold_session)

    async def exercise() -> None:
        await alchemy_lab._schedule_exploration_session("lab_active_1")
        await asyncio.sleep(0)
        with pytest.raises(GenerationCapacityExceeded):
            await alchemy_lab._schedule_exploration_session("lab_active_2")
        active = list(alchemy_lab._background_tasks)
        release.set()
        await asyncio.gather(*active)
        with generation_capacity(tmp_path, limit=1, namespace="lab-session"):
            pass

    asyncio.run(exercise())


def test_lab_history_route_offloads_and_rejects_when_scan_capacity_is_full(monkeypatch) -> None:
    from app.main import list_alchemy_lab_history
    from starlette.requests import Request

    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    started = threading.Event()
    finish = threading.Event()
    observed: list[tuple[int | None, bool, int]] = []

    def slow_history(*, limit, include_mock, veyra_user_id, is_admin):
        observed.append((veyra_user_id, is_admin, threading.get_ident()))
        started.set()
        assert finish.wait(5)
        return {"items": [], "total": limit}

    async def history_context(_request, _authorization):
        return {"user_id": 23, "is_admin": False}

    monkeypatch.setattr(main_module, "list_lab_history", slow_history)
    monkeypatch.setattr(main_module, "_veyra_history_context", history_context)
    request = Request({"type": "http", "method": "GET", "path": "/api/lab/history", "headers": []})

    async def exercise() -> None:
        event_loop_thread = threading.get_ident()
        first = asyncio.create_task(
            list_alchemy_lab_history(request, limit=80, include_mock=True, authorization="test")
        )
        assert await asyncio.to_thread(started.wait, 2)
        loop_ticked = asyncio.Event()
        asyncio.get_running_loop().call_soon(loop_ticked.set)
        await asyncio.wait_for(loop_ticked.wait(), timeout=1)
        with pytest.raises(HTTPException) as full:
            await list_alchemy_lab_history(request, limit=80, include_mock=True, authorization="test")
        assert full.value.status_code == 429
        assert full.value.detail["retryable"] is True
        finish.set()
        response = await first
        assert response == {"items": [], "total": 80}
        assert len(observed) == 1
        assert observed[0][:2] == (23, False)
        assert observed[0][2] != event_loop_thread

    asyncio.run(exercise())


def test_v1_retryable_capacity_failure_reuses_idempotent_job(tmp_path: Path, monkeypatch) -> None:
    repository.reset()
    monkeypatch.setattr(image_service.media_store, "root", tmp_path)
    monkeypatch.setattr(image_service.settings, "llm_prompt_planning_enabled", False)

    async def exercise():
        first = await image_service.submit_image_job(
            session_id="session_capacity_retry",
            prompt="A simple offline fake image job",
            idempotency_key="capacity-retry-key",
        )
        first.job.status = JobStatus.failed
        first.job.error = ProviderError(
            code="generation_capacity",
            message="Image generation is busy. Please retry shortly.",
            retryable=True,
            detail={"retry_after_seconds": 5},
        )
        repository.save_job(first.job)
        retried = await image_service.submit_image_job(
            session_id="session_capacity_retry",
            prompt="A simple offline fake image job",
            idempotency_key="capacity-retry-key",
        )
        assert retried.job.id == first.job.id
        assert retried.request is not None
        assert retried.job.status == JobStatus.generating
        assert retried.job.error is None
        retried.job.status = JobStatus.failed
        retried.job.error = ProviderError(
            code="generation_capacity",
            message="Image generation is busy. Please retry shortly.",
            retryable=True,
            detail={"retry_after_seconds": 5},
        )
        repository.save_job(retried.job)
        changed_payload = await image_service.submit_image_job(
            session_id="session_capacity_retry",
            prompt="A different fake image request",
            idempotency_key="capacity-retry-key",
        )
        assert changed_payload.job.id == first.job.id
        assert changed_payload.request is None
        assert changed_payload.job.status == JobStatus.failed

    asyncio.run(exercise())
    repository.reset()
