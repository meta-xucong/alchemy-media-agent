"""Metadata critic for e-commerce image set plans."""

from __future__ import annotations

from .contracts import CommerceCriticReport, CommerceIntelligenceBrief, EcommerceAssetRecipe, MarketplaceRuleProfile, ProductTruthLock


class CommerceCritic:
    """Review recipes for product correctness, clarity, trust, and platform fit."""

    def review(
        self,
        *,
        truth: ProductTruthLock,
        brief: CommerceIntelligenceBrief,
        marketplace_profile: MarketplaceRuleProfile,
        recipes: list[EcommerceAssetRecipe],
    ) -> CommerceCriticReport:
        checks: list[dict] = []
        warnings: list[str] = []
        checks.append(self._check("product_truth", bool(truth.immutable_attributes), "Product truth facts are available."))
        checks.append(self._check("slot_coverage", len(recipes) >= 5, f"{len(recipes)} image slot(s) planned."))
        checks.append(
            self._check(
                "selling_point_mapping",
                all(recipe.selling_point for recipe in recipes),
                "Every planned image has one primary selling point.",
            )
        )
        checks.append(
            self._check(
                "platform_profile",
                bool(marketplace_profile.image_slots and marketplace_profile.canvas_rules),
                f"Marketplace profile is available for {marketplace_profile.platform}.",
            )
        )
        checks.append(
            self._check(
                "claim_risk",
                not brief.claim_risk_warnings,
                "Unsupported claims require softer copy or evidence before export.",
            )
        )
        if truth.warnings:
            warnings.extend(truth.warnings)
        if marketplace_profile.warnings:
            warnings.extend(marketplace_profile.warnings)
        if brief.claim_risk_warnings:
            warnings.extend(brief.claim_risk_warnings)

        status = "attention" if any(check["status"] == "attention" for check in checks) else "ready"
        return CommerceCriticReport(
            status=status,
            checks=checks,
            warnings=list(dict.fromkeys(warnings)),
            metadata={
                "source": "CommerceCritic",
                "metadata_only_review": True,
                "recipe_count": len(recipes),
            },
        )

    def _check(self, check_id: str, passed: bool, detail: str) -> dict:
        return {
            "id": check_id,
            "label": check_id.replace("_", " ").title(),
            "status": "done" if passed else "attention",
            "detail": detail,
        }
