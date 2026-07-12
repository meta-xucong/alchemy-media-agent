"""Export metadata packaging for e-commerce image sets."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import CommerceCriticReport, EcommerceAssetRecipe, EcommerceExportPackage, MarketplaceRuleProfile


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
        export_rules = marketplace_profile.export_rules
        naming = str(export_rules.get("naming") or "{slot}_{index}_{platform}.png")
        dimension_hint = str(export_rules.get("dimension_hint") or "1200x1200")
        files = []
        localization_review_required = False
        claim_review_required = False
        pending_product_facts: dict[str, dict] = {}
        blocked_product_fact_ids: set[str] = set()
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
            fact_bindings = list(recipe.metadata.get("product_fact_bindings") or [])
            pending_fact_ids = [str(item) for item in recipe.metadata.get("pending_product_fact_ids") or [] if str(item)]
            for fact in fact_bindings:
                if isinstance(fact, dict) and str(fact.get("fact_id") or "") in pending_fact_ids:
                    pending_product_facts[str(fact["fact_id"])] = fact
            blocked_product_fact_ids.update(
                str(item) for item in recipe.metadata.get("blocked_product_fact_ids") or [] if str(item)
            )
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
                    "evidence_intent_id": recipe.metadata.get("evidence_intent_id"),
                    "platform_compliance_intent_id": recipe.metadata.get("platform_compliance_intent_id"),
                    "platform_compliance_evidence_tier": recipe.metadata.get("platform_compliance_evidence_tier"),
                    "creative_strategy_id": recipe.metadata.get("creative_strategy_id"),
                    "creative_strategy_applied": recipe.metadata.get("creative_strategy_applied"),
                    "product_fact_ledger_version": recipe.metadata.get("product_fact_ledger_version"),
                    "product_fact_bindings": fact_bindings,
                    "pending_product_fact_ids": pending_fact_ids,
                    "format": export_rules.get("format", "png"),
                    "business_goal": recipe.business_goal,
                    "review_status": "needs_pixel_review",
                    "overlay_text": recipe.overlay_text,
                    "provider_native_text": recipe.provider_native_text,
                    "copy_locale": copy_plan.get("copy_locale"),
                    "copy_source": copy_plan.get("source"),
                    "copy_review_required": copy_review_required,
                    "claim_review_required": copy_claim_review_required,
                    "marketplace_profile_id": marketplace_profile.metadata.get("profile_id"),
                    "marketplace_profile_version": marketplace_profile.metadata.get("profile_version"),
                }
            )
        publish_checks = self._publish_checks(
            marketplace_profile=marketplace_profile,
            critic=critic,
            localization_review_required=localization_review_required,
            claim_review_required=claim_review_required,
            pending_product_facts=list(pending_product_facts.values()),
            blocked_product_fact_ids=sorted(blocked_product_fact_ids),
        )
        return EcommerceExportPackage(
            package_id=stable_id("ecommerce_export", job_key, marketplace_profile.platform, marketplace_profile.market),
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            files=files,
            naming_pattern=naming,
            dimensions={recipe.slot: dimension_hint for recipe in recipes},
            review_status="attention" if any(check["status"] == "attention" for check in publish_checks) else "metadata_ready",
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
                "evidence_intent_ids": {
                    recipe.slot: recipe.metadata.get("evidence_intent_id")
                    for recipe in recipes
                    if recipe.metadata.get("evidence_intent_id")
                },
                "platform_compliance_intent_ids": {
                    recipe.slot: recipe.metadata.get("platform_compliance_intent_id")
                    for recipe in recipes
                    if recipe.metadata.get("platform_compliance_intent_id")
                },
                "creative_strategy_ids": {
                    recipe.slot: recipe.metadata.get("creative_strategy_id")
                    for recipe in recipes
                    if recipe.metadata.get("creative_strategy_id")
                },
                "product_fact_ledger_versions": list(
                    dict.fromkeys(
                        str(recipe.metadata.get("product_fact_ledger_version"))
                        for recipe in recipes
                        if recipe.metadata.get("product_fact_ledger_version")
                    )
                ),
                "product_fact_bindings": {
                    recipe.slot: list(recipe.metadata.get("product_fact_bindings") or [])
                    for recipe in recipes
                    if recipe.metadata.get("product_fact_bindings")
                },
                "pending_product_facts": list(pending_product_facts.values()),
                "blocked_product_fact_ids": sorted(blocked_product_fact_ids),
                "publish_checks": publish_checks,
                "publish_summary": self._publish_summary(files, publish_checks),
            },
        )

    def _publish_checks(
        self,
        *,
        marketplace_profile: MarketplaceRuleProfile,
        critic: CommerceCriticReport | None,
        localization_review_required: bool,
        claim_review_required: bool,
        pending_product_facts: list[dict],
        blocked_product_fact_ids: list[str],
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
                    "message": "Have a native-language reviewer confirm the overlay copy before rendering or export.",
                }
            )
        if claim_review_required:
            checks.append(
                {
                    "id": "claim_evidence",
                    "status": "attention",
                    "message": "Verify evidence and platform eligibility for overlay claims before publishing.",
                }
            )
        if pending_product_facts:
            checks.append(
                {
                    "id": "product_fact_confirmation",
                    "status": "attention",
                    "message": "Confirm supplier or user facts not visible in the product reference before publishing: "
                    + ", ".join(str(fact.get("label") or fact.get("value") or "fact") for fact in pending_product_facts),
                }
            )
        if blocked_product_fact_ids:
            checks.append(
                {
                    "id": "blocked_product_facts",
                    "status": "attention",
                    "message": "Blocked product facts were withheld from planned prompts and copy; review the source before adding them manually.",
                }
            )
        if critic:
            for check in critic.checks:
                if check["status"] == "attention" and check["id"] in {
                    "category_evidence_coverage",
                    "suite_differentiation",
                    "blocked_product_fact_leakage",
                }:
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
