from __future__ import annotations

import io
import hashlib
from dataclasses import dataclass
from typing import Any

from PIL import Image, ImageOps, ImageChops

from app.services.uploaded_assets import uploaded_asset_path




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
    source_sha256: str = ""


class _QrSkip(ValueError):
    """An unverifiable optional enhancement leaves its baseline untouched."""


def preserve_requested_qr_code(
    *, content: bytes, metadata: dict[str, Any], output_format: str,
    mime_type: str, _qr_preservation_enabled: bool = False,
) -> QrPreservationResult:
    """Only an internal Brain permission may enter this optional pixel stage."""
    if _qr_preservation_enabled is not True:
        return QrPreservationResult(content=content)
    receipt: dict[str, Any] = {"requested": True, "applied": False}
    try:
        source_images, placement = _authorized_qr_target(metadata)
        source_crop = _first_qr_crop(source_images)
        if source_crop is None or not source_crop.decoded_text:
            raise _QrSkip("source_not_decodable")
        receipt.update({
            "decoded": True, "source_asset_id": source_crop.asset_id,
            "source_bbox": list(source_crop.bbox), "source_sha256": source_crop.source_sha256,
            "pre_qr_sha256": hashlib.sha256(content).hexdigest(), "processing_version": "qr_opt_in_v1",
        })
        with Image.open(io.BytesIO(content)) as raw:
            if getattr(raw, "n_frames", 1) != 1 or raw.mode not in {"RGB", "RGBA"}:
                raise _QrSkip("image_invariant_failed")
            if raw.getexif().get(274, 1) != 1:
                raise _QrSkip("image_invariant_failed")
            fmt = _pil_format(output_format, mime_type)
            if raw.format != fmt:
                raise _QrSkip("image_invariant_failed")
            # These PNG rendering chunks are not retained by the current
            # encoder path. Pixel-array equality alone cannot prove equal color.
            if raw.format == "PNG" and any(key in raw.info for key in ("gamma", "chromaticity", "srgb")):
                raise _QrSkip("unsupported_color_metadata")
            original_mode = raw.mode
            image_info = {k: raw.info[k] for k in ("icc_profile", "exif") if raw.info.get(k)}
            original = raw.convert("RGBA")
        qr_size = _target_qr_size(original.size, source_crop.image.size)
        padding = max(10, int(min(original.size) * 0.012))
        margin = max(24, int(min(original.size) * 0.04))
        x, y = _placement_xy(original.size, qr_size, padding=padding, margin=margin, placement=placement)
        target = (x-padding, y-padding, x+qr_size[0]+padding, y+qr_size[1]+padding)
        if not _valid_qr_box(target, original.size):
            raise _QrSkip("target_unresolved")
        receipt.update({"paste_box": list(target), "placement": placement})
        if _composed_qr_decodes(original, target, source_crop.decoded_text):
            receipt.update({"reason": "already_satisfied", "verified_decoded": True})
            return QrPreservationResult(content=content, metadata=receipt)
        if fmt == "JPEG":
            raise _QrSkip("unsupported_lossless_edit")
        composed, paste_box = _paste_qr_crop(original.copy(), source_crop.image, placement=placement)
        if paste_box != target or composed.size != original.size:
            raise _QrSkip("image_invariant_failed")
        buffer = io.BytesIO()
        candidate = composed.convert(original_mode)
        if fmt == "WEBP":
            candidate.save(buffer, format="WEBP", lossless=True, exact=True, **image_info)
        else:
            candidate.save(buffer, format="PNG", **image_info)
        candidate_bytes = buffer.getvalue()
        with Image.open(io.BytesIO(candidate_bytes)) as saved:
            if saved.size != original.size or saved.format != fmt or getattr(saved, "n_frames", 1) != 1:
                raise _QrSkip("image_invariant_failed")
            verified = saved.convert("RGBA")
        difference = ImageChops.difference(original, verified)
        difference.paste((0, 0, 0, 0), target)
        if any(band.getbbox() is not None for band in difference.split()):
            raise _QrSkip("image_invariant_failed")
        if not _composed_qr_decodes(verified, target, source_crop.decoded_text):
            raise _QrSkip("postprocess_verification_failed")
        receipt.update({"applied": True, "verified_decoded": True,
            "method": "authorized_qr_slot_overlay", "processed_sha256": hashlib.sha256(candidate_bytes).hexdigest()})
        return QrPreservationResult(content=candidate_bytes, metadata=receipt)
    except _QrSkip as exc:
        receipt["reason"] = str(exc)
    except Exception as exc:
        # Cancellation/SystemExit and core output-storage errors are not swallowed.
        receipt.update({"reason": "qr_exception", "error_type": type(exc).__name__})
    return QrPreservationResult(content=content, metadata=receipt)


def _authorized_qr_target(metadata: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    intent = metadata.get("orchestrator_task_intent")
    slots = intent.get("slot_plan") if isinstance(intent, dict) else None
    targets = [s for s in slots if isinstance(s, dict) and s.get("slot") == "qr_code"] if isinstance(slots, list) else []
    if len(targets) != 1:
        raise _QrSkip("target_ambiguous" if targets else "target_unresolved")
    target = targets[0]
    placement = target.get("rule")
    allowed = {"top_left", "top_right", "bottom_left", "bottom_right", "top_center", "bottom_center", "center"}
    if target.get("target_surface") != "poster" or not isinstance(placement, str) or placement not in allowed:
        raise _QrSkip("target_unresolved")
    inputs = metadata.get("input_images")
    inputs = [i for i in inputs if isinstance(i, dict) and isinstance(i.get("asset_id"), str) and i["asset_id"]] if isinstance(inputs, list) else []
    selected = target.get("source_asset_id")
    if selected is not None:
        if not isinstance(selected, str) or not selected:
            raise _QrSkip("source_ambiguous")
        inputs = [i for i in inputs if i["asset_id"] == selected]
    unique = {i["asset_id"]: i for i in inputs}
    if len(unique) != 1:
        raise _QrSkip("source_ambiguous" if unique else "source_not_decodable")
    return list(unique.values()), placement


def _valid_qr_box(box: Any, size: tuple[int, int]) -> bool:
    return (isinstance(box, (list, tuple)) and len(box) == 4
        and all(isinstance(v, int) and not isinstance(v, bool) for v in box)
        and 0 <= box[0] < box[2] <= size[0] and 0 <= box[1] < box[3] <= size[1])


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
    # The caller has resolved one current, authorized source before pixel work.
    if len(input_images) != 1 or not isinstance(input_images[0], dict):
        raise _QrSkip("source_ambiguous")
    asset_id = input_images[0].get("asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        return None
    path = uploaded_asset_path(asset_id)
    if path is None or not path.is_file():
        return None
    source_bytes = path.read_bytes()
    with Image.open(io.BytesIO(source_bytes)) as raw:
        if getattr(raw, "n_frames", 1) != 1:
            raise _QrSkip("source_visibility_unverified")
        visible_source = ImageOps.exif_transpose(raw).convert("RGBA")
        if visible_source.getchannel("A").getextrema()[0] < 255:
            # Do not turn hidden RGB under alpha into visible source truth.
            raise _QrSkip("source_visibility_unverified")
        source = visible_source.convert("RGB")
    detected = _detect_qr_bbox(source)
    if detected is None or not isinstance(detected[1], str) or not detected[1]:
        return None
    bbox, decoded = detected
    if not _valid_qr_box(bbox, source.size):
        raise _QrSkip("crop_invalid")
    crop_box = _expand_bbox(bbox, source.size)
    crop = source.crop(crop_box)
    if min(crop.size) < 24:
        raise _QrSkip("crop_invalid")
    checked = _detect_qr_bbox(crop)
    if checked is None or checked[1] != decoded:
        raise _QrSkip("crop_invalid")
    return _QrCrop(asset_id=asset_id, image=crop, bbox=crop_box,
        decoded_text=decoded, source_sha256=hashlib.sha256(source_bytes).hexdigest())


def _detect_qr_bbox(image: Image.Image) -> tuple[tuple[int, int, int, int], str] | None:
    try:
        import cv2  # type: ignore[import-not-found]
        import numpy as np  # type: ignore[import-not-found]
    except Exception:
        return None
    detector = cv2.QRCodeDetector()
    detected = _detect_qr_bbox_on_image(image, detector=detector, cv2=cv2, np=np)
    if detected and detected[1]:
        return detected
    candidates: list[tuple[tuple[int, int, int, int], str]] = []
    for zone in _qr_search_zones(image.size):
        crop = image.crop(zone)
        detected = _detect_qr_bbox_on_image(crop, detector=detector, cv2=cv2, np=np)
        if not detected or not detected[1]:
            continue
        bbox, decoded = detected
        x_min, y_min, x_max, y_max = bbox
        zone_x, zone_y, _, _ = zone
        absolute = (x_min + zone_x, y_min + zone_y, x_max + zone_x, y_max + zone_y)
        duplicate = any(
            text == decoded
            and max(box[0], absolute[0]) < min(box[2], absolute[2])
            and max(box[1], absolute[1]) < min(box[3], absolute[3])
            for box, text in candidates
        )
        if not duplicate:
            candidates.append((absolute, decoded))
        if len(candidates) > 1:
            raise _QrSkip("source_ambiguous")
    return candidates[0] if candidates else None


def _detect_qr_bbox_on_image(image: Image.Image, *, detector: Any, cv2: Any, np: Any) -> tuple[tuple[int, int, int, int], str] | None:
    array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    found, texts, multi_points, _ = detector.detectAndDecodeMulti(array)
    if multi_points is not None and len(multi_points) > 1:
        # Do not fall through into zone searches and silently select one code.
        raise _QrSkip("source_ambiguous")
    if found and multi_points is not None and len(multi_points) == 1:
        decoded, points = texts[0], multi_points[0]
    else:
        decoded, points, _ = detector.detectAndDecode(array)
    if points is None:
        return None
    pts = points.reshape(-1, 2)
    if pts.shape != (4, 2) or not np.isfinite(pts).all():
        return None
    box = (max(0, int(pts[:, 0].min())), max(0, int(pts[:, 1].min())),
        min(image.width, int(pts[:, 0].max()) + 1), min(image.height, int(pts[:, 1].max()) + 1))
    if not _valid_qr_box(box, image.size):
        return None
    return box, decoded if isinstance(decoded, str) else ""


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


def _composed_qr_decodes(image: Image.Image, paste_box: tuple[int, int, int, int], expected: str) -> bool:
    # Only this exact target can certify the operation; never another whole-image QR.
    if not expected or not _valid_qr_box(paste_box, image.size):
        return False
    try:
        detected = _detect_qr_bbox(image.crop(paste_box).convert("RGB"))
    except _QrSkip as exc:
        raise _QrSkip("target_ambiguous") from exc
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





def _pil_format(output_format: str, mime_type: str) -> str:
    normalized = f"{output_format} {mime_type}".lower()
    if "jpeg" in normalized or "jpg" in normalized:
        return "JPEG"
    if "webp" in normalized:
        return "WEBP"
    return "PNG"
