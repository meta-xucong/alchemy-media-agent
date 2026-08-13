"""V3-owned Project Mode stores."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil

from .contracts import ProjectRecord, ProjectTimelineItem


_PROJECT_ID_PATTERN = re.compile(r"^project_[A-Za-z0-9_-]{1,64}$")
_DOC270_PHASE4_PRIVATE_NAMESPACES = frozenset(
    {
        "doc270_phase4_activation_policy",
        "doc270_phase4_commands",
        "doc270_phase4_registry_entries",
        "doc270_phase4_resolution_decisions",
    }
)


class InMemoryProjectStore:
    """Deterministic store for Project Mode tests and local app sessions."""

    def __init__(self) -> None:
        self._projects: dict[str, ProjectRecord] = {}
        self._timeline: dict[str, list[ProjectTimelineItem]] = {}
        # Server-private append-only contracts, intentionally separate from
        # ProjectRecord.metadata so public project projections cannot expose
        # command identities, evidence, or frozen source bindings.
        self._private_records: dict[str, dict[str, list[dict[str, object]]]] = {}

    def save_project(self, project: ProjectRecord) -> ProjectRecord:
        self._projects[project.project_id] = project
        return project

    def get_project(self, project_id: str) -> ProjectRecord | None:
        return self._projects.get(project_id)

    def list_projects(self, limit: int = 20) -> list[ProjectRecord]:
        bounded_limit = max(1, min(int(limit or 20), 100))
        return sorted(self._projects.values(), key=lambda project: project.updated_at, reverse=True)[:bounded_limit]

    def append_timeline(self, item: ProjectTimelineItem) -> ProjectTimelineItem:
        self._timeline.setdefault(item.project_id, []).append(item)
        project = self._projects.get(item.project_id)
        if project is not None and item.timeline_item_id not in project.timeline_refs:
            project.timeline_refs.append(item.timeline_item_id)
            project.updated_at = item.created_at
            self.save_project(project)
        return item

    def list_timeline(self, project_id: str) -> list[ProjectTimelineItem]:
        return sorted(self._timeline.get(project_id, []), key=lambda item: item.created_at)

    def append_private_record(
        self,
        project_id: str,
        namespace: str,
        record: dict[str, object],
    ) -> dict[str, object]:
        if namespace not in _DOC270_PHASE4_PRIVATE_NAMESPACES:
            raise ValueError("private_record_namespace_invalid")
        candidate = _frozen_private_record(record)
        records = self._private_records.setdefault(project_id, {}).setdefault(namespace, [])
        identity_digest = str(candidate.get("identity_digest") or "").strip()
        if identity_digest:
            for existing in records:
                if str(existing.get("identity_digest") or "").strip() != identity_digest:
                    continue
                if existing != candidate:
                    raise ValueError("private_record_identity_conflict")
                return _frozen_private_record(existing)
        if candidate not in records:
            records.append(candidate)
            self._write_private_records(project_id)
        return _frozen_private_record(candidate)

    def list_private_records(self, project_id: str, namespace: str) -> list[dict[str, object]]:
        if namespace not in _DOC270_PHASE4_PRIVATE_NAMESPACES:
            raise ValueError("private_record_namespace_invalid")
        return [_frozen_private_record(item) for item in self._private_records.get(project_id, {}).get(namespace, [])]

    def delete_project(self, project_id: str) -> bool:
        project = self._projects.pop(project_id, None)
        timeline = self._timeline.pop(project_id, None)
        self._private_records.pop(project_id, None)
        return project is not None or timeline is not None

    def _write_private_records(self, project_id: str) -> None:
        """In-memory stores have no durable private-record backing."""


class PersistentProjectStore(InMemoryProjectStore):
    """Persistent local project store for the V3 project-first workflow."""

    def __init__(self, storage_root: str | Path | None = None) -> None:
        super().__init__()
        self.storage_root = Path(storage_root) if storage_root else _default_storage_root()

    def save_project(self, project: ProjectRecord) -> ProjectRecord:
        super().save_project(project)
        self._write_project(project)
        return project

    def get_project(self, project_id: str) -> ProjectRecord | None:
        cached = super().get_project(project_id)
        if cached is not None:
            return cached
        loaded = self._read_project(project_id)
        if loaded is None:
            return None
        self._projects[loaded.project_id] = loaded
        return loaded

    def append_private_record(
        self,
        project_id: str,
        namespace: str,
        record: dict[str, object],
    ) -> dict[str, object]:
        self._load_private_records(project_id)
        return super().append_private_record(project_id, namespace, record)

    def list_private_records(self, project_id: str, namespace: str) -> list[dict[str, object]]:
        self._load_private_records(project_id)
        return super().list_private_records(project_id, namespace)

    def list_projects(self, limit: int = 20) -> list[ProjectRecord]:
        self._load_all_projects()
        return super().list_projects(limit)

    def append_timeline(self, item: ProjectTimelineItem) -> ProjectTimelineItem:
        self._load_timeline(item.project_id)
        existing_ids = {entry.timeline_item_id for entry in self._timeline.get(item.project_id, [])}
        if item.timeline_item_id not in existing_ids:
            self._timeline.setdefault(item.project_id, []).append(item)
            self._write_timeline(item.project_id)
        project = self.get_project(item.project_id)
        if project is not None and item.timeline_item_id not in project.timeline_refs:
            project.timeline_refs.append(item.timeline_item_id)
            project.updated_at = item.created_at
            self.save_project(project)
        return item

    def list_timeline(self, project_id: str) -> list[ProjectTimelineItem]:
        self._load_timeline(project_id)
        return super().list_timeline(project_id)

    def delete_project(self, project_id: str) -> bool:
        if not _valid_project_id(project_id):
            return False
        removed = super().delete_project(project_id)
        project_dir = self.storage_root / project_id
        if project_dir.exists():
            _safe_remove_tree(self.storage_root, project_dir)
            removed = True
        return removed

    def _load_all_projects(self) -> None:
        if not self.storage_root.exists():
            return
        for path in self.storage_root.glob("project_*/project.json"):
            project = self._read_project(path.parent.name)
            if project is not None:
                self._projects[project.project_id] = project

    def _load_timeline(self, project_id: str) -> None:
        if project_id in self._timeline:
            return
        self._timeline[project_id] = self._read_timeline(project_id)

    def _load_private_records(self, project_id: str) -> None:
        if project_id in self._private_records:
            return
        path = self._private_records_path(project_id)
        if not path.exists():
            self._private_records[project_id] = {}
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            self._private_records[project_id] = {}
            return
        if not isinstance(payload, dict):
            self._private_records[project_id] = {}
            return
        sanitized: dict[str, list[dict[str, object]]] = {}
        for namespace, records in payload.items():
            if namespace not in _DOC270_PHASE4_PRIVATE_NAMESPACES or not isinstance(records, list):
                continue
            try:
                sanitized[namespace] = [_frozen_private_record(item) for item in records]
            except ValueError:
                continue
        self._private_records[project_id] = sanitized

    def _read_project(self, project_id: str) -> ProjectRecord | None:
        if not _valid_project_id(project_id):
            return None
        path = self._project_path(project_id)
        if not path.exists():
            return None
        try:
            return ProjectRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _read_timeline(self, project_id: str) -> list[ProjectTimelineItem]:
        if not _valid_project_id(project_id):
            return []
        path = self._timeline_path(project_id)
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        items: list[ProjectTimelineItem] = []
        for item in data:
            try:
                items.append(ProjectTimelineItem.model_validate(item))
            except Exception:
                continue
        return sorted(items, key=lambda entry: entry.created_at)

    def _write_project(self, project: ProjectRecord) -> None:
        path = self._project_path(project.project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(path, project.model_dump(mode="json"))

    def _write_timeline(self, project_id: str) -> None:
        path = self._timeline_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.model_dump(mode="json") for item in self._timeline.get(project_id, [])]
        _atomic_write_json(path, payload)

    def _write_private_records(self, project_id: str) -> None:
        self._load_private_records(project_id)
        path = self._private_records_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            namespace: [_frozen_private_record(item) for item in records]
            for namespace, records in self._private_records.get(project_id, {}).items()
            if namespace in _DOC270_PHASE4_PRIVATE_NAMESPACES
        }
        _atomic_write_json(path, payload)

    def _project_path(self, project_id: str) -> Path:
        return self.storage_root / project_id / "project.json"

    def _timeline_path(self, project_id: str) -> Path:
        return self.storage_root / project_id / "timeline.json"

    def _private_records_path(self, project_id: str) -> Path:
        return self.storage_root / project_id / "private_records.json"


def _atomic_write_json(path: Path, payload: object) -> None:
    temp = path.with_suffix(f"{path.suffix}.tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _frozen_private_record(value: object) -> dict[str, object]:
    """Validate JSON-only records and break all caller-owned references."""

    if not isinstance(value, dict):
        raise ValueError("private_record_invalid")
    try:
        serialized = json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        copied = json.loads(serialized)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("private_record_invalid") from exc
    if not isinstance(copied, dict):
        raise ValueError("private_record_invalid")
    return copied


def _valid_project_id(project_id: str) -> bool:
    return bool(_PROJECT_ID_PATTERN.match(str(project_id or "")))


def _safe_remove_tree(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved == root_resolved or root_resolved not in target_resolved.parents:
        raise ValueError("Refusing to delete outside the V3 project storage root.")
    if target_resolved.exists():
        shutil.rmtree(target_resolved)


def _default_storage_root() -> Path:
    configured = os.getenv("ALCHEMY_V3_PROJECT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / ".media_storage" / "v3_projects"
