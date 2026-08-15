"""Private Doc278 evidence for an opaque E-Commerce Provider rejection hold."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from .provider_deliverability_closure import (
    _current_source_binding,
    _physical_reference_bindings,
    _terminal_role_execution_plan_binding,
    _verified_command_binding,
)


_AUDIT_FIELDS = (
    "schema_version",
    "authority",
    "provider_capability_id",
    "provider_name",
    "model",
    "operation",
    "route_identity",
)
_TERMINAL_SOURCES = frozenset(
    {
        "provider_failure_retry.execution_audit",
        "specialized_role_execution.provider_failure",
    }
)
_OPAQUE_FAILURE_CODE = "image_edit_invalid_request_unattributed"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _output_indexes(bindings: list[dict[str, Any]]) -> list[int] | None:
    try:
        indexes = [int(item.get("output_index")) for item in bindings]
    except (AttributeError, TypeError, ValueError):
        return None
    return indexes if indexes == list(range(1, len(indexes) + 1)) else None


def _execution_audit(failure: dict[str, Any]) -> dict[str, Any] | None:
    audit = failure.get("execution_audit")
    if (
        not isinstance(audit, dict)
        or any(not _clean(audit.get(key)) for key in _AUDIT_FIELDS)
        or _clean(audit.get("schema_version")) != "v3_provider_execution_audit_v1"
        or _clean(audit.get("authority")) != "v3_generation_router"
        or _clean(audit.get("operation")) != "image_edit"
    ):
        return None
    return dict(audit)


def _outer_request_count(failure: dict[str, Any]) -> int:
    raw = failure.get("outer_request_count")
    if raw is None and isinstance(failure.get("reference_input_execution"), dict):
        raw = failure["reference_input_execution"].get("outer_request_count")
    try:
        return max(0, int(raw or 0))
    except (TypeError, ValueError):
        return 0


def _canonical_attempts(
    attempts: list[Any],
    *,
    audit: dict[str, Any],
    expected_indexes: list[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]] | None:
    """Keep raw retry history while requiring one final opaque fact per output."""

    grouped: dict[int, list[dict[str, Any]]] = {}
    canonical: list[dict[str, Any]] = []
    for item in attempts:
        if not isinstance(item, dict):
            return None
        try:
            attempt = int(item.get("attempt"))
            output_index = int(item.get("output_index"))
            role_output_index = int(item.get("role_output_index"))
        except (TypeError, ValueError):
            return None
        item_audit = item.get("execution_audit")
        if (
            attempt < 1
            or output_index not in expected_indexes
            or role_output_index != output_index
            or not isinstance(item_audit, dict)
            or item_audit != audit
        ):
            return None
        normalized = {
            "attempt": attempt,
            "output_index": output_index,
            "role_output_index": role_output_index,
            "status": _clean(item.get("status")),
            "classification": _clean(item.get("classification")),
            "failure_code": _clean(item.get("failure_code")),
            "upstream_code": _clean(item.get("upstream_code")),
            "retryable": bool(item.get("retryable")),
            "execution_audit": dict(audit),
        }
        canonical.append(normalized)
        grouped.setdefault(output_index, []).append(normalized)
    if sorted(grouped) != expected_indexes:
        return None

    final_evidence: list[dict[str, Any]] = []
    for output_index in expected_indexes:
        terminal = grouped[output_index][-1]
        if (
            terminal["status"] != "failed"
            or terminal["classification"] != "non_retryable_provider_failure"
            or terminal["failure_code"] != _OPAQUE_FAILURE_CODE
            or terminal["upstream_code"] != "provider_error"
            or terminal["retryable"]
        ):
            return None
        final_evidence.append(
            {
                "output_index": output_index,
                "role_output_index": output_index,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": _OPAQUE_FAILURE_CODE,
                "upstream_code": "provider_error",
                "execution_audit": dict(audit),
            }
        )
    return canonical, final_evidence


def _terminal_receipt(
    record: Any,
    *,
    physical_bindings: list[dict[str, Any]],
) -> dict[str, Any] | None:
    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    failure = metadata.get("provider_failure_retry")
    if not isinstance(failure, dict):
        return None
    if (
        _clean(failure.get("final_status")) != "failed"
        or _clean(failure.get("final_classification")) != "non_retryable_provider_failure"
        or _clean(failure.get("final_failure_code")) != _OPAQUE_FAILURE_CODE
    ):
        return None
    audit = _execution_audit(failure)
    indexes = _output_indexes(physical_bindings)
    attempts = failure.get("attempts")
    source = _clean(failure.get("terminal_receipt_source"))
    created_at = _clean(failure.get("terminal_created_at"))
    if (
        audit is None
        or indexes is None
        or not isinstance(attempts, list)
        or not attempts
        or _outer_request_count(failure) < 1
        or source not in _TERMINAL_SOURCES
        or not created_at
    ):
        return None
    evidence = _canonical_attempts(attempts, audit=audit, expected_indexes=indexes)
    if evidence is None:
        return None
    raw_attempts, final_evidence = evidence
    payload = {
        "schema_version": "doc278_terminal_job_receipt_v1",
        "project_id": _clean(metadata.get("project_id")),
        "terminal_job_id": _clean(getattr(record, "job_id", "")),
        "terminal_status": _clean(
            getattr(getattr(record, "status", None), "value", getattr(record, "status", ""))
        ),
        "final_status": "failed",
        "final_classification": "non_retryable_provider_failure",
        "final_failure_code": _OPAQUE_FAILURE_CODE,
        "outer_request_count": _outer_request_count(failure),
        "provider_attempt_evidence": raw_attempts,
        "provider_attempt_evidence_digest": _digest(raw_attempts),
        "per_output_opaque_evidence": final_evidence,
        "per_output_opaque_evidence_digest": _digest(final_evidence),
        "execution_audit": audit,
        "terminal_receipt_source": source,
        "created_at": created_at,
    }
    if (
        not payload["project_id"]
        or not payload["terminal_job_id"]
        or payload["terminal_status"] not in {"blocked", "failed"}
    ):
        return None
    return {**payload, "receipt_digest": _digest(payload)}


def build_ambiguous_provider_request_hold_receipt(
    record: Any,
    *,
    uploaded_asset_lookup: Callable[[str], Any | None] | None = None,
    generated_output_lookup: Callable[[str], Any | None] | None = None,
    source_job_lookup: Callable[[str], Any | None] | None = None,
    project_goal_snapshot_lookup: Callable[[str, str], dict[str, Any] | None] | None = None,
    command_attempt_association_lookup: Callable[[str, str], dict[str, Any] | None] | None = None,
    output_records_lookup: Callable[[str], list[Any]] | None = None,
) -> dict[str, Any] | None:
    """Build a private receipt only from an actual zero-pixel opaque failure."""

    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    project_id = _clean(metadata.get("project_id"))
    template_id = _clean(metadata.get("template_id"))
    job_id = _clean(getattr(record, "job_id", ""))
    if project_id == "" or template_id != "ecommerce_template" or job_id == "":
        return None
    if not callable(output_records_lookup):
        return None
    try:
        if output_records_lookup(job_id):
            return None
    except Exception:
        return None
    physical_bindings = _physical_reference_bindings(metadata, job_id)
    if physical_bindings is None:
        return None
    execution_plan = _terminal_role_execution_plan_binding(
        metadata,
        job_id=job_id,
        physical_bindings=physical_bindings,
    )
    terminal = _terminal_receipt(record, physical_bindings=physical_bindings)
    if execution_plan is None or terminal is None:
        return None
    command = _verified_command_binding(
        record,
        project_id=project_id,
        template_id=template_id,
        project_goal_snapshot_lookup=project_goal_snapshot_lookup,
        command_attempt_association_lookup=command_attempt_association_lookup,
    )
    if command is None:
        return None
    project_goal, command_direction, canonical_goal_prompt_digest = command
    source_binding = _current_source_binding(
        metadata,
        project_id=project_id,
        job_id=job_id,
        physical_bindings=physical_bindings,
        uploaded_asset_lookup=uploaded_asset_lookup,
        generated_output_lookup=generated_output_lookup,
        source_job_lookup=source_job_lookup,
    )
    frozen_binding = metadata.get("frozen_visual_asset_binding_set")
    current_reference_binding_digest = _clean(metadata.get("current_reference_binding_digest"))
    if (
        source_binding is None
        or not isinstance(frozen_binding, dict)
        or frozen_binding.get("state") != "valid"
        or not isinstance(frozen_binding.get("bindings"), list)
        or len(frozen_binding["bindings"]) != 1
        or not current_reference_binding_digest
    ):
        return None
    _source_record, source_binding_digest = source_binding
    execution_plan_record, execution_plan_digest = execution_plan
    audit = terminal["execution_audit"]
    payload = {
        "schema_version": "doc278_ambiguous_provider_request_hold_receipt_v1",
        "authority": "v3_ecommerce_opaque_provider_hold",
        "project_id": project_id,
        "terminal_job_id": job_id,
        "created_at": terminal["created_at"],
        "terminal_job_receipt_digest": terminal["receipt_digest"],
        "terminal_job_receipt_source": terminal["terminal_receipt_source"],
        "provider_capability_id": _clean(audit.get("provider_capability_id")),
        "provider_name": _clean(audit.get("provider_name")),
        "provider_model": _clean(audit.get("model")),
        "provider_operation": "image_edit",
        "provider_route_identity": _clean(audit.get("route_identity")),
        "canonical_goal_prompt_digest": canonical_goal_prompt_digest,
        "canonical_project_goal_digest": _digest(
            {"template_id": template_id, "project_goal": project_goal}
        ),
        "canonical_command_direction_digest": _digest(
            {"template_id": template_id, "command_direction": command_direction}
        ),
        "requested_output_count": len(physical_bindings),
        "current_reference_binding_digest": current_reference_binding_digest,
        "current_project_source_binding_digest": source_binding_digest,
        "per_output_reference_bindings": physical_bindings,
        "per_output_reference_bindings_digest": _digest(physical_bindings),
        "physical_plan_digests": [item["plan_digest"] for item in physical_bindings],
        "locked_visual_asset_binding_digest": _digest(
            {"bindings": frozen_binding["bindings"]}
        ),
        "selected_continuation_admissions_digest": _digest(
            metadata.get("doc269_selected_continuation_admissions", [])
        ),
        "terminal_role_execution_plan_digest": execution_plan_digest,
        "terminal_role_execution_plan": execution_plan_record,
    }
    if any(
        not _clean(payload[key])
        for key in (
            "provider_capability_id",
            "provider_name",
            "provider_model",
            "provider_route_identity",
        )
    ):
        return None
    return {
        **payload,
        "hold_receipt_id": f"hold_{_digest(payload)[:24]}",
    }


def verified_ambiguous_provider_request_hold_receipt(
    record: Any,
    **kwargs: Any,
) -> dict[str, Any] | None:
    """Read a stored exact receipt or enough complete legacy evidence read-only."""

    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    rebuilt = build_ambiguous_provider_request_hold_receipt(record, **kwargs)
    stored = metadata.get("ambiguous_provider_request_hold_receipt")
    if stored is not None:
        return dict(stored) if isinstance(stored, dict) and rebuilt is not None and stored == rebuilt else None
    return rebuilt


def safe_ambiguous_provider_request_hold_operation(_receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": "ambiguous_provider_request_hold",
        "terminal": True,
        "pending": False,
        "next_actions": [{"id": "review_generation_conditions"}],
    }
