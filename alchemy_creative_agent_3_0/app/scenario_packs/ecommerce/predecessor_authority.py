"""Private Doc279 evidence for a transparent E-Commerce planning successor."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable


DOC279_PRIVATE_NAMESPACE = "doc279_ecommerce_transparent_predecessor_receipts"
_SCHEMA_VERSION = "doc279_ecommerce_transparent_predecessor_receipt_v1"
_AUTHORITY = "v3_project_mode"
_SOURCE_RESOLVER_IDENTITY = "doc263_doc269_server_binding_v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value: object) -> str:
    return str(value or "").strip()


def _requested_output_count(metadata: dict[str, Any]) -> int | None:
    try:
        count = int(metadata.get("requested_image_count"))
    except (TypeError, ValueError):
        return None
    return count if count >= 1 else None


def _has_provider_execution(metadata: dict[str, Any]) -> bool:
    """Treat unknown terminal execution evidence as authoritative, never transparent."""

    failure = metadata.get("provider_failure_retry")
    if failure is None:
        return False
    if not isinstance(failure, dict):
        return True
    try:
        outer_request_count = int(
            failure.get("outer_request_count")
            if failure.get("outer_request_count") is not None
            else dict(failure.get("reference_input_execution") or {}).get(
                "outer_request_count",
                0,
            )
        )
    except (TypeError, ValueError):
        return True
    return bool(
        outer_request_count > 0
        or failure.get("execution_audit")
        or failure.get("attempts")
        or failure.get("reference_input_execution")
        or failure.get("terminal_receipt_source")
    )


def build_transparent_predecessor_receipt(
    record: Any,
    *,
    output_records_lookup: Callable[[str], list[Any]] | None,
    provider_route_identity: str,
) -> dict[str, Any] | None:
    """Build E33 evidence only for a durable blocked Job with no execution."""

    request = getattr(record, "request", None)
    metadata = dict(getattr(request, "metadata", {}) or {})
    project_id = _clean(metadata.get("project_id"))
    job_id = _clean(getattr(record, "job_id", ""))
    status = _clean(getattr(getattr(record, "status", None), "value", getattr(record, "status", "")))
    command = metadata.get("doc271_command_binding")
    source = metadata.get("doc271_current_source_binding")
    locked_binding = metadata.get("frozen_visual_asset_binding_set")
    continuations = metadata.get("doc269_selected_continuation_admissions", [])
    requested_output_count = _requested_output_count(metadata)
    current_reference_binding_digest = _clean(metadata.get("current_reference_binding_digest"))
    if (
        project_id == ""
        or job_id == ""
        or status != "blocked"
        or _clean(metadata.get("template_id")) != "ecommerce_template"
        or getattr(record, "planning_result", None) is not None
        or getattr(record, "generation_result", None) is not None
        or not callable(output_records_lookup)
        or _has_provider_execution(metadata)
        or not isinstance(command, dict)
        or not isinstance(source, dict)
        or not isinstance(locked_binding, dict)
        or not isinstance(continuations, list)
        or requested_output_count is None
        or not current_reference_binding_digest
        or not _clean(provider_route_identity)
    ):
        return None
    try:
        if output_records_lookup(job_id):
            return None
    except Exception:
        return None
    command_binding_digest = _clean(command.get("command_binding_digest"))
    source_binding_digest = _clean(source.get("source_binding_digest"))
    if (
        command.get("authority") != _AUTHORITY
        or command.get("project_id") != project_id
        or command.get("template_id") != "ecommerce_template"
        or not command_binding_digest
        or source.get("authority") != _AUTHORITY
        or source.get("project_id") != project_id
        or not source_binding_digest
        or locked_binding.get("state") != "valid"
        or not isinstance(locked_binding.get("bindings"), list)
    ):
        return None
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "authority": _AUTHORITY,
        "project_id": project_id,
        "terminal_job_id": job_id,
        "template_id": "ecommerce_template",
        "terminal_status": "blocked",
        "command_binding_digest": command_binding_digest,
        "current_reference_binding_digest": current_reference_binding_digest,
        "current_source_binding_digest": source_binding_digest,
        "locked_visual_asset_binding": deepcopy(locked_binding),
        "selected_continuation_admissions_digest": _digest(continuations),
        "requested_output_count": requested_output_count,
        "provider_route_identity": provider_route_identity,
        "source_resolver_identity": _SOURCE_RESOLVER_IDENTITY,
        "execution_phase": "pre_provider_planning",
        "outer_request_count": 0,
        "delivered_output_count": 0,
        "terminal": True,
    }
    payload["identity_digest"] = _digest(
        {
            "project_id": project_id,
            "terminal_job_id": job_id,
            "command_binding_digest": command_binding_digest,
        }
    )
    return {**payload, "receipt_digest": _digest(payload)}


def verified_transparent_predecessor_receipt(
    record: Any,
    receipt: object,
    *,
    output_records_lookup: Callable[[str], list[Any]] | None,
    provider_route_identity: str,
) -> dict[str, Any] | None:
    """Rebuild trusted durable facts; a private receipt is never self-authenticating."""

    rebuilt = build_transparent_predecessor_receipt(
        record,
        output_records_lookup=output_records_lookup,
        provider_route_identity=provider_route_identity,
    )
    if not isinstance(receipt, dict) or rebuilt is None or receipt != rebuilt:
        return None
    return deepcopy(rebuilt)
