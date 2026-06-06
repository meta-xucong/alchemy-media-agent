from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.providers.evolinkai import EVOLINKAI_PROVIDER_ID
from app.schemas import LicensePolicy, PromptCase


HEADING_RE = re.compile(
    r"^###\s+Case\s+(?P<number>\d+):\s+(?P<title>.+?)\s*$",
    re.MULTILINE,
)
LINK_TITLE_RE = re.compile(r"^\[(?P<title>[^\]]+)\]\((?P<url>[^)]+)\)")
IMAGE_RE = re.compile(r"<img\s+[^>]*src=[\"'](?P<src>[^\"']+)[\"']", re.IGNORECASE)
SOURCE_RE = re.compile(r"\*\*Source\*\*:\s*\[?[^\]\n]*\]?\((?P<url>[^)]+)\)", re.IGNORECASE)
FENCE_RE = re.compile(r"```(?:json|text|prompt)?\s*\n(?P<body>.*?)\n```", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class MarkdownCaseDocument:
    path: str
    text: str


def parse_evolinkai_markdown_cases(
    documents: list[MarkdownCaseDocument],
    *,
    source_version: str,
) -> list[PromptCase]:
    cases: list[PromptCase] = []
    seen: set[str] = set()
    for document in documents:
        category = _category_from_path(document.path)
        for case in _parse_document(document, category=category, source_version=source_version):
            if case.case_id in seen:
                continue
            seen.add(case.case_id)
            cases.append(case)
    cases.sort(key=lambda item: (item.category, item.case_id))
    return cases


def _parse_document(document: MarkdownCaseDocument, *, category: str, source_version: str) -> list[PromptCase]:
    matches = list(HEADING_RE.finditer(document.text))
    parsed: list[PromptCase] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(document.text)
        segment = document.text[start:end].strip()
        prompt = _extract_prompt(segment)
        if not prompt:
            continue
        case_number = match.group("number")
        title, source_url = _extract_title_and_source(match.group("title"), segment)
        preview_url = _extract_preview_url(segment)
        case_id = _case_id(category, case_number, title)
        prompt_atoms = _extract_prompt_atoms(prompt, title=title, category=category)
        visual_features = _extract_visual_features(prompt, category=category)
        style_tags = _style_tags(prompt, title)
        use_case_tags = _use_case_tags(prompt, category)
        risk_tags = _risk_tags(prompt)
        parsed.append(
            PromptCase(
                case_id=case_id,
                provider_id=EVOLINKAI_PROVIDER_ID,
                index_version=f"{EVOLINKAI_PROVIDER_ID}:{source_version}",
                source_url=source_url or _github_blob_url(document.path),
                title=title,
                category=category,
                summary=_summary_from_prompt(prompt),
                preview_url=preview_url,
                raw_prompt=prompt,
                prompt_atoms=prompt_atoms,
                visual_features=visual_features,
                style_tags=style_tags,
                use_case_tags=use_case_tags,
                risk_tags=risk_tags,
                license_policy=LicensePolicy(
                    template_reuse_allowed="requires_portrait_authorization" not in risk_tags,
                    raw_image_final_use_allowed=False,
                    commercial_use_status="requires_case_level_safety_check",
                ),
                quality_score=_quality_score(prompt, style_tags, use_case_tags),
            )
        )
    return parsed


def _category_from_path(path: str) -> str:
    return PurePosixPath(path.replace("\\", "/")).stem.lower()


def _extract_title_and_source(raw_title: str, segment: str) -> tuple[str, str | None]:
    raw_title = raw_title.strip()
    link = LINK_TITLE_RE.match(raw_title)
    if link:
        return _clean_title(link.group("title")), link.group("url")
    source = SOURCE_RE.search(segment)
    return _clean_title(re.sub(r"\s+\(by\s+.+?\)\s*$", "", raw_title)), source.group("url") if source else None


def _clean_title(title: str) -> str:
    return re.sub(r"\s+", " ", title).strip(" #")


def _extract_preview_url(segment: str) -> str | None:
    image = IMAGE_RE.search(segment)
    return image.group("src") if image else None


def _extract_prompt(segment: str) -> str:
    prompt_anchor = re.search(r"\*\*Prompt\*\*:?", segment, re.IGNORECASE)
    search_area = segment[prompt_anchor.end() :] if prompt_anchor else segment
    fence = FENCE_RE.search(search_area)
    if fence:
        return fence.group("body").strip()
    return ""


def _extract_prompt_atoms(prompt: str, *, title: str, category: str) -> dict[str, Any]:
    parsed_json = _try_parse_prompt_json(prompt)
    flat = _flatten_json(parsed_json) if parsed_json is not None else {}
    atoms: dict[str, Any] = {
        "subject": _first_value(flat, ["subject", "product", "character", "brand", "visual"]) or _keyword_subject(prompt, title),
        "scene": _first_value(flat, ["scene", "background", "environment", "setting"]),
        "composition": _first_value(flat, ["composition", "layout", "grid", "orientation"]),
        "lighting": _first_value(flat, ["lighting", "light"]),
        "color_palette": _first_value(flat, ["color_palette", "palette", "colors"]),
        "material_texture": _first_value(flat, ["material", "texture", "materials"]),
        "mood": _first_value(flat, ["mood", "feel", "atmosphere", "style"]),
        "typography": _first_value(flat, ["typography", "text", "headline", "logo"]),
        "constraints": _constraints(prompt),
        "category": category,
    }
    return {key: value for key, value in atoms.items() if not _is_empty_value(value)}


def _extract_visual_features(prompt: str, *, category: str) -> dict[str, Any]:
    lower = prompt.lower()
    return {
        "primary_subject_type": _primary_subject_type(lower, category),
        "background_complexity": "high" if any(word in lower for word in ["grid", "sections", "storyboard"]) else "medium",
        "contains_text": any(word in lower for word in ["typography", "headline", "text", "logo", "title"]),
        "commercial_fit": "high" if category in {"ad-creative", "ecommerce", "poster"} else "medium",
        "composition_type": _composition_type(lower, category),
        "feature_keywords": _feature_keywords(lower, category),
    }


def _try_parse_prompt_json(prompt: str) -> Any | None:
    stripped = prompt.strip()
    if not stripped.startswith(("{", "[")):
        return None
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return None


def _flatten_json(value: Any, prefix: str = "") -> dict[str, Any]:
    flat: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            child_key = f"{prefix}.{key}" if prefix else str(key)
            flat[child_key] = child
            flat.update(_flatten_json(child, child_key))
    elif isinstance(value, list):
        for index, child in enumerate(value[:12]):
            child_key = f"{prefix}.{index}" if prefix else str(index)
            flat[child_key] = child
            flat.update(_flatten_json(child, child_key))
    return flat


def _first_value(flat: dict[str, Any], keys: list[str]) -> Any | None:
    for wanted in keys:
        for key, value in flat.items():
            if key.lower().endswith(wanted.lower()) or wanted.lower() in key.lower().split("."):
                return _compact_value(value)
    return None


def _compact_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _compact_value(child) for key, child in list(value.items())[:8]}
    if isinstance(value, list):
        return [_compact_value(item) for item in value[:8]]
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value).strip()
    return value


def _is_empty_value(value: Any) -> bool:
    return value is None or value == "" or value == []


def _keyword_subject(prompt: str, title: str) -> str:
    lower = f"{title} {prompt}".lower()
    for subject in [
        "product",
        "perfume",
        "skincare",
        "poster",
        "dashboard",
        "portrait",
        "mascot",
        "character",
        "food",
        "drink",
        "shoe",
        "app",
    ]:
        if subject in lower:
            return subject
    return title


def _constraints(prompt: str) -> list[str]:
    constraints = []
    lower = prompt.lower()
    for marker in ["no watermark", "avoid", "negative prompt", "do not", "without"]:
        if marker in lower:
            constraints.append(marker)
    return constraints


def _style_tags(prompt: str, title: str) -> list[str]:
    lower = f"{title} {prompt}".lower()
    candidates = {
        "premium": ["premium", "high-end", "luxury", "luxurious"],
        "cinematic": ["cinematic", "film", "moody"],
        "studio-lighting": ["studio", "softbox", "rim light", "key light"],
        "minimal": ["minimal", "clean", "uncluttered"],
        "editorial": ["editorial", "magazine"],
        "commercial": ["commercial", "advertising", "campaign"],
        "ui": ["ui", "dashboard", "interface", "mockup"],
        "product": ["product", "packaging"],
        "photorealistic": ["photorealistic", "realistic", "photo"],
        "typography": ["typography", "headline", "text"],
        "brand-safe": ["brand-safe", "original", "no resemblance"],
    }
    return _dedupe([tag for tag, words in candidates.items() if any(word in lower for word in words)])


def _use_case_tags(prompt: str, category: str) -> list[str]:
    lower = prompt.lower()
    tags = [category]
    mapping = {
        "ecommerce": ["e-commerce", "ecommerce", "marketplace", "product listing", "main image"],
        "ad-creative": ["ad ", "advertising", "campaign", "commercial"],
        "poster": ["poster", "flyer"],
        "social-media": ["instagram", "social media", "story"],
        "ui": ["ui", "dashboard", "interface", "landing page"],
        "portrait": ["portrait", "headshot", "face"],
        "character": ["character", "mascot"],
        "brand-visual": ["brand identity", "branding", "logo"],
        "storyboard": ["storyboard", "tvc"],
    }
    for tag, words in mapping.items():
        if any(word in lower for word in words):
            tags.append(tag)
    return _dedupe(tags)


def _risk_tags(prompt: str) -> list[str]:
    lower = prompt.lower()
    tags = ["raw_image_not_final_asset"]
    if any(word in lower for word in ["preserve her exact", "real person", "uploaded portrait", "elon musk"]):
        tags.append("requires_portrait_authorization")
    if any(word in lower for word in ["chanel", "dior", "apple", "tesla", "spacex", "logo", "trademark"]):
        tags.append("avoid_real_brand_copying")
    if any(word in lower for word in ["anime girl", "shiba inu mascot", "character"]):
        tags.append("avoid_protected_character_similarity")
    return _dedupe(tags)


def _primary_subject_type(lower: str, category: str) -> str:
    if category == "ui" or any(word in lower for word in ["dashboard", "interface", "ui"]):
        return "interface"
    if any(word in lower for word in ["portrait", "woman", "man", "person", "model"]):
        return "person"
    if any(word in lower for word in ["product", "bottle", "shoe", "food", "drink", "packaging"]):
        return "product"
    if "character" in lower or "mascot" in lower:
        return "character"
    return category


def _composition_type(lower: str, category: str) -> str:
    if "grid" in lower or "panel" in lower:
        return "multi_panel"
    if "centered" in lower or "hero" in lower:
        return "centered_hero"
    if category == "poster":
        return "poster_layout"
    if category == "ui":
        return "interface_layout"
    return "general"


def _feature_keywords(lower: str, category: str) -> list[str]:
    rules = {
        "subject.perfume": ["perfume", "parfum", "fragrance"],
        "subject.skincare": ["skincare", "serum", "cream", "cosmetic"],
        "subject.bottle": ["bottle", "flacon", "vessel"],
        "subject.watch": ["watch", "chronograph", "timepiece"],
        "subject.food_drink": ["food", "drink", "beverage", "coffee", "tea", "can", "snack"],
        "subject.person": ["portrait", "person", "woman", "man", "model", "founder"],
        "subject.character": ["character", "mascot", "full-body"],
        "subject.interface": ["ui", "dashboard", "interface", "app", "saas"],
        "material.glass": ["glass", "transparent", "crystal", "refraction"],
        "material.metal": ["metal", "metallic", "brushed", "chrome"],
        "color.black": ["black", "charcoal", "dark"],
        "color.gold": ["gold", "golden", "brass", "amber"],
        "tone.luxury": ["luxury", "luxurious", "premium", "high-end", "opulence", "elegance"],
        "tone.minimal": ["minimal", "clean", "negative space", "uncluttered"],
        "tone.cinematic": ["cinematic", "film", "dramatic", "moody"],
        "tone.cyberpunk": ["cyberpunk", "neon", "futuristic", "sci-fi"],
        "tone.retro": ["retro", "vintage", "nostalgic"],
        "style.illustration": ["illustration", "illustrated", "hand-drawn", "drawing"],
        "lighting.studio": ["studio", "softbox", "rim light", "key light", "controlled lighting"],
        "composition.hero": ["hero", "centered", "main image", "centered composition"],
        "use.ecommerce": ["ecommerce", "marketplace", "product listing", "commercial product"],
        "use.poster": ["poster", "headline", "typography-safe"],
        "use.ad": ["advertising", "campaign", "commercial", "ad creative"],
        "use.social": ["social media", "instagram", "story"],
    }
    keywords = [feature for feature, words in rules.items() if category in feature or any(word in lower for word in words)]
    return _dedupe(keywords)


def _summary_from_prompt(prompt: str) -> str:
    compact = re.sub(r"\s+", " ", prompt).strip()
    return compact[:260].rstrip() + ("..." if len(compact) > 260 else "")


def _quality_score(prompt: str, style_tags: list[str], use_case_tags: list[str]) -> float:
    score = 0.55
    score += min(len(prompt) / 4000, 0.2)
    score += min(len(style_tags) * 0.025, 0.15)
    score += min(len(use_case_tags) * 0.015, 0.1)
    return round(min(score, 0.95), 3)


def _case_id(category: str, case_number: str, title: str) -> str:
    digest = hashlib.sha1(f"{category}:{case_number}:{title}".encode("utf-8")).hexdigest()[:6]
    return f"case_github_evolinkai_{category.replace('-', '_')}_{int(case_number):04d}_{digest}"


def _github_blob_url(path: str) -> str:
    return f"https://github.com/EvoLinkAI/awesome-gpt-image-2-API-and-Prompts/blob/main/{path}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            unique.append(item)
    return unique
