"""Convert commerce strategy into an e-commerce image set recipe."""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief, EcommerceAssetRecipe, MarketplaceRuleProfile, ProductTruthLock
from .copy_bridge import EcommerceCopyBridge


SLOT_GOALS = {
    "main_image": ("click", "Clean product-first image with strong silhouette and minimal distraction."),
    "hero_image": ("click", "Premium product hero with strong thumbnail readability."),
    "feature_image_1": ("understand", "Feature-led composition with one clear benefit callout."),
    "feature_image_2": ("understand", "Second benefit or functional proof image."),
    "benefit_image": ("understand", "Benefit-led visual proof for fast marketplace scanning."),
    "benefit_hook": ("desire", "Ad-friendly benefit hook with one memorable claim-safe idea."),
    "detail_image": ("trust", "Macro or cutaway-style detail proof without inventing product internals."),
    "scenario_image": ("desire", "Realistic usage scene that keeps product identity central."),
    "size_spec_image": ("compare", "Scale, dimensions, compatibility, or package count clarification."),
    "trust_image": ("trust", "Quality, package, warranty-safe, or evidence-backed trust cue."),
    "trust_comparison_image": ("compare", "Comparison-safe difference image focused on supplied facts."),
    "ad_cover": ("remember", "Campaign cover for traffic acquisition."),
    "store_banner": ("remember", "Store asset with product family and brand feel."),
    "collection_cover": ("remember", "Collection cover with product family rhythm."),
}


class SellingPointToImagePlanner:
    """Map ranked selling points into a coherent listing-ready image sequence."""

    def __init__(self, copy_bridge: EcommerceCopyBridge | None = None) -> None:
        self.copy_bridge = copy_bridge or EcommerceCopyBridge()

    def plan(
        self,
        *,
        truth: ProductTruthLock,
        brief: CommerceIntelligenceBrief,
        marketplace_profile: MarketplaceRuleProfile,
        uploaded_asset_ids: list[str],
    ) -> list[EcommerceAssetRecipe]:
        selling_points = brief.differentiated_selling_points or ["Clear product identity"]
        recipes: list[EcommerceAssetRecipe] = []
        for index, slot in enumerate(marketplace_profile.image_slots):
            goal, scene = SLOT_GOALS.get(slot, ("support", "Product-focused commercial composition."))
            selling_point = (
                "Clear product identity"
                if slot in {"main_image", "hero_image"}
                else selling_points[min(max(index - 1, 0), len(selling_points) - 1)]
            )
            buyer_intent = self._buyer_intent(index, brief)
            overlay_text = self.copy_bridge.overlay_for_slot(slot=slot, selling_point=selling_point, brief=brief)
            visual_scene, lifestyle_metadata = self._visual_scene(
                slot=slot,
                default_scene=scene,
                truth=truth,
                brief=brief,
                marketplace_profile=marketplace_profile,
            )
            recipes.append(
                EcommerceAssetRecipe(
                    slot=slot,
                    business_goal=goal,
                    selling_point=selling_point,
                    buyer_intent=buyer_intent,
                    required_product_facts=truth.immutable_attributes[:8],
                    visual_scene=visual_scene,
                    overlay_text=overlay_text,
                    reference_bindings=self._reference_bindings(uploaded_asset_ids, slot),
                    review_checks=[
                        "product remains large and recognizable",
                        "required product facts remain correct",
                        "overlay text stays readable and does not cover key details",
                        "claims match supplied evidence",
                        "slot fits marketplace profile",
                    ],
                    metadata={
                        "sequence_index": index + 1,
                        "platform": marketplace_profile.platform,
                        "market": marketplace_profile.market,
                        **lifestyle_metadata,
                    },
                )
            )
        return recipes

    def _buyer_intent(self, index: int, brief: CommerceIntelligenceBrief) -> str:
        for pool in [brief.buying_motivations, brief.pain_points, brief.trust_drivers]:
            if pool:
                return pool[min(index, len(pool) - 1)]
        return "Understand why this product is worth choosing"

    def _reference_bindings(self, uploaded_asset_ids: list[str], slot: str) -> list[str]:
        if not uploaded_asset_ids:
            return []
        primary = uploaded_asset_ids[0]
        if slot in {"main_image", "hero_image", "detail_image", "size_spec_image"}:
            return [f"{primary}: preserve product identity"]
        return [f"{primary}: product identity anchor", *[f"{asset_id}: optional style/layout reference" for asset_id in uploaded_asset_ids[1:3]]]

    def _visual_scene(
        self,
        *,
        slot: str,
        default_scene: str,
        truth: ProductTruthLock,
        brief: CommerceIntelligenceBrief,
        marketplace_profile: MarketplaceRuleProfile,
    ) -> tuple[str, dict[str, str | bool]]:
        if slot not in {"scenario_image", "ad_cover", "benefit_hook", "store_banner", "collection_cover"}:
            return default_scene, {"lifestyle_realism_required": False}
        category = self._lifestyle_category(truth, brief)
        if category == "beauty_bathroom":
            scene = (
                "Real-world bathroom vanity or morning skincare moment with natural window light, believable countertop "
                "texture, and the real product identity kept central; avoid fake perfume props, generic luxury bottles, "
                "or over-polished studio staging."
            )
        elif category == "drink_summer":
            scene = (
                "Real outdoor or cafe summer refreshment moment with daylight, condensation, hand/table interaction, "
                "and believable lifestyle surroundings while keeping product shape, label, and color accurate."
            )
        elif category == "home_office":
            scene = (
                "Real home-office or desk-use moment with practical context, natural shadows, and believable everyday "
                "surface details while preserving product proportions and material."
            )
        elif category == "travel_outdoor":
            scene = (
                "Real travel or outdoor-use moment with environmental context, natural light, and human-scale cues while "
                "keeping the product clear and not inventing unrelated accessories."
            )
        else:
            scene = (
                "Real-life in-use scene rather than a pure studio render: believable surface, natural light, human-scale "
                "context, and everyday surroundings while preserving product identity and marketplace clarity."
            )
        return (
            f"{scene} {default_scene}",
            {
                "lifestyle_realism_required": True,
                "lifestyle_scene_category": category,
                "lifestyle_platform": marketplace_profile.platform,
            },
        )

    def _lifestyle_category(self, truth: ProductTruthLock, brief: CommerceIntelligenceBrief) -> str:
        text = " ".join(
            [
                truth.product_category,
                *truth.visible_attributes,
                *truth.immutable_attributes,
                *brief.buying_motivations,
                *brief.pain_points,
                *brief.visual_strategy,
            ]
        ).lower()
        if any(token in text for token in ["skincare", "beauty", "cream", "serum", "makeup", "cosmetic", "bathroom"]):
            return "beauty_bathroom"
        if any(token in text for token in ["drink", "beverage", "bottle", "summer", "refresh", "juice", "tea", "coffee"]):
            return "drink_summer"
        if any(token in text for token in ["desk", "office", "lamp", "computer", "chair", "keyboard"]):
            return "home_office"
        if any(token in text for token in ["travel", "outdoor", "camp", "sport", "portable", "backpack"]):
            return "travel_outdoor"
        return "generic_real_life"
