"""Commerce brief synthesis for visual planning."""

from __future__ import annotations

from typing import Any

from .contracts import CommerceIntelligenceBrief, MarketplaceRuleProfile, ProductTruthLock
from .utils import as_list, clean_text, parameter_value, unique_preserve_order


CATEGORY_DEFAULTS = {
    "desk_lamp": {
        "audience": ["home office users", "students", "gift buyers"],
        "motivations": ["better task lighting", "desk organization", "eye-comfort perception", "room style upgrade"],
        "pain": ["glare", "small workspace", "cheap-looking materials", "unclear size"],
        "trust": ["material close-up", "stable base", "control details", "scale context"],
    },
    "headphones": {
        "audience": ["commuters", "office users", "fitness users", "students"],
        "motivations": ["noise reduction", "comfort", "battery confidence", "portable style"],
        "pain": ["uncomfortable fit", "short battery life", "unclear compatibility", "weak build quality"],
        "trust": ["fit detail", "case detail", "battery or feature callout", "lifestyle proof"],
    },
    "skincare": {
        "audience": ["beauty shoppers", "gift buyers", "routine upgraders"],
        "motivations": ["premium routine", "ingredient confidence", "skin-feel promise", "gift value"],
        "pain": ["unclear ingredient proof", "messy texture", "cheap packaging", "overclaimed results"],
        "trust": ["texture macro", "package clarity", "ingredient-safe wording", "premium lighting"],
    },
    "generic_product": {
        "audience": ["comparison shoppers", "gift buyers", "repeat category buyers"],
        "motivations": ["clear value", "quality confidence", "ease of use", "visual appeal"],
        "pain": ["unclear size", "unclear material", "weak feature proof", "low trust"],
        "trust": ["detail close-up", "scale cue", "feature proof", "package or warranty-safe trust cue"],
    },
}


class CommerceBriefBuilder:
    """Turn seller inputs into a conversion-oriented visual brief."""

    def build(
        self,
        *,
        user_input: str,
        product_profile: dict[str, Any],
        parameters: dict[str, Any],
        product_truth: ProductTruthLock,
        marketplace_profile: MarketplaceRuleProfile,
    ) -> CommerceIntelligenceBrief:
        defaults = CATEGORY_DEFAULTS.get(product_truth.product_category, CATEGORY_DEFAULTS["generic_product"])
        keywords = self._keywords(product_profile, parameters)
        selling_points = self._selling_points(product_profile, product_truth, keywords)
        claim_warnings = [
            warning
            for warning in product_truth.warnings
            if "claim" in warning.lower() or "evidence" in warning.lower()
        ]
        competitor_patterns = self._competitor_patterns(product_profile, parameters)
        visual_strategy = [
            f"Use {marketplace_profile.platform} slot sequence so every image has one clear business job.",
            "Start with product clarity, then prove benefits, then show use context and trust.",
            "Convert copywriting ideas into short overlay labels, not long listing copy.",
        ]
        if competitor_patterns:
            visual_strategy.append("Borrow reusable visual grammar from references without copying content or claims.")

        return CommerceIntelligenceBrief(
            target_audience=unique_preserve_order([*as_list(parameter_value(parameters, product_profile, "target_audience", "audience")), *defaults["audience"]])[:8],
            buying_motivations=unique_preserve_order([*as_list(parameter_value(parameters, product_profile, "buying_motivations", "motivations")), *defaults["motivations"]])[:10],
            pain_points=unique_preserve_order([*as_list(parameter_value(parameters, product_profile, "pain_points")), *defaults["pain"]])[:10],
            trust_drivers=unique_preserve_order([*as_list(parameter_value(parameters, product_profile, "trust_drivers", "proof_points")), *defaults["trust"]])[:10],
            keyword_intent_map=self._keyword_intent_map(keywords),
            competitor_patterns=competitor_patterns,
            differentiated_selling_points=selling_points,
            visual_strategy=visual_strategy,
            claim_risk_warnings=claim_warnings,
            metadata={
                "source": "CommerceBriefBuilder",
                "platform": marketplace_profile.platform,
                "market": marketplace_profile.market,
                "external_research_used": False,
                "user_input_digest": clean_text(user_input)[:180],
            },
        )

    def _keywords(self, profile: dict[str, Any], parameters: dict[str, Any]) -> list[str]:
        values: list[str] = []
        for field in ["keywords", "keyword_roots", "search_terms", "root_words"]:
            values.extend(as_list(parameter_value(parameters, profile, field)))
        return unique_preserve_order(values)[:30]

    def _keyword_intent_map(self, keywords: list[str]) -> list[dict[str, str]]:
        mapped: list[dict[str, str]] = []
        for keyword in keywords[:20]:
            lower = keyword.lower()
            if any(token in lower for token in ["for ", "gift", "home", "office", "travel"]):
                intent = "usage scene"
            elif any(token in lower for token in ["waterproof", "fast", "wireless", "portable", "large", "small"]):
                intent = "feature requirement"
            elif any(token in lower for token in ["best", "premium", "cheap", "luxury"]):
                intent = "value perception"
            else:
                intent = "category search"
            mapped.append({"keyword": keyword, "intent": intent})
        return mapped

    def _selling_points(
        self,
        profile: dict[str, Any],
        truth: ProductTruthLock,
        keywords: list[str],
    ) -> list[str]:
        explicit = as_list(profile.get("selling_points") or profile.get("benefits") or profile.get("features"))
        facts = [
            item
            for item in truth.visible_attributes
            if (":" in item or len(item.split()) <= 8)
            and "uploaded product/reference image" not in item.lower()
        ]
        keyword_points = [f"Matches shopper intent: {keyword}" for keyword in keywords[:4]]
        defaults = [
            "Clear product identity",
            "Visible material and detail proof",
            "Realistic usage scene",
            "Scale or compatibility clarity",
            "Trust cue without unsupported claims",
        ]
        return unique_preserve_order([*explicit, *facts, *keyword_points, *defaults])[:8]

    def _competitor_patterns(self, profile: dict[str, Any], parameters: dict[str, Any]) -> list[str]:
        raw = []
        for field in ["competitor_references", "competitor_patterns", "listing_references", "style_references"]:
            raw.extend(as_list(parameter_value(parameters, profile, field)))
        if raw:
            return unique_preserve_order(raw)[:8]
        if as_list(parameter_value(parameters, profile, "competitor_asset_ids", "style_asset_ids")):
            return ["Uploaded reference assets should guide reusable layout, palette, or scene grammar."]
        return []
