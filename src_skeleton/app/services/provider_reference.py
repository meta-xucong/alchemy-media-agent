from __future__ import annotations

import hashlib
from pathlib import Path

from app.config import settings


SUPPORTED_PROVIDER_REFERENCE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def prepare_provider_reference_image(path) -> Path | object:
    """Return an upstream-friendly reference image without modifying the source file."""
    try:
        source = Path(str(path))
        if not source.exists() or not source.is_file():
            return path
        max_bytes = max(128_000, int(settings.openai_image_reference_max_upload_bytes))
        if source.stat().st_size <= max_bytes and source.suffix.lower() in SUPPORTED_PROVIDER_REFERENCE_SUFFIXES:
            return source
        return _compressed_reference_path(source, max_bytes=max_bytes)
    except Exception:
        return path


def prepare_provider_reference_images(paths: list) -> list:
    return [prepare_provider_reference_image(path) for path in paths]


def _compressed_reference_path(source: Path, *, max_bytes: int) -> Path:
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError:
        return source

    max_edge = max(512, int(settings.openai_image_reference_max_edge))
    initial_quality = min(95, max(50, int(settings.openai_image_reference_jpeg_quality)))
    stat = source.stat()
    digest = hashlib.sha256(
        f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{max_bytes}:{max_edge}:{initial_quality}".encode("utf-8")
    ).hexdigest()[:24]
    cache_dir = settings.media_storage_root / "provider_reference_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{source.stem}-{digest}.jpg"
    if target.exists() and target.stat().st_size <= max_bytes:
        return target

    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image = _to_rgb_on_white(image, Image)
        if max(image.size) > max_edge:
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)

        qualities = [initial_quality, 85, 80, 75, 70, 65, 60]
        for quality in dict.fromkeys(qualities):
            image.save(target, format="JPEG", quality=quality, optimize=True)
            if target.stat().st_size <= max_bytes:
                return target

        current = image
        while target.stat().st_size > max_bytes and max(current.size) > 512:
            next_size = tuple(max(1, int(side * 0.86)) for side in current.size)
            current = current.resize(next_size, Image.Resampling.LANCZOS)
            current.save(target, format="JPEG", quality=70, optimize=True)
    return target if target.exists() else source


def _to_rgb_on_white(image, Image):
    if image.mode not in {"RGB", "L"}:
        background = Image.new("RGB", image.size, (255, 255, 255))
        if image.mode in {"RGBA", "LA"}:
            alpha = image.getchannel("A")
            background.paste(image.convert("RGB"), mask=alpha)
            return background
        return image.convert("RGB")
    if image.mode == "L":
        return image.convert("RGB")
    return image
