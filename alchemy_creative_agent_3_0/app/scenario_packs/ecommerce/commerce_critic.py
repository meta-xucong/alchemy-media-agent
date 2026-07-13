"""Factual preflight checks for remote-Brain E-Commerce work."""

from __future__ import annotations

from .contracts import CommerceCriticReport, CommerceIntelligenceBrief, EcommerceAssetRecipe, EcommerceCreativeContext, MarketplaceRuleProfile, ProductTruthLock


class CommerceCritic:
    """Observe factual readiness; never grade or assemble a local image suite."""

    def review(
        self,
        *,
        truth: ProductTruthLock,
        brief: CommerceIntelligenceBrief,
        marketplace_profile: MarketplaceRuleProfile,
        recipes: list[EcommerceAssetRecipe],
    ) -> CommerceCriticReport:
        """Historical input compatibility with no recipe-level creative logic."""

        del recipes
        context = EcommerceCreativeContext(
            context_id="historical_ecommerce_context",
            product_truth=truth,
            platform_constraints={"platform": marketplace_profile.platform, "market": marketplace_profile.market},
            claim_risk_warnings=list(brief.claim_risk_warnings),
        )
        report = self.review_context(context=context, marketplace_profile=marketplace_profile, brief=brief)
        return report.model_copy(
            update={
                "metadata": {
                    **dict(report.metadata),
                    "historical_recipe_input_ignored": True,
                    "creative_recipe_present": False,
                }
            }
        )

    def review_context(
        self,
        *,
        context: EcommerceCreativeContext,
        marketplace_profile: MarketplaceRuleProfile,
        brief: CommerceIntelligenceBrief,
    ) -> CommerceCriticReport:
        """Check evidence before a remote Brain creates visual intent."""

        profile = dict(marketplace_profile.metadata or {})
        has_lineage = bool(
            profile.get("profile_id")
            and profile.get("profile_version")
            and profile.get("profile_status")
        )
        checks = [
            self._check(
                "product_truth",
                bool(context.product_truth.immutable_attributes),
                "Supplied product facts and reference evidence are available to the remote Brain.",
            ),
            self._check(
                "platform_constraint_lineage",
                has_lineage,
                "Platform constraints retain an identifier, version, and source status.",
            ),
            self._check(
                "approved_copy_claim_risk",
                not context.claim_risk_warnings,
                "Approved literal copy and claims have no unresolved evidence warning.",
            ),
            self._check(
                "creative_direction_owner",
                True,
                "A remote Brain, not a local slot planner, must choose the output intents.",
            ),
        ]
        warnings = [*context.warnings, *brief.claim_risk_warnings]
        return CommerceCriticReport(
            status="attention" if any(check["status"] == "attention" for check in checks) else "ready",
            checks=checks,
            warnings=list(dict.fromkeys(warnings)),
            metadata={
                "source": "CommerceCritic.review_context",
                "creative_recipe_present": False,
                "ecommerce_context_id": context.context_id,
            },
        )

    def _check(self, check_id: str, passed: bool, detail: str) -> dict:
        return {
            "id": check_id,
            "label": check_id.replace("_", " ").title(),
            "status": "done" if passed else "attention",
            "detail": detail,
        }
