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
        localization_review_required = False
        claim_review_required = False
        category_ids = list(
            dict.fromkeys(
                str(recipe.metadata.get("category_id"))
                for recipe in recipes
                if recipe.metadata.get("category_id")
            )
        )
        category_profile_versions = list(
            dict.fromkeys(
                str(recipe.metadata.get("category_profile_version"))
                for recipe in recipes
                if recipe.metadata.get("category_profile_version")
            )
        )
        for index, recipe in enumerate(recipes, start=1):
            copy_plan = recipe.metadata.get("copy_plan") or {}
            copy_review_required = bool(copy_plan.get("needs_localization_review"))
            copy_claim_review_required = bool(copy_plan.get("claim_review_required"))
            localization_review_required = localization_review_required or copy_review_required
            claim_review_required = claim_review_required or copy_claim_review_required
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
                    "overlay_text": recipe.overlay_text,
                    "copy_locale": copy_plan.get("copy_locale"),
                    "copy_source": copy_plan.get("source"),
                    "copy_review_required": copy_review_required,
                    "claim_review_required": copy_claim_review_required,
                    "marketplace_profile_id": marketplace_profile.metadata.get("profile_id"),
                    "marketplace_profile_version": marketplace_profile.metadata.get("profile_version"),
                }
            )
        return EcommerceExportPackage(
            package_id=stable_id("ecommerce_export", job_key, marketplace_profile.platform, marketplace_profile.market),
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            files=files,
            naming_pattern=naming,
            dimensions={recipe.slot: dimension_hint for recipe in recipes},
            review_status="attention" if localization_review_required or claim_review_required else "metadata_ready",
            metadata={
                "source": "EcommerceExportPackager",
                "file_count": len(files),
                "pixel_assets_required_before_download": True,
                "copy_locale": marketplace_profile.metadata.get("copy_locale"),
                "localization_review_required": localization_review_required,
                "claim_review_required": claim_review_required,
                "marketplace_profile_id": marketplace_profile.metadata.get("profile_id"),
                "marketplace_profile_version": marketplace_profile.metadata.get("profile_version"),
                "marketplace_profile_status": marketplace_profile.metadata.get("profile_status"),
                "marketplace_profile_source_notes": marketplace_profile.metadata.get("profile_source_notes"),
                "category_ids": category_ids,
                "category_profile_versions": category_profile_versions,
            },
        )
