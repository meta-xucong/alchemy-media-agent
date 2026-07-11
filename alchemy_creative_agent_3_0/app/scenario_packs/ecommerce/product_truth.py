"""Product truth locking for E-Commerce image generation."""

from __future__ import annotations

from typing import Any

from .contracts import ProductTruthLock
from .utils import as_list, clean_text, first_non_empty, unique_preserve_order


CATEGORY_HINTS = {
    "desk_lamp": ("lamp", "lighting", "light", "desk lamp", "table lamp"),
    "headphones": ("headphone", "earbud", "earphone", "bluetooth"),
    "skincare": ("skincare", "serum", "cream", "bottle", "cosmetic"),
    "perfume": ("perfume", "fragrance", "scent"),
    "drink": ("drink", "beverage", "tea", "coffee", "juice"),
    "home_storage": ("organizer", "storage", "rack", "shelf", "box"),
    "pet_product": ("pet", "dog", "cat"),
    "apparel": ("shirt", "shoe", "bag", "clothing", "apparel"),
}

CLAIM_RISK_TOKENS = ("certified", "fda", "medical", "cure", "patent", "100%", "guarantee", "guaranteed")


def claim_review_required(text: str, unsupported_claims: list[str] | None = None) -> bool:
    lower = text.lower()
    if any(token in lower for token in CLAIM_RISK_TOKENS):
        return True
    return any(claim.lower() in lower for claim in unsupported_claims or [] if claim)


class ProductTruthLockBuilder:
    """Build a deterministic first-pass product truth lock from supplied evidence."""

    def build(
        self,
        *,
        user_input: str,
        product_profile: dict[str, Any],
        uploaded_asset_ids: list[str],
        parameters: dict[str, Any],
    ) -> ProductTruthLock:
        category = self._category(user_input, product_profile, parameters)
        visible_attributes = self._visible_attributes(product_profile, uploaded_asset_ids)
        immutable_attributes = unique_preserve_order(
            [
                *as_list(product_profile.get("immutable_attributes")),
                *visible_attributes,
                "product shape and proportions",
                "visible logo or label text",
                "material and finish",
                "included components and quantity",
            ]
        )
        evidence_sources = self._evidence_sources(product_profile, uploaded_asset_ids)
        claims = as_list(product_profile.get("claims"))
        unsupported_claims = [
            claim
            for claim in claims
            if self._claim_requires_evidence(claim) and not as_list(product_profile.get("evidence") or product_profile.get("evidence_sources"))
        ]
        warnings = [f"Claim needs evidence before visual use: {claim}" for claim in unsupported_claims]
        if not uploaded_asset_ids:
            warnings.append("No product image was supplied; product truth must be reviewed manually.")

        return ProductTruthLock(
            product_category=category,
            visible_attributes=visible_attributes,
            immutable_attributes=immutable_attributes,
            allowed_scene_changes=[
                "background replacement",
                "lighting polish",
                "lifestyle environment",
                "props that do not block the product",
                "platform-safe overlay labels",
            ],
            forbidden_transformations=[
                "changing product shape",
                "changing material or color without user evidence",
                "inventing certifications, test results, patents, or awards",
                "removing or distorting visible logos and labels",
                "changing package count, included accessories, or functional claims",
            ],
            evidence_sources=evidence_sources,
            confidence={
                "uploaded_image": 0.86 if uploaded_asset_ids else 0.0,
                "user_text": 0.68 if clean_text(user_input) else 0.0,
                "product_specs": 0.78 if product_profile else 0.0,
            },
            review_obligations=[
                "Product silhouette remains recognizable in every slot.",
                "Logo, label, material, color, quantity, and visible components match supplied evidence.",
                "Unsupported claims are removed or softened before export.",
                "Overlay text does not cover key product details.",
            ],
            warnings=warnings,
            metadata={
                "source": "ProductTruthLockBuilder",
                "unsupported_claims": unsupported_claims,
                "uploaded_asset_count": len(uploaded_asset_ids),
            },
        )

    def _category(self, user_input: str, product_profile: dict[str, Any], parameters: dict[str, Any]) -> str:
        explicit = first_non_empty(
            product_profile.get("product_category"),
            product_profile.get("category"),
            parameters.get("product_category"),
            parameters.get("category"),
        )
        if explicit:
            return explicit.lower().replace(" ", "_")
        lower = f"{user_input} {product_profile}".lower()
        for category, tokens in CATEGORY_HINTS.items():
            if any(token in lower for token in tokens):
                return category
        return "generic_product"

    def _visible_attributes(self, profile: dict[str, Any], uploaded_asset_ids: list[str]) -> list[str]:
        fields = [
            "visible_attributes",
            "facts",
            "product_specs",
            "specs",
            "materials",
            "material",
            "color",
            "colors",
            "dimensions",
            "size",
            "components",
            "package",
            "quantity",
            "logo",
            "brand_or_project_name",
            "brand_name",
        ]
        values: list[str] = []
        for field in fields:
            values.extend(as_list(profile.get(field)))
        if uploaded_asset_ids:
            values.append(f"{len(uploaded_asset_ids)} uploaded product/reference image(s)")
        return unique_preserve_order(values)[:16]

    def _evidence_sources(self, profile: dict[str, Any], uploaded_asset_ids: list[str]) -> list[str]:
        sources = [f"uploaded_asset:{asset_id}" for asset_id in uploaded_asset_ids]
        if clean_text(profile.get("description")):
            sources.append("product description")
        if as_list(profile.get("product_specs") or profile.get("specs")):
            sources.append("product specs")
        if as_list(profile.get("claims")):
            sources.append("supplied claims")
        if as_list(profile.get("evidence") or profile.get("evidence_sources")):
            sources.append("claim evidence")
        return sources or ["user prompt"]

    def _claim_requires_evidence(self, claim: str) -> bool:
        return claim_review_required(claim)
