"""E-Commerce Scenario Pack implementation."""

from __future__ import annotations

from typing import Any

from ..base import ScenarioPack
from .commerce_brief import CommerceBriefBuilder
from .commerce_critic import CommerceCritic
from .category_profiles import resolve_category
from .contracts import EcommercePackOutput
from .export_packager import EcommerceExportPackager
from .manifest import ECOMMERCE_MANIFEST
from .marketplace_rules import MarketplaceRuleEngine
from .product_truth import ProductTruthLockBuilder
from .selling_point_planner import SellingPointToImagePlanner


ECOMMERCE_MAX_REQUESTED_IMAGES = 4
LIFESTYLE_SLOT_HINTS = {"scenario_image", "ad_cover", "benefit_hook", "store_banner", "collection_cover"}


class EcommerceScenarioPack(ScenarioPack):
    """Active V3 Scenario Pack for e-commerce image-set planning."""

    manifest = ECOMMERCE_MANIFEST


class EcommerceScenarioPackPlanner:
    """Compose deterministic commerce modules into one product-language output."""

    def __init__(
        self,
        product_truth_builder: ProductTruthLockBuilder | None = None,
        marketplace_rule_engine: MarketplaceRuleEngine | None = None,
        brief_builder: CommerceBriefBuilder | None = None,
        image_planner: SellingPointToImagePlanner | None = None,
        critic: CommerceCritic | None = None,
        export_packager: EcommerceExportPackager | None = None,
    ) -> None:
        self.product_truth_builder = product_truth_builder or ProductTruthLockBuilder()
        self.marketplace_rule_engine = marketplace_rule_engine or MarketplaceRuleEngine()
        self.brief_builder = brief_builder or CommerceBriefBuilder()
        self.image_planner = image_planner or SellingPointToImagePlanner()
        self.critic = critic or CommerceCritic()
        self.export_packager = export_packager or EcommerceExportPackager()

    def plan(
        self,
        *,
        user_input: str,
        product_profile: dict[str, Any],
        uploaded_asset_ids: list[str],
        scenario_parameters: dict[str, Any],
        platform_profile: str | None,
        job_key: str,
    ) -> EcommercePackOutput:
        marketplace_profile = self.marketplace_rule_engine.profile(
            platform_profile=platform_profile,
            parameters=scenario_parameters,
            product_profile=product_profile,
        )
        category_profile = resolve_category(product_profile.get("product_category"), user_input=user_input)
        requested_count = _bounded_requested_count(scenario_parameters.get("requested_image_count"))
        selected_slots = _selected_slots(
            marketplace_profile.image_slots,
            scenario_parameters=scenario_parameters,
            user_input=user_input,
            requested_count=requested_count,
            category_priority=category_profile.default_slot_priority if category_profile else (),
        )
        marketplace_profile = marketplace_profile.model_copy(
            update={
                "image_slots": selected_slots,
                "metadata": {
                    **marketplace_profile.metadata,
                    "requested_image_count": requested_count,
                    "slot_count_unified_with_requested_count": bool(requested_count),
                    "default_image_slot_count": len(marketplace_profile.image_slots),
                    "selected_image_slots": selected_slots,
                    **(category_profile.metadata() if category_profile else {"category_id": "generic_product"}),
                },
            }
        )
        truth = self.product_truth_builder.build(
            user_input=user_input,
            product_profile=product_profile,
            uploaded_asset_ids=uploaded_asset_ids,
            parameters=scenario_parameters,
        )
        brief = self.brief_builder.build(
            user_input=user_input,
            product_profile=product_profile,
            parameters=scenario_parameters,
            product_truth=truth,
            marketplace_profile=marketplace_profile,
        )
        recipes = self.image_planner.plan(
            truth=truth,
            brief=brief,
            marketplace_profile=marketplace_profile,
            uploaded_asset_ids=uploaded_asset_ids,
            category_profile=category_profile,
            scenario_parameters=scenario_parameters,
        )
        critic = self.critic.review(
            truth=truth,
            brief=brief,
            marketplace_profile=marketplace_profile,
            recipes=recipes,
        )
        export_package = self.export_packager.package(
            job_key=job_key,
            marketplace_profile=marketplace_profile,
            recipes=recipes,
            critic=critic,
        )
        warnings = list(dict.fromkeys([*truth.warnings, *marketplace_profile.warnings, *brief.claim_risk_warnings, *critic.warnings]))
        return EcommercePackOutput(
            product_truth=truth,
            commerce_brief=brief,
            marketplace_profile=marketplace_profile,
            recipes=recipes,
            critic=critic,
            export_package=export_package,
            warnings=warnings,
            metadata={
                "source": "EcommerceScenarioPackPlanner",
                "scenario_id": "ecommerce",
                "mode": scenario_parameters.get("mode") or "one_click_product_set",
                "recipe_count": len(recipes),
                "requested_image_count": requested_count,
                "selected_image_slots": selected_slots,
                "category_id": category_profile.category_id if category_profile else "generic_product",
                "marketplace_profile_id": marketplace_profile.metadata.get("profile_id"),
                "marketplace_profile_version": marketplace_profile.metadata.get("profile_version"),
                "uses_v3_core": True,
                "imports_v1_v2_runtime": False,
            },
        )


def _bounded_requested_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(1, min(ECOMMERCE_MAX_REQUESTED_IMAGES, int(value)))
    except (TypeError, ValueError):
        return None


def _selected_slots(
    default_slots: list[str],
    *,
    scenario_parameters: dict[str, Any],
    user_input: str,
    requested_count: int | None,
    category_priority: tuple[str, ...] = (),
) -> list[str]:
    explicit = _clean_slot_list(scenario_parameters.get("suite_slot_request"))
    default_order = [slot for slot in default_slots if slot]
    if requested_count is None and not explicit:
        return default_order
    if requested_count is None and explicit:
        return [slot for slot in explicit if slot in default_order] or default_order
    priority = _slot_priority(default_order, user_input=user_input, scenario_parameters=scenario_parameters)
    if category_priority:
        priority = [slot for slot in category_priority if slot in default_order] + [slot for slot in priority if slot not in category_priority]
    selected: list[str] = []
    for slot in explicit:
        if slot in default_order and slot not in selected:
            selected.append(slot)
    for slot in priority:
        if slot not in selected:
            selected.append(slot)
    if requested_count:
        selected = selected[:requested_count]
    return selected or default_order


def _clean_slot_list(value: object) -> list[str]:
    if isinstance(value, str):
        raw_values = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        raw_values = [str(part).strip() for part in value]
    else:
        raw_values = []
    return [item for item in raw_values if item]


def _slot_priority(
    default_slots: list[str],
    *,
    user_input: str,
    scenario_parameters: dict[str, Any],
) -> list[str]:
    text = " ".join(
        [
            str(user_input or ""),
            str(scenario_parameters.get("scene") or ""),
            str(scenario_parameters.get("style") or ""),
            str(scenario_parameters.get("mode") or ""),
        ]
    ).lower()
    wants_lifestyle = any(
        token in text
        for token in [
            "lifestyle",
            "in use",
            "real scene",
            "outdoor",
            "home",
            "travel",
            "office",
            "kitchen",
            "浴室",
            "户外",
            "生活",
            "场景",
            "真实",
        ]
    )
    if wants_lifestyle:
        preferred = [
            "main_image",
            "scenario_image",
            "ad_cover",
            "benefit_hook",
            "detail_image",
            "feature_image_1",
            "trust_image",
            "size_spec_image",
            "store_banner",
            "collection_cover",
        ]
    else:
        preferred = [
            "main_image",
            "hero_image",
            "feature_image_1",
            "scenario_image",
            "detail_image",
            "feature_image_2",
            "benefit_image",
            "size_spec_image",
            "trust_image",
            "ad_cover",
            "store_banner",
            "collection_cover",
        ]
    ordered = [slot for slot in preferred if slot in default_slots]
    ordered.extend(slot for slot in default_slots if slot not in ordered)
    return ordered
