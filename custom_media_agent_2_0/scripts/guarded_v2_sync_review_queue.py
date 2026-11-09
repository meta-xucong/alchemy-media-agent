"""Synchronize the live V2 runtime queue through its authenticated local API."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import sqlite3
import time
import uuid
from pathlib import Path

import httpx


API_ROOT = "http://127.0.0.1:8020"
SETTINGS_PATH = "/api/v2/runtime/model-settings"
REVIEW_STATUS_PATH = "/api/v2/review-agent/status"
FALLBACK_QUEUE = ["kimi-k3", "gpt-6.1-sol"]


def _read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, separator, value = line.strip().removeprefix("export ").partition("=")
        if separator and key and not key.startswith("#"):
            values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _headers(secret: str, *, user_id: int, method: str, path: str) -> dict[str, str]:
    if not secret:
        return {}
    surfaces = ("v2",)
    request_id = "codex-v2-queue-" + uuid.uuid4().hex
    issued_at = int(time.time())
    nonce = uuid.uuid4().hex
    canonical = "\n".join([
        str(user_id), ",".join(surfaces), request_id, str(issued_at), nonce,
        method.upper(), path,
    ]).encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), canonical, hashlib.sha256).hexdigest()
    return {
        "X-Alchemy-Access-User": str(user_id),
        "X-Alchemy-Access-Surfaces": ",".join(surfaces),
        "X-Alchemy-Access-Request": request_id,
        "X-Alchemy-Access-Issued": str(issued_at),
        "X-Alchemy-Access-Nonce": nonce,
        "X-Alchemy-Access-Signature": signature,
    }


def _request(client: httpx.Client, method: str, path: str, *, secret: str, user_id: int, json_body=None) -> dict:
    response = client.request(
        method,
        API_ROOT + path,
        headers=_headers(secret, user_id=user_id, method=method, path=path),
        json=json_body,
    )
    if response.status_code < 200 or response.status_code >= 300:
        raise RuntimeError("v2_settings_api_request_failed")
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("v2_settings_api_invalid_response")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    arguments = parser.parse_args()

    environment = _read_env(Path("/etc/alchemy/alchemy-v2.env"))
    environment.update(_read_env(Path("/etc/alchemy/alchemy-v2-api-runtime.env")))
    secret = environment.get("ALCHEMY_ACCESS_BRIDGE_SECRET", "")
    auth_enabled = environment.get("VEYRA_AUTH_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
    data_dir = environment.get("V2_DATA_DIR")
    if not data_dir:
        raise RuntimeError("v2_data_root_unconfigured")
    database = Path(data_dir).expanduser().resolve() / "repository.sqlite3"
    connection = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        row = connection.execute(
            "SELECT payload FROM v2_records WHERE namespace='image_jobs' AND record_key=?",
            (arguments.job_id,),
        ).fetchone()
    finally:
        connection.close()
    job = json.loads(row[0]) if row and isinstance(row[0], str) else {}
    owner_id = job.get("veyra_user_id")
    owner_id = owner_id if type(owner_id) is int and owner_id > 0 else None
    if auth_enabled and (not secret or owner_id is None):
        raise RuntimeError("v2_access_bridge_identity_unavailable")
    request_secret = secret if owner_id is not None else ""
    request_user_id = owner_id or 1

    with httpx.Client(timeout=15.0, trust_env=False) as client:
        before = _request(client, "GET", SETTINGS_PATH, secret=request_secret, user_id=request_user_id)
        update = _request(client, "POST", SETTINGS_PATH, secret=request_secret, user_id=request_user_id, json_body={
            "claude_orchestrator_fallback_models": FALLBACK_QUEUE,
        })
        review_status = _request(client, "GET", REVIEW_STATUS_PATH, secret=request_secret, user_id=request_user_id)

    expected_primary = update.get("claude_orchestrator_multimodal_model") or update.get("claude_orchestrator_model")
    expected_queue = [expected_primary, *FALLBACK_QUEUE]
    if not isinstance(expected_primary, str) or not expected_primary.startswith("claude-"):
        raise RuntimeError("v2_claude_primary_not_configured")
    if review_status.get("model_queue") != expected_queue:
        raise RuntimeError("v2_review_queue_sync_mismatch")
    for key, value in before.items():
        if key not in {"claude_orchestrator_fallback_models", "persisted"} and update.get(key) != value:
            raise RuntimeError("v2_unrelated_model_setting_changed")

    runtime_path = Path(data_dir).expanduser().resolve() / "runtime_model_settings.json"
    runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
    if runtime.get("claude_orchestrator_fallback_models") != FALLBACK_QUEUE:
        raise RuntimeError("v2_persisted_review_queue_mismatch")

    print("SAFE_V2_REVIEW_QUEUE_SYNC=" + json.dumps({
        "api_model_queue": review_status["model_queue"],
        "persisted_fallback_queue": runtime["claude_orchestrator_fallback_models"],
        "unrelated_settings_preserved": True,
    }, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as error:
        print(json.dumps({
            "event": "SAFE_V2_REVIEW_QUEUE_SYNC_ERROR",
            "error_type": type(error).__name__,
        }), flush=True)
        raise SystemExit(1)
