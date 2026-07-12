"""Deployment-gated manifest for the isolated Photography module."""

from __future__ import annotations

import os

from ..contracts import ScenarioPackManifest, ScenarioPackStatus


PHOTOGRAPHY_PRODUCTION_GATE = "V3_PHOTOGRAPHY_PRODUCTION_ENABLED"


def photography_production_enabled() -> bool:
    """Return the explicit deployment gate; imports never activate Photography."""

    return os.getenv(PHOTOGRAPHY_PRODUCTION_GATE, "false").strip().lower() in {"1", "true", "yes", "on"}


def photography_manifest(*, enabled: bool | None = None) -> ScenarioPackManifest:
    """Build a fresh manifest so a process-level gate cannot mutate old jobs."""

    active = photography_production_enabled() if enabled is None else bool(enabled)
    return ScenarioPackManifest(
        scenario_id="photography",
        display_name="Photography",
        category="specialized",
        status=ScenarioPackStatus.ACTIVE if active else ScenarioPackStatus.INACTIVE,
        description=(
            "Professional photographic planning and AI reshoot through the shared V3 runtime."
            if active
            else "Professional photographic planning and AI reshoot module; deployment gate is disabled."
        ),
        # P4/P5 only certify one hero output. A session-package switch must
        # arrive with its own photographer-owned suite contract.
        default_mode_id="single_hero",
        supported_mode_ids=["single_hero", "reference_reshoot"],
        preset_ids=[],
        enabled_capabilities=["photography_direction"] if active else [],
        route_hint="/creative-agent-v3/photography",
        ui_card={
            "label": "Photography",
            "state": "active" if active else "inactive",
            "primary_action": "start_template" if active else "none",
        },
        metadata={
            "current_stage": "photography_production_activation" if active else "photography_p5_gated",
            "document_family": "docs/photography_module/P00-P07",
            "activation_ready": active,
            "registered_in_default_scenario_registry": active,
            "deployment_gate": PHOTOGRAPHY_PRODUCTION_GATE,
            "named_profile_selection": "mainline_immutable_binding_only" if active else "user_explicit_ui_only",
            "default_profile_id": "general_photography",
            "v1_v2_runtime_import": False,
            "direct_provider_call": False,
            "shared_review_retry_owner": "v3_product_runtime",
        },
    )


# Compatibility export for the inactive P1-P5 tests and documentation.
PHOTOGRAPHY_MANIFEST = photography_manifest(enabled=False)
