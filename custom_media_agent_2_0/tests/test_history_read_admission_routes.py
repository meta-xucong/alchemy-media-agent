from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app import main
from app.repositories.sqlite_calls import SQLiteStorageBusy


@pytest.mark.parametrize("endpoint", ["image_history", "veyra_history"])
@pytest.mark.parametrize("auth_enabled", [False, True])
def test_history_routes_only_use_read_admission(monkeypatch, endpoint, auth_enabled):
    calls = []
    expected = object()

    async def read(function, *args, **kwargs):
        calls.append((function, args, kwargs))
        return expected

    async def forbid_write(*args, **kwargs):
        raise AssertionError("history must use bounded read admission")

    async def context(*args, **kwargs):
        return {"user_id": 77, "is_admin": False}

    monkeypatch.setattr(main, "settings", SimpleNamespace(veyra_auth_enabled=auth_enabled))
    monkeypatch.setattr(main, "_veyra_request_context", context)
    monkeypatch.setattr(main.sqlite_calls, "run_read", read)
    monkeypatch.setattr(main.sqlite_calls, "run", forbid_write)
    result = asyncio.run(getattr(main, endpoint)(
        SimpleNamespace(), limit=24, offset=48, authorization=""
    ))
    assert result is expected
    assert len(calls) == 1
    function, args, kwargs = calls[0]
    assert function is main.list_image_history
    assert args == ()
    assert kwargs["limit"] == 24
    assert kwargs["offset"] == 48
    if auth_enabled:
        assert kwargs["veyra_user_id"] == 77
        assert kwargs["include_legacy_public"] is True
        assert kwargs["include_all"] is False


def test_read_admission_busy_retains_existing_retry_response(monkeypatch):
    async def busy(*args, **kwargs):
        raise SQLiteStorageBusy("full", capacity_full=True)

    monkeypatch.setattr(main.sqlite_calls, "run_read", busy)
    with pytest.raises(HTTPException) as captured:
        asyncio.run(main._run_sqlite_read_api_call(lambda: None))
    assert captured.value.status_code == 503
    assert captured.value.headers == {"Retry-After": "1"}
    assert captured.value.detail["error_code"] == "storage_busy"


def test_write_wrapper_keeps_immediate_admission(monkeypatch):
    expected = object()

    async def write(function, *args, **kwargs):
        return expected

    async def forbid_read(*args, **kwargs):
        raise AssertionError("writes must not silently opt into read queuing")

    monkeypatch.setattr(main.sqlite_calls, "run", write)
    monkeypatch.setattr(main.sqlite_calls, "run_read", forbid_read)
    assert asyncio.run(main._run_sqlite_api_call(lambda: None)) is expected
