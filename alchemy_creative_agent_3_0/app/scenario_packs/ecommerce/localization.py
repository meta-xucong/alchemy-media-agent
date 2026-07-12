"""Versioned locale guidance for commerce copy plans.

This module plans locale ownership and review. It intentionally does not claim
to translate product copy or render final typography.
"""

from __future__ import annotations

from dataclasses import dataclass

from .utils import clean_text


LOCALIZATION_PROFILE_VERSION = "v3_ecommerce_localization_2026_07_12"


@dataclass(frozen=True)
class LocalizationProfile:
    locale: str
    language: str
    market: str
    max_characters_by_slot: dict[str, int]

    def character_limit(self, slot: str) -> int:
        return self.max_characters_by_slot.get(slot, self.max_characters_by_slot["default"])

    def metadata(self) -> dict[str, object]:
        return {
            "copy_locale": self.locale,
            "copy_language": self.language,
            "localization_profile_version": LOCALIZATION_PROFILE_VERSION,
        }


_DEFAULT_LIMITS = {
    "default": 44,
    "detail_image": 46,
    "size_spec_image": 46,
    "trust_image": 42,
    "trust_comparison_image": 42,
    "ad_cover": 38,
    "benefit_hook": 38,
    "store_banner": 38,
    "collection_cover": 38,
}


def resolve_localization(*, platform: str, market: str, requested_locale: str | None = None) -> LocalizationProfile:
    locale = clean_text(requested_locale).replace("_", "-")
    if not locale:
        if platform == "ozon" or market.upper() == "RU":
            locale = "ru-RU"
        elif platform in {"taobao", "jd", "pinduoduo"} or market.upper() == "CN":
            locale = "zh-CN"
        else:
            locale = "en-US"
    language = locale.split("-", 1)[0].lower()
    return LocalizationProfile(locale=locale, language=language, market=market, max_characters_by_slot=dict(_DEFAULT_LIMITS))
