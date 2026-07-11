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


def prepare_identity_repair_artifacts(
    output_path: str | Path,
    normalized_face_box: list[float],
) -> dict[str, object]:
    """Prepare a bounded edit canvas and a same-size feathered face mask."""
    source = Path(output_path)
    canvas = Path(prepare_provider_reference_image(source))
    if len(normalized_face_box) != 4:
        raise ValueError("identity repair requires a normalized face box")
    from PIL import Image, ImageDraw, ImageFilter

    with Image.open(canvas) as raw:
        width, height = raw.size
    x, y, box_width, box_height = [float(value) for value in normalized_face_box]
    left = max(0, int((x - box_width * 0.10) * width))
    top = max(0, int((y - box_height * 0.16) * height))
    right = min(width, int((x + box_width * 1.10) * width))
    bottom = min(height, int((y + box_height * 1.13) * height))
    if right - left < 32 or bottom - top < 32:
        raise ValueError("identity repair face box is too small")

    stat = canvas.stat()
    digest = hashlib.sha256(
        f"{canvas.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{left}:{top}:{right}:{bottom}:doc96-mask-v1".encode("utf-8")
    ).hexdigest()[:24]
    cache_dir = settings.media_storage_root / "provider_reference_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    mask_path = cache_dir / f"{canvas.stem}-identity-repair-mask-{digest}.png"
    if not mask_path.exists():
        alpha = Image.new("L", (width, height), color=255)
        draw = ImageDraw.Draw(alpha)
        draw.ellipse((left, top, right, bottom), fill=0)
        blur_radius = max(4, min(28, int(min(right - left, bottom - top) * 0.055)))
        alpha = alpha.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        mask = Image.new("RGBA", (width, height), color=(255, 255, 255, 255))
        mask.putalpha(alpha)
        mask.save(mask_path, format="PNG", optimize=True)
    return {
        "canvas_path": str(canvas),
        "mask_path": str(mask_path),
        "canvas_size": [width, height],
        "normalized_face_box": [round(value, 6) for value in (x, y, box_width, box_height)],
        "mask_box": [left, top, right, bottom],
        "ephemeral": True,
    }


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
            derivatives.append(_truth_derivative(source, asset_id=asset_id, kind="portrait_identity_geometry_crop"))
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
        "portrait_identity_geometry_crop": "portrait_identity_truth",
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
        "identity_color_neutralized": kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"} and not fallback,
        "identity_color_retention": (
            0.90 if kind == "portrait_identity_crop" else 0.65 if kind == "portrait_identity_geometry_crop" else None
        ),
        "identity_color_policy": (
            "face_color_preserved_context_neutralized_with_legacy_fallback"
            if kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"} and not fallback
            else None
        ),
        "identity_face_color_retention": (
            1.0 if kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"} and not fallback else None
        ),
        "identity_context_color_retention": (
            0.0 if kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"} and not fallback else None
        ),
        "identity_background_neutralized": False,
        "identity_context_reduced_by_tight_crop": kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"} and not fallback,
        "identity_evidence_scope": (
            "feature_detail" if kind == "portrait_identity_crop" else "head_geometry" if kind == "portrait_identity_geometry_crop" else None
        ),
        "identity_gateway_min_edge_px": 512 if kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"} and not fallback else None,
        "provider_only": True,
    }


def _cropped_reference_path(source: Path, *, kind: str) -> Path:
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError:
        return source

    max_bytes = max(128_000, int(settings.openai_image_reference_max_upload_bytes))
    if kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"}:
        max_bytes = min(max_bytes, 480_000)
    max_edge = max(512, int(settings.openai_image_reference_max_edge))
    quality = min(95, max(50, int(settings.openai_image_reference_jpeg_quality)))
    stat = source.stat()
    digest = hashlib.sha256(
        f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{kind}:doc96-face-color-context-neutral-v4:{max_bytes}:{max_edge}:{quality}".encode("utf-8")
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
        if kind in {"portrait_identity_crop", "portrait_identity_geometry_crop"}:
            from PIL import ImageEnhance

            neutralized = _face_preserving_context_neutralization(cropped)
            if neutralized is not None:
                cropped = neutralized
            else:
                color_retention = 0.90 if kind == "portrait_identity_crop" else 0.65
                cropped = ImageEnhance.Color(cropped).enhance(color_retention)
            minimum_edge = min(512, max_edge)
            if min(cropped.size) < minimum_edge:
                scale = minimum_edge / max(1, min(cropped.size))
                target_size = (
                    max(1, int(round(cropped.width * scale))),
                    max(1, int(round(cropped.height * scale))),
                )
                if max(target_size) > max_edge:
                    fit_scale = max_edge / max(target_size)
                    target_size = (
                        max(1, int(round(target_size[0] * fit_scale))),
                        max(1, int(round(target_size[1] * fit_scale))),
                    )
                cropped = cropped.resize(target_size, Image.Resampling.LANCZOS)
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


def _face_preserving_context_neutralization(image):
    try:
        import cv2 as cv
        import numpy as np
        from PIL import Image, ImageDraw, ImageFilter, ImageOps

        model_path = Path(settings.v3_identity_model_dir) / "face_detection_yunet_2023mar.onnx"
        if not model_path.is_file():
            return None
        rgb = np.asarray(image.convert("RGB"))
        bgr = cv.cvtColor(rgb, cv.COLOR_RGB2BGR)
        height, width = bgr.shape[:2]
        detector = cv.FaceDetectorYN.create(str(model_path), "", (width, height), 0.5, 0.3, 5000)
        _status, faces = detector.detect(bgr)
        if faces is None or len(faces) == 0:
            return None
        face = max(faces, key=lambda value: float(value[2] * value[3]) * max(0.1, float(value[-1])))
        x, y, face_width, face_height = [float(value) for value in face[:4]]
        left = max(0, int(round(x - face_width * 0.08)))
        top = max(0, int(round(y - face_height * 0.08)))
        right = min(width, int(round(x + face_width * 1.08)))
        bottom = min(height, int(round(y + face_height * 1.08)))
        if right - left < 48 or bottom - top < 48:
            return None
        mask = Image.new("L", image.size, color=0)
        ImageDraw.Draw(mask).ellipse((left, top, right, bottom), fill=255)
        blur_radius = max(3, min(18, int(min(right - left, bottom - top) * 0.035)))
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        grayscale = ImageOps.grayscale(image).convert("RGB")
        return Image.composite(image.convert("RGB"), grayscale, mask)
    except Exception:
        return None


def _truth_crop_box(size: tuple[int, int], kind: str) -> tuple[int, int, int, int]:
    width, height = size
    if width <= 0 or height <= 0:
        return (0, 0, max(1, width), max(1, height))
    if kind == "portrait_identity_crop":
        if height > width * 1.15:
            crop_w = int(width * 0.76)
            crop_h = int(height * 0.48)
            center_x = width * 0.5
            center_y = height * 0.31
        elif width > height * 1.15:
            crop_w = int(width * 0.42)
            crop_h = int(height * 0.72)
            center_x = width * 0.5
            center_y = height * 0.42
        else:
            crop_w = int(width * 0.58)
            crop_h = int(height * 0.53)
            center_x = width * 0.5
            center_y = height * 0.31
    elif kind == "portrait_identity_geometry_crop":
        if height > width * 1.15:
            crop_w = int(width * 0.90)
            crop_h = int(height * 0.64)
            center_x = width * 0.5
            center_y = height * 0.35
        elif width > height * 1.15:
            crop_w = int(width * 0.58)
            crop_h = int(height * 0.92)
            center_x = width * 0.5
            center_y = height * 0.45
        else:
            crop_w = int(width * 0.72)
            crop_h = int(height * 0.58)
            center_x = width * 0.5
            center_y = height * 0.29
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
