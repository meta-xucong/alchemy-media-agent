"""Doc269's immutable, per-output renderer input authority for E-Commerce."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from .reference_projection import PhysicalProductReferenceProjection, ProductTruthAdmission


DOC269_PHYSICAL_PLAN_SCHEMA = "doc269_physical_renderer_reference_plan_v1"
# Doc269's professional renderer set is intentionally smaller than the
# underlying GPT Image 2 transport capacity.  The E-Commerce module owns this
# product-truth plan cap; the shared Provider may still accept the official
# sixteen-image edit envelope for other V3 requests.
DOC269_MAX_REFERENCE_IMAGES = 5
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: dict[str, Any]) -> str:
    payload = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _clean(value: Any) -> str:
    return str(value or "").strip()


class PhysicalRendererReferenceEntry(BaseModel):
    """One immutable physical file, in the precise order sent to the renderer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reference_id: str
    source_id: str
    role: Literal["product_reference", "face_reference", "selected_continuation_reference"]
    channel: Literal["product_truth", "people_identity", "generated_selected"]
    source_type: Literal["uploaded", "visual_asset_library", "generated_selected"]
    file_path: str
    content_sha256: str
    ordinal: int = Field(ge=1)
    selection_binding: "ContinuationSelectionBinding | None" = None

    def model_post_init(self, __context: Any) -> None:
        if not all(_clean(value) for value in (self.reference_id, self.source_id, self.file_path)):
            raise ValueError("doc269_reference_identity_required")
        if not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("doc269_reference_digest_invalid")
        expected = {
            "product_reference": ("product_truth", "uploaded"),
            "face_reference": ("people_identity", "visual_asset_library"),
            "selected_continuation_reference": ("generated_selected", "generated_selected"),
        }
        if expected[self.role] != (self.channel, self.source_type):
            raise ValueError("doc269_reference_role_channel_invalid")
        if self.channel == "generated_selected":
            if (
                self.selection_binding is None
                or self.selection_binding.output_id != self.reference_id
                or self.selection_binding.output_id != self.source_id
                or self.selection_binding.content_sha256 != self.content_sha256
            ):
                raise ValueError("doc269_continuation_binding_invalid")
        elif self.selection_binding is not None:
            raise ValueError("doc269_reference_selection_binding_invalid")


class ContinuationSelectionBinding(BaseModel):
    """Doc265's server-issued selected-output admission for one continuation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    selection_authority: Literal["doc265_project_mode"]
    project_id: str
    reference_id: str
    output_id: str
    source_job_id: str
    project_job_ids: tuple[str, ...]
    content_sha256: str

    def model_post_init(self, __context: Any) -> None:
        if not all(
            _clean(value)
            for value in (self.project_id, self.reference_id, self.output_id, self.source_job_id)
        ) or (
            not self.project_job_ids
            or self.source_job_id not in self.project_job_ids
            or len(self.project_job_ids) != len(set(self.project_job_ids))
            or any(not _clean(job_id) for job_id in self.project_job_ids)
            or not _SHA256.fullmatch(self.content_sha256)
        ):
            raise ValueError("doc269_continuation_binding_invalid")


class PhysicalRendererReferencePlan(BaseModel):
    """The server-issued final physical input plan for one E-Commerce output."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[DOC269_PHYSICAL_PLAN_SCHEMA] = DOC269_PHYSICAL_PLAN_SCHEMA
    job_id: str
    output_index: int = Field(ge=1)
    projection_digest: str
    maximum_reference_images: int = Field(ge=1)
    references: tuple[PhysicalRendererReferenceEntry, ...]
    reference_image_asset_ids: tuple[str, ...]
    reference_image_count: int = Field(ge=1)
    plan_digest: str

    def model_post_init(self, __context: Any) -> None:
        if not _clean(self.job_id) or not _SHA256.fullmatch(self.projection_digest):
            raise ValueError("doc269_plan_binding_invalid")
        if not _SHA256.fullmatch(self.plan_digest):
            raise ValueError("doc269_plan_digest_invalid")
        if self.reference_image_count != len(self.references):
            raise ValueError("doc269_plan_count_invalid")
        ids = tuple(item.reference_id for item in self.references)
        source_ids = tuple(item.source_id for item in self.references)
        if (
            self.reference_image_asset_ids != ids
            or len(ids) != len(set(ids))
            or len(source_ids) != len(set(source_ids))
        ):
            raise ValueError("doc269_plan_ids_invalid")
        content_groups: dict[str, list[PhysicalRendererReferenceEntry]] = {}
        for item in self.references:
            content_groups.setdefault(item.content_sha256, []).append(item)
        if any(
            len(entries) > 1
            and not all(
                item.role == "face_reference"
                and item.channel == "people_identity"
                and item.source_type == "visual_asset_library"
                for item in entries
            )
            for entries in content_groups.values()
        ):
            raise ValueError("doc269_plan_content_duplicate_invalid")
        if self.reference_image_count > self.maximum_reference_images:
            raise ValueError("doc269_plan_capacity_invalid")
        if tuple(item.ordinal for item in self.references) != tuple(range(1, len(self.references) + 1)):
            raise ValueError("doc269_plan_order_invalid")
        if self._canonical_payload() != self.plan_digest:
            raise ValueError("doc269_plan_digest_mismatch")

    def _canonical_payload(self) -> str:
        return _digest(
            {
                "schema_version": self.schema_version,
                "job_id": self.job_id,
                "output_index": self.output_index,
                "projection_digest": self.projection_digest,
                "maximum_reference_images": self.maximum_reference_images,
                "references": [item.model_dump(mode="json") for item in self.references],
                "reference_image_asset_ids": list(self.reference_image_asset_ids),
                "reference_image_count": self.reference_image_count,
            }
        )

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        return super().model_dump(**kwargs)


class NativeEcommerceIdentityBindingEntry(BaseModel):
    """One server-owned People evidence item issued to the Native host."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str
    file_path: str
    content_sha256: str
    role: Literal["face_reference"] = "face_reference"
    channel: Literal["people_identity"] = "people_identity"
    source_type: Literal["visual_asset_library"] = "visual_asset_library"

    def model_post_init(self, __context: Any) -> None:
        if not _clean(self.source_id) or not _clean(self.file_path) or not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("native_ecommerce_identity_binding_entry_invalid")


class NativeEcommerceIdentityBinding(BaseModel):
    """Internal, typed Native authority carrier for a single output."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["native_ecommerce_identity_binding_v1"] = (
        "native_ecommerce_identity_binding_v1"
    )
    authority: Literal["native_server_owned_people_binding"] = (
        "native_server_owned_people_binding"
    )
    project_id: str
    job_id: str
    asset_id: str
    output_index: int = Field(ge=1)
    plan_digest: str
    maximum_reference_images: int = Field(ge=1)
    entries: tuple[NativeEcommerceIdentityBindingEntry, ...]

    def model_post_init(self, __context: Any) -> None:
        if (
            not _clean(self.project_id)
            or not _clean(self.job_id)
            or not _clean(self.asset_id)
            or not _SHA256.fullmatch(self.plan_digest)
            or not self.entries
        ):
            raise ValueError("native_ecommerce_identity_binding_invalid")
        source_ids = tuple(item.source_id for item in self.entries)
        paths = tuple(item.file_path for item in self.entries)
        if len(source_ids) != len(set(source_ids)) or len(paths) != len(set(paths)):
            raise ValueError("native_ecommerce_identity_binding_duplicate")
        if len(self.entries) > self.maximum_reference_images:
            raise ValueError("native_ecommerce_identity_binding_capacity_invalid")


class NativeEcommerceBodyReferenceBinding(BaseModel):
    """Internal server-owned Body Silhouette input for Native E-Commerce.

    Body evidence is selected by the Professional binding resolver rather than
    by Product API's product/identity plan.  Keeping that auxiliary input in a
    separate typed carrier prevents the Native adapter from smuggling it
    through mutable public metadata while leaving the Doc269 plan authoritative
    for product truth and identity evidence.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: Literal["native_ecommerce_body_reference_binding_v1"] = (
        "native_ecommerce_body_reference_binding_v1"
    )
    authority: Literal["native_server_owned_body_binding"] = (
        "native_server_owned_body_binding"
    )
    project_id: str
    job_id: str
    asset_id: str
    output_index: int = Field(ge=1)
    plan_digest: str
    maximum_reference_images: int = Field(ge=1)
    source_id: str
    file_path: str
    content_sha256: str
    role: Literal["body_proportion_reference"] = "body_proportion_reference"
    channel: Literal["body_proportion_reference"] = "body_proportion_reference"
    source_type: Literal["visual_asset_library"] = "visual_asset_library"
    body_view_kind: Literal["front_full", "side_full", "rear_full"]

    def model_post_init(self, __context: Any) -> None:
        if (
            not all(
                _clean(value)
                for value in (
                    self.project_id,
                    self.job_id,
                    self.asset_id,
                    self.source_id,
                    self.file_path,
                )
            )
            or not _SHA256.fullmatch(self.plan_digest)
            or not _SHA256.fullmatch(self.content_sha256)
            or self.maximum_reference_images < 1
        ):
            raise ValueError("native_ecommerce_body_reference_binding_invalid")


def _as_mapping(value: Any) -> dict[str, Any]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return dict(value) if isinstance(value, dict) else {}


def _source_id(value: dict[str, Any]) -> str:
    return _clean(value.get("output_id") or value.get("asset_id") or value.get("source_id"))


def _file_entry(
    value: dict[str, Any],
    *,
    role: Literal["product_reference", "face_reference", "selected_continuation_reference"],
    channel: Literal["product_truth", "people_identity", "generated_selected"],
    source_type: Literal["uploaded", "visual_asset_library", "generated_selected"],
    ordinal: int,
    selection_binding: ContinuationSelectionBinding | None = None,
) -> PhysicalRendererReferenceEntry:
    source_id = _source_id(value)
    try:
        path = Path(_clean(value.get("file_path"))).resolve(strict=True)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ValueError("doc269_reference_file_unreadable") from exc
    if not path.is_file():
        raise ValueError("doc269_reference_file_unreadable")
    try:
        content_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError("doc269_reference_file_unreadable") from exc
    return PhysicalRendererReferenceEntry(
        reference_id=source_id,
        source_id=source_id,
        role=role,
        channel=channel,
        source_type=source_type,
        file_path=str(path),
        content_sha256=content_sha256,
        ordinal=ordinal,
        selection_binding=selection_binding,
    )


def build_physical_renderer_reference_plan(
    *,
    admission: ProductTruthAdmission,
    projection: PhysicalProductReferenceProjection,
    uploaded_assets: list[Any],
    locked_identity_references: list[Any],
    selected_continuation_references: list[Any],
    maximum_reference_images: int,
) -> PhysicalRendererReferencePlan:
    """Freeze the only physical provider inputs allowed for one output."""

    projection.validate_against(admission)
    if projection.job_id != admission.job_id:
        raise ValueError("doc269_plan_job_binding_invalid")
    products = {_source_id(_as_mapping(item)): _as_mapping(item) for item in uploaded_assets}
    faces = {_source_id(_as_mapping(item)): _as_mapping(item) for item in locked_identity_references}
    continuation: dict[str, tuple[dict[str, Any], ContinuationSelectionBinding]] = {}
    for item in selected_continuation_references:
        source = _as_mapping(item)
        if str(source.get("source_type") or "").strip() != "generated_selected":
            continue
        binding = ContinuationSelectionBinding.model_validate(source.get("selection_binding"))
        source_id = _source_id(source)
        if source_id != binding.output_id:
            raise ValueError("doc269_continuation_binding_invalid")
        continuation[source_id] = (source, binding)
    entries: list[PhysicalRendererReferenceEntry] = []
    for source_id in projection.selected_product_asset_ids:
        source = products.get(source_id)
        if not source or str(source.get("role") or "").strip() != "product_reference":
            raise ValueError("doc269_product_projection_source_invalid")
        entry = _file_entry(source, role="product_reference", channel="product_truth", source_type="uploaded", ordinal=len(entries) + 1)
        admitted_source = next((item for item in admission.sources if item.asset_id == source_id), None)
        if admitted_source is None or entry.content_sha256 != admitted_source.content_sha256:
            raise ValueError("doc269_product_projection_digest_mismatch")
        entries.append(entry)
    for source_id, source in faces.items():
        if str(source.get("role") or "").strip() != "face_reference":
            raise ValueError("doc269_locked_identity_source_invalid")
        entries.append(_file_entry(source, role="face_reference", channel="people_identity", source_type="visual_asset_library", ordinal=len(entries) + 1))
    for source_id, (source, binding) in continuation.items():
        entry = _file_entry(
            source,
            role="selected_continuation_reference",
            channel="generated_selected",
            source_type="generated_selected",
            ordinal=len(entries) + 1,
            selection_binding=binding,
        )
        if entry.content_sha256 != binding.content_sha256:
            raise ValueError("doc269_continuation_digest_mismatch")
        entries.append(entry)
    source_ids = tuple(item.reference_id for item in entries)
    if not source_ids or len(source_ids) != len(set(source_ids)):
        raise ValueError("doc269_reference_duplicate")
    payload = {
        "schema_version": DOC269_PHYSICAL_PLAN_SCHEMA,
        "job_id": admission.job_id,
        "output_index": projection.output_index,
        "projection_digest": projection.projection_digest,
        "maximum_reference_images": maximum_reference_images,
        "references": [item.model_dump(mode="json") for item in entries],
        "reference_image_asset_ids": list(source_ids),
        "reference_image_count": len(entries),
    }
    return PhysicalRendererReferencePlan(
        **payload,
        plan_digest=_digest(payload),
    )
