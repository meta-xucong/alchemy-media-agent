"""Doc173 library-first Visual Asset contracts and project binding service.

This module is intentionally small and framework-neutral.  It separates
reusable asset ownership from project usage without creating a second image,
Brain, Provider, review, retry, or byte-storage system.  The initial release
owned People Asset / Face Identity; Doc178 supersedes that scope by adding the
Character Card's nested Face, Expression, and Body modules without changing
the Visual Asset category or Standard Mode.
"""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Any, Callable, Literal, Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel
from .anchor_pack import AnchorPackPreparationResult
from .character_card import (
    BodySilhouettePublicRequest,
    CharacterCardPreparationService,
    CharacterCardRuntimeUnavailable,
    CharacterCardStageHost,
    CharacterCardState,
    apply_face_identity_pack_to_card,
)
from .contracts import (
    FACE_IDENTITY_CHANNELS,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    PeopleAsset,
    RootSourceProvenance,
)


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
_SAFE_STORAGE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class _StrictLibraryModel(V3BaseModel):
    model_config = ConfigDict(validate_assignment=True, validate_default=True, extra="forbid")


class LibraryRootSourceProvenance(_StrictLibraryModel):
    """Safe pointer to existing V3 upload provenance, never image bytes."""

    source_asset_id: str
    consent_reference: str
    source_type: Literal["uploaded_portrait", "generated_character"] = "uploaded_portrait"
    supplementary_source_asset_ids: list[str] = Field(default_factory=list, max_length=1)

    @field_validator("source_asset_id", "consent_reference")
    @classmethod
    def require_nonempty(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("library root source provenance is required")
        return value

    @model_validator(mode="after")
    def validate_supplementary_sources(self) -> "LibraryRootSourceProvenance":
        supplemental = [str(item or "").strip() for item in self.supplementary_source_asset_ids]
        if any(not item for item in supplemental):
            raise ValueError("supplementary source evidence is required when supplied")
        if self.source_asset_id in supplemental or len(supplemental) != len(set(supplemental)):
            raise ValueError("supplementary source evidence must be unique and cannot repeat the root")
        return self


class VisualAssetVersion(_StrictLibraryModel):
    """One reviewed Face Identity version; Character Card modules remain nested state."""

    version_id: str
    visual_asset_id: str
    module_type: Literal["face_identity"] = "face_identity"
    lifecycle_status: VisualAssetVersionStatus = "draft"
    owned_channels: tuple[str, ...] = _PEOPLE_OWNED_CHANNELS
    approved_evidence_ids: list[str] = Field(default_factory=list)
    activation_confirmed: bool = False
    immutable_source_provenance: LibraryRootSourceProvenance
    # Metadata only: this is the existing append-only Anchor Pack contract,
    # not an alternate pixel store.  It lets the generic library lifecycle
    # reuse the shared three-view preparation and explicit activation host.
    anchor_pack: IdentityAnchorPackVersion | None = None
    # Safe operator-facing classification for a failed preparation.  This is
    # deliberately not a provider error body, prompt, endpoint, or job ID.
    failure_code: str | None = None
    failure_attempt_count: int = Field(default=0, ge=0, le=3)
    # The renderer channel is provenance only.  Both channels write through
    # the same V3 output/review/winner contract and therefore the same card
    # slots; it never changes the asset's identity semantics.
    generation_channel: Literal["provider", "mcp"] = "provider"
    # Opaque receipts used only to resume a blocked local MCP materialization.
    # They never contain a path, prompt, provider response, or artifact.
    mcp_handoff_ids: list[str] = Field(default_factory=list)

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
            raise ValueError("Visual Asset versions own the Face Identity base; Doc178 Character Card modules are nested")
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
    preparation_intent: str
    active_version_id: str | None = None
    versions: list[VisualAssetVersion] = Field(default_factory=list)
    created_at: str
    updated_at: str
    provenance: dict[str, str] = Field(default_factory=dict)
    # Doc178 adds a resumable Character Card template inside the same People
    # Asset.  It is not a new asset category and stays empty until the shared
    # Face/Expression/Body stages produce reviewed evidence.
    character_card: CharacterCardState = Field(
        default_factory=lambda: CharacterCardState.initial(card_version_id="card_pending")
    )

    @field_validator("visual_asset_id", "display_name", "owner_scope", "preparation_intent")
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
    supplementary_source_asset_ids: list[str] = Field(default_factory=list, max_length=1)

    @field_validator("display_name", "root_source_asset_id", "consent_reference", "preparation_intent")
    @classmethod
    def require_request_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Visual Asset creation requires complete user-confirmed source and intent information")
        return value

    @model_validator(mode="after")
    def validate_supplementary_sources(self) -> "LibraryVisualAssetCreateRequest":
        supplemental = [str(item or "").strip() for item in self.supplementary_source_asset_ids]
        if any(not item for item in supplemental):
            raise ValueError("supplementary source evidence is required when supplied")
        if self.root_source_asset_id in supplemental or len(supplemental) != len(set(supplemental)):
            raise ValueError("supplementary source evidence must be unique and cannot repeat the root")
        return self


class ProjectVisualAssetBinding(_StrictLibraryModel):
    binding_id: str
    project_id: str
    visual_asset_id: str
    selected_version_id: str
    asset_type: Literal["people"] = "people"
    owned_channels: tuple[str, ...] = _PEOPLE_OWNED_CHANNELS
    approved_evidence_ids: list[str] = Field(default_factory=list)
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
                    "approved_evidence_ids": list(item.approved_evidence_ids),
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
                supplementary_source_asset_ids=list(request.supplementary_source_asset_ids),
            ),
            preparation_intent=request.preparation_intent,
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

    def save(self, asset: VisualAsset) -> VisualAsset:
        """Persist a validated current metadata revision without mutating history."""

        key = (asset.owner_scope, asset.visual_asset_id)
        if key not in self._assets:
            raise KeyError("visual_asset_not_found")
        self._assets[key] = asset.model_copy(deep=True)
        return asset.model_copy(deep=True)


class PersistentVisualAssetLibraryCatalog(VisualAssetLibraryCatalog):
    """JSON-backed library metadata catalog.

    The backing root is deliberately separate from the historical
    ``PersistentVisualAssetCatalog`` project directory.  It persists metadata
    and evidence pointers only; uploads, outputs, candidates and review
    receipts remain in their existing shared stores.
    """

    def __init__(self, storage_root: str | Path) -> None:
        super().__init__()
        self.storage_root = Path(storage_root)
        self._loaded_scopes: set[str] = set()

    def create(self, *, owner_scope: str, request: LibraryVisualAssetCreateRequest) -> VisualAsset:
        self._load_scope(owner_scope)
        created = super().create(owner_scope=owner_scope, request=request)
        self._write_scope(owner_scope)
        return created

    def get(self, *, owner_scope: str, visual_asset_id: str) -> VisualAsset | None:
        self._load_scope(owner_scope)
        return super().get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)

    def list_assets(self, *, owner_scope: str, include_archived: bool = False) -> list[VisualAsset]:
        self._load_scope(owner_scope)
        return super().list_assets(owner_scope=owner_scope, include_archived=include_archived)

    def activate_version(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        version_id: str,
        approved_evidence_ids: list[str],
    ) -> VisualAsset:
        self._load_scope(owner_scope)
        activated = super().activate_version(
            owner_scope=owner_scope,
            visual_asset_id=visual_asset_id,
            version_id=version_id,
            approved_evidence_ids=approved_evidence_ids,
        )
        self._write_scope(owner_scope)
        return activated

    def save(self, asset: VisualAsset) -> VisualAsset:
        self._load_scope(asset.owner_scope)
        saved = super().save(asset)
        self._write_scope(asset.owner_scope)
        return saved

    def _load_scope(self, owner_scope: str) -> None:
        _validate_storage_component(owner_scope, "owner_scope")
        if owner_scope in self._loaded_scopes:
            return
        self._loaded_scopes.add(owner_scope)
        path = self._scope_path(owner_scope)
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, list):
            return
        for item in payload:
            try:
                asset = VisualAsset.model_validate(item)
            except Exception:
                continue
            if asset.owner_scope == owner_scope:
                self._assets[(owner_scope, asset.visual_asset_id)] = asset

    def _write_scope(self, owner_scope: str) -> None:
        path = self._scope_path(owner_scope)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            item.model_dump(mode="json")
            for (scope, _), item in sorted(self._assets.items())
            if scope == owner_scope
        ]
        _atomic_write_json(path, payload)

    def _scope_path(self, owner_scope: str) -> Path:
        _validate_storage_component(owner_scope, "owner_scope")
        return self.storage_root / "library" / owner_scope / "visual_assets.json"


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
        version = asset.active_version()
        if version is None or not version.approved_evidence_ids:
            raise ValueError("visual_asset_binding_evidence_required")
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
            approved_evidence_ids=list(version.approved_evidence_ids),
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


class PersistentProjectVisualAssetBindingService(ProjectVisualAssetBindingService):
    """Persist project selections and append-only frozen job snapshots.

    Current bindings and historical snapshots are separate files.  Updating or
    removing a project selection therefore cannot mutate an old Job's frozen
    evidence truth.
    """

    def __init__(self, catalog: VisualAssetLibraryCatalog, storage_root: str | Path) -> None:
        super().__init__(catalog)
        self.storage_root = Path(storage_root)
        self._loaded_projects: set[str] = set()
        self._loaded_frozen_projects: set[str] = set()

    def current(self, *, project_id: str) -> ProjectVisualAssetBindingSet:
        self._load_project(project_id)
        return super().current(project_id=project_id)

    def bind(
        self,
        *,
        owner_scope: str,
        project_id: str,
        request: ProjectVisualAssetBindingRequest,
    ) -> ProjectVisualAssetBinding:
        self._load_project(project_id)
        binding = super().bind(owner_scope=owner_scope, project_id=project_id, request=request)
        self._write_current(project_id)
        return binding

    def remove(self, *, project_id: str, binding_id: str, confirm_removal: bool) -> ProjectVisualAssetBinding:
        self._load_project(project_id)
        removed = super().remove(
            project_id=project_id,
            binding_id=binding_id,
            confirm_removal=confirm_removal,
        )
        self._write_current(project_id)
        return removed

    def freeze_for_job(self, *, project_id: str, job_id: str) -> FrozenVisualAssetBindingSet:
        self._load_project(project_id)
        snapshot = super().freeze_for_job(project_id=project_id, job_id=job_id)
        self._write_frozen(project_id)
        return snapshot

    def frozen_for_job(self, *, project_id: str, job_id: str) -> FrozenVisualAssetBindingSet | None:
        self._load_frozen(project_id)
        return super().frozen_for_job(project_id=project_id, job_id=job_id)

    def _load_project(self, project_id: str) -> None:
        _validate_storage_component(project_id, "project_id")
        if project_id in self._loaded_projects:
            return
        self._loaded_projects.add(project_id)
        path = self._current_path(project_id)
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, list):
            return
        records: list[ProjectVisualAssetBinding] = []
        for item in payload:
            try:
                binding = ProjectVisualAssetBinding.model_validate(item)
            except Exception:
                continue
            if binding.project_id == project_id:
                records.append(binding)
        self._current[project_id] = records

    def _load_frozen(self, project_id: str) -> None:
        _validate_storage_component(project_id, "project_id")
        if project_id in self._loaded_frozen_projects:
            return
        self._loaded_frozen_projects.add(project_id)
        path = self._frozen_path(project_id)
        if not path.exists():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(payload, list):
            return
        for item in payload:
            try:
                snapshot = FrozenVisualAssetBindingSet.model_validate(item)
            except Exception:
                continue
            if snapshot.project_id == project_id:
                self._frozen[(project_id, snapshot.job_id)] = snapshot

    def _write_current(self, project_id: str) -> None:
        path = self._current_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(path, [item.model_dump(mode="json") for item in self._current.get(project_id, [])])

    def _write_frozen(self, project_id: str) -> None:
        path = self._frozen_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            item.model_dump(mode="json")
            for (owner, _), item in sorted(self._frozen.items())
            if owner == project_id
        ]
        _atomic_write_json(path, payload)

    def _current_path(self, project_id: str) -> Path:
        _validate_storage_component(project_id, "project_id")
        return self.storage_root / "project_bindings" / project_id / "current_bindings.json"

    def _frozen_path(self, project_id: str) -> Path:
        _validate_storage_component(project_id, "project_id")
        return self.storage_root / "project_bindings" / project_id / "frozen_job_bindings.json"


class LibraryAssetPreparationHost(Protocol):
    """The already-existing shared Anchor Pack host, expressed generically."""

    def prepare(
        self,
        *,
        project_id: str,
        people_asset: PeopleAsset,
        root_source_provenance: RootSourceProvenance,
    ) -> AnchorPackPreparationResult:
        """Prepare through shared Brain/Provider/Vision only."""

    def activate(self, pack: IdentityAnchorPackVersion, *, confirmed: bool) -> IdentityAnchorPackVersion:
        """Activate an already reviewed pack after user confirmation."""

    def prepare_character_card(
        self,
        *,
        project_id: str,
        people_asset: PeopleAsset,
        root_source_provenance: RootSourceProvenance,
    ) -> AnchorPackPreparationResult:
        """Prepare the additive reverse/rear Face Identity slots."""


class VisualAssetLibraryLifecycleService:
    """Library lifecycle that adapts the existing shared Face Identity host.

    The adapter owns no prompt, provider or reviewer.  Its only job is to map
    a library asset's immutable provenance to the existing Face Identity
    preparation contract and save the resulting metadata version back under
    the library owner scope.
    """

    def __init__(
        self,
        catalog: VisualAssetLibraryCatalog,
        *,
        root_source_resolver: Callable[[str], Any | None] | None = None,
        anchor_pack_host: LibraryAssetPreparationHost | None = None,
        character_card_stage_host: CharacterCardStageHost | None = None,
    ) -> None:
        self.catalog = catalog
        self.root_source_resolver = root_source_resolver
        self.anchor_pack_host = anchor_pack_host
        self.character_card_stage_host = character_card_stage_host

    def create_draft(
        self,
        *,
        owner_scope: str,
        request: LibraryVisualAssetCreateRequest,
    ) -> VisualAsset:
        if self.root_source_resolver is not None:
            source_ids = [request.root_source_asset_id, *request.supplementary_source_asset_ids]
            for index, source_asset_id in enumerate(source_ids):
                source = self.root_source_resolver(source_asset_id)
                if source is None or str(getattr(source, "status", "") or "").lower() != "ready":
                    raise ValueError(
                        "root_source_asset_not_ready" if index == 0 else "supplementary_source_asset_not_ready"
                    )
                role = getattr(source, "role", None)
                resolved_role = str(getattr(role, "value", role) or "").strip().lower()
                if request.asset_type == "people" and resolved_role != "face_reference":
                    raise ValueError(
                        "visual_asset_root_requires_face_reference"
                        if index == 0
                        else "visual_asset_supplementary_requires_face_reference"
                    )
        return self.catalog.create(owner_scope=owner_scope, request=request)

    def get(self, *, owner_scope: str, visual_asset_id: str) -> VisualAsset:
        asset = self.catalog.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        if asset is None:
            raise KeyError("visual_asset_not_found")
        return asset

    def list(self, *, owner_scope: str) -> list[VisualAsset]:
        return self.catalog.list_assets(owner_scope=owner_scope)

    def prepare(self, *, owner_scope: str, visual_asset_id: str) -> VisualAsset:
        if self.anchor_pack_host is None:
            raise RuntimeError("visual_asset_prepare_unavailable")
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        if asset.asset_type != "people":
            raise ValueError("visual_asset_type_not_available")
        staging_project_id = _library_staging_scope(owner_scope)
        people_asset = PeopleAsset(
            people_asset_id=asset.visual_asset_id,
            project_id=staging_project_id,
            subject_kind="human_person",
            face_identity_module=FaceIdentityModule(
                module_id=f"face_{asset.visual_asset_id}",
                people_asset_id=asset.visual_asset_id,
                status="draft",
            ),
            root_source_provenance=RootSourceProvenance(
                source_type="uploaded_portrait",
                source_asset_id=asset.root_source_provenance.source_asset_id,
                project_id=staging_project_id,
                consent_reference=asset.root_source_provenance.consent_reference,
                supplementary_source_asset_ids=list(asset.root_source_provenance.supplementary_source_asset_ids),
            ),
            preparation_intent=asset.preparation_intent,
            status="draft",
        )
        result = self.anchor_pack_host.prepare(
            project_id=staging_project_id,
            people_asset=people_asset,
            root_source_provenance=people_asset.root_source_provenance,
        )
        pack = result.pack
        if (
            pack.people_asset_id != asset.visual_asset_id
            or pack.root_source_provenance.source_asset_id != asset.root_source_provenance.source_asset_id
        ):
            raise ValueError("visual_asset_prepare_binding_mismatch")
        version = VisualAssetVersion(
            version_id=pack.pack_version_id,
            visual_asset_id=asset.visual_asset_id,
            lifecycle_status="review" if pack.status == "review" else "failed",
            approved_evidence_ids=[item.output_id for item in pack.anchor_views if item.active],
            activation_confirmed=False,
            immutable_source_provenance=asset.root_source_provenance,
            anchor_pack=pack,
            failure_code=(
                next(
                    (
                        str(item.failure_code).strip()
                        for item in result.generation_failures
                        if str(item.failure_code or "").strip()
                    ),
                    None,
                )
                or (
                    str(result.failure_codes[0]).strip()
                    if pack.status != "review" and result.failure_codes
                    else None
                )
            ),
            mcp_handoff_ids=list(getattr(result, "mcp_handoff_ids", []) or []),
        )
        existing_versions = [item for item in asset.versions if item.version_id != version.version_id]
        updated = asset.model_copy(
            update={
                "versions": [*existing_versions, version],
                "lifecycle_status": "review" if version.lifecycle_status == "review" else "blocked",
                "updated_at": _utc_now(),
            }
        )
        return self.catalog.save(updated)

    def activate(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        version_id: str,
        confirm_activation: bool,
    ) -> VisualAsset:
        if not confirm_activation:
            raise ValueError("visual_asset_activation_confirmation_required")
        if self.anchor_pack_host is None:
            raise RuntimeError("visual_asset_activate_unavailable")
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        version = next((item for item in asset.versions if item.version_id == version_id), None)
        if version is None or version.lifecycle_status != "review" or version.anchor_pack is None:
            raise ValueError("visual_asset_version_not_ready_for_activation")
        active_pack = self.anchor_pack_host.activate(version.anchor_pack, confirmed=True)
        if active_pack.status != "active" or not active_pack.user_activation_confirmed:
            raise ValueError("visual_asset_activation_not_confirmed")
        active_version = version.model_copy(
            update={
                "lifecycle_status": "active",
                "activation_confirmed": True,
                "approved_evidence_ids": [item.output_id for item in active_pack.anchor_views if item.active],
                "anchor_pack": active_pack,
            }
        )
        versions = [
            active_version
            if item.version_id == version_id
            else item.model_copy(update={"lifecycle_status": "superseded"})
            if item.lifecycle_status == "active"
            else item
            for item in asset.versions
        ]
        return self.catalog.save(
            asset.model_copy(
                update={
                    "versions": versions,
                    "active_version_id": version_id,
                    "lifecycle_status": "active",
                    "character_card": apply_face_identity_pack_to_card(asset.character_card, active_pack),
                    "updated_at": _utc_now(),
                }
            )
        )

    def archive(self, *, owner_scope: str, visual_asset_id: str) -> VisualAsset:
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        return self.catalog.save(
            asset.model_copy(update={"lifecycle_status": "archived", "updated_at": _utc_now()})
        )

    def prepare_character_card_stage(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        stage: Literal["expression_set", "body_silhouette"],
        body_request: BodySilhouettePublicRequest | None = None,
        generation_channel: Literal["provider", "mcp"] = "provider",
    ) -> VisualAsset:
        """Resume one Character Card stage through a shared-runtime host."""

        if self.character_card_stage_host is None:
            raise CharacterCardRuntimeUnavailable("character_card_stage_prepare_unavailable")
        if getattr(self.character_card_stage_host, "production_shared_runtime", False) is not True:
            raise CharacterCardRuntimeUnavailable("character_card_stage_host_shared_runtime_required")
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        card = asset.character_card
        if stage == "expression_set" and card.face_identity_status != "active":
            raise ValueError("character_card_expression_requires_face_identity")
        if stage == "body_silhouette":
            if card.face_identity_status != "active":
                raise ValueError("character_card_body_requires_face_identity")
            if card.expression_set_status != "active":
                raise ValueError("character_card_body_requires_expression_set")
            if body_request is None:
                raise ValueError("character_card_body_source_required")
            if body_request.source_class == "observed":
                self._require_authorized_body_reference(body_request)
        method = getattr(self.character_card_stage_host, f"prepare_{stage}", None)
        if not callable(method):
            raise CharacterCardRuntimeUnavailable("character_card_stage_prepare_unavailable")
        if stage == "body_silhouette":
            method_kwargs = {"asset": asset, "card": card, "request": body_request}
            if generation_channel == "mcp":
                method_kwargs["generation_channel"] = "mcp"
            result = method(**method_kwargs)
        else:
            # Expression intent must come from the shared host/Brain.  There is
            # intentionally no browser-side expression dictionary or local
            # default wording to pass here.
            method_kwargs = {"asset": asset, "card": card}
            if generation_channel == "mcp":
                method_kwargs["generation_channel"] = "mcp"
            result = method(**method_kwargs)
        if getattr(result, "card", None) is None:
            raise ValueError("character_card_stage_result_missing")
        if getattr(result, "status", None) == "review":
            if getattr(result, "shared_runtime_receipt", None) is None:
                raise CharacterCardRuntimeUnavailable("character_card_shared_runtime_receipt_required")
        elif getattr(result, "status", None) == "blocked":
            if getattr(result, "shared_runtime_failure", None) is None:
                raise CharacterCardRuntimeUnavailable("character_card_shared_runtime_failure_receipt_required")
        else:
            raise CharacterCardRuntimeUnavailable("character_card_stage_status_invalid")
        return self.catalog.save(
            asset.model_copy(update={"character_card": result.card, "updated_at": _utc_now()})
        )

    def _require_authorized_body_reference(self, request: BodySilhouettePublicRequest) -> Any:
        """Resolve an observed body source without accepting paths or claims."""

        if self.root_source_resolver is None:
            raise CharacterCardRuntimeUnavailable("character_card_body_reference_unavailable")
        source = self.root_source_resolver(str(request.body_reference_asset_id))
        status = str(getattr(getattr(source, "status", None), "value", getattr(source, "status", "")) or "").lower()
        role = str(getattr(getattr(source, "role", None), "value", getattr(source, "role", "")) or "").strip().lower()
        if source is None or status != "ready":
            raise ValueError("character_card_body_reference_not_ready")
        if role not in {"full_body_reference", "body_reference", "body_full_reference"}:
            raise ValueError("character_card_body_reference_role_invalid")
        metadata = getattr(source, "metadata", {}) or {}
        consent = metadata.get("consent_reference") or metadata.get("rights_reference")
        if not str(consent or "").strip():
            raise ValueError("character_card_body_reference_consent_required")
        return source

    def prepare_character_card_face(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        resume: bool = False,
        generation_channel: Literal["provider", "mcp"] = "provider",
    ) -> VisualAsset:
        """Prepare all five Face Identity slots through the existing host."""

        if self.anchor_pack_host is None:
            raise CharacterCardRuntimeUnavailable("character_card_face_prepare_unavailable")
        method = getattr(self.anchor_pack_host, "prepare_character_card", None)
        if not callable(method):
            raise CharacterCardRuntimeUnavailable("character_card_face_prepare_unavailable")
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        staging_project_id = _library_staging_scope(owner_scope)
        people_asset = PeopleAsset(
            people_asset_id=asset.visual_asset_id,
            project_id=staging_project_id,
            subject_kind="human_person",
            face_identity_module=FaceIdentityModule(
                module_id=f"face_{asset.visual_asset_id}",
                people_asset_id=asset.visual_asset_id,
                status="draft",
            ),
            root_source_provenance=RootSourceProvenance(
                source_type="uploaded_portrait",
                source_asset_id=asset.root_source_provenance.source_asset_id,
                project_id=staging_project_id,
                consent_reference=asset.root_source_provenance.consent_reference,
                supplementary_source_asset_ids=list(asset.root_source_provenance.supplementary_source_asset_ids),
            ),
            preparation_intent=asset.preparation_intent,
            status="draft",
        )
        resume_pack = None
        if resume:
            resume_pack = next(
                (
                    version.anchor_pack
                    for version in reversed(asset.versions)
                    if version.lifecycle_status == "failed"
                    and version.anchor_pack is not None
                    and version.anchor_pack.status == "failed"
                ),
                None,
            )
            if resume_pack is None:
                raise ValueError("character_card_face_resume_checkpoint_missing")
        method_kwargs = {
            "project_id": staging_project_id,
            "people_asset": people_asset,
            "root_source_provenance": people_asset.root_source_provenance,
        }
        if resume_pack is not None:
            method_kwargs["resume_from_pack"] = resume_pack
        if generation_channel == "mcp":
            method_kwargs["generation_channel"] = "mcp"
        result = method(
            **method_kwargs,
        )
        pack = result.pack
        if pack.people_asset_id != asset.visual_asset_id or pack.root_source_provenance.source_asset_id != asset.root_source_provenance.source_asset_id:
            raise ValueError("character_card_face_prepare_binding_mismatch")
        version = VisualAssetVersion(
            version_id=pack.pack_version_id,
            visual_asset_id=asset.visual_asset_id,
            lifecycle_status="review" if pack.status == "review" else "failed",
            approved_evidence_ids=[item.output_id for item in pack.anchor_views if item.active],
            activation_confirmed=False,
            immutable_source_provenance=asset.root_source_provenance,
            anchor_pack=pack,
            failure_code=(
                next(
                    (
                        str(item.failure_code).strip()
                        for item in result.generation_failures
                        if str(item.failure_code or "").strip()
                    ),
                    None,
                )
                or (
                    str(result.failure_codes[0]).strip()
                    if pack.status != "review" and result.failure_codes
                    else None
                )
            ),
            failure_attempt_count=(
                min(3, max(1, len(result.generation_failures) or len(result.failure_codes) or 3))
                if pack.status != "review"
                else 0
            ),
            generation_channel=generation_channel,
            mcp_handoff_ids=list(getattr(result, "mcp_handoff_ids", []) or []),
        )
        existing_versions = [item for item in asset.versions if item.version_id != version.version_id]
        card = asset.character_card
        if pack.status in {"review", "failed"}:
            card = apply_face_identity_pack_to_card(card, pack)
            if pack.status == "review":
                card = card.model_copy(update={"face_identity_status": "reviewing"})
            else:
                failure_code = version.failure_code or "character_card_face_prepare_paused"
                active_view_count = sum(1 for item in pack.anchor_views if item.active)
                card = card.model_copy(
                    update={
                        "face_identity_status": "partial" if active_view_count else "blocked",
                        "last_failure_code": failure_code,
                        "last_failure_attempt_count": 3,
                        "resume_available": True,
                    }
                )
        updated = asset.model_copy(
            update={
                "versions": [*existing_versions, version],
                "lifecycle_status": "review" if version.lifecycle_status == "review" else "blocked",
                "character_card": card,
                "updated_at": _utc_now(),
            }
        )
        return self.catalog.save(updated)

    def activate_character_card_module(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        module: Literal["expression_set", "body_silhouette"],
        confirm_activation: bool,
    ) -> VisualAsset:
        if not confirm_activation:
            raise ValueError("character_card_module_activation_confirmation_required")
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        card = CharacterCardPreparationService.activate_module(
            asset.character_card,
            module=module,
            confirmed=True,
        )
        return self.catalog.save(asset.model_copy(update={"character_card": card, "updated_at": _utc_now()}))

    def activate_character_card_face(
        self,
        *,
        owner_scope: str,
        visual_asset_id: str,
        confirm_activation: bool,
    ) -> VisualAsset:
        """Activate the reviewed Face Identity module from the Character Card route."""

        if not confirm_activation:
            raise ValueError("character_card_face_activation_confirmation_required")
        asset = self.get(owner_scope=owner_scope, visual_asset_id=visual_asset_id)
        latest_version = asset.versions[-1] if asset.versions else None
        if latest_version is None or latest_version.lifecycle_status != "review":
            raise ValueError("character_card_face_not_ready_for_activation")
        return self.activate(
            owner_scope=owner_scope,
            visual_asset_id=visual_asset_id,
            version_id=latest_version.version_id,
            confirm_activation=True,
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _validate_storage_component(value: str, label: str) -> None:
    if not _SAFE_STORAGE_COMPONENT.fullmatch(str(value or "")):
        raise ValueError(f"invalid {label}")


def _atomic_write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def _library_staging_scope(owner_scope: str) -> str:
    """Internal compatibility scope for existing project-scoped Anchor Pack types."""

    import hashlib

    return f"library_{hashlib.sha256(owner_scope.encode('utf-8')).hexdigest()[:20]}"


__all__ = [
    "FrozenVisualAssetBindingSet",
    "LibraryRootSourceProvenance",
    "LibraryVisualAssetCreateRequest",
    "LibraryAssetPreparationHost",
    "ProjectVisualAssetBinding",
    "ProjectVisualAssetBindingRequest",
    "ProjectVisualAssetBindingService",
    "ProjectVisualAssetBindingSet",
    "VisualAsset",
    "VisualAssetLibraryCatalog",
    "VisualAssetVersion",
    "VisualAssetLibraryLifecycleService",
    "PersistentProjectVisualAssetBindingService",
    "PersistentVisualAssetLibraryCatalog",
]
