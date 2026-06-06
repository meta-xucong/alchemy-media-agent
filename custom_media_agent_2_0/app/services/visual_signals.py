from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas import PromptCase


@dataclass(frozen=True)
class CaseVisualSignals:
    background_color_signals: list[str] = field(default_factory=list)
    accent_color_signals: list[str] = field(default_factory=list)
    material_signals: list[str] = field(default_factory=list)
    style_keywords: list[str] = field(default_factory=list)
    lighting_signals: list[str] = field(default_factory=list)
    composition_signals: list[str] = field(default_factory=list)
    color_tags: list[str] = field(default_factory=list)
    material_tags: list[str] = field(default_factory=list)
    style_tags: list[str] = field(default_factory=list)
    reusable_principles: list[str] = field(default_factory=list)
    brief: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "brief": self.brief,
            "background_color_signals": self.background_color_signals,
            "accent_color_signals": self.accent_color_signals,
            "material_signals": self.material_signals,
            "style_keywords": self.style_keywords,
            "lighting_signals": self.lighting_signals,
            "composition_signals": self.composition_signals,
            "reusable_principles": self.reusable_principles,
        }


def build_case_visual_signals(case: PromptCase) -> CaseVisualSignals:
    text = _case_search_text(case)
    background = _match_groups(
        text,
        [
            ("warm cream/beige background", ["beige", "cream", "ivory", "off white", "off-white", "warm neutral"]),
            ("soft white minimal background", ["white background", "clean white", "pure white", "minimal white"]),
            ("dark black/charcoal base", ["black background", "charcoal", "noir", "dark background", "deep black"]),
            ("pastel pink background", ["pastel pink", "blush", "rose background", "soft pink background"]),
            ("cool blue/cyan background", ["blue background", "cyan background", "icy blue", "cool blue"]),
        ],
    )
    accents = _match_groups(
        text,
        [
            ("deep green accent", ["emerald", "forest green", "deep green", "bottle green", "dark green"]),
            ("warm gold/amber metallic accent", ["gold", "golden", "brass", "bronze", "amber", "metallic gold", "gold foil"]),
            ("black/charcoal contrast accent", ["black accent", "charcoal accent", "black gold", "black-and-gold"]),
            ("crimson/red accent", ["crimson", "scarlet", "red accent", "ruby"]),
            ("electric blue/cyan accent", ["electric blue", "cyan accent", "neon blue", "blue accent"]),
            ("violet/purple accent", ["violet", "purple", "lavender"]),
            ("soft pink accent", ["pink accent", "soft pink", "blush"]),
            ("silver/chrome accent", ["silver", "chrome", "platinum", "mirror metal"]),
        ],
    )
    materials = _match_groups(
        text,
        [
            ("transparent glass/liquid highlights", ["glass", "transparent", "translucent", "liquid", "refraction"]),
            ("polished metal or foil detail", ["metal", "metallic", "chrome", "brass", "gold foil", "silver"]),
            ("soft fabric texture", ["fabric", "silk", "cloth", "textile", "velvet", "linen"]),
            ("paper/card print texture", ["paper", "card", "poster", "print", "label", "typography"]),
            ("ceramic or stone surface", ["ceramic", "marble", "stone", "porcelain"]),
            ("wood or natural grain", ["wood", "wooden", "grain", "natural texture"]),
            ("leather premium texture", ["leather", "suede"]),
        ],
    )
    styles = _match_groups(
        text,
        [
            ("premium luxury", ["premium", "luxury", "high end", "high-end", "elegant", "refined"]),
            ("minimal clean", ["minimal", "minimalist", "clean", "simple"]),
            ("editorial commercial", ["editorial", "campaign", "commercial", "advertising"]),
            ("cinematic dramatic", ["cinematic", "dramatic", "moody", "film"]),
            ("tech futuristic", ["futuristic", "technology", "cyber", "neon", "sci fi", "sci-fi"]),
            ("playful illustration", ["playful", "cute", "illustration", "illustrated"]),
            ("retro vintage", ["retro", "vintage", "nostalgic"]),
        ],
    )
    lighting = _match_groups(
        text,
        [
            ("soft studio lighting", ["soft studio", "studio lighting", "soft light", "diffused light"]),
            ("rim/back light separation", ["rim light", "backlight", "edge light", "halo"]),
            ("dramatic high contrast lighting", ["dramatic lighting", "high contrast", "chiaroscuro"]),
            ("natural daylight", ["natural light", "daylight", "sunlight"]),
            ("neon glow lighting", ["neon", "glow", "luminous"]),
        ],
    )
    composition = _match_groups(
        text,
        [
            ("centered hero product hierarchy", ["hero shot", "centered", "central product", "product hero"]),
            ("close-up material detail", ["close up", "close-up", "macro", "detail shot"]),
            ("flat lay / top-down layout", ["flat lay", "top down", "top-down", "overhead"]),
            ("poster layout with typography-safe space", ["poster", "typography", "copy space", "negative space"]),
            ("multi-card or annotated information layout", ["card", "cards", "annotation", "infographic", "feature sheet"]),
        ],
    )
    color_tags = _dedupe([*_labels_to_color_tags(background), *_labels_to_color_tags(accents)])
    material_tags = _dedupe(_labels_to_material_tags(materials))
    style_tags = _dedupe(_labels_to_style_tags(styles))
    principles = _build_principles(background, accents, materials, styles, lighting, composition)
    brief = _build_brief(background, accents, materials, styles, lighting, composition)
    return CaseVisualSignals(
        background_color_signals=background,
        accent_color_signals=accents,
        material_signals=materials,
        style_keywords=styles,
        lighting_signals=lighting,
        composition_signals=composition,
        color_tags=color_tags,
        material_tags=material_tags,
        style_tags=style_tags,
        reusable_principles=principles,
        brief=brief,
    )


def _case_search_text(case: PromptCase) -> str:
    parts: list[str] = [
        case.title,
        case.summary,
        case.raw_prompt,
        " ".join(case.style_tags),
        " ".join(case.use_case_tags),
        _flatten(case.prompt_atoms),
        _flatten(case.visual_features),
    ]
    return _normalize_text(" ".join(part for part in parts if part))


def _flatten(value: Any) -> str:
    parts: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            parts.append(str(key).replace("_", " "))
            parts.append(_flatten(child))
    elif isinstance(value, list):
        for child in value:
            parts.append(_flatten(child))
    elif value is not None:
        parts.append(str(value))
    return " ".join(part for part in parts if part)


def _normalize_text(value: str) -> str:
    lowered = value.lower().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", lowered).strip()


def _match_groups(text: str, groups: list[tuple[str, list[str]]]) -> list[str]:
    matched: list[str] = []
    for label, aliases in groups:
        if any(_contains_alias(text, alias) for alias in aliases):
            matched.append(label)
    return matched


def _contains_alias(text: str, alias: str) -> bool:
    normalized = _normalize_text(alias)
    if not normalized:
        return False
    if " " in normalized:
        return normalized in text
    return re.search(rf"(?<![a-z0-9]){re.escape(normalized)}(?![a-z0-9])", text) is not None


def _build_principles(
    background: list[str],
    accents: list[str],
    materials: list[str],
    styles: list[str],
    lighting: list[str],
    composition: list[str],
) -> list[str]:
    principles: list[str] = []
    if accents:
        principles.append(
            "Preserve small distinctive accent colors as controlled highlights instead of reducing the style to the dominant background palette."
        )
        principles.append(f"Use accent cues sparingly: {', '.join(accents[:3])}.")
    if background:
        principles.append(f"Keep compatible background atmosphere from the reference: {', '.join(background[:2])}.")
    if materials:
        principles.append(f"Reuse material handling as abstract texture cues: {', '.join(materials[:3])}.")
    if lighting:
        principles.append(f"Carry over lighting logic where compatible: {', '.join(lighting[:2])}.")
    if composition:
        principles.append(f"Respect reusable composition structure: {', '.join(composition[:2])}.")
    if styles:
        principles.append(f"Keep the overall aesthetic direction: {', '.join(styles[:3])}.")
    return _dedupe(principles)[:6]


def _build_brief(
    background: list[str],
    accents: list[str],
    materials: list[str],
    styles: list[str],
    lighting: list[str],
    composition: list[str],
) -> str:
    parts: list[str] = []
    if styles:
        parts.append(f"aesthetic={', '.join(styles[:3])}")
    if composition:
        parts.append(f"composition={', '.join(composition[:2])}")
    if lighting:
        parts.append(f"lighting={', '.join(lighting[:2])}")
    if background:
        parts.append(f"background={', '.join(background[:2])}")
    if accents:
        parts.append(f"accent_colors={', '.join(accents[:3])}")
    if materials:
        parts.append(f"materials={', '.join(materials[:3])}")
    return "; ".join(parts)


def _labels_to_color_tags(labels: list[str]) -> list[str]:
    tags: list[str] = []
    mapping = {
        "beige": "warm neutral",
        "cream": "warm neutral",
        "ivory": "white",
        "white": "white",
        "black": "black",
        "charcoal": "black",
        "pink": "pink",
        "blue": "blue",
        "cyan": "blue",
        "green": "green",
        "gold": "gold",
        "amber": "gold",
        "red": "red",
        "crimson": "red",
        "violet": "purple",
        "purple": "purple",
        "silver": "silver",
        "chrome": "silver",
    }
    for label in labels:
        lowered = label.lower()
        for key, tag in mapping.items():
            if key in lowered:
                tags.append(tag)
    return tags


def _labels_to_material_tags(labels: list[str]) -> list[str]:
    tags: list[str] = []
    mapping = {
        "glass": "glass",
        "liquid": "liquid",
        "metal": "metal",
        "foil": "metal",
        "fabric": "fabric",
        "paper": "paper",
        "card": "paper",
        "ceramic": "ceramic",
        "stone": "stone",
        "wood": "wood",
        "leather": "leather",
    }
    for label in labels:
        lowered = label.lower()
        for key, tag in mapping.items():
            if key in lowered:
                tags.append(tag)
    return tags


def _labels_to_style_tags(labels: list[str]) -> list[str]:
    tags: list[str] = []
    mapping = {
        "premium": "premium",
        "luxury": "luxury",
        "minimal": "minimal",
        "clean": "clean",
        "editorial": "editorial",
        "commercial": "commercial",
        "cinematic": "cinematic",
        "dramatic": "dramatic",
        "tech": "tech",
        "futuristic": "futuristic",
        "playful": "playful",
        "illustration": "illustration",
        "retro": "retro",
        "vintage": "vintage",
    }
    for label in labels:
        lowered = label.lower()
        for key, tag in mapping.items():
            if key in lowered:
                tags.append(tag)
    return tags


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        clean = " ".join(str(item or "").strip().split())
        key = clean.lower()
        if clean and key not in seen:
            seen.add(key)
            unique.append(clean)
    return unique
