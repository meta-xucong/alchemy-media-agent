"""Prompt-facing vocabulary guards for V3 generation."""

from __future__ import annotations

from collections.abc import Iterable
import re
from typing import Any


ECOMMERCE_TEMPLATE_IDS = {"ecommerce_template"}
ECOMMERCE_SCENARIO_IDS = {"ecommerce"}
GENERAL_TEMPLATE_IDS = {"general_template"}
GENERAL_SCENARIO_IDS = {"general_creative"}
ECOMMERCE_INDUSTRIES = {"ecommerce_product"}
ECOMMERCE_ASSET_TYPES = {"ecommerce_main_image", "product_detail_banner"}
ECOMMERCE_PLATFORMS = {"taobao", "jd", "ecommerce_generic"}
PRODUCT_REFERENCE_ROLES = {
    "product",
    "product_reference",
    "sku_reference",
    "packaging_reference",
}
HUMAN_SUBJECT_CONTEXT_KEYWORDS = (
    "portrait",
    "photo",
    "photography",
    "model",
    "woman",
    "girl",
    "man",
    "boy",
    "face",
    "fashion",
    "editorial",
    "people",
    "person",
    "real person",
    "\u4eba\u50cf",
    "\u5199\u771f",
    "\u6444\u5f71",
    "\u7167\u7247",
    "\u6a21\u7279",
    "\u7f8e\u5973",
    "\u4eba\u7269",
    "\u5973\u6027",
    "\u5973\u751f",
    "\u7537\u6027",
    "\u771f\u4eba",
    "\u8138",
)
STRUCTURED_APPEARANCE_KEYWORDS = (
    "outfit",
    "garment",
    "dress",
    "robe",
    "gown",
    "uniform",
    "costume",
    "sleeve",
    "cuff",
    "collar",
    "neckline",
    "layered",
    "layering",
    "sheer",
    "translucent",
    "fabric",
    "embroidery",
    "pattern",
    "motif",
    "trim",
    "sash",
    "belt",
    "pleat",
    "drape",
    "wardrobe",
    "\u670d\u88c5",
    "\u7a7f\u642d",
    "\u88d9",
    "\u957f\u88d9",
    "\u5916\u642d",
    "\u6750\u8d28",
    "\u534a\u900f\u660e",
    "\u900f\u660e",
    "\u9886\u53e3",
    "\u8863\u9886",
    "\u8896",
    "\u8896\u53e3",
    "\u8170\u5e26",
    "\u8170\u5c01",
    "\u7eb9\u6837",
    "\u56fe\u6848",
    "\u523a\u7ee3",
    "\u5c42\u6b21",
    "\u53e0\u7a7f",
    "\u8919",
    "\u76b1",
    "\u9762\u6599",
    "\u98d8\u9038",
)
EXPLICIT_ECOMMERCE_CONTEXT_KEYWORDS = (
    "ecommerce",
    "e-commerce",
    "product image",
    "main image",
    "detail page",
    "marketplace",
    "amazon listing",
    "sku",
    "shopify",
    "taobao",
    "jd",
    "\u7535\u5546",
    "\u4e3b\u56fe",
    "\u8be6\u60c5\u9875",
    "\u8be6\u60c5\u56fe",
    "\u5546\u54c1\u56fe",
    "\u4ea7\u54c1\u56fe",
    "\u6dd8\u5b9d",
    "\u4eac\u4e1c",
    "\u4e9a\u9a6c\u900a",
)

PRODUCT_INTENT_KEYWORDS = (
    "商品",
    "产品",
    "电商",
    "主图",
    "详情页",
    "详情图",
    "包装",
    "瓶",
    "罐",
    "香水",
    "护肤",
    "化妆品",
    "面霜",
    "精华",
    "口红",
    "耳机",
    "淘宝",
    "京东",
    "亚马逊",
    "sku",
    "product",
    "ecommerce",
    "e-commerce",
    "packaging",
    "package",
    "label",
    "bottle",
    "jar",
    "perfume",
    "skincare",
    "cosmetic",
    "amazon",
    "shopify",
)
GENERAL_NEGATED_RETAIL_NEGATIVE_CONSTRAINTS = (
    "unrequested retail-style props",
    "unrequested cosmetic containers",
    "unrequested shop-item styling",
)
NEGATIVE_PROMPT_MARKERS = (
    "\u8d1f\u9762\u63d0\u793a\u8bcd",
    "\u53cd\u5411\u63d0\u793a\u8bcd",
    "\u8d1f\u9762\u8bcd",
    "\u53cd\u5411\u8bcd",
    "negative prompt",
    "negative prompts",
    "negative:",
    "avoid:",
)

NEGATED_PRODUCT_PATTERNS = (
    "不要香水",
    "不要护肤品",
    "不要任何商品",
    "不要商品",
    "不需要商品",
    "不是商品",
    "不要产品",
    "不需要产品",
    "不是产品",
    "不要包装",
    "不要瓶",
    "不要罐",
    "no product",
    "no products",
    "without product",
    "without products",
    "do not add product",
    "do not include product",
    "no perfume",
    "no skincare",
    "no cosmetics",
)
NEGATED_PRODUCT_CLAUSE_MARKERS = (
    "不要",
    "不需要",
    "不是",
    "避免",
    "禁止",
    "无",
    "没有",
    "不含",
    "别加",
    "别出现",
    "no ",
    "without ",
    "do not add ",
    "do not include ",
)
NEGATED_PRODUCT_CLAUSE_BOUNDARIES = ("，", "。", "；", "\n", ",", ".", ";")


def looks_like_human_subject_context(value: Any) -> bool:
    normalized = str(value or "").lower()
    return any(keyword.lower() in normalized for keyword in HUMAN_SUBJECT_CONTEXT_KEYWORDS)


def looks_like_human_structured_appearance_context(value: Any) -> bool:
    normalized = str(value or "").lower()
    return looks_like_human_subject_context(normalized) and any(
        keyword.lower() in normalized for keyword in STRUCTURED_APPEARANCE_KEYWORDS
    )


def contains_explicit_ecommerce_context(value: Any) -> bool:
    normalized = _strip_negated_product_phrases(str(value or "")).lower()
    return any(keyword.lower() in normalized for keyword in EXPLICIT_ECOMMERCE_CONTEXT_KEYWORDS)


def product_language_allowed(
    *,
    template_id: Any = None,
    scenario_id: Any = None,
    industry: Any = None,
    asset_type: Any = None,
    platform: Any = None,
    user_input: Any = None,
    metadata: dict[str, Any] | None = None,
    uploaded_assets: Iterable[Any] | None = None,
    reference_assets: Iterable[Any] | None = None,
) -> bool:
    """Return true only when model-facing prompt text may use product wording."""

    metadata = metadata or {}
    template_value = _value(template_id) or _value(metadata.get("template_id")) or _value(metadata.get("template_manifest_id"))
    scenario_value = _value(scenario_id) or _value(metadata.get("scenario_id"))
    industry_value = _value(industry) or _value(metadata.get("industry"))
    asset_type_value = _value(asset_type) or _value(metadata.get("asset_type"))
    platform_value = _value(platform) or _value(metadata.get("platform"))

    if template_value in ECOMMERCE_TEMPLATE_IDS:
        return True
    if scenario_value in ECOMMERCE_SCENARIO_IDS:
        return True
    if template_value in GENERAL_TEMPLATE_IDS or scenario_value in GENERAL_SCENARIO_IDS:
        return _general_template_has_positive_product_intent(
            str(user_input or metadata.get("user_input") or metadata.get("normalized_input") or ""),
            uploaded_assets=uploaded_assets,
            reference_assets=reference_assets,
        )
    if industry_value in ECOMMERCE_INDUSTRIES:
        return True
    if asset_type_value in ECOMMERCE_ASSET_TYPES:
        return True
    if platform_value in ECOMMERCE_PLATFORMS:
        return True
    if _asset_roles_have_product_reference(uploaded_assets):
        return True
    if _asset_roles_have_product_reference(reference_assets):
        return True

    normalized_input = str(user_input or metadata.get("user_input") or metadata.get("normalized_input") or "").lower()
    return any(keyword.lower() in normalized_input for keyword in PRODUCT_INTENT_KEYWORDS)


def strip_negated_product_phrases(value: str) -> str:
    """Remove product-like words only when the user mentioned them as things to avoid."""

    return " ".join(_strip_negated_product_phrases(value).split())


def general_negated_retail_constraints(value: str) -> list[str]:
    """Return neutral negative constraints for general prompts with product-like exclusions."""

    original = " ".join(str(value or "").split())
    cleaned = strip_negated_product_phrases(original)
    if cleaned == original:
        return []
    return list(GENERAL_NEGATED_RETAIL_NEGATIVE_CONSTRAINTS)


def split_positive_and_negative_prompt(value: str) -> tuple[str, list[str]]:
    """Split explicit negative-prompt sections out of a user request."""

    text = str(value or "").strip()
    if not text:
        return "", []
    lowered = text.lower()
    matches = [(lowered.find(marker), marker) for marker in NEGATIVE_PROMPT_MARKERS if lowered.find(marker) >= 0]
    if not matches:
        return " ".join(text.split()), []
    start, marker = min(matches, key=lambda item: item[0])
    positive = text[:start].strip()
    negative = text[start + len(marker):].strip()
    negative = re.sub(r"^[\s:：\-\n\r]+", "", negative)
    return " ".join(positive.split()), _split_negative_items(negative)


def _general_template_has_positive_product_intent(
    user_input: str,
    *,
    uploaded_assets: Iterable[Any] | None,
    reference_assets: Iterable[Any] | None,
) -> bool:
    if _asset_roles_have_product_reference(uploaded_assets):
        return True
    if _asset_roles_have_product_reference(reference_assets):
        return True
    normalized = _strip_negated_product_phrases(user_input).lower()
    return any(keyword.lower() in normalized for keyword in PRODUCT_INTENT_KEYWORDS)


def _split_negative_items(value: str) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts = re.split(r"[,，、;；\n\r]+", text)
    return list(dict.fromkeys(part.strip(" \t.:：。") for part in parts if part.strip(" \t.:：。")))


def _strip_negated_product_phrases(value: str) -> str:
    text = str(value or "")
    text = _strip_negated_product_clauses(text)
    lowered = text.lower()
    for pattern in NEGATED_PRODUCT_PATTERNS:
        pattern_lower = pattern.lower()
        start = lowered.find(pattern_lower)
        while start >= 0:
            end = start + len(pattern_lower)
            text = f"{text[:start]} {text[end:]}"
            lowered = text.lower()
            start = lowered.find(pattern_lower)
    return text


def _strip_negated_product_clauses(value: str) -> str:
    text = str(value or "")
    lowered = text.lower()
    for marker in NEGATED_PRODUCT_CLAUSE_MARKERS:
        marker_lower = marker.lower()
        start = lowered.find(marker_lower)
        while start >= 0:
            end = _negated_clause_end(text, start + len(marker_lower))
            clause = text[start:end].lower()
            if any(keyword.lower() in clause for keyword in PRODUCT_INTENT_KEYWORDS):
                text = f"{text[:start]} {text[end:]}"
                lowered = text.lower()
                start = lowered.find(marker_lower)
            else:
                start = lowered.find(marker_lower, start + len(marker_lower))
    return text


def _negated_clause_end(text: str, start: int) -> int:
    candidates = [text.find(boundary, start) for boundary in NEGATED_PRODUCT_CLAUSE_BOUNDARIES]
    candidates = [index for index in candidates if index >= 0]
    return min(candidates) if candidates else len(text)


def _asset_roles_have_product_reference(assets: Iterable[Any] | None) -> bool:
    if not assets:
        return False
    for asset in assets:
        role = ""
        if isinstance(asset, dict):
            role = str(asset.get("role") or asset.get("use_policy") or "")
        else:
            role = str(getattr(asset, "role", "") or getattr(asset, "use_policy", ""))
        if role.strip().lower() in PRODUCT_REFERENCE_ROLES:
            return True
    return False


def _value(value: Any) -> str:
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw).strip().lower()
