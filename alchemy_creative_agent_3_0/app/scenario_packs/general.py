"""General Creative active Scenario Pack."""

from __future__ import annotations

from .base import ScenarioPack
from .contracts import ScenarioPackManifest, ScenarioPackStatus


class GeneralCreativeScenarioPack(ScenarioPack):
    """Default active Scenario Pack for the current V3 product stage."""

    manifest = ScenarioPackManifest(
        scenario_id="general_creative",
        display_name="General Creative",
        category="general",
        status=ScenarioPackStatus.ACTIVE,
        description="Natural-language commercial visual creation for general business and brand scenarios.",
        default_mode_id="freeform",
        supported_mode_ids=[
            "freeform",
            "campaign_poster",
            "social_cover",
            "brand_visual",
            "product_style_hero",
        ],
        preset_ids=[
            "blank",
            "campaign_poster",
            "social_cover",
            "brand_key_visual",
            "product_style_hero",
        ],
        enabled_capabilities=[
            "central_creative_brain",
            "brand_memory",
            "generation_loop",
            "asset_packaging",
        ],
        route_hint="/creative-agent-v3/general",
        ui_card={
            "label": "General Creative",
            "state": "available",
            "primary_action": "create_job",
        },
        metadata={
            "current_stage": "v3_foundation",
            "policy_boundary": "general_only_no_marketplace_rules",
        },
    )
