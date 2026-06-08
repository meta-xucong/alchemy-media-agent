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
            information_dense = _information_integrity_active(metadata)
            placement = _placement_from_metadata(metadata, information_dense=information_dense)
            output_placeholder = _detect_qr_bbox(output_image.convert("RGB"))
            if output_placeholder and _placeholder_safe_for_qr(output_placeholder[0], output_image.size, information_dense):
                composed, paste_box = _paste_qr_crop_to_bbox(
                    output_image,
                    source_crop.image,
                    output_placeholder[0],
                    information_dense=information_dense,
                )
                method = "detected_output_qr_placeholder_overlay"
                placement_value = "detected_output_qr_zone"
            else:
                base_image = (
                    _cover_bbox_with_light_card(output_image, output_placeholder[0])
                    if output_placeholder and information_dense
                    else output_image
                )
                composed, paste_box = _paste_qr_crop(
                    base_image,
                    source_crop.image,
                    placement=placement,
                    information_dense=information_dense,
                )
                method = "unsafe_output_qr_repositioned" if output_placeholder and information_dense else "detected_qr_crop_overlay"
                placement_value = placement
            save_format = _pil_format(output_format, mime_type)
            verified_decoded = _composed_qr_decodes(composed, paste_box, source_crop.decoded_text)
            saved = io.BytesIO()
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
            "method": method,
            "source_asset_id": source_crop.asset_id,
            "decoded": bool(source_crop.decoded_text),
            "verified_decoded": verified_decoded,
            "source_bbox": list(source_crop.bbox),
            "placement": placement_value,
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


def _information_integrity_active(metadata: dict[str, Any]) -> bool:
    if metadata.get("information_integrity_lock_enabled") is True:
        return True
    contract = metadata.get("information_integrity_contract")
    if isinstance(contract, dict) and contract.get("active"):
        return True
    grammar = metadata.get("visual_grammar_contract")
    if isinstance(grammar, dict):
        info = grammar.get("information_integrity")
        if isinstance(info, dict) and info.get("active"):
            return True
        source_layout_risk = grammar.get("source_layout_risk")
        if isinstance(source_layout_risk, dict) and source_layout_risk.get("detected"):
            return True
    return False


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
    detector = cv2.QRCodeDetector()
    detected = _detect_qr_bbox_on_image(image, detector=detector, cv2=cv2, np=np)
    if detected:
        return detected
    for zone in _qr_search_zones(image.size):
        crop = image.crop(zone)
        detected = _detect_qr_bbox_on_image(crop, detector=detector, cv2=cv2, np=np)
        if not detected:
            continue
        bbox, decoded = detected
        x_min, y_min, x_max, y_max = bbox
        zone_x, zone_y, _, _ = zone
        return (x_min + zone_x, y_min + zone_y, x_max + zone_x, y_max + zone_y), decoded
    return None


def _detect_qr_bbox_on_image(
    image: Image.Image,
    *,
    detector: Any,
    cv2: Any,
    np: Any,
) -> tuple[tuple[int, int, int, int], str] | None:
    rgb = image.convert("RGB")
    array = cv2.cvtColor(np.array(rgb), cv2.COLOR_RGB2BGR)
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


def _qr_search_zones(size: tuple[int, int]) -> list[tuple[int, int, int, int]]:
    width, height = size
    return [
        (int(width * 0.76), int(height * 0.08), width, int(height * 0.62)),
        (int(width * 0.62), 0, width, int(height * 0.52)),
        (int(width * 0.58), int(height * 0.42), width, int(height * 0.86)),
        (int(width * 0.52), int(height * 0.55), width, height),
        (0, int(height * 0.55), width, height),
    ]


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
    information_dense: bool = False,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    canvas = output_image.convert("RGBA")
    qr = crop.convert("RGBA")
    target_size = _target_qr_size(canvas.size, qr.size, max_side_ratio=0.18 if information_dense else 0.3)
    if qr.size != target_size:
        qr = qr.resize(target_size, Image.Resampling.NEAREST)
    padding = max(10, int(min(canvas.size) * 0.012))
    margin = max(24, int(min(canvas.size) * 0.04))
    x, y = _placement_xy(canvas.size, qr.size, padding=padding, margin=margin, placement=placement)
    backing = Image.new("RGBA", (qr.width + padding * 2, qr.height + padding * 2), (255, 255, 255, 255))
    backing.paste(qr, (padding, padding), qr)
    canvas.paste(backing, (x - padding, y - padding), backing)
    return canvas, (x - padding, y - padding, x + qr.width + padding, y + qr.height + padding)


def _paste_qr_crop_to_bbox(
    output_image: Image.Image,
    crop: Image.Image,
    bbox: tuple[int, int, int, int],
    *,
    information_dense: bool = False,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    canvas = output_image.convert("RGBA")
    qr = crop.convert("RGBA")
    x_min, y_min, x_max, y_max = bbox
    preferred_longest = max(80, x_max - x_min, y_max - y_min)
    min_canvas = min(canvas.size)
    max_longest = max(96, int(min_canvas * (0.2 if information_dense else 0.32)))
    source_detection = _detect_qr_bbox(qr.convert("RGB"))
    source_decoded = source_detection[1] if source_detection else ""
    min_longest = min(max_longest, max(80, int(preferred_longest * 0.72)))
    for longest in _qr_size_candidates(
        preferred_longest=preferred_longest,
        source_longest=max(qr.size),
        min_longest=min_longest,
        max_longest=max_longest,
    ):
        candidate_qr = _resize_preserving_aspect(qr, longest)
        candidate_detection = _detect_qr_bbox(candidate_qr.convert("RGB"))
        if not candidate_detection or not candidate_detection[1]:
            continue
        composed, paste_box = _compose_qr_crop_at_bbox(canvas, candidate_qr, bbox)
        composed_detection = _detect_qr_bbox(composed.convert("RGB"))
        if composed_detection and composed_detection[1] and (
            not source_decoded or composed_detection[1] == source_decoded
        ):
            return composed, paste_box
    qr = _resize_qr_crop_for_decoding(qr, preferred_longest=preferred_longest, max_longest=max_longest)
    return _compose_qr_crop_at_bbox(canvas, qr, bbox)


def _placeholder_safe_for_qr(
    bbox: tuple[int, int, int, int],
    canvas_size: tuple[int, int],
    information_dense: bool,
) -> bool:
    if not information_dense:
        return True
    x_min, y_min, x_max, y_max = bbox
    width, height = canvas_size
    box_width = x_max - x_min
    box_height = y_max - y_min
    center_x = (x_min + x_max) / 2
    center_y = (y_min + y_max) / 2
    right_rail_card = (
        x_min >= width * 0.76
        and y_min >= height * 0.08
        and y_max <= height * 0.62
        and box_width <= width * 0.23
        and box_height <= height * 0.28
    )
    if right_rail_card:
        return True
    return (
        center_x >= width * 0.55
        and center_y >= height * 0.52
        and box_width <= width * 0.24
        and box_height <= height * 0.22
    )


def _cover_bbox_with_light_card(
    image: Image.Image,
    bbox: tuple[int, int, int, int],
) -> Image.Image:
    canvas = image.convert("RGBA")
    x_min, y_min, x_max, y_max = bbox
    side = max(x_max - x_min, y_max - y_min)
    margin = max(8, int(side * 0.08))
    box = (
        max(0, x_min - margin),
        max(0, y_min - margin),
        min(canvas.width, x_max + margin),
        min(canvas.height, y_max + margin),
    )
    cover = Image.new("RGBA", (box[2] - box[0], box[3] - box[1]), (255, 252, 246, 255))
    canvas.paste(cover, (box[0], box[1]), cover)
    return canvas


def _composed_qr_decodes(
    image: Image.Image,
    paste_box: tuple[int, int, int, int],
    expected: str,
) -> bool:
    if not expected:
        return False
    whole = _detect_qr_bbox(image.convert("RGB"))
    if whole and whole[1] == expected:
        return True
    x_min, y_min, x_max, y_max = paste_box
    margin = max(12, int(max(x_max - x_min, y_max - y_min) * 0.18))
    crop_box = (
        max(0, x_min - margin),
        max(0, y_min - margin),
        min(image.width, x_max + margin),
        min(image.height, y_max + margin),
    )
    crop = image.crop(crop_box)
    detected = _detect_qr_bbox(crop.convert("RGB"))
    return bool(detected and detected[1] == expected)


def _compose_qr_crop_at_bbox(
    canvas: Image.Image,
    qr: Image.Image,
    bbox: tuple[int, int, int, int],
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    canvas = canvas.convert("RGBA")
    x_min, y_min, x_max, y_max = bbox
    qr_longest = max(qr.size)
    padding = max(8, int(qr_longest * 0.08))
    backing = Image.new("RGBA", (qr.width + padding * 2, qr.height + padding * 2), (255, 255, 255, 255))
    backing.paste(qr, (padding, padding), qr)
    center_x = (x_min + x_max) // 2
    center_y = (y_min + y_max) // 2
    paste_x = center_x - backing.width // 2
    paste_y = center_y - backing.height // 2
    paste_x = max(0, min(canvas.width - backing.width, paste_x))
    paste_y = max(0, min(canvas.height - backing.height, paste_y))
    canvas.paste(backing, (paste_x, paste_y), backing)
    return canvas, (paste_x, paste_y, paste_x + backing.width, paste_y + backing.height)


def _resize_qr_crop_for_decoding(qr: Image.Image, *, preferred_longest: int, max_longest: int) -> Image.Image:
    source_longest = max(qr.size)
    min_longest = min(max_longest, max(80, int(preferred_longest * 0.72)))
    candidates = _qr_size_candidates(
        preferred_longest=preferred_longest,
        source_longest=source_longest,
        min_longest=min_longest,
        max_longest=max_longest,
    )
    fallback = _resize_preserving_aspect(qr, max(min_longest, min(max_longest, preferred_longest)))
    fallback_detected = _detect_qr_bbox(fallback.convert("RGB"))
    for longest in candidates:
        resized = _resize_preserving_aspect(qr, longest)
        detected = _detect_qr_bbox(resized.convert("RGB"))
        if detected and detected[1]:
            return resized
        if detected and not fallback_detected:
            fallback = resized
            fallback_detected = detected
    return fallback


def _qr_size_candidates(
    *,
    preferred_longest: int,
    source_longest: int,
    min_longest: int,
    max_longest: int,
) -> list[int]:
    values: list[int] = []
    upper = min(max_longest, max(preferred_longest + 96, source_longest, 260))
    lower = max(80, min_longest)
    for offset in range(0, 97):
        values.append(preferred_longest + offset)
        if offset:
            values.append(preferred_longest - offset)
    values.extend(
        [
            source_longest,
            260,
            256,
            240,
            230,
            224,
            200,
            max(80, min(max_longest, preferred_longest)),
        ]
    )
    seen: set[int] = set()
    candidates: list[int] = []
    for value in values:
        longest = int(value)
        if longest < lower or longest > upper or longest in seen:
            continue
        seen.add(longest)
        candidates.append(longest)
    return candidates


def _resize_preserving_aspect(image: Image.Image, target_longest: int) -> Image.Image:
    width, height = image.size
    longest = max(width, height)
    if longest <= 0 or longest == target_longest:
        return image.copy()
    scale = target_longest / float(longest)
    target_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return image.resize(target_size, Image.Resampling.NEAREST)


def _target_qr_size(
    canvas_size: tuple[int, int],
    qr_size: tuple[int, int],
    *,
    max_side_ratio: float = 0.3,
) -> tuple[int, int]:
    min_canvas = min(canvas_size)
    max_side = max(96, int(min_canvas * max_side_ratio))
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
        "right_lower": (right, max(top, min(bottom, int(height * 0.62)))),
        "bottom_right": (right, bottom),
    }
    backing_x, backing_y = positions.get(placement, positions["bottom_right"])
    backing_x = max(0, min(width - backing_width, backing_x))
    backing_y = max(0, min(height - backing_height, backing_y))
    return backing_x + padding, backing_y + padding


def _placement_from_metadata(metadata: dict[str, Any], *, information_dense: bool = False) -> str:
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
        ("right_lower", ("右侧下方", "右下侧", "lower right side", "right lower")),
        ("bottom_right", ("右下", "bottom right")),
    ]
    for placement, markers in checks:
        if any(marker in text for marker in markers):
            return placement
    if information_dense:
        return "right_lower"
    return "bottom_right"


def _pil_format(output_format: str, mime_type: str) -> str:
    normalized = f"{output_format} {mime_type}".lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return "JPEG"
    if "webp" in normalized:
        return "WEBP"
    return "PNG"
