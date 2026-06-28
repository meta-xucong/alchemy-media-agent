"""E-Commerce Scenario Pack implementation."""

from __future__ import annotations

from typing import Any

from ..base import ScenarioPack
from .commerce_brief import CommerceBriefBuilder
from .commerce_critic import CommerceCritic
from .contracts import EcommercePackOutput
from .export_packager import EcommerceExportPackager
from .manifest import ECOMMERCE_MANIFEST
from .marketplace_rules import MarketplaceRuleEngine
from .product_truth import ProductTruthLockBuilder
from .selling_point_planner import SellingPointToImagePlanner


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
                "uses_v3_core": True,
                "imports_v1_v2_runtime": False,
            },
        )
