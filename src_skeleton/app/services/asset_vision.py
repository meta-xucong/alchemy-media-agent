from __future__ import annotations

from collections import Counter
from colorsys import rgb_to_hsv
from pathlib import Path
from typing import Any

from app.schemas import Asset, AssetVisionProfile
from app.services.utils import now_iso
from app.storage import media_store


ROLE_LABELS = {
    "style_reference": "风格参考",
    "subject_reference": "主体参考",
    "logo_overlay": "Logo/标识",
    "portrait_identity": "人物脸/身份",
    "background_reference": "背景参考",
    "composition_reference": "构图参考",
    "local_edit": "局部修改",
    "negative_reference": "反向参考",
}


def analyze_asset_image(asset: Asset) -> AssetVisionProfile:
    created_at = now_iso()
    if not asset.mime_type.startswith("image/"):
        return AssetVisionProfile(
            asset_id=asset.id,
            status="skipped",
            summary="非图片素材已跳过视觉理解。",
            recommended_roles=_recommended_roles(asset, has_alpha=False),
            created_at=created_at,
        )

    path = media_store.find_asset_file(asset.id)
    if not path:
        return AssetVisionProfile(
            asset_id=asset.id,
            status="skipped",
            summary="图片文件尚未写入本地存储，暂时只能使用用户声明的素材用途。",
            image={"filename": asset.filename, "stored": False},
            recommended_roles=_recommended_roles(asset, has_alpha=False),
            created_at=created_at,
        )

    try:
        from PIL import Image, ImageOps, ImageStat

        with Image.open(path) as raw_image:
            image = ImageOps.exif_transpose(raw_image)
            width, height = image.size
            has_alpha = _has_alpha(image)
            rgb = _flatten_to_rgb(image)
            sample = rgb.copy()
            sample.thumbnail((96, 96), Image.Resampling.LANCZOS)
            palette = _palette(sample)
            color_roles = _color_roles(palette)
            luminance = _luminance(sample, ImageStat)
            contrast = _contrast(sample, ImageStat)
            orientation = _orientation(width, height)
            style = {
                "palette": palette,
                "dominant_color": palette[0]["hex"] if palette else None,
                **color_roles,
                "brightness": round(luminance, 3),
                "brightness_label": _brightness_label(luminance),
                "contrast": round(contrast, 3),
                "contrast_label": _contrast_label(contrast),
                "has_transparency": has_alpha,
                "texture_hint": _texture_hint(contrast),
                "style_keywords": _style_keywords(color_roles=color_roles, luminance=luminance, contrast=contrast),
            }
            composition = {
                "orientation": orientation,
                "aspect_ratio": round(width / height, 3) if height else None,
                "width": width,
                "height": height,
                "safe_area_hint": _safe_area_hint(orientation),
            }
            logo_candidates = _logo_candidates(asset, has_alpha=has_alpha, path=path)
            faces = _face_candidates(asset)
            subjects = _subject_candidates(asset, logo_candidates=logo_candidates, faces=faces)
            summary = _summary(
                width=width,
                height=height,
                orientation=orientation,
                style=style,
                asset=asset,
            )
            return AssetVisionProfile(
                asset_id=asset.id,
                status="ready",
                summary=summary,
                image={
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "stored": True,
                    "path_name": path.name,
                    "width": width,
                    "height": height,
                },
                style=style,
                composition=composition,
                subjects=subjects,
                logo_candidates=logo_candidates,
                faces=faces,
                risks=_risks(asset, logo_candidates=logo_candidates, faces=faces),
                recommended_roles=_recommended_roles(asset, has_alpha=has_alpha),
                created_at=created_at,
            )
    except Exception as exc:
        return AssetVisionProfile(
            asset_id=asset.id,
            status="failed",
            summary="本地视觉理解失败，已退回用户声明的素材用途。",
            image={"filename": asset.filename, "stored": True},
            recommended_roles=_recommended_roles(asset, has_alpha=False),
            error={"type": type(exc).__name__, "message": str(exc)[:300]},
            created_at=created_at,
        )


def _flatten_to_rgb(image):
    from PIL import Image

    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.getchannel("A"))
        return canvas
    return image.convert("RGB")


def _has_alpha(image) -> bool:
    return image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info)


def _palette(image, *, limit: int = 18) -> list[dict[str, Any]]:
    resized = image.convert("RGB").resize((32, 32))
    raw = resized.tobytes()
    data = [(raw[index], raw[index + 1], raw[index + 2]) for index in range(0, len(raw), 3)]
    if not data:
        return []
    bucketed = Counter((_bucket(r), _bucket(g), _bucket(b)) for r, g, b in data)
    total = sum(bucketed.values()) or 1
    colors = []
    for (r, g, b), count in bucketed.most_common(limit):
        colors.append(
            {
                "hex": f"#{r:02x}{g:02x}{b:02x}",
                "rgb": [r, g, b],
                "ratio": round(count / total, 3),
            }
        )
    return colors


def _bucket(value: int) -> int:
    return max(0, min(255, int(round(value / 32) * 32)))


def _color_roles(palette: list[dict[str, Any]]) -> dict[str, Any]:
    if not palette:
        return {
            "background_color": None,
            "accent_colors": [],
            "dark_accent_colors": [],
            "warm_metal_colors": [],
        }
    dominant = palette[0]
    dominant_rgb = dominant.get("rgb") or [0, 0, 0]
    candidates = []
    for item in palette[1:]:
        rgb = item.get("rgb") or [0, 0, 0]
        r, g, b = [int(value) for value in rgb[:3]]
        hue, saturation, value = rgb_to_hsv(r / 255, g / 255, b / 255)
        luminance = _relative_luminance(r, g, b)
        distance = _rgb_distance(rgb, dominant_rgb)
        ratio = float(item.get("ratio") or 0)
        candidates.append(
            {
                **item,
                "hue": round(hue, 3),
                "saturation": round(saturation, 3),
                "value": round(value, 3),
                "luminance": round(luminance, 3),
                "distance_from_dominant": round(distance, 3),
                "salience": round(ratio * (0.55 + saturation + distance), 4),
            }
        )

    accent_colors = _select_color_candidates(
        candidates,
        predicate=lambda item: item["ratio"] >= 0.004 and item["saturation"] >= 0.28 and (item["distance_from_dominant"] >= 0.2 or item["luminance"] <= 0.4),
        limit=5,
    )
    dark_accent_colors = _select_color_candidates(
        candidates,
        predicate=lambda item: item["ratio"] >= 0.004 and item["luminance"] <= 0.34 and item["saturation"] >= 0.24,
        limit=3,
    )
    warm_metal_colors = _select_color_candidates(
        candidates,
        predicate=lambda item: item["ratio"] >= 0.004 and 0.07 <= item["hue"] <= 0.16 and item["saturation"] >= 0.38 and item["value"] >= 0.45,
        limit=3,
    )
    return {
        "background_color": dominant.get("hex"),
        "accent_colors": accent_colors,
        "dark_accent_colors": dark_accent_colors,
        "warm_metal_colors": warm_metal_colors,
    }


def _select_color_candidates(candidates: list[dict[str, Any]], *, predicate, limit: int) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in sorted(candidates, key=lambda candidate: (candidate["salience"], candidate["ratio"]), reverse=True):
        if not predicate(item):
            continue
        color = str(item.get("hex") or "")
        if not color or color in seen:
            continue
        seen.add(color)
        selected.append(
            {
                "hex": color,
                "ratio": item.get("ratio"),
                "salience": item.get("salience"),
            }
        )
        if len(selected) >= limit:
            break
    return selected


def _relative_luminance(r: int, g: int, b: int) -> float:
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _rgb_distance(rgb: list[int], base_rgb: list[int]) -> float:
    try:
        r, g, b = [int(value) for value in rgb[:3]]
        base_r, base_g, base_b = [int(value) for value in base_rgb[:3]]
    except (TypeError, ValueError):
        return 0.0
    return min((((r - base_r) ** 2 + (g - base_g) ** 2 + (b - base_b) ** 2) ** 0.5) / 441.673, 1.0)


def _style_keywords(*, color_roles: dict[str, Any], luminance: float, contrast: float) -> list[str]:
    keywords: list[str] = []
    if luminance >= 0.62:
        keywords.append("明亮柔和")
    elif luminance <= 0.32:
        keywords.append("低调暗色")
    if contrast <= 0.24:
        keywords.append("干净低对比")
    elif contrast >= 0.52:
        keywords.append("高对比层次")
    if color_roles.get("dark_accent_colors"):
        keywords.append("深色高级强调")
    if color_roles.get("warm_metal_colors"):
        keywords.append("暖金/琥珀点缀")
    return keywords


def _luminance(image, image_stat) -> float:
    stat = image_stat.Stat(image.convert("L"))
    return float(stat.mean[0]) / 255.0


def _contrast(image, image_stat) -> float:
    stat = image_stat.Stat(image.convert("L"))
    return min(float(stat.stddev[0]) / 128.0, 1.0)


def _orientation(width: int, height: int) -> str:
    if width == height:
        return "square"
    return "landscape" if width > height else "portrait"


def _brightness_label(value: float) -> str:
    if value >= 0.72:
        return "bright"
    if value <= 0.32:
        return "dark"
    return "balanced"


def _contrast_label(value: float) -> str:
    if value >= 0.55:
        return "high"
    if value <= 0.2:
        return "low"
    return "medium"


def _texture_hint(contrast: float) -> str:
    if contrast >= 0.55:
        return "rich detail or strong edge contrast"
    if contrast <= 0.2:
        return "clean, flat, or soft texture"
    return "moderate texture detail"


def _safe_area_hint(orientation: str) -> str:
    if orientation == "portrait":
        return "keep subject hierarchy clear and reserve vertical negative space when text or logo is required"
    if orientation == "landscape":
        return "use horizontal depth and keep key subject away from crowded side edges"
    return "balance central subject placement with clean margins"


def _logo_candidates(asset: Asset, *, has_alpha: bool, path: Path) -> list[dict[str, Any]]:
    filename = asset.filename.lower()
    if asset.declared_role == "logo_overlay" or "logo" in filename or "brand" in filename or has_alpha:
        return [
            {
                "confidence": 0.72 if has_alpha else 0.62,
                "source": "filename_or_alpha",
                "hint": "可能是需要保持清晰边缘和透明通道的品牌/标识素材。",
                "path_name": path.name,
            }
        ]
    return []


def _face_candidates(asset: Asset) -> list[dict[str, Any]]:
    if asset.declared_role == "portrait_identity":
        return [
            {
                "confidence": 0.6,
                "source": "declared_role",
                "hint": "用户声明为人物脸/身份参考，生成时应走图片引用链路并控制身份漂移。",
            }
        ]
    return []


def _subject_candidates(asset: Asset, *, logo_candidates: list[dict[str, Any]], faces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if logo_candidates:
        label = "品牌/标识素材"
    elif faces:
        label = "人物身份参考素材"
    elif asset.declared_role:
        label = f"{ROLE_LABELS.get(asset.declared_role, asset.declared_role)}素材"
    else:
        label = "用户上传图片素材"
    return [{"label": label, "source": "declared_role_and_file_metadata", "confidence": 0.55}]


def _risks(asset: Asset, *, logo_candidates: list[dict[str, Any]], faces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    risks = []
    if logo_candidates:
        risks.append({"code": "logo_integrity", "message": "Logo/标识建议通过后处理叠加，避免生图模型重绘导致变形。"})
    if faces:
        risks.append({"code": "identity_drift", "message": "人物脸参考需要 provider 图片输入支持，且仍需复检身份漂移。"})
    if asset.declared_role in {"subject_reference", "portrait_identity"}:
        risks.append({"code": "prompt_only_insufficient", "message": "主体/人物保真不能只靠提示词，必须传入参考图片。"})
    return risks


def _recommended_roles(asset: Asset, *, has_alpha: bool) -> list[str]:
    roles: list[str] = []
    if asset.declared_role:
        roles.append(asset.declared_role)
    if asset.mime_type.startswith("image/"):
        roles.extend(["style_reference", "composition_reference", "background_reference"])
    filename = asset.filename.lower()
    if "logo" in filename or "brand" in filename or has_alpha:
        roles.append("logo_overlay")
    if asset.declared_role == "portrait_identity":
        roles.append("portrait_identity")
    elif asset.mime_type.startswith("image/") and "logo" not in filename:
        roles.append("subject_reference")
    return sorted(set(roles))


def _summary(*, width: int, height: int, orientation: str, style: dict[str, Any], asset: Asset) -> str:
    role = ROLE_LABELS.get(asset.declared_role or "", "图片素材")
    dominant = style.get("dominant_color") or "unknown"
    accents = _hex_list(style.get("accent_colors") or [])
    dark_accents = _hex_list(style.get("dark_accent_colors") or [])
    warm_metals = _hex_list(style.get("warm_metal_colors") or [])
    brightness = _zh_label(style.get("brightness_label"), {"bright": "明亮", "dark": "偏暗", "balanced": "均衡"})
    contrast = _zh_label(style.get("contrast_label"), {"high": "高", "low": "低", "medium": "中等"})
    orientation_label = _zh_label(orientation, {"square": "方图", "portrait": "竖图", "landscape": "横图"})
    parts = [
        f"{role}，{width}x{height}",
        f"{orientation_label}构图",
        f"主色 {dominant}",
    ]
    if accents:
        parts.append(f"强调色 {'、'.join(accents[:4])}")
    if dark_accents:
        parts.append(f"深色强调 {'、'.join(dark_accents[:3])}")
    if warm_metals:
        parts.append(f"暖金/琥珀点缀 {'、'.join(warm_metals[:3])}")
    parts.extend([f"{brightness}亮度", f"{contrast}对比度"])
    return "，".join(parts) + "。"


def _hex_list(values: list[Any]) -> list[str]:
    colors: list[str] = []
    for item in values:
        if isinstance(item, dict):
            value = item.get("hex")
        else:
            value = item
        text = str(value or "").strip()
        if text:
            colors.append(text)
    return colors


def _zh_label(value: Any, labels: dict[str, str]) -> str:
    return labels.get(str(value), str(value or ""))
