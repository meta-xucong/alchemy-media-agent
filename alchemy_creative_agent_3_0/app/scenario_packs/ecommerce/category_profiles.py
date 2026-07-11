"""Versioned, commerce-owned category evidence profiles."""

from __future__ import annotations

from dataclasses import dataclass


CATEGORY_PROFILE_VERSION = "v3_ecommerce_categories_2026_07_12"


@dataclass(frozen=True)
class CategoryProfile:
    category_id: str
    display_name: str
    required_evidence: tuple[str, ...]
    optional_evidence: tuple[str, ...]
    default_slot_priority: tuple[str, ...]
    review_checks: tuple[str, ...]

    def metadata(self) -> dict[str, object]:
        return {
            "category_id": self.category_id,
            "category_profile_version": CATEGORY_PROFILE_VERSION,
            "required_evidence": list(self.required_evidence),
            "optional_evidence": list(self.optional_evidence),
        }


_PROFILES = {
    "apparel": CategoryProfile(
        "apparel", "Apparel, shoes, and bags",
        ("fit and silhouette", "front/back/side visibility", "material or texture", "wear context"),
        ("styling combination", "size guidance"),
        ("main_image", "feature_image_1", "scenario_image", "detail_image", "size_spec_image", "trust_image"),
        ("preserve garment construction", "keep human proportions natural", "show fit evidence when requested"),
    ),
    "beauty": CategoryProfile(
        "beauty", "Beauty and skincare",
        ("package identity", "texture or application", "usage context"),
        ("routine scene", "ingredient or benefit proof when supplied"),
        ("main_image", "feature_image_1", "detail_image", "scenario_image", "trust_image", "size_spec_image"),
        ("preserve package and label", "do not invent ingredients or medical claims", "keep effect claims evidence-backed"),
    ),
    "electronics": CategoryProfile(
        "electronics", "Electronics and 3C",
        ("product silhouette", "ports or functional structure", "scale", "real-use context"),
        ("included accessories", "compatibility or specification proof"),
        ("main_image", "feature_image_1", "detail_image", "size_spec_image", "scenario_image", "trust_image"),
        ("preserve ports and controls", "do not invent accessories", "do not alter logo or connector layout"),
    ),
    "home_kitchen": CategoryProfile(
        "home_kitchen", "Home and kitchen",
        ("size and space fit", "material", "function", "capacity or quantity when confirmed"),
        ("cleaning or storage", "before/after only when truthful"),
        ("main_image", "scenario_image", "feature_image_1", "detail_image", "size_spec_image", "trust_image"),
        ("preserve material and structure", "do not invent capacity", "keep use scene practical and believable"),
    ),
    "food_beverage": CategoryProfile(
        "food_beverage", "Food and beverage",
        ("package identity", "serving or contents", "portion or scale", "consumption context"),
        ("ingredient detail when supplied", "gift or bundle presentation"),
        ("main_image", "scenario_image", "detail_image", "size_spec_image", "feature_image_1", "trust_image"),
        ("preserve label and package count", "do not invent ingredients", "avoid unsupported health claims"),
    ),
}


_ALIASES = {
    "clothing": "apparel", "fashion": "apparel", "shoes": "apparel", "bags": "apparel",
    "skincare": "beauty", "cosmetics": "beauty", "makeup": "beauty",
    "3c": "electronics", "electronic": "electronics", "headphones": "electronics", "earbuds": "electronics",
    "home": "home_kitchen", "kitchen": "home_kitchen", "furniture": "home_kitchen",
    "drink": "food_beverage", "beverage": "food_beverage", "food": "food_beverage",
}


def resolve_category(product_category: str | None, *, user_input: str = "") -> CategoryProfile | None:
    raw = " ".join([str(product_category or ""), str(user_input or "")]).strip().lower()
    normalized = raw.replace("-", "_").replace("/", " ")
    for category_id, profile in _PROFILES.items():
        if category_id in normalized:
            return profile
    for alias, category_id in _ALIASES.items():
        if alias in normalized:
            return _PROFILES[category_id]
    return None


def list_category_profiles() -> tuple[CategoryProfile, ...]:
    return tuple(_PROFILES.values())

