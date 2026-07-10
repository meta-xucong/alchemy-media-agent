from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

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


def prepare_reference_truth_derivatives(
    path,
    *,
    asset_id: str = "",
    truth_layers: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Create provider-only focused references without changing the user's upload."""
    try:
        source = Path(str(path))
        if not source.exists() or not source.is_file():
            return []
        layers = {str(item).strip() for item in (truth_layers or []) if str(item).strip()}
        if not layers:
            return []
        derivatives: list[dict[str, Any]] = []
        if "portrait_identity_truth" in layers:
            derivatives.append(_truth_derivative(source, asset_id=asset_id, kind="portrait_identity_crop"))
        if "product_identity_truth" in layers:
            derivatives.append(_truth_derivative(source, asset_id=asset_id, kind="product_truth_crop"))
        if "structured_appearance_truth" in layers:
            derivatives.append(_truth_derivative(source, asset_id=asset_id, kind="appearance_truth_crop"))
        return [item for item in derivatives if item]
    except Exception:
        return []


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


def _truth_derivative(source: Path, *, asset_id: str, kind: str) -> dict[str, Any]:
    try:
        target = _cropped_reference_path(source, kind=kind)
        fallback = target.resolve() == source.resolve()
    except Exception:
        target = prepare_provider_reference_image(source)
        try:
            fallback = Path(str(target)).resolve() == source.resolve()
        except Exception:
            fallback = True
    truth_layer = {
        "portrait_identity_crop": "portrait_identity_truth",
        "product_truth_crop": "product_identity_truth",
        "appearance_truth_crop": "structured_appearance_truth",
    }.get(kind, "style_context_truth")
    return {
        "source_asset_id": asset_id,
        "truth_layer": truth_layer,
        "derivative_kind": kind,
        "path": str(target),
        "path_name": Path(str(target)).name,
        "fallback_to_original": bool(fallback),
        "identity_color_neutralized": kind == "portrait_identity_crop" and not fallback,
        "provider_only": True,
    }


def _cropped_reference_path(source: Path, *, kind: str) -> Path:
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError:
        return source

    max_bytes = max(128_000, int(settings.openai_image_reference_max_upload_bytes))
    max_edge = max(512, int(settings.openai_image_reference_max_edge))
    quality = min(95, max(50, int(settings.openai_image_reference_jpeg_quality)))
    stat = source.stat()
    digest = hashlib.sha256(
        f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{kind}:doc93-identity-neutral-v1:{max_bytes}:{max_edge}:{quality}".encode("utf-8")
    ).hexdigest()[:24]
    cache_dir = settings.media_storage_root / "provider_reference_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{source.stem}-{kind}-{digest}.jpg"
    if target.exists() and target.stat().st_size <= max_bytes:
        return target

    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw)
        image = _to_rgb_on_white(image, Image)
        box = _truth_crop_box(image.size, kind)
        cropped = image.crop(box)
        if kind == "portrait_identity_crop":
            from PIL import ImageEnhance

            cropped = ImageEnhance.Color(cropped).enhance(0.08)
        if max(cropped.size) > max_edge:
            cropped.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        for current_quality in dict.fromkeys([quality, 88, 84, 80, 76, 72, 68]):
            cropped.save(target, format="JPEG", quality=current_quality, optimize=True)
            if target.stat().st_size <= max_bytes:
                return target
        current = cropped
        while target.stat().st_size > max_bytes and max(current.size) > 512:
            next_size = tuple(max(1, int(side * 0.88)) for side in current.size)
            current = current.resize(next_size, Image.Resampling.LANCZOS)
            current.save(target, format="JPEG", quality=72, optimize=True)
    return target if target.exists() else source


def _truth_crop_box(size: tuple[int, int], kind: str) -> tuple[int, int, int, int]:
    width, height = size
    if width <= 0 or height <= 0:
        return (0, 0, max(1, width), max(1, height))
    if kind == "portrait_identity_crop":
        if height >= width:
            crop_w = int(width * 0.74)
            crop_h = int(height * 0.56)
            center_x = width * 0.5
            center_y = height * 0.31
        else:
            crop_w = int(width * 0.50)
            crop_h = int(height * 0.72)
            center_x = width * 0.5
            center_y = height * 0.42
    elif kind == "appearance_truth_crop":
        crop_w = int(width * 0.88)
        crop_h = int(height * 0.92)
        center_x = width * 0.5
        center_y = height * 0.52
    else:
        crop_w = int(width * 0.84)
        crop_h = int(height * 0.84)
        center_x = width * 0.5
        center_y = height * 0.5
    crop_w = max(1, min(width, crop_w))
    crop_h = max(1, min(height, crop_h))
    left = int(round(center_x - crop_w / 2))
    top = int(round(center_y - crop_h / 2))
    left = max(0, min(width - crop_w, left))
    top = max(0, min(height - crop_h, top))
    return (left, top, left + crop_w, top + crop_h)


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
