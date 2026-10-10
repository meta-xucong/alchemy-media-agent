from __future__ import annotations

import asyncio
import sqlite3
import time
from types import SimpleNamespace

from fastapi import HTTPException

from app.main import favorite_history_item
from app import main as v2_main
from app.schemas import FavoriteImageRequest
from app.services import favorites


def test_favorite_busy_database_does_not_block_event_loop_and_returns_retryable_status(monkeypatch):
    favorites.list_favorite_ids(include_all=True)
    lock = sqlite3.connect(favorites._database_path(), timeout=0.1, check_same_thread=False)
    lock.execute("BEGIN IMMEDIATE")

    async def allow_output(*_args, **_kwargs):
        return {"user_id": 77}

    monkeypatch.setattr("app.main._require_output_visible", allow_output)
    monkeypatch.setattr("app.main.repository.get_output", lambda _output_id: object())

    async def exercise_route():
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
                await favorite_history_item(
                    "out_busy_test_0001",
                    FavoriteImageRequest(favorite=True),
                    SimpleNamespace(),
                )
            except HTTPException as exc:
                response = exc
            else:
                response = None
        finally:
            finished.set()
            await ticker_task
        return response, ticks, time.monotonic() - started

    try:
        response, ticks, elapsed = asyncio.run(exercise_route())
    finally:
        lock.rollback()
        lock.close()

    assert isinstance(response, HTTPException)
    assert response.status_code == 503
    assert response.headers.get("Retry-After") == "1"
    assert ticks >= 5
    assert elapsed < 1.5


def test_v2_history_image_and_download_routes_keep_event_loop_live(monkeypatch, tmp_path):
    database = tmp_path / "route-busy.sqlite3"
    lock = sqlite3.connect(database, timeout=0.1, check_same_thread=False)
    lock.execute("CREATE TABLE IF NOT EXISTS busy_probe (value INTEGER)")
    lock.commit()
    lock.execute("BEGIN IMMEDIATE")

    def write_while_locked(*_args, **_kwargs):
        connection = sqlite3.connect(database, timeout=0.1)
        try:
            connection.execute("INSERT INTO busy_probe(value) VALUES(1)")
        finally:
            connection.close()

    async def allow_output(*_args, **_kwargs):
        return {"user_id": 77, "is_admin": False, "owner_id": 77}

    monkeypatch.setattr(v2_main, "_require_output_visible", allow_output)
    monkeypatch.setattr(v2_main, "list_favorite_ids", lambda **_kwargs: ["output-lock"])
    request = SimpleNamespace()
    cases = [
        ("read_history_thumbnail", "image_history_thumbnail", ()),
        ("read_history_preview", "image_history_preview", ()),
        ("resolve_output_file", "output_download", ()),
        (
            "create_reference_asset_from_history_output",
            "history_reference_asset",
            (SimpleNamespace(),),
        ),
    ]

    async def exercise():
        results = []
        for operation_name, endpoint_name, extra_args in cases:
            monkeypatch.setattr(v2_main, operation_name, write_while_locked)
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
                    await getattr(v2_main, endpoint_name)(
                        "output-lock", *extra_args, request, authorization=""
                    )
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
