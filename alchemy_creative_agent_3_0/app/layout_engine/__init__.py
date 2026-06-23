"""V3 layout engine package."""

from typing import TYPE_CHECKING

from .html_renderer import build_html_render_spec
from .render_spec import build_text_layers, canvas_dimensions
from .svg_renderer import build_svg_render_spec

if TYPE_CHECKING:
    from .planner import LayoutPlanner

__all__ = ["LayoutPlanner", "build_html_render_spec", "build_svg_render_spec", "build_text_layers", "canvas_dimensions"]


def __getattr__(name: str):
    if name == "LayoutPlanner":
        from .planner import LayoutPlanner

        return LayoutPlanner
    raise AttributeError(name)
