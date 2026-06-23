"""Render manifest helpers for V3.3 editable poster output."""

from __future__ import annotations

from typing import Any

from ..layout_engine.html_renderer import build_html_render_spec
from ..layout_engine.svg_renderer import build_svg_render_spec
from ..schemas import LayoutPlan, TextRenderingMode


def render_spec_for_layout(layout_plan: LayoutPlan) -> dict[str, Any]:
    if layout_plan.text_rendering == TextRenderingMode.SVG_OVERLAY:
        return build_svg_render_spec(layout_plan)
    return build_html_render_spec(layout_plan)


def render_manifest_entry(layout_plan: LayoutPlan) -> dict[str, Any]:
    render_spec = render_spec_for_layout(layout_plan)
    return {
        "layout_plan_id": layout_plan.layout_plan_id,
        "asset_id": layout_plan.asset_id,
        "renderer": render_spec["renderer"],
        "runtime_mode": render_spec["runtime_mode"],
        "text_rendering": layout_plan.text_rendering,
        "canvas": render_spec["canvas"],
        "editable_text_layers": render_spec["text_layers"],
        "editable_text_layer_count": render_spec["editable_text_layer_count"],
        "preserves_exact_text": render_spec["preserves_exact_text"],
        "composition_output": render_spec["composition_output"],
        "render_spec": render_spec,
    }


def render_manifest(layout_plans: list[LayoutPlan]) -> dict[str, Any]:
    entries = [render_manifest_entry(layout_plan) for layout_plan in layout_plans]
    return {
        "render_manifest_version": "v3.3-render-manifest-001",
        "asset_count": len(entries),
        "assets": entries,
        "editable_text_layer_count": sum(entry["editable_text_layer_count"] for entry in entries),
        "preserves_exact_text": all(entry["preserves_exact_text"] for entry in entries),
    }
