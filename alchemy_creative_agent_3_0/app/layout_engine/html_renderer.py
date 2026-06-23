"""HTML render-spec builder for V3 commercial poster overlays."""

from __future__ import annotations

from typing import Any

from .render_spec import build_base_render_spec, css_style, escaped_text
from ..schemas import LayoutPlan


def build_html_render_spec(layout_plan: LayoutPlan) -> dict[str, Any]:
    spec = build_base_render_spec(layout_plan, renderer="html_spec_renderer")
    canvas = spec["canvas"]
    layer_html = "\n".join(_layer_html(layer) for layer in spec["text_layers"])
    spec["html"] = (
        f'<main class="v3-poster" data-asset-id="{escaped_text(layout_plan.asset_id)}" '
        f'style="position:relative;width:{canvas["width"]}px;height:{canvas["height"]}px;overflow:hidden;">\n'
        '  <section class="v3-base-visual" aria-label="generated base visual" '
        'style="position:absolute;inset:0;background:#f7f7f2;"></section>\n'
        f"{layer_html}\n"
        "</main>"
    )
    spec["composition_output"] = {
        "format": "html",
        "entrypoint": "main.v3-poster",
        "requires_external_assets": False,
    }
    return spec


def _layer_html(layer: dict[str, Any]) -> str:
    content = escaped_text(layer["content"])
    aria_label = escaped_text(f"{layer['role']} text layer")
    return (
        f'  <div class="v3-text-layer v3-text-{layer["role"]}" '
        f'data-layer-id="{escaped_text(layer["layer_id"])}" '
        f'data-editable="true" aria-label="{aria_label}" '
        f'style="{css_style(layer)}">{content}</div>'
    )
