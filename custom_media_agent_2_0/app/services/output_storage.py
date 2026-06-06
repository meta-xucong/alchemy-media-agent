from __future__ import annotations

import base64
import io
from pathlib import Path
from typing import Any
from urllib.parse import quote

from PIL import Image, ImageOps

from app.config import settings
from app.repositories import repository
from app.schemas import ImageHistoryItem, ImageOutput


THUMBNAIL_SIZE = (512, 512)
THUMBNAIL_QUALITY = 78


def save_provider_output(*, job_id: str, output: ImageOutput, encoded: str, output_format: str, mime_type: str) -> ImageOutput:
    content = base64.b64decode(encoded)
    fmt = _normalize_format(output_format, mime_type)
    output_dir = settings.storage_dir / "outputs" / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{output.output_id}.{fmt}"
    output_path.write_bytes(content)
    thumbnail_path = _write_thumbnail(output.output_id, content)
    metadata = {
        **output.metadata,
        "native_v2_storage": True,
        "storage_path": str(output_path),
        "thumbnail_path": str(thumbnail_path) if thumbnail_path else None,
        "thumbnail_url": _thumbnail_url(output.output_id) if thumbnail_path else None,
        "mime_type": mime_type,
        "format": fmt,
    }
    return output.model_copy(
        update={
            "url": f"/api/v2/outputs/{output.output_id}/download",
            "metadata": metadata,
        }
    )


def read_output_content(output_id: str) -> tuple[bytes, str] | None:
    path, mime_type = _output_path_and_type(output_id)
    if not path or not path.exists():
        return None
    return path.read_bytes(), mime_type


def read_output_thumbnail(output_id: str) -> tuple[bytes, str] | None:
    output = repository.get_output(output_id)
    path = None
    if output:
        path = _path_from_metadata(output.metadata, "thumbnail_path")
    if not path:
        item = _history_item(output_id)
        if item:
            path = _path_from_metadata(item.metadata, "thumbnail_path")
    if not path or not path.exists():
        content = read_output_content(output_id)
        if not content:
            return None
        thumbnail = _make_thumbnail(content[0])
        if not thumbnail:
            return None
        path = _thumbnail_path(output_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(thumbnail)
    return path.read_bytes(), "image/webp"


def delete_output_storage(output_id: str, metadata: dict[str, Any] | None = None) -> dict[str, bool]:
    metadata = metadata or {}
    deleted_output = False
    deleted_thumbnail = False
    output_path = _path_from_metadata(metadata, "storage_path")
    thumbnail_path = _path_from_metadata(metadata, "thumbnail_path") or _thumbnail_path(output_id)
    if output_path:
        deleted_output = _safe_unlink(output_path, settings.storage_dir)
        _prune_empty_output_parent(output_path)
    if thumbnail_path:
        deleted_thumbnail = _safe_unlink(thumbnail_path, settings.storage_dir)
    return {"deleted_file": deleted_output, "deleted_thumbnail": deleted_thumbnail}


def _output_path_and_type(output_id: str) -> tuple[Path | None, str]:
    output = repository.get_output(output_id)
    metadata: dict[str, Any] = output.metadata if output else {}
    if not metadata:
        item = _history_item(output_id)
        metadata = item.metadata if item else {}
    path = _path_from_metadata(metadata, "storage_path")
    mime_type = str(metadata.get("mime_type") or _mime_from_format(metadata.get("format")) or "image/png")
    return path, mime_type


def _history_item(output_id: str) -> ImageHistoryItem | None:
    from app.services.image_history import get_image_history_item

    return get_image_history_item(output_id)


def _write_thumbnail(output_id: str, content: bytes) -> Path | None:
    thumbnail = _make_thumbnail(content)
    if not thumbnail:
        return None
    path = _thumbnail_path(output_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(thumbnail)
    return path


def _make_thumbnail(content: bytes) -> bytes | None:
    try:
        with Image.open(io.BytesIO(content)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
            if image.mode in {"RGBA", "LA", "P"}:
                converted = image.convert("RGBA") if image.mode == "P" else image
                canvas = Image.new("RGB", converted.size, (255, 255, 255))
                canvas.paste(converted, mask=converted.getchannel("A") if "A" in converted.getbands() else None)
                image = canvas
            else:
                image = image.convert("RGB")
            output = io.BytesIO()
            image.save(output, format="WEBP", quality=THUMBNAIL_QUALITY, method=6)
            return output.getvalue()
    except (OSError, ValueError):
        return None


def _thumbnail_path(output_id: str) -> Path:
    return settings.storage_dir / "thumbnails" / f"{output_id}.webp"


def _safe_unlink(path: Path, root: Path) -> bool:
    try:
        resolved = path.resolve()
        resolved_root = root.resolve()
    except OSError:
        return False
    if resolved_root != resolved and resolved_root not in resolved.parents:
        return False
    if not resolved.exists() or not resolved.is_file():
        return False
    resolved.unlink(missing_ok=True)
    return True


def _prune_empty_output_parent(path: Path) -> None:
    try:
        parent = path.parent.resolve()
        outputs_root = (settings.storage_dir / "outputs").resolve()
        if parent.parent == outputs_root and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass


def _thumbnail_url(output_id: str) -> str:
    return f"/api/v2/image/history/{quote(output_id, safe='')}/thumbnail"


def _path_from_metadata(metadata: dict[str, Any], key: str) -> Path | None:
    value = metadata.get(key)
    if not value:
        return None
    path = Path(str(value))
    return path if path.is_absolute() else settings.storage_dir / path


def _normalize_format(output_format: str, mime_type: str) -> str:
    candidate = str(output_format or "").lower().strip(".")
    if candidate in {"png", "jpeg", "jpg", "webp"}:
        return "jpeg" if candidate == "jpg" else candidate
    return _format_from_mime(mime_type) or "png"


def _mime_from_format(value: Any) -> str | None:
    normalized = str(value or "").lower()
    if "jpeg" in normalized or normalized == "jpg":
        return "image/jpeg"
    if "webp" in normalized:
        return "image/webp"
    if "png" in normalized:
        return "image/png"
    return None


def _format_from_mime(value: Any) -> str | None:
    normalized = str(value or "").lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return "jpeg"
    if "webp" in normalized:
        return "webp"
    if "png" in normalized:
        return "png"
    return None
