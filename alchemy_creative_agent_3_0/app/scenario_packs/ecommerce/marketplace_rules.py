"""Versioned marketplace constraints for remote-Brain reasoning.

These records are evidence/provenance only.  They deliberately contain no
automatic suite slots, camera recipes, composition defaults, or text regions.
"""

from __future__ import annotations

from typing import Any

from .contracts import MarketplaceRuleProfile
from .localization import resolve_localization
from .utils import clean_text


PROFILE_VERSION = "v3_ecommerce_constraints_2026_07_13"
PROFILE_UPDATED_AT = "2026-07-13"
PROFILE_STATUS = "internal_draft"

PROFILE_SOURCE_NOTES = {
    "amazon": "Internal strategic evidence; confirm current Seller Central requirements before publishing.",
    "ozon": "Internal strategic evidence; confirm current Ozon seller requirements before publishing.",
    "taobao": "Internal strategic evidence; confirm current Taobao/Tmall requirements before publishing.",
    "jd": "Internal strategic evidence; confirm current JD requirements before publishing.",
    "pinduoduo": "Internal strategic evidence; confirm current Pinduoduo requirements before publishing.",
    "tiktok_shop": "Internal strategic evidence; confirm current TikTok Shop requirements before publishing.",
    "shopify": "Internal store-design evidence, not a third-party marketplace policy.",
    "generic": "Internal generic commerce evidence; no marketplace policy is implied.",
}

PLATFORM_ALIASES = {
    "amazon_us": ("amazon", "US"), "amazon": ("amazon", "US"),
    "ozon": ("ozon", "RU"), "shopify": ("shopify", "global"),
    "tiktok_shop": ("tiktok_shop", "global"), "tiktok": ("tiktok_shop", "global"),
    "taobao": ("taobao", "CN"), "tmall": ("taobao", "CN"),
    "jd": ("jd", "CN"), "jingdong": ("jd", "CN"),
    "pdd": ("pinduoduo", "CN"), "pinduoduo": ("pinduoduo", "CN"),
    "generic": ("generic", "global"), "ecommerce_generic": ("generic", "global"),
}


class MarketplaceRuleEngine:
    """Return platform constraints without deciding what images to make."""

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
        localization = resolve_localization(
            platform=platform,
            market=market,
            requested_locale=parameters.get("copy_locale") or parameters.get("locale"),
        )
        return MarketplaceRuleProfile(
            platform=platform,
            market=market,
            image_slots=[],
            canvas_rules=self._canvas_constraints(platform),
            content_rules=self._content_constraints(platform),
            export_rules=self._export_rules(platform),
            warnings=["Marketplace guidance is versioned evidence, not live legal or platform-policy advice."],
            metadata={
                "source": "MarketplaceRuleEngine",
                "profile_id": f"ecommerce_{platform}_{market.lower()}",
                "profile_version": PROFILE_VERSION,
                "profile_updated_at": PROFILE_UPDATED_AT,
                "profile_status": PROFILE_STATUS,
                "profile_source_notes": PROFILE_SOURCE_NOTES.get(platform, PROFILE_SOURCE_NOTES["generic"]),
                "raw_platform_profile": raw_platform,
                "live_policy_lookup": False,
                "text_policy": self._text_constraint(platform),
                "creative_slot_map_present": False,
                **localization.metadata(),
            },
        )

    def _canvas_constraints(self, platform: str) -> dict[str, Any]:
        hints = {
            "ozon": ("1:1", "3:4"),
            "tiktok_shop": ("4:5", "1:1"),
            "taobao": ("1:1", "3:4"),
            "jd": ("1:1", "3:4"),
            "pinduoduo": ("1:1", "3:4"),
            "shopify": ("4:5", "16:9"),
        }
        primary, alternate = hints.get(platform, ("1:1", "4:5"))
        return {
            "preferred_delivery_aspect_ratios": [primary, alternate],
            "constraint_type": "technical_delivery_hint",
            "creative_composition_owner": "remote_llm_and_image_provider",
        }

    def _content_constraints(self, platform: str) -> list[str]:
        rules = [
            "Keep supported product facts and visible identity faithful to supplied evidence.",
            "Do not make unsupported claims, certifications, awards, ingredients, compatibility, or performance promises.",
            "If literal copy is explicitly approved, render it only as part of the complete provider image and inspect final pixels.",
            "Keep output treatment responsive to the current product, request, and platform constraints rather than a fixed marketplace template.",
        ]
        platform_notes = {
            "amazon": "Confirm current category-specific primary-listing requirements before publication; the Brain must not assume a reusable Amazon shot recipe.",
            "ozon": "Confirm current Ozon listing requirements for the market before publication; Russian requested copy needs final-pixel review.",
            "taobao": "Confirm current Taobao/Tmall listing requirements before publication; do not infer a fixed detail-page sequence.",
            "jd": "Confirm current JD listing requirements before publication; do not infer a fixed detail-page sequence.",
            "pinduoduo": "Confirm current Pinduoduo listing requirements before publication.",
            "tiktok_shop": "Confirm current TikTok Shop listing and advertising requirements before publication.",
            "shopify": "Use seller/store requirements as the authority; no third-party marketplace policy is implied.",
        }
        if platform in platform_notes:
            rules.append(platform_notes[platform])
        return rules

    def _export_rules(self, platform: str) -> dict[str, Any]:
        dimensions = {
            "ozon": "1200x1200", "tiktok_shop": "1080x1350",
            "taobao": "1200x1200", "jd": "1200x1200", "pinduoduo": "1200x1200",
            "shopify": "1600x2000",
        }
        return {
            "format": "png",
            "naming": "{opaque_output_id}.png",
            "dimension_hint": dimensions.get(platform, "1200x1200"),
            "creative_slot_map_present": False,
        }

    def _text_constraint(self, platform: str) -> dict[str, str]:
        return {
            "default": "provider_native_only",
            "primary_listing_requirement": (
                "verify_current_platform_policy_before_publication"
                if platform in {"amazon", "ozon", "taobao", "jd", "pinduoduo", "tiktok_shop"}
                else "seller_decides"
            ),
            "local_renderer": "forbidden",
        }
