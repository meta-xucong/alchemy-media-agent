"""Export metadata packaging for e-commerce image sets."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import EcommerceAssetRecipe, EcommerceExportPackage, MarketplaceRuleProfile


class EcommerceExportPackager:
    """Build platform-aware export metadata for the frontend and later storage adapters."""

    def package(
        self,
        *,
        job_key: str,
        marketplace_profile: MarketplaceRuleProfile,
        recipes: list[EcommerceAssetRecipe],
    ) -> EcommerceExportPackage:
        export_rules = marketplace_profile.export_rules
        naming = str(export_rules.get("naming") or "{slot}_{index}_{platform}.png")
        dimension_hint = str(export_rules.get("dimension_hint") or "1200x1200")
        files = []
        for index, recipe in enumerate(recipes, start=1):
            filename = naming.format(
                slot=recipe.slot,
                index=f"{index:02d}",
                platform=marketplace_profile.platform,
                market=marketplace_profile.market.lower(),
            )
            files.append(
                {
                    "slot": recipe.slot,
                    "filename": filename,
                    "dimension_hint": dimension_hint,
                    "format": export_rules.get("format", "png"),
                    "business_goal": recipe.business_goal,
                    "review_status": "needs_pixel_review",
                }
            )
        return EcommerceExportPackage(
            package_id=stable_id("ecommerce_export", job_key, marketplace_profile.platform, marketplace_profile.market),
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            files=files,
            naming_pattern=naming,
            dimensions={recipe.slot: dimension_hint for recipe in recipes},
            review_status="metadata_ready",
            metadata={
                "source": "EcommerceExportPackager",
                "file_count": len(files),
                "pixel_assets_required_before_download": True,
            },
        )
