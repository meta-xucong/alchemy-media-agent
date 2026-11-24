"""Recover an unresponsive Alchemy main container when durable work is idle."""

import datetime as dt
import http.client
import json
import logging
from pathlib import Path
import subprocess
import time

from scripts.vps_cutover_guard import (
    CutoverBlocked,
    _read_v3_bootstrap_environment,
    inspect_active_work,
    verify_bridge_storage_configuration,
)

CONTAINER = "alchemy-media-agent"
RELEASE = Path("/opt/alchemy-media-agent")
LOCK = Path("/run/lock/alchemy-media-agent-release.lock")
MAINTENANCE = Path("/etc/alchemy/alchemy-media-agent-maintenance")
V2_ENV = Path("/etc/alchemy/alchemy-v2.env")
COOLDOWN = Path("/var/lib/alchemy-media-agent-watchdog/last-restart")
STARTUP_GRACE = 120
RESTART_INTERVAL = 300
log = logging.getLogger("alchemy-main-watchdog")


def healthy() -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", 8017, timeout=2)
    try:
        connection.request("GET", "/healthz")
        return connection.getresponse().status == 200
    except (OSError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def container() -> dict:
    result = subprocess.run(
        ["docker", "inspect", "--type", "container", CONTAINER],
        capture_output=True, check=True, timeout=5,
    )
    return json.loads(result.stdout)[0]


def identity(info: dict) -> tuple[str, str]:
    return info["Id"], info["State"]["StartedAt"]


def work_is_idle(info: dict) -> bool:
    mounts = {entry["Destination"]: Path(entry["Source"]) for entry in info["Mounts"]}
    media = mounts["/app/.media_storage"]
    v2 = _read_v3_bootstrap_environment(V2_ENV, {"V2_DATA_DIR", "V2_TASK_QUEUE_DB_PATH"})
    data = Path(v2.get("V2_DATA_DIR") or mounts["/var/lib/alchemy/v2/storage"])
    queue = Path(v2.get("V2_TASK_QUEUE_DB_PATH") or (data / "task_queue.sqlite3"))
    bridge = verify_bridge_storage_configuration(mounts["/app/.env"], V2_ENV, (RELEASE,))
    v2_repository = data / "repository.sqlite3"
    if not v2_repository.is_file() or not Path(bridge["state_root"]).is_dir():
        raise CutoverBlocked("watchdog_storage_unavailable")
    result = inspect_active_work(
        media / "repository.sqlite3", queue, media / "v3_projects",
        v3_container_started_at=identity(info)[1],
        bridge_state_root=Path(bridge["state_root"]),
        bridge_frozen_root=data / "render_bridge_primary" / "requests",
        v2_repository=v2_repository,
    )
    return result["status"] == "idle" and result["active_work_items"] == 0


def restart_if_idle() -> None:
    if MAINTENANCE.exists() or healthy():
        return
    info = container()
    state = info["State"]
    if not state["Running"] or state["Restarting"]:
        return
    container_id, started = identity(info)
    started_at = dt.datetime.fromisoformat(started).timestamp()
    if time.time() - started_at < STARTUP_GRACE:
        return
    if COOLDOWN.exists() and time.time() - COOLDOWN.stat().st_mtime < RESTART_INTERVAL:
        log.warning("Still unresponsive. Waiting for restart cooldown.")
        return
    if not work_is_idle(info):
        log.warning("Main service unresponsive. Restart deferred while durable work is active.")
        return
    latest = container()
    state = latest["State"]
    if (identity(latest) != (container_id, started) or not state["Running"]
            or state["Restarting"] or MAINTENANCE.exists() or healthy()):
        return
    COOLDOWN.touch()
    log.warning("Main service unresponsive. Restarting the idle container.")
    subprocess.run(
        ["docker", "restart", "--time", "15", container_id],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=35,
    )
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if healthy():
            log.warning("Main service responded after restart.")
            return
        time.sleep(3)
    log.error("Main service did not become healthy after restart.")


def main() -> None:
    import fcntl

    for attempt in range(3):
        if MAINTENANCE.exists() or healthy():
            return
        if attempt < 2:
            time.sleep(3)
    try:
        with LOCK.open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return
            restart_if_idle()
    except (CutoverBlocked, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        # Do not dump docker inspect or environment values to journald.
        log.error("Main-service recovery did not complete (%s).", type(error).__name__)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    main()
