"""Typography defaults for V3 external text rendering."""

DEFAULT_CHINESE_TYPOGRAPHY = {
    "headline": "large readable bold commercial title",
    "cta": "clear button-like commercial call to action",
    "body": "high legibility supporting text",
}


DEFAULT_CHINESE_FONT_STACK = [
    "Noto Sans SC",
    "Microsoft YaHei",
    "PingFang SC",
    "Heiti SC",
    "Arial",
    "sans-serif",
]


TYPOGRAPHY_LAYER_PRESETS = {
    "headline": {
        "font_weight": 800,
        "font_size_ratio": 0.056,
        "line_height": 1.12,
        "align": "center",
    },
    "subtitle": {
        "font_weight": 500,
        "font_size_ratio": 0.032,
        "line_height": 1.24,
        "align": "center",
    },
    "cta": {
        "font_weight": 700,
        "font_size_ratio": 0.034,
        "line_height": 1.18,
        "align": "center",
    },
    "logo": {
        "font_weight": 700,
        "font_size_ratio": 0.022,
        "line_height": 1.1,
        "align": "left",
    },
    "body": {
        "font_weight": 500,
        "font_size_ratio": 0.026,
        "line_height": 1.28,
        "align": "center",
    },
}


def typography_for_role(role: str, canvas_height: int) -> dict:
    preset = TYPOGRAPHY_LAYER_PRESETS.get(role, TYPOGRAPHY_LAYER_PRESETS["body"])
    return {
        "font_family": DEFAULT_CHINESE_FONT_STACK,
        "font_weight": preset["font_weight"],
        "font_size_px": max(18, round(canvas_height * preset["font_size_ratio"])),
        "line_height": preset["line_height"],
        "align": preset["align"],
    }
