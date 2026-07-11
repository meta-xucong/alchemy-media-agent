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
        ("size and space fit", "material", "function"),
        ("capacity or quantity when confirmed", "cleaning or storage", "before/after only when truthful"),
        ("main_image", "feature_image_1", "scenario_image", "detail_image", "size_spec_image", "trust_image"),
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
    "clothing": "apparel", "fashion": "apparel", "shoes": "apparel", "bag": "apparel", "bags": "apparel", "shirt": "apparel",
    "skincare": "beauty", "cosmetics": "beauty", "makeup": "beauty", "serum": "beauty", "cream": "beauty",
    "3c": "electronics", "electronic": "electronics", "headphones": "electronics", "earbuds": "electronics",
    "keyboard": "electronics", "phone": "electronics", "tablet": "electronics", "computer": "electronics",
    "home": "home_kitchen", "kitchen": "home_kitchen", "furniture": "home_kitchen", "lamp": "home_kitchen",
    "lighting": "home_kitchen", "organizer": "home_kitchen", "storage": "home_kitchen",
    "drink": "food_beverage", "beverage": "food_beverage", "food": "food_beverage",
}


_SLOT_EVIDENCE = {
    "apparel": {
        "main_image": ("fit and silhouette",),
        "feature_image_1": ("front/back/side visibility",),
        "detail_image": ("material or texture",),
        "scenario_image": ("wear context",),
        "size_spec_image": ("size guidance",),
    },
    "beauty": {
        "main_image": ("package identity",),
        "feature_image_1": ("texture or application",),
        "detail_image": ("package identity",),
        "scenario_image": ("usage context",),
    },
    "electronics": {
        "main_image": ("product silhouette",),
        "feature_image_1": ("ports or functional structure",),
        "detail_image": ("ports or functional structure",),
        "size_spec_image": ("scale",),
        "scenario_image": ("real-use context",),
    },
    "home_kitchen": {
        "main_image": ("material",),
        "feature_image_1": ("function",),
        "detail_image": ("material",),
        "size_spec_image": ("size and space fit",),
        "scenario_image": ("function",),
    },
    "food_beverage": {
        "main_image": ("package identity",),
        "feature_image_1": ("serving or contents",),
        "detail_image": ("serving or contents",),
        "size_spec_image": ("portion or scale",),
        "scenario_image": ("consumption context",),
    },
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


def evidence_for_slot(profile: CategoryProfile | None, slot: str) -> tuple[str, ...]:
    if profile is None:
        return ()
    return _SLOT_EVIDENCE.get(profile.category_id, {}).get(slot, ())
