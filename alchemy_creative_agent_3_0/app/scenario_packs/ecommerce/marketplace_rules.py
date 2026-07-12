"""Versioned marketplace profile hints for E-Commerce recipes."""

from __future__ import annotations

from typing import Any

from .contracts import MarketplaceRuleProfile
from .localization import resolve_localization
from .utils import clean_text


PROFILE_VERSION = "v3_ecommerce_rules_2026_07_12"
PROFILE_UPDATED_AT = "2026-07-12"
PROFILE_STATUS = "internal_draft"

PROFILE_SOURCE_NOTES = {
    "amazon": "Verified main-image baseline is recorded separately; confirm category and regional exceptions in Seller Central before publishing.",
    "ozon": "Photo ordering, review, and media capabilities are documented; scene-led styling remains an optional internal strategy.",
    "taobao": "Current category, campaign, and placement image rules require seller-side verification; no universal style is asserted here.",
    "jd": "Truthful product information is a baseline; category and placement image styling requires seller-side verification.",
    "pinduoduo": "Current category and placement image rules require seller-side verification; no price-led visual claim is inferred.",
    "tiktok_shop": "Listing-detail evidence and creator/content presentation are separate modes; verify market-specific rules before publishing.",
    "shopify": "Storefront presentation is theme and merchant-configured, not a third-party marketplace policy.",
    "generic": "Internal generic commerce profile; no marketplace policy is implied.",
}

PLATFORM_ALIASES = {
    "amazon_us": ("amazon", "US"),
    "amazon": ("amazon", "US"),
    "ozon": ("ozon", "RU"),
    "shopify": ("shopify", "global"),
    "tiktok_shop": ("tiktok_shop", "global"),
    "tiktok": ("tiktok_shop", "global"),
    "taobao": ("taobao", "CN"),
    "tmall": ("taobao", "CN"),
    "jd": ("jd", "CN"),
    "jingdong": ("jd", "CN"),
    "pdd": ("pinduoduo", "CN"),
    "pinduoduo": ("pinduoduo", "CN"),
    "generic": ("generic", "global"),
    "ecommerce_generic": ("generic", "global"),
}


CREATIVE_STRATEGY_ALIASES = {
    "": "evidence_first",
    "evidence_first": "evidence_first",
    "scene_story": "scene_story",
    "information_rich": "information_rich",
    "content_hook": "content_hook",
    "brand_story": "brand_story",
}


def resolve_creative_strategy(value: object) -> str:
    return CREATIVE_STRATEGY_ALIASES.get(clean_text(value).lower(), "evidence_first")


def evidence_intent_for_slot(slot: str) -> dict[str, str]:
    """Define what a listing role must prove, independent of platform aesthetics."""

    if slot in {"main_image", "hero_image"}:
        return {
            "id": "primary_product_truth",
            "direction": "Show the actual product as sold in one unambiguous, complete, clearly recognizable primary view.",
        }
    if slot in {"feature_image_1", "feature_image_2", "benefit_image", "benefit_hook"}:
        return {
            "id": "single_feature_proof",
            "direction": "Prove one supplied function or benefit with visible product evidence; do not invent performance results.",
        }
    if slot == "detail_image":
        return {
            "id": "material_or_component_detail",
            "direction": "Show material, finish, controls, ports, or another visible component without inventing hidden internals.",
        }
    if slot == "scenario_image":
        return {
            "id": "verified_use_context",
            "direction": "Show a believable use context and human scale only when it remains consistent with the supplied product facts.",
        }
    if slot == "size_spec_image":
        return {
            "id": "scale_or_quantity_clarity",
            "direction": "Clarify supplied dimensions, compatibility, package count, or relative scale; never invent measurements.",
        }
    if slot in {"trust_image", "trust_comparison_image"}:
        return {
            "id": "evidence_backed_trust",
            "direction": "Use only supplied facts to support quality, included items, or comparison clarity; do not fabricate certificates or awards.",
        }
    return {
        "id": "content_or_collection_context",
        "direction": "Keep the actual product recognizable and make one evidence-backed commercial purpose clear.",
    }


def platform_compliance_intent_for_slot(platform: str, market: str, slot: str) -> dict[str, str]:
    """Return only verified platform-specific visual constraints, never styling assumptions."""

    if str(platform).lower() == "amazon" and slot in {"main_image", "hero_image"}:
        return {
            "id": "amazon_main_image_verified_baseline",
            "evidence_tier": "verified_requirement",
            "direction": (
                "Amazon main-image baseline: use the actual product as sold on a pure-white background; keep it fully "
                "visible and clear, with no unrelated props, badges, borders, watermarks, or added text. Apply category "
                "and regional exceptions only after current Seller Central verification."
            ),
        }
    return {
        "id": "no_verified_platform_visual_override",
        "evidence_tier": "no_verified_visual_override",
        "direction": "",
    }


def creative_strategy_for_slot(strategy: object, slot: str) -> dict[str, str]:
    """Apply an explicit seller choice without overriding evidence or compliance intent."""

    strategy_id = resolve_creative_strategy(strategy)
    if strategy_id == "scene_story" and slot in {"scenario_image", "ad_cover", "collection_cover", "store_banner"}:
        return {
            "id": strategy_id,
            "direction": "Use a restrained, believable scene to connect the product to its intended use while keeping it identifiable.",
        }
    if strategy_id == "information_rich" and slot not in {"main_image", "hero_image"}:
        return {
            "id": strategy_id,
            "direction": "Organize one proof point with clear visual hierarchy and reserve uncluttered space for a future approved text layer.",
        }
    if strategy_id == "content_hook" and slot in {"ad_cover", "benefit_hook", "collection_cover", "store_banner"}:
        return {
            "id": strategy_id,
            "direction": "Use one truthful, immediately understandable visual hook for content placement without obscuring the product.",
        }
    if strategy_id == "brand_story" and slot not in {"main_image", "hero_image"}:
        return {
            "id": strategy_id,
            "direction": "Use consistent lighting, material treatment, and setting that can support a merchant-defined brand story without inventing brand facts.",
        }
    return {"id": strategy_id, "direction": ""}
class MarketplaceRuleEngine:
    """Return stable first-pass platform guidance without pretending it is live policy."""

    def profile(
        self,
        *,
        platform_profile: str | None,
        parameters: dict[str, Any],
        product_profile: dict[str, Any],
    ) -> MarketplaceRuleProfile:
        raw_platform = clean_text(
            platform_profile
            or parameters.get("platform")
            or parameters.get("marketplace")
            or product_profile.get("platform")
            or product_profile.get("marketplace")
            or "generic"
        ).lower()
        platform, default_market = PLATFORM_ALIASES.get(raw_platform, (raw_platform or "generic", "global"))
        market = clean_text(parameters.get("market") or product_profile.get("market") or default_market) or default_market
        image_slots = self._slots_for(platform)
        canvas_rules = self._canvas_rules(parameters)
        content_rules = self._content_rules(platform)
        export_rules = self._export_rules(platform, parameters)
        text_policy = self._text_policy(platform, image_slots)
        localization = resolve_localization(
            platform=platform,
            market=market,
            requested_locale=parameters.get("copy_locale") or parameters.get("locale"),
        )
        warnings = [
            "Marketplace policy guidance is versioned first-pass metadata, not live legal or platform-policy advice."
        ]
        return MarketplaceRuleProfile(
            platform=platform,
            market=market,
            image_slots=image_slots,
            canvas_rules=canvas_rules,
            content_rules=content_rules,
            export_rules=export_rules,
            warnings=warnings,
            metadata={
                "source": "MarketplaceRuleEngine",
                "profile_id": f"ecommerce_{platform}_{market.lower()}",
                "profile_version": PROFILE_VERSION,
                "profile_updated_at": PROFILE_UPDATED_AT,
                "profile_status": PROFILE_STATUS,
                "profile_source_notes": PROFILE_SOURCE_NOTES.get(platform, PROFILE_SOURCE_NOTES["generic"]),
                "profile_evidence_tier": "mixed_verified_and_internal",
                "raw_platform_profile": raw_platform,
                "live_policy_lookup": False,
                "text_policy": text_policy,
                **localization.metadata(),
            },
        )

    def _slots_for(self, platform: str) -> list[str]:
        if platform == "amazon":
            return [
                "main_image",
                "feature_image_1",
                "feature_image_2",
                "scenario_image",
                "size_spec_image",
                "trust_comparison_image",
                "ad_cover",
            ]
        if platform == "ozon":
            return [
                "main_image",
                "scenario_image",
                "benefit_image",
                "detail_image",
                "size_spec_image",
                "trust_image",
            ]
        if platform in {"taobao", "jd", "pinduoduo"}:
            return [
                "main_image",
                "benefit_image",
                "detail_image",
                "scenario_image",
                "size_spec_image",
                "trust_image",
                "store_banner",
            ]
        if platform == "tiktok_shop":
            return ["ad_cover", "main_image", "benefit_hook", "scenario_image", "trust_image"]
        if platform == "shopify":
            return ["hero_image", "feature_image_1", "detail_image", "scenario_image", "trust_image", "collection_cover"]
        return [
            "main_image",
            "feature_image_1",
            "feature_image_2",
            "scenario_image",
            "size_spec_image",
            "trust_comparison_image",
            "ad_cover",
        ]

    def _canvas_rules(self, parameters: dict[str, Any]) -> dict[str, Any]:
        requested_size = clean_text(parameters.get("requested_image_size"))
        requested_ratio = _aspect_ratio_from_requested_size(requested_size)
        ratio = requested_ratio or "1:1"
        return {
            "primary_aspect_ratio": ratio,
            "secondary_aspect_ratio": ratio,
            "canvas_source": "explicit_output_size" if requested_ratio else "internal_neutral_fallback",
        }

    def _content_rules(self, platform: str) -> list[str]:
        rules = [
            "Product remains clear, large, and unobstructed.",
            "Claims must be supported by supplied facts or softened.",
            "Any requested in-image copy must be generated by the image provider and pass final-pixel review.",
            "Set uses a consistent product identity across all slots.",
        ]
        if platform == "amazon":
            rules.insert(0, "Amazon main-image requirements are recorded separately and must be rechecked by category and region.")
        if platform == "ozon":
            rules.append("Ozon photo ordering and moderation are platform facts; scene styling remains an explicit seller strategy.")
        if platform == "tiktok_shop":
            rules.append("Listing-detail proof and creator/content presentation are separate deliverable modes.")
        if platform == "shopify":
            rules.append("Storefront media presentation depends on the merchant theme, page placement, and variant configuration.")
        return rules

    def _export_rules(self, platform: str, parameters: dict[str, Any]) -> dict[str, Any]:
        requested_size = clean_text(parameters.get("requested_image_size"))
        return {
            "format": "png",
            "naming": "{slot}_{index}_{platform}.png",
            "dimension_hint": requested_size or "seller placement configuration required",
            "dimension_source": "explicit_output_size" if _aspect_ratio_from_requested_size(requested_size) else "seller_configuration_required",
        }

    def _text_policy(self, platform: str, image_slots: list[str]) -> dict[str, list[str]]:
        forbidden = [slot for slot in image_slots if slot in {"main_image", "hero_image"}]
        return {
            "text_forbidden_slots": forbidden,
            "text_enabled_slots": [slot for slot in image_slots if slot not in forbidden],
            "policy_owner": f"ecommerce_{platform}_profile",
        }


def _aspect_ratio_from_requested_size(value: str) -> str | None:
    parts = value.lower().split("x")
    if len(parts) != 2:
        return None
    try:
        width, height = (int(part.strip()) for part in parts)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    divisor = _greatest_common_divisor(width, height)
    return f"{width // divisor}:{height // divisor}"


def _greatest_common_divisor(left: int, right: int) -> int:
    while right:
        left, right = right, left % right
    return left
