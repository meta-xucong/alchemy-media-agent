from __future__ import annotations

import multiprocessing
import asyncio
import os
import sqlite3
import threading
import time
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreativeRun, FavoriteReferenceAssetRequest
from app.services.generation_capacity import GenerationCapacityExceeded, generation_capacity
from app.services import task_queue as task_queue_service
from app.services import generation_capacity as capacity_module
from app.services import history_scan_capacity as history_scan_module
from app.services.generation_capacity import run_with_generation_capacity
from app.services.task_queue import QueueCapacityExceeded, claim_next_task, enqueue_creative_task, task_queue_stats
from app.services.image_history import list_image_history
from app.main import _read_limited_request_body
from app.main import _require_output_visible, history_reference_asset, output_download
from app.repositories import repository
from app.services import image_history as image_history_service
from app.services import output_storage as output_storage_service
from fastapi import HTTPException
from starlette.requests import Request
import json


def test_v2_history_scan_admission_is_bounded_and_holds_slot_after_cancel(monkeypatch) -> None:
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


def test_v2_async_output_permission_fallback_scans_history_off_event_loop(monkeypatch, tmp_path: Path) -> None:
    started = threading.Event()
    finish = threading.Event()
    monkeypatch.setattr("app.main.settings", replace(settings, veyra_auth_enabled=False))
    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr(repository, "get_output", lambda _output_id: None)

    def slow_lookup(_output_id: str):
        started.set()
        finish.wait(5)
        return None

    monkeypatch.setattr(image_history_service, "get_image_history_item", slow_lookup)
    request = Request({"type": "http", "method": "GET", "path": "/api/v2/outputs/missing", "headers": []})

    async def exercise() -> None:
        lookup = asyncio.create_task(_require_output_visible(request, "missing"))
        assert await asyncio.to_thread(started.wait, 2)
        with pytest.raises(HTTPException) as full:
            await history_scan_module.run_history_scan(lambda: "unexpected")
        assert full.value.status_code == 429
        finish.set()
        result = await lookup
        assert result["owner_id"] is None

    asyncio.run(exercise())


def test_v2_reference_asset_work_uses_bounded_history_admission(monkeypatch) -> None:
    started = threading.Event()
    finish = threading.Event()
    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr("app.main._require_output_visible", _async_public_output)
    monkeypatch.setattr("app.main.list_favorite_ids", lambda **_kwargs: ["favorite-output"])

    def slow_reference(*_args, **_kwargs):
        started.set()
        finish.wait(5)
        return {"asset_id": "asset_fake"}

    monkeypatch.setattr("app.main.create_reference_asset_from_history_output", slow_reference)
    request = Request({"type": "http", "method": "POST", "path": "/api/v2/image/history/favorite-output/reference-asset", "headers": []})
    body = FavoriteReferenceAssetRequest()

    async def exercise() -> None:
        task = asyncio.create_task(history_reference_asset("favorite-output", body, request))
        assert await asyncio.to_thread(started.wait, 2)
        with pytest.raises(HTTPException) as full:
            await history_scan_module.run_history_scan(lambda: "unexpected")
        assert full.value.status_code == 429 and full.value.detail["retryable"] is True
        finish.set()
        assert await task == {"asset_id": "asset_fake"}

    asyncio.run(exercise())


def test_v2_output_download_history_fallback_uses_bounded_scan(monkeypatch) -> None:
    started = threading.Event()
    finish = threading.Event()
    monkeypatch.setattr(history_scan_module, "_slots", threading.BoundedSemaphore(1))
    monkeypatch.setattr("app.main._require_output_visible", _async_public_output)
    monkeypatch.setattr(repository, "get_output", lambda _output_id: None)

    def slow_history_item(_output_id: str):
        started.set()
        finish.wait(5)
        return None

    monkeypatch.setattr(output_storage_service, "_history_item", slow_history_item)
    request = Request({"type": "http", "method": "GET", "path": "/api/v2/outputs/missing/download", "headers": []})

    async def exercise() -> None:
        download = asyncio.create_task(output_download("missing", request))
        assert await asyncio.to_thread(started.wait, 2)
        with pytest.raises(HTTPException) as full:
            await history_scan_module.run_history_scan(lambda: "unexpected")
        assert full.value.status_code == 429 and full.value.detail["retryable"] is True
        finish.set()
        with pytest.raises(HTTPException) as not_found:
            await download
        assert not_found.value.status_code == 404

    asyncio.run(exercise())


async def _async_public_output(*_args, **_kwargs):
    return {"user_id": None, "is_admin": False, "owner_id": None}


def _hold_generation_slot(data_dir: str, acquired, release) -> None:
    with generation_capacity(Path(data_dir) / "queue.sqlite3", limit=1, lease_ttl_seconds=0.5):
        acquired.set()
        release.wait(10)


def _crash_with_generation_slot(data_dir: str, acquired) -> None:
    with generation_capacity(Path(data_dir) / "queue.sqlite3", limit=1, lease_ttl_seconds=0.5):
        acquired.set()
        os._exit(0)


def test_v2_generation_capacity_is_cross_process_and_released_on_exit(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    release = context.Event()
    process = context.Process(target=_hold_generation_slot, args=(str(tmp_path), acquired, release))
    process.start()
    try:
        assert acquired.wait(10)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path / "queue.sqlite3", limit=1, lease_ttl_seconds=0.5):
                pass
    finally:
        release.set()
        process.join(10)
    assert process.exitcode == 0
    with generation_capacity(tmp_path / "queue.sqlite3", limit=1):
        pass


def _queued_run(run_id: str) -> CreativeRun:
    now = utc_now()
    return CreativeRun(
        run_id=run_id,
        status="generating",
        mode="smart_enhance",
        intent_summary="capacity test",
        trace_id=f"trace_{run_id}",
        created_at=now,
        updated_at=now,
    )


def test_v2_pending_queue_limit_is_enforced_transactionally(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.services.task_queue.settings",
        replace(settings, task_queue_db_path=tmp_path / "queue.sqlite3", task_queue_max_pending=1),
    )
    first = _queued_run("run_capacity_1")
    second = _queued_run("run_capacity_2")
    enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "first"}, queued_run=first)
    with pytest.raises(GenerationCapacityExceeded):
        with generation_capacity(tmp_path / "queue.sqlite3", request_kind="direct"):
            pass
    with generation_capacity(tmp_path / "queue.sqlite3", request_kind="worker"):
        pass
    with pytest.raises(QueueCapacityExceeded):
        enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "second"}, queued_run=second)
    assert task_queue_stats()["counts"] == {"queued": 1}


def test_v2_stale_running_task_recovers_same_durable_identity(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(
        "app.services.task_queue.settings",
        replace(settings, task_queue_db_path=database_path, task_queue_max_attempts=3, task_queue_claim_timeout_seconds=0.01),
    )
    run = _queued_run("run_recovery_same_task")
    enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline recovery"}, queued_run=run)
    first = claim_next_task("crashed-worker")
    assert first is not None
    assert first.attempts == 1
    with task_queue_service._connect() as connection:
        stale_locked_at = (utc_now() - timedelta(seconds=1)).isoformat()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, first.task_id),
        )
    recovered = claim_next_task("replacement-worker")
    assert recovered is not None
    assert recovered.task_id == first.task_id
    assert recovered.run_id == first.run_id
    assert recovered.attempts == 2


def test_v2_exhausted_stale_task_is_terminalized_and_releases_direct_priority(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "queue.sqlite3"
    monkeypatch.setattr(
        "app.services.task_queue.settings",
        replace(
            settings,
            task_queue_db_path=database_path,
            task_queue_max_attempts=1,
            task_queue_claim_timeout_seconds=0.01,
            max_concurrent_image_generations=1,
        ),
    )
    run = _queued_run("run_recovery_exhausted")
    enqueue_creative_task(kind="creative_run", request_payload={"user_prompt": "offline recovery"}, queued_run=run)
    claimed = claim_next_task("last-attempt-worker")
    assert claimed is not None
    assert claimed.attempts == claimed.max_attempts == 1
    with task_queue_service._connect() as connection:
        stale_locked_at = (utc_now() - timedelta(seconds=1)).isoformat()
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, claimed.task_id),
        )

    # A dead worker on its final attempt must not hold queue priority forever.
    with task_queue_service.generation_capacity(request_kind="direct"):
        pass

    with task_queue_service._connect() as connection:
        row = connection.execute(
            "SELECT status, error_json, locked_by, locked_at FROM v2_tasks WHERE task_id = ?",
            (claimed.task_id,),
        ).fetchone()
    assert row is not None
    assert row["status"] == "failed"
    assert row["locked_by"] is None and row["locked_at"] is None
    error = json.loads(row["error_json"])
    assert error["error_code"] == "worker_recovery_exhausted"
    assert error["retryable"] is False
    snapshot = task_queue_service.get_run_snapshot(run.run_id)
    assert snapshot is not None and snapshot.status == "failed"
    assert "final allowed attempt" in snapshot.next_actions[0]


def test_v2_capacity_release_after_exception(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError):
        with generation_capacity(tmp_path / "queue.sqlite3", limit=1):
            raise RuntimeError("simulated provider failure")
    with generation_capacity(tmp_path / "queue.sqlite3", limit=1):
        pass


def test_v2_heartbeat_keeps_long_running_slot_active(tmp_path: Path) -> None:
    with generation_capacity(tmp_path / "queue.sqlite3", limit=1, lease_ttl_seconds=0.2):
        time.sleep(0.35)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path / "queue.sqlite3", limit=1, lease_ttl_seconds=0.2):
                pass


def test_v2_crash_lease_waits_for_timeout_before_reuse(tmp_path: Path) -> None:
    context = multiprocessing.get_context("spawn")
    acquired = context.Event()
    process = context.Process(target=_crash_with_generation_slot, args=(str(tmp_path), acquired))
    process.start()
    assert acquired.wait(10)
    process.join(10)
    assert process.exitcode == 0
    with pytest.raises(GenerationCapacityExceeded):
        with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.5):
            pass
    time.sleep(0.55)
    with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.5):
        pass


def test_v2_heartbeat_retries_transient_database_error_without_releasing_slot(tmp_path: Path, monkeypatch) -> None:
    original_connect = capacity_module._connect
    calls = 0

    def fail_one_heartbeat(path: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise sqlite3.OperationalError("temporary heartbeat failure")
        return original_connect(path)

    monkeypatch.setattr(capacity_module, "_connect", fail_one_heartbeat)
    with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.6):
        time.sleep(0.4)
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(tmp_path / "queue.sqlite3", lease_ttl_seconds=0.6):
                pass


def test_v2_cancellation_keeps_slot_until_provider_thread_finishes(tmp_path: Path) -> None:
    started = threading.Event()
    finish_provider = threading.Event()
    database_path = tmp_path / "queue.sqlite3"

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
                database_path=database_path,
                lease_ttl_seconds=1,
            )
        )
        assert await asyncio.to_thread(started.wait, 5)
        task.cancel()
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(GenerationCapacityExceeded):
            with generation_capacity(database_path, lease_ttl_seconds=1):
                pass
        finish_provider.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        with generation_capacity(database_path, lease_ttl_seconds=1):
            pass

    asyncio.run(exercise())


def test_v2_provider_timeout_does_not_prove_remote_work_stopped(tmp_path: Path) -> None:
    remote_still_running = threading.Event()
    finish_remote = threading.Event()
    database_path = tmp_path / "queue.sqlite3"

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
            await run_with_generation_capacity(
                provider_client_timeout,
                database_path=database_path,
                lease_ttl_seconds=1,
            )
        assert remote_still_running.is_set()
        with generation_capacity(database_path, lease_ttl_seconds=1):
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

    return Request({"type": "http", "method": "PUT", "path": "/upload", "headers": headers}, receive)


def test_v2_upload_body_limit_rejects_stream_overflow() -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(_read_limited_request_body(_request_with_body(b"123456"), 5))
    assert error.value.status_code == 413
    assert error.value.detail["error_code"] == "asset_too_large"


def test_v2_history_uses_streaming_read_and_preserves_pagination(tmp_path: Path, monkeypatch) -> None:
    history_path = tmp_path / "history.jsonl"
    original_history_path = settings.image_history_path
    original_data_dir = settings.data_dir
    base = {
        "job_id": "job_history",
        "provider_id": "mock_image",
        "model": "fake",
        "prompt": "test prompt",
        "url": "/fake.png",
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }
    records = [
        {**base, "output_id": f"out_{index}", "created_at": (utc_now() + timedelta(seconds=index)).isoformat()}
        for index in range(3)
    ]
    history_path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")
    object.__setattr__(settings, "image_history_path", history_path)
    object.__setattr__(settings, "data_dir", tmp_path)
    original_read_text = Path.read_text

    def disallow_full_read(path: Path, *args, **kwargs):
        if path == history_path:
            raise AssertionError("history must be read as a stream")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", disallow_full_read)
    try:
        response = list_image_history(limit=1, offset=1)
        assert response.total == 3
        assert len(response.items) == 1
        assert response.items[0].output_id == "out_1"
    finally:
        object.__setattr__(settings, "image_history_path", original_history_path)
        object.__setattr__(settings, "data_dir", original_data_dir)
