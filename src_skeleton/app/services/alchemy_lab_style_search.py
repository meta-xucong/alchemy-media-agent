from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

from app.services.alchemy_lab_llm import LabLLMError, plan_lab_json


TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
MIN_STYLE_RELEVANCE_SCORE = 0.18
MAX_LOCAL_CANDIDATES = 120
MAX_QUERY_CHARS = 500

_STYLE_BASE_TEXT_CACHE: dict[str, str] = {}
_STYLE_SEARCH_TEXT_CACHE: dict[str, str] = {}
_STYLE_TOKEN_COUNTER_CACHE: dict[str, Counter[str]] = {}
_STYLE_TOKEN_SET_CACHE: dict[str, set[str]] = {}
_STYLE_FEATURE_CACHE: dict[str, set[str]] = {}

GENERIC_QUERY_TOKENS = {
    "ad",
    "art",
    "campaign",
    "design",
    "image",
    "poster",
    "product",
    "style",
    "visual",
}

QUERY_EXPANSIONS = {
    "电商": ["ecommerce", "marketplace", "product", "listing"],
    "主图": ["product", "ecommerce", "hero"],
    "产品": ["product", "commercial", "packaging", "object"],
    "包装": ["packaging", "label", "product"],
    "瓶": ["bottle", "vessel", "product"],
    "玻璃瓶": ["glass", "bottle", "transparent", "product"],
    "香水": ["perfume", "fragrance", "bottle", "luxury"],
    "护肤": ["skincare", "beauty", "cosmetic", "product"],
    "医疗": ["medical", "clinical", "clean", "laboratory"],
    "色谱柱": ["chromatography", "medical", "laboratory", "column", "metal"],
    "黄金": ["gold", "metal", "luxury"],
    "金属": ["metal", "metallic", "chrome", "brushed"],
    "海报": ["poster", "graphic", "typography", "campaign"],
    "广告": ["advertising", "campaign", "commercial"],
    "节日": ["holiday", "festival", "celebration", "poster"],
    "端午": ["dragon boat", "zongzi", "food", "festival", "chinese", "green", "poster"],
    "粽子": ["zongzi", "food", "rice dumpling", "festival", "chinese", "green", "poster"],
    "春节": ["spring festival", "chinese new year", "red", "festive"],
    "中式": ["chinese", "oriental", "ink", "traditional"],
    "国风": ["chinese", "ink", "traditional", "craft"],
    "食物": ["food", "dish", "meal", "restaurant"],
    "美食": ["food", "dish", "restaurant", "poster"],
    "甜品": ["dessert", "cake", "pastry", "sweet"],
    "饮料": ["drink", "beverage", "product", "fresh"],
    "人像": ["portrait", "person", "fashion", "photography"],
    "美女": ["portrait", "fashion", "sweet", "soft"],
    "甜美": ["sweet", "soft", "pastel", "cute"],
    "时尚": ["fashion", "editorial", "portrait"],
    "角色": ["character", "mascot", "illustration"],
    "玩具": ["toy", "collectible", "product"],
    "建筑": ["architecture", "space", "interior"],
    "空间": ["space", "interior", "architecture"],
    "科技": ["technology", "digital", "interface", "futuristic"],
    "界面": ["ui", "interface", "dashboard", "digital"],
    "游戏": ["game", "pixel", "interface", "fantasy"],
    "赛博": ["cyberpunk", "neon", "futuristic"],
    "霓虹": ["neon", "cyberpunk", "glow"],
    "复古": ["retro", "vintage", "archive"],
    "电影": ["cinematic", "film", "scene"],
    "摄影": ["photo", "photography", "camera"],
    "插画": ["illustration", "drawing", "comic"],
    "水彩": ["watercolor", "soft", "illustration"],
    "极简": ["minimal", "clean", "negative space"],
    "高级": ["premium", "luxury", "high-end"],
    "奢华": ["luxury", "premium", "gold"],
    "黑金": ["black", "gold", "luxury"],
}

FEATURE_RULES = {
    "subject.product": ["产品", "商品", "包装", "瓶", "product", "packaging", "bottle", "object"],
    "subject.food": [
        "食物",
        "食品",
        "美食",
        "甜品",
        "饮料",
        "粽子",
        "food",
        "zongzi",
        "rice",
        "dumpling",
        "biscuit",
        "candy",
        "dessert",
        "beverage",
        "cake",
        "dish",
        "meal",
        "restaurant",
    ],
    "subject.person": ["人像", "人物", "美女", "portrait", "person", "model", "fashion"],
    "subject.character": ["角色", "吉祥物", "玩具", "character", "mascot", "toy"],
    "subject.medical": ["医疗", "实验室", "色谱柱", "medical", "clinical", "laboratory", "chromatography"],
    "use.poster": ["海报", "广告", "封面", "poster", "campaign", "cover", "typography"],
    "use.product_showcase": ["电商", "主图", "产品图", "showcase", "ecommerce", "listing"],
    "use.festival": ["节日", "端午", "春节", "festival", "holiday", "celebration"],
    "use.interface": ["界面", "仪表盘", "ui", "dashboard", "interface"],
    "tone.luxury": ["高级", "奢华", "质感", "premium", "luxury", "high-end"],
    "tone.clean": ["极简", "干净", "留白", "minimal", "clean"],
    "tone.cinematic": ["电影", "戏剧", "cinematic", "film"],
    "tone.cute": ["甜美", "可爱", "soft", "cute", "pastel"],
    "tone.cyberpunk": ["赛博", "霓虹", "neon", "cyberpunk", "futuristic"],
    "tone.retro": ["复古", "vintage", "retro", "archive"],
    "medium.photography": ["摄影", "photo", "photography", "camera"],
    "medium.illustration": ["插画", "漫画", "水彩", "illustration", "comic", "watercolor"],
    "medium.graphic": ["平面", "海报", "印刷", "graphic", "print", "poster"],
    "medium.craft": ["工艺", "地域", "传统", "craft", "folk", "woodcut"],
    "material.glass": ["玻璃", "透明", "glass", "transparent", "crystal"],
    "material.metal": ["金属", "黄金", "银色", "metal", "gold", "chrome"],
    "color.gold": ["金", "黄金", "黑金", "gold", "golden"],
    "color.green": ["绿", "端午", "green", "emerald"],
    "color.red": ["红", "春节", "red", "crimson"],
    "color.blue": ["蓝", "科技蓝", "blue", "cyan"],
}

FEATURE_LABELS_ZH = {
    "subject.product": "产品/包装",
    "subject.food": "食物饮品",
    "subject.person": "人物人像",
    "subject.character": "角色玩具",
    "subject.medical": "医疗实验室",
    "use.poster": "海报广告",
    "use.product_showcase": "产品展示",
    "use.festival": "节日祝贺",
    "use.interface": "界面科技",
    "tone.luxury": "高级奢华",
    "tone.clean": "干净极简",
    "tone.cinematic": "电影感",
    "tone.cute": "甜美柔和",
    "tone.cyberpunk": "赛博霓虹",
    "tone.retro": "复古档案",
    "medium.photography": "摄影媒介",
    "medium.illustration": "插画媒介",
    "medium.graphic": "平面印刷",
    "medium.craft": "工艺传统",
    "material.glass": "玻璃透明",
    "material.metal": "金属材质",
    "color.gold": "金色",
    "color.green": "绿色",
    "color.red": "红色",
    "color.blue": "蓝色",
}

FAMILY_FEATURES = {
    "film": {"tone.cinematic", "medium.photography"},
    "fashion": {"subject.person", "medium.photography"},
    "product": {"subject.product", "use.product_showcase"},
    "photography": {"medium.photography"},
    "illustration": {"medium.illustration", "subject.character"},
    "graphic": {"medium.graphic", "use.poster"},
    "craft": {"medium.craft"},
    "digital": {"use.interface", "tone.cyberpunk"},
    "space": {"subject.architecture"},
    "material": {"material.glass", "material.metal", "subject.product"},
}

CORE_QUERY_FEATURES = {
    "subject.product",
    "subject.food",
    "subject.person",
    "subject.character",
    "subject.medical",
    "use.poster",
    "use.product_showcase",
    "use.interface",
}

CORE_FEATURE_EQUIVALENTS = {
    "subject.product": {"subject.product", "use.product_showcase", "material.glass", "material.metal"},
    "subject.food": {"subject.food"},
    "subject.person": {"subject.person", "medium.photography"},
    "subject.character": {"subject.character", "medium.illustration"},
    "subject.medical": {"subject.medical", "tone.clean", "material.metal"},
    "use.poster": {"use.poster", "medium.graphic"},
    "use.product_showcase": {"use.product_showcase", "subject.product"},
    "use.interface": {"use.interface", "tone.cyberpunk"},
}

FAMILY_AFFINITY = {
    "subject.product": {
        "product": 1.0,
        "material": 0.9,
        "graphic": 0.58,
        "photography": 0.56,
        "craft": 0.42,
    },
    "subject.food": {
        "photography": 0.9,
        "graphic": 0.72,
        "craft": 0.58,
        "illustration": 0.52,
        "product": 0.45,
    },
    "subject.person": {
        "fashion": 1.0,
        "photography": 0.92,
        "film": 0.66,
        "illustration": 0.52,
    },
    "subject.character": {
        "illustration": 0.95,
        "digital": 0.72,
        "film": 0.56,
        "craft": 0.46,
    },
    "subject.medical": {
        "product": 0.88,
        "material": 0.82,
        "photography": 0.64,
        "graphic": 0.52,
    },
    "use.poster": {
        "graphic": 1.0,
        "illustration": 0.76,
        "craft": 0.6,
        "photography": 0.52,
        "product": 0.46,
        "film": 0.42,
    },
    "use.product_showcase": {
        "product": 1.0,
        "material": 0.82,
        "photography": 0.62,
        "graphic": 0.54,
    },
    "use.interface": {
        "digital": 1.0,
        "graphic": 0.5,
        "product": 0.38,
    },
    "tone.cinematic": {
        "film": 1.0,
        "photography": 0.66,
        "fashion": 0.44,
    },
    "medium.photography": {
        "photography": 1.0,
        "fashion": 0.76,
        "film": 0.7,
        "product": 0.5,
    },
    "medium.illustration": {
        "illustration": 1.0,
        "graphic": 0.64,
        "digital": 0.56,
        "craft": 0.46,
    },
    "medium.graphic": {
        "graphic": 1.0,
        "illustration": 0.62,
        "craft": 0.52,
        "product": 0.42,
    },
    "medium.craft": {
        "craft": 1.0,
        "graphic": 0.42,
        "illustration": 0.38,
    },
}


class SearchLabStylesRequest(BaseModel):
    query_text: str = ""
    family_filter: str | None = None
    limit: int = Field(default=80, ge=1, le=620)
    diversity_level: str = "medium"


@dataclass(frozen=True)
class _StyleQueryContext:
    expanded_text: str
    counter: Counter[str]
    tokens: set[str]
    specific_tokens: set[str]
    features: set[str]
    normalized_query: str


async def search_lab_styles(
    request: SearchLabStylesRequest,
    styles: list[Any],
) -> dict[str, Any]:
    enabled = [style for style in styles if bool(_value(style, "is_enabled", True))]
    if request.family_filter:
        enabled = [style for style in enabled if _value(style, "family", "") == request.family_filter]
    query = _normalized_query_text(request.query_text)
    if not query:
        return {
            "styles": [_style_payload(style, score=_quality_score(style), why_selected="default library order") for style in enabled[: request.limit]],
            "ranking_explanation": "No query supplied; returned enabled styles in library order.",
            "query_features": [],
            "source": "default",
        }
    context = _style_query_context(query)
    scored: list[tuple[float, str, Any]] = []
    for style in enabled:
        score, reason = _score_style(style, context=context)
        if _style_has_relevance_evidence(style, score, context=context):
            scored.append((score, reason, style))
    scored.sort(key=lambda item: (-item[0], _value(item[2], "id", "")))
    local_candidates = scored[:MAX_LOCAL_CANDIDATES]
    ranked = []
    if str(request.diversity_level or "").strip().lower() in {"llm", "deep", "semantic_llm"}:
        ranked = await _llm_rerank_styles(query=query, candidates=local_candidates, context=context)
    if ranked:
        result = ranked[: request.limit]
        source = "llm_rerank"
    else:
        result = local_candidates[: request.limit]
        source = "local_scorer"
    return {
        "styles": [_style_payload(style, score=round(score, 4), why_selected=reason) for score, reason, style in result],
        "ranking_explanation": _ranking_explanation(query=query, total=len(scored), source=source, features=context.features),
        "query_features": [_feature_label(feature) for feature in sorted(context.features)],
        "source": source,
    }


def _style_query_context(query_text: str) -> _StyleQueryContext:
    expanded_text = _expanded_query_text(query_text)
    tokens = set(_tokens(expanded_text))
    specific_tokens = {token for token in tokens if token not in GENERIC_QUERY_TOKENS and len(token) > 2}
    return _StyleQueryContext(
        expanded_text=expanded_text,
        counter=Counter(_tokens(expanded_text)),
        tokens=tokens,
        specific_tokens=specific_tokens,
        features=_feature_tags(expanded_text),
        normalized_query=query_text.strip().lower(),
    )


def _score_style(style: Any, *, context: _StyleQueryContext) -> tuple[float, str]:
    query_counter = context.counter
    style_text = _style_search_text(style)
    style_counter = _style_token_counter(style)
    overlap = sum((query_counter & style_counter).values())
    semantic = overlap / max(1, sum(query_counter.values()))
    substring_match = _substring_match_score(context.normalized_query, style_text)
    query_features = context.features
    style_features = _style_feature_tags(style)
    feature_hits = query_features.intersection(style_features)
    feature_match = len(feature_hits) / max(1, len(query_features)) if query_features else 0.0
    family_affinity = _family_affinity_score(_value(style, "family", ""), query_features)
    anchor_match = _core_anchor_match_score(query_features, style_features)
    quality = _quality_score(style)
    conflict_penalty = _style_conflict_penalty(style, query_features=query_features, style_features=style_features)
    score = (
        semantic * 0.24
        + feature_match * 0.3
        + substring_match * 0.1
        + family_affinity * 0.13
        + anchor_match * 0.08
        + quality * 0.15
    )
    score = max(0.0, score - conflict_penalty)
    reasons: list[str] = []
    if feature_hits:
        reasons.append("特征匹配：" + "、".join(_feature_label(feature) for feature in sorted(feature_hits)[:4]))
    if semantic > 0:
        reasons.append("语义词重合")
    if substring_match > 0:
        reasons.append("模糊文本命中")
    if family_affinity >= 0.7:
        reasons.append("风格族贴合")
    elif family_affinity >= 0.45:
        reasons.append("风格族部分贴合")
    if anchor_match:
        reasons.append("核心用途/主体命中")
    if conflict_penalty:
        reasons.append("已降低不相关风格族权重")
    reasons.append(f"风格完整度 {quality:.2f}")
    return score, "；".join(reasons)


def _style_conflict_penalty(style: Any, *, query_features: set[str], style_features: set[str]) -> float:
    family = str(_value(style, "family", "") or "")
    penalty = 0.0
    core_anchors = _query_core_anchors(query_features)
    if core_anchors and _core_anchor_match_score(query_features, style_features) <= 0:
        penalty += 0.14
    if "use.poster" in query_features and family not in {"graphic", "illustration", "craft", "photography", "product"}:
        penalty += 0.12
    if {"use.festival", "use.poster"}.intersection(query_features) and "use.interface" in style_features and "use.interface" not in query_features:
        penalty += 0.16
    if "subject.person" in query_features and "subject.person" not in style_features and family not in {"fashion", "photography", "illustration"}:
        penalty += 0.14
    if "subject.product" in query_features and family == "fashion" and "subject.person" not in query_features:
        penalty += 0.12
    if "subject.food" in query_features and "subject.food" not in style_features and family in {"digital", "space"}:
        penalty += 0.12
    if "subject.medical" in query_features and family in {"fashion", "character"}:
        penalty += 0.14
    return min(0.32, penalty)


def _query_core_anchors(query_features: set[str]) -> set[str]:
    return {feature for feature in query_features if feature in CORE_QUERY_FEATURES}


def _core_anchor_match_score(query_features: set[str], style_features: set[str]) -> float:
    anchors = _query_core_anchors(query_features)
    if not anchors:
        return 0.0
    matched = 0
    for anchor in anchors:
        accepted = CORE_FEATURE_EQUIVALENTS.get(anchor, {anchor})
        if accepted.intersection(style_features):
            matched += 1
    return matched / max(1, len(anchors))


def _family_affinity_score(family: str, query_features: set[str]) -> float:
    family = str(family or "")
    scores: list[float] = []
    for feature in query_features:
        weights = FAMILY_AFFINITY.get(feature)
        if weights and family in weights:
            scores.append(float(weights[family]))
    if scores:
        return max(scores)
    if query_features.intersection(FAMILY_FEATURES.get(family, set())):
        return 0.45
    return 0.25 if query_features else 0.5


async def _llm_rerank_styles(
    *,
    query: str,
    candidates: list[tuple[float, str, Any]],
    context: _StyleQueryContext,
) -> list[tuple[float, str, Any]]:
    if not candidates:
        return []
    compact_candidates = [
        {
            "id": _value(style, "id", ""),
            "display_name": _value(style, "display_name", ""),
            "family": _value(style, "family", ""),
            "category": _value(style, "category", ""),
            "description": _value(style, "short_description", ""),
            "tags": list(_value(style, "tags", []) or [])[:8],
            "local_score": round(float(score), 4),
        }
        for score, _reason, style in candidates[:60]
    ]
    system_prompt = (
        "You are Alchemy Lab's independent rare-style search ranker. "
        "Rank candidate visual sub-styles for the user's natural-language goal. "
        "Respect the original rare style identity; do not invent new style ids. "
        "Return compact JSON only with a ranked list. Each item must include id, score from 0 to 1, and reason in Chinese."
    )
    try:
        plan, _metadata = await plan_lab_json(
            system_prompt=system_prompt,
            user_payload={
                "query_text": query,
                "query_features": [_feature_label(feature) for feature in sorted(context.features)],
                "candidate_styles": compact_candidates,
                "output_schema": {"ranked": [{"id": "style id", "score": 0.0, "reason": "short Chinese reason"}]},
            },
            reasoning_effort="low",
            max_tokens=1600,
            temperature=0.1,
            timeout_seconds=6.0,
        )
    except (LabLLMError, Exception):
        return []
    ranked_raw = plan.get("ranked") if isinstance(plan, dict) else None
    if not isinstance(ranked_raw, list):
        return []
    by_id = {_value(style, "id", ""): (score, reason, style) for score, reason, style in candidates}
    ranked: list[tuple[float, str, Any]] = []
    seen: set[str] = set()
    for item in ranked_raw:
        if not isinstance(item, dict):
            continue
        style_id = str(item.get("id") or "").strip()
        if not style_id or style_id in seen or style_id not in by_id:
            continue
        local_score, local_reason, style = by_id[style_id]
        try:
            llm_score = float(item.get("score"))
        except (TypeError, ValueError):
            llm_score = local_score
        score = max(0.0, min(1.0, (llm_score * 0.72) + (float(local_score) * 0.28)))
        reason = str(item.get("reason") or "").strip() or local_reason
        ranked.append((score, reason, style))
        seen.add(style_id)
    if len(ranked) < min(12, len(candidates)):
        for local_score, local_reason, style in candidates:
            style_id = _value(style, "id", "")
            if style_id not in seen:
                ranked.append((local_score, local_reason, style))
                seen.add(style_id)
    ranked.sort(key=lambda item: (-item[0], _value(item[2], "id", "")))
    return ranked


def _style_has_relevance_evidence(style: Any, score: float, *, context: _StyleQueryContext) -> bool:
    if not context.normalized_query:
        return True
    style_text = _style_search_text(style)
    style_tokens = _style_token_set(style)
    style_features = _style_feature_tags(style)
    if not context.features:
        if context.specific_tokens:
            return bool(context.specific_tokens.intersection(style_tokens))
        if _contains_cjk(context.normalized_query):
            return context.normalized_query in style_text.lower()
        return False
    if context.features and context.features.intersection(_style_feature_tags(style)):
        return True
    if context.specific_tokens and context.specific_tokens.intersection(style_tokens):
        return True
    if _contains_cjk(context.normalized_query):
        return context.normalized_query in style_text.lower() or score >= MIN_STYLE_RELEVANCE_SCORE
    return score >= MIN_STYLE_RELEVANCE_SCORE


def _style_search_text(style: Any) -> str:
    cache_key = _style_cache_key(style)
    cached = _STYLE_SEARCH_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    text = " ".join(
        [
            _style_base_text(style),
            " ".join(_value(style, "mode_affinity", []) or []),
        ]
    ).lower()
    _STYLE_SEARCH_TEXT_CACHE[cache_key] = text
    return text


def _style_base_text(style: Any) -> str:
    cache_key = _style_cache_key(style)
    cached = _STYLE_BASE_TEXT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    text = " ".join(
        [
            str(_value(style, "id", "")),
            str(_value(style, "display_name", "")),
            str(_value(style, "short_description", "")),
            str(_value(style, "family", "")),
            str(_value(style, "category", "")),
            " ".join(_value(style, "tags", []) or []),
            " ".join(_value(style, "prompt_directives", []) or []),
        ]
    ).lower()
    _STYLE_BASE_TEXT_CACHE[cache_key] = text
    return text


def _style_token_counter(style: Any) -> Counter[str]:
    cache_key = _style_cache_key(style)
    cached = _STYLE_TOKEN_COUNTER_CACHE.get(cache_key)
    if cached is not None:
        return cached
    counter = Counter(_tokens(_style_search_text(style)))
    _STYLE_TOKEN_COUNTER_CACHE[cache_key] = counter
    return counter


def _style_token_set(style: Any) -> set[str]:
    cache_key = _style_cache_key(style)
    cached = _STYLE_TOKEN_SET_CACHE.get(cache_key)
    if cached is not None:
        return set(cached)
    tokens = set(_style_token_counter(style))
    _STYLE_TOKEN_SET_CACHE[cache_key] = set(tokens)
    return tokens


def _style_feature_tags(style: Any) -> set[str]:
    cache_key = _style_cache_key(style)
    cached = _STYLE_FEATURE_CACHE.get(cache_key)
    if cached is not None:
        return set(cached)
    lower = _style_base_text(style)
    tokens = set(_tokens(lower))
    features = _feature_tags(lower)
    features.update(FAMILY_FEATURES.get(_value(style, "family", ""), set()))
    if _value(style, "freshness", "") == "high":
        features.add("tone.retro") if "复古" in lower or "retro" in lower else None
    refined = {feature for feature in features if _feature_matches_text(feature, lower, tokens) or feature in FAMILY_FEATURES.get(_value(style, "family", ""), set())}
    _STYLE_FEATURE_CACHE[cache_key] = set(refined)
    return refined


def _feature_tags(text: str) -> set[str]:
    lower = text.lower()
    tokens = set(_tokens(lower))
    return {feature for feature in FEATURE_RULES if _feature_matches_text(feature, lower, tokens)}


def _feature_matches_text(feature: str, lower_text: str, token_set: set[str]) -> bool:
    return any(_contains_alias(lower_text, token_set, alias) for alias in FEATURE_RULES.get(feature, []))


def _expanded_query_text(text: str) -> str:
    expansions: list[str] = []
    for marker, words in QUERY_EXPANSIONS.items():
        if marker in text:
            expansions.extend(words)
    return " ".join([text, *expansions])


def _substring_match_score(query_text: str, style_text: str) -> float:
    normalized_query = query_text.strip().lower()
    if not normalized_query:
        return 0.0
    markers = [marker for marker in [normalized_query, *_expanded_query_text(normalized_query).split()] if marker not in GENERIC_QUERY_TOKENS]
    hits = [marker for marker in markers if len(marker) >= 2 and marker in style_text]
    return min(1.0, len(set(hits)) / max(1, min(8, len(set(markers)))))


def _quality_score(style: Any) -> float:
    tags = list(_value(style, "tags", []) or [])
    directives = list(_value(style, "prompt_directives", []) or [])
    score = 0.48 + min(len(tags) * 0.025, 0.18) + min(len(directives) * 0.035, 0.2)
    if _value(style, "freshness", "") == "high":
        score += 0.06
    return round(min(score, 0.95), 3)


def _style_payload(style: Any, *, score: float, why_selected: str) -> dict[str, Any]:
    payload = style.model_dump() if hasattr(style, "model_dump") else dict(style)
    payload["score"] = float(score)
    payload["why_selected"] = why_selected
    return payload


def _style_cache_key(style: Any) -> str:
    style_id = str(_value(style, "id", "") or "")
    if style_id:
        return "|".join(
            [
                style_id,
                str(_value(style, "version", "")),
                str(_value(style, "display_name", "")),
                str(_value(style, "family", "")),
                str(_value(style, "freshness", "")),
            ]
        )
    return str(id(style))


def _normalized_query_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) > MAX_QUERY_CHARS:
        text = text[:MAX_QUERY_CHARS].rstrip()
    return text


def _value(style: Any, key: str, default: Any = None) -> Any:
    if isinstance(style, dict):
        return style.get(key, default)
    return getattr(style, key, default)


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "")]


def _contains_alias(lower_text: str, token_set: set[str], alias: str) -> bool:
    normalized = alias.lower().strip()
    if not normalized:
        return False
    if re.search(r"[\u4e00-\u9fff]", normalized):
        return normalized in lower_text
    if re.fullmatch(r"[a-z0-9]+", normalized):
        return normalized in token_set
    return normalized in lower_text


def _contains_cjk(text: str) -> bool:
    return re.search(r"[\u4e00-\u9fff]", text or "") is not None


def _feature_label(feature: str) -> str:
    return FEATURE_LABELS_ZH.get(feature, feature)


def _ranking_explanation(*, query: str, total: int, source: str, features: set[str]) -> str:
    feature_text = "、".join(_feature_label(feature) for feature in sorted(features)) or "通用语义"
    source_text = "LLM 语义重排" if source == "llm_rerank" else "本地语义评分"
    return f"{source_text}：根据“{query}”的{feature_text}，从 {total} 个候选里按相关度排序。"
