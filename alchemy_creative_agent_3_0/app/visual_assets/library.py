"""Doc173 library-first Visual Asset contracts and project binding service.

This module is intentionally small and framework-neutral.  It separates
reusable asset ownership from project usage without creating a second image,
Brain, Provider, review, retry, or byte-storage system.  The first released
asset type is a reviewed People Asset / Face Identity version; future asset
types are represented only as rejected request values until their own modules
and evidence contracts exist.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .contracts import FACE_IDENTITY_CHANNELS


VisualAssetType = Literal["people", "product", "scene", "brand"]
VisualAssetStatus = Literal[
    "draft",
    "preparing",
    "review",
    "active",
    "superseded",
    "archived",
    "blocked",
]
VisualAssetVersionStatus = Literal["draft", "preparing", "review", "active", "failed", "superseded"]
ProjectBindingStatus = Literal["active", "removed", "superseded_for_future_jobs", "blocked"]
BindingSetState = Literal["valid", "empty", "blocked"]

_RELEASED_ASSET_TYPES = frozenset({"people"})
_PEOPLE_OWNED_CHANNELS = ("face_geometry", "face_feature_relationships", "same_person_continuity")


class _StrictLibraryModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


class LibraryRootSourceProvenance(_StrictLibraryModel):
    """Safe pointer to existing V3 upload provenance, never image bytes."""

    source_asset_id: str
    consent_reference: str
    source_type: Literal["uploaded_portrait", "generated_character"] = "uploaded_portrait"

    @field_validator("source_asset_id", "consent_reference")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("library root source provenance is required")
        return value


class VisualAssetVersion(_StrictLibraryModel):
    """One reviewed module version; only Face Identity exists in release one."""

    version_id: str
    visual_asset_id: str
    module_type: Literal["face_identity"] = "face_identity"
    lifecycle_status: VisualAssetVersionStatus = "draft"
    owned_channels: tuple[str, ...] = _PEOPLE_OWNED_CHANNELS
    approved_evidence_ids: list[str] = Field(default_factory=list)
    activation_confirmed: bool = False
    immutable_source_provenance: LibraryRootSourceProvenance

    @field_validator("version_id", "visual_asset_id")
    @classmethod
    def require_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("visual asset version identifiers are required")
        return value

    @field_validator("approved_evidence_ids")
    @classmethod
    def unique_evidence(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item.strip()]
        if len(cleaned) != len(set(cleaned)):
            raise ValueError("approved evidence IDs must be unique")
        return cleaned

    @model_validator(mode="after")
    def enforce_face_identity_first_release(self) -> "VisualAssetVersion":
        if self.module_type != "face_identity" or set(self.owned_channels) != set(_PEOPLE_OWNED_CHANNELS):
            raise ValueError("only the Face Identity module is available in the first Visual Asset release")
        if self.lifecycle_status == "active":
            if not self.activation_confirmed or not self.approved_evidence_ids:
                raise ValueError("an active Visual Asset version requires reviewed evidence and user activation")
        return self


class VisualAsset(_StrictLibraryModel):
    """Library-owned reusable record.  It deliberately has no ``project_id``."""

    visual_asset_id: str
    asset_type: VisualAssetType
    display_name: str
    owner_scope: str
    lifecycle_status: VisualAssetStatus = "draft"
    root_source_provenance: LibraryRootSourceProvenance
    active_version_id: str | None = None
    versions: list[VisualAssetVersion] = Field(default_factory=list)
    created_at: str
    updated_at: str
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("visual_asset_id", "display_name", "owner_scope")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Visual Asset identity and owner scope are required")
        return value

    @model_validator(mode="after")
    def active_version_must_belong_to_asset(self) -> "VisualAsset":
        if self.asset_type != "people":
            raise ValueError("visual_asset_type_not_available")
        version_ids = {item.version_id for item in self.versions}
        if len(version_ids) != len(self.versions):
            raise ValueError("Visual Asset version IDs must be unique")
        if self.active_version_id and self.active_version_id not in version_ids:
            raise ValueError("active Visual Asset version must belong to the asset")
        if self.lifecycle_status == "active" and not self.active_version_id:
            raise ValueError("an active Visual Asset requires an active version")
        return self

    def active_version(self) -> VisualAssetVersion | None:
        return next((item for item in self.versions if item.version_id == self.active_version_id), None)


class LibraryVisualAssetCreateRequest(_StrictLibraryModel):
    display_name: str
    asset_type: VisualAssetType = "people"
    root_source_asset_id: str
    consent_reference: str
    preparation_intent: str

    @field_validator("display_name", "root_source_asset_id", "consent_reference", "preparation_intent")
    @classmethod
    def require_request_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Visual Asset creation requires complete user-confirmed source and intent information")
        return value


class ProjectVisualAssetBinding(_StrictLibraryModel):
    binding_id: str
    project_id: str
    visual_asset_id: str
    selected_version_id: str
    asset_type: Literal["people"] = "people"
    owned_channels: tuple[str, ...] = _PEOPLE_OWNED_CHANNELS
    owner_scope: str
    user_confirmed: bool
    status: ProjectBindingStatus = "active"
    created_at: str
    provenance: dict[str, str] = Field(default_factory=dict)

    @field_validator("binding_id", "project_id", "visual_asset_id", "selected_version_id", "owner_scope")
    @classmethod
    def require_binding_identifier(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Visual Asset binding identifiers are required")
        return value

    @model_validator(mode="after")
    def require_explicit_confirmation_for_active_binding(self) -> "ProjectVisualAssetBinding":
        if self.status == "active" and not self.user_confirmed:
            raise ValueError("visual_asset_binding_confirmation_required")
        if set(self.owned_channels) != set(_PEOPLE_OWNED_CHANNELS):
            raise ValueError("first-release People Asset bindings may own identity channels only")
        return self


class ProjectVisualAssetBindingRequest(_StrictLibraryModel):
    visual_asset_id: str
    selected_version_id: str | None = None
    confirm_binding: bool = False

    @field_validator("visual_asset_id", "selected_version_id")
    @classmethod
    def clean_optional_identifier(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FrozenVisualAssetBindingSet(_StrictLibraryModel):
    binding_set_id: str
    project_id: str
    job_id: str
    bindings: list[ProjectVisualAssetBinding] = Field(default_factory=list)
    state: BindingSetState = "empty"
    contract_version: Literal["visual_asset_library_binding_v1"] = "visual_asset_library_binding_v1"

    @model_validator(mode="after")
    def validate_snapshot(self) -> "FrozenVisualAssetBindingSet":
        if self.state == "empty" and self.bindings:
            raise ValueError("empty binding snapshots cannot contain bindings")
        if self.state == "valid" and not self.bindings:
            raise ValueError("valid binding snapshots require bindings")
        if any(item.project_id != self.project_id for item in self.bindings):
            raise ValueError("frozen bindings must belong to the job project")
        return self

    def to_brain_evidence(self) -> dict[str, object]:
        """Safe typed facts only; no prompt fragments, files, or raw review."""

        return {
            "contract_version": self.contract_version,
            "binding_set_id": self.binding_set_id,
            "bindings": [
                {
                    "visual_asset_id": item.visual_asset_id,
                    "selected_version_id": item.selected_version_id,
                    "asset_type": item.asset_type,
                    "owned_channels": list(item.owned_channels),
                }
                for item in self.bindings
            ],
        }


class ProjectVisualAssetBindingSet(_StrictLibraryModel):
    """Current project selection; safe to change only for future jobs."""

    project_id: str
    bindings: list[ProjectVisualAssetBinding] = Field(default_factory=list)
    state: BindingSetState = "empty"
    contract_version: Literal["visual_asset_library_binding_v1"] = "visual_asset_library_binding_v1"

    @model_validator(mode="after")
    def validate_current_set(self) -> "ProjectVisualAssetBindingSet":
        active = [item for item in self.bindings if item.status == "active"]
        if self.state == "empty" and active:
            raise ValueError("empty binding set cannot contain active bindings")
        if self.state == "valid" and not active:
            raise ValueError("valid binding set requires an active binding")
        occupied: set[str] = set()
        for item in active:
            if item.project_id != self.project_id:
                raise ValueError("all bindings must belong to one project")
            overlap = occupied.intersection(item.owned_channels)
            if overlap:
                raise ValueError("visual_asset_binding_channel_conflict")
            occupied.update(item.owned_channels)
        return self


class VisualAssetLibraryCatalog:
    """In-memory library catalog; a persistent adapter is introduced in P1."""

    def __init__(self) -> None:
        self._assets: dict[tuple[str, str], VisualAsset] = {}

    def create(self, *, owner_scope: str, request: LibraryVisualAssetCreateRequest) -> VisualAsset:
        owner_scope = owner_scope.strip()
        if not owner_scope:
            raise ValueError("visual_asset_owner_scope_required")
        if request.asset_type not in _RELEASED_ASSET_TYPES:
            raise ValueError("visual_asset_type_not_available")
        now = _utc_now()
        visual_asset_id = f"visual_asset_{uuid4().hex[:16]}"
        asset = VisualAsset(
            visual_asset_id=visual_asset_id,
            asset_type="people",
            display_name=request.display_name,
            owner_scope=owner_scope,
            root_source_provenance=LibraryRootSourceProvenance(
                source_asset_id=request.root_source_asset_id,
                consent_reference=request.consent_reference,
            ),
            created_at=now,
            updated_at=now,
            provenance={"preparation_intent": request.preparation_intent},
        )
        self._assets[(owner_scope, visual_asset_id)] = asset
        return asset.model_copy(deep=True)

    def get(self, *, owner_scope: str, visual_asset_id: str) -> VisualAsset | None:
        asset = self._assets.get((owner_scope, visual_asset_id))
        return asset.model_copy(deep=True) if asset is not None else None

    def list_assets(self, *, owner_scope: str, include_archived: bool = False) -> list[VisualAsset]:
        return [
            asset.model_copy(deep=True)
            for (scope, _), asset in sorted(self._assets.items())
            if scope == owner_scope and (include_archived or asset.lifecycle_status != "archived")
        ]

    def activate_version(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        version_id: str,
        approved_evidence_ids: list[str],
    ) -> VisualAsset:
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        if asset is None:
            raise KeyError("visual_asset_not_found")
        version = VisualAssetVersion(
            version_id=version_id,
            visual_asset_id=asset.visual_asset_id,
            lifecycle_status="active",
            approved_evidence_ids=approved_evidence_ids,
            activation_confirmed=True,
            immutable_source_provenance=asset.root_source_provenance,
        )
        superseded = [
            item.model_copy(update={"lifecycle_status": "superseded"})
            if item.lifecycle_status == "active"
            else item
            for item in asset.versions
        ]
        updated = asset.model_copy(
            update={
                "versions": [*superseded, version],
                "active_version_id": version.version_id,
                "lifecycle_status": "active",
                "updated_at": _utc_now(),
            }
        )
        self._assets[(owner_scope, visual_asset_id)] = updated
        return updated.model_copy(deep=True)


class ProjectVisualAssetBindingService:
    """Explicit current bindings plus immutable job snapshots.

    A project never owns or deletes the library asset.  Removal changes only
    future job selection; previously frozen snapshots are retained separately.
    """

    def __init__(self, catalog: VisualAssetLibraryCatalog) -> None:
        self.catalog = catalog
        self._current: dict[str, list[ProjectVisualAssetBinding]] = {}
        self._frozen: dict[tuple[str, str], FrozenVisualAssetBindingSet] = {}

    def current(self, *, project_id: str) -> ProjectVisualAssetBindingSet:
        active = [item.model_copy(deep=True) for item in self._current.get(project_id, []) if item.status == "active"]
        if not active:
            return ProjectVisualAssetBindingSet(project_id=project_id, bindings=[], state="empty")
        for binding in active:
            asset = self.catalog.get(owner_scope=binding.owner_scope, visual_asset_id=binding.visual_asset_id)
            if (
                asset is None
                or asset.lifecycle_status != "active"
                or asset.active_version_id != binding.selected_version_id
            ):
                return ProjectVisualAssetBindingSet(project_id=project_id, bindings=active, state="blocked")
        return ProjectVisualAssetBindingSet(project_id=project_id, bindings=active, state="valid")

    def bind(
        self,
        *,
        owner_scope: str,
        project_id: str,
        request: ProjectVisualAssetBindingRequest,
    ) -> ProjectVisualAssetBinding:
        if not request.confirm_binding:
            raise ValueError("visual_asset_binding_confirmation_required")
        asset = self.catalog.get(owner_scope=owner_scope, visual_asset_id=request.visual_asset_id)
        if asset is None:
            raise KeyError("visual_asset_not_found")
        selected_version_id = request.selected_version_id or asset.active_version_id
        if asset.lifecycle_status != "active" or selected_version_id != asset.active_version_id:
            raise ValueError("visual_asset_version_not_active")
        existing = self.current(project_id=project_id)
        if existing.state == "blocked":
            raise ValueError("visual_asset_binding_set_blocked")
        if any(set(item.owned_channels).intersection(_PEOPLE_OWNED_CHANNELS) for item in existing.bindings):
            raise ValueError("visual_asset_binding_channel_conflict")
        binding = ProjectVisualAssetBinding(
            binding_id=f"binding_{uuid4().hex[:16]}",
            project_id=project_id,
            visual_asset_id=asset.visual_asset_id,
            selected_version_id=selected_version_id,
            owner_scope=owner_scope,
            user_confirmed=True,
            created_at=_utc_now(),
            provenance={"selection": "user_confirmed"},
        )
        self._current.setdefault(project_id, []).append(binding)
        return binding.model_copy(deep=True)

    def remove(self, *, project_id: str, binding_id: str, confirm_removal: bool) -> ProjectVisualAssetBinding:
        if not confirm_removal:
            raise ValueError("visual_asset_binding_removal_confirmation_required")
        records = self._current.get(project_id, [])
        for index, record in enumerate(records):
            if record.binding_id == binding_id and record.status == "active":
                removed = record.model_copy(update={"status": "removed"})
                records[index] = removed
                return removed.model_copy(deep=True)
        raise KeyError("visual_asset_binding_not_found")

    def freeze_for_job(self, *, project_id: str, job_id: str) -> FrozenVisualAssetBindingSet:
        current = self.current(project_id=project_id)
        if current.state == "blocked":
            raise ValueError("visual_asset_binding_set_blocked")
        snapshot = FrozenVisualAssetBindingSet(
            binding_set_id=f"frozen_binding_set_{uuid4().hex[:16]}",
            project_id=project_id,
            job_id=job_id,
            bindings=[item.model_copy(deep=True) for item in current.bindings],
            state=current.state,
        )
        self._frozen[(project_id, job_id)] = snapshot
        return snapshot.model_copy(deep=True)

    def frozen_for_job(self, *, project_id: str, job_id: str) -> FrozenVisualAssetBindingSet | None:
        snapshot = self._frozen.get((project_id, job_id))
        return snapshot.model_copy(deep=True) if snapshot is not None else None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


__all__ = [
    "FrozenVisualAssetBindingSet",
    "LibraryRootSourceProvenance",
    "LibraryVisualAssetCreateRequest",
    "ProjectVisualAssetBinding",
    "ProjectVisualAssetBindingRequest",
    "ProjectVisualAssetBindingService",
    "ProjectVisualAssetBindingSet",
    "VisualAsset",
    "VisualAssetLibraryCatalog",
    "VisualAssetVersion",
]
