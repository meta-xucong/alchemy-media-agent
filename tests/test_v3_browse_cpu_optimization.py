from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading
import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import src_skeleton.app.main as app_main


def test_bounded_header_worker_allows_one_active_two_waiting_and_rejects_fourth(monkeypatch) -> None:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-v3-header")
    monkeypatch.setattr(app_main, "_v3_browse_header_executor", executor)
    with app_main._v3_browse_header_gate_lock:  # noqa: SLF001
        app_main._v3_browse_header_admitted = 0  # noqa: SLF001
        app_main._v3_browse_header_active = 0  # noqa: SLF001

    entered = threading.Event()
    release = threading.Event()
    state_lock = threading.Lock()
    active = 0
    peak_active = 0

    def slow_scan(value):
        nonlocal active, peak_active
        with state_lock:
            active += 1
            peak_active = max(peak_active, active)
        if value == 1:
            entered.set()
            assert release.wait(timeout=5)
        time.sleep(0.01)
        with state_lock:
            active -= 1
        return value

    async def exercise():
        first = asyncio.create_task(app_main._run_v3_project_header_scan(lambda: slow_scan(1)))
        assert await asyncio.to_thread(entered.wait, 5)
        second = asyncio.create_task(app_main._run_v3_project_header_scan(lambda: slow_scan(2)))
        third = asyncio.create_task(app_main._run_v3_project_header_scan(lambda: slow_scan(3)))
        await asyncio.sleep(0.02)
        assert app_main._v3_browse_header_admitted == 3  # noqa: SLF001
        with pytest.raises(HTTPException) as exc_info:
            await app_main._run_v3_project_header_scan(lambda: slow_scan(4))
        release.set()
        return await asyncio.gather(first, second, third), exc_info.value

    try:
        results, error = asyncio.run(exercise())
    finally:
        release.set()
        executor.shutdown(wait=True)

    assert results == [1, 2, 3]
    assert peak_active == 1
    assert error.status_code == 503
    assert error.detail["code"] == "v3_browse_read_capacity_exceeded"
    assert error.headers == {"Retry-After": "1"}


def test_summary_projects_route_offloads_only_detached_headers(monkeypatch) -> None:
    header = {
        "project_id": "project_route_header",
        "status": "active",
        "created_at": "2026-09-01T00:00:00+00:00",
        "updated_at": "2026-09-02T00:00:00+00:00",
        "owner_user_id": 7,
    }
    scan_threads: list[int] = []
    handler_threads: list[int] = []
    seen_headers: list[dict[str, object]] = []

    def read_headers():
        scan_threads.append(threading.get_ident())
        return [dict(header)]

    class Handlers:
        project_service = SimpleNamespace(
            project_store=SimpleNamespace(list_project_headers=read_headers),
        )

        @staticmethod
        def get_projects(limit, owner_user_id, cursor, view, *, project_headers=None):
            handler_threads.append(threading.get_ident())
            seen_headers.extend(project_headers or [])
            return {"projects": [], "total": 0, "view": view}

    async def run():
        monkeypatch.setattr(app_main, "v3_route_handlers", Handlers())
        monkeypatch.setattr(app_main, "_require_veyra_user_if_enabled", lambda *_args: 7)
        monkeypatch.setattr(app_main, "_v3_is_admin_request", lambda *_args: asyncio.sleep(0, result=False))
        return await app_main.v3_projects_endpoint(
            request=SimpleNamespace(),
            limit=12,
            cursor=None,
            view="summary",
            authorization="",
        )

    event_loop_thread = threading.get_ident()
    response = asyncio.run(run())

    assert response["view"] == "summary"
    assert scan_threads and scan_threads[0] != event_loop_thread
    assert handler_threads == [event_loop_thread]
    assert seen_headers == [header]


def test_cancelled_queued_header_scans_keep_the_executor_queue_physically_bounded(monkeypatch) -> None:
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="test-v3-header-cancel")
    monkeypatch.setattr(app_main, "_v3_browse_header_executor", executor)
    with app_main._v3_browse_header_gate_lock:  # noqa: SLF001
        app_main._v3_browse_header_admitted = 0  # noqa: SLF001
        app_main._v3_browse_header_active = 0  # noqa: SLF001

    entered = threading.Event()
    release = threading.Event()
    queued_ran: list[int] = []

    def active_scan():
        entered.set()
        assert release.wait(timeout=5)
        return "active"

    def queued_scan(index):
        queued_ran.append(index)
        return index

    async def exercise():
        active = asyncio.create_task(app_main._run_v3_project_header_scan(active_scan))
        assert await asyncio.to_thread(entered.wait, 5)
        queued_one = asyncio.create_task(app_main._run_v3_project_header_scan(lambda: queued_scan(1)))
        queued_two = asyncio.create_task(app_main._run_v3_project_header_scan(lambda: queued_scan(2)))
        await asyncio.sleep(0.02)
        assert app_main._v3_browse_header_admitted == 3  # noqa: SLF001
        queued_one.cancel()
        queued_two.cancel()
        await asyncio.gather(queued_one, queued_two, return_exceptions=True)
        assert app_main._v3_browse_header_admitted == 3  # noqa: SLF001
        assert executor._work_queue.qsize() == 2  # noqa: SLF001
        for index in range(1000):
            pending = asyncio.create_task(
                app_main._run_v3_project_header_scan(lambda index=index: queued_scan(index + 10))
            )
            await asyncio.sleep(0)
            if not pending.done():
                pending.cancel()
            result = await asyncio.gather(pending, return_exceptions=True)
            if isinstance(result[0], HTTPException):
                assert result[0].status_code == 503
            else:
                assert isinstance(result[0], asyncio.CancelledError)
        assert executor._work_queue.qsize() == 2  # noqa: SLF001
        release.set()
        assert await active == "active"
        await asyncio.sleep(0.02)
        assert executor._work_queue.qsize() == 0  # noqa: SLF001

    try:
        asyncio.run(exercise())
    finally:
        release.set()
        executor.shutdown(wait=True)

    assert queued_ran == []
    assert app_main._v3_browse_header_admitted == 0  # noqa: SLF001
