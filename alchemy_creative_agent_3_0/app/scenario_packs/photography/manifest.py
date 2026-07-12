"""Inactive manifest for the isolated Photography P1 skeleton."""

from __future__ import annotations

from ..contracts import ScenarioPackManifest, ScenarioPackStatus


PHOTOGRAPHY_MANIFEST = ScenarioPackManifest(
    scenario_id="photography",
    display_name="Photography",
    category="specialized",
    status=ScenarioPackStatus.INACTIVE,
    description="Professional photographic planning and AI reshoot module; not active in the P1 skeleton stage.",
    default_mode_id="single_hero",
    supported_mode_ids=[
        "single_hero",
        "professional_set",
        "reference_reshoot",
    ],
    preset_ids=[],
    enabled_capabilities=[],
    route_hint="/creative-agent-v3/photography",
    ui_card={
        "label": "Photography",
        "state": "inactive",
        "primary_action": "none",
    },
    metadata={
        "current_stage": "photography_p1_inactive_skeleton",
        "document_family": "docs/photography_module/P00-P04",
        "activation_ready": False,
        "registered_in_default_scenario_registry": False,
        "named_profile_selection": "user_explicit_ui_only",
        "default_profile_id": "general_photography",
        "v1_v2_runtime_import": False,
        "direct_provider_call": False,
    },
)
