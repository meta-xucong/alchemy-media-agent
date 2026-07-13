"""E-Commerce factual-context preparation.

New work stops here before Central Brain.  This module is intentionally unable
to choose a suite role, product shot, scene, crop, camera, or copy phrase.
"""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from ..base import ScenarioPack
from .category_profiles import resolve_category
from .commerce_brief import CommerceBriefBuilder
from .commerce_critic import CommerceCritic
from .contracts import EcommerceCreativeContext, EcommercePackOutput
from .export_packager import EcommerceExportPackager
from .manifest import ECOMMERCE_MANIFEST
from .marketplace_rules import MarketplaceRuleEngine
from .product_truth import ProductTruthLockBuilder
from .utils import as_list, clean_text, unique_preserve_order


class EcommerceScenarioPack(ScenarioPack):
    """Active V3 Scenario Pack for an LLM-directed commerce image set."""

    manifest = ECOMMERCE_MANIFEST


class EcommerceScenarioPackPlanner:
    """Prepare factual E-Commerce context; never produce a visual recipe."""

    def __init__(
        self,
        product_truth_builder: ProductTruthLockBuilder | None = None,
        marketplace_rule_engine: MarketplaceRuleEngine | None = None,
        brief_builder: CommerceBriefBuilder | None = None,
        critic: CommerceCritic | None = None,
        export_packager: EcommerceExportPackager | None = None,
    ) -> None:
        self.product_truth_builder = product_truth_builder or ProductTruthLockBuilder()
        self.marketplace_rule_engine = marketplace_rule_engine or MarketplaceRuleEngine()
        self.brief_builder = brief_builder or CommerceBriefBuilder()
        self.critic = critic or CommerceCritic()
        self.export_packager = export_packager or EcommerceExportPackager()

    def build_creative_context(
        self,
        *,
        user_input: str,
        product_profile: dict[str, Any],
        uploaded_asset_ids: list[str],
        scenario_parameters: dict[str, Any],
        platform_profile: str | None,
        job_key: str,
    ) -> EcommerceCreativeContext:
        """Build factual input for the remote Brain without a visual answer."""

        marketplace = self.marketplace_rule_engine.profile(
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
        category = resolve_category(product_profile.get("product_category"), user_input=user_input)
        approved_copy = _explicit_approved_copy(product_profile, scenario_parameters)
        locale = (
            clean_text(scenario_parameters.get("copy_locale") or scenario_parameters.get("locale"))
            or clean_text(marketplace.metadata.get("copy_locale"))
            or None
        )
        seller_inputs = _seller_inputs(product_profile, scenario_parameters)
        category_questions = _category_evidence_questions(category)
        platform_constraints = {
            "platform": marketplace.platform,
            "market": marketplace.market,
            "content_constraints": list(marketplace.content_rules),
            "warnings": list(marketplace.warnings),
            "profile_id": marketplace.metadata.get("profile_id"),
            "profile_version": marketplace.metadata.get("profile_version"),
            "profile_status": marketplace.metadata.get("profile_status"),
            "source_notes": marketplace.metadata.get("profile_source_notes"),
            # Delivery dimensions are factual output constraints, not a scene
            # or composition choice.  The Brain still decides the image.
            "canvas_constraints": dict(marketplace.canvas_rules),
        }
        claim_warnings = [
            warning
            for warning in truth.warnings
            if "claim" in warning.lower() or "evidence" in warning.lower()
        ]
        return EcommerceCreativeContext(
            context_id=stable_id(
                "ecommerce_creative_context",
                job_key,
                marketplace.platform,
                marketplace.market,
                user_input,
                product_profile,
                uploaded_asset_ids,
                scenario_parameters,
            ),
            product_truth=truth,
            platform_constraints=platform_constraints,
            category_evidence_questions=category_questions,
            seller_inputs=seller_inputs,
            approved_literal_copy=approved_copy,
            copy_locale=locale,
            claim_risk_warnings=claim_warnings,
            warnings=unique_preserve_order([*truth.warnings, *marketplace.warnings]),
            metadata={
                "source": "EcommerceScenarioPackPlanner.build_creative_context",
                "creative_recipe_present": False,
                "category_id": category.category_id if category else "generic_product",
                "platform_profile_id": marketplace.metadata.get("profile_id"),
                "platform_profile_version": marketplace.metadata.get("profile_version"),
            },
        )

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
        """Return a read-compatible, recipe-free summary for a new job."""

        context = self.build_creative_context(
            user_input=user_input,
            product_profile=product_profile,
            uploaded_asset_ids=uploaded_asset_ids,
            scenario_parameters=scenario_parameters,
            platform_profile=platform_profile,
            job_key=job_key,
        )
        marketplace_base = self.marketplace_rule_engine.profile(
            platform_profile=platform_profile,
            parameters=scenario_parameters,
            product_profile=product_profile,
        )
        marketplace = marketplace_base.model_copy(
            update={
                "image_slots": [],
                "metadata": {
                    **marketplace_base.metadata,
                    "legacy_slot_map_retired": True,
                },
            }
        )
        brief = self.brief_builder.build(
            user_input=user_input,
            product_profile=product_profile,
            parameters=scenario_parameters,
            product_truth=context.product_truth,
            marketplace_profile=marketplace,
        )
        critic = self.critic.review_context(context=context, marketplace_profile=marketplace, brief=brief)
        export_package = self.export_packager.package_context(
            job_key=job_key,
            context=context,
            marketplace_profile=marketplace,
            critic=critic,
        )
        return EcommercePackOutput(
            product_truth=context.product_truth,
            commerce_brief=brief,
            marketplace_profile=marketplace,
            recipes=[],
            critic=critic,
            export_package=export_package,
            creative_context=context,
            warnings=unique_preserve_order([*context.warnings, *brief.claim_risk_warnings, *critic.warnings]),
            metadata={
                "source": "EcommerceScenarioPackPlanner",
                "scenario_id": "ecommerce",
                "creative_recipe_present": False,
                "remote_brain_required": True,
                "requested_image_count": _bounded_requested_count(scenario_parameters.get("requested_image_count")),
                "ecommerce_context_id": context.context_id,
                "uses_v3_core": True,
                "imports_v1_v2_runtime": False,
            },
        )


def _explicit_approved_copy(product_profile: dict[str, Any], parameters: dict[str, Any]) -> str | None:
    """Accept literal copy only from an explicit approval-shaped field."""

    for source in (parameters, product_profile):
        for field in ("approved_literal_copy", "approved_copy", "literal_copy"):
            value = source.get(field)
            if isinstance(value, str) and clean_text(value):
                return clean_text(value)
    return None


def _seller_inputs(product_profile: dict[str, Any], parameters: dict[str, Any]) -> dict[str, Any]:
    """Keep only user-provided business facts; never add category defaults."""

    fields = (
        "target_audience", "audience", "buying_motivations", "motivations",
        "pain_points", "trust_drivers", "claims", "evidence", "evidence_sources",
        "selling_points", "benefits", "keywords", "competitor_references",
        "style_references", "product_category", "category",
    )
    result: dict[str, Any] = {}
    for field in fields:
        value = parameters.get(field)
        source = "scenario_parameters"
        if value in (None, "", [], {}):
            value = product_profile.get(field)
            source = "product_profile"
        if value in (None, "", [], {}):
            continue
        result[field] = as_list(value) if isinstance(value, (list, tuple, set)) else value
        result[f"{field}_source"] = source
    return result


def _category_evidence_questions(category) -> list[str]:
    if category is None:
        return []
    values = [*category.required_evidence, *category.optional_evidence, *category.review_checks]
    return unique_preserve_order(str(item).strip() for item in values if str(item).strip())[:12]


def _bounded_requested_count(value: object) -> int | None:
    if value in (None, ""):
        return None
    try:
        return max(1, min(4, int(value)))
    except (TypeError, ValueError):
        return None
