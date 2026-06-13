from __future__ import annotations

import hashlib
import io
import mimetypes
import zipfile
from collections import OrderedDict
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings
from app.repositories import repository

DEFAULT_CASE_THUMBNAIL_VARIANT = "grid"
CASE_THUMBNAIL_VERSION = "v2"
CASE_THUMBNAIL_VARIANTS = {
    "grid": {"size": (720, 900), "quality": 84},
    "preview": {"size": (1280, 1600), "quality": 88},
}
_ARCHIVE_MEMBER_INDEX_CACHE_MAX = 4
_archive_member_index_cache: OrderedDict[tuple[str, int, int], dict[str, str]] = OrderedDict()


def read_case_asset(asset_path: str) -> tuple[bytes, str] | None:
    normalized_path = _normalize_asset_path(asset_path)
    if not normalized_path:
        return None
    content = _read_asset_bytes(normalized_path)
    if content is None:
        return None
    media_type = mimetypes.guess_type(normalized_path)[0] or "application/octet-stream"
    return content, media_type


def read_case_thumbnail(asset_path: str, variant: str = DEFAULT_CASE_THUMBNAIL_VARIANT) -> tuple[bytes, str] | None:
    normalized_path = _normalize_asset_path(asset_path)
    if not normalized_path:
        return None
    thumbnail_variant = _thumbnail_variant(variant)
    if not thumbnail_variant:
        return None
    snapshot_path = _active_snapshot_path()
    if not snapshot_path or not snapshot_path.exists():
        return None
    cache_path = _thumbnail_cache_path(normalized_path, snapshot_path, thumbnail_variant)
    if cache_path.exists():
        return cache_path.read_bytes(), "image/webp"
    original = _read_asset_bytes(normalized_path, snapshot_path=snapshot_path)
    if original is None:
        return None
    try:
        thumbnail = _make_thumbnail(original, thumbnail_variant)
    except (OSError, UnidentifiedImageError, ValueError):
        return None
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    temp = cache_path.with_suffix(cache_path.suffix + ".tmp")
    temp.write_bytes(thumbnail)
    temp.replace(cache_path)
    return thumbnail, "image/webp"


def _normalize_asset_path(asset_path: str) -> str | None:
    normalized = asset_path.replace("\\", "/").lstrip("/")
    while normalized.startswith("../"):
        normalized = normalized[3:]
    if ".." in normalized.split("/"):
        return None
    if not normalized.startswith("images/"):
        return None
    return normalized


def _read_asset_bytes(asset_path: str, snapshot_path: Path | None = None) -> bytes | None:
    active_snapshot = snapshot_path or _active_snapshot_path()
    if not active_snapshot or not active_snapshot.exists():
        return None
    with zipfile.ZipFile(active_snapshot) as archive:
        member = _find_archive_member(archive, asset_path, active_snapshot)
        if not member:
            return None
        with archive.open(member) as file:
            return file.read()


def _thumbnail_cache_path(asset_path: str, snapshot_path: Path, variant: str) -> Path:
    index_version = repository.get_active_index_version() or snapshot_path.stem
    spec = CASE_THUMBNAIL_VARIANTS[variant]
    digest = hashlib.sha1(
        f"{CASE_THUMBNAIL_VERSION}:{index_version}:{asset_path}:{variant}:{spec['size']}:{spec['quality']}".encode("utf-8")
    ).hexdigest()
    return settings.case_thumbnail_dir / digest[:2] / f"{digest}.webp"


def _make_thumbnail(content: bytes, variant: str = DEFAULT_CASE_THUMBNAIL_VARIANT) -> bytes:
    spec = CASE_THUMBNAIL_VARIANTS[variant]
    with Image.open(io.BytesIO(content)) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail(spec["size"], Image.Resampling.LANCZOS)
        if image.mode in {"RGBA", "LA", "P"}:
            canvas = Image.new("RGB", image.size, (255, 255, 255))
            if image.mode == "P":
                image = image.convert("RGBA")
            canvas.paste(image, mask=image.getchannel("A") if "A" in image.getbands() else None)
            image = canvas
        else:
            image = image.convert("RGB")
        output = io.BytesIO()
        image.save(output, format="WEBP", quality=spec["quality"], method=6)
        return output.getvalue()


def _thumbnail_variant(variant: str) -> str | None:
    normalized = (variant or DEFAULT_CASE_THUMBNAIL_VARIANT).strip().lower()
    return normalized if normalized in CASE_THUMBNAIL_VARIANTS else None


def _active_snapshot_path() -> Path | None:
    index_version = repository.get_active_index_version() or ""
    source_version = index_version.rsplit(":", 1)[-1] if ":" in index_version else index_version
    if source_version.startswith("github-"):
        candidate = settings.remote_snapshot_dir / f"{source_version}.zip"
        if candidate.exists():
            return candidate
    snapshots = sorted(settings.remote_snapshot_dir.glob("github-*.zip"), key=lambda path: path.stat().st_mtime, reverse=True)
    return snapshots[0] if snapshots else None


def _find_archive_member(archive: zipfile.ZipFile, asset_path: str, snapshot_path: Path) -> str | None:
    index = _archive_member_index(archive, snapshot_path)
    member = index.get(asset_path)
    if member:
        return member
    suffix = f"/{asset_path}"
    for name in archive.namelist():
        normalized = name.replace("\\", "/")
        if normalized == asset_path or normalized.endswith(suffix):
            return name
    return None


def _archive_member_index(archive: zipfile.ZipFile, snapshot_path: Path) -> dict[str, str]:
    cache_key = _archive_member_index_cache_key(snapshot_path)
    cached = _archive_member_index_cache.get(cache_key)
    if cached is not None:
        _archive_member_index_cache.move_to_end(cache_key)
        return cached
    index: dict[str, str] = {}
    for name in archive.namelist():
        normalized = name.replace("\\", "/")
        index.setdefault(normalized, name)
        images_position = normalized.find("images/")
        if images_position >= 0:
            index.setdefault(normalized[images_position:], name)
    _archive_member_index_cache[cache_key] = index
    if len(_archive_member_index_cache) > _ARCHIVE_MEMBER_INDEX_CACHE_MAX:
        _archive_member_index_cache.popitem(last=False)
    return index


def _archive_member_index_cache_key(snapshot_path: Path) -> tuple[str, int, int]:
    try:
        stat = snapshot_path.stat()
        return str(snapshot_path.resolve()), stat.st_mtime_ns, stat.st_size
    except OSError:
        return str(snapshot_path), 0, 0
