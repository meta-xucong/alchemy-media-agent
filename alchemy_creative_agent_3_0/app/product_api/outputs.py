"""V3-owned generated image output storage."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
import threading
from uuid import uuid4


_OUTPUT_ID_PATTERN = re.compile(r"^v3_output_[a-f0-9]{20}$")
_FORMAT_SUFFIXES = {"png": ".png", "jpeg": ".jpg", "jpg": ".jpg", "webp": ".webp"}
_MIME_FORMATS = {"image/png": "png", "image/jpeg": "jpeg", "image/jpg": "jpeg", "image/webp": "webp"}


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
        self._records_cache_signature: tuple[tuple[str, int, int], ...] | None = None
        self._records_cache: list[V3GeneratedOutputRecord] | None = None
        self._records_by_job_cache: dict[str, list[V3GeneratedOutputRecord]] | None = None

    def save_base64_output(
        self,
        *,
        job_id: str,
        candidate_id: str,
        asset_id: str,
        provider: str,
        model: str | None,
        encoded_image: str,
        mime_type: str | None = None,
        output_format: str | None = None,
        width: int | None = None,
        height: int | None = None,
        metadata: dict | None = None,
    ) -> V3GeneratedOutputRecord:
        output_id = f"v3_output_{uuid4().hex[:20]}"
        fmt = _normalise_format(output_format, mime_type)
        mime = _normalise_mime(mime_type, fmt)
        content = _decode_image(encoded_image)
        actual_width, actual_height = _validate_image(content)
        width = width or actual_width
        height = height or actual_height

        output_dir = self.storage_root / output_id
        output_dir.mkdir(parents=True, exist_ok=True)
        original_path = output_dir / f"original{_FORMAT_SUFFIXES.get(fmt, '.png')}"
        original_path.write_bytes(content)
        preview_path = output_dir / "preview.png"
        thumbnail_path = output_dir / "thumbnail.png"
        _write_resized_png(content, preview_path, max_side=1600)
        _write_resized_png(content, thumbnail_path, max_side=512)

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
            metadata={**(metadata or {}), "v3_owned_output": True},
        )
        self._write_record(record)
        self._invalidate_cache()
        return record

    def get_output(self, output_id: str) -> V3GeneratedOutputRecord | None:
        if not _valid_output_id(output_id):
            return None
        path = self._record_path(output_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return V3GeneratedOutputRecord(**data)
        except Exception:
            return None

    def list_outputs(self, limit: int = 100) -> list[V3GeneratedOutputRecord]:
        records = self._read_records_cached()
        return records[: max(1, int(limit or 100))]

    def list_by_job(self, job_id: str) -> list[V3GeneratedOutputRecord]:
        target = str(job_id or "").strip()
        if not target:
            return []
        self._read_records_cached()
        with self._cache_lock:
            by_job = self._records_by_job_cache or {}
            return list(by_job.get(target, []))

    def file_for_variant(self, output_id: str, variant: str) -> tuple[Path, str, str] | None:
        record = self.get_output(output_id)
        if record is None:
            return None
        if variant == "download":
            path = Path(record.file_path)
            media_type = record.mime_type
            filename = f"{output_id}.{_extension(record.output_format)}"
        elif variant == "preview":
            path = Path(record.preview_path)
            media_type = "image/png"
            filename = f"{output_id}_preview.png"
        elif variant == "thumbnail":
            path = Path(record.thumbnail_path)
            media_type = "image/png"
            filename = f"{output_id}_thumbnail.png"
        else:
            return None
        if not path.exists() or not path.is_file():
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
        self._invalidate_cache()
        return True

    def update_metadata(self, output_id: str, updates: dict) -> V3GeneratedOutputRecord | None:
        record = self.get_output(output_id)
        if record is None:
            return None
        updated = replace(record, metadata={**dict(record.metadata or {}), **dict(updates or {})})
        self._write_record(updated)
        self._invalidate_cache()
        return updated

    def _write_record(self, record: V3GeneratedOutputRecord) -> None:
        path = self._record_path(record.output_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(record.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def _record_path(self, output_id: str) -> Path:
        return self.storage_root / output_id / "output.json"

    def _invalidate_cache(self) -> None:
        with self._cache_lock:
            self._records_cache_signature = None
            self._records_cache = None
            self._records_by_job_cache = None

    def _record_paths_signature(self) -> tuple[tuple[Path, ...], tuple[tuple[str, int, int], ...]]:
        paths = sorted(self.storage_root.glob("v3_output_*/output.json"))
        signature_items: list[tuple[str, int, int]] = []
        for path in paths:
            try:
                stat = path.stat()
            except OSError:
                continue
            signature_items.append((str(path), int(stat.st_mtime_ns), int(stat.st_size)))
        return tuple(paths), tuple(signature_items)

    def _read_records_cached(self) -> list[V3GeneratedOutputRecord]:
        paths, signature = self._record_paths_signature()
        with self._cache_lock:
            if signature == self._records_cache_signature and self._records_cache is not None:
                return list(self._records_cache)

        records: list[V3GeneratedOutputRecord] = []
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(V3GeneratedOutputRecord(**data))
            except Exception:
                continue
        records = sorted(records, key=lambda record: record.created_at or "", reverse=True)
        by_job: dict[str, list[V3GeneratedOutputRecord]] = {}
        for record in records:
            by_job.setdefault(str(record.job_id or ""), []).append(record)

        with self._cache_lock:
            self._records_cache_signature = signature
            self._records_cache = list(records)
            self._records_by_job_cache = {key: list(value) for key, value in by_job.items()}
        return list(records)


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


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _valid_output_id(output_id: str) -> bool:
    return bool(_OUTPUT_ID_PATTERN.match(str(output_id or "")))


def _safe_remove_tree(root: Path, target: Path) -> None:
    root_resolved = root.resolve()
    target_resolved = target.resolve()
    if target_resolved == root_resolved or root_resolved not in target_resolved.parents:
        raise ValueError("Refusing to delete outside the V3 output storage root.")
    if target_resolved.exists():
        shutil.rmtree(target_resolved)


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
