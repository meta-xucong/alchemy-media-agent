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
        (
            "main_image",
            "feature_image_1",
            "feature_image_2",
            "detail_image",
            "scenario_image",
            "size_spec_image",
            "trust_comparison_image",
        ),
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
        "feature_image_1": ("fit and silhouette", "front/back/side visibility"),
        "feature_image_2": ("front/back/side visibility",),
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


_SLOT_GUIDANCE = {
    "apparel": {
        "main_image": (
            "apparel_primary_silhouette",
            "Show the complete garment in its supplied reference silhouette, color, pattern scale, and construction; do not substitute a generic garment.",
        ),
        "feature_image_1": (
            "apparel_worn_front_fit",
            "Show an honest front worn view that makes fit, silhouette, and the supplied front construction clear without hiding the garment behind props.",
        ),
        "feature_image_2": (
            "apparel_back_or_side_construction",
            "Show a distinct back or side construction view when that construction is supported by supplied evidence; otherwise use a distinct truthful angle and do not invent garment details.",
        ),
        "detail_image": (
            "apparel_material_or_embroidery_detail",
            "Show a close, correctly located textile, stitching, embroidery, or hardware detail while preserving the supplied pattern scale and finish.",
        ),
        "scenario_image": (
            "apparel_real_wear_context",
            "Show a believable adult wear context with natural posture and styling, while keeping the garment visibly identifiable and fit-relevant.",
        ),
        "size_spec_image": (
            "apparel_fit_or_size_evidence",
            "Use supplied size facts only; without confirmed measurements, show fit or relative-scale evidence and do not invent a size chart.",
        ),
        "trust_comparison_image": (
            "apparel_styling_versatility",
            "Show distinct, truthful styling alternatives using the same garment; do not imply a performance, certification, or comparison claim.",
        ),
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


def slot_guidance_for(
    profile: CategoryProfile | None,
    slot: str,
    *,
    product_category: str = "",
) -> dict[str, str]:
    if profile is None:
        return {"id": "", "direction": ""}
    if profile.category_id == "apparel" and any(
        token in product_category.lower()
        for token in ("shoe", "sneaker", "boot", "sandal", "bag", "handbag", "backpack", "luggage")
    ):
        return {"id": "", "direction": ""}
    guidance = _SLOT_GUIDANCE.get(profile.category_id, {}).get(slot)
    if not guidance:
        return {"id": "", "direction": ""}
    guidance_id, direction = guidance
    return {"id": guidance_id, "direction": direction}
