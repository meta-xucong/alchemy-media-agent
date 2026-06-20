from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.alchemy_lab_uploads_models import LabUploadedAsset


def analyze_lab_uploaded_asset(asset: LabUploadedAsset, path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {
            "asset_id": asset.asset_id,
            "role": asset.role or "style_material_reference",
            "visual_summary": "上传参考图尚未保存到本地。",
            "usable_as_input_image": False,
            "warnings": ["asset_file_missing"],
        }
    try:
        from PIL import Image, ImageOps

        with Image.open(path) as image:
            image = ImageOps.exif_transpose(image)
            width, height = image.size
            mode = image.mode
            palette = _palette_preview(image)
    except Exception as exc:
        return {
            "asset_id": asset.asset_id,
            "role": asset.role or _suggest_role(asset),
            "visual_summary": "上传参考图可作为约束，但本地视觉分析失败。",
            "usable_as_input_image": True,
            "warnings": ["local_analysis_failed", f"{type(exc).__name__}: {str(exc)[:160]}"],
        }
    role = asset.role or _suggest_role(asset)
    return {
        "asset_id": asset.asset_id,
        "role": role,
        "visual_summary": _summary(asset, role=role, width=width, height=height),
        "usable_as_input_image": True,
        "warnings": [],
        "image": {
            "width": width,
            "height": height,
            "mode": mode,
            "aspect_ratio": round(width / height, 4) if height else None,
        },
        "palette": palette,
    }


def _suggest_role(asset: LabUploadedAsset) -> str:
    text = f"{asset.filename} {asset.intended_use or ''}".lower()
    if any(marker in text for marker in ["logo", "brand", "标识", "商标", "品牌"]):
        return "logo_reference"
    if any(marker in text for marker in ["product", "package", "商品", "产品", "包装"]):
        return "product_reference"
    if any(marker in text for marker in ["material", "texture", "color", "材质", "纹理", "色彩"]):
        return "style_material_reference"
    if any(marker in text for marker in ["composition", "layout", "构图", "版式"]):
        return "composition_reference"
    return "subject_reference"


def _summary(asset: LabUploadedAsset, *, role: str, width: int, height: int) -> str:
    labels = {
        "subject_reference": "主体/商品参考",
        "product_reference": "产品参考",
        "logo_reference": "Logo/标识参考",
        "style_material_reference": "材质/色彩参考",
        "composition_reference": "构图参考",
        "negative_reference": "反向参考",
    }
    label = labels.get(role, "参考图")
    return f"{label}，{width}x{height}，用于稀有风格探索中的可选视觉约束。"


def _palette_preview(image) -> list[dict[str, Any]]:
    try:
        sample = image.convert("RGB")
        sample.thumbnail((64, 64))
        colors = sample.getcolors(maxcolors=64 * 64) or []
        colors = sorted(colors, key=lambda item: item[0], reverse=True)[:5]
        total = sum(count for count, _ in colors) or 1
        return [
            {
                "hex": "#%02x%02x%02x" % rgb,
                "weight": round(count / total, 3),
            }
            for count, rgb in colors
        ]
    except Exception:
        return []
