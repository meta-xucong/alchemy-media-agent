"""Project-scoped People Asset catalog and append-only lifecycle history."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import re
from typing import Literal
from uuid import uuid4

from pydantic import ConfigDict, Field

from ..schemas.models import V3BaseModel
from .contracts import IdentityAnchorPackVersion, PeopleAsset


CatalogEventType = Literal["create", "update", "activate", "supersede", "archive"]
PackEventType = Literal["prepare", "review", "activate", "supersede", "fail"]
_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


class PeopleAssetRevision(V3BaseModel):
    """Immutable metadata snapshot; image bytes remain in existing V3 stores."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    revision_id: str
    project_id: str
    people_asset_id: str
    event_type: CatalogEventType
    created_at: str
    asset_snapshot: PeopleAsset


class AnchorPackRevision(V3BaseModel):
    """Immutable pack metadata snapshot; candidate pixels stay in V3 output storage."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    revision_id: str
    project_id: str
    people_asset_id: str
    pack_version_id: str
    event_type: PackEventType
    created_at: str
    pack_snapshot: IdentityAnchorPackVersion


class InMemoryVisualAssetCatalog:
    """Small catalog abstraction used by M1 and future Project Mode adapters."""

    def __init__(self) -> None:
        self._assets: dict[tuple[str, str], PeopleAsset] = {}
        self._history: dict[tuple[str, str], list[PeopleAssetRevision]] = {}
        self._packs: dict[tuple[str, str, str], IdentityAnchorPackVersion] = {}
        self._pack_history: dict[tuple[str, str], list[AnchorPackRevision]] = {}

    def save(
        self,
        asset: PeopleAsset,
        *,
        project_id: str | None = None,
        event_type: CatalogEventType = "update",
    ) -> PeopleAsset:
        owner_project_id = project_id or asset.project_id
        _validate_component(owner_project_id, "project_id")
        _validate_component(asset.people_asset_id, "people_asset_id")
        if owner_project_id != asset.project_id:
            raise ValueError("People Asset and catalog entry must belong to the same project")
        key = (owner_project_id, asset.people_asset_id)
        snapshot = asset.model_copy(deep=True)
        self._assets[key] = snapshot
        self._history.setdefault(key, []).append(
            PeopleAssetRevision(
                revision_id=f"revision_{uuid4().hex}",
                project_id=owner_project_id,
                people_asset_id=asset.people_asset_id,
                event_type=event_type,
                created_at=datetime.now(UTC).isoformat(),
                asset_snapshot=snapshot,
            )
        )
        return snapshot.model_copy(deep=True)

    def save_pack(
        self,
        pack: IdentityAnchorPackVersion,
        *,
        project_id: str | None = None,
        event_type: PackEventType = "review",
    ) -> IdentityAnchorPackVersion:
        owner_project_id = project_id or pack.root_source_provenance.project_id
        _validate_component(owner_project_id, "project_id")
        _validate_component(pack.people_asset_id, "people_asset_id")
        _validate_component(pack.pack_version_id, "pack_version_id")
        if owner_project_id != pack.root_source_provenance.project_id:
            raise ValueError("anchor pack and catalog entry must belong to the same project")
        key = (owner_project_id, pack.people_asset_id, pack.pack_version_id)
        snapshot = pack.model_copy(deep=True)
        self._packs[key] = snapshot
        self._pack_history.setdefault((owner_project_id, pack.people_asset_id), []).append(
            AnchorPackRevision(
                revision_id=f"pack_revision_{uuid4().hex}",
                project_id=owner_project_id,
                people_asset_id=pack.people_asset_id,
                pack_version_id=pack.pack_version_id,
                event_type=event_type,
                created_at=datetime.now(UTC).isoformat(),
                pack_snapshot=snapshot,
            )
        )
        return snapshot.model_copy(deep=True)

    def get(self, project_id: str, people_asset_id: str) -> PeopleAsset | None:
        _validate_component(project_id, "project_id")
        _validate_component(people_asset_id, "people_asset_id")
        asset = self._assets.get((project_id, people_asset_id))
        return asset.model_copy(deep=True) if asset is not None else None

    def list_assets(self, project_id: str) -> list[PeopleAsset]:
        _validate_component(project_id, "project_id")
        return [
            asset.model_copy(deep=True)
            for (owner, _), asset in sorted(self._assets.items())
            if owner == project_id
        ]

    def list_history(self, project_id: str, people_asset_id: str) -> list[PeopleAssetRevision]:
        _validate_component(project_id, "project_id")
        _validate_component(people_asset_id, "people_asset_id")
        return [item.model_copy(deep=True) for item in self._history.get((project_id, people_asset_id), [])]

    def get_pack(self, project_id: str, people_asset_id: str, pack_version_id: str) -> IdentityAnchorPackVersion | None:
        _validate_component(project_id, "project_id")
        _validate_component(people_asset_id, "people_asset_id")
        _validate_component(pack_version_id, "pack_version_id")
        pack = self._packs.get((project_id, people_asset_id, pack_version_id))
        return pack.model_copy(deep=True) if pack is not None else None

    def list_pack_history(self, project_id: str, people_asset_id: str) -> list[AnchorPackRevision]:
        _validate_component(project_id, "project_id")
        _validate_component(people_asset_id, "people_asset_id")
        return [
            item.model_copy(deep=True)
            for item in self._pack_history.get((project_id, people_asset_id), [])
        ]


class PersistentVisualAssetCatalog(InMemoryVisualAssetCatalog):
    """Metadata-only catalog with per-project JSON and append-only history."""

    def __init__(self, storage_root: str | Path) -> None:
        super().__init__()
        self.storage_root = Path(storage_root)
        self._loaded_projects: set[str] = set()

    def save(
        self,
        asset: PeopleAsset,
        *,
        project_id: str | None = None,
        event_type: CatalogEventType = "update",
    ) -> PeopleAsset:
        owner_project_id = project_id or asset.project_id
        self._load_project(owner_project_id)
        saved = super().save(asset, project_id=project_id, event_type=event_type)
        self._write_project(owner_project_id)
        return saved

    def save_pack(
        self,
        pack: IdentityAnchorPackVersion,
        *,
        project_id: str | None = None,
        event_type: PackEventType = "review",
    ) -> IdentityAnchorPackVersion:
        owner_project_id = project_id or pack.root_source_provenance.project_id
        self._load_project(owner_project_id)
        saved = super().save_pack(pack, project_id=project_id, event_type=event_type)
        self._write_project(owner_project_id)
        return saved

    def get(self, project_id: str, people_asset_id: str) -> PeopleAsset | None:
        self._load_project(project_id)
        return super().get(project_id, people_asset_id)

    def list_assets(self, project_id: str) -> list[PeopleAsset]:
        self._load_project(project_id)
        return super().list_assets(project_id)

    def list_history(self, project_id: str, people_asset_id: str) -> list[PeopleAssetRevision]:
        self._load_project(project_id)
        return super().list_history(project_id, people_asset_id)

    def get_pack(self, project_id: str, people_asset_id: str, pack_version_id: str) -> IdentityAnchorPackVersion | None:
        self._load_project(project_id)
        return super().get_pack(project_id, people_asset_id, pack_version_id)

    def list_pack_history(self, project_id: str, people_asset_id: str) -> list[AnchorPackRevision]:
        self._load_project(project_id)
        return super().list_pack_history(project_id, people_asset_id)

    def _load_project(self, project_id: str) -> None:
        _validate_component(project_id, "project_id")
        if project_id in self._loaded_projects:
            return
        self._loaded_projects.add(project_id)
        assets_path, history_path, packs_path, pack_history_path = self._paths(project_id)
        if assets_path.exists():
            try:
                raw_assets = json.loads(assets_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw_assets = []
            if isinstance(raw_assets, list):
                for raw in raw_assets:
                    try:
                        asset = PeopleAsset.model_validate(raw)
                    except Exception:
                        continue
                    if asset.project_id == project_id:
                        self._assets[(project_id, asset.people_asset_id)] = asset
        if history_path.exists():
            try:
                raw_history = json.loads(history_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw_history = []
            if isinstance(raw_history, list):
                for raw in raw_history:
                    try:
                        revision = PeopleAssetRevision.model_validate(raw)
                    except Exception:
                        continue
                    if revision.project_id == project_id:
                        self._history.setdefault((project_id, revision.people_asset_id), []).append(revision)
        if packs_path.exists():
            try:
                raw_packs = json.loads(packs_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw_packs = []
            if isinstance(raw_packs, list):
                for raw in raw_packs:
                    try:
                        pack = IdentityAnchorPackVersion.model_validate(raw)
                    except Exception:
                        continue
                    if pack.root_source_provenance.project_id == project_id:
                        self._packs[(project_id, pack.people_asset_id, pack.pack_version_id)] = pack
        if pack_history_path.exists():
            try:
                raw_pack_history = json.loads(pack_history_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                raw_pack_history = []
            if isinstance(raw_pack_history, list):
                for raw in raw_pack_history:
                    try:
                        revision = AnchorPackRevision.model_validate(raw)
                    except Exception:
                        continue
                    if revision.project_id == project_id:
                        self._pack_history.setdefault((project_id, revision.people_asset_id), []).append(revision)

    def _write_project(self, project_id: str) -> None:
        assets_path, history_path, packs_path, pack_history_path = self._paths(project_id)
        assets_path.parent.mkdir(parents=True, exist_ok=True)
        assets = [
            asset.model_dump(mode="json")
            for (owner, _), asset in sorted(self._assets.items())
            if owner == project_id
        ]
        history = [
            revision.model_dump(mode="json")
            for (owner, _), entries in sorted(self._history.items())
            if owner == project_id
            for revision in entries
        ]
        _atomic_write_json(assets_path, assets)
        _atomic_write_json(history_path, history)
        packs = [
            pack.model_dump(mode="json")
            for (owner, _, _), pack in sorted(self._packs.items())
            if owner == project_id
        ]
        pack_history = [
            revision.model_dump(mode="json")
            for (owner, _), entries in sorted(self._pack_history.items())
            if owner == project_id
            for revision in entries
        ]
        _atomic_write_json(packs_path, packs)
        _atomic_write_json(pack_history_path, pack_history)

    def _paths(self, project_id: str) -> tuple[Path, Path, Path, Path]:
        _validate_component(project_id, "project_id")
        project_dir = self.storage_root / project_id
        return (
            project_dir / "people_assets.json",
            project_dir / "people_asset_history.json",
            project_dir / "identity_anchor_packs.json",
            project_dir / "identity_anchor_pack_history.json",
        )


def _validate_component(value: str, label: str) -> None:
    if not _SAFE_COMPONENT.fullmatch(str(value or "")):
        raise ValueError(f"invalid {label}")


def _atomic_write_json(path: Path, payload: object) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
