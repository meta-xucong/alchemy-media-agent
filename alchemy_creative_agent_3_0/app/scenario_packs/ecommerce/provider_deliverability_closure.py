"""Doc271's private E-Commerce provider-deliverability closure evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable

from .physical_renderer_reference_plan import (
    PhysicalRendererReferencePlan,
)
from .reference_projection import PhysicalProductReferenceProjection, ProductTruthAdmission


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_AUDIT_FIELDS = (
    "provider_capability_id",
    "provider_name",
    "model",
    "operation",
    "route_identity",
)
_TERMINAL_RECEIPT_SOURCES = frozenset(
    {
        "provider_failure_retry.execution_audit",
        "specialized_role_execution.provider_failure",
    }
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _terminal_policy_evidence(attempts: list[Any]) -> list[dict[str, Any]] | None:
    """Canonicalize durable retry attempts for terminal receipt authentication."""

    evidence: list[dict[str, Any]] = []
    for item in attempts:
        if not isinstance(item, dict):
            return None
        try:
            attempt = int(item.get("attempt"))
        except (TypeError, ValueError):
            return None
        if attempt < 1:
            return None
        output_index = item.get("output_index")
        try:
            output_index = int(output_index) if output_index is not None else None
        except (TypeError, ValueError):
            return None
        evidence.append(
            {
                "attempt": attempt,
                "output_index": output_index,
                "status": _clean(item.get("status")),
                "classification": _clean(item.get("classification")),
                "failure_code": _clean(item.get("failure_code")),
                "upstream_code": _clean(item.get("upstream_code")),
                "role_key": _clean(item.get("role_key")),
                "role_output_index": item.get("role_output_index"),
                "execution_audit": dict(item.get("execution_audit") or {})
                if isinstance(item.get("execution_audit"), dict)
                else {},
            }
        )
    return evidence


def _normalized_final_policy_evidence(
    attempts: list[Any],
    *,
    execution_audit: dict[str, Any],
    expected_output_indexes: list[int] | None = None,
) -> list[dict[str, Any]] | None:
    """Derive one canonical final refusal per output from durable attempts.

    Current Product API writes this result once.  A complete historical record
    may be read-only recognized when the same derivation is independently
    possible; ambiguous or partial retry history fails open.
    """

    grouped: dict[int, list[dict[str, Any]]] = {}
    for item in attempts:
        if not isinstance(item, dict):
            return None
        try:
            output_index = int(item.get("output_index"))
            role_output_index = int(item.get("role_output_index"))
        except (TypeError, ValueError):
            return None
        if output_index < 1 or role_output_index != output_index or item.get("execution_audit") != execution_audit:
            return None
        grouped.setdefault(output_index, []).append(item)
    indexes = sorted(grouped)
    if not indexes or indexes != (expected_output_indexes or list(range(1, len(indexes) + 1))):
        return None
    evidence: list[dict[str, Any]] = []
    for output_index in indexes:
        terminal = grouped[output_index][-1]
        if (
            _clean(terminal.get("status")) != "failed"
            or _clean(terminal.get("classification")) != "non_retryable_provider_failure"
            or _clean(terminal.get("failure_code")) != "provider_policy_blocked"
            or _clean(terminal.get("upstream_code")) != "content_policy_violation"
        ):
            return None
        evidence.append(
            {
                "output_index": output_index,
                "role_output_index": output_index,
                "status": "failed",
                "classification": "non_retryable_provider_failure",
                "failure_code": "provider_policy_blocked",
                "upstream_code": "content_policy_violation",
                "execution_audit": dict(execution_audit),
            }
        )
    return evidence


def _terminal_job_receipt(record: Any) -> dict[str, Any] | None:
    """Rebuild the canonical digest that authenticates a terminal Job fact."""

    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    failure = metadata.get("provider_failure_retry")
    if not isinstance(failure, dict):
        return None
    attempts = failure.get("attempts")
    audit = failure.get("execution_audit")
    if not isinstance(attempts, list) or not attempts or not isinstance(audit, dict):
        return None
    if (
        _clean(failure.get("final_status")) != "failed"
        or _clean(failure.get("final_classification")) != "non_retryable_provider_failure"
        or _clean(failure.get("final_failure_code")) != "provider_policy_blocked"
    ):
        return None
    policy_evidence = _terminal_policy_evidence(attempts)
    final_policy_evidence = failure.get("doc271_per_output_policy_evidence")
    derived_evidence = _normalized_final_policy_evidence(
        attempts,
        execution_audit=audit,
    )
    if (
        policy_evidence is None
        or derived_evidence is None
        or (final_policy_evidence is not None and final_policy_evidence != derived_evidence)
    ):
        return None
    final_policy_evidence = derived_evidence
    terminal_receipt_source = _clean(failure.get("terminal_receipt_source"))
    if terminal_receipt_source not in _TERMINAL_RECEIPT_SOURCES:
        return None
    values = {
        "project_id": _clean(metadata.get("project_id")),
        "terminal_job_id": _clean(getattr(record, "job_id", "")),
        "terminal_status": _clean(getattr(getattr(record, "status", None), "value", getattr(record, "status", ""))),
        "provider_failure_code": _clean(failure.get("final_failure_code")),
        "provider_failure_classification": _clean(failure.get("final_classification")),
        "policy_evidence_code": "content_policy_violation",
        "provider_attempt_evidence": policy_evidence,
        "provider_attempt_evidence_digest": _digest(policy_evidence),
        "per_output_policy_evidence": final_policy_evidence,
        "per_output_policy_evidence_digest": _digest(final_policy_evidence),
        "terminal_receipt_source": terminal_receipt_source,
        # This is persisted when the terminal fact is first recorded.  It is
        # never derived from wall-clock time while a receipt is read.
        "created_at": _clean(failure.get("terminal_created_at")),
    }
    if not all(values.values()) or any(not _clean(audit.get(key)) for key in ("schema_version", "authority", *_REQUIRED_AUDIT_FIELDS)):
        return None
    payload = {
        "schema_version": "doc271_terminal_job_receipt_v1",
        **values,
        "execution_audit": dict(audit),
    }
    return {**payload, "receipt_digest": _digest(payload)}


def _verified_terminal_job_receipt(record: Any) -> dict[str, Any] | None:
    expected = _terminal_job_receipt(record)
    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    stored = metadata.get("doc271_terminal_job_receipt")
    if expected is None or not isinstance(stored, dict) or stored != expected:
        return None
    return expected


def _all_output_policy_evidence(
    metadata: dict[str, Any],
    bindings: list[dict[str, Any]],
    execution_audit: dict[str, Any],
) -> bool:
    """Require one attributable terminal policy fact for every frozen output."""

    failure = metadata.get("provider_failure_retry")
    attempts = failure.get("attempts") if isinstance(failure, dict) else None
    persisted_evidence = failure.get("doc271_per_output_policy_evidence") if isinstance(failure, dict) else None
    expected_indexes = [item["output_index"] for item in bindings]
    derived_evidence = _normalized_final_policy_evidence(
        attempts if isinstance(attempts, list) else [],
        execution_audit=execution_audit,
        expected_output_indexes=expected_indexes,
    )
    if derived_evidence is None or (persisted_evidence is not None and persisted_evidence != derived_evidence):
        return False
    expected_evidence = [
        {
            "output_index": item["output_index"],
            "role_output_index": item["output_index"],
            "status": "failed",
            "classification": "non_retryable_provider_failure",
            "failure_code": "provider_policy_blocked",
            "upstream_code": "content_policy_violation",
            "execution_audit": dict(execution_audit),
        }
        for item in bindings
    ]
    return derived_evidence == expected_evidence


def _canonical_final_policy_evidence(value: list[Any]) -> bool:
    """Validate the normalized final policy fact, never a raw retry attempt."""

    indexes: list[int] = []
    for item in value:
        if not isinstance(item, dict):
            return False
        try:
            index = int(item.get("output_index"))
            role_index = int(item.get("role_output_index"))
        except (TypeError, ValueError):
            return False
        if (
            index < 1
            or role_index != index
            or _clean(item.get("status")) != "failed"
            or _clean(item.get("classification")) != "non_retryable_provider_failure"
            or _clean(item.get("failure_code")) != "provider_policy_blocked"
            or _clean(item.get("upstream_code")) != "content_policy_violation"
            or not isinstance(item.get("execution_audit"), dict)
        ):
            return False
        indexes.append(index)
    return indexes == list(range(1, len(indexes) + 1))


def _physical_reference_bindings(metadata: dict[str, Any], job_id: str) -> list[dict[str, Any]] | None:
    """Read every complete, byte-verified Doc269 plan for one closure.

    A set closure is authoritative only when its projections and final plans
    form the same exact, contiguous output-index set.  A valid first plan is
    never evidence for a missing, drifted, or cross-output sibling.
    """

    raw_plans = metadata.get("physical_renderer_reference_plans")
    raw_projections = metadata.get("professional_ecommerce_physical_product_projections")
    if (
        not isinstance(raw_plans, dict)
        or not isinstance(raw_projections, dict)
        or not raw_plans
        or set(raw_plans) != set(raw_projections)
    ):
        return None
    try:
        output_keys = sorted(raw_plans, key=lambda key: int(str(key)))
    except (TypeError, ValueError):
        return None
    if output_keys != [str(index) for index in range(1, len(output_keys) + 1)]:
        return None
    bindings: list[dict[str, Any]] = []
    for key in output_keys:
        try:
            plan = PhysicalRendererReferencePlan.model_validate(raw_plans[key])
            projection = PhysicalProductReferenceProjection.from_mapping(raw_projections[key])
        except (TypeError, ValueError):
            return None
        if (
            plan.job_id != job_id
            or plan.output_index != int(key)
            or projection.job_id != job_id
            or projection.output_index != plan.output_index
            or projection.projection_digest != plan.projection_digest
        ):
            return None
        references = [entry.model_dump(mode="json") for entry in plan.references]
        product = [item for item in references if item["channel"] == "product_truth"]
        faces = [item for item in references if item["channel"] == "people_identity"]
        continuation = [item for item in references if item["channel"] == "generated_selected"]
        if len(product) != 1 or len(faces) != 3 or len(continuation) > 1:
            return None
        if [item["channel"] for item in references] != ["product_truth", "people_identity", "people_identity", "people_identity"] + (["generated_selected"] if continuation else []):
            return None
        if [item["role"] for item in references] != ["product_reference", "face_reference", "face_reference", "face_reference"] + (["selected_continuation_reference"] if continuation else []):
            return None
        if [item["source_type"] for item in references] != ["uploaded", "visual_asset_library", "visual_asset_library", "visual_asset_library"] + (["generated_selected"] if continuation else []):
            return None
        if any(not _SHA256.fullmatch(_clean(item.get("content_sha256")).lower()) for item in references):
            return None
        for item in references:
            try:
                path = Path(_clean(item.get("file_path"))).resolve(strict=True)
                actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, RuntimeError, ValueError):
                return None
            if not path.is_file() or actual_digest != item["content_sha256"]:
                return None
        binding = {
            "ordered_reference_ids": [item["reference_id"] for item in references],
            "ordered_reference_channels": [item["channel"] for item in references],
            "ordered_reference_roles": [item["role"] for item in references],
            "ordered_reference_source_types": [item["source_type"] for item in references],
            "ordered_reference_sha256": [item["content_sha256"] for item in references],
            "locked_face_output_ids": [item["reference_id"] for item in faces],
            "selected_continuation_output_id": continuation[0]["reference_id"] if continuation else "",
            "selected_continuation_sha256": continuation[0]["content_sha256"] if continuation else "",
        }
        bindings.append(
            {
                "output_index": plan.output_index,
                "projection_digest": projection.projection_digest,
                "plan_digest": plan.plan_digest,
                "reference_binding": binding,
                "reference_binding_digest": _digest(binding),
            }
        )
    return bindings


def _terminal_role_execution_plan_binding(
    metadata: dict[str, Any],
    *,
    job_id: str,
    physical_bindings: list[dict[str, Any]],
) -> tuple[dict[str, Any], str] | None:
    """Authenticate the frozen all-output execution plan against Doc269 plans.

    The executor plan does not choose images or output count. It is a strict
    server-generated projection of already-admitted physical plans, so a
    mutable execution record cannot redefine which outputs need terminal
    policy evidence for a closure.
    """

    indexes = [item.get("output_index") for item in physical_bindings]
    if indexes != list(range(1, len(indexes) + 1)):
        return None
    expected = {
        "schema_version": "doc271_ecommerce_terminal_role_execution_v1",
        "authority": "v3_product_api",
        "job_id": job_id,
        "requested_image_count": len(indexes),
        "role_recipes": [
            {
                "role_key": f"ecommerce_output_{output_index}",
                "output_index": output_index,
                "label": f"E-Commerce output {output_index}",
                "purpose": "frozen_terminal_evidence_only",
            }
            for output_index in indexes
        ],
        "policy": {
            "mode": "professional_ecommerce_terminal_evidence",
            "generated_output_reference_chain": "explicit_references_only",
        },
        "metadata": {
            "scenario_id": "ecommerce",
            "professional_ecommerce": True,
            "require_independent_role_terminal_states": True,
            "terminal_attempt_limit_per_output": 1,
            "terminal_evidence_only": True,
        },
    }
    raw = metadata.get("specialized_role_execution_plan")
    if not isinstance(raw, dict) or raw != expected:
        return None
    return expected, _digest(expected)


def _current_source_binding(
    metadata: dict[str, Any],
    *,
    project_id: str,
    job_id: str,
    physical_bindings: list[dict[str, Any]],
    uploaded_asset_lookup: Callable[[str], Any | None] | None,
    generated_output_lookup: Callable[[str], Any | None] | None,
    source_job_lookup: Callable[[str], Any | None] | None,
) -> tuple[dict[str, Any], str] | None:
    """Verify Project Mode's complete active-source record against Doc263/269 facts."""

    raw = metadata.get("doc271_current_source_binding")
    expected_keys = {
        "schema_version",
        "authority",
        "project_id",
        "sources",
        "source_binding_digest",
    }
    source_keys = {
        "ordinal",
        "asset_id",
        "content_sha256",
        "source_type",
        "use_policy",
        "persisted_role",
        "reference_channel",
        "continuation_role",
        "continuation_channel",
    }
    if (
        not isinstance(raw, dict)
        or set(raw) != expected_keys
        or raw.get("schema_version") != "doc271_current_project_source_binding_v1"
        or raw.get("authority") != "v3_project_mode"
        or raw.get("project_id") != project_id
        or not isinstance(raw.get("sources"), list)
        or not _SHA256.fullmatch(_clean(raw.get("source_binding_digest")))
    ):
        return None
    sources = raw["sources"]
    if not sources or any(not isinstance(item, dict) or set(item) != source_keys for item in sources):
        return None
    canonical_sources: list[dict[str, Any]] = []
    for ordinal, item in enumerate(sources, start=1):
        if (
            item.get("ordinal") != ordinal
            or not all(isinstance(item.get(key), str) and _clean(item.get(key)) for key in source_keys - {"ordinal"})
            or not _SHA256.fullmatch(_clean(item.get("content_sha256")).lower())
        ):
            return None
        canonical_sources.append(dict(item))
    expected_digest = _digest(
        {
            "schema_version": "doc271_current_project_source_binding_v1",
            "project_id": project_id,
            "sources": canonical_sources,
        }
    )
    if raw["source_binding_digest"] != expected_digest:
        return None
    if (
        not callable(uploaded_asset_lookup)
        or not callable(generated_output_lookup)
        or not callable(source_job_lookup)
    ):
        return None
    raw_admissions = metadata.get("doc269_selected_continuation_admissions", [])
    if not isinstance(raw_admissions, list) or len(raw_admissions) > 1:
        return None
    admissions_by_output = {
        _clean(item.get("output_id")): item
        for item in raw_admissions
        if isinstance(item, dict) and _clean(item.get("output_id"))
    }
    if len(admissions_by_output) != len(raw_admissions):
        return None
    for item in canonical_sources:
        if item["source_type"] not in {"uploaded", "generated_selected"}:
            return None
        if item["source_type"] == "generated_selected":
            admission = admissions_by_output.get(item["asset_id"])
            if (
                not isinstance(admission, dict)
                or _clean(admission.get("selection_authority")) != "doc265_project_mode"
                or _clean(admission.get("project_id")) != project_id
                or _clean(admission.get("output_id")) != item["asset_id"]
                or _clean(admission.get("content_sha256")).lower() != item["content_sha256"]
                or _clean(admission.get("source_type")) != "generated_selected"
                or _clean(admission.get("use_policy")) != "style"
                or _clean(admission.get("role")) != "selected_continuation_reference"
                or _clean(admission.get("channel")) != "generated_selected"
                or item["reference_channel"] != "generated_selected"
                or item["continuation_role"] != "selected_continuation_reference"
                or item["continuation_channel"] != "generated_selected"
                or item["use_policy"] != "style"
                or item["persisted_role"] != "generated_output"
            ):
                return None
            source_job_id = _clean(admission.get("source_job_id"))
            candidate_id = _clean(admission.get("candidate_id"))
            project_job_ids = admission.get("project_job_ids")
            output = generated_output_lookup(item["asset_id"])
            source_job = source_job_lookup(source_job_id)
            path = Path(str(getattr(output, "file_path", "") or "")) if output else None
            if (
                not source_job_id
                or not candidate_id
                or not isinstance(project_job_ids, list)
                or source_job_id not in project_job_ids
                or len(project_job_ids) != len(set(project_job_ids))
                or any(not _clean(value) for value in project_job_ids)
                or output is None
                or _clean(getattr(getattr(source_job, "request", None), "metadata", {}).get("project_id"))
                != project_id
                or _clean(getattr(output, "output_id", "")) != item["asset_id"]
                or _clean(getattr(output, "job_id", "")) != source_job_id
                or _clean(getattr(output, "candidate_id", "")) != candidate_id
                or path is None
                or not path.is_file()
            ):
                return None
            try:
                if hashlib.sha256(path.read_bytes()).hexdigest() != item["content_sha256"]:
                    return None
            except OSError:
                return None
            continue
        if item["reference_channel"] not in {"product_truth", "uploaded_reference"}:
            return None
        if item["reference_channel"] == "product_truth" and item["use_policy"] != "product":
            return None
        if item["reference_channel"] == "uploaded_reference" and item["use_policy"] == "product":
            return None
        if item["persisted_role"] not in {"product_reference", "subject_reference"}:
            return None
        upload = uploaded_asset_lookup(item["asset_id"])
        path = Path(str(getattr(upload, "file_path", "") or "")) if upload else None
        if (
            upload is None
            or str(getattr(upload, "role", "") or "").strip() != item["persisted_role"]
            or path is None
            or not path.is_file()
        ):
            return None
        try:
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["content_sha256"]:
                return None
        except OSError:
            return None
    try:
        admission = ProductTruthAdmission.from_mapping(
            metadata.get("professional_ecommerce_product_truth_admission")
        )
    except ValueError:
        return None
    if admission.project_id != project_id or admission.job_id != job_id:
        return None
    product_sources = [item for item in canonical_sources if item["reference_channel"] == "product_truth"]
    expected_products = [
        {
            "asset_id": item.asset_id,
            "content_sha256": item.content_sha256,
            "reference_channel": item.product_truth_channel,
        }
        for item in admission.sources
    ]
    actual_products = [
        {
            "asset_id": item["asset_id"],
            "content_sha256": item["content_sha256"],
            "reference_channel": item["reference_channel"],
        }
        for item in product_sources
    ]
    if sorted(actual_products, key=lambda item: item["asset_id"]) != sorted(
        expected_products,
        key=lambda item: item["asset_id"],
    ):
        return None
    for physical in physical_bindings:
        binding = physical["reference_binding"]
        selected_product = next(
            (
                item
                for item in product_sources
                if item["asset_id"] == binding["ordered_reference_ids"][0]
                and item["content_sha256"] == binding["ordered_reference_sha256"][0]
            ),
            None,
        )
        if selected_product is None or binding["ordered_reference_roles"][0] != "product_reference":
            return None
    continuation = [item for item in canonical_sources if item["reference_channel"] == "generated_selected"]
    if len(continuation) > 1:
        return None
    for physical in physical_bindings:
        binding = physical["reference_binding"]
        if binding["selected_continuation_output_id"]:
            if len(continuation) != 1:
                return None
            item = continuation[0]
            if (
                item["asset_id"] != binding["selected_continuation_output_id"]
                or item["content_sha256"] != binding["selected_continuation_sha256"]
                or item["source_type"] != "generated_selected"
                or item["continuation_role"] != "selected_continuation_reference"
                or item["continuation_channel"] != "generated_selected"
            ):
                return None
        elif continuation:
            return None
    return {**raw, "sources": canonical_sources}, expected_digest


def _verified_command_binding(
    record: Any,
    *,
    project_id: str,
    template_id: str,
    project_goal_snapshot_lookup: Callable[[str, str], dict[str, Any] | None] | None,
    command_attempt_association_lookup: Callable[[str, str], dict[str, Any] | None] | None,
) -> tuple[str, str, str] | None:
    """Authenticate Project Mode's immutable goal snapshot against the Job."""

    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    raw = metadata.get("doc271_command_binding")
    expected_keys = {
        "schema_version",
        "authority",
        "project_id",
        "template_id",
        "command_attempt_id",
        "goal_snapshot_id",
        "goal_snapshot_digest",
        "command_direction",
        "command_binding_digest",
    }
    if (
        not isinstance(raw, dict)
        or set(raw) != expected_keys
        or raw.get("schema_version") != "doc271_command_binding_v1"
        or raw.get("authority") != "v3_project_mode"
        or raw.get("project_id") != project_id
        or raw.get("template_id") != template_id
        or not callable(project_goal_snapshot_lookup)
        or not callable(command_attempt_association_lookup)
    ):
        return None
    snapshot_id = _clean(raw.get("goal_snapshot_id"))
    command_attempt_id = _clean(raw.get("command_attempt_id"))
    snapshot = project_goal_snapshot_lookup(project_id, snapshot_id)
    association = command_attempt_association_lookup(project_id, command_attempt_id)
    if not isinstance(snapshot, dict):
        return None
    snapshot_keys = {
        "schema_version",
        "authority",
        "snapshot_id",
        "project_id",
        "template_id",
        "command_attempt_id",
        "project_goal",
        "snapshot_digest",
    }
    if (
        set(snapshot) != snapshot_keys
        or snapshot.get("schema_version") != "doc271_project_goal_snapshot_v1"
        or snapshot.get("authority") != "v3_project_mode"
        or snapshot.get("snapshot_id") != snapshot_id
        or snapshot.get("project_id") != project_id
        or snapshot.get("template_id") != template_id
        or snapshot.get("command_attempt_id") != command_attempt_id
        or not isinstance(association, dict)
        or association.get("authority") != "v3_project_mode"
        or association.get("project_id") != project_id
        or association.get("template_id") != template_id
        or association.get("command_attempt_id") != command_attempt_id
        or association.get("snapshot_id") != snapshot_id
        or association.get("job_id") != _clean(getattr(record, "job_id", ""))
    ):
        return None
    snapshot_payload = {key: snapshot[key] for key in snapshot_keys - {"snapshot_digest"}}
    if (
        snapshot.get("snapshot_digest") != _digest(snapshot_payload)
        or raw.get("goal_snapshot_digest") != snapshot["snapshot_digest"]
    ):
        return None
    project_goal = _clean(snapshot.get("project_goal"))
    command_direction = _clean(raw.get("command_direction"))
    if (
        not project_goal
        or not command_direction
        or command_direction != _clean(getattr(getattr(record, "request", None), "user_input", ""))
    ):
        return None
    binding_payload = {
        "template_id": template_id,
        "project_id": project_id,
        "command_attempt_id": command_attempt_id,
        "goal_snapshot_id": snapshot_id,
        "goal_snapshot_digest": snapshot["snapshot_digest"],
        "command_direction": command_direction,
    }
    if raw.get("command_binding_digest") != _digest(binding_payload):
        return None
    return project_goal, command_direction, _digest(
        {
            "template_id": template_id,
            "project_goal": project_goal,
            "command_direction": command_direction,
        }
    )


def build_provider_deliverability_closure_receipt(
    record: Any,
    *,
    uploaded_asset_lookup: Callable[[str], Any | None] | None = None,
    generated_output_lookup: Callable[[str], Any | None] | None = None,
    source_job_lookup: Callable[[str], Any | None] | None = None,
    project_goal_snapshot_lookup: Callable[[str, str], dict[str, Any] | None] | None = None,
    command_attempt_association_lookup: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    """Build one immutable receipt only from complete terminal durable facts."""

    request = getattr(record, "request", None)
    metadata = dict(getattr(request, "metadata", {}) or {})
    terminal = _verified_terminal_job_receipt(record)
    if terminal is None:
        return None
    failure = metadata["provider_failure_retry"]
    audit = dict(failure["execution_audit"])
    if (
        terminal["terminal_status"] not in {"blocked", "failed"}
        or terminal["provider_failure_code"] != "provider_policy_blocked"
        or terminal["policy_evidence_code"] != "content_policy_violation"
        or audit.get("schema_version") != "v3_provider_execution_audit_v1"
        or audit.get("authority") != "v3_generation_router"
    ):
        return None
    project_id = _clean(metadata.get("project_id"))
    template_id = _clean(metadata.get("template_id"))
    job_id = _clean(getattr(record, "job_id", ""))
    if not project_id or template_id != "ecommerce_template" or not job_id:
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
    project_goal, command_direction, expected_command_digest = command
    physical_bindings = _physical_reference_bindings(metadata, job_id)
    execution_plan = (
        _terminal_role_execution_plan_binding(
            metadata,
            job_id=job_id,
            physical_bindings=physical_bindings,
        )
        if physical_bindings is not None
        else None
    )
    frozen_binding = metadata.get("frozen_visual_asset_binding_set")
    if (
        physical_bindings is None
        or execution_plan is None
        or not _all_output_policy_evidence(metadata, physical_bindings, audit)
        or not isinstance(frozen_binding, dict)
        or frozen_binding.get("state") != "valid"
    ):
        return None
    bindings = frozen_binding.get("bindings")
    if not isinstance(bindings, list) or len(bindings) != 1:
        return None
    current_source_binding = _current_source_binding(
        metadata,
        project_id=project_id,
        job_id=job_id,
        physical_bindings=physical_bindings,
        uploaded_asset_lookup=uploaded_asset_lookup,
        generated_output_lookup=generated_output_lookup,
        source_job_lookup=source_job_lookup,
    )
    if current_source_binding is None:
        return None
    _source_record, current_source_binding_digest = current_source_binding
    _execution_plan, execution_plan_digest = execution_plan
    payload = {
        "schema_version": "doc271_provider_deliverability_closure_receipt_v1",
        "authority": "v3_provider_deliverability_closure",
        "project_id": project_id,
        "terminal_job_id": job_id,
        "created_at": terminal["created_at"],
        "terminal_job_receipt_digest": terminal["receipt_digest"],
        "terminal_job_receipt_source": terminal["terminal_receipt_source"],
        "policy_evidence_class": "explicit_content_policy_violation",
        "provider_capability_id": _clean(audit.get("provider_capability_id")),
        "provider_name": _clean(audit.get("provider_name")),
        "provider_model": _clean(audit.get("model")),
        "provider_operation": _clean(audit.get("operation")),
        "provider_route_identity": _clean(audit.get("route_identity")),
        "canonical_goal_prompt_digest": expected_command_digest,
        "canonical_project_goal_digest": _digest(
            {"template_id": template_id, "project_goal": project_goal}
        ),
        "canonical_command_direction_digest": _digest(
            {"template_id": template_id, "command_direction": command_direction}
        ),
        "current_project_source_binding_digest": current_source_binding_digest,
        "per_output_reference_bindings": physical_bindings,
        "per_output_reference_bindings_digest": _digest(physical_bindings),
        "locked_visual_asset_binding_digest": _digest({"bindings": bindings}),
        "physical_plan_digests": [item["plan_digest"] for item in physical_bindings],
        "terminal_role_execution_plan_digest": execution_plan_digest,
    }
    if any(not _clean(payload[key]) for key in ("provider_capability_id", "provider_name", "provider_model", "provider_operation", "provider_route_identity")):
        return None
    return {**payload, "closure_receipt_id": f"closure_{_digest(payload)[:24]}"}


def verified_provider_deliverability_closure_receipt(
    record: Any,
    *,
    uploaded_asset_lookup: Callable[[str], Any | None] | None = None,
    generated_output_lookup: Callable[[str], Any | None] | None = None,
    source_job_lookup: Callable[[str], Any | None] | None = None,
    project_goal_snapshot_lookup: Callable[[str, str], dict[str, Any] | None] | None = None,
    command_attempt_association_lookup: Callable[[str, str], dict[str, Any] | None] | None = None,
) -> dict[str, Any] | None:
    """Accept an exact stored receipt or synthesize complete legacy evidence read-only."""

    metadata = dict(getattr(getattr(record, "request", None), "metadata", {}) or {})
    rebuilt = build_provider_deliverability_closure_receipt(
        record,
        uploaded_asset_lookup=uploaded_asset_lookup,
        generated_output_lookup=generated_output_lookup,
        source_job_lookup=source_job_lookup,
        project_goal_snapshot_lookup=project_goal_snapshot_lookup,
        command_attempt_association_lookup=command_attempt_association_lookup,
    )
    stored = metadata.get("provider_deliverability_closure_receipt")
    if stored is not None:
        return dict(stored) if isinstance(stored, dict) and rebuilt is not None and stored == rebuilt else None
    return rebuilt


def safe_closure_operation(receipt: dict[str, Any]) -> dict[str, Any]:
    return {
        "state": "delivery_route_unavailable",
        "terminal": True,
        "pending": False,
        "closure_receipt_id": _clean(receipt.get("closure_receipt_id")),
        "next_actions": [{"id": "review_delivery_options"}],
    }
