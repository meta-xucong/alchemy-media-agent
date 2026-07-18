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
    reference_policy: dict[str, Any] | None = None,
    portrait_identity_derivative_kinds: list[str] | tuple[str, ...] | None = None,
) -> list[dict[str, Any]]:
    """Create provider-only focused references without changing the user's upload.

    Professional serial anchor stages may provide a bounded derivative list for
    an already-prepared root identity anchor.  The default remains the legacy
    complementary feature-detail plus head-geometry pair for every portrait
    source, so Standard Mode and ordinary reference-conditioned jobs are
    unchanged.
    """
    try:
        source = Path(str(path))
        if not source.exists() or not source.is_file():
            return []
        layers = {str(item).strip() for item in (truth_layers or []) if str(item).strip()}
        if not layers:
            return []
        derivatives: list[dict[str, Any]] = []
        if "portrait_identity_truth" in layers:
            allowed_kinds = {
                "portrait_identity_crop",
                "portrait_identity_geometry_crop",
                "portrait_identity_pose_geometry_crop",
            }
            requested_kinds = (
                tuple(portrait_identity_derivative_kinds)
                if portrait_identity_derivative_kinds is not None
                else ("portrait_identity_crop", "portrait_identity_geometry_crop")
            )
            if any(kind not in allowed_kinds for kind in requested_kinds):
                return []
            face_box = (
                _detect_primary_face_box(source)
                if any(
                    _identity_channel_isolation_profile(reference_policy, kind=kind).get("applies")
                    for kind in requested_kinds
                )
                else None
            )
            derivatives.extend(
                _truth_derivative(
                    source,
                    asset_id=asset_id,
                    kind=kind,
                    reference_policy=reference_policy,
                    normalized_face_box=face_box,
                )
                for kind in requested_kinds
            )
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


def _truth_derivative(
    source: Path,
    *,
    asset_id: str,
    kind: str,
    reference_policy: dict[str, Any] | None = None,
    normalized_face_box: tuple[float, float, float, float] | None = None,
) -> dict[str, Any]:
    isolation = _identity_channel_isolation_profile(reference_policy, kind=kind)
    face_localized = bool(isolation.get("applies") and normalized_face_box)
    if face_localized:
        isolation["normalized_face_box"] = normalized_face_box
    try:
        target = _cropped_reference_path(source, kind=kind, identity_isolation=isolation)
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
        "portrait_identity_pose_geometry_crop": "portrait_identity_truth",
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
        "identity_color_neutralized": kind in {
            "portrait_identity_crop",
            "portrait_identity_geometry_crop",
            "portrait_identity_pose_geometry_crop",
        } and not fallback,
        "identity_color_retention": (
            0.90
            if kind == "portrait_identity_crop"
            else 0.65
            if kind == "portrait_identity_geometry_crop"
            else 0.58
            if kind == "portrait_identity_pose_geometry_crop"
            else None
        ),
        "identity_outer_color_retention": isolation.get("outer_color_retention") if not fallback else None,
        "identity_channel_isolation_applied": bool(isolation.get("applies")) and not fallback,
        "identity_channel_isolation_profile": (
            "face_localized_prompt_owned_channel_isolation_v3"
            if face_localized and not fallback
            else isolation.get("profile_id")
            if not fallback
            else None
        ),
        "identity_face_localization_applied": face_localized and not fallback,
        "identity_face_localization_status": (
            "detected"
            if face_localized and not fallback
            else "heuristic_fallback"
            if isolation.get("applies") and not fallback
            else "not_applicable"
        ),
        "identity_nonidentity_pixel_suppression_profile": (
            "face_localized_nonidentity_suppression_v1"
            if face_localized and not fallback
            else "exterior_context_isolation_v2"
            if isolation.get("applies") and not fallback
            else None
        ),
        "identity_prompt_owned_channels": list(isolation.get("prompt_owned_channels") or []) if not fallback else [],
        "identity_outer_context_softened": bool(isolation.get("soften_outer_context")) and not fallback,
        "identity_outer_context_neutralized": bool(isolation.get("neutralize_outer_context")) and not fallback,
        "identity_background_neutralized": False,
        "identity_context_reduced_by_tight_crop": kind in {
            "portrait_identity_crop",
            "portrait_identity_geometry_crop",
            "portrait_identity_pose_geometry_crop",
        } and not fallback,
        "identity_evidence_scope": (
            "feature_detail"
            if kind == "portrait_identity_crop"
            else "head_geometry"
            if kind == "portrait_identity_geometry_crop"
            else "pose_geometry"
            if kind == "portrait_identity_pose_geometry_crop"
            else None
        ),
        "identity_gateway_min_edge_px": 512 if kind in {
            "portrait_identity_crop",
            "portrait_identity_geometry_crop",
            "portrait_identity_pose_geometry_crop",
        } and not fallback else None,
        "provider_only": True,
    }


def _cropped_reference_path(
    source: Path,
    *,
    kind: str,
    identity_isolation: dict[str, Any] | None = None,
) -> Path:
    try:
        from PIL import Image, ImageOps
    except ModuleNotFoundError:
        return source

    max_bytes = max(128_000, int(settings.openai_image_reference_max_upload_bytes))
    if kind in {
        "portrait_identity_crop",
        "portrait_identity_geometry_crop",
        "portrait_identity_pose_geometry_crop",
    }:
        max_bytes = min(max_bytes, 480_000)
    max_edge = max(512, int(settings.openai_image_reference_max_edge))
    quality = min(95, max(50, int(settings.openai_image_reference_jpeg_quality)))
    stat = source.stat()
    isolation = dict(identity_isolation or {})
    isolation_key = str(isolation.get("cache_key") or "legacy")
    normalized_face_box = _coerce_normalized_face_box(isolation.get("normalized_face_box"))
    face_key = ",".join(f"{value:.6f}" for value in normalized_face_box) if normalized_face_box else "none"
    digest = hashlib.sha256(
        f"{source.resolve()}:{stat.st_size}:{stat.st_mtime_ns}:{kind}:doc163-face-localized-evidence-v3:{isolation_key}:{face_key}:{max_bytes}:{max_edge}:{quality}".encode("utf-8")
    ).hexdigest()[:24]
    cache_dir = settings.media_storage_root / "provider_reference_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / f"{source.stem}-{kind}-{digest}.jpg"
    if target.exists() and target.stat().st_size <= max_bytes:
        return target

    with Image.open(source) as raw:
        image = ImageOps.exif_transpose(raw)
        image = _to_rgb_on_white(image, Image)
        box = _truth_crop_box(image.size, kind, normalized_face_box=normalized_face_box)
        cropped = image.crop(box)
        if kind in {
            "portrait_identity_crop",
            "portrait_identity_geometry_crop",
            "portrait_identity_pose_geometry_crop",
        }:
            from PIL import ImageEnhance

            color_retention = (
                0.90
                if kind == "portrait_identity_crop"
                else 0.65
                if kind == "portrait_identity_geometry_crop"
                else 0.58
            )
            if isolation.get("applies"):
                face_box_in_crop = _normalized_face_box_in_crop(
                    normalized_face_box,
                    source_size=image.size,
                    crop_box=box,
                )
                cropped = _isolate_prompt_owned_identity_channels(
                    cropped,
                    kind=kind,
                    face_color_retention=color_retention,
                    outer_color_retention=float(isolation.get("outer_color_retention") or 0.0),
                    normalized_face_box=face_box_in_crop,
                )
            else:
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


def _identity_channel_isolation_profile(
    reference_policy: dict[str, Any] | None,
    *,
    kind: str,
) -> dict[str, Any]:
    policy = dict(reference_policy or {})
    if kind not in {
        "portrait_identity_crop",
        "portrait_identity_geometry_crop",
        "portrait_identity_pose_geometry_crop",
    } or not policy:
        return {"applies": False, "profile_id": "legacy_identity_evidence", "cache_key": "legacy"}
    prompt_owned = {
        str(item)
        for item in policy.get("prompt_owned_channels", [])
        if str(item).strip()
    }
    for channel in (
        "hair_direction",
        "makeup_style",
        "wardrobe_structure",
        "accessory_system",
        "lighting_color",
        "scene_background",
        "camera_composition",
        "mood_art_direction",
        "style_finish",
    ):
        if str(policy.get(channel) or "") in {"prompt_owned", "off"}:
            prompt_owned.add(channel)
    isolation_channels = sorted(
        prompt_owned
        & {
            "hair_direction",
            "makeup_style",
            "wardrobe_structure",
            "accessory_system",
            "lighting_color",
            "scene_background",
            "camera_composition",
            "mood_art_direction",
            "style_finish",
        }
    )
    hair_is_assigned = str(policy.get("hair_direction") or "") in {"hard", "medium", "soft"}
    applies = (
        bool(isolation_channels)
        and str(policy.get("source_role") or "") == "portrait_identity_reference"
        and not hair_is_assigned
    )
    outer_retention = (
        0.03
        if kind == "portrait_identity_crop"
        else 0.01
        if kind == "portrait_identity_pose_geometry_crop"
        else 0.015
    )
    return {
        "applies": applies,
        "profile_id": "prompt_owned_channel_isolation_v2" if applies else "assigned_channel_preservation_v1",
        "cache_key": (
            "prompt-owned-v2:" + ",".join(isolation_channels)
            if applies
            else "assigned-v1"
        ),
        "prompt_owned_channels": isolation_channels,
        "outer_color_retention": outer_retention if applies else None,
        "soften_outer_context": applies,
        "neutralize_outer_context": applies,
    }


def _isolate_prompt_owned_identity_channels(
    image,
    *,
    kind: str,
    face_color_retention: float,
    outer_color_retention: float,
    normalized_face_box: tuple[float, float, float, float] | None = None,
):
    from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

    face = ImageEnhance.Color(image).enhance(face_color_retention)
    outer = ImageEnhance.Color(image).enhance(outer_color_retention)
    outer = ImageEnhance.Contrast(outer).enhance(0.20)
    neutral = Image.new("RGB", image.size, color=(236, 236, 236))
    outer = Image.blend(outer, neutral, 0.86)
    blur_radius = max(1.0, min(image.size) * (0.015 if kind == "portrait_identity_crop" else 0.019))
    outer = outer.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    mask = Image.new("L", image.size, color=0)
    draw = ImageDraw.Draw(mask)
    width, height = image.size
    face_box = _coerce_normalized_face_box(normalized_face_box)
    if face_box:
        x, y, face_width, face_height = face_box
        if kind == "portrait_identity_crop":
            expansion = (0.12, 0.04, 0.12, 0.10)
        elif kind == "portrait_identity_pose_geometry_crop":
            expansion = (0.28, 0.08, 0.28, 0.16)
        else:
            expansion = (0.22, 0.06, 0.22, 0.12)
        left = max(0.0, x - face_width * expansion[0])
        top = max(0.0, y - face_height * expansion[1])
        right = min(1.0, x + face_width * (1.0 + expansion[2]))
        bottom = min(1.0, y + face_height * (1.0 + expansion[3]))
        box = (width * left, height * top, width * right, height * bottom)
    elif kind == "portrait_identity_crop":
        box = (width * 0.24, height * 0.15, width * 0.76, height * 0.66)
    elif kind == "portrait_identity_pose_geometry_crop":
        # Keep the contour and view cues (ears, neck and shoulder direction)
        # available for a supplementary stage, while still fading prompt-owned
        # hair/wardrobe/light/scene channels outside the face region.
        box = (width * 0.15, height * 0.11, width * 0.85, height * 0.88)
    else:
        box = (width * 0.18, height * 0.12, width * 0.82, height * 0.78)
    draw.ellipse(tuple(int(round(value)) for value in box), fill=255)
    feather = max(4.0, min(image.size) * 0.045)
    mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
    return Image.composite(face, outer, mask)


def _truth_crop_box(
    size: tuple[int, int],
    kind: str,
    *,
    normalized_face_box: tuple[float, float, float, float] | None = None,
) -> tuple[int, int, int, int]:
    width, height = size
    if width <= 0 or height <= 0:
        return (0, 0, max(1, width), max(1, height))
    face_box = _coerce_normalized_face_box(normalized_face_box)
    if face_box and kind in {
        "portrait_identity_crop",
        "portrait_identity_geometry_crop",
        "portrait_identity_pose_geometry_crop",
    }:
        x, y, face_width, face_height = face_box
        if kind == "portrait_identity_crop":
            margins = (0.42, 0.35, 0.42, 0.28)
        elif kind == "portrait_identity_pose_geometry_crop":
            margins = (0.74, 0.52, 0.74, 0.48)
        else:
            margins = (0.62, 0.45, 0.62, 0.38)
        return _clamp_crop_box(
            (
                int(round((x - face_width * margins[0]) * width)),
                int(round((y - face_height * margins[1]) * height)),
                int(round((x + face_width * (1.0 + margins[2])) * width)),
                int(round((y + face_height * (1.0 + margins[3])) * height)),
            ),
            size,
        )
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
    elif kind == "portrait_identity_pose_geometry_crop":
        if height > width * 1.15:
            crop_w = int(width * 0.94)
            crop_h = int(height * 0.76)
            center_x = width * 0.5
            center_y = height * 0.40
        elif width > height * 1.15:
            crop_w = int(width * 0.68)
            crop_h = int(height * 0.96)
            center_x = width * 0.5
            center_y = height * 0.46
        else:
            crop_w = int(width * 0.84)
            crop_h = int(height * 0.70)
            center_x = width * 0.5
            center_y = height * 0.38
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


def _coerce_normalized_face_box(value: Any) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        x, y, width, height = (float(item) for item in value)
    except (TypeError, ValueError):
        return None
    if width <= 0.0 or height <= 0.0:
        return None
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    width = max(0.0, min(1.0 - x, width))
    height = max(0.0, min(1.0 - y, height))
    return (x, y, width, height) if width > 0.0 and height > 0.0 else None


def _clamp_crop_box(
    box: tuple[int, int, int, int],
    size: tuple[int, int],
) -> tuple[int, int, int, int]:
    width, height = size
    left, top, right, bottom = box
    left = max(0, min(max(0, width - 1), left))
    top = max(0, min(max(0, height - 1), top))
    right = max(left + 1, min(width, right))
    bottom = max(top + 1, min(height, bottom))
    return (left, top, right, bottom)


def _normalized_face_box_in_crop(
    face_box: tuple[float, float, float, float] | None,
    *,
    source_size: tuple[int, int],
    crop_box: tuple[int, int, int, int],
) -> tuple[float, float, float, float] | None:
    normalized = _coerce_normalized_face_box(face_box)
    if not normalized:
        return None
    source_width, source_height = source_size
    left, top, right, bottom = crop_box
    crop_width = max(1, right - left)
    crop_height = max(1, bottom - top)
    x, y, width, height = normalized
    return _coerce_normalized_face_box(
        (
            (x * source_width - left) / crop_width,
            (y * source_height - top) / crop_height,
            width * source_width / crop_width,
            height * source_height / crop_height,
        )
    )


def _detect_primary_face_box(source: Path) -> tuple[float, float, float, float] | None:
    """Return one ephemeral normalized face box; never persist landmarks or vectors."""
    try:
        import cv2 as cv

        model_path = Path(settings.v3_identity_model_dir) / "face_detection_yunet_2023mar.onnx"
        if not model_path.is_file():
            return None
        image = cv.imread(str(source))
        if image is None:
            return None
        height, width = image.shape[:2]
        detector = cv.FaceDetectorYN.create(str(model_path), "", (width, height), 0.5, 0.3, 5000)
        _status, faces = detector.detect(image)
        if faces is None or len(faces) == 0:
            return None
        face = max(
            faces,
            key=lambda item: float(item[2] * item[3]) * max(0.1, float(item[-1])),
        )
        return _coerce_normalized_face_box(
            (
                float(face[0]) / max(1, width),
                float(face[1]) / max(1, height),
                float(face[2]) / max(1, width),
                float(face[3]) / max(1, height),
            )
        )
    except Exception:
        return None


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
