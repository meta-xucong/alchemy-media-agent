"""E-Commerce-only delivery scope contracts and legacy suite compatibility."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .utils import clean_text


DELIVERY_SCOPE_VERSION = "v3_ecommerce_delivery_scopes_2026_07_12"
LISTING_ONLY = "listing_only"
LISTING_PLUS_A_PLUS = "listing_plus_a_plus_planning"
CONTENT_ASSETS = "content_assets"
STOREFRONT_ASSETS = "storefront_assets"


@dataclass(frozen=True)
class DeliveryScope:
    scope_id: str
    label: str
    description: str
    slot_ids: tuple[str, ...]
    requires_placement_context: bool = False


_SCOPES = {
    LISTING_ONLY: DeliveryScope(
        scope_id=LISTING_ONLY,
        label="Listing only",
        description="Listing image roles only; no A+, content, or storefront deliverables are implied.",
        slot_ids=(),
    ),
    LISTING_PLUS_A_PLUS: DeliveryScope(
        scope_id=LISTING_PLUS_A_PLUS,
        label="Listing plus A+ planning",
        description="Plans distinct A+ image modules only; it does not promise final rendered text pixels.",
        slot_ids=("a_plus_brand_story", "a_plus_feature_proof", "a_plus_comparison_context"),
        requires_placement_context=True,
    ),
    CONTENT_ASSETS: DeliveryScope(
        scope_id=CONTENT_ASSETS,
        label="Content assets",
        description="Plans content-cover, feature-hook, and creator/use image roles separately from listing roles.",
        slot_ids=("content_cover", "content_feature_hook", "content_creator_context"),
    ),
    STOREFRONT_ASSETS: DeliveryScope(
        scope_id=STOREFRONT_ASSETS,
        label="Storefront assets",
        description="Plans merchant storefront roles only when a merchant or theme placement is supplied.",
        slot_ids=("storefront_hero", "storefront_collection", "storefront_feature"),
        requires_placement_context=True,
    ),
}

_LEGACY_SUITE_SCOPE_MAP = {
    "recommended": LISTING_ONLY,
    "listing_core": LISTING_ONLY,
    "listing_full": LISTING_ONLY,
    "detail_supplement": LISTING_ONLY,
}

_LISTING_SLOT_IDS = {
    "main_image",
    "hero_image",
    "feature_image_1",
    "feature_image_2",
    "benefit_image",
    "detail_image",
    "scenario_image",
    "size_spec_image",
    "trust_image",
    "trust_comparison_image",
}


def resolve_delivery_scope(
    parameters: dict[str, Any] | None,
    *,
    product_category: str = "",
    market: str = "",
) -> dict[str, Any]:
    """Resolve an additive delivery scope without interpreting legacy scope as a new package."""

    values = dict(parameters or {})
    requested = clean_text(
        values.get("delivery_scope")
        or values.get("ecommerce_delivery_scope")
        or values.get("delivery_scope_id")
    ).lower()
    legacy_scope = clean_text(values.get("legacy_suite_scope") or values.get("suite_scope") or values.get("ecommerce_suite_scope")).lower()
    source = "explicit_delivery_scope" if requested in _SCOPES else "legacy_suite_scope" if legacy_scope in _LEGACY_SUITE_SCOPE_MAP else "default_listing_only"
    scope_id = requested if requested in _SCOPES else _LEGACY_SUITE_SCOPE_MAP.get(legacy_scope, LISTING_ONLY)
    scope = _SCOPES[scope_id]
    placement_context = clean_text(values.get("placement_context") or values.get("a_plus_placement_context") or values.get("storefront_placement_context"))
    missing_requirements: list[str] = []
    if scope.requires_placement_context:
        if not placement_context:
            missing_requirements.append("merchant placement context")
        if not clean_text(product_category):
            missing_requirements.append("product category")
        if not clean_text(market) or clean_text(market).lower() == "global":
            missing_requirements.append("target market")
    ready = not missing_requirements
    return {
        "delivery_scope_id": scope.scope_id,
        "delivery_scope_label": scope.label,
        "delivery_scope_description": scope.description,
        "delivery_scope_version": DELIVERY_SCOPE_VERSION,
        "delivery_scope_source": source,
        "legacy_suite_scope": legacy_scope or None,
        "placement_context_provided": bool(placement_context),
        "requires_placement_context": scope.requires_placement_context,
        "missing_requirements": missing_requirements,
        "status": "ready" if ready else "needs_placement_context",
        "slot_ids": list(scope.slot_ids) if ready else [],
        "text_pixel_delivery_promised": False,
    }


def slots_for_scope(default_listing_slots: list[str], resolved_scope: dict[str, Any]) -> list[str]:
    """Return scope-owned slots; special scopes never reuse listing role names."""

    scope_id = str(resolved_scope.get("delivery_scope_id") or LISTING_ONLY)
    if scope_id == LISTING_ONLY:
        return [slot for slot in default_listing_slots if slot in _LISTING_SLOT_IDS]
    return [str(slot) for slot in resolved_scope.get("slot_ids") or [] if str(slot)]


def delivery_scope_metadata(resolved_scope: dict[str, Any]) -> dict[str, Any]:
    """Keep scope lineage compact and safe for recipes, exports, and historical jobs."""

    return {
        key: resolved_scope.get(key)
        for key in (
            "delivery_scope_id",
            "delivery_scope_label",
            "delivery_scope_description",
            "delivery_scope_version",
            "delivery_scope_source",
            "legacy_suite_scope",
            "placement_context_provided",
            "requires_placement_context",
            "missing_requirements",
            "status",
            "text_pixel_delivery_promised",
        )
    }
