"""SVG render-spec builder for V3 commercial poster overlays."""

from __future__ import annotations

from typing import Any

from .render_spec import build_base_render_spec, escaped_text
from ..schemas import LayoutPlan


def build_svg_render_spec(layout_plan: LayoutPlan) -> dict[str, Any]:
    spec = build_base_render_spec(layout_plan, renderer="svg_spec_renderer")
    canvas = spec["canvas"]
    text_nodes = "\n".join(_text_node(layer) for layer in spec["text_layers"])
    spec["svg"] = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas["width"]}" height="{canvas["height"]}" '
        f'viewBox="0 0 {canvas["width"]} {canvas["height"]}" role="img" '
        f'aria-label="{escaped_text(layout_plan.asset_id)} commercial poster">\n'
        '  <rect width="100%" height="100%" fill="#f7f7f2"/>\n'
        f"{text_nodes}\n"
        "</svg>"
    )
    spec["composition_output"] = {
        "format": "svg",
        "root": "svg",
        "requires_external_assets": False,
    }
    return spec


def _text_node(layer: dict[str, Any]) -> str:
    bounds = layer["bounds_px"]
    typography = layer["typography"]
    family = ", ".join(typography["font_family"])
    x = bounds["x"] + bounds["w"] / 2
    y = bounds["y"] + bounds["h"] / 2
    return (
        f'  <text id="{escaped_text(layer["layer_id"])}" '
        f'x="{x:.0f}" y="{y:.0f}" dominant-baseline="middle" text-anchor="middle" '
        f'font-family="{escaped_text(family)}" font-size="{typography["font_size_px"]}" '
        f'font-weight="{typography["font_weight"]}" '
        f'data-editable="true" data-role="{escaped_text(layer["role"])}">'
        f'{escaped_text(layer["content"])}</text>'
    )
