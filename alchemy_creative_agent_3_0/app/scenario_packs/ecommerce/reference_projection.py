"""Server-owned E-Commerce product truth admission and input projection."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Any


DOC263_ADMISSION_SCHEMA = "doc263_product_truth_admission_v1"
DOC263_PROJECTION_SCHEMA = "doc263_physical_product_reference_projection_v1"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _upload_receipt_digest(
    *,
    asset_id: str,
    content_sha256: str,
    role: str,
    product_truth_channel: str,
    consent_reference: str,
    rights_reference: str,
) -> str:
    payload = "|".join(
        (
            "v3_upload_authorization_receipt_v1",
            asset_id,
            content_sha256,
            role,
            product_truth_channel,
            consent_reference,
            rights_reference,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProductTruthSource:
    asset_id: str
    content_sha256: str
    consent_reference: str
    rights_reference: str
    receipt_digest: str
    role: str
    product_truth_channel: str
    readiness: str
    file_integrity: str
    provenance: str

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str)
            for value in (
                self.asset_id,
                self.content_sha256,
                self.consent_reference,
                self.rights_reference,
                self.receipt_digest,
                self.role,
                self.product_truth_channel,
                self.readiness,
                self.file_integrity,
                self.provenance,
            )
        ):
            raise ValueError("doc263_product_truth_source_shape_invalid")
        if (
            not _clean(self.asset_id)
            or not _clean(self.content_sha256)
            or not _clean(self.provenance)
        ):
            raise ValueError("doc263_product_truth_source_identity_required")
        if not _SHA256_PATTERN.fullmatch(self.content_sha256):
            raise ValueError("doc263_product_truth_source_hash_invalid")
        if not _clean(self.consent_reference) or not _clean(self.rights_reference):
            raise ValueError("doc263_product_truth_source_receipts_required")
        if not _clean(self.receipt_digest):
            raise ValueError("doc263_product_truth_source_receipt_digest_required")
        if self.role != "product_reference" or self.product_truth_channel != "product_truth":
            raise ValueError("doc263_product_truth_source_role_invalid")
        if self.readiness != "ready" or self.file_integrity != "sha256_verified":
            raise ValueError("doc263_product_truth_source_not_ready")
        if self.receipt_digest != _upload_receipt_digest(
            asset_id=self.asset_id,
            content_sha256=self.content_sha256.lower(),
            role=self.role,
            product_truth_channel=self.product_truth_channel,
            consent_reference=self.consent_reference,
            rights_reference=self.rights_reference,
        ):
            raise ValueError("doc263_product_truth_source_receipt_digest_mismatch")


@dataclass(frozen=True, slots=True)
class ProductTruthAdmission:
    project_id: str
    job_id: str
    canonical_asset_ids: tuple[str, ...]
    sources: tuple[ProductTruthSource, ...]
    source_binding_digest: str
    product_truth_plan_digest: str
    schema_version: str = DOC263_ADMISSION_SCHEMA

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str)
            for value in (
                self.schema_version,
                self.project_id,
                self.job_id,
                self.source_binding_digest,
                self.product_truth_plan_digest,
            )
        ):
            raise ValueError("doc263_product_truth_admission_shape_invalid")
        if self.schema_version != DOC263_ADMISSION_SCHEMA:
            raise ValueError("doc263_product_truth_admission_schema_invalid")
        if not _clean(self.project_id) or not _clean(self.job_id):
            raise ValueError("doc263_product_truth_admission_binding_required")
        if not self.canonical_asset_ids or len(self.canonical_asset_ids) != len(set(self.canonical_asset_ids)):
            raise ValueError("doc263_product_truth_admission_assets_invalid")
        if len(self.sources) != len(self.canonical_asset_ids):
            raise ValueError("doc263_product_truth_admission_sources_invalid")
        if tuple(item.asset_id for item in self.sources) != self.canonical_asset_ids:
            raise ValueError("doc263_product_truth_admission_source_invalid")
        if not _clean(self.source_binding_digest) or not _clean(self.product_truth_plan_digest):
            raise ValueError("doc263_product_truth_admission_digest_required")
        if not (
            _SHA256_PATTERN.fullmatch(self.source_binding_digest)
            and _SHA256_PATTERN.fullmatch(self.product_truth_plan_digest)
        ):
            raise ValueError("doc263_product_truth_admission_digest_invalid")
        if self.source_binding_digest != _admission_digest(
            project_id=self.project_id,
            job_id=self.job_id,
            sources=self.sources,
        ):
            raise ValueError("doc263_product_truth_admission_digest_mismatch")

    @classmethod
    def from_mapping(cls, value: Any) -> "ProductTruthAdmission":
        if not isinstance(value, dict):
            raise ValueError("doc263_product_truth_admission_missing")
        expected = {
            "schema_version",
            "project_id",
            "job_id",
            "canonical_asset_ids",
            "sources",
            "source_binding_digest",
            "product_truth_plan_digest",
        }
        if set(value) != expected:
            raise ValueError("doc263_product_truth_admission_shape_invalid")
        if any(
            not isinstance(value[key], str)
            for key in (
                "schema_version",
                "project_id",
                "job_id",
                "source_binding_digest",
                "product_truth_plan_digest",
            )
        ):
            raise ValueError("doc263_product_truth_admission_shape_invalid")
        if str(value.get("schema_version") or "") != DOC263_ADMISSION_SCHEMA:
            raise ValueError("doc263_product_truth_admission_schema_invalid")
        raw_ids = value["canonical_asset_ids"]
        raw_sources = value["sources"]
        if not isinstance(raw_ids, list) or not isinstance(raw_sources, list):
            raise ValueError("doc263_product_truth_admission_shape_invalid")
        if any(not isinstance(item, str) for item in raw_ids):
            raise ValueError("doc263_product_truth_admission_asset_shape_invalid")
        source_keys = {
            "asset_id",
            "content_sha256",
            "consent_reference",
            "rights_reference",
            "receipt_digest",
            "role",
            "product_truth_channel",
            "readiness",
            "file_integrity",
            "provenance",
        }
        sources = []
        for item in raw_sources:
            if not isinstance(item, dict) or set(item) != source_keys:
                raise ValueError("doc263_product_truth_admission_source_shape_invalid")
            if any(not isinstance(item[key], str) for key in source_keys):
                raise ValueError("doc263_product_truth_admission_source_shape_invalid")
            sources.append(ProductTruthSource(**item))
        return cls(
            schema_version=value["schema_version"],
            project_id=value["project_id"],
            job_id=value["job_id"],
            canonical_asset_ids=tuple(raw_ids),
            sources=tuple(sources),
            source_binding_digest=value["source_binding_digest"],
            product_truth_plan_digest=value["product_truth_plan_digest"],
        )

    def model_dump(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "job_id": self.job_id,
            "canonical_asset_ids": list(self.canonical_asset_ids),
            "sources": [asdict(item) for item in self.sources],
            "source_binding_digest": self.source_binding_digest,
            "product_truth_plan_digest": self.product_truth_plan_digest,
        }


@dataclass(frozen=True, slots=True)
class PhysicalProductReferenceProjection:
    job_id: str
    output_index: int
    admission_binding_digest: str
    selected_product_asset_ids: tuple[str, ...]
    selection_source: str
    selection_role: str
    cap_reservation: int
    projection_digest: str
    projection_state: str = "ready"
    historical_lineage_id: str | None = None
    schema_version: str = DOC263_PROJECTION_SCHEMA

    def __post_init__(self) -> None:
        if (
            not isinstance(self.schema_version, str)
            or not isinstance(self.job_id, str)
            or not isinstance(self.output_index, int)
            or isinstance(self.output_index, bool)
            or not isinstance(self.admission_binding_digest, str)
            or not isinstance(self.selection_source, str)
            or not isinstance(self.selection_role, str)
            or not isinstance(self.cap_reservation, int)
            or isinstance(self.cap_reservation, bool)
            or not isinstance(self.projection_digest, str)
            or (
                self.historical_lineage_id is not None
                and not isinstance(self.historical_lineage_id, str)
            )
            or any(not isinstance(item, str) for item in self.selected_product_asset_ids)
        ):
            raise ValueError("doc263_product_projection_shape_invalid")
        if self.schema_version != DOC263_PROJECTION_SCHEMA:
            raise ValueError("doc263_product_projection_schema_invalid")
        if not _clean(self.job_id) or self.output_index <= 0:
            raise ValueError("doc263_product_projection_binding_required")
        if not self.admission_binding_digest or not self.selected_product_asset_ids:
            raise ValueError("doc263_product_projection_selection_required")
        if not _SHA256_PATTERN.fullmatch(self.admission_binding_digest):
            raise ValueError("doc263_product_projection_admission_digest_invalid")
        if (
            len(self.selected_product_asset_ids) > 2
            or len(self.selected_product_asset_ids) != len(set(self.selected_product_asset_ids))
        ):
            raise ValueError("doc263_product_projection_selection_invalid")
        if not _clean(self.selection_source) or not _clean(self.selection_role):
            raise ValueError("doc263_product_projection_selection_metadata_required")
        if self.cap_reservation not in {1, 2} or self.cap_reservation < len(self.selected_product_asset_ids):
            raise ValueError("doc263_product_projection_cap_reservation_invalid")
        if not _clean(self.projection_digest) or not _SHA256_PATTERN.fullmatch(self.projection_digest):
            raise ValueError("doc263_product_projection_digest_required")
        if self.projection_state not in {"ready", "legacy_drift_recovery"}:
            raise ValueError("doc263_product_projection_state_invalid")
        if self.projection_state == "legacy_drift_recovery" and not _clean(self.historical_lineage_id):
            raise ValueError("doc263_product_projection_lineage_required")
        if self.projection_digest != _projection_digest(
            job_id=self.job_id,
            output_index=self.output_index,
            admission_binding_digest=self.admission_binding_digest,
            selected_product_asset_ids=self.selected_product_asset_ids,
            selection_source=self.selection_source,
            selection_role=self.selection_role,
            cap_reservation=self.cap_reservation,
            projection_state=self.projection_state,
            historical_lineage_id=self.historical_lineage_id,
        ):
            raise ValueError("doc263_product_projection_digest_mismatch")

    @classmethod
    def from_mapping(cls, value: Any) -> "PhysicalProductReferenceProjection":
        if not isinstance(value, dict):
            raise ValueError("doc263_product_projection_missing")
        expected = {
            "schema_version",
            "job_id",
            "output_index",
            "admission_binding_digest",
            "selected_product_asset_ids",
            "selection_source",
            "selection_role",
            "cap_reservation",
            "projection_digest",
            "projection_state",
            "historical_lineage_id",
        }
        if set(value) != expected:
            raise ValueError("doc263_product_projection_shape_invalid")
        if str(value.get("schema_version") or "") != DOC263_PROJECTION_SCHEMA:
            raise ValueError("doc263_product_projection_schema_invalid")
        selected = value["selected_product_asset_ids"]
        if (
            not isinstance(value["schema_version"], str)
            or not isinstance(value["job_id"], str)
            or not isinstance(value["output_index"], int)
            or isinstance(value["output_index"], bool)
            or not isinstance(value["admission_binding_digest"], str)
            or not isinstance(selected, list)
            or any(not isinstance(item, str) for item in selected)
            or not isinstance(value["selection_source"], str)
            or not isinstance(value["selection_role"], str)
            or not isinstance(value["cap_reservation"], int)
            or isinstance(value["cap_reservation"], bool)
            or not isinstance(value["projection_digest"], str)
            or not isinstance(value["projection_state"], str)
            or (
                value["historical_lineage_id"] is not None
                and not isinstance(value["historical_lineage_id"], str)
            )
        ):
            raise ValueError("doc263_product_projection_shape_invalid")
        return cls(
            schema_version=value["schema_version"],
            job_id=value["job_id"],
            output_index=value["output_index"],
            admission_binding_digest=value["admission_binding_digest"],
            selected_product_asset_ids=tuple(selected),
            selection_source=value["selection_source"],
            selection_role=value["selection_role"],
            cap_reservation=value["cap_reservation"],
            projection_digest=value["projection_digest"],
            projection_state=value["projection_state"],
            historical_lineage_id=(
                value["historical_lineage_id"]
                if value["historical_lineage_id"] is not None
                else None
            ),
        )

    def validate_against(self, admission: ProductTruthAdmission) -> None:
        if self.admission_binding_digest != admission.source_binding_digest:
            raise ValueError("doc263_product_projection_admission_binding_mismatch")
        if any(asset_id not in admission.canonical_asset_ids for asset_id in self.selected_product_asset_ids):
            raise ValueError("doc263_product_projection_selection_not_admitted")

    def model_dump(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "output_index": self.output_index,
            "admission_binding_digest": self.admission_binding_digest,
            "selected_product_asset_ids": list(self.selected_product_asset_ids),
            "selection_source": self.selection_source,
            "selection_role": self.selection_role,
            "cap_reservation": self.cap_reservation,
            "projection_digest": self.projection_digest,
            "projection_state": self.projection_state,
            "historical_lineage_id": self.historical_lineage_id,
        }


def build_product_truth_admission(
    *,
    project_id: str,
    job_id: str,
    sources: list[ProductTruthSource],
    product_truth_plan_digest: str,
) -> ProductTruthAdmission:
    canonical_asset_ids = tuple(item.asset_id for item in sources)
    binding_payload = {
        "schema_version": DOC263_ADMISSION_SCHEMA,
        "project_id": project_id,
        "job_id": job_id,
        "sources": [asdict(item) for item in sources],
    }
    return ProductTruthAdmission(
        project_id=project_id,
        job_id=job_id,
        canonical_asset_ids=canonical_asset_ids,
        sources=tuple(sources),
        source_binding_digest=_digest(binding_payload),
        product_truth_plan_digest=product_truth_plan_digest,
    )


def _admission_digest(
    *,
    project_id: str,
    job_id: str,
    sources: tuple[ProductTruthSource, ...],
) -> str:
    return _digest(
        {
            "schema_version": DOC263_ADMISSION_SCHEMA,
            "project_id": project_id,
            "job_id": job_id,
            "sources": [asdict(item) for item in sources],
        }
    )


def _projection_digest(
    *,
    job_id: str,
    output_index: int,
    admission_binding_digest: str,
    selected_product_asset_ids: tuple[str, ...],
    selection_source: str,
    selection_role: str,
    cap_reservation: int,
    projection_state: str,
    historical_lineage_id: str | None,
) -> str:
    return _digest(
        {
            "schema_version": DOC263_PROJECTION_SCHEMA,
            "job_id": job_id,
            "output_index": output_index,
            "admission_binding_digest": admission_binding_digest,
            "selected_product_asset_ids": list(selected_product_asset_ids),
            "selection_source": selection_source,
            "selection_role": selection_role,
            "cap_reservation": cap_reservation,
            "projection_state": projection_state,
            "historical_lineage_id": historical_lineage_id,
        }
    )


def build_physical_product_projection(
    *,
    job_id: str,
    output_index: int,
    admission: ProductTruthAdmission,
    selected_product_asset_ids: list[str],
    selection_source: str,
    selection_role: str,
    cap_reservation: int,
    projection_state: str = "ready",
    historical_lineage_id: str | None = None,
) -> PhysicalProductReferenceProjection:
    selected = tuple(selected_product_asset_ids)
    return PhysicalProductReferenceProjection(
        job_id=job_id,
        output_index=output_index,
        admission_binding_digest=admission.source_binding_digest,
        selected_product_asset_ids=selected,
        selection_source=selection_source,
        selection_role=selection_role,
        cap_reservation=cap_reservation,
        projection_digest=_projection_digest(
            job_id=job_id,
            output_index=output_index,
            admission_binding_digest=admission.source_binding_digest,
            selected_product_asset_ids=selected,
            selection_source=selection_source,
            selection_role=selection_role,
            cap_reservation=cap_reservation,
            projection_state=projection_state,
            historical_lineage_id=historical_lineage_id,
        ),
        projection_state=projection_state,
        historical_lineage_id=historical_lineage_id,
    )
