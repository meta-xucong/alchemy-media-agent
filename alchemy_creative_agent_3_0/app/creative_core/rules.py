"""Deterministic V3.0 planning rules.

The foundation intentionally avoids hidden LLM calls so contracts can be tested offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
import re

from ..schemas import AssetType, IndustryCategory, Platform


RULE_VERSION = "v3.0-foundation-rules-001"
NO_FAKE_TEXT_PROVIDER_NOTE = (
    "Generate the product / background / atmosphere only. Reserve clean regions for real "
    "text overlay. Do not render fake final Chinese text inside the image."
)


def stable_id(prefix: str, *parts: object) -> str:
    seed = "|".join(str(part) for part in parts if part is not None)
    digest = sha1(seed.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def normalize_input(value: str) -> str:
    normalized = value.strip()
    normalized = normalized.replace("，", ",").replace("。", ".").replace("；", ";")
    return normalized.lower()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword.lower() in text for keyword in keywords)


PORTRAIT_BEAUTY_CONTEXT_TERMS: tuple[str, ...] = (
    "portrait",
    "photo",
    "photography",
    "model",
    "woman",
    "girl",
    "face",
    "fashion",
    "editorial",
    "\u4eba\u50cf",
    "\u5199\u771f",
    "\u7167\u7247",
    "\u6444\u5f71",
    "\u6a21\u7279",
    "\u7f8e\u5973",
    "\u4eba\u7269",
)
LOCAL_SERVICE_CONTEXT_TERMS: tuple[str, ...] = (
    "salon",
    "spa",
    "nail",
    "service",
    "booking",
    "appointment",
    "store",
    "opening",
    "\u7f8e\u7532",
    "\u7f8e\u776b",
    "\u7f8e\u5bb9",
    "\u7f8e\u53d1",
    "\u76ae\u80a4\u7ba1\u7406",
    "\u6309\u6469",
    "\u5230\u5e97",
    "\u9884\u7ea6",
    "\u5f00\u4e1a\u4f18\u60e0",
)


def _is_portrait_beauty_context(normalized_input: str) -> bool:
    has_beauty_word = "beauty" in normalized_input or "\u7f8e\u5973" in normalized_input
    if not has_beauty_word:
        return False
    return _contains_any(normalized_input, PORTRAIT_BEAUTY_CONTEXT_TERMS) and not _contains_any(
        normalized_input,
        LOCAL_SERVICE_CONTEXT_TERMS,
    )


INDUSTRY_KEYWORDS: tuple[tuple[IndustryCategory, tuple[str, ...]], ...] = (
    (
        IndustryCategory.BEVERAGE,
        ("奶茶", "茶饮", "果茶", "咖啡", "饮品", "冷饮", "柠檬茶", "coffee", "milk tea", "beverage"),
    ),
    (
        IndustryCategory.RESTAURANT_BARBECUE,
        ("烧烤", "烤串", "夜宵", "烤肉", "barbecue", "bbq"),
    ),
    (
        IndustryCategory.RESTAURANT_HOTPOT,
        ("火锅", "麻辣烫", "冒菜", "锅底", "hotpot"),
    ),
    (
        IndustryCategory.ECOMMERCE_PRODUCT,
        (
            "淘宝",
            "天猫",
            "京东",
            "拼多多",
            "电商",
            "主图",
            "详情页",
            "商品图",
            "产品图",
            "耳机",
            "手机壳",
            "服装",
            "鞋子",
            "包包",
            "ecommerce",
            "product image",
            "main image",
        ),
    ),
    (
        IndustryCategory.LOCAL_SERVICE_BEAUTY,
        ("美甲", "美睫", "美容", "美发", "皮肤管理", "按摩", " spa", "开业优惠", "nail", "beauty", "salon"),
    ),
    (
        IndustryCategory.HOSPITALITY,
        ("酒店", "民宿", "客栈", "度假", "温泉", "hotel", "homestay", "resort"),
    ),
    (
        IndustryCategory.RESTAURANT_GENERAL,
        ("餐厅", "饭店", "小吃", "快餐", "中餐", "西餐", "料理", "外卖店", "restaurant", "food"),
    ),
)


DEFAULT_TONES: dict[IndustryCategory, list[str]] = {
    IndustryCategory.BEVERAGE: ["fresh", "clean", "commercial", "appetizing"],
    IndustryCategory.RESTAURANT_BARBECUE: ["appetite", "warm", "night_food", "clean", "commercial"],
    IndustryCategory.RESTAURANT_HOTPOT: ["warm", "appetite", "rich", "lively", "commercial"],
    IndustryCategory.RESTAURANT_GENERAL: ["appetite", "clean", "commercial"],
    IndustryCategory.ECOMMERCE_PRODUCT: ["clean", "product_focused", "commercial"],
    IndustryCategory.LOCAL_SERVICE_BEAUTY: ["gentle", "clean", "premium"],
    IndustryCategory.HOSPITALITY: ["warm", "clean", "inviting"],
    IndustryCategory.UNKNOWN: ["clean", "commercial", "inviting"],
}


TONE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("clean", ("干净", "清爽", "简洁", "高级干净", "clean", "minimal", "simple")),
    ("premium", ("高级", "质感", "精致", "高端", "premium", "luxury", "refined")),
    ("fresh", ("清新", "夏天", "夏季", "冰爽", "水果", "fresh", "summer", "refreshing")),
    ("appetite", ("有食欲", "诱人", "好吃", "烟火气", "热气腾腾", "appetizing", "foodie")),
    ("warm", ("温暖", "温馨", "冬季", "热闹", "warm", "cozy")),
    ("tech", ("科技感", "未来感", "数码", "智能", "tech", "futuristic")),
    ("gentle", ("温柔", "柔和", "女性化", "优雅", "gentle", "soft", "elegant")),
    ("lively", ("热闹", "活泼", "节日", "喜庆", "lively", "festival")),
)


NEGATIVE_STYLE_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("avoid_tacky", ("不要太土", "不要土", "不土", "tacky")),
    ("avoid_clutter", ("不要杂乱", "不要太花", "clutter", "busy")),
    ("avoid_cheap_look", ("不要廉价", "cheap")),
    ("avoid_dark_style", ("不要暗黑", "dark")),
    ("avoid_cyberpunk", ("不要赛博", "cyberpunk")),
    ("avoid_overdecorated", ("不要太花", "overdecorated")),
)


CONTINUATION_KEYWORDS: tuple[str, ...] = (
    "沿用上次",
    "继续上次",
    "继续之前",
    "保持之前",
    "还是那个风格",
    "还是那个品牌风格",
    "同一个品牌风格",
    "上次风格",
)


SCENARIO_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("festival_promotion", ("端午", "中秋", "春节", "圣诞", "七夕", "节日", "festival")),
    ("opening_promotion", ("开业", "新店", "开业优惠", "opening", "new store")),
    ("set_meal_promotion", ("套餐", "双人餐", "团购", "package", "set meal")),
    ("new_product_promotion", ("新品", "上新", "新品上市", "new product", "launch")),
    ("generic_promotion", ("促销", "优惠", "活动", "立减", "折扣", "promotion", "discount", "campaign")),
)


BUSINESS_GOAL_BY_SCENARIO: dict[str, str] = {
    "new_product_promotion": "drive awareness and trial purchase",
    "opening_promotion": "attract first-time customers",
    "festival_promotion": "seasonal campaign conversion",
    "set_meal_promotion": "sell package or group-buying offer",
    "generic_promotion": "drive purchase or inquiry",
    "brand_or_commercial_poster": "improve brand recognition and commercial presentation",
}


PLATFORM_KEYWORDS: tuple[tuple[Platform, tuple[str, ...]], ...] = (
    (Platform.XIAOHONGSHU, ("小红书", "红书", "种草", "xiaohongshu", "rednote")),
    (Platform.WECHAT_MOMENTS, ("朋友圈", "微信朋友圈", "私域", "wechat", "moments")),
    (Platform.MEITUAN, ("美团", "meituan")),
    (Platform.ELEME, ("饿了么", "eleme")),
    (Platform.DELIVERY_APP, ("外卖", "团购", "到店", "delivery")),
    (Platform.TAOBAO, ("淘宝", "天猫", "taobao")),
    (Platform.JD, ("京东", "jd")),
    (Platform.ECOMMERCE_GENERIC, ("拼多多", "电商", "主图", "详情页", "商品图", "ecommerce")),
    (Platform.DOUYIN, ("抖音", "douyin", "tiktok", "短视频封面")),
    (Platform.STORE_SCREEN, ("门店屏幕", "电视屏", "大屏", "横屏", "店内展示", "store screen")),
    (Platform.PRINT_POSTER, ("打印", "印刷", "海报打印", "a4", "门店张贴", "print")),
)


PLATFORM_ASPECT_RATIOS: dict[Platform, str] = {
    Platform.XIAOHONGSHU: "4:5",
    Platform.WECHAT_MOMENTS: "4:5",
    Platform.DELIVERY_APP: "1:1",
    Platform.MEITUAN: "1:1",
    Platform.ELEME: "1:1",
    Platform.TAOBAO: "1:1",
    Platform.JD: "1:1",
    Platform.ECOMMERCE_GENERIC: "1:1",
    Platform.DOUYIN: "9:16",
    Platform.STORE_SCREEN: "16:9",
    Platform.PRINT_POSTER: "A4",
    Platform.GENERIC_SOCIAL: "4:5",
    Platform.GENERIC: "4:5",
}


COLOR_DEFAULTS: dict[IndustryCategory, list[str]] = {
    IndustryCategory.BEVERAGE: ["mint green", "cream white", "warm yellow"],
    IndustryCategory.RESTAURANT_BARBECUE: ["charcoal black", "warm amber", "clean cream"],
    IndustryCategory.RESTAURANT_HOTPOT: ["warm red", "cream white", "deep green"],
    IndustryCategory.ECOMMERCE_PRODUCT: ["cool gray", "clean white", "electric blue"],
    IndustryCategory.LOCAL_SERVICE_BEAUTY: ["soft pink", "cream white", "champagne"],
    IndustryCategory.HOSPITALITY: ["warm beige", "deep green", "linen white"],
    IndustryCategory.UNKNOWN: ["clean white", "warm neutral", "accent color"],
}


CREATIVE_DEFAULTS: dict[IndustryCategory, dict[str, object]] = {
    IndustryCategory.BEVERAGE: {
        "visual_direction": "bright commercial beverage photography with clean premium freshness",
        "composition": "large centered drink product with clean top and bottom text areas",
        "lighting": "soft daylight with refreshing highlights",
        "materials": ["ice", "fruit", "condensation", "clean gradient background"],
        "negative": ["messy table", "cheap plastic look", "fake unreadable text"],
    },
    IndustryCategory.RESTAURANT_BARBECUE: {
        "visual_direction": "appetizing barbecue food in a clean premium late-night dining atmosphere",
        "composition": "hero grilled food centered with warm controlled atmosphere and clear offer space",
        "lighting": "warm night-food lighting with controlled highlights",
        "materials": ["grilled skewers", "controlled smoke", "clean dining surface"],
        "negative": ["dirty smoke", "chaotic fire", "greasy low-end look"],
    },
    IndustryCategory.RESTAURANT_HOTPOT: {
        "visual_direction": "modern appetizing hotpot visual with warm steam and rich ingredients",
        "composition": "central hotpot or ingredient hero with clear promotional text regions",
        "lighting": "warm dining light with clean commercial contrast",
        "materials": ["warm steam", "fresh ingredients", "modern restaurant table"],
        "negative": ["outdated festive clutter", "overly red cheap poster style"],
    },
    IndustryCategory.ECOMMERCE_PRODUCT: {
        "visual_direction": "clean premium product hero shot with feature-focused platform conversion",
        "composition": "center product hero with crisp separation and clean feature label regions",
        "lighting": "high contrast studio lighting",
        "materials": ["premium background", "feature callout space", "subtle tech accents"],
        "negative": ["unclear product shape", "busy background", "fake text"],
    },
    IndustryCategory.LOCAL_SERVICE_BEAUTY: {
        "visual_direction": "soft premium beauty service image with elegant clean details",
        "composition": "service detail hero with gentle negative space for offer and CTA",
        "lighting": "soft premium lighting",
        "materials": ["clean hands or service detail", "elegant background", "soft color accents"],
        "negative": ["medical fear style", "messy salon background", "cheap overdecorated poster"],
    },
    IndustryCategory.UNKNOWN: {
        "visual_direction": "clean polished creative visual with clear subject and atmosphere",
        "composition": "main subject centered with balanced scene space and optional clean overlay area",
        "lighting": "clean refined lighting",
        "materials": ["clean background", "simple scene elements"],
        "negative": ["messy background", "fake unreadable text"],
    },
}


def detect_industry(normalized_input: str) -> IndustryCategory:
    for industry, keywords in INDUSTRY_KEYWORDS:
        if industry == IndustryCategory.LOCAL_SERVICE_BEAUTY and _is_portrait_beauty_context(normalized_input):
            continue
        if _contains_any(normalized_input, keywords):
            return industry
    return IndustryCategory.UNKNOWN


def detect_platforms(normalized_input: str) -> list[Platform]:
    platforms: list[Platform] = []
    for platform, keywords in PLATFORM_KEYWORDS:
        if _contains_any(normalized_input, keywords) and platform not in platforms:
            platforms.append(platform)
    if Platform.MEITUAN in platforms and Platform.DELIVERY_APP in platforms:
        platforms.remove(Platform.DELIVERY_APP)
    if Platform.ELEME in platforms and Platform.DELIVERY_APP in platforms:
        platforms.remove(Platform.DELIVERY_APP)
    if any(platform in platforms for platform in (Platform.TAOBAO, Platform.JD)) and Platform.ECOMMERCE_GENERIC in platforms:
        platforms.remove(Platform.ECOMMERCE_GENERIC)
    return platforms


def default_platforms_for_industry(industry: IndustryCategory) -> list[Platform]:
    square_platform = Platform.ECOMMERCE_GENERIC if industry == IndustryCategory.ECOMMERCE_PRODUCT else Platform.DELIVERY_APP
    if industry not in {
        IndustryCategory.BEVERAGE,
        IndustryCategory.RESTAURANT_BARBECUE,
        IndustryCategory.RESTAURANT_HOTPOT,
        IndustryCategory.RESTAURANT_GENERAL,
        IndustryCategory.ECOMMERCE_PRODUCT,
    }:
        square_platform = Platform.GENERIC_SOCIAL
    return [Platform.GENERIC_SOCIAL, Platform.XIAOHONGSHU, square_platform]


def detect_visual_tones(normalized_input: str, industry: IndustryCategory) -> list[str]:
    tones: list[str] = []
    for tone, keywords in TONE_KEYWORDS:
        if _contains_any(normalized_input, keywords):
            tones.append(tone)
    for tone in DEFAULT_TONES.get(industry, DEFAULT_TONES[IndustryCategory.UNKNOWN]):
        if tone not in tones:
            tones.append(tone)
    return tones


def detect_negative_styles(normalized_input: str) -> list[str]:
    values: list[str] = []
    for tag, keywords in NEGATIVE_STYLE_KEYWORDS:
        if _contains_any(normalized_input, keywords):
            values.append(tag)
    return values


def detect_continuation_request(normalized_input: str) -> bool:
    return _contains_any(normalized_input, CONTINUATION_KEYWORDS)


def detect_scenario(normalized_input: str) -> str:
    matched = [scenario for scenario, keywords in SCENARIO_KEYWORDS if _contains_any(normalized_input, keywords)]
    if "set_meal_promotion" in matched and "冬季" in normalized_input:
        return "winter_set_meal_promotion"
    if "festival_promotion" in matched and "set_meal_promotion" in matched:
        return "winter_set_meal_promotion" if "冬季" in normalized_input else "festival_set_meal_promotion"
    if "new_product_promotion" in matched and ("夏季" in normalized_input or "夏天" in normalized_input):
        return "summer_new_product_promotion"
    return matched[0] if matched else "brand_or_commercial_poster"


def business_goal_for_scenario(scenario: str) -> str:
    if scenario == "summer_new_product_promotion":
        return BUSINESS_GOAL_BY_SCENARIO["new_product_promotion"]
    if scenario in {"winter_set_meal_promotion", "festival_set_meal_promotion"}:
        return BUSINESS_GOAL_BY_SCENARIO["set_meal_promotion"]
    return BUSINESS_GOAL_BY_SCENARIO.get(scenario, BUSINESS_GOAL_BY_SCENARIO["brand_or_commercial_poster"])


def detect_commercial_hooks(normalized_input: str, scenario: str, industry: IndustryCategory) -> list[str]:
    hooks: list[str] = []
    if "夏" in normalized_input:
        hooks.append("summer freshness")
    if "冬" in normalized_input:
        hooks.append("winter warmth")
    if "新品" in normalized_input or scenario == "new_product_promotion":
        hooks.append("new product")
    if any(token in normalized_input for token in ("促销", "优惠", "活动", "立减", "折扣")):
        hooks.append("promotion")
    if "夜宵" in normalized_input:
        hooks.append("late night")
    if industry == IndustryCategory.RESTAURANT_BARBECUE:
        hooks.append("barbecue appetite")
    if industry == IndustryCategory.ECOMMERCE_PRODUCT:
        hooks.append("product feature clarity")
    if not hooks:
        hooks.append("clear commercial presentation")
    return list(dict.fromkeys(hooks))


def detect_selling_points(normalized_input: str) -> list[str]:
    values: list[str] = []
    if "降噪" in normalized_input or "noise" in normalized_input:
        values.append("noise cancellation")
    if "续航" in normalized_input or "battery" in normalized_input:
        values.append("battery life")
    if "新品" in normalized_input:
        values.append("new arrival")
    if "套餐" in normalized_input or "双人餐" in normalized_input:
        values.append("set meal value")
    return values


def is_single_image_request(normalized_input: str) -> bool:
    return any(token in normalized_input for token in ("只要一张", "仅一张", "单张", "one image"))


def wants_series(normalized_input: str) -> bool:
    return any(token in normalized_input for token in ("一组", "系列", "一套", "series"))


def platform_aspect_ratio(platform: Platform | str) -> str:
    return PLATFORM_ASPECT_RATIOS[Platform(platform)]


def asset_type_for_platform(platform: Platform, index: int, industry: IndustryCategory, single: bool = False) -> AssetType:
    if single:
        return AssetType.SINGLE_IMAGE
    if platform == Platform.XIAOHONGSHU:
        return AssetType.SOCIAL_COVER
    if platform == Platform.WECHAT_MOMENTS:
        return AssetType.WECHAT_MOMENTS_POSTER
    if platform in {Platform.DELIVERY_APP, Platform.MEITUAN, Platform.ELEME}:
        return AssetType.GROUP_BUYING_IMAGE if "meituan" == platform.value else AssetType.DELIVERY_COVER
    if platform in {Platform.TAOBAO, Platform.JD, Platform.ECOMMERCE_GENERIC}:
        return AssetType.ECOMMERCE_MAIN_IMAGE if index == 0 else AssetType.PRODUCT_DETAIL_BANNER
    if platform == Platform.STORE_SCREEN:
        return AssetType.STORE_SCREEN_IMAGE
    if platform == Platform.GENERIC_SOCIAL and index == 0:
        return AssetType.MAIN_POSTER
    return AssetType.CAMPAIGN_BANNER if industry == IndustryCategory.ECOMMERCE_PRODUCT else AssetType.MAIN_POSTER


def purpose_for_asset(platform: Platform, asset_type: AssetType, industry: IndustryCategory) -> str:
    if asset_type == AssetType.ECOMMERCE_MAIN_IMAGE:
        return "product main image for platform conversion"
    if asset_type == AssetType.PRODUCT_DETAIL_BANNER:
        return "feature highlight image"
    if platform == Platform.XIAOHONGSHU:
        return "social cover and campaign poster"
    if platform == Platform.WECHAT_MOMENTS:
        return "private-domain social promotion poster"
    if platform in {Platform.DELIVERY_APP, Platform.MEITUAN, Platform.ELEME}:
        return "delivery or group-buying product image"
    if platform == Platform.STORE_SCREEN:
        return "in-store screen campaign image"
    if industry == IndustryCategory.ECOMMERCE_PRODUCT:
        return "commercial product conversion visual"
    return "directly usable creative image"


def default_color_palette(industry: IndustryCategory, tones: list[str]) -> list[str]:
    palette = list(COLOR_DEFAULTS.get(industry, COLOR_DEFAULTS[IndustryCategory.UNKNOWN]))
    if "premium" in tones and "champagne accent" not in palette:
        palette.append("champagne accent")
    if "tech" in tones and "electric blue" not in palette:
        palette.append("electric blue")
    return palette


def creative_defaults(industry: IndustryCategory) -> dict[str, object]:
    return CREATIVE_DEFAULTS.get(industry, CREATIVE_DEFAULTS[IndustryCategory.UNKNOWN])


def is_poster_like(asset_type: AssetType | str) -> bool:
    value = AssetType(asset_type)
    return value not in {AssetType.STORE_SCREEN_IMAGE}


@dataclass(frozen=True)
class ExplicitText:
    headline: str | None = None
    cta: str | None = None


def extract_explicit_chinese_text(raw_input: str) -> ExplicitText:
    title_match = re.search(r"标题写[“\"]([^”\"]+)[”\"]", raw_input)
    cta_match = re.search(r"(?:下面写|副标题写|文案写)[“\"]([^”\"]+)[”\"]", raw_input)
    return ExplicitText(
        headline=title_match.group(1) if title_match else None,
        cta=cta_match.group(1) if cta_match else None,
    )
