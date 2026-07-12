"""Versioned marketplace profile hints for E-Commerce recipes."""

from __future__ import annotations

from typing import Any

from .contracts import MarketplaceRuleProfile
from .localization import resolve_localization
from .utils import clean_text


PROFILE_VERSION = "v3_ecommerce_rules_2026_06_28"
PROFILE_UPDATED_AT = "2026-06-28"
PROFILE_STATUS = "internal_draft"

PROFILE_SOURCE_NOTES = {
    "amazon": "Internal strategic draft; confirm current Seller Central requirements before publishing.",
    "ozon": "Internal strategic draft; confirm current Ozon seller requirements before publishing.",
    "taobao": "Internal strategic draft; confirm current Taobao/Tmall requirements before publishing.",
    "jd": "Internal strategic draft; confirm current JD requirements before publishing.",
    "pinduoduo": "Internal strategic draft; confirm current Pinduoduo requirements before publishing.",
    "tiktok_shop": "Internal strategic draft; confirm current TikTok Shop requirements before publishing.",
    "shopify": "Internal store-design profile, not a third-party marketplace policy.",
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


def platform_visual_intent_for_slot(platform: str, slot: str) -> dict[str, str]:
    """Return versioned internal visual grammar for one marketplace suite role."""

    normalized_platform = str(platform or "generic").strip().lower()
    primary_slot = slot in {"main_image", "hero_image"}
    traffic_slot = slot in {"ad_cover", "benefit_hook", "store_banner", "collection_cover"}
    if normalized_platform == "amazon":
        if primary_slot:
            return {
                "id": "amazon_white_background_primary",
                "direction": (
                    "Use a clean pure-white, product-first listing main image: show the complete product clearly with "
                    "minimal distraction; no props, people, badges, borders, or rendered text."
                ),
            }
        return {
            "id": "amazon_narrative_secondary",
            "direction": (
                "Use a conversion-oriented secondary image that proves one supplied benefit through clear detail, "
                "scale, compatibility, or realistic use context without unsupported claims."
            ),
        }
    if normalized_platform == "ozon":
        return {
            "id": "ozon_mobile_scene_led",
            "direction": (
                "Use a mobile-readable, scene-led commerce composition with an immediately recognizable product, "
                "believable scale, and one clear real-use idea rather than an empty studio-only frame."
            ),
        }
    if normalized_platform == "taobao":
        if primary_slot:
            return {
                "id": "taobao_high_impact_primary",
                "direction": (
                    "Use a high-impact product-first hero with polished lighting, clear silhouette, and a strong first "
                    "impression while keeping the actual product identity central."
                ),
            }
        return {
            "id": "taobao_detail_story",
            "direction": (
                "Use rich detail-page storytelling: one focused feature proof, material or scale evidence, and an "
                "intentionally layered but readable commercial composition."
            ),
        }
    if normalized_platform == "jd":
        return {
            "id": "jd_parameter_confidence",
            "direction": (
                "Use a clear, quality-confidence composition that makes the product, supplied parameters, material "
                "detail, and real-use evidence easy to compare without adding unsupported service claims."
            ),
        }
    if normalized_platform == "pinduoduo":
        return {
            "id": "pinduoduo_fast_comprehension",
            "direction": (
                "Make product type, supplied quantity or scale, and practical function immediately understandable; "
                "do not introduce price, discount, savings, or promotion claims."
            ),
        }
    if normalized_platform == "tiktok_shop":
        return {
            "id": "tiktok_real_use_hook" if traffic_slot else "tiktok_creator_real_use",
            "direction": (
                "Use a scroll-stopping but truthful real-use composition with a clear product identity, natural human "
                "scale when relevant, and one memorable visual hook without fabricated performance claims."
            ),
        }
    if normalized_platform == "shopify":
        return {
            "id": "shopify_brand_story",
            "direction": (
                "Use a brand-consistent product story with coherent lighting, material detail, and lifestyle context "
                "that can extend from a product page into a campaign without inventing brand facts."
            ),
        }
    return {
        "id": "generic_product_first",
        "direction": (
            "Use a clear product-first commercial composition with one evidence-backed visual purpose and no "
            "unsupported claims."
        ),
}
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
        canvas_rules = self._canvas_rules(platform)
        content_rules = self._content_rules(platform)
        export_rules = self._export_rules(platform)
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

    def _canvas_rules(self, platform: str) -> dict[str, Any]:
        if platform == "ozon":
            return {"primary_aspect_ratio": "1:1", "secondary_aspect_ratio": "3:4", "crop_safety_guidance": "keep the primary product evidence comfortably inside the canvas"}
        if platform == "tiktok_shop":
            return {"primary_aspect_ratio": "4:5", "secondary_aspect_ratio": "1:1", "crop_safety_guidance": "keep the primary product evidence comfortably inside the canvas"}
        if platform in {"taobao", "jd", "pinduoduo"}:
            return {"primary_aspect_ratio": "1:1", "secondary_aspect_ratio": "3:4", "crop_safety_guidance": "keep the primary product evidence comfortably inside the canvas"}
        if platform == "shopify":
            return {"primary_aspect_ratio": "4:5", "secondary_aspect_ratio": "16:9", "crop_safety_guidance": "keep the primary product evidence comfortably inside the canvas"}
        return {"primary_aspect_ratio": "1:1", "secondary_aspect_ratio": "4:5", "crop_safety_guidance": "keep the primary product evidence comfortably inside the canvas"}

    def _content_rules(self, platform: str) -> list[str]:
        rules = [
            "Product remains clear, large, and unobstructed.",
            "Claims must be supported by supplied facts or softened.",
            "Any requested in-image copy must be generated by the image provider and pass final-pixel review.",
            "Set uses a consistent product identity across all slots.",
        ]
        if platform == "amazon":
            rules.insert(0, "Main image should stay product-first with minimal distractions.")
        if platform == "ozon":
            rules.insert(0, "Main image should make the product immediately understandable on a mobile listing.")
            rules.append("Russian provider-native copy needs final-pixel readability review when explicitly requested.")
        if platform in {"taobao", "jd", "pinduoduo"}:
            rules.append("Detail and trust images may communicate supported evidence with provider-native creative treatment when requested.")
        if platform == "tiktok_shop":
            rules.append("Ad cover should communicate one hook within thumbnail viewing distance.")
        return rules

    def _export_rules(self, platform: str) -> dict[str, Any]:
        if platform == "ozon":
            return {"format": "png", "naming": "{slot}_{index}_ozon.png", "dimension_hint": "1200x1200"}
        if platform == "tiktok_shop":
            return {"format": "png", "naming": "{slot}_{index}_tiktok_shop.png", "dimension_hint": "1080x1350"}
        if platform in {"taobao", "jd", "pinduoduo"}:
            return {"format": "png", "naming": "{slot}_{index}_{platform}.png", "dimension_hint": "1200x1200"}
        if platform == "shopify":
            return {"format": "png", "naming": "{slot}_{index}_shopify.png", "dimension_hint": "1600x2000"}
        return {"format": "png", "naming": "{slot}_{index}_{platform}.png", "dimension_hint": "1200x1200"}

    def _text_policy(self, platform: str, image_slots: list[str]) -> dict[str, list[str]]:
        forbidden = [slot for slot in image_slots if slot in {"main_image", "hero_image"}]
        return {
            "text_forbidden_slots": forbidden,
            "text_enabled_slots": [slot for slot in image_slots if slot not in forbidden],
            "policy_owner": f"ecommerce_{platform}_profile",
        }
