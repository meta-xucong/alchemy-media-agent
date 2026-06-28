"""Manifest for the active E-Commerce Scenario Pack."""

from __future__ import annotations

from ..contracts import ScenarioPackManifest, ScenarioPackStatus


ECOMMERCE_MANIFEST = ScenarioPackManifest(
    scenario_id="ecommerce",
    display_name="E-Commerce",
    category="specialized",
    status=ScenarioPackStatus.ACTIVE,
    description="One-click product image set planning for listing, ads, and store assets.",
    default_mode_id="one_click_product_set",
    supported_mode_ids=[
        "one_click_product_set",
        "marketplace_listing_set",
        "style_recreation_set",
        "ad_creative_set",
        "listing_visual_copy_pack",
    ],
    preset_ids=[
        "one_click_product_set",
        "marketplace_listing_set",
        "style_recreation_set",
        "ad_creative_set",
        "listing_visual_copy_pack",
    ],
    enabled_capabilities=[
        "central_creative_brain",
        "asset_role_analyzer",
        "asset_binding_planner",
        "product_truth_lock",
        "commerce_brief_builder",
        "marketplace_rule_engine",
        "selling_point_to_image_planner",
        "commerce_critic",
        "export_packager",
    ],
    route_hint="/creative-agent-v3/ecommerce",
    ui_card={
        "label": "E-Commerce",
        "state": "available",
        "primary_action": "create_job",
    },
    metadata={
        "current_stage": "v3_8_ecommerce_pack",
        "document": "docs/26_ECOMMERCE_SCENARIO_PACK_AND_COMMERCE_CAPABILITY_SPEC.md",
        "external_research_required": False,
        "v1_v2_runtime_import": False,
    },
)
