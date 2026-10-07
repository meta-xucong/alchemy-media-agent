"""V3-owned Project Mode stores."""

from __future__ import annotations

import json
import heapq
from contextlib import contextmanager
from threading import RLock
import time
from uuid import uuid4
import os
from pathlib import Path
import re
import shutil
from weakref import WeakValueDictionary

from .contracts import ProjectRecord, ProjectTimelineItem


_PROJECT_ID_PATTERN = re.compile(r"^project_[A-Za-z0-9_-]{1,64}$")
_PROJECT_HEADER_CACHE_MAX_ENTRIES = 4096
_DOC270_PHASE4_PRIVATE_NAMESPACES = frozenset(
    {
        "doc270_phase4_activation_policy",
        "doc270_phase4_commands",
        "doc270_phase4_registry_entries",
        "doc270_phase4_resolution_decisions",
        "doc277_project_planning_operations",
        "doc279_ecommerce_transparent_predecessor_receipts",
        "doc281_source_association_terminal_receipts_v1",
        "doc281_general_commands_v1",
        "doc281_general_selection_receipts_v2",
        "doc281_general_requirements_v1",
        "doc281_source_evidence_observations_v1",
        "doc281_general_resolution_receipts_v1",
        "doc73_auto_identity_anchor_controls_v1",
        "doc322_continuity_anchor_bindings_v1",
    }
)


class InMemoryProjectStore:
    """Deterministic store for Project Mode tests and local app sessions."""

    def __init__(self) -> None:
        self._private_lock = RLock()
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

    def list_all_projects(self) -> list[ProjectRecord]:
        """Return every project for server-owned maintenance recovery only."""

        return sorted(self._projects.values(), key=lambda project: project.updated_at, reverse=True)

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

    def compare_and_append_private_record(self, project_id: str, namespace: str, record: dict, *, expected_version: int) -> dict:
        with self._private_lock:
            return self._append_private_version(project_id, namespace, record, expected_version)

    def _append_private_version(self, project_id: str, namespace: str, record: dict, expected_version: int) -> dict:
        records = self._private_records.get(project_id, {}).get(namespace, [])
        if type(expected_version) is not int or len(records) != expected_version or record.get("version") != expected_version + 1:
            raise ValueError("continuity_anchor_conflict")
        return InMemoryProjectStore.append_private_record(self, project_id, namespace, record)

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
        # The cache must preserve identity while a caller is actively using a
        # mutable ProjectRecord, but must not keep historical projects alive
        # after the request releases them.
        self._projects = WeakValueDictionary()
        self.storage_root = Path(storage_root) if storage_root else _default_storage_root()
        self._project_revisions: dict[str, tuple[int, int, int]] = {}
        self._project_header_cache: dict[str, tuple[tuple[int, int, int], dict[str, object]]] = {}
        self._timeline_lock = RLock()

    def save_project(self, project: ProjectRecord) -> ProjectRecord:
        saved = super().save_project(project)
        self._write_project(saved)
        revision = self._project_revision(self._project_path(saved.project_id))
        if revision is not None:
            self._cache_project(saved, revision)
        else:
            self._evict_project(saved.project_id)
        return saved

    def get_project(self, project_id: str) -> ProjectRecord | None:
        cached = super().get_project(project_id)
        revision = self._project_revision(self._project_path(project_id))
        if cached is not None and revision is not None and self._project_revisions.get(project_id) == revision:
            return cached
        if revision is None:
            self._evict_project(project_id)
            return None
        loaded = self._read_project(project_id)
        if loaded is None:
            self._evict_project(project_id)
            return None
        self._cache_project(loaded, revision)
        return loaded

    def list_project_headers(self) -> list[dict[str, object]]:
        return list(self.iter_project_headers())

    def iter_project_headers(self):
        """Read only the fields needed to sort and authorize project pages.

        Project JSON can contain large append-only workflow evidence. Listing
        projects must not deserialize and retain that history for every row.
        One file is scanned through a fixed-size buffer; full ProjectRecords
        are loaded only for the requested page by the service layer.
        """

        if not self.storage_root.exists():
            self._project_header_cache.clear()
            return
        for path in self.storage_root.glob("project_*/project.json"):
            project_id = path.parent.name
            if not _valid_project_id(project_id):
                continue
            revision = self._project_revision(path)
            cached = self._project_header_cache.get(project_id)
            if revision is not None and cached is not None and cached[0] == revision:
                self._project_header_cache.pop(project_id, None)
                self._project_header_cache[project_id] = cached
                yield cached[1]
                continue
            try:
                header = _read_project_header_json(path, project_id)
            except (OSError, json.JSONDecodeError, UnicodeError, ValueError):
                self._project_header_cache.pop(project_id, None)
                continue
            refreshed_revision = self._project_revision(path)
            if revision is None or refreshed_revision != revision:
                self._project_header_cache.pop(project_id, None)
                continue
            self._project_header_cache[project_id] = (revision, header)
            while len(self._project_header_cache) > _PROJECT_HEADER_CACHE_MAX_ENTRIES:
                self._project_header_cache.pop(next(iter(self._project_header_cache)))
            yield header
        for project_id, (cached_revision, _) in list(self._project_header_cache.items()):
            if self._project_revision(self._project_path(project_id)) != cached_revision:
                self._project_header_cache.pop(project_id, None)

    def _cache_project(self, project: ProjectRecord, revision: tuple[int, int, int]) -> None:
        project_id = project.project_id
        self._projects[project_id] = project
        self._project_revisions[project_id] = revision
        self._prune_project_revisions()

    def _evict_project(self, project_id: str) -> None:
        self._projects.pop(project_id, None)
        self._project_revisions.pop(project_id, None)

    def _prune_project_revisions(self) -> None:
        for project_id in set(self._project_revisions) - set(self._projects):
            self._project_revisions.pop(project_id, None)

    def append_private_record(
        self,
        project_id: str,
        namespace: str,
        record: dict[str, object],
    ) -> dict[str, object]:
        with self._private_transaction(project_id):
            return super().append_private_record(project_id, namespace, record)

    def list_private_records(self, project_id: str, namespace: str) -> list[dict[str, object]]:
        with self._private_transaction(project_id):
            return super().list_private_records(project_id, namespace)

    def compare_and_append_private_record(self, project_id: str, namespace: str, record: dict, *, expected_version: int) -> dict:
        with self._private_transaction(project_id):
            return self._append_private_version(project_id, namespace, record, expected_version)

    @contextmanager
    def _private_transaction(self, project_id: str):
        # All private appends share this lock so unrelated stale caches cannot
        # overwrite an anchor event. No new registry or storage service.
        if not _valid_project_id(project_id):
            raise ValueError("private_record_project_invalid")
        path = self.storage_root / project_id / ".private-records.lock"
        with self._private_lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a+b") as handle:
                if path.stat().st_size == 0:
                    handle.write(b"0"); handle.flush()
                if os.name == "nt":
                    import msvcrt
                    deadline = time.monotonic() + 10
                    while True:
                        try:
                            handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError:
                            if time.monotonic() >= deadline:
                                raise ValueError("continuity_anchor_busy")
                            time.sleep(0.01)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
                try:
                    self._private_records.pop(project_id, None)
                    self._load_private_records(project_id)
                    yield
                finally:
                    self._private_records.pop(project_id, None)
                    if os.name == "nt":
                        handle.seek(0); msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


    def list_projects(self, limit: int = 20) -> list[ProjectRecord]:
        bounded_limit = max(1, min(int(limit or 20), 100))
        candidates: list[tuple[tuple[str, int], dict[str, object]]] = []
        for ordinal, header in enumerate(self.iter_project_headers()):
            key = (str(header.get("updated_at") or ""), -ordinal)
            entry = (key, header)
            if len(candidates) < bounded_limit:
                heapq.heappush(candidates, entry)
            elif key > candidates[0][0]:
                heapq.heapreplace(candidates, entry)
        projects: list[ProjectRecord] = []
        for _, header in sorted(candidates, reverse=True):
            project = self.get_project(str(header.get("project_id") or ""))
            if project is not None:
                projects.append(project)
        return projects

    def iter_all_projects(self):
        """Yield complete catalog records one at a time for maintenance work."""

        if not self.storage_root.exists():
            for project_id in list(self._project_revisions):
                self._evict_project(project_id)
            return
        seen: set[str] = set()
        for path in self.storage_root.glob("project_*/project.json"):
            project_id = path.parent.name
            if not _valid_project_id(project_id):
                continue
            seen.add(project_id)
            revision = self._project_revision(path)
            cached = self._projects.get(project_id)
            if cached is not None and revision is not None and self._project_revisions.get(project_id) == revision:
                yield cached
                continue
            if revision is None:
                self._evict_project(project_id)
                continue
            project = self._read_project(project_id)
            if project is not None:
                self._cache_project(project, revision)
                yield project
            else:
                self._evict_project(project_id)
        for project_id in set(self._project_revisions) - seen:
            self._evict_project(project_id)

    def list_all_projects(self) -> list[ProjectRecord]:
        return sorted(
            list(self.iter_all_projects()),
            key=lambda project: project.updated_at,
            reverse=True,
        )

    def append_timeline(self, item: ProjectTimelineItem) -> ProjectTimelineItem:
        with self._timeline_lock:
            items = self._read_timeline(item.project_id)
            existing_ids = {entry.timeline_item_id for entry in items}
            if item.timeline_item_id not in existing_ids:
                items.append(item)
                self._write_timeline_items(item.project_id, items)
            project = self.get_project(item.project_id)
            if project is not None and item.timeline_item_id not in project.timeline_refs:
                project.timeline_refs.append(item.timeline_item_id)
                project.updated_at = item.created_at
                self.save_project(project)
        return item

    def list_timeline(self, project_id: str) -> list[ProjectTimelineItem]:
        return self._read_timeline(project_id)

    def delete_project(self, project_id: str) -> bool:
        if not _valid_project_id(project_id):
            return False
        removed = super().delete_project(project_id)
        self._evict_project(project_id)
        project_dir = self.storage_root / project_id
        if project_dir.exists():
            _safe_remove_tree(self.storage_root, project_dir)
            removed = True
        return removed

    def _load_all_projects(self) -> list[ProjectRecord]:
        return list(self.iter_all_projects())

    @staticmethod
    def _project_revision(path: Path) -> tuple[int, int, int] | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), int(stat.st_ctime_ns), int(stat.st_size)

    def _load_private_records(self, project_id: str) -> None:
        if project_id in self._private_records:
            return
        path = self._private_records_path(project_id)
        if not path.exists():
            self._private_records[project_id] = {}
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ValueError("private_record_store_invalid") from exc
        if not isinstance(payload, dict):
            raise ValueError("private_record_store_invalid")
        sanitized: dict[str, list[dict[str, object]]] = {}
        for namespace, records in payload.items():
            if namespace == "doc322_continuity_anchor_bindings_v1" and not isinstance(records, list):
                raise ValueError("continuity_anchor_history_invalid")
            if namespace not in _DOC270_PHASE4_PRIVATE_NAMESPACES or not isinstance(records, list):
                continue
            try:
                sanitized[namespace] = [_frozen_private_record(item) for item in records]
            except ValueError:
                if namespace == "doc322_continuity_anchor_bindings_v1":
                    raise
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

    def _write_timeline_items(self, project_id: str, items: list[ProjectTimelineItem]) -> None:
        path = self._timeline_path(project_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [item.model_dump(mode="json") for item in items]
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
    temp = path.with_suffix(f"{path.suffix}.{uuid4().hex}.tmp")
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


class _JsonStreamReader:
    """Small-buffer JSON scanner that skips large nested values without copying them."""

    _CHUNK_SIZE = 64 * 1024
    _MAX_CAPTURED_STRING_CHARS = 4096
    _MAX_NESTING = 256

    def __init__(self, handle) -> None:
        self.handle = handle
        self.buffer = ""
        self.offset = 0

    def _peek(self) -> str:
        if self.offset >= len(self.buffer):
            self.buffer = self.handle.read(self._CHUNK_SIZE)
            self.offset = 0
        return self.buffer[self.offset] if self.offset < len(self.buffer) else ""

    def _read(self) -> str:
        character = self._peek()
        if character:
            self.offset += 1
        return character

    def _skip_whitespace(self) -> None:
        while self._peek() in {" ", "\t", "\r", "\n"}:
            self._read()

    def _expect(self, expected: str, error: str) -> None:
        self._skip_whitespace()
        if self._read() != expected:
            raise ValueError(error)

    def _read_string(self, *, capture: bool) -> str | None:
        if self._read() != '"':
            raise ValueError("project_json_string_expected")
        raw: list[str] | None = [] if capture else None
        escaped = False
        while True:
            character = self._read()
            if not character:
                raise ValueError("project_json_string_truncated")
            if raw is not None and len(raw) <= self._MAX_CAPTURED_STRING_CHARS:
                raw.append(character)
            if escaped:
                if character not in '"\\/bfnrtu':
                    raise ValueError("project_json_escape_invalid")
                if character == "u":
                    digits = "".join(self._read() for _ in range(4))
                    if len(digits) != 4 or any(digit not in "0123456789abcdefABCDEF" for digit in digits):
                        raise ValueError("project_json_unicode_escape_invalid")
                    if raw is not None and len(raw) <= self._MAX_CAPTURED_STRING_CHARS:
                        raw.append(digits)
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                break
            elif ord(character) < 0x20:
                raise ValueError("project_json_control_character_invalid")
            if raw is not None and len(raw) > self._MAX_CAPTURED_STRING_CHARS:
                raw = None
        if raw is None:
            return None
        return json.loads('"' + "".join(raw[:-1]) + '"')

    def _read_scalar(self) -> object:
        self._skip_whitespace()
        character = self._peek()
        if character == '"':
            return self._read_string(capture=True)
        if character in {"[", "{"}:
            self._skip_value()
            return None
        raw: list[str] = []
        while (character := self._peek()) and character not in ",}] \t\r\n":
            raw.append(self._read())
            if len(raw) > 128:
                raise ValueError("project_json_scalar_too_large")
        if not raw:
            raise ValueError("project_json_primitive_invalid")
        return json.loads("".join(raw))

    def _skip_string(self) -> None:
        self._read_string(capture=False)

    def _skip_value(self, depth: int = 0) -> None:
        self._skip_whitespace()
        character = self._peek()
        if not character:
            raise ValueError("project_json_value_missing")
        if character == '"':
            self._skip_string()
            return
        if character in "[{":
            if depth >= self._MAX_NESTING:
                raise ValueError("project_json_nesting_limit")
            if self._read() == "{":
                self._skip_whitespace()
                if self._peek() == "}":
                    self._read()
                    return
                while True:
                    self._skip_whitespace()
                    if self._peek() != '"':
                        raise ValueError("project_json_object_key_invalid")
                    self._read_string(capture=False)
                    self._expect(":", "project_json_object_separator_invalid")
                    self._skip_value(depth + 1)
                    self._skip_whitespace()
                    delimiter = self._read()
                    if delimiter == "}":
                        return
                    if delimiter != ",":
                        raise ValueError("project_json_object_terminator_invalid")
            else:
                self._skip_whitespace()
                if self._peek() == "]":
                    self._read()
                    return
                while True:
                    self._skip_value(depth + 1)
                    self._skip_whitespace()
                    delimiter = self._read()
                    if delimiter == "]":
                        return
                    if delimiter != ",":
                        raise ValueError("project_json_array_terminator_invalid")
            return
        if character in ",}]":
            raise ValueError("project_json_value_missing")
        primitive: list[str] = []
        while (character := self._peek()) and character not in ",}] \t\r\n":
            primitive.append(self._read())
            if len(primitive) > 128:
                raise ValueError("project_json_primitive_invalid")
        if "".join(primitive) not in {"true", "false", "null"} and not re.fullmatch(
            r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?",
            "".join(primitive),
        ):
            raise ValueError("project_json_primitive_invalid")

    def _read_object_member(self, wanted_key: str) -> object:
        self._skip_whitespace()
        if self._peek() != "{":
            self._skip_value()
            return None
        self._read()
        found: object = None
        while True:
            self._skip_whitespace()
            if self._peek() == "}":
                self._read()
                return found
            key = self._read_string(capture=True)
            self._expect(":", "project_metadata_separator_invalid")
            if key == wanted_key:
                found = self._read_scalar()
            else:
                self._skip_value()
            self._skip_whitespace()
            delimiter = self._read()
            if delimiter == "}":
                return found
            if delimiter == ",":
                self._skip_whitespace()
                if self._peek() == "}":
                    raise ValueError("project_metadata_trailing_comma")
                continue
            else:
                raise ValueError("project_metadata_terminator_invalid")


def _read_project_header_json(path: Path, project_id: str) -> dict[str, object]:
    """Stream catalog fields while skipping large append-only JSON subtrees."""

    selected: dict[str, object] = {}
    owner_user_id: object = None
    with path.open("r", encoding="utf-8") as handle:
        reader = _JsonStreamReader(handle)
        reader._expect("{", "project_record_not_object")
        while True:
            reader._skip_whitespace()
            if reader._peek() == "}":
                reader._read()
                break
            key = reader._read_string(capture=True)
            reader._expect(":", "project_record_separator_invalid")
            if key == "metadata":
                owner_user_id = reader._read_object_member("veyra_user_id")
            elif key in {"status", "created_at", "updated_at"}:
                selected[key] = reader._read_scalar()
            else:
                reader._skip_value()
            reader._skip_whitespace()
            delimiter = reader._read()
            if delimiter == "}":
                break
            if delimiter == ",":
                reader._skip_whitespace()
                if reader._peek() == "}":
                    raise ValueError("project_record_trailing_comma")
                continue
            else:
                raise ValueError("project_record_terminator_invalid")
        reader._skip_whitespace()
        if reader._peek():
            raise ValueError("project_record_trailing_data")
    return {
        "project_id": project_id,
        "status": str(selected.get("status") or "active"),
        "created_at": str(selected.get("created_at") or ""),
        "updated_at": str(selected.get("updated_at") or ""),
        "owner_user_id": owner_user_id,
    }


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
