import datetime as dt
import subprocess
import sys
import time
from types import SimpleNamespace

import pytest

from scripts import vps_main_watchdog as watchdog
from scripts.vps_cutover_guard import CutoverBlocked


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr(watchdog, "LOCK", tmp_path / "release.lock")
    monkeypatch.setattr(watchdog, "MAINTENANCE", tmp_path / "maintenance")
    monkeypatch.setattr(watchdog, "COOLDOWN", tmp_path / "cooldown")
    monkeypatch.setattr(watchdog.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(watchdog, "healthy", lambda: False)
    info = {
        "Id": "original",
        "State": {
            "Running": True,
            "Restarting": False,
            "StartedAt": dt.datetime.fromtimestamp(time.time() - 500, dt.timezone.utc).isoformat(),
        },
    }
    monkeypatch.setattr(watchdog, "container", lambda: info)
    monkeypatch.setattr(watchdog, "work_is_idle", lambda _info: True)
    restarts = []
    monkeypatch.setattr(watchdog.subprocess, "run", lambda args, **kwargs: restarts.append(args))
    monkeypatch.setitem(sys.modules, "fcntl", SimpleNamespace(
        flock=lambda *_args: None, LOCK_EX=2, LOCK_NB=4,
    ))
    return info, restarts


def test_healthy_and_transient_failure_do_not_inspect_container(runtime, monkeypatch):
    def unexpected():
        pytest.fail("healthy path touched Docker")

    monkeypatch.setattr(watchdog, "container", unexpected)
    monkeypatch.setattr(watchdog, "healthy", iter([True]).__next__)
    watchdog.main()
    monkeypatch.setattr(watchdog, "healthy", iter([False, True]).__next__)
    watchdog.main()
    assert runtime[1] == []


def test_idle_hang_restarts_exact_container_once_and_recovers(runtime, monkeypatch, caplog):
    monkeypatch.setattr(watchdog, "healthy", iter([False] * 5 + [True]).__next__)
    watchdog.main()
    assert runtime[1] == [["docker", "restart", "--time", "15", "original"]]
    assert watchdog.COOLDOWN.exists()
    assert "responded after restart" in caplog.text
    monkeypatch.setattr(watchdog, "healthy", lambda: False)
    watchdog.main()
    assert len(runtime[1]) == 1


@pytest.mark.parametrize("condition", ["maintenance", "cutover", "active", "unreadable", "new", "stopped", "changed"])
def test_restart_deferred(runtime, monkeypatch, condition):
    info, restarts = runtime

    def blocked(*_args):
        raise CutoverBlocked("busy")

    def locked(*_args):
        raise BlockingIOError

    if condition == "maintenance":
        watchdog.MAINTENANCE.touch()
    elif condition == "cutover":
        monkeypatch.setattr(sys.modules["fcntl"], "flock", locked)
    elif condition == "active":
        monkeypatch.setattr(watchdog, "work_is_idle", lambda _: False)
    elif condition == "unreadable":
        monkeypatch.setattr(watchdog, "work_is_idle", blocked)
    elif condition == "new":
        info["State"]["StartedAt"] = dt.datetime.now(dt.timezone.utc).isoformat()
    elif condition == "stopped":
        info["State"]["Running"] = False
    elif condition == "changed":
        monkeypatch.setattr(watchdog, "container", iter([info, {**info, "Id": "replacement"}]).__next__)
    watchdog.main()
    assert restarts == []
    assert not watchdog.COOLDOWN.exists()


def test_restart_error_reserves_cooldown(runtime, monkeypatch, caplog):
    def failed(args, **_kwargs):
        runtime[1].append(args)
        raise subprocess.TimeoutExpired(args, 35)

    monkeypatch.setattr(watchdog.subprocess, "run", failed)
    watchdog.main()
    watchdog.main()
    assert len(runtime[1]) == 1
    assert watchdog.COOLDOWN.exists()
    assert "TimeoutExpired" in caplog.text


def test_durable_inventory_uses_live_mount_and_exact_start(tmp_path, monkeypatch):
    media = tmp_path / "v1"
    data = tmp_path / "v2"
    bridge = tmp_path / "bridge"
    data.mkdir()
    bridge.mkdir()
    (data / "repository.sqlite3").touch()
    env = tmp_path / "v2.env"
    queue = data / "active.sqlite3"
    env.write_text(f"V2_DATA_DIR={data}\nV2_TASK_QUEUE_DB_PATH={queue}\n", encoding="utf-8")
    monkeypatch.setattr(watchdog, "V2_ENV", env)
    monkeypatch.setattr(watchdog, "verify_bridge_storage_configuration",
                        lambda *_args: {"state_root": str(bridge)})
    calls = []

    def inventory(*args, **kwargs):
        calls.append((args, kwargs))
        return {"status": "idle", "active_work_items": 0}

    monkeypatch.setattr(watchdog, "inspect_active_work", inventory)
    info = {
        "Id": "original",
        "State": {"StartedAt": "2026-11-24T00:00:00.123456789Z"},
        "Mounts": [
            {"Destination": "/app/.media_storage", "Source": str(media)},
            {"Destination": "/app/.env", "Source": str(tmp_path / "v1.env")},
        ],
    }
    assert watchdog.work_is_idle(info)
    assert calls == [(
        (media / "repository.sqlite3", queue, media / "v3_projects"),
        {
            "v3_container_started_at": info["State"]["StartedAt"],
            "bridge_state_root": bridge,
            "bridge_frozen_root": data / "render_bridge_primary" / "requests",
            "v2_repository": data / "repository.sqlite3",
        },
    )]
