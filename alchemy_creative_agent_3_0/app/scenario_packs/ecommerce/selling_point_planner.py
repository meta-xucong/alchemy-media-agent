"""Convert commerce strategy into an e-commerce image set recipe."""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief, EcommerceAssetRecipe, MarketplaceRuleProfile, ProductTruthLock
from .category_profiles import CategoryProfile, evidence_for_slot, slot_guidance_for
from .copy_bridge import EcommerceCopyBridge
from .localization import resolve_localization
from .marketplace_rules import (
    creative_strategy_for_slot,
    evidence_intent_for_slot,
    platform_compliance_intent_for_slot,
    resolve_creative_strategy,
)


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
        creative_strategy = resolve_creative_strategy(scenario_parameters.get("creative_strategy"))
        brief_metadata = dict(brief.metadata or {})
        price_positioning = str(brief_metadata.get("price_positioning") or "").strip()
        price_positioning_label = str(brief_metadata.get("price_positioning_label") or "").strip()
        price_positioning_direction = str(brief_metadata.get("price_positioning_direction") or "").strip()
        price_positioning_metadata = {
            "price_positioning": price_positioning,
            "price_positioning_label": price_positioning_label,
        } if price_positioning else {}
        localization = resolve_localization(
            platform=marketplace_profile.platform,
            market=marketplace_profile.market,
            requested_locale=scenario_parameters.get("copy_locale") or scenario_parameters.get("locale"),
        )
        text_forbidden_slots = set(
            (marketplace_profile.metadata.get("text_policy") or {}).get("text_forbidden_slots") or []
        )
        unverified_visual_facts = [
            str(fact)
            for fact in truth.metadata.get("unverified_visual_facts") or []
            if str(fact).strip()
        ]
        blocked_fact_values = [
            str(fact)
            for fact in truth.metadata.get("blocked_fact_values") or []
            if str(fact).strip()
        ]
        selling_points = [
            point
            for point in (brief.differentiated_selling_points or ["Clear product identity"])
            if not any(blocked.lower() in point.lower() for blocked in blocked_fact_values)
        ] or ["Clear product identity"]
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
                blocked_fact_values=blocked_fact_values,
            )
            provider_native_text = copy_plan["text"]
            fact_bindings = self._fact_bindings_for_slot(truth, slot)
            evidence_intent = evidence_intent_for_slot(slot)
            category_slot_guidance = slot_guidance_for(
                category_profile,
                slot,
                product_category=truth.product_category,
            )
            platform_compliance_intent = platform_compliance_intent_for_slot(
                marketplace_profile.platform,
                marketplace_profile.market,
                slot,
            )
            creative_intent = creative_strategy_for_slot(creative_strategy, slot)
            visual_scene, lifestyle_metadata = self._visual_scene(
                slot=slot,
                default_scene=scene,
                truth=truth,
                brief=brief,
                marketplace_profile=marketplace_profile,
            )
            visual_scene = f"{visual_scene} {evidence_intent['direction']}"
            if category_slot_guidance["direction"]:
                visual_scene = f"{visual_scene} {category_slot_guidance['direction']}"
            if platform_compliance_intent["direction"]:
                visual_scene = f"{visual_scene} {platform_compliance_intent['direction']}"
            if creative_intent["direction"]:
                visual_scene = f"{visual_scene} {creative_intent['direction']}"
            if price_positioning_direction:
                visual_scene = f"{visual_scene} {price_positioning_direction}"
            recipes.append(
                EcommerceAssetRecipe(
                    slot=slot,
                    business_goal=goal,
                    selling_point=selling_point,
                    buyer_intent=buyer_intent,
                    required_product_facts=fact_bindings["required_product_facts"],
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
                        "category_slot_guidance_id": category_slot_guidance["id"],
                        "category_slot_guidance": category_slot_guidance["direction"],
                        "unverified_visual_facts": unverified_visual_facts,
                        "product_fact_ledger_version": truth.metadata.get("fact_ledger_version"),
                        "product_fact_bindings": fact_bindings["records"],
                        "pending_product_fact_ids": fact_bindings["pending_ids"],
                        "blocked_product_fact_ids": list(truth.metadata.get("blocked_fact_ids") or []),
                        "copy_plan": copy_plan,
                        "evidence_intent_id": evidence_intent["id"],
                        "evidence_intent_direction": evidence_intent["direction"],
                        "platform_compliance_intent_id": platform_compliance_intent["id"],
                        "platform_compliance_evidence_tier": platform_compliance_intent["evidence_tier"],
                        "creative_strategy_id": creative_intent["id"],
                        "creative_strategy_direction": creative_intent["direction"],
                        "creative_strategy_applied": bool(creative_intent["direction"]),
                        **price_positioning_metadata,
                        **lifestyle_metadata,
                    },
                )
            )
        return recipes

    def _fact_bindings_for_slot(self, truth: ProductTruthLock, slot: str) -> dict[str, object]:
        records = [
            fact
            for fact in truth.fact_ledger
            if fact.verification != "blocked" and (not fact.allowed_slot_ids or slot in fact.allowed_slot_ids)
        ]
        values = [fact.value for fact in records]
        ledger_values = {fact.value.lower() for fact in truth.fact_ledger}
        generic_truth = [
            fact
            for fact in truth.immutable_attributes
            if fact.lower() not in ledger_values and fact not in values
        ]
        return {
            # A fact record determines relevance. Do not truncate this list by
            # position: losing a sourced global fact would turn the ledger back
            # into an arbitrary best-effort summary.
            "required_product_facts": list(dict.fromkeys([*values, *generic_truth])),
            "records": [fact.model_dump(mode="json") for fact in records],
            "pending_ids": [fact.fact_id for fact in records if fact.verification == "requires_confirmation"],
        }

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
