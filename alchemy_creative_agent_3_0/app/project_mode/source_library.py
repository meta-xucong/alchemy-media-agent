"""Server-owned Doc270 read model for active project-upload originals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


DOC270_LIBRARY_SCHEMA = "doc270_project_source_library_v1"
DOC270_PUBLIC_LIBRARY_SCHEMA = "doc270_project_source_library_public_v1"
DOC270_PROFILE_SCHEMA = "doc270_source_evidence_profile_v1"
DOC270_ANALYSIS_RECEIPT_SCHEMA = "doc270_source_analysis_receipt_v1"
DOC270_SHADOW_REQUIREMENT_SCHEMA = "doc270_reference_requirement_v1"
DOC270_SHADOW_RECEIPT_SCHEMA = "doc270_reference_resolution_receipt_v1"
DOC270_SHADOW_RESOLVER = {
    "authority": "v3_doc270_shadow_matcher",
    "version": "doc270_shadow_matcher_v1",
}

# Phase 2 is deliberately a closed, server-side comparison vocabulary.  It
# proves the contract across unrelated source domains without importing an
# E-Commerce product taxonomy into General or Photography.
_DOC270_SHADOW_REQUIREMENTS: dict[str, tuple[str, str, str]] = {
    "object_front_presentation": ("object_front_presentation", "front", "object_or_product"),
    "object_rear_structure": ("object_back_or_structure", "rear", "object_or_product"),
    "object_detail": ("object_detail", "detail_or_macro", "object_or_product"),
    "person_environment_context": ("environment", "environment_wide", "person"),
    "brand_scene_material": ("logo_or_mark", "packaging", "brand_or_graphic"),
}
_DOC270_PRODUCTION_CAPABILITIES = {
    "requirement_issuer": {
        "authority": "v3_server_template_requirement_issuer",
        "schema_version": "doc270_requirement_issuer_v1",
        "version": "doc270_server_requirement_issuer_v1",
    },
    "image_evidence_analyzer": {
        "authority": "v3_server_image_evidence",
        "schema_version": "doc270_image_evidence_analyzer_v1",
        "version": "doc270_server_image_evidence_v1",
    },
    "template:general_template": {"shadow_enabled": True},
    "template:ecommerce_template": {"shadow_enabled": True},
}
_DOC270_SHADOW_MAXIMUM_SOURCES = 4
_DOC270_SUBJECT_KINDS = {"object_or_product", "person", "brand_or_graphic"}
_DOC270_VIEW_KINDS = {"front", "rear", "detail_or_macro", "environment_wide", "packaging"}
_DOC270_AFFORDANCES = {
    "object_front_presentation", "object_back_or_structure", "object_detail", "environment", "logo_or_mark"
}


def canonical_digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_project_source_library(
    *,
    project_id: str,
    references: list[Any],
    upload_lookup: Callable[[str], Any | None],
) -> dict[str, Any]:
    """Catalog active uploaded originals and bind verified bytes when usable.

    This intentionally has no generated-output, Visual Asset, continuation, or
    matcher fallback input.  Those channels retain their existing authorities.
    """

    entries: list[dict[str, Any]] = []
    for reference in references:
        source_type = str(getattr(getattr(reference, "source_type", None), "value", getattr(reference, "source_type", ""))).strip()
        status = str(getattr(getattr(reference, "status", None), "value", getattr(reference, "status", ""))).strip()
        asset_id = str(getattr(reference, "asset_ref_id", "") or "").strip()
        reference_id = str(getattr(reference, "reference_id", "") or "").strip()
        use_policy = str(
            getattr(getattr(reference, "use_policy", None), "value", getattr(reference, "use_policy", ""))
        ).strip()
        if source_type != "uploaded" or status != "active" or not asset_id or not reference_id:
            continue
        record = upload_lookup(asset_id)
        record_status = str(
            getattr(getattr(record, "status", None), "value", getattr(record, "status", ""))
        ).strip()
        role = str(getattr(getattr(record, "role", None), "value", getattr(record, "role", ""))).strip()
        record_metadata = dict(getattr(record, "metadata", {}) or {}) if record is not None else {}
        authorization = record_metadata.get("upload_authorization_receipt")
        reference_channel = (
            str(authorization.get("reference_channel") or "").strip()
            if isinstance(authorization, dict)
            else str(record_metadata.get("codex_native_reference_channel") or "").strip()
        )
        persisted_digest = str(getattr(record, "content_sha256", "") or "").strip().lower()
        path = Path(str(getattr(record, "file_path", "") or "")) if record is not None else None
        actual_digest = ""
        availability_state = "upload_missing"
        if record is not None and record_status != "ready":
            availability_state = "upload_not_ready"
        elif record is not None and (path is None or not path.is_file()):
            availability_state = "file_missing"
        elif record is not None:
            try:
                actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                availability_state = "file_unreadable"
            else:
                availability_state = (
                    "ready_verified" if persisted_digest and persisted_digest == actual_digest else "content_drift"
                )
                if availability_state == "ready_verified" and role not in {
                    "product_reference",
                    "subject_reference",
                    "general",
                    "unknown_reference",
                }:
                    availability_state = "role_or_channel_invalid"
        verified = availability_state == "ready_verified"
        automatic_use_eligible = verified and role in {
            "product_reference",
            "subject_reference",
            "general",
            "unknown_reference",
        }
        profile = None
        analysis_receipt = None
        if verified:
            profile = {
                "schema_version": DOC270_PROFILE_SCHEMA,
                "source_asset_id": asset_id,
                "content_sha256": actual_digest,
                # Phase 1 has no image-semantic analyzer yet.  It observes
                # verified bytes only and reserves semantic match authority.
                "evidence_state": "not_observed",
                "subject_kind": "unknown",
                "view_kind": "unknown",
                "affordances": [],
            }
            profile["profile_digest"] = canonical_digest(profile)
            analysis_receipt = {
                "schema_version": DOC270_ANALYSIS_RECEIPT_SCHEMA,
                "authority": "v3_project_source_library",
                "project_id": project_id,
                "reference_id": reference_id,
                "asset_id": asset_id,
                "source_type": source_type,
                "use_policy": use_policy,
                "role": role,
                "reference_channel": reference_channel,
                "content_sha256": actual_digest,
                "profile_digest": profile["profile_digest"],
            }
            analysis_receipt["receipt_digest"] = canonical_digest(analysis_receipt)
        entries.append(
            {
                "reference_id": reference_id,
                "asset_id": asset_id,
                "source_type": "uploaded",
                "use_policy": use_policy,
                "role": role,
                "reference_channel": reference_channel,
                "record_status": record_status,
                "persisted_content_sha256": persisted_digest,
                "content_sha256": actual_digest or None,
                "availability_state": availability_state,
                "automatic_use_eligible": automatic_use_eligible,
                "ecommerce_product_eligible": bool(
                    verified
                    and use_policy == "product"
                    and role == "product_reference"
                    and reference_channel == "product_truth"
                ),
                "profile": profile,
                "analysis_receipt": analysis_receipt,
            }
        )
    snapshot = {
        "schema_version": DOC270_LIBRARY_SCHEMA,
        "project_id": project_id,
        "entries": entries,
    }
    snapshot["snapshot_digest"] = canonical_digest(snapshot)
    return snapshot


def public_project_source_library(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return the browser-safe catalog view of a trusted internal snapshot.

    The complete snapshot is an internal Project Mode-to-Product API binding
    input.  Project reads need only association-scoped labels and availability;
    bytes, receipt digests, semantic observations, and storage facts remain
    server-side and are never reconstructed from this public projection.
    """

    entries: list[dict[str, Any]] = []
    for index, item in enumerate(snapshot.get("entries", []), start=1):
        if not isinstance(item, dict):
            continue
        association_reference_id = str(item.get("reference_id") or "").strip()
        availability_state = str(item.get("availability_state") or "").strip()
        if not association_reference_id or not availability_state:
            continue
        entries.append(
            {
                # This is the only opaque association token the existing
                # reference-removal route needs.  It is not an asset/output ID.
                "association_reference_id": association_reference_id,
                "label": f"项目原始素材 {index}",
                "availability_state": availability_state,
                "automatic_use_eligible": bool(item.get("automatic_use_eligible")),
                "ecommerce_product_eligible": bool(item.get("ecommerce_product_eligible")),
            }
        )
    return {
        "schema_version": DOC270_PUBLIC_LIBRARY_SCHEMA,
        "entries": entries,
    }


def _shadow_receipt(
    *,
    state: str,
    project_id: str = "",
    output_index: int = 0,
    source_library_snapshot_digest: str = "",
    requirement_digest: str = "",
    command_plan_binding_digest: str = "",
    output_identity: str = "",
    requirement_nonce: str = "",
    matched_references: list[dict[str, str]] | None = None,
    evidence_profile_digests: list[str] | None = None,
    rationale_codes: list[str] | None = None,
    ranking_tie_break: str | None = None,
) -> dict[str, Any]:
    """Build the Phase 2 ephemeral result without retaining any source state."""

    receipt: dict[str, Any] = {
        "schema_version": DOC270_SHADOW_RECEIPT_SCHEMA,
        "project_id": project_id,
        "output_index": output_index,
        "source_library_snapshot_digest": source_library_snapshot_digest,
        "source_resolver": dict(DOC270_SHADOW_RESOLVER),
        "requirement_digest": requirement_digest,
        "command_plan_binding_digest": command_plan_binding_digest,
        "output_identity": output_identity,
        "requirement_nonce": requirement_nonce,
        "state": state,
        "matched_references": matched_references or [],
        "evidence_profile_digests": evidence_profile_digests or [],
        "rationale_codes": rationale_codes or [],
        "shadow_only": True,
    }
    if ranking_tie_break:
        receipt["ranking_tie_break"] = ranking_tie_break
    receipt["receipt_digest"] = canonical_digest(receipt)
    return receipt


def _shadow_invalid(code: str) -> dict[str, Any]:
    # Deliberately do not reflect lookup identifiers or exception text.
    return _shadow_receipt(state="invalid", rationale_codes=[code])


def _mapping(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _same_digest_record(value: dict[str, Any], digest_field: str) -> bool:
    actual = str(value.get(digest_field) or "").strip().lower()
    if len(actual) != 64:
        return False
    candidate = {key: item for key, item in value.items() if key != digest_field}
    return actual == canonical_digest(candidate)


def _shadow_requirement_is_trusted(
    requirement: dict[str, Any],
    plan_binding: dict[str, Any],
    *,
    project_id: str,
    command_plan_binding: dict[str, Any],
    snapshot_digest: str,
) -> bool:
    if requirement.get("schema_version") != DOC270_SHADOW_REQUIREMENT_SCHEMA:
        return False
    if not _same_digest_record(requirement, "requirement_digest"):
        return False
    if requirement.get("project_id") != project_id:
        return False
    if requirement.get("command_plan_binding") != command_plan_binding:
        return False
    if requirement.get("source_library_snapshot_digest") != snapshot_digest:
        return False
    if requirement.get("kind") not in {*_DOC270_SHADOW_REQUIREMENTS, "no_reference"}:
        return False
    maximum_sources = requirement.get("maximum_sources")
    if not isinstance(maximum_sources, int) or isinstance(maximum_sources, bool):
        return False
    if not 1 <= maximum_sources <= _DOC270_SHADOW_MAXIMUM_SOURCES:
        return False
    required_plan_fields = (
        "project_id",
        "command_plan_binding",
        "output_index",
        "output_identity",
        "requirement_nonce",
        "requirement_digest",
        "source_library_snapshot_digest",
        "issuer",
    )
    return all(plan_binding.get(field) == requirement.get(field) for field in required_plan_fields)


def _shadow_command_binding_is_trusted(command_plan_binding: dict[str, Any], *, project_id: str) -> bool:
    allowed = {"schema_version", "authority", "command_id", "plan_id", "plan_version", "command_binding_digest"}
    if set(command_plan_binding) != allowed:
        return False
    if command_plan_binding.get("schema_version") != "doc270_shadow_command_handle_v1":
        return False
    if command_plan_binding.get("authority") != "v3_server_shadow_command_handle":
        return False
    if not isinstance(command_plan_binding.get("command_id"), str) or not command_plan_binding["command_id"].strip():
        return False
    if not isinstance(command_plan_binding.get("plan_id"), str) or not command_plan_binding["plan_id"].strip():
        return False
    if not isinstance(command_plan_binding.get("plan_version"), int) or isinstance(command_plan_binding["plan_version"], bool):
        return False
    return _same_digest_record(command_plan_binding, "command_binding_digest") and project_id in {
        command_plan_binding["command_id"].removeprefix("server-command-"),
        command_plan_binding["plan_id"].removeprefix("server-plan-"),
    }


def _shadow_evidence_is_valid(
    evidence: dict[str, Any],
    entry: dict[str, Any],
    *,
    project_id: str,
    analyzer_capability: dict[str, Any],
) -> bool:
    if not _same_digest_record(evidence, "profile_digest"):
        return False
    analyzer = evidence.get("analyzer")
    if not isinstance(analyzer, dict) or analyzer != analyzer_capability:
        return False
    if not isinstance(evidence.get("subject_kind"), str) or evidence["subject_kind"] not in _DOC270_SUBJECT_KINDS:
        return False
    if not isinstance(evidence.get("view_kind"), str) or evidence["view_kind"] not in _DOC270_VIEW_KINDS:
        return False
    affordances = evidence.get("affordances")
    if (
        not isinstance(affordances, list)
        or not affordances
        or any(not isinstance(item, str) or item not in _DOC270_AFFORDANCES for item in affordances)
        or len(affordances) != len(set(affordances))
    ):
        return False
    return (
        evidence.get("project_id") == project_id
        and evidence.get("reference_id") == entry.get("reference_id")
        and evidence.get("asset_id") == entry.get("asset_id")
        and evidence.get("content_sha256") == entry.get("content_sha256")
        and evidence.get("evidence_state") == "observed"
        and isinstance(evidence.get("affordances"), list)
    )


def resolve_doc270_shadow_reference_requirements(
    *,
    project_id: str,
    command_plan_binding: dict[str, Any],
    trusted_project_lookup: Callable[[str], Any | None],
    upload_lookup: Callable[[str], Any | None],
    trusted_requirement_lookup: Callable[[dict[str, Any]], Any | None],
    trusted_plan_binding_lookup: Callable[[dict[str, Any]], Any | None],
    evidence_lookup: Callable[[dict[str, Any]], Any | None],
    trusted_capability_lookup: Callable[[str], Any | None] | None = None,
) -> dict[str, Any]:
    """Resolve a server-private, non-persistent Doc270 Phase 2 shadow receipt.

    Callers supply only lookup capabilities and the server-issued command/plan
    handle.  The function intentionally accepts no library snapshot, browser
    requirement, persistence store, or write callback.
    """

    if not isinstance(command_plan_binding, dict):
        return _shadow_invalid("trusted_command_binding_invalid")
    try:
        project = trusted_project_lookup(project_id)
    except Exception:  # Trusted lookup failures are private invalid states.
        return _shadow_invalid("trusted_project_unavailable")
    if project is None:
        return _shadow_invalid("trusted_project_unavailable")
    durable_project_id = str(getattr(project, "project_id", "") or "").strip()
    if not durable_project_id or durable_project_id != project_id:
        return _shadow_invalid("trusted_project_invalid")
    if not _shadow_command_binding_is_trusted(command_plan_binding, project_id=project_id):
        return _shadow_invalid("trusted_command_binding_invalid")
    capability_lookup = trusted_capability_lookup or _DOC270_PRODUCTION_CAPABILITIES.get
    try:
        issuer_capability = _mapping(capability_lookup("requirement_issuer"))
        analyzer_capability = _mapping(capability_lookup("image_evidence_analyzer"))
    except Exception:
        return _shadow_invalid("trusted_capability_unavailable")
    if issuer_capability is None or analyzer_capability is None:
        return _shadow_invalid("trusted_capability_unavailable")
    try:
        requirement = _mapping(trusted_requirement_lookup(command_plan_binding))
        plan_binding = _mapping(trusted_plan_binding_lookup(command_plan_binding))
    except Exception:
        return _shadow_invalid("trusted_plan_unavailable")
    if requirement is None or plan_binding is None:
        return _shadow_invalid("trusted_plan_unavailable")

    try:
        snapshot = build_project_source_library(
            project_id=durable_project_id,
            references=list(getattr(project, "reference_assets", []) or []),
            upload_lookup=upload_lookup,
        )
    except Exception:
        return _shadow_invalid("trusted_source_library_unavailable")
    snapshot_digest = str(snapshot.get("snapshot_digest") or "")
    if requirement.get("issuer") != issuer_capability or not _shadow_requirement_is_trusted(
        requirement,
        plan_binding,
        project_id=durable_project_id,
        command_plan_binding=command_plan_binding,
        snapshot_digest=snapshot_digest,
    ):
        return _shadow_invalid("trusted_requirement_invalid")

    output_index = requirement.get("output_index")
    if not isinstance(output_index, int) or isinstance(output_index, bool) or output_index < 1:
        return _shadow_invalid("trusted_output_invalid")
    base = {
        "project_id": durable_project_id,
        "output_index": output_index,
        "source_library_snapshot_digest": snapshot_digest,
        "requirement_digest": str(requirement["requirement_digest"]),
        "command_plan_binding_digest": str(command_plan_binding["command_binding_digest"]),
        "output_identity": str(requirement["output_identity"]),
        "requirement_nonce": str(requirement["requirement_nonce"]),
    }
    template_capability = _mapping(capability_lookup(f"template:{requirement.get('template_id')}"))
    if not template_capability or template_capability.get("shadow_enabled") is not True:
        return _shadow_receipt(state="not_applicable", **base)
    if requirement["kind"] == "no_reference":
        return _shadow_receipt(state="not_applicable", **base)
    entries = snapshot.get("entries")
    if not isinstance(entries, list):
        return _shadow_invalid("trusted_source_library_invalid")
    reference_ids = [str(item.get("reference_id") or "") for item in entries if isinstance(item, dict)]
    if not reference_ids or len(reference_ids) != len(set(reference_ids)):
        return _shadow_invalid("trusted_source_library_invalid")
    expected_affordance, expected_view, expected_subject = _DOC270_SHADOW_REQUIREMENTS[requirement["kind"]]
    matches: list[dict[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            return _shadow_invalid("trusted_source_library_invalid")
        if not entry.get("automatic_use_eligible") or entry.get("availability_state") != "ready_verified":
            continue
        try:
            evidence = _mapping(evidence_lookup(entry))
        except Exception:
            return _shadow_invalid("trusted_evidence_unavailable")
        if evidence is None:
            continue
        if not _shadow_evidence_is_valid(
            evidence,
            entry,
            project_id=durable_project_id,
            analyzer_capability=analyzer_capability,
        ):
            return _shadow_invalid("trusted_evidence_invalid")
        if (
            expected_affordance not in evidence["affordances"]
            or evidence.get("view_kind") != expected_view
            or evidence.get("subject_kind") != expected_subject
        ):
            continue
        matches.append(
            {
                "reference_id": str(entry["reference_id"]),
                "asset_id": str(entry["asset_id"]),
                "content_sha256": str(entry["content_sha256"]),
                "profile_digest": str(evidence["profile_digest"]),
            }
        )
    if not matches:
        return _shadow_receipt(state="insufficient_evidence", **base)
    matches.sort(key=canonical_digest)
    maximum_sources = int(requirement["maximum_sources"])
    selected = matches[:maximum_sources]
    return _shadow_receipt(
        state="resolved",
        matched_references=selected,
        evidence_profile_digests=[item["profile_digest"] for item in selected],
        ranking_tie_break="canonical_evidence_binding_v1",
        **base,
    )
