"""Public-safe stage timing trace for remote Brain planning diagnostics.

The trace is opt-in through ``V3_BRAIN_STAGE_TRACE_FILE``.  It records only
component names, stage names, elapsed timing, terminal reason, counts, and
safe booleans.  It must never record endpoint URLs, credentials, prompts,
filesystem paths, provider bodies, job IDs, handoff IDs, or output IDs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
from typing import Any


_TRACE_STARTED_AT = time.monotonic()
_TRACE_SCHEMA_VERSION = "v3_brain_stage_trace_v1"
_SAFE_EXTRA_KEYS = {
    "requested_image_count",
    "stage",
    "terminal_reason",
    "status",
    "error_class",
    "transport_error_class",
    "timeout_phase",
    "timeout_seconds",
    "elapsed_ms",
    "response_started",
    "first_content_observed",
    "complete_response_observed",
    "json_parse_started",
    "json_parse_completed",
    "attempts",
    "json_serialization_recovery_attempted",
    "json_serialization_recovery_succeeded",
    "error_family",
    "json_failure_kind",
    "logical_budget_seconds",
    "remaining_ms",
    "state",
    "remote_contract_rejected_count",
    "remote_contract_rejected_sections",
    "expected_image_count",
    "remote_image_count",
    "remote_shot_plan_count",
    "cardinality_valid",
    "validation_error_count",
    "validation_error_paths",
    "validation_error_types",
    "semantic_recovery_attempted",
    "finalizer_call_count",
    "remote_brain_call_count",
    "remote_http_status_code",
    "exitcode",
}
_SAFE_REJECTED_SECTION_VALUES = {
    "image_set_plan",
    "prompt_guidance",
    "prompt_review",
    "user_visible_summary",
    "visual_task_profile",
    "visual_task_profile.rendering_intent",
    "capability_activation_intent",
    "canonical_provider_prompts",
    "checkpoints",
}
_SAFE_REASON_VALUES = {
    "unknown",
    "cannot_create_jobs",
    "capability_activation_error",
    "local_mcp_planning_timeout",
    "timeout",
    "unavailable",
    "provider_error",
    "validation_error",
    "execution_budget_exhausted",
    "truncated_response",
    "invalid_response",
    "invalid_json_response",
    "content_policy",
    "canceled",
    "upstream_http_error",
    "planned_for_codex_native_imagegen",
    "planned",
    "blocked",
    "generated",
    "completed",
    "complete",
    "failed",
    "passed",
    "rejected",
    "warning",
    "brainprovidererror",
    "brainproviderunavailable",
    "braintransporttimeouterror",
    "brainpromptcontractinvalid",
    "runtimeerror",
    "valueerror",
    "0",
    "1",
    "-1",
}


def stage_trace_enabled() -> bool:
    return bool(_trace_path())


def record_stage_event(
    component: str,
    event: str,
    *,
    stage: str | None = None,
    terminal_reason: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Append one safe event if stage tracing is explicitly enabled."""

    path = _trace_path()
    if path is None:
        return
    record: dict[str, Any] = {
        "schema_version": _TRACE_SCHEMA_VERSION,
        "pid": os.getpid(),
        "elapsed_ms": int((time.monotonic() - _TRACE_STARTED_AT) * 1000),
        "component": _safe_token(component),
        "event": _safe_token(event),
    }
    if stage is not None:
        record["stage"] = _safe_token(stage)
    if terminal_reason is not None:
        record["terminal_reason"] = _safe_reason(terminal_reason)
    for key, value in _safe_extra(extra).items():
        record[key] = value
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
    except OSError:
        # Diagnostics must never change product behavior.
        return


def _trace_path() -> Path | None:
    raw = os.getenv("V3_BRAIN_STAGE_TRACE_FILE")
    if not raw or not raw.strip():
        return None
    return Path(raw).expanduser()


def _safe_extra(extra: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(extra, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, value in extra.items():
        safe_key = _safe_token(key)
        if safe_key not in _SAFE_EXTRA_KEYS:
            continue
        if safe_key in {"terminal_reason", "error_class", "status", "transport_error_class"}:
            cleaned[safe_key] = _safe_reason(value)
        elif safe_key == "logical_budget_seconds":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                cleaned[safe_key] = round(float(value), 3)
        elif safe_key == "remaining_ms":
            if isinstance(value, int) and not isinstance(value, bool):
                cleaned[safe_key] = value
        elif isinstance(value, bool):
            cleaned[safe_key] = value
        elif isinstance(value, int):
            cleaned[safe_key] = value
        elif isinstance(value, float):
            cleaned[safe_key] = round(value, 3)
        elif safe_key == "remote_contract_rejected_sections" and isinstance(value, list):
            sections = []
            for item in value:
                token = _safe_token(item)
                if token in _SAFE_REJECTED_SECTION_VALUES:
                    sections.append(token)
            cleaned[safe_key] = list(dict.fromkeys(sections))[:8]
        elif safe_key in {"validation_error_paths", "validation_error_types"} and isinstance(value, list):
            cleaned[safe_key] = list(dict.fromkeys(_safe_token(item) for item in value))[:8]
        elif value is None:
            cleaned[safe_key] = None
        else:
            cleaned[safe_key] = _safe_token(value)
    return cleaned


def _safe_token(value: Any) -> str:
    token = str(value or "unknown").strip().lower()
    allowed = []
    for char in token[:96]:
        allowed.append(char if char.isalnum() or char in {"_", "-", "."} else "_")
    return "".join(allowed).strip("_") or "unknown"


def _safe_reason(value: Any) -> str:
    token = _safe_token(value)
    return token if token in _SAFE_REASON_VALUES else "unknown"
