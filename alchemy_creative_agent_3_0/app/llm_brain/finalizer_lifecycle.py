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
    "request_contract_invalid",
    "timeout",
    "truncated_response",
    "upstream_http_error",
    "upstream_transport_error",
}
REMOTE_BRAIN_REQUEST_ACCEPTANCE_STATES = {
    "not_started",
    "dispatched",
    "unknown",
}


def remote_brain_receipts_are_monotonic(
    *,
    request_started: Any = None,
    request_acceptance: Any = None,
    finalizer_lifecycle: dict[str, Any] | None = None,
    transport_attempt: dict[str, Any] | None = None,
    transport_failure: dict[str, Any] | None = None,
) -> bool:
    """Check cross-receipt lifecycle monotonicity after local sanitization.

    The aggregate attempt may summarize an earlier retry, so a positive
    aggregate fact is not required to agree with a weaker current-stage
    receipt. The reverse direction is strict: current-stage evidence that a
    request or response was observed must not be projected alongside an
    aggregate receipt that says no such event occurred.
    """

    if request_started is not None and not isinstance(request_started, bool):
        return False
    if request_acceptance is not None and (
        not isinstance(request_acceptance, str)
        or request_acceptance not in REMOTE_BRAIN_REQUEST_ACCEPTANCE_STATES
    ):
        return False
    if request_started is not None and request_acceptance is not None:
        if request_started is not (request_acceptance == "dispatched"):
            return False

    # A bare call-entry boolean is not acceptance evidence. It is valid for
    # this top-level field to be omitted when a nested lifecycle or transport
    # receipt supplies the authoritative acceptance, but an isolated
    # ``request_started=True`` must never survive projection.
    if request_started is True and request_acceptance is None:
        nested_dispatched = bool(
            isinstance(finalizer_lifecycle, dict)
            and finalizer_lifecycle.get("remote_brain_request_started") is True
            and finalizer_lifecycle.get("remote_brain_request_acceptance") == "dispatched"
        )
        transport_dispatched = bool(
            isinstance(transport_attempt, dict)
            and transport_attempt.get("request_dispatched") is True
        )
        failure_dispatched = bool(
            isinstance(transport_failure, dict)
            and transport_failure.get("request_acceptance") == "dispatched"
        )
        if not (nested_dispatched or transport_dispatched or failure_dispatched):
            return False

    if transport_attempt is None:
        return True

    request_dispatched = transport_attempt.get("request_dispatched") is True
    response_started = transport_attempt.get("response_started") is True
    if request_started is True and not request_dispatched:
        return False
    if request_acceptance == "dispatched" and not request_dispatched:
        return False

    if finalizer_lifecycle is not None:
        if (
            finalizer_lifecycle.get("remote_brain_request_started") is True
            and not request_dispatched
        ):
            return False
        if finalizer_lifecycle.get("response_started") is True and not response_started:
            return False

    if transport_failure is not None:
        failure_acceptance = transport_failure.get("request_acceptance")
        if failure_acceptance == "dispatched" and not request_dispatched:
            return False
        if transport_failure.get("response_started") is True and not response_started:
            return False

    return True


def build_remote_brain_finalizer_lifecycle(
    *,
    stage: str,
    provider_available: bool,
    remote_brain_request_started: bool,
    response_started: bool,
    failure_code: str,
    remote_brain_request_acceptance: str,
) -> dict[str, Any]:
    """Build a closed finalizer lifecycle fact from server-owned evidence."""

    return safe_remote_brain_finalizer_lifecycle(
        {
            "schema_version": REMOTE_BRAIN_FINALIZER_LIFECYCLE_SCHEMA_VERSION,
            "stage": str(stage or "").strip(),
            "provider_available": provider_available,
            "remote_brain_request_started": remote_brain_request_started,
            "remote_brain_request_acceptance": remote_brain_request_acceptance,
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
    if value.get("schema_version") != REMOTE_BRAIN_FINALIZER_LIFECYCLE_SCHEMA_VERSION:
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
    acceptance = value.get("remote_brain_request_acceptance")
    if not isinstance(acceptance, str) or acceptance not in REMOTE_BRAIN_REQUEST_ACCEPTANCE_STATES:
        return {}
    # Explicit acceptance is authoritative over the legacy booleans. A
    # call-entry observation is not proof that upstream accepted bytes; only
    # ``dispatched`` may set request_started or response_started.
    if request_started is not (acceptance == "dispatched"):
        return {}
    if response_started and acceptance != "dispatched":
        return {}
    # A provider-unavailable preflight cannot have entered an accepted
    # request, and a response can only exist after the provider was available.
    if not provider_available and acceptance != "not_started":
        return {}
    if (request_started or response_started) and not provider_available:
        return {}
    if response_started and request_started is not True:
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
        "remote_brain_request_acceptance": acceptance,
    }
