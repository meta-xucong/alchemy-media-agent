"""Typed, server-owned E-Commerce authority for the Native planner.

The Native adapter is a planning host, not a second Product API.  It may
receive authority from its embedding host, but it must never reconstruct that
authority from public request inputs, prompts, or free-form metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
import hashlib
from pathlib import Path
import re
from typing import Any, Protocol

from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.physical_renderer_reference_plan import (
    DOC269_MAX_REFERENCE_IMAGES,
    NativeEcommerceBodyReferenceBinding,
    NativeEcommerceIdentityBinding,
    NativeEcommerceIdentityBindingEntry,
    PhysicalRendererReferencePlan,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.reference_projection import (
    PhysicalProductReferenceProjection,
    ProductTruthAdmission,
)
from alchemy_creative_agent_3_0.app.product_api.service import (
    ProductApiEcommerceAuthoritySnapshot,
)
from .contracts import NativeReferenceInput


NATIVE_ECOMMERCE_AUTHORITY_METADATA_KEYS = frozenset(
    {
        "professional_ecommerce_contract_authority",
        "professional_ecommerce_product_truth_admission",
        "professional_ecommerce_physical_product_projection",
        "professional_ecommerce_physical_product_projections",
        "physical_renderer_reference_plans",
    }
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


_LEGACY_TEST_AUTHORITY_CAPABILITY = object()


def is_explicit_test_only_legacy_resolver(
    resolver: Any,
    *,
    preflight: "NativeEcommerceAuthorityPreflight | None",
) -> bool:
    """Recognize the explicitly injected test-only compatibility adapter.

    A copied attribute or a module name is not an authority boundary.  The
    test adapter must receive the private capability through its preflight
    result; production readers never issue that capability.
    """

    return (
        getattr(resolver, "legacy_test_only_post_brain_resolution", False) is True
        and isinstance(preflight, NativeEcommerceAuthorityPreflight)
        and preflight.legacy_test_adapter_capability is _LEGACY_TEST_AUTHORITY_CAPABILITY
    )


@dataclass(frozen=True, slots=True)
class NativeEcommerceAuthorityPreflight:
    """Typed host proof that a frozen E-Commerce authority is available.

    The Native planner cannot ask the remote Brain to invent Product API
    authority.  The embedding host therefore proves authority availability
    before planning.  The same immutable typed records are reused after Brain
    returns only to bind the planned output positions; no authority is issued
    or resolved again.
    """

    schema_version: str
    project_id: str
    job_id: str
    requested_output_count: int
    authority_digest: str
    output_asset_ids: tuple[str, ...] = ()
    authorities: tuple["NativeEcommerceAuthority", ...] = ()
    legacy_test_adapter_capability: object | None = None

    def __post_init__(self) -> None:
        if (
            self.schema_version != "native_ecommerce_authority_preflight_v1"
            or not isinstance(self.project_id, str)
            or not self.project_id.strip()
            or not isinstance(self.job_id, str)
            or not self.job_id.strip()
            or not isinstance(self.requested_output_count, int)
            or isinstance(self.requested_output_count, bool)
            or not 1 <= self.requested_output_count <= 16
            or not _SHA256.fullmatch(self.authority_digest)
            or not isinstance(self.output_asset_ids, tuple)
            or any(not isinstance(asset_id, str) or not asset_id.strip() for asset_id in self.output_asset_ids)
            or len(self.output_asset_ids) not in {0, self.requested_output_count}
            or len(self.output_asset_ids) != len(set(self.output_asset_ids))
            or not isinstance(self.authorities, tuple)
            or any(not isinstance(item, NativeEcommerceAuthority) for item in self.authorities)
            or (
                self.legacy_test_adapter_capability is not None
                and self.legacy_test_adapter_capability is not _LEGACY_TEST_AUTHORITY_CAPABILITY
            )
        ):
            raise ValueError("native_ecommerce_authority_preflight_invalid")
        if self.authorities:
            if (
                len(self.authorities) != self.requested_output_count
                or tuple(item.asset_id for item in self.authorities) != self.output_asset_ids
                or tuple(item.output_index for item in self.authorities)
                != tuple(range(1, self.requested_output_count + 1))
                or any(
                    item.project_id != self.project_id or item.job_id != self.job_id
                    for item in self.authorities
                )
            ):
                raise ValueError("native_ecommerce_authority_preflight_map_invalid")

    def matches(self, *, project_id: str, job_id: str, requested_output_count: int) -> bool:
        return (
            self.project_id == project_id
            and self.job_id == job_id
            and self.requested_output_count == requested_output_count
        )


class NativeEcommerceAuthorityResolver(Protocol):
    """Explicit host interface for a complete pre-Brain authority map.

    Test-only legacy adapters may opt into the old callable resolution path by
    declaring ``legacy_test_only_post_brain_resolution = True`` and receiving
    the private capability in their preflight result.  Production resolvers do
    not have a post-Brain escape hatch.
    """

    def preflight(
        self,
        *,
        project_id: str,
        job_id: str,
        requested_output_count: int,
        server_owned_references: tuple[Any, ...] = (),
        server_owned_body_references: tuple[NativeReferenceInput, ...] = (),
    ) -> NativeEcommerceAuthorityPreflight | None: ...

    def __call__(self, **kwargs: Any) -> "NativeEcommerceAuthority | None": ...

def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class NativeEcommerceAuthority:
    """One validated Product API authority projection for one output.

    ``projections`` and ``physical_plans`` carry the complete frozen maps so
    every Provider request can be checked against the same deliverable set.
    They are typed records, never untrusted dictionaries.  The primary
    ``projection`` and ``physical_plan`` must be present in those maps.
    """

    project_id: str
    job_id: str
    asset_id: str
    output_index: int
    admission: ProductTruthAdmission
    projection: PhysicalProductReferenceProjection
    physical_plan: PhysicalRendererReferencePlan
    projections: tuple[PhysicalProductReferenceProjection, ...] = ()
    physical_plans: tuple[PhysicalRendererReferencePlan, ...] = ()
    native_identity_binding: NativeEcommerceIdentityBinding | None = None
    native_body_reference_bindings: tuple[NativeEcommerceBodyReferenceBinding, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.project_id, str)
            or not self.project_id.strip()
            or not isinstance(self.job_id, str)
            or not self.job_id.strip()
            or not isinstance(self.asset_id, str)
            or not self.asset_id.strip()
            or not isinstance(self.output_index, int)
            or isinstance(self.output_index, bool)
            or self.output_index <= 0
            or not isinstance(self.admission, ProductTruthAdmission)
            or not isinstance(self.projection, PhysicalProductReferenceProjection)
            or not isinstance(self.physical_plan, PhysicalRendererReferencePlan)
            or not isinstance(self.native_body_reference_bindings, tuple)
            or any(
                not isinstance(item, NativeEcommerceBodyReferenceBinding)
                for item in self.native_body_reference_bindings
            )
        ):
            raise ValueError("native_ecommerce_authority_shape_invalid")

        projections = self.projections or (self.projection,)
        physical_plans = self.physical_plans or (self.physical_plan,)
        if any(not isinstance(item, PhysicalProductReferenceProjection) for item in projections):
            raise ValueError("native_ecommerce_authority_projection_shape_invalid")
        if any(not isinstance(item, PhysicalRendererReferencePlan) for item in physical_plans):
            raise ValueError("native_ecommerce_authority_plan_shape_invalid")
        if not projections or not physical_plans:
            raise ValueError("native_ecommerce_authority_records_missing")

        projection_by_index = {item.output_index: item for item in projections}
        plan_by_index = {item.output_index: item for item in physical_plans}
        if len(projection_by_index) != len(projections) or len(plan_by_index) != len(physical_plans):
            raise ValueError("native_ecommerce_authority_duplicate_output")
        if set(projection_by_index) != set(plan_by_index):
            raise ValueError("native_ecommerce_authority_output_map_mismatch")
        expected_output_indexes = tuple(range(1, len(projections) + 1))
        if tuple(item.output_index for item in projections) != expected_output_indexes:
            raise ValueError("native_ecommerce_authority_projection_order_invalid")
        if tuple(item.output_index for item in physical_plans) != expected_output_indexes:
            raise ValueError("native_ecommerce_authority_plan_order_invalid")
        if self.output_index not in projection_by_index:
            raise ValueError("native_ecommerce_authority_primary_projection_missing")
        if self.output_index not in plan_by_index:
            raise ValueError("native_ecommerce_authority_primary_plan_missing")
        if (
            self.projection != projection_by_index[self.output_index]
            or self.physical_plan != plan_by_index[self.output_index]
        ):
            raise ValueError("native_ecommerce_authority_primary_record_mismatch")

        if self.admission.project_id != self.project_id or self.admission.job_id != self.job_id:
            raise ValueError("native_ecommerce_authority_admission_binding_invalid")
        for output_index, projection in projection_by_index.items():
            projection.validate_against(self.admission)
            if projection.job_id != self.job_id or projection.output_index != output_index:
                raise ValueError("native_ecommerce_authority_projection_binding_invalid")
            plan = plan_by_index[output_index]
            if (
                plan.job_id != self.job_id
                or plan.output_index != output_index
                or plan.projection_digest != projection.projection_digest
                or plan.maximum_reference_images != DOC269_MAX_REFERENCE_IMAGES
                or plan.reference_image_count > DOC269_MAX_REFERENCE_IMAGES
                or plan.reference_image_count > plan.maximum_reference_images
            ):
                raise ValueError("native_ecommerce_authority_plan_binding_invalid")
            for entry in plan.references:
                try:
                    path = Path(entry.file_path).resolve(strict=True)
                    if not path.is_file() or _file_sha256(path) != entry.content_sha256:
                        raise ValueError("native_ecommerce_authority_file_digest_invalid")
                except (OSError, RuntimeError, ValueError) as exc:
                    if str(exc) == "native_ecommerce_authority_file_digest_invalid":
                        raise
                    raise ValueError("native_ecommerce_authority_file_unreadable") from exc

        if self.native_identity_binding is not None:
            binding = self.native_identity_binding
            if (
                binding.project_id != self.project_id
                or binding.job_id != self.job_id
                or binding.asset_id != self.asset_id
                or binding.output_index != self.output_index
                or binding.plan_digest != self.physical_plan.plan_digest
                or binding.maximum_reference_images != self.physical_plan.maximum_reference_images
            ):
                raise ValueError("native_ecommerce_authority_identity_binding_invalid")
            identity_entries = tuple(
                entry for entry in self.physical_plan.references if entry.channel == "people_identity"
            )
            if len(binding.entries) != len(identity_entries) or not identity_entries:
                raise ValueError("native_ecommerce_authority_identity_binding_invalid")
            if any(
                bound.source_id != planned.source_id
                or bound.file_path != str(Path(planned.file_path).resolve())
                or bound.content_sha256 != planned.content_sha256
                or bound.role != planned.role
                or bound.channel != planned.channel
                or bound.source_type != planned.source_type
                for bound, planned in zip(binding.entries, identity_entries, strict=True)
            ):
                raise ValueError("native_ecommerce_authority_identity_binding_mismatch")

        seen_body_views: set[str] = set()
        for binding in self.native_body_reference_bindings:
            if (
                binding.project_id != self.project_id
                or binding.job_id != self.job_id
                or binding.asset_id != self.asset_id
                or binding.output_index != self.output_index
                or binding.plan_digest != self.physical_plan.plan_digest
                or binding.maximum_reference_images != self.physical_plan.maximum_reference_images
                or binding.body_view_kind in seen_body_views
            ):
                raise ValueError("native_ecommerce_authority_body_binding_invalid")
            try:
                path = Path(binding.file_path).resolve(strict=True)
                if not path.is_file() or _file_sha256(path) != binding.content_sha256:
                    raise ValueError("native_ecommerce_authority_body_binding_digest_invalid")
            except (OSError, RuntimeError) as exc:
                raise ValueError("native_ecommerce_authority_body_binding_unreadable") from exc
            seen_body_views.add(binding.body_view_kind)

        object.__setattr__(self, "projections", tuple(projections))
        object.__setattr__(self, "physical_plans", tuple(physical_plans))

    def provider_metadata(self) -> dict[str, Any]:
        """Return only the five existing Provider authority fields."""

        projections = {
            str(item.output_index): item.model_dump()
            for item in self.projections
        }
        physical_plans = {
            str(item.output_index): item.model_dump(mode="json")
            for item in self.physical_plans
        }
        return {
            "professional_ecommerce_contract_authority": "v3_product_api",
            "professional_ecommerce_product_truth_admission": self.admission.model_dump(),
            "professional_ecommerce_physical_product_projection": self.projection.model_dump(),
            "professional_ecommerce_physical_product_projections": projections,
            "physical_renderer_reference_plans": physical_plans,
        }

    def issue_native_identity_binding(
        self,
        server_owned_references: tuple[Any, ...],
    ) -> NativeEcommerceIdentityBinding:
        """Issue the Native-only People evidence carrier from host-owned refs."""

        plan_entries = {
            entry.source_id: entry
            for entry in self.physical_plan.references
            if entry.channel == "people_identity"
        }
        if not plan_entries or len(plan_entries) != len(
            [entry for entry in self.physical_plan.references if entry.channel == "people_identity"]
        ):
            raise ValueError("native_ecommerce_identity_binding_plan_invalid")

        entries: list[NativeEcommerceIdentityBindingEntry] = []
        seen: set[str] = set()
        for reference in server_owned_references:
            if not getattr(reference, "server_owned", False):
                raise ValueError("native_ecommerce_identity_binding_not_server_owned")
            source_id = str(getattr(reference, "asset_id", "") or "").strip()
            file_path = str(getattr(reference, "file_path", "") or "").strip()
            content_sha256 = str(getattr(reference, "source_sha256", "") or "").strip().lower()
            if not source_id or source_id in seen or not file_path or not content_sha256:
                raise ValueError("native_ecommerce_identity_binding_entry_invalid")
            plan_entry = plan_entries.get(source_id)
            if plan_entry is None:
                raise ValueError("native_ecommerce_identity_binding_plan_mismatch")
            path = Path(file_path).resolve(strict=True)
            if (
                str(path) != str(Path(plan_entry.file_path).resolve())
                or content_sha256 != plan_entry.content_sha256
                or _file_sha256(path) != content_sha256
                or plan_entry.role != "face_reference"
                or plan_entry.channel != "people_identity"
                or plan_entry.source_type != "visual_asset_library"
            ):
                raise ValueError("native_ecommerce_identity_binding_entry_mismatch")
            entries.append(
                NativeEcommerceIdentityBindingEntry(
                    source_id=source_id,
                    file_path=str(path),
                    content_sha256=content_sha256,
                )
            )
            seen.add(source_id)

        if seen != set(plan_entries):
            raise ValueError("native_ecommerce_identity_binding_identity_set_mismatch")
        return NativeEcommerceIdentityBinding(
            project_id=self.project_id,
            job_id=self.job_id,
            asset_id=self.asset_id,
            output_index=self.output_index,
            plan_digest=self.physical_plan.plan_digest,
            maximum_reference_images=self.physical_plan.maximum_reference_images,
            entries=tuple(entries),
        )

    def issue_native_body_reference_binding(
        self,
        server_owned_reference: NativeReferenceInput,
    ) -> NativeEcommerceBodyReferenceBinding:
        """Issue the Native-only auxiliary body input from host-owned evidence."""

        if (
            not isinstance(server_owned_reference, NativeReferenceInput)
            or not server_owned_reference.server_owned
            or server_owned_reference.channel
            != "body_proportion_reference"
        ):
            raise ValueError("native_ecommerce_body_reference_not_server_owned")
        source_id = server_owned_reference.asset_id.strip()
        file_path = server_owned_reference.file_path.strip()
        content_sha256 = server_owned_reference.source_sha256.strip().lower()
        body_view_kind = (server_owned_reference.body_view_kind or "").strip()
        if not source_id or not file_path or not content_sha256 or not body_view_kind:
            raise ValueError("native_ecommerce_body_reference_invalid")
        path = Path(file_path).resolve(strict=True)
        if _file_sha256(path) != content_sha256:
            raise ValueError("native_ecommerce_body_reference_digest_mismatch")
        return NativeEcommerceBodyReferenceBinding(
            project_id=self.project_id,
            job_id=self.job_id,
            asset_id=self.asset_id,
            output_index=self.output_index,
            plan_digest=self.physical_plan.plan_digest,
            maximum_reference_images=self.physical_plan.maximum_reference_images,
            source_id=source_id,
            file_path=str(path),
            content_sha256=content_sha256,
            body_view_kind=body_view_kind,
        )

    def with_native_identity_binding(
        self,
        server_owned_references: tuple[Any, ...],
    ) -> "NativeEcommerceAuthority":
        return replace(
            self,
            native_identity_binding=self.issue_native_identity_binding(server_owned_references),
        )

    def with_native_bindings(
        self,
        *,
        server_owned_references: tuple[Any, ...],
        server_owned_body_references: tuple[NativeReferenceInput, ...],
    ) -> "NativeEcommerceAuthority":
        """Freeze all server-owned evidence before the Brain is invoked."""

        return replace(
            self,
            native_identity_binding=self.issue_native_identity_binding(server_owned_references),
            native_body_reference_bindings=tuple(
                self.issue_native_body_reference_binding(reference)
                for reference in server_owned_body_references
            ),
        )

    def native_body_reference_binding_for_view(
        self,
        body_view_kind: str,
    ) -> NativeEcommerceBodyReferenceBinding | None:
        for binding in self.native_body_reference_bindings:
            if binding.body_view_kind == body_view_kind:
                return binding
        return None


class ProductApiEcommerceAuthorityReader:
    """Read authority from an existing, validated Product API job record."""

    requires_complete_preflight = True

    def __init__(self, product_api: Any) -> None:
        self._product_api = product_api

    def __call__(self, **kwargs: Any) -> NativeEcommerceAuthority | None:
        return self.resolve(**kwargs)

    @staticmethod
    def _authorities_from_snapshot(
        snapshot: ProductApiEcommerceAuthoritySnapshot,
        *,
        server_owned_references: tuple[Any, ...] = (),
        server_owned_body_references: tuple[NativeReferenceInput, ...] = (),
    ) -> tuple[NativeEcommerceAuthority, ...] | None:
        if not isinstance(snapshot, ProductApiEcommerceAuthoritySnapshot):
            return None
        authorities: list[NativeEcommerceAuthority] = []
        try:
            for output_index, (asset_id, projection, physical_plan) in enumerate(
                zip(
                    snapshot.asset_ids,
                    snapshot.projections,
                    snapshot.physical_plans,
                    strict=True,
                ),
                start=1,
            ):
                if (
                    projection.output_index != output_index
                    or physical_plan.output_index != output_index
                ):
                    return None
                authorities.append(
                    NativeEcommerceAuthority(
                        project_id=snapshot.project_id,
                        job_id=snapshot.job_id,
                        asset_id=asset_id,
                        output_index=output_index,
                        admission=snapshot.admission,
                        projection=projection,
                        physical_plan=physical_plan,
                        projections=snapshot.projections,
                        physical_plans=snapshot.physical_plans,
                    )
                )
        except (TypeError, ValueError):
            return None
        if len(authorities) != snapshot.requested_output_count:
            return None
        if server_owned_references or server_owned_body_references:
            try:
                authorities = [
                    authority.with_native_bindings(
                        server_owned_references=server_owned_references,
                        server_owned_body_references=server_owned_body_references,
                    )
                    for authority in authorities
                ]
            except (OSError, RuntimeError, ValueError):
                return None
        return tuple(authorities)

    def preflight(
        self,
        *,
        project_id: str,
        job_id: str,
        requested_output_count: int,
        server_owned_references: tuple[Any, ...] = (),
        server_owned_body_references: tuple[NativeReferenceInput, ...] = (),
    ) -> NativeEcommerceAuthorityPreflight | None:
        """Prove that the existing Product API authority can be consumed.

        This is deliberately read-only.  The Native relay has no permission
        to create a Product API job in order to satisfy its own preflight.
        """

        project_id = str(project_id or "").strip()
        job_id = str(job_id or "").strip()
        if (
            not project_id
            or not job_id
            or not isinstance(requested_output_count, int)
            or isinstance(requested_output_count, bool)
            or not 1 <= requested_output_count <= 16
        ):
            return None
        try:
            snapshot = self._product_api.get_ecommerce_authority_snapshot(job_id)
            if (
                not isinstance(snapshot, ProductApiEcommerceAuthoritySnapshot)
                or snapshot.project_id != project_id
                or snapshot.job_id != job_id
                or snapshot.requested_output_count != requested_output_count
            ):
                return None
            authorities = self._authorities_from_snapshot(
                snapshot,
                server_owned_references=server_owned_references,
                server_owned_body_references=server_owned_body_references,
            )
            if authorities is None:
                return None
            return NativeEcommerceAuthorityPreflight(
                schema_version="native_ecommerce_authority_preflight_v1",
                project_id=project_id,
                job_id=job_id,
                requested_output_count=requested_output_count,
                authority_digest=snapshot.authority_digest,
                output_asset_ids=snapshot.asset_ids,
                authorities=authorities,
            )
        except Exception:
            return None

    def resolve(
        self,
        *,
        project_id: str,
        job_id: str,
        asset_id: str,
        output_index: int,
        **_: Any,
    ) -> NativeEcommerceAuthority | None:
        project_id = str(project_id or "").strip()
        job_id = str(job_id or "").strip()
        asset_id = str(asset_id or "").strip()
        if (
            not project_id
            or not job_id
            or not asset_id
            or not isinstance(output_index, int)
            or isinstance(output_index, bool)
        ):
            return None
        try:
            snapshot = self._product_api.get_ecommerce_authority_snapshot(job_id)
            if (
                not isinstance(snapshot, ProductApiEcommerceAuthoritySnapshot)
                or snapshot.project_id != project_id
                or snapshot.job_id != job_id
                or not 1 <= output_index <= snapshot.requested_output_count
            ):
                return None
            authorities = self._authorities_from_snapshot(snapshot)
            if authorities is None:
                return None
            for authority in authorities:
                if authority.asset_id == asset_id and authority.output_index == output_index:
                    return authority
            return None
        except Exception:
            return None


def product_api_ecommerce_authority_resolver(product_api: Any) -> NativeEcommerceAuthorityResolver:
    """Build the explicit Native host resolver over Product API state."""

    return ProductApiEcommerceAuthorityReader(product_api)
