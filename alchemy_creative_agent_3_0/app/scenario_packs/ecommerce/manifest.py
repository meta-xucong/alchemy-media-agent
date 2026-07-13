"""Manifest for the active E-Commerce Scenario Pack."""

from __future__ import annotations

from ..contracts import ScenarioPackManifest, ScenarioPackStatus


ECOMMERCE_MANIFEST = ScenarioPackManifest(
    scenario_id="ecommerce",
    display_name="E-Commerce",
    category="specialized",
    status=ScenarioPackStatus.ACTIVE,
    description="LLM-directed product image sets using factual commerce context and shared V3 delivery.",
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
        "commerce_factual_context",
        "marketplace_constraint_evidence",
        "remote_v3_creative_brain",
        "shared_provider_review_retry",
    ],
    route_hint="/creative-agent-v3/ecommerce",
    ui_card={
        "label": "E-Commerce",
        "state": "available",
        "primary_action": "create_job",
    },
    metadata={
        "current_stage": "llm_native_ecommerce_correction",
        "document": "docs/ecommerce_module/E17_LLM_NATIVE_ECOMMERCE_ARCHITECTURE_CORRECTION.md",
        "external_research_required": False,
        "v1_v2_runtime_import": False,
    },
)
