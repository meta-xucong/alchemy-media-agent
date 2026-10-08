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
from starlette.requests import Request

from app.services.generation_capacity import GenerationCapacityExceeded, generation_capacity
from app.services import generation_capacity as capacity_module
from app.services.generation_capacity import run_with_generation_capacity
from app.services import history_scan_capacity as history_scan_module
from app.main import _read_limited_request_body
import app.services.alchemy_lab as alchemy_lab
import app.services.image_service as image_service
from app.repositories import repository
from app.schemas import JobStatus, ProviderError


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
        first.cancel()
        await asyncio.sleep(0.03)
        with pytest.raises(HTTPException):
            await history_scan_module.run_history_scan(lambda: "unexpected")
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await first
        assert await history_scan_module.run_history_scan(lambda: "available") == "available"

    asyncio.run(exercise())


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
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path, lease_ttl_seconds=1):
                pass
        finish_provider.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        with generation_capacity(tmp_path, lease_ttl_seconds=1):
            pass

    asyncio.run(exercise())


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
        alchemy_lab._schedule_exploration_session("lab_active_1")
        await asyncio.sleep(0)
        with pytest.raises(GenerationCapacityExceeded):
            alchemy_lab._schedule_exploration_session("lab_active_2")
        active = list(alchemy_lab._background_tasks)
        release.set()
        await asyncio.gather(*active)
        with generation_capacity(tmp_path, limit=1, namespace="lab-session"):
            pass

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
