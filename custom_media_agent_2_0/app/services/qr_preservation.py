from __future__ import annotations

import io
import json
import re
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps

from app.services.uploaded_assets import uploaded_asset_path


QR_REQUEST_PATTERN = re.compile(r"(二维码|qr\s*code|qr-code|qrcode|qr码|scan\s*code)", re.IGNORECASE)


@dataclass(frozen=True)
class QrPreservationResult:
    content: bytes
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class _QrCrop:
    asset_id: str
    image: Image.Image
    bbox: tuple[int, int, int, int]
    decoded_text: str


def preserve_requested_qr_code(
    *,
    content: bytes,
    metadata: dict[str, Any],
    output_format: str,
    mime_type: str,
) -> QrPreservationResult:
    if not _qr_requested(metadata):
        return QrPreservationResult(content=content)
    input_images = metadata.get("input_images") if isinstance(metadata.get("input_images"), list) else []
    if not input_images:
        return QrPreservationResult(
            content=content,
            metadata={"requested": True, "applied": False, "reason": "no_provider_input_images"},
        )
    source_crop = _first_qr_crop(input_images)
    if not source_crop:
        return QrPreservationResult(
            content=content,
            metadata={"requested": True, "applied": False, "reason": "qr_not_detected_in_uploaded_assets"},
        )
    try:
        with Image.open(io.BytesIO(content)) as raw_output:
            output_image = ImageOps.exif_transpose(raw_output).convert("RGBA")
            placement = _placement_from_metadata(metadata)
            composed, paste_box = _paste_qr_crop(output_image, source_crop.image, placement=placement)
            saved = io.BytesIO()
            save_format = _pil_format(output_format, mime_type)
            if save_format == "JPEG":
                composed = composed.convert("RGB")
                composed.save(saved, format=save_format, quality=95, optimize=True)
            elif save_format == "WEBP":
                composed.save(saved, format=save_format, quality=95, method=6)
            else:
                composed.save(saved, format="PNG", optimize=True)
    except (OSError, ValueError):
        return QrPreservationResult(
            content=content,
            metadata={"requested": True, "applied": False, "reason": "output_image_decode_failed"},
        )
    return QrPreservationResult(
        content=saved.getvalue(),
        metadata={
            "requested": True,
            "applied": True,
            "method": "detected_qr_crop_overlay",
            "source_asset_id": source_crop.asset_id,
            "decoded": bool(source_crop.decoded_text),
            "source_bbox": list(source_crop.bbox),
            "placement": placement,
            "paste_box": list(paste_box),
        },
    )


def _qr_requested(metadata: dict[str, Any]) -> bool:
    searchable = {
        "user_prompt": metadata.get("user_prompt"),
        "provider_input_plan": metadata.get("provider_input_plan"),
        "input_images": metadata.get("input_images"),
    }
    try:
        text = json.dumps(searchable, ensure_ascii=False)
    except TypeError:
        text = str(searchable)
    return bool(QR_REQUEST_PATTERN.search(text))


def _first_qr_crop(input_images: list[Any]) -> _QrCrop | None:
    for item in input_images:
        if not isinstance(item, dict):
            continue
        asset_id = str(item.get("asset_id") or "")
        if not asset_id:
            continue
        path = uploaded_asset_path(asset_id)
        if not path or not path.exists():
            continue
        try:
            with Image.open(path) as raw_image:
                source = ImageOps.exif_transpose(raw_image).convert("RGB")
        except (OSError, ValueError):
            continue
        detected = _detect_qr_bbox(source)
        if not detected:
            continue
        bbox, decoded = detected
        crop_box = _expand_bbox(bbox, source.size)
        crop = source.crop(crop_box)
        if crop.width < 24 or crop.height < 24:
            continue
        return _QrCrop(asset_id=asset_id, image=crop, bbox=crop_box, decoded_text=decoded)
    return None


def _detect_qr_bbox(image: Image.Image) -> tuple[tuple[int, int, int, int], str] | None:
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception:
        return None
    rgb = image.convert("RGB")
    array = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
    detector = cv2.QRCodeDetector()
    decoded, points, _ = detector.detectAndDecode(array)
    if points is None:
        found, points = detector.detect(array)
        if not found or points is None:
            return None
        decoded = ""
    pts = points.reshape(-1, 2)
    x_min = max(0, int(pts[:, 0].min()))
    y_min = max(0, int(pts[:, 1].min()))
    x_max = min(image.width, int(pts[:, 0].max()))
    y_max = min(image.height, int(pts[:, 1].max()))
    if x_max <= x_min or y_max <= y_min:
        return None
    return (x_min, y_min, x_max, y_max), str(decoded or "")


def _expand_bbox(bbox: tuple[int, int, int, int], size: tuple[int, int]) -> tuple[int, int, int, int]:
    x_min, y_min, x_max, y_max = bbox
    width, height = size
    side = max(x_max - x_min, y_max - y_min)
    margin = max(8, int(side * 0.14))
    return (
        max(0, x_min - margin),
        max(0, y_min - margin),
        min(width, x_max + margin),
        min(height, y_max + margin),
    )


def _paste_qr_crop(
    output_image: Image.Image,
    crop: Image.Image,
    *,
    placement: str,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    canvas = output_image.convert("RGBA")
    qr = crop.convert("RGBA")
    target_size = _target_qr_size(canvas.size, qr.size)
    if qr.size != target_size:
        qr = qr.resize(target_size, Image.Resampling.NEAREST)
    padding = max(10, int(min(canvas.size) * 0.012))
    margin = max(24, int(min(canvas.size) * 0.04))
    x, y = _placement_xy(canvas.size, qr.size, padding=padding, margin=margin, placement=placement)
    backing = Image.new("RGBA", (qr.width + padding * 2, qr.height + padding * 2), (255, 255, 255, 255))
    backing.paste(qr, (padding, padding), qr)
    canvas.paste(backing, (x - padding, y - padding), backing)
    return canvas, (x - padding, y - padding, x + qr.width + padding, y + qr.height + padding)


def _target_qr_size(canvas_size: tuple[int, int], qr_size: tuple[int, int]) -> tuple[int, int]:
    min_canvas = min(canvas_size)
    max_side = max(96, int(min_canvas * 0.3))
    min_side = max(80, int(min_canvas * 0.12))
    qr_width, qr_height = qr_size
    longest = max(qr_width, qr_height)
    if min_side <= longest <= max_side:
        return qr_size
    target_longest = max(min_side, min(max_side, longest))
    if longest > max_side:
        target_longest = max_side
    scale = target_longest / float(longest)
    return max(1, int(qr_width * scale)), max(1, int(qr_height * scale))


def _placement_xy(
    canvas_size: tuple[int, int],
    qr_size: tuple[int, int],
    *,
    padding: int,
    margin: int,
    placement: str,
) -> tuple[int, int]:
    width, height = canvas_size
    qr_width, qr_height = qr_size
    backing_width = qr_width + padding * 2
    backing_height = qr_height + padding * 2
    right = width - margin - backing_width
    left = margin
    top = margin
    bottom = height - margin - backing_height
    center_x = max(margin, (width - backing_width) // 2)
    center_y = max(margin, (height - backing_height) // 2)
    positions = {
        "top_left": (left, top),
        "top_right": (right, top),
        "bottom_left": (left, bottom),
        "bottom_center": (center_x, bottom),
        "top_center": (center_x, top),
        "center": (center_x, center_y),
        "bottom_right": (right, bottom),
    }
    backing_x, backing_y = positions.get(placement, positions["bottom_right"])
    backing_x = max(0, min(width - backing_width, backing_x))
    backing_y = max(0, min(height - backing_height, backing_y))
    return backing_x + padding, backing_y + padding


def _placement_from_metadata(metadata: dict[str, Any]) -> str:
    text = ""
    try:
        text = json.dumps(
            {
                "user_prompt": metadata.get("user_prompt"),
                "input_images": metadata.get("input_images"),
                "provider_input_plan": metadata.get("provider_input_plan"),
            },
            ensure_ascii=False,
        ).lower()
    except TypeError:
        text = str(metadata).lower()
    checks = [
        ("top_left", ("左上", "top left")),
        ("top_right", ("右上", "top right")),
        ("bottom_left", ("左下", "bottom left")),
        ("bottom_center", ("底部居中", "下方居中", "bottom center")),
        ("top_center", ("顶部居中", "top center")),
        ("bottom_right", ("右下", "bottom right")),
    ]
    for placement, markers in checks:
        if any(marker in text for marker in markers):
            return placement
    return "bottom_right"


def _pil_format(output_format: str, mime_type: str) -> str:
    normalized = f"{output_format} {mime_type}".lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return "JPEG"
    if "webp" in normalized:
        return "WEBP"
    return "PNG"
