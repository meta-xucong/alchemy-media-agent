#!/usr/bin/env python3
"""Run one authenticated V3 generation against a loopback candidate API."""

from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class SafeApiError(RuntimeError):
    def __init__(self, code: str, status: int | None = None):
        super().__init__(code)
        self.code = code
        self.status = status


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPENER = build_opener(NoRedirect())
MAX_RESPONSE_BYTES = 32 * 1024 * 1024
ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,128}$")
SAFE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,120}$")
IMAGE_SIGNATURES = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)


def _base_url() -> str:
    value = os.getenv("ALCHEMY_CANDIDATE_API_BASE_URL", "http://127.0.0.1:18017").rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.path
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise SafeApiError("candidate_api_base_must_be_loopback_http")
    return value


def _auth_token() -> str:
    value = os.getenv("V3_CANDIDATE_AUTH_TOKEN", "").strip()
    if not value:
        raise SafeApiError("candidate_auth_secret_missing")
    return value


def _request(method: str, path: str, token: str, body: dict | None = None) -> tuple[object, dict[str, str]]:
    base = _base_url()
    if not path.startswith("/") or path.startswith("//"):
        raise SafeApiError("candidate_api_path_invalid")
    encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8") if body is not None else None
    request = Request(
        base + path,
        data=encoded,
        method=method,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
            **({"Content-Type": "application/json; charset=utf-8"} if encoded is not None else {}),
        },
    )
    try:
        with OPENER.open(request, timeout=35) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise SafeApiError("candidate_api_response_too_large")
            headers = {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as exc:
        raise SafeApiError("candidate_api_http_error", exc.code) from None
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        code = "candidate_api_timeout" if isinstance(reason, (TimeoutError, socket.timeout)) else "candidate_api_transport_error"
        raise SafeApiError(code) from None
    except (TimeoutError, socket.timeout):
        raise SafeApiError("candidate_api_timeout") from None
    if method == "GET" and headers.get("content-type", "").lower().startswith("image/"):
        return raw, headers
    try:
        return json.loads(raw.decode("utf-8")), headers
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise SafeApiError("candidate_api_json_invalid") from None


def _mapping(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _project(payload: object) -> dict:
    root = _mapping(payload)
    return _mapping(root.get("project")) or root


def _job_id(project_payload: object, accepted_payload: object | None = None) -> str:
    for source in (accepted_payload, project_payload):
        root = _mapping(source)
        candidate = root.get("job_id")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
        project = _project(source)
        ids = project.get("job_ids")
        if isinstance(ids, list):
            for value in reversed(ids):
                if isinstance(value, str) and value.strip():
                    return value.strip()
    return ""


def _operation(project_payload: object) -> dict:
    project = _project(project_payload)
    metadata = _mapping(project.get("metadata"))
    operation = metadata.get("doc277_planning_current_operation") or metadata.get("current_operation")
    if isinstance(operation, dict):
        return operation
    response_metadata = _mapping(_mapping(project_payload).get("metadata"))
    operation = response_metadata.get("current_operation")
    return operation if isinstance(operation, dict) else {}


def _find_route_value(value: object, depth: int = 0) -> tuple[str, str]:
    if depth > 8:
        return "", ""
    if isinstance(value, dict):
        route = str(value.get("route") or "").strip().lower()
        if route in {"bridge", "api"}:
            reason = str(value.get("reason") or value.get("route_reason") or "").strip()
            return route, reason if SAFE_CODE_PATTERN.fullmatch(reason) else ""
        for child in value.values():
            route, reason = _find_route_value(child, depth + 1)
            if route:
                return route, reason
    elif isinstance(value, list):
        for child in value[:100]:
            route, reason = _find_route_value(child, depth + 1)
            if route:
                return route, reason
    return "", ""


def _require_bridge_route(route: str) -> None:
    if str(route or "").strip().lower() != "bridge":
        raise SafeApiError("candidate_v3_bridge_route_not_confirmed")


def _final_delivery_item(outputs: object, project_id: str, job_id: str) -> dict:
    """Resolve only the job's normal user-facing delivery projection."""
    root = _mapping(outputs)
    items = root.get("items")
    if not isinstance(items, list):
        items = []
    matches = [
        item for item in items
        if isinstance(item, dict) and str(item.get("job_id") or "").strip() == job_id
    ]
    if len(matches) != 1:
        raise SafeApiError("candidate_v3_delivery_output_count_invalid")

    item = matches[0]
    output_id = str(item.get("output_id") or "").strip()
    if (
        not ID_PATTERN.fullmatch(output_id)
        or str(item.get("project_id") or "").strip() != project_id
        or str(item.get("delivery_state") or "").strip().lower() != "final_delivery"
    ):
        raise SafeApiError("candidate_v3_delivery_output_binding_invalid")

    if (
        str(item.get("review_mode") or "").strip().lower() not in {"vision_model", "hybrid"}
        or str(item.get("review_status") or "").strip().lower() not in {"pass", "warning"}
        or str(item.get("verification_state") or "").strip().lower() != "verified"
        or str(item.get("certification_state") or "").strip().lower() != "certified"
        or str(item.get("public_delivery_state") or "").strip().lower() != "ready"
    ):
        raise SafeApiError("candidate_v3_delivery_output_not_certified")

    expected_preview = f"/api/v3/creative-agent/outputs/{quote(output_id, safe='')}/preview"
    expected_download = f"/api/v3/creative-agent/outputs/{quote(output_id, safe='')}/download"
    if item.get("preview_url") != expected_preview or item.get("download_url") != expected_download:
        raise SafeApiError("candidate_v3_delivery_output_binding_invalid")
    return item


def _validate_image_response(raw: object, headers: dict[str, str], *, kind: str) -> None:
    if not isinstance(raw, bytes):
        raise SafeApiError(f"candidate_v3_{kind}_not_image")
    content_type = str(headers.get("content-type", "")).split(";", 1)[0].strip().lower()
    signature_type = next(
        (mime for signature, mime in IMAGE_SIGNATURES if raw.startswith(signature)),
        None,
    )
    if signature_type is None and len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        signature_type = "image/webp"
    if len(raw) < 1024 or content_type != signature_type:
        raise SafeApiError(f"candidate_v3_{kind}_invalid")


def _reserve_once() -> None:
    expected_sha = os.getenv("EXPECTED_CANDIDATE_SHA", "")
    run_id = os.getenv("GITHUB_RUN_ID", "")
    run_attempt = os.getenv("GITHUB_RUN_ATTEMPT", "")
    if not re.fullmatch(r"[0-9a-f]{40}", expected_sha):
        raise SafeApiError("candidate_sha_invalid")
    if not run_id.isdigit() or not run_attempt.isdigit():
        raise SafeApiError("candidate_run_identity_invalid")
    host = os.getenv("VPS_HOST", "").strip()
    user = os.getenv("VPS_USER", "root").strip() or "root"
    port = os.getenv("VPS_PORT", "22").strip()
    if not host or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,255}", host):
        raise SafeApiError("candidate_ssh_host_invalid")
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise SafeApiError("candidate_ssh_port_invalid")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", user):
        raise SafeApiError("candidate_ssh_user_invalid")

    remote = f"{user}@{host}"
    ssh = [
        "ssh", "-i", str(Path.home() / ".ssh" / "id_ed25519"),
        "-p", port, "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new",
        remote, "bash", "-s", "--", expected_sha, run_id, run_attempt,
    ]
    marker_script = r'''set -euo pipefail
expected_sha="$1"
run_id="$2"
run_attempt="$3"
[[ "$expected_sha" =~ ^[0-9a-f]{40}$ ]]
[[ "$run_id" =~ ^[0-9]+$ && "$run_attempt" =~ ^[0-9]+$ ]]
marker_root="/var/lib/alchemy/candidate-smoke/v3/$expected_sha"
install -d -m 700 "$marker_root"
marker="$marker_root/generation-started"
if ( set -o noclobber; : > "$marker" ) 2>/dev/null; then
  chmod 600 "$marker"
  printf 'run_id=%s\nrun_attempt=%s\n' "$run_id" "$run_attempt" > "$marker"
  printf 'GUARDED_CANDIDATE_V3_GENERATION_RESERVED=1\n'
else
  printf 'GUARDED_CANDIDATE_V3_STOP=generation_already_attempted_for_sha\n' >&2
  exit 2
fi
'''
    try:
        result = subprocess.run(
            ssh,
            input=marker_script,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={key: value for key, value in os.environ.items() if key != "V3_CANDIDATE_AUTH_TOKEN"},
            timeout=45,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SafeApiError("candidate_generation_reservation_transport_error") from None
    if result.returncode != 0 or "GUARDED_CANDIDATE_V3_GENERATION_RESERVED=1" not in result.stdout:
        raise SafeApiError("candidate_generation_reservation_failed")


def _write_summary(data: dict) -> None:
    summary = os.getenv("GITHUB_STEP_SUMMARY", "")
    if not summary:
        return
    lines = [
        "## Guarded candidate V3 smoke",
        "",
        f"- Candidate SHA: `{data.get('candidate_sha', 'unknown')}`",
        f"- Result: `{data.get('result', 'failed')}`",
        f"- Project: `{data.get('project_id', 'unavailable')}`",
        f"- Job: `{data.get('job_id', 'unavailable')}`",
        f"- Job status: `{data.get('job_status', 'unknown')}`",
        f"- Outputs: `{data.get('output_count', 0)}`",
        f"- Preview checks: `{data.get('preview_checks', 0)}`",
        f"- Download checks: `{data.get('download_checks', 0)}`",
        f"- Review: `{data.get('review_status', 'unknown')}` / `{data.get('certification_state', 'unknown')}`",
        f"- Delivery state: `{data.get('delivery_state', 'unknown')}`",
        f"- Observed provider route: `{data.get('route') or 'unknown'}`",
        f"- Route reason: `{data.get('route_reason') or 'unavailable'}`",
        "",
        "Generation was submitted at most once. No output selection or production activation was performed.",
        "",
    ]
    with open(summary, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def _run() -> int:
    result: dict = {
        "candidate_sha": os.getenv("EXPECTED_CANDIDATE_SHA", "unknown"),
        "result": "failed",
        "project_id": "",
        "job_id": "",
        "job_status": "unknown",
        "output_count": 0,
        "preview_checks": 0,
        "download_checks": 0,
        "review_status": "unknown",
        "certification_state": "unknown",
        "delivery_state": "unknown",
        "route": "",
        "route_reason": "",
    }
    try:
        token = _auth_token()
        user_input = os.getenv("CANDIDATE_V3_USER_INPUT", "").strip()
        if not user_input or len(user_input) > 1000 or any(ord(ch) < 32 and ch not in "\n\t" for ch in user_input):
            raise SafeApiError("candidate_v3_user_input_invalid")

        capabilities, _ = _request("GET", "/api/access/capabilities", token)
        surfaces = _mapping(capabilities).get("surfaces")
        if not isinstance(surfaces, list) or "v3" not in surfaces:
            raise SafeApiError("candidate_v3_surface_not_allowed")

        # A persistent server-side marker prevents accidental resubmission on this SHA.
        _reserve_once()

        created, _ = _request(
            "POST",
            "/api/v3/creative-agent/projects",
            token,
            {"user_goal": user_input, "primary_template_id": "general_template"},
        )
        project = _project(created)
        project_id = str(project.get("project_id") or "").strip()
        if not ID_PATTERN.fullmatch(project_id):
            raise SafeApiError("candidate_v3_project_id_missing")
        result["project_id"] = project_id

        metadata = {
            "require_real_images": True,
            "requested_image_count": 1,
            "requested_image_size": "1024x1024",
        }
        accepted = None
        try:
            accepted, _ = _request(
                "POST",
                f"/api/v3/creative-agent/projects/{quote(project_id, safe='')}/jobs",
                token,
                {
                    "user_input": user_input,
                    "template_id": "general_template",
                    "metadata": metadata,
                    "auto_generate": {"quality_mode": "standard", "metadata": metadata},
                },
            )
        except SafeApiError as exc:
            # The write outcome may be unknown. Never repeat it; reconcile by project reads only.
            if exc.status is not None and exc.status < 500:
                raise

        timeout_seconds = int(os.getenv("CANDIDATE_V3_TIMEOUT_SECONDS", "3300"))
        if not 60 <= timeout_seconds <= 3600:
            raise SafeApiError("candidate_v3_timeout_invalid")
        deadline = time.monotonic() + timeout_seconds
        job_id = _job_id(None, accepted)
        job_payload: object = accepted
        project_payload: object = None
        while time.monotonic() < deadline:
            try:
                project_payload, _ = _request(
                    "GET",
                    f"/api/v3/creative-agent/projects/{quote(project_id, safe='')}",
                    token,
                )
            except SafeApiError as exc:
                if exc.status in {401, 403, 404}:
                    raise
                time.sleep(10)
                continue
            if not job_id:
                job_id = _job_id(project_payload, accepted)
            operation = _operation(project_payload)
            operation_state = str(operation.get("state") or "").strip().lower()
            operation_id = str(operation.get("operation_id") or "").strip()
            if not job_id and operation_state == "planning_failed":
                raise SafeApiError("candidate_v3_planning_failed")
            if not job_id:
                result["operation_id"] = operation_id
                time.sleep(10)
                continue
            if not ID_PATTERN.fullmatch(job_id):
                raise SafeApiError("candidate_v3_job_id_invalid")
            result["job_id"] = job_id
            try:
                job_payload, _ = _request(
                    "GET",
                    f"/api/v3/creative-agent/jobs/{quote(job_id, safe='')}",
                    token,
                )
            except SafeApiError as exc:
                if exc.status in {401, 403, 404}:
                    raise
                time.sleep(10)
                continue
            job_root = _mapping(job_payload)
            job = _mapping(job_root.get("job")) or job_root
            status = str(job.get("status") or job_root.get("status") or "").strip().lower()
            result["job_status"] = status or "unknown"
            route, reason = _find_route_value(job_payload)
            if route:
                result["route"], result["route_reason"] = route, reason
            if status in {"generated", "failed", "blocked", "cancelled"}:
                break
            time.sleep(10)
        else:
            raise SafeApiError("candidate_v3_generation_timeout")

        if result["job_status"] != "generated":
            raise SafeApiError(f"candidate_v3_job_{result['job_status'] or 'not_generated'}")

        _require_bridge_route(result["route"])

        query = urlencode({"project_id": project_id, "compact": "true", "limit": "60"})
        outputs, _ = _request("GET", f"/api/v3/creative-agent/project-outputs?{query}", token)
        item = _final_delivery_item(outputs, project_id, job_id)
        result["output_count"] = 1
        result["review_status"] = item["review_status"]
        result["certification_state"] = item["certification_state"]
        result["delivery_state"] = item["delivery_state"]

        preview, preview_headers = _request("GET", item["preview_url"], token)
        _validate_image_response(preview, preview_headers, kind="preview")
        result["preview_checks"] = 1

        download, download_headers = _request("GET", item["download_url"], token)
        _validate_image_response(download, download_headers, kind="download")
        result["download_checks"] = 1
        result["result"] = "pass"
        print(json.dumps({key: value for key, value in result.items() if key != "operation_id"}, separators=(",", ":")))
        return 0
    except SafeApiError as exc:
        result["error"] = exc.code
        if exc.status is not None:
            result["http_status"] = exc.status
        print(json.dumps(result, separators=(",", ":")))
        return 2
    finally:
        _write_summary(result)


if __name__ == "__main__":
    sys.exit(_run())
