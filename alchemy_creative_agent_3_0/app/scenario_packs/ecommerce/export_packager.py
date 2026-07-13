"""Export metadata packaging for e-commerce image sets."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import CommerceCriticReport, EcommerceAssetRecipe, EcommerceCreativeContext, EcommerceExportPackage, MarketplaceRuleProfile


class EcommerceExportPackager:
    """Build platform-aware export metadata for the frontend and later storage adapters."""

    def package(
        self,
        *,
        job_key: str,
        marketplace_profile: MarketplaceRuleProfile,
        recipes: list[EcommerceAssetRecipe],
        critic: CommerceCriticReport | None = None,
    ) -> EcommerceExportPackage:
        # Kept to deserialize historic calls only.  New jobs must bind files
        # after the provider produces opaque Brain-selected outputs.
        del recipes
        localization_review_required = False
        claim_review_required = bool(critic and critic.status == "attention")
        publish_checks = self._publish_checks(
            marketplace_profile=marketplace_profile,
            critic=critic,
            localization_review_required=localization_review_required,
            claim_review_required=claim_review_required,
        )
        return EcommerceExportPackage(
            package_id=stable_id("ecommerce_export", job_key, marketplace_profile.platform, marketplace_profile.market),
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            files=[],
            naming_pattern="{opaque_output_id}.png",
            dimensions={},
            review_status="attention",
            metadata={
                "source": "EcommerceExportPackager",
                "file_count": 0,
                "pixel_assets_required_before_download": True,
                "copy_locale": marketplace_profile.metadata.get("copy_locale"),
                "localization_review_required": localization_review_required,
                "claim_review_required": claim_review_required,
                "marketplace_profile_id": marketplace_profile.metadata.get("profile_id"),
                "marketplace_profile_version": marketplace_profile.metadata.get("profile_version"),
                "marketplace_profile_status": marketplace_profile.metadata.get("profile_status"),
                "marketplace_profile_source_notes": marketplace_profile.metadata.get("profile_source_notes"),
                "historical_recipe_input_ignored": True,
                "creative_recipe_present": False,
                "publish_checks": publish_checks,
                "publish_summary": self._publish_summary([], publish_checks),
            },
        )

    def package_context(
        self,
        *,
        job_key: str,
        context: EcommerceCreativeContext,
        marketplace_profile: MarketplaceRuleProfile,
        critic: CommerceCriticReport | None = None,
    ) -> EcommerceExportPackage:
        """Return pre-generation metadata without inventing export files."""

        publish_checks = self._publish_checks(
            marketplace_profile=marketplace_profile,
            critic=critic,
            localization_review_required=bool(context.approved_literal_copy),
            claim_review_required=bool(context.claim_risk_warnings),
        )
        return EcommerceExportPackage(
            package_id=stable_id("ecommerce_export", job_key, marketplace_profile.platform, marketplace_profile.market),
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            files=[],
            naming_pattern="{opaque_output_id}.png",
            dimensions={},
            review_status="attention",
            metadata={
                "source": "EcommerceExportPackager.package_context",
                "ecommerce_context_id": context.context_id,
                "creative_recipe_present": False,
                "pixel_assets_required_before_download": True,
                "marketplace_profile_id": marketplace_profile.metadata.get("profile_id"),
                "marketplace_profile_version": marketplace_profile.metadata.get("profile_version"),
                "marketplace_profile_status": marketplace_profile.metadata.get("profile_status"),
                "copy_locale": context.copy_locale,
                "publish_checks": publish_checks,
                "publish_summary": "Remote Brain direction and provider-rendered final pixels are required before export.",
            },
        )

    def _publish_checks(
        self,
        *,
        marketplace_profile: MarketplaceRuleProfile,
        critic: CommerceCriticReport | None,
        localization_review_required: bool,
        claim_review_required: bool,
    ) -> list[dict[str, str]]:
        checks = [
            {
                "id": "product_truth",
                "status": "attention",
                "message": "Before publishing, verify shape, label, material, color, quantity, and included items against the real product.",
            },
            {
                "id": "platform_profile",
                "status": "attention" if marketplace_profile.metadata.get("profile_status") != "reviewed" else "ready",
                "message": "Confirm current platform image requirements before publishing; this profile is versioned planning guidance.",
            },
        ]
        if localization_review_required:
            checks.append(
                {
                    "id": "localized_copy",
                    "status": "attention",
                    "message": "Have a native-language reviewer confirm requested provider-native copy in the final image before export.",
                }
            )
        if claim_review_required:
            checks.append(
                {
                    "id": "claim_evidence",
                    "status": "attention",
                    "message": "Verify evidence and platform eligibility for requested claims before publishing.",
                }
            )
        if critic:
            for check in critic.checks:
                if check["status"] == "attention" and check["id"] in {"category_evidence_coverage", "suite_differentiation"}:
                    checks.append(
                        {
                            "id": check["id"],
                            "status": "attention",
                            "message": check["detail"],
                        }
                    )
        return checks

    def _publish_summary(self, files: list[dict], checks: list[dict[str, str]]) -> str:
        attention = [check["id"].replace("_", " ") for check in checks if check["status"] == "attention"]
        if attention:
            return f"{len(files)} planned image(s). Review before publishing: {', '.join(attention)}."
        return f"{len(files)} planned image(s). Metadata checks are ready for final pixel review."
