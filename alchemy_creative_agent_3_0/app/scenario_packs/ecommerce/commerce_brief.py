"""Seller-fact aggregation for E-Commerce Brain context.

This module intentionally does not add category personas, buyer motivations,
default selling points, keyword interpretations, or visual strategies.
"""

from __future__ import annotations

from typing import Any

from .contracts import CommerceIntelligenceBrief, MarketplaceRuleProfile, ProductTruthLock
from .utils import as_list, clean_text, parameter_value, unique_preserve_order


class CommerceBriefBuilder:
    """Preserve supplied commercial facts without creating an image recipe."""

    def build(
        self,
        *,
        user_input: str,
        product_profile: dict[str, Any],
        parameters: dict[str, Any],
        product_truth: ProductTruthLock,
        marketplace_profile: MarketplaceRuleProfile,
    ) -> CommerceIntelligenceBrief:
        claims = as_list(product_profile.get("claims"))
        facts = [
            item
            for item in product_truth.visible_attributes
            if item and "uploaded product/reference image" not in item.lower()
        ]
        return CommerceIntelligenceBrief(
            target_audience=self._values(parameters, product_profile, "target_audience", "audience"),
            buying_motivations=self._values(parameters, product_profile, "buying_motivations", "motivations"),
            pain_points=self._values(parameters, product_profile, "pain_points"),
            trust_drivers=self._values(parameters, product_profile, "trust_drivers", "proof_points"),
            keyword_intent_map=[{"keyword": item, "intent": "seller_supplied"} for item in self._values(parameters, product_profile, "keywords", "keyword_roots", "search_terms")],
            competitor_patterns=self._values(parameters, product_profile, "competitor_references", "competitor_patterns", "listing_references", "style_references"),
            differentiated_selling_points=unique_preserve_order([
                *self._values(parameters, product_profile, "selling_points", "benefits", "features"),
                *facts,
            ])[:12],
            visual_strategy=[],
            claim_risk_warnings=[
                warning
                for warning in product_truth.warnings
                if "claim" in warning.lower() or "evidence" in warning.lower()
            ],
            metadata={
                "source": "CommerceBriefBuilder",
                "platform": marketplace_profile.platform,
                "market": marketplace_profile.market,
                "external_research_used": False,
                "user_input_digest": clean_text(user_input)[:180],
                "default_persona_or_selling_point_added": False,
                "claims_supplied": claims,
            },
        )

    def _values(self, parameters: dict[str, Any], profile: dict[str, Any], *fields: str) -> list[str]:
        values: list[str] = []
        for field in fields:
            values.extend(as_list(parameter_value(parameters, profile, field)))
        return unique_preserve_order(values)[:20]
