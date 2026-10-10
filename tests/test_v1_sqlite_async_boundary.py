from __future__ import annotations

import asyncio
import sqlite3
import time
from types import SimpleNamespace

from fastapi import HTTPException

from app.main import _run_sqlite_api_call
from app import main as v1_main
from app.repositories.sqlite_json import connect


def test_v1_busy_database_is_offloaded_and_returns_retryable_status(tmp_path):
    database = tmp_path / "busy.sqlite3"
    lock = connect(database)
    lock.execute("BEGIN IMMEDIATE")

    def write_while_locked():
        connection = sqlite3.connect(database, timeout=0.1)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS busy_probe (value INTEGER)")
            connection.execute("INSERT INTO busy_probe(value) VALUES(1)")
        finally:
            connection.close()

    async def exercise():
        ticks = 0
        finished = asyncio.Event()

        async def ticker():
            nonlocal ticks
            while not finished.is_set():
                ticks += 1
                await asyncio.sleep(0.01)

        ticker_task = asyncio.create_task(ticker())
        started = time.monotonic()
        try:
            try:
                await _run_sqlite_api_call(write_while_locked)
            except HTTPException as exc:
                response = exc
            else:
                response = None
        finally:
            finished.set()
            await ticker_task
        return response, ticks, time.monotonic() - started

    try:
        response, ticks, elapsed = asyncio.run(exercise())
    finally:
        lock.rollback()
        lock.close()

    assert isinstance(response, HTTPException)
    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "1"
    assert ticks >= 5
    assert elapsed < 1.5


def test_v1_history_lab_and_output_read_routes_keep_event_loop_live(monkeypatch, tmp_path):
    database = tmp_path / "route-busy.sqlite3"
    lock = connect(database)
    lock.execute("BEGIN IMMEDIATE")

    def write_while_locked(*_args, **_kwargs):
        connection = sqlite3.connect(database, timeout=0.1)
        try:
            connection.execute("CREATE TABLE IF NOT EXISTS busy_probe (value INTEGER)")
            connection.execute("INSERT INTO busy_probe(value) VALUES(1)")
        finally:
            connection.close()

    async def history_context(*_args, **_kwargs):
        return {"user_id": 77, "is_admin": False}

    async def allow_output(*_args, **_kwargs):
        return {"user_id": 77, "is_admin": False}

    monkeypatch.setattr(v1_main, "_veyra_history_context", history_context)
    monkeypatch.setattr(v1_main, "_require_output_visible", allow_output)
    request = SimpleNamespace()
    cases = [
        ("_list_image_history_sync", "list_image_history", {
            "request": request, "session_id": None, "limit": 50, "offset": 0, "authorization": "",
        }),
        ("list_lab_history", "list_alchemy_lab_history", {
            "request": request, "limit": 50, "include_mock": False, "authorization": "",
        }),
        ("_resolve_output_file", "download_output", {
            "output_id": "output-lock", "request": request, "authorization": "",
        }),
        ("_ensure_output_thumbnail", "thumbnail_output", {
            "output_id": "output-lock", "request": request, "authorization": "",
        }),
        ("_ensure_output_preview", "preview_output", {
            "output_id": "output-lock", "request": request, "authorization": "",
        }),
    ]

    async def exercise():
        results = []
        for operation_name, endpoint_name, endpoint_kwargs in cases:
            monkeypatch.setattr(v1_main, operation_name, write_while_locked)
            ticks = 0
            finished = asyncio.Event()

            async def ticker():
                nonlocal ticks
                while not finished.is_set():
                    ticks += 1
                    await asyncio.sleep(0.01)

            ticker_task = asyncio.create_task(ticker())
            started = time.monotonic()
            try:
                try:
                    await getattr(v1_main, endpoint_name)(**endpoint_kwargs)
                except HTTPException as exc:
                    response = exc
                else:
                    response = None
            finally:
                finished.set()
                await ticker_task
            results.append((response, ticks, time.monotonic() - started))
        return results

    try:
        results = asyncio.run(exercise())
    finally:
        lock.rollback()
        lock.close()

    for response, ticks, elapsed in results:
        assert isinstance(response, HTTPException)
        assert response.status_code == 503
        assert response.headers.get("Retry-After") == "1"
        assert ticks >= 5
        assert elapsed < 1.5
