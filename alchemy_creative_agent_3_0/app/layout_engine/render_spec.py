"""Shared helpers for deterministic V3 poster render specs."""

from __future__ import annotations

from html import escape
from typing import Any

from .typography import typography_for_role
from ..schemas import LayoutPlan, LayoutRegion


ASPECT_RATIO_DIMENSIONS = {
    "1:1": {"width": 1080, "height": 1080},
    "3:4": {"width": 1080, "height": 1440},
    "4:5": {"width": 1080, "height": 1350},
    "9:16": {"width": 1080, "height": 1920},
    "16:9": {"width": 1920, "height": 1080},
    "A4": {"width": 1240, "height": 1754},
}


def canvas_dimensions(aspect_ratio: str) -> dict[str, int]:
    normalized = aspect_ratio.strip().upper()
    return dict(ASPECT_RATIO_DIMENSIONS.get(normalized, ASPECT_RATIO_DIMENSIONS["4:5"]))


def text_regions(layout_plan: LayoutPlan) -> list[LayoutRegion]:
    regions: list[LayoutRegion] = []
    seen: set[tuple[object, ...]] = set()
    for region in [
        layout_plan.headline_area,
        layout_plan.subtitle_area,
        layout_plan.cta_area,
        *layout_plan.reserved_text_regions,
        layout_plan.logo_area if layout_plan.logo_area and layout_plan.logo_area.text else None,
    ]:
        if region is None:
            continue
        region_key = _region_identity(region)
        if region_key not in seen:
            regions.append(region)
            seen.add(region_key)
    return regions


def _region_identity(region: LayoutRegion) -> tuple[object, ...]:
    box = region.relative_box or {}
    box_key = tuple((key, box[key]) for key in sorted(box))
    return (region.name, region.position, region.text, box_key)


def role_for_region(region: LayoutRegion) -> str:
    name = region.name.lower()
    if "headline" in name or "title" in name:
        return "headline"
    if "subtitle" in name:
        return "subtitle"
    if "cta" in name or "offer" in name:
        return "cta"
    if "logo" in name or "brand" in name:
        return "logo"
    return "body"


def normalized_box(region: LayoutRegion) -> dict[str, float]:
    raw = region.relative_box or {}
    x = _clamp(float(raw.get("x", 0.0)))
    y = _clamp(float(raw.get("y", 0.0)))
    w = _clamp(float(raw.get("w", 1.0 - x)), minimum=0.01)
    h = _clamp(float(raw.get("h", 0.1)), minimum=0.01)
    if x + w > 1.0:
        w = max(0.01, 1.0 - x)
    if y + h > 1.0:
        h = max(0.01, 1.0 - y)
    return {"x": round(x, 4), "y": round(y, 4), "w": round(w, 4), "h": round(h, 4)}


def pixel_box(region: LayoutRegion, canvas: dict[str, int]) -> dict[str, int]:
    box = normalized_box(region)
    width = canvas["width"]
    height = canvas["height"]
    return {
        "x": round(box["x"] * width),
        "y": round(box["y"] * height),
        "w": round(box["w"] * width),
        "h": round(box["h"] * height),
    }


def build_text_layers(layout_plan: LayoutPlan) -> list[dict[str, Any]]:
    canvas = canvas_dimensions(layout_plan.aspect_ratio)
    layers: list[dict[str, Any]] = []
    for index, region in enumerate(text_regions(layout_plan), start=1):
        role = role_for_region(region)
        content = region.text if region.text is not None else ""
        layers.append(
            {
                "layer_id": f"{layout_plan.asset_id}_{role}_{index}",
                "source_region_name": region.name,
                "role": role,
                "editable": True,
                "content": content,
                "preserve_exact_text": True,
                "position": region.position,
                "priority": region.priority,
                "bounds_pct": normalized_box(region),
                "bounds_px": pixel_box(region, canvas),
                "typography": typography_for_role(role, canvas["height"]),
                "z_index": 20 + index,
                "notes": region.notes,
                "metadata": region.metadata,
            }
        )
    return layers


def build_background_layer(layout_plan: LayoutPlan) -> dict[str, Any]:
    canvas = canvas_dimensions(layout_plan.aspect_ratio)
    return {
        "layer_id": f"{layout_plan.asset_id}_base_visual",
        "role": "base_visual",
        "editable": False,
        "bounds_pct": {"x": 0.0, "y": 0.0, "w": 1.0, "h": 1.0},
        "bounds_px": {"x": 0, "y": 0, "w": canvas["width"], "h": canvas["height"]},
        "source": "image_generation_candidate_or_placeholder",
        "notes": layout_plan.background_strategy,
        "z_index": 0,
    }


def build_base_render_spec(layout_plan: LayoutPlan, renderer: str) -> dict[str, Any]:
    text_layers = build_text_layers(layout_plan)
    return {
        "renderer": renderer,
        "runtime_mode": "spec_only",
        "layout_plan_id": layout_plan.layout_plan_id,
        "asset_id": layout_plan.asset_id,
        "platform": layout_plan.platform,
        "aspect_ratio": layout_plan.aspect_ratio,
        "canvas": canvas_dimensions(layout_plan.aspect_ratio),
        "text_rendering": layout_plan.text_rendering,
        "text_layers": text_layers,
        "text_regions": [region.model_dump(mode="json") for region in text_regions(layout_plan)],
        "layers": [build_background_layer(layout_plan), *text_layers],
        "editable_text_layer_count": len(text_layers),
        "preserves_exact_text": all(layer["preserve_exact_text"] for layer in text_layers),
        "metadata": {
            "render_spec_version": "v3.3-render-spec-001",
            "typography_strategy": layout_plan.typography_strategy,
            "visual_hierarchy": layout_plan.visual_hierarchy,
            "source": "LayoutPlan",
        },
    }


def css_style(layer: dict[str, Any]) -> str:
    bounds = layer["bounds_pct"]
    typography = layer["typography"]
    family = ", ".join(typography["font_family"])
    return (
        "position:absolute;"
        f"left:{bounds['x'] * 100:.4f}%;"
        f"top:{bounds['y'] * 100:.4f}%;"
        f"width:{bounds['w'] * 100:.4f}%;"
        f"height:{bounds['h'] * 100:.4f}%;"
        "display:flex;align-items:center;justify-content:center;"
        f"text-align:{typography['align']};"
        f"font-family:{family};"
        f"font-size:{typography['font_size_px']}px;"
        f"font-weight:{typography['font_weight']};"
        f"line-height:{typography['line_height']};"
        "white-space:pre-wrap;overflow:hidden;"
    )


def escaped_text(value: str) -> str:
    return escape(value, quote=True)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return min(maximum, max(minimum, value))
