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
            return {"primary_aspect_ratio": "1:1", "secondary_aspect_ratio": "3:4", "safe_area": "center 84%"}
        if platform == "tiktok_shop":
            return {"primary_aspect_ratio": "4:5", "secondary_aspect_ratio": "1:1", "safe_area": "center 82%"}
        if platform in {"taobao", "jd", "pinduoduo"}:
            return {"primary_aspect_ratio": "1:1", "secondary_aspect_ratio": "3:4", "safe_area": "center 86%"}
        if platform == "shopify":
            return {"primary_aspect_ratio": "4:5", "secondary_aspect_ratio": "16:9", "safe_area": "center 84%"}
        return {"primary_aspect_ratio": "1:1", "secondary_aspect_ratio": "4:5", "safe_area": "center 85%"}

    def _content_rules(self, platform: str) -> list[str]:
        rules = [
            "Product remains clear, large, and unobstructed.",
            "Claims must be supported by supplied facts or softened.",
            "Overlay text must be short and readable.",
            "Set uses a consistent product identity across all slots.",
        ]
        if platform == "amazon":
            rules.insert(0, "Main image should stay product-first with minimal distractions.")
        if platform == "ozon":
            rules.insert(0, "Main image should make the product immediately understandable on a mobile listing.")
            rules.append("Russian overlay copy must remain short and readable when a text-enabled slot is selected.")
        if platform in {"taobao", "jd", "pinduoduo"}:
            rules.append("Detail and trust images may use denser feature callouts when readable.")
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
