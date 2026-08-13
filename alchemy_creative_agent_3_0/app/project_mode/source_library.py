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
