"""V3-owned generated image output storage."""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from io import BytesIO
import json
import os
from pathlib import Path
import re
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
        records: list[V3GeneratedOutputRecord] = []
        for path in self.storage_root.glob("v3_output_*/output.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                records.append(V3GeneratedOutputRecord(**data))
            except Exception:
                continue
        return sorted(records, key=lambda record: record.created_at or "", reverse=True)[: max(1, int(limit or 100))]

    def list_by_job(self, job_id: str) -> list[V3GeneratedOutputRecord]:
        target = str(job_id or "").strip()
        if not target:
            return []
        return [record for record in self.list_outputs(limit=500) if record.job_id == target]

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

    def _write_record(self, record: V3GeneratedOutputRecord) -> None:
        path = self._record_path(record.output_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(record.to_json_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(path)

    def _record_path(self, output_id: str) -> Path:
        return self.storage_root / output_id / "output.json"


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
