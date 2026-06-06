from __future__ import annotations

from collections import Counter
from colorsys import rgb_to_hsv
from pathlib import Path
from typing import Any

from app.schemas import AssetBrief, ConstraintStrength, UploadedAsset


HARD_INPUT_ROLES = {"subject_reference", "logo_reference", "face_reference", "background_reference"}


def analyze_uploaded_asset(asset: UploadedAsset, path: Path | None) -> AssetBrief:
    role = asset.role or _suggest_role(asset, path)
    strength = asset.constraint_strength
    if not path or not path.exists():
        return AssetBrief(
            asset_id=asset.asset_id,
            role=role,
            constraint_strength=strength,
            visual_summary=f"Uploaded image `{asset.filename}` is not available on local storage yet.",
            identity_requirements=_identity_requirements(role),
            style_signals=[],
            usable_as_input_image=False,
            provider_input_required=_provider_input_required(role, strength),
            warnings=["asset_file_missing"],
        )
    try:
        from PIL import Image, ImageOps, ImageStat

        with Image.open(path) as raw:
            image = ImageOps.exif_transpose(raw)
            width, height = image.size
            rgb = _flatten_to_rgb(image)
            sample = rgb.copy()
            sample.thumbnail((96, 96), Image.Resampling.LANCZOS)
            palette = _palette(sample)
            brightness = _brightness(sample, ImageStat)
            contrast = _contrast(sample, ImageStat)
            accent_colors = _accent_colors(palette)
            composition = {
                "width": width,
                "height": height,
                "orientation": _orientation(width, height),
                "aspect_ratio": round(width / height, 3) if height else None,
            }
            style_signals = _style_signals(
                brightness=brightness,
                contrast=contrast,
                palette=palette,
                accent_colors=accent_colors,
                role=role,
            )
            return AssetBrief(
                asset_id=asset.asset_id,
                role=role,
                constraint_strength=strength,
                visual_summary=_summary(asset, role=role, width=width, height=height, style_signals=style_signals),
                identity_requirements=_identity_requirements(role),
                style_signals=style_signals,
                image={
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "width": width,
                    "height": height,
                    "stored": True,
                },
                palette=palette[:8],
                composition=composition,
                usable_as_input_image=True,
                provider_input_required=_provider_input_required(role, strength),
            )
    except Exception as exc:
        return AssetBrief(
            asset_id=asset.asset_id,
            role=role,
            constraint_strength=strength,
            visual_summary=f"Local visual analysis failed for uploaded image `{asset.filename}`.",
            identity_requirements=_identity_requirements(role),
            usable_as_input_image=True,
            provider_input_required=_provider_input_required(role, strength),
            warnings=["asset_vision_failed"],
            image={"filename": asset.filename, "stored": True},
            detected_text=[],
        ).model_copy(update={"warnings": ["asset_vision_failed", f"{type(exc).__name__}: {str(exc)[:160]}"]})


def _suggest_role(asset: UploadedAsset, path: Path | None) -> str:
    name = asset.filename.lower()
    if any(token in name for token in ["logo", "brand", "标志", "品牌"]):
        return "logo_reference"
    if any(token in name for token in ["face", "portrait", "headshot", "人像", "脸"]):
        return "face_reference"
    if any(token in name for token in ["background", "scene", "背景"]):
        return "background_reference"
    if any(token in name for token in ["style", "mood", "风格"]):
        return "style_reference"
    if path:
        try:
            from PIL import Image

            with Image.open(path) as image:
                if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
                    return "logo_reference"
        except Exception:
            pass
    return "subject_reference"


def _provider_input_required(role: str, strength: ConstraintStrength) -> bool:
    if role in HARD_INPUT_ROLES:
        return True
    return strength == "required" and role in {"style_reference", "composition_reference", "color_reference"}


def _identity_requirements(role: str) -> list[str]:
    if role == "subject_reference":
        return ["preserve visible subject identity", "preserve product shape and key proportions"]
    if role == "logo_reference":
        return ["preserve logo shape", "do not invent unreadable brand text"]
    if role == "face_reference":
        return ["preserve face identity cues", "avoid identity drift"]
    if role == "background_reference":
        return ["preserve requested background environment when compatible"]
    if role == "composition_reference":
        return ["preserve camera angle and spatial layout as an abstract guide"]
    if role == "color_reference":
        return ["preserve key palette and accent-color rhythm"]
    if role == "negative_reference":
        return ["avoid visual traits from this reference"]
    return ["use as soft aesthetic evidence only"]


def _flatten_to_rgb(image):
    from PIL import Image

    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    return image.convert("RGB")


def _palette(image, *, limit: int = 12) -> list[dict[str, Any]]:
    resized = image.convert("RGB").resize((32, 32))
    raw = resized.tobytes()
    pixels = [(raw[index], raw[index + 1], raw[index + 2]) for index in range(0, len(raw), 3)]
    if not pixels:
        return []
    counts = Counter((_bucket(r), _bucket(g), _bucket(b)) for r, g, b in pixels)
    total = sum(counts.values()) or 1
    return [
        {"hex": f"#{r:02x}{g:02x}{b:02x}", "rgb": [r, g, b], "ratio": round(count / total, 3)}
        for (r, g, b), count in counts.most_common(limit)
    ]


def _bucket(value: int) -> int:
    return max(0, min(255, int(round(value / 32) * 32)))


def _brightness(image, image_stat) -> float:
    stat = image_stat.Stat(image.convert("L"))
    return round((stat.mean[0] if stat.mean else 0) / 255.0, 3)


def _contrast(image, image_stat) -> float:
    stat = image_stat.Stat(image.convert("L"))
    return round((stat.stddev[0] if stat.stddev else 0) / 128.0, 3)


def _accent_colors(palette: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(palette) <= 1:
        return []
    accents: list[dict[str, Any]] = []
    dominant = palette[0].get("rgb") or [0, 0, 0]
    for item in palette[1:]:
        rgb = item.get("rgb") or [0, 0, 0]
        r, g, b = [int(value) for value in rgb[:3]]
        _, saturation, value = rgb_to_hsv(r / 255, g / 255, b / 255)
        distance = min((((r - dominant[0]) ** 2 + (g - dominant[1]) ** 2 + (b - dominant[2]) ** 2) ** 0.5) / 441.673, 1.0)
        if float(item.get("ratio") or 0) >= 0.006 and saturation >= 0.25 and distance >= 0.18:
            accents.append(item)
        if len(accents) >= 4:
            break
    return accents


def _style_signals(
    *,
    brightness: float,
    contrast: float,
    palette: list[dict[str, Any]],
    accent_colors: list[dict[str, Any]],
    role: str,
) -> list[str]:
    signals: list[str] = []
    if brightness >= 0.62:
        signals.append("bright clean lighting")
    elif brightness <= 0.32:
        signals.append("low-key dark lighting")
    if contrast >= 0.5:
        signals.append("high contrast visual structure")
    elif contrast <= 0.24:
        signals.append("soft low-contrast palette")
    if palette:
        signals.append(f"dominant color {palette[0]['hex']}")
    if accent_colors:
        signals.append("distinctive accent colors " + ", ".join(item["hex"] for item in accent_colors[:3]))
    if role in {"logo_reference", "subject_reference", "face_reference"}:
        signals.append("identity preservation required")
    return signals


def _orientation(width: int, height: int) -> str:
    if not width or not height:
        return "unknown"
    ratio = width / height
    if ratio > 1.12:
        return "landscape"
    if ratio < 0.88:
        return "portrait"
    return "square"


def _summary(asset: UploadedAsset, *, role: str, width: int, height: int, style_signals: list[str]) -> str:
    label = role.replace("_", " ")
    signals = "; ".join(style_signals[:4])
    return f"{label} image `{asset.filename}`, {width}x{height}. {signals}".strip()
