"""V3-owned generated image output storage."""

from __future__ import annotations

import base64
from collections import OrderedDict
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import heapq
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import threading
from typing import Any, Iterable
from uuid import uuid4

from ..creative_core.doc281_output_plan_binding import (
    finalize_doc73_auto_identity_anchor_binding,
    validate_doc73_binding,
)


_OUTPUT_ID_PATTERN = re.compile(r"^v3_output_[a-f0-9]{20}$")
_FORMAT_SUFFIXES = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp"}
_MIME_FORMATS = {"image/png": "png", "image/jpeg": "jpeg", "image/jpg": "jpeg", "image/webp": "webp"}
_IMMUTABLE_OUTPUT_METADATA_KEYS = frozenset({"content_sha256", "source_integrity_id"})
_CLOSURE_BOUND_OUTPUT_METADATA_KEYS = frozenset({"capability_execution_envelope", "output_index"})
_OUTPUT_RECORD_CACHE_MAX_ENTRIES = 128
_OUTPUT_VALIDATION_CACHE_MAX_ENTRIES = 256
_OUTPUT_SCOPED_INDEX_MAX_RECORDS = 4096
_OUTPUT_LIST_MAX_ENTRIES = 10000
_OUTPUT_PROJECT_LIST_MAX_ENTRIES = 4097
_SCOPED_INDEX_FIELD_PATTERN = re.compile(
    rb'"(?P<field>job_id|project_id)"\s*:\s*"(?P<value>(?:[^"\\]|\\.)*)"'
)


@dataclass(frozen=True)
class V3GeneratedOutputRecord:
    output_id: str
    job_id: str
    candidate_id: str
    asset_id: str
    provider: str
    model: str | None = None
    mime_type: str = "image/png"
    output_format: str = "png"
    width: int | None = None
    height: int | None = None
    file_path: str = ""
    preview_path: str = ""
    thumbnail_path: str = ""
    download_url: str = ""
    preview_url: str = ""
    thumbnail_url: str = ""
    created_at: str = ""
    metadata: dict = field(default_factory=dict)

    def to_json_dict(self) -> dict:
        return asdict(self)


class V3GeneratedOutputStore:
    """Persistent local store for V3-generated image files only."""

    def __init__(self, storage_root: str | Path | None = None) -> None:
        self.storage_root = Path(storage_root) if storage_root else _default_storage_root()
        self._cache_lock = threading.RLock()
        # Includes the per-file signature so out-of-band output.json edits
        # invalidate the byte-scan locator even when the root directory mtime
        # is unchanged.
        self._scoped_index_revision: tuple[Any, Any] | None = None
        self._scoped_paths_by_job: dict[str, tuple[Path, ...]] | None = None
        self._scoped_paths_by_project: dict[str, tuple[Path, ...]] | None = None
        self._scoped_records_by_id_cache: OrderedDict[str, V3GeneratedOutputRecord] = OrderedDict()
        self._record_file_revisions: OrderedDict[str, tuple[int, int, int]] = OrderedDict()
        self._integrity_validation_cache: OrderedDict[
            str, tuple[tuple[int, int, int], str | None, bool]
        ] = OrderedDict()
        self._image_validation_cache: OrderedDict[str, tuple[tuple[int, int, int], bool]] = OrderedDict()

    def save_base64_output(
        self,
        *,
        job_id: str,
        candidate_id: str,
        asset_id: str,
        provider: str,
        model: str | None,
        encoded_image: str,
        output_id: str | None = None,
        mime_type: str | None = None,
        output_format: str | None = None,
        width: int | None = None,
        height: int | None = None,
        metadata: dict | None = None,
    ) -> V3GeneratedOutputRecord:
        fmt = _normalise_format(output_format, mime_type)
        mime = _normalise_mime(mime_type, fmt)
        content = _decode_image(encoded_image)
        actual_width, actual_height = _validate_image(content)
        source_dimensions = (actual_width, actual_height)
        content, normalized_dimensions = _normalize_requested_aspect_ratio(
            content,
            image_format=fmt,
            metadata=metadata or {},
            source_dimensions=(actual_width, actual_height),
        )
        if normalized_dimensions is not None:
            actual_width, actual_height = normalized_dimensions
        content_sha256 = hashlib.sha256(content).hexdigest()
        width = width or actual_width
        height = height or actual_height
        if normalized_dimensions is not None:
            width, height = normalized_dimensions
        output_id = str(output_id or "").strip() or f"v3_output_{uuid4().hex[:20]}"
        if not _valid_output_id(output_id):
            raise ValueError("refusing to persist an invalid V3 output id")

        existing = self.get_output(output_id)
        if existing is not None:
            if (
                existing.job_id != job_id
                or existing.candidate_id != candidate_id
                or existing.asset_id != asset_id
            ):
                raise ValueError("existing V3 output checkpoint belongs to another candidate")
            existing_sha = str((existing.metadata or {}).get("content_sha256") or "")
            if existing_sha and existing_sha != content_sha256:
                raise ValueError("existing V3 output checkpoint content changed")
            return existing

        output_dir = self.storage_root / output_id
        output_dir.mkdir(parents=True, exist_ok=True)
        original_path = output_dir / f"original{_FORMAT_SUFFIXES.get(fmt, '.png')}"
        original_path.write_bytes(content)
        preview_path = output_dir / "preview.png"
        thumbnail_path = output_dir / "thumbnail.png"
        _write_resized_png(content, preview_path, max_side=1600)
        _write_resized_png(content, thumbnail_path, max_side=512)

        stored_metadata = _doc281_bind_output_record_metadata(dict(metadata or {}), output_id=output_id)
        stored_metadata = finalize_doc73_auto_identity_anchor_binding(
            stored_metadata,
            job_id=job_id,
            project_id=str(stored_metadata.get("project_id") or "").strip(),
            candidate_id=candidate_id,
            asset_id=asset_id,
            output_id=output_id,
            content_sha256=content_sha256,
        )
        source_binding = stored_metadata.get("doc73_auto_identity_anchor_binding")
        if _is_doc73_source_binding(source_binding) and not self.claim_doc73_auto_identity_anchor(source_binding):
            stored_metadata.pop("doc73_auto_identity_anchor_binding", None)
        if normalized_dimensions is not None:
            stored_metadata["aspect_ratio_normalization"] = "server_crop_to_explicit_user_ratio"
            stored_metadata["aspect_ratio_source_dimensions"] = {
                "width": int(source_dimensions[0] or 0),
                "height": int(source_dimensions[1] or 0),
            }
            stored_metadata["aspect_ratio_actual_dimensions"] = {
                "width": int(width or 0),
                "height": int(height or 0),
            }
        record = V3GeneratedOutputRecord(
            output_id=output_id,
            job_id=job_id,
            candidate_id=candidate_id,
            asset_id=asset_id,
            provider=provider,
            model=model,
            mime_type=mime,
            output_format=fmt,
            width=width,
            height=height,
            file_path=str(original_path),
            preview_path=str(preview_path),
            thumbnail_path=str(thumbnail_path),
            download_url=download_route(output_id),
            preview_url=preview_route(output_id),
            thumbnail_url=thumbnail_route(output_id),
            created_at=_now_iso(),
            metadata={
                **stored_metadata,
                "v3_owned_output": True,
                "content_sha256": content_sha256,
                # New records publish both names for one canonical integrity
                # fact; older readers may still provide either one.
                "source_integrity_id": f"sha256:{content_sha256}",
            },
        )
        self._write_record(record)
        self._invalidate_cache()
        return record

    def get_output(self, output_id: str) -> V3GeneratedOutputRecord | None:
        if not _valid_output_id(output_id):
            return None
        path = self._record_path(output_id)
        file_revision = self._record_file_revision(path)
        with self._cache_lock:
            cached_record = self._scoped_records_by_id_cache.get(output_id)
            if (
                cached_record is not None
                and file_revision is not None
                and self._record_file_revisions.get(output_id) == file_revision
            ):
                self._scoped_records_by_id_cache.move_to_end(output_id)
                self._record_file_revisions.move_to_end(output_id)
                return cached_record
            self._scoped_records_by_id_cache.pop(output_id, None)
            self._record_file_revisions.pop(output_id, None)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            record = V3GeneratedOutputRecord(**data)
        except Exception:
            with self._cache_lock:
                self._scoped_records_by_id_cache.pop(output_id, None)
                self._record_file_revisions.pop(output_id, None)
            return None
        with self._cache_lock:
            if file_revision is not None:
                _bounded_cache_set(
                    self._scoped_records_by_id_cache,
                    output_id,
                    record,
                    _OUTPUT_RECORD_CACHE_MAX_ENTRIES,
                )
                _bounded_cache_set(
                    self._record_file_revisions,
                    output_id,
                    file_revision,
                    _OUTPUT_RECORD_CACHE_MAX_ENTRIES,
                )
        return record

    def claim_doc73_auto_identity_anchor(self, binding: dict) -> bool:
        """Atomically keep the first valid source binding for one Job."""

        if not _is_doc73_source_binding(binding):
            return False
        job_id = str(binding.get("job_id") or "").strip()
        project_id = str(binding.get("project_id") or "").strip()
        output_id = str(binding.get("source_output_id") or "").strip()
        if not job_id or not project_id or not validate_doc73_binding(
            binding,
            expected_job_id=job_id,
            expected_project_id=project_id,
            expected_output_id=output_id,
            expected_source_asset_id=str(binding.get("source_asset_id") or "").strip(),
            expected_source_plan_position=0,
            expected_source_candidate_id=str(binding.get("source_candidate_id") or "").strip(),
        ):
            return False
        receipt_path = self._doc73_anchor_receipt_path(job_id)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(dict(binding), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        try:
            descriptor = os.open(
                receipt_path,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            )
        except FileExistsError:
            return self.get_doc73_auto_identity_anchor_receipt(job_id) == dict(binding)
        except OSError:
            return False
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        except OSError:
            try:
                receipt_path.unlink()
            except OSError:
                pass
            return False
        return True

    def get_doc73_auto_identity_anchor_receipt(self, job_id: str) -> dict | None:
        """Read the immutable source receipt used by retry/replay paths."""

        path = self._doc73_anchor_receipt_path(job_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return dict(data) if isinstance(data, dict) else None

    def list_outputs(self, limit: int = 100) -> list[V3GeneratedOutputRecord]:
        bounded_limit = _bounded_output_limit(limit, default=100)
        return self._read_records_cached(bounded_limit)

    def list_by_job(self, job_id: str, limit: int | None = None) -> list[V3GeneratedOutputRecord]:
        target = str(job_id or "").strip()
        if not target:
            return []
        scoped_limit = None if limit is None else _bounded_output_limit(limit, default=1)
        paths = self._scoped_output_paths(field="job_id", target=target)
        records = self._read_scoped_records(paths, job_id=target, limit=scoped_limit)
        # An out-of-band edit can move an existing record to another job while
        # leaving the output directory revision unchanged. If the cached
        # candidate paths produced no exact match, rebuild the locator once so
        # the new authoritative job_id can be discovered. Normal repeated
        # reads use the bounded path index when the catalog is small enough.
        if not records:
            paths = self._scoped_output_paths(field="job_id", target=target, force_rescan=True)
            records = self._read_scoped_records(paths, job_id=target, limit=scoped_limit)
        return records

    def list_by_project(self, project_id: str, limit: int = 256) -> list[V3GeneratedOutputRecord]:
        target = str(project_id or "").strip()
        if not target:
            return []
        bounded_limit = _bounded_output_limit(
            limit, default=256, maximum=_OUTPUT_PROJECT_LIST_MAX_ENTRIES
        )
        paths = self._scoped_output_paths(field="project_id", target=target)
        records = self._read_scoped_records(paths, project_id=target, limit=bounded_limit)
        # Match list_by_job: an in-place output.json edit may change the
        # authoritative project_id without changing the directory revision.
        # Rebuild only when the cached candidates produce no exact match.
        if not records:
            paths = self._scoped_output_paths(
                field="project_id", target=target, force_rescan=True
            )
            records = self._read_scoped_records(paths, project_id=target, limit=bounded_limit)
        return records

    def file_for_variant(self, output_id: str, variant: str) -> tuple[Path, str, str] | None:
        record = self.get_output(output_id)
        if record is None:
            return None
        output_dir = (self.storage_root / output_id).resolve(strict=False)
        if not _path_is_within(self.storage_root, output_dir) or output_dir.name != record.output_id:
            return None
        if variant == "download":
            media_type = record.mime_type
            filename = f"{output_id}.{_extension(record.output_format)}"
            fallback_path = output_dir / f"original{_FORMAT_SUFFIXES.get(record.output_format, '.png')}"
        elif variant == "preview":
            media_type = "image/png"
            filename = f"{output_id}_preview.png"
            fallback_path = output_dir / "preview.png"
        elif variant == "thumbnail":
            media_type = "image/png"
            filename = f"{output_id}_thumbnail.png"
            fallback_path = output_dir / "thumbnail.png"
        else:
            return None
        # Record paths are historical metadata and may be stale or hostile.
        # Serve only the canonical output directory after validating the
        # original content binding; never follow an arbitrary persisted path.
        if not self._canonical_output_files_match_record_cached(record, output_dir):
            return None
        path = fallback_path
        if not _path_is_within(output_dir, path) or not path.exists() or not path.is_file():
            return None
        if not self._image_is_valid_cached(path):
            return None
        return path, media_type, filename

    def delete_output(self, output_id: str) -> bool:
        if not _valid_output_id(output_id):
            return False
        output_dir = self.storage_root / output_id
        if not output_dir.exists():
            self._invalidate_cache()
            return False
        _safe_remove_tree(self.storage_root, output_dir)
        self._mark_storage_mutation()
        self._invalidate_cache()
        return True

    def update_metadata(self, output_id: str, updates: dict) -> V3GeneratedOutputRecord | None:
        record = self.get_output(output_id)
        if record is None:
            return None
        existing_metadata = dict(record.metadata or {})
        incoming = dict(updates or {})
        for key in _IMMUTABLE_OUTPUT_METADATA_KEYS:
            if key in incoming and key in existing_metadata and incoming[key] != existing_metadata[key]:
                raise ValueError(f"output_metadata_immutable:{key}")
        closure = self.get_job_closure(record.job_id)
        if closure is not None:
            for key in _CLOSURE_BOUND_OUTPUT_METADATA_KEYS:
                if key in incoming and incoming[key] != existing_metadata.get(key):
                    raise ValueError(f"closed_output_metadata_immutable:{key}")
        updated = replace(record, metadata={**existing_metadata, **incoming})
        self._write_record(updated)
        self._invalidate_cache()
        return updated

    def save_job_closure(self, job_id: str, closure: dict[str, Any]) -> dict[str, Any]:
        """Persist one immutable, job-level output/review closure receipt.

        Output pixels and their per-output records are append-only.  The
        closure is written only after review and delivery projection finish,
        so restore can distinguish a complete job from a process crash between
        pixel persistence and lifecycle projection.
        """

        target_job_id = str(job_id or "").strip()
        if not target_job_id or not isinstance(closure, dict):
            raise ValueError("invalid_v3_output_job_closure")
        payload = dict(closure)
        if str(payload.get("job_id") or target_job_id).strip() != target_job_id:
            raise ValueError("v3_output_job_closure_job_mismatch")
        payload["job_id"] = target_job_id
        path = self._job_closure_path(target_job_id)
        existing = self.get_job_closure(target_job_id)
        if existing is not None:
            if existing != payload:
                raise ValueError("v3_output_job_closure_immutable")
            return existing
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        except FileExistsError:
            existing = self.get_job_closure(target_job_id)
            if existing == payload:
                return existing
            raise ValueError("v3_output_job_closure_immutable") from None
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            try:
                if path.exists() and self.get_job_closure(target_job_id) is None:
                    path.unlink()
            except OSError:
                pass
        self._mark_storage_mutation()
        return dict(payload)

    def get_job_closure(self, job_id: str) -> dict[str, Any] | None:
        """Read the immutable job-level closure receipt, if one exists."""

        target_job_id = str(job_id or "").strip()
        if not target_job_id:
            return None
        path = self._job_closure_path(target_job_id)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        if not isinstance(data, dict) or str(data.get("job_id") or "").strip() != target_job_id:
            return None
        return dict(data)

    def _write_record(self, record: V3GeneratedOutputRecord) -> None:
        path = self._record_path(record.output_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(record.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)
        self._mark_storage_mutation()

    def _mark_storage_mutation(self) -> None:
        """Advance the cheap cross-instance cache revision after a local write."""

        try:
            self.storage_root.touch(exist_ok=True)
        except OSError:
            # The write itself remains authoritative.  A later reader will
            # rebuild its cache if it cannot observe the directory revision.
            pass

    def _record_path(self, output_id: str) -> Path:
        return self.storage_root / output_id / "output.json"

    def _job_closure_path(self, job_id: str) -> Path:
        job_digest = hashlib.sha256(str(job_id or "").strip().encode("utf-8")).hexdigest()
        return self.storage_root / "_job_closures" / f"{job_digest}.json"

    def _doc73_anchor_receipt_path(self, job_id: str) -> Path:
        job_digest = hashlib.sha256(str(job_id or "").strip().encode("utf-8")).hexdigest()
        return self.storage_root / "_doc73_anchor_receipts" / f"{job_digest}.json"

    def _invalidate_cache(self) -> None:
        with self._cache_lock:
            self._scoped_index_revision = None
            self._scoped_paths_by_job = None
            self._scoped_paths_by_project = None
            self._scoped_records_by_id_cache.clear()
            self._record_file_revisions.clear()
            self._integrity_validation_cache.clear()
            self._image_validation_cache.clear()

    def _canonical_output_files_match_record_cached(
        self,
        record: V3GeneratedOutputRecord,
        output_dir: Path,
    ) -> bool:
        original_path = output_dir / f"original{_FORMAT_SUFFIXES.get(record.output_format, '.png')}"
        try:
            stat = original_path.stat()
        except OSError:
            return False
        fingerprint = (int(stat.st_mtime_ns), int(stat.st_ctime_ns), int(stat.st_size))
        expected_sha = _expected_output_content_sha256(record)
        key = str(record.output_id or "").strip()
        with self._cache_lock:
            cached = self._integrity_validation_cache.get(key)
            if cached is not None and cached[:2] == (fingerprint, expected_sha):
                self._integrity_validation_cache.move_to_end(key)
                return cached[2]
        valid = _canonical_output_files_match_record(record, output_dir)
        with self._cache_lock:
            _bounded_cache_set(
                self._integrity_validation_cache,
                key,
                (fingerprint, expected_sha, valid),
                _OUTPUT_VALIDATION_CACHE_MAX_ENTRIES,
            )
        return valid

    def _image_is_valid_cached(self, path: Path) -> bool:
        key = str(path)
        try:
            stat = path.stat()
        except OSError:
            return False
        fingerprint = (int(stat.st_mtime_ns), int(stat.st_ctime_ns), int(stat.st_size))
        with self._cache_lock:
            cached = self._image_validation_cache.get(key)
            if cached is not None and cached[0] == fingerprint:
                self._image_validation_cache.move_to_end(key)
                return cached[1]
        try:
            _validate_image(path.read_bytes())
        except (OSError, ValueError):
            valid = False
        else:
            valid = True
        with self._cache_lock:
            _bounded_cache_set(
                self._image_validation_cache,
                key,
                (fingerprint, valid),
                _OUTPUT_VALIDATION_CACHE_MAX_ENTRIES,
            )
        return valid

    def _storage_revision(self) -> tuple[int, int] | None:
        """Return a constant-time revision for the output directory.

        Earlier versions restatted every ``output.json`` on every lookup.  A
        project page can make dozens of lookups, so a long-lived local output
        store made that path scale with *all* historical images.  Writes made
        through this store update the root directory timestamp, which lets a
        separate process still discover new records without repeatedly
        traversing the full history.
        """

        try:
            stat = self.storage_root.stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), int(stat.st_ctime_ns)

    @staticmethod
    def _record_file_revision(path: Path) -> tuple[int, int, int] | None:
        """Return a cheap per-record revision for out-of-band edits.

        The output root revision only changes for writes performed through this
        store. A reviewer may read a record written by another process, or a
        repair tool may update one ``output.json`` in place. Checking this
        single file's metadata keeps the fast scoped cache while preventing a
        stale record from being used as review evidence.
        """

        try:
            stat = path.stat()
        except OSError:
            return None
        return int(stat.st_mtime_ns), int(stat.st_ctime_ns), int(stat.st_size)

    def _record_paths_signature(
        self,
    ) -> tuple[tuple[Path, ...], tuple[tuple[str, int, int, int], ...], bool]:
        paths: list[Path] = []
        signature_items: list[tuple[str, int, int, int]] = []
        for path in _iter_output_record_paths(self.storage_root):
            if len(paths) >= _OUTPUT_SCOPED_INDEX_MAX_RECORDS:
                # Keep only a fixed-size sample. Large catalogs use a second,
                # streaming query scan instead of building an O(N) index.
                return tuple(paths), (), True
            paths.append(path)
            try:
                stat = path.stat()
            except OSError:
                continue
            signature_items.append(
                (str(path), int(stat.st_mtime_ns), int(stat.st_ctime_ns), int(stat.st_size))
            )
        paths.sort()
        signature_items.sort()
        return tuple(paths), tuple(signature_items), False

    def _scoped_output_paths(
        self,
        *,
        field: str,
        target: str,
        force_rescan: bool = False,
    ) -> Iterable[Path]:
        """Locate scoped records without deserializing the full output history.

        Project pages normally need only a small subset of output records. A
        small catalog index is retained for speed; larger indexes are used only
        for the current request and are not kept by the store. Using a full
        deserialized history for every scoped lookup makes a cold process parse
        every large legacy ``output.json`` before it can answer one project.
        The byte scan below only builds candidate paths. Callers still load each
        candidate through ``get_output`` and exact-match its authoritative
        fields before returning it.
        """

        paths, signature, oversized = self._record_paths_signature()
        if oversized:
            with self._cache_lock:
                self._scoped_index_revision = None
                self._scoped_paths_by_job = None
                self._scoped_paths_by_project = None
            return self._iter_scoped_output_paths(field=field, target=target)

        storage_revision = self._storage_revision()
        revision = (storage_revision, signature)
        with self._cache_lock:
            if not force_rescan and (
                revision == self._scoped_index_revision
                and self._scoped_paths_by_job is not None
                and self._scoped_paths_by_project is not None
            ):
                index = (
                    self._scoped_paths_by_job
                    if field == "job_id"
                    else self._scoped_paths_by_project
                )
                return index.get(target, ())

        by_job: dict[str, list[Path]] = {}
        by_project: dict[str, list[Path]] = {}
        for path in paths:
            output_id = path.parent.name
            if not _valid_output_id(output_id):
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            seen_job_ids: set[str] = set()
            seen_project_ids: set[str] = set()
            for match in _SCOPED_INDEX_FIELD_PATTERN.finditer(raw):
                value = _decode_scoped_index_value(match.group("value"))
                if not value:
                    continue
                if match.group("field") == b"job_id":
                    seen_job_ids.add(value)
                else:
                    seen_project_ids.add(value)
            for job_id in seen_job_ids:
                by_job.setdefault(job_id, []).append(path)
            for project_id in seen_project_ids:
                by_project.setdefault(project_id, []).append(path)

        frozen_by_job = {key: tuple(value) for key, value in by_job.items()}
        frozen_by_project = {key: tuple(value) for key, value in by_project.items()}
        with self._cache_lock:
            self._scoped_index_revision = revision
            self._scoped_paths_by_job = frozen_by_job
            self._scoped_paths_by_project = frozen_by_project
        index = frozen_by_job if field == "job_id" else frozen_by_project
        return index.get(target, ())

    def _iter_scoped_output_paths(self, *, field: str, target: str):
        """Yield matching paths one at a time for catalogs beyond the index bound."""

        for path in _iter_output_record_paths(self.storage_root):
            output_id = path.parent.name
            if not _valid_output_id(output_id):
                continue
            try:
                raw = path.read_bytes()
            except OSError:
                continue
            for match in _SCOPED_INDEX_FIELD_PATTERN.finditer(raw):
                if match.group("field").decode("ascii") != field:
                    continue
                if _decode_scoped_index_value(match.group("value")) == target:
                    yield path
                    break

    def _read_scoped_records(
        self,
        paths: Iterable[Path],
        *,
        job_id: str | None = None,
        project_id: str | None = None,
        limit: int | None = None,
    ) -> list[V3GeneratedOutputRecord]:
        records: list[tuple[str, int, str, V3GeneratedOutputRecord]] = []
        for path in paths:
            record = self.get_output(path.parent.name)
            if record is None:
                continue
            if job_id is not None and str(record.job_id or "").strip() != job_id:
                continue
            actual_project_id = str((record.metadata or {}).get("project_id") or "").strip()
            if project_id is not None and actual_project_id != project_id:
                continue
            entry = (
                str(record.created_at or ""),
                -_output_id_order_number(record.output_id),
                str(path),
                record,
            )
            if limit is None:
                records.append(entry)
            elif len(records) < limit:
                heapq.heappush(records, entry)
            elif entry[:2] > records[0][:2]:
                heapq.heapreplace(records, entry)
        return [record for _created, _reverse_id, _path, record in sorted(records, reverse=True)]

    def _read_records_cached(self, limit: int = 100) -> list[V3GeneratedOutputRecord]:
        """Read a bounded newest-first page without retaining the full catalog."""

        bounded_limit = _bounded_output_limit(limit, default=100)
        newest: list[tuple[str, int, str, V3GeneratedOutputRecord]] = []
        for path in _iter_output_record_paths(self.storage_root):
            try:
                with path.open("r", encoding="utf-8") as handle:
                    record = V3GeneratedOutputRecord(**json.load(handle))
            except Exception:
                continue
            entry = (
                str(record.created_at or ""),
                -_output_id_order_number(record.output_id),
                str(path),
                record,
            )
            if len(newest) < bounded_limit:
                heapq.heappush(newest, entry)
            elif entry[:2] > newest[0][:2]:
                heapq.heapreplace(newest, entry)
        return [record for _created, _reverse_id, _path, record in sorted(newest, reverse=True)]


def download_route(output_id: str) -> str:
    return f"/api/v3/creative-agent/outputs/{output_id}/download"


def preview_route(output_id: str) -> str:
    return f"/api/v3/creative-agent/outputs/{output_id}/preview"


def thumbnail_route(output_id: str) -> str:
    return f"/api/v3/creative-agent/outputs/{output_id}/thumbnail"


def _default_storage_root() -> Path:
    configured = os.getenv("ALCHEMY_V3_OUTPUT_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[3] / ".media_storage" / "v3_outputs"


def _iter_output_record_paths(storage_root: Path) -> Iterable[Path]:
    """Yield output record paths through scandir without materializing the directory."""

    try:
        with os.scandir(storage_root) as entries:
            for entry in entries:
                try:
                    if not _valid_output_id(entry.name) or not entry.is_dir(follow_symlinks=False):
                        continue
                    record_path = Path(entry.path) / "output.json"
                    if not record_path.is_file():
                        continue
                except OSError:
                    continue
                yield record_path
    except OSError:
        return


def _output_id_order_number(output_id: str) -> int:
    """Return a stable lexical rank for valid, fixed-width V3 output IDs."""

    value = str(output_id or "")
    if not _valid_output_id(value):
        return 0
    try:
        return int(value.rsplit("_", 1)[1], 16)
    except (IndexError, ValueError):
        return 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_output_id(output_id: str) -> bool:
    return bool(_OUTPUT_ID_PATTERN.match(str(output_id or "")))


def _bounded_output_limit(
    value: Any, *, default: int, maximum: int | None = None
) -> int:
    try:
        requested = int(value or default)
    except (TypeError, ValueError):
        requested = default
    return max(1, min(requested, _OUTPUT_LIST_MAX_ENTRIES if maximum is None else maximum))


def _bounded_cache_set(cache: OrderedDict, key: Any, value: Any, max_entries: int) -> None:
    cache[key] = value
    cache.move_to_end(key)
    while len(cache) > max_entries:
        cache.popitem(last=False)


def _decode_scoped_index_value(raw_value: bytes) -> str:
    try:
        value = json.loads(b'"' + raw_value + b'"')
    except (UnicodeDecodeError, ValueError, TypeError):
        return ""
    return str(value).strip() if isinstance(value, str) else ""


def _is_doc73_source_binding(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and "source_output_id" in value
        and "target_output_id" not in value
    )


def _doc281_bind_output_record_metadata(metadata: dict, *, output_id: str) -> dict:
    """Bind a server-issued plan item to the immutable persisted output ID."""

    result = dict(metadata)
    envelope = result.get("doc281_output_plan_binding")
    required = {
        "schema_version", "job_id", "command_identity_digest", "output_index",
        "output_nonce", "output_binding_digest", "source_receipt_digest",
    }
    if not isinstance(envelope, dict) or set(envelope) != required:
        return result
    bound = {**envelope, "output_id": output_id}
    digest_payload = json.dumps(bound, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    result["doc281_output_plan_binding"] = {
        **bound,
        "record_binding_digest": hashlib.sha256(digest_payload.encode("utf-8")).hexdigest(),
    }
    return result


def _canonical_output_files_match_record(record: V3GeneratedOutputRecord, output_dir: Path) -> bool:
    if output_dir.name != record.output_id or not _path_is_within(output_dir.parent, output_dir):
        return False
    original_path = output_dir / f"original{_FORMAT_SUFFIXES.get(record.output_format, '.png')}"
    if not _path_is_within(output_dir, original_path):
        return False
    if not original_path.exists() or not original_path.is_file():
        return False
    metadata = record.metadata or {}
    canonical_hash_present = any(key in metadata for key in _IMMUTABLE_OUTPUT_METADATA_KEYS)
    expected_sha = _expected_output_content_sha256(record)
    if canonical_hash_present:
        if not expected_sha:
            return False
        try:
            return hashlib.sha256(original_path.read_bytes()).hexdigest() == expected_sha
        except OSError:
            return False
    if expected_sha:
        try:
            return hashlib.sha256(original_path.read_bytes()).hexdigest() == expected_sha
        except OSError:
            return False
    try:
        width, height = _validate_image(original_path.read_bytes())
    except ValueError:
        return False
    if record.width is not None and int(record.width) != int(width):
        # Pre-hash V3 records occasionally contain the provider's requested
        # dimensions instead of the dimensions of the persisted PNG.  The
        # canonical file has already been decoded successfully above, so a
        # hashless legacy dimension mismatch is descriptive metadata drift,
        # not evidence that the file is unsafe. Hash-bound records remain
        # strict because their metadata is part of the immutable contract.
        if canonical_hash_present or expected_sha:
            return False
    if record.height is not None and int(record.height) != int(height):
        if canonical_hash_present or expected_sha:
            return False
    return True


def _expected_output_content_sha256(record: V3GeneratedOutputRecord) -> str:
    metadata = record.metadata or {}
    # New records have two names for one canonical content hash.  If either
    # name is present, both must be valid and agree; otherwise a malformed
    # canonical value must never fall through to a weaker legacy alias.
    canonical_values: list[str] = []
    for key in ("content_sha256", "source_integrity_id"):
        if key not in metadata:
            continue
        value = str(metadata.get(key) or "").strip().lower()
        if value.startswith("sha256:"):
            value = value.split(":", 1)[1].strip()
        if not re.fullmatch(r"[a-f0-9]{64}", value):
            return ""
        canonical_values.append(value)
    if canonical_values:
        return canonical_values[0] if len(set(canonical_values)) == 1 else ""
    for key in ("artifact_sha256", "output_sha256", "original_sha256"):
        value = str(metadata.get(key) or "").strip().lower()
        if value.startswith("sha256:"):
            value = value.split(":", 1)[1].strip()
        if re.fullmatch(r"[a-f0-9]{64}", value):
            return value
    return ""


def _path_is_within(root: Path, candidate: Path) -> bool:
    """Return true only when a resolved candidate stays under its root."""

    try:
        root_resolved = root.resolve(strict=False)
        candidate.resolve(strict=False).relative_to(root_resolved)
    except (OSError, ValueError):
        return False
    return True


def _safe_remove_tree(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved == root_resolved or root_resolved not in target_resolved.parents:
        raise ValueError("Refusing to delete outside the V3 output storage root.")
    if target_resolved.exists():
        shutil.rmtree(target_resolved)


def _requested_aspect_ratio(value: object) -> float | None:
    raw = str(value or "").strip().lower().replace("：", ":")
    if ":" not in raw:
        return None
    numerator, denominator = (part.strip() for part in raw.split(":", 1))
    try:
        ratio = float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return ratio if ratio > 0 else None


def _normalize_requested_aspect_ratio(
    content: bytes,
    *,
    image_format: str,
    metadata: dict,
    source_dimensions: tuple[int | None, int | None],
) -> tuple[bytes, tuple[int, int] | None]:
    """Crop only when the Brain froze an explicit user-owned aspect ratio."""

    ratio = _requested_aspect_ratio(metadata.get("requested_image_aspect_ratio"))
    source_width, source_height = source_dimensions
    if ratio is None or not source_width or not source_height:
        return content, None
    current_ratio = float(source_width) / float(source_height)
    if abs(current_ratio - ratio) < 0.005:
        return content, None
    if ratio >= 1:
        target_width = int(source_width)
        target_height = max(1, round(target_width / ratio))
        if target_height > source_height:
            target_height = int(source_height)
            target_width = max(1, round(target_height * ratio))
    else:
        target_height = int(source_height)
        target_width = max(1, round(target_height * ratio))
        if target_width > source_width:
            target_width = int(source_width)
            target_height = max(1, round(target_width / ratio))
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(content)) as source:
            image = ImageOps.fit(
                source.convert("RGBA"),
                (target_width, target_height),
                method=getattr(getattr(Image, "Resampling", Image), "LANCZOS"),
                centering=(0.5, 0.5),
            )
        output = BytesIO()
        if image_format == "jpeg":
            image.convert("RGB").save(output, format="JPEG", quality=95)
        elif image_format == "webp":
            image.save(output, format="WEBP", quality=95)
        else:
            image.save(output, format="PNG", optimize=True)
        return output.getvalue(), (target_width, target_height)
    except Exception as exc:
        raise ValueError("V3 output could not be normalized to the explicit aspect ratio") from exc


def _decode_image(encoded_image: str) -> bytes:
    value = str(encoded_image or "").strip()
    if value.startswith("data:image/") and "," in value:
        value = value.split(",", 1)[1]
    try:
        content = base64.b64decode(value, validate=False)
    except Exception as exc:
        raise ValueError("V3 provider output was not valid base64 image data.") from exc
    if not content:
        raise ValueError("V3 provider output image was empty.")
    return content


def _validate_image(content: bytes) -> tuple[int | None, int | None]:
    try:
        from PIL import Image

        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            return image.size
    except Exception as exc:
        raise ValueError(f"V3 provider output was not a valid image: {str(exc)[:200]}") from exc


def _write_resized_png(content: bytes, path: Path, *, max_side: int) -> None:
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(content)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            image.save(path, format="PNG", optimize=True)
    except Exception:
        path.write_bytes(content)


def _normalise_format(output_format: str | None, mime_type: str | None) -> str:
    fmt = str(output_format or "").strip().lower()
    if fmt == "jpg":
        fmt = "jpeg"
    if fmt not in {"png", "jpeg", "webp"}:
        fmt = _MIME_FORMATS.get(str(mime_type or "").strip().lower(), "png")
    return fmt


def _normalise_mime(mime_type: str | None, output_format: str) -> str:
    mime = str(mime_type or "").strip().lower()
    if mime in _MIME_FORMATS:
        return "image/jpeg" if mime == "image/jpg" else mime
    return {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}.get(output_format, "image/png")


def _extension(output_format: str) -> str:
    if output_format == "jpeg":
        return "jpg"
    if output_format in {"png", "webp"}:
        return output_format
    return "png"
