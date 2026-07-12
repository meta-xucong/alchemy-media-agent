"""Convert commerce strategy into an e-commerce image set recipe."""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief, EcommerceAssetRecipe, MarketplaceRuleProfile, ProductTruthLock
from .category_profiles import CategoryProfile, evidence_for_slot
from .copy_bridge import EcommerceCopyBridge
from .localization import resolve_localization


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
        category_profile: CategoryProfile | None = None,
        scenario_parameters: dict | None = None,
    ) -> list[EcommerceAssetRecipe]:
        scenario_parameters = scenario_parameters or {}
        localization = resolve_localization(
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            requested_locale=scenario_parameters.get("copy_locale") or scenario_parameters.get("locale"),
        )
        text_forbidden_slots = set(
            (marketplace_profile.metadata.get("text_policy") or {}).get("text_forbidden_slots") or []
        )
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
            copy_plan = self.copy_bridge.plan_for_slot(
                slot=slot,
                selling_point=selling_point,
                brief=brief,
                localization=localization,
                parameters=scenario_parameters,
                unsupported_claims=list(truth.metadata.get("unsupported_claims") or []),
                text_forbidden_slots=text_forbidden_slots,
            )
            provider_native_text = copy_plan["text"]
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
                    overlay_text=None,
                    provider_native_text=provider_native_text,
                    reference_bindings=self._reference_bindings(uploaded_asset_ids, slot),
                    review_checks=[
                        "product remains large and recognizable",
                        "required product facts remain correct",
                        "provider-native text is reviewed as final pixels when explicitly requested",
                        "claims match supplied evidence",
                        "slot fits marketplace profile",
                    ],
                    metadata={
                        "sequence_index": index + 1,
                        "platform": marketplace_profile.platform,
                        "market": marketplace_profile.market,
                        **(category_profile.metadata() if category_profile else {}),
                        "category_evidence_targets": list(evidence_for_slot(category_profile, slot)),
                        "copy_plan": copy_plan,
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
        scene = (
            "Let the LLM and image provider derive a believable in-use setting from the user request, product facts, buyer intent, "
            "and requested mood. Preserve product identity, avoid unsupported claims, and do not fall back to a named category recipe."
        )
        return (
            f"{scene} {default_scene}",
            {
                "lifestyle_realism_required": True,
                "lifestyle_scene_category": "llm_directed",
                "lifestyle_platform": marketplace_profile.platform,
            },
        )
