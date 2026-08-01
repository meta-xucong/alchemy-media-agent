"""Public-safe Remote Brain finalizer lifecycle projection.

This module owns the closed contract shared by Brain adapter audit,
ScenarioRuntime blocked outcomes, and ProductApi public status.  Keeping the
schema here prevents those three sanitizer boundaries from drifting while still
letting each layer decide when it is allowed to emit the fact.
"""

from __future__ import annotations

from typing import Any


REMOTE_BRAIN_FINALIZER_LIFECYCLE_SCHEMA_VERSION = "v3_remote_brain_finalizer_lifecycle_v1"
REMOTE_BRAIN_FINALIZER_STAGE = "provider_prompt_finalize"
REMOTE_BRAIN_FINALIZER_FAILURE_FAMILY = "remote_brain_signoff"

REMOTE_BRAIN_FINALIZER_LIFECYCLE_FAILURE_CODES = {
    "canceled",
    "content_policy",
    "execution_budget_exhausted",
    "invalid_response",
    "provider_error",
    "provider_unavailable",
    "timeout",
    "truncated_response",
    "upstream_http_error",
    "upstream_transport_error",
}


def build_remote_brain_finalizer_lifecycle(
    *,
    stage: str,
    provider_available: bool,
    remote_brain_request_started: bool,
    response_started: bool,
    failure_code: str,
) -> dict[str, Any]:
    """Build a closed finalizer lifecycle fact from server-owned evidence."""

    return safe_remote_brain_finalizer_lifecycle(
        {
            "schema_version": REMOTE_BRAIN_FINALIZER_LIFECYCLE_SCHEMA_VERSION,
            "stage": str(stage or "").strip(),
            "provider_available": provider_available,
            "remote_brain_request_started": remote_brain_request_started,
            "response_started": response_started,
            "status": "blocked",
            "failure_family": REMOTE_BRAIN_FINALIZER_FAILURE_FAMILY,
            "failure_code": str(failure_code or "").strip(),
        }
    )


def safe_remote_brain_finalizer_lifecycle(value: Any) -> dict[str, Any]:
    """Project only the closed public-safe lifecycle fields."""

    if not isinstance(value, dict):
        return {}
    if str(value.get("stage") or "").strip() != REMOTE_BRAIN_FINALIZER_STAGE:
        return {}
    provider_available = value.get("provider_available")
    request_started = value.get("remote_brain_request_started")
    response_started = value.get("response_started")
    if not all(isinstance(item, bool) for item in (provider_available, request_started, response_started)):
        return {}
    if str(value.get("status") or "").strip() != "blocked":
        return {}
    if str(value.get("failure_family") or "").strip() != REMOTE_BRAIN_FINALIZER_FAILURE_FAMILY:
        return {}
    failure_code = str(value.get("failure_code") or "").strip()
    if failure_code not in REMOTE_BRAIN_FINALIZER_LIFECYCLE_FAILURE_CODES:
        return {}
    return {
        "schema_version": REMOTE_BRAIN_FINALIZER_LIFECYCLE_SCHEMA_VERSION,
        "stage": REMOTE_BRAIN_FINALIZER_STAGE,
        "provider_available": provider_available,
        "remote_brain_request_started": request_started,
        "response_started": response_started,
        "status": "blocked",
        "failure_family": REMOTE_BRAIN_FINALIZER_FAILURE_FAMILY,
        "failure_code": failure_code,
    }
