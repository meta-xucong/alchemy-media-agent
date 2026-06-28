"""Placeholder Scenario Packs for future V3 specialization stages."""

from __future__ import annotations

from .base import ScenarioPack
from .contracts import ScenarioPackManifest, ScenarioPackStatus


class EcommerceScenarioPackPlaceholder(ScenarioPack):
    manifest = ScenarioPackManifest(
        scenario_id="ecommerce",
        display_name="E-Commerce",
        category="specialized",
        status=ScenarioPackStatus.PLACEHOLDER,
        description="Future product-image and listing-set specialist. Not active in the current foundation stage.",
        default_mode_id="coming_soon",
        supported_mode_ids=["coming_soon"],
        route_hint="/creative-agent-v3/ecommerce",
        ui_card={
            "label": "E-Commerce",
            "state": "coming_soon",
            "primary_action": "show_placeholder",
        },
        metadata={"future_spec": "docs/26_ECOMMERCE_SCENARIO_PACK_AND_COMMERCE_CAPABILITY_SPEC.md"},
    )


class NewMediaScenarioPack(ScenarioPack):
    manifest = ScenarioPackManifest(
        scenario_id="new_media",
        display_name="New Media",
        category="specialized",
        status=ScenarioPackStatus.PLACEHOLDER,
        description="Future short-form and social content specialist. Not active in the current foundation stage.",
        default_mode_id="coming_soon",
        supported_mode_ids=["coming_soon"],
        route_hint="/creative-agent-v3/new-media",
        ui_card={
            "label": "New Media",
            "state": "coming_soon",
            "primary_action": "show_placeholder",
        },
    )


class PrivateDomainScenarioPack(ScenarioPack):
    manifest = ScenarioPackManifest(
        scenario_id="private_domain",
        display_name="Private Domain",
        category="specialized",
        status=ScenarioPackStatus.PLACEHOLDER,
        description="Future private-community and CRM visual specialist. Not active in the current foundation stage.",
        default_mode_id="coming_soon",
        supported_mode_ids=["coming_soon"],
        route_hint="/creative-agent-v3/private-domain",
        ui_card={
            "label": "Private Domain",
            "state": "coming_soon",
            "primary_action": "show_placeholder",
        },
    )


class BrandIPScenarioPack(ScenarioPack):
    manifest = ScenarioPackManifest(
        scenario_id="brand_ip",
        display_name="Brand IP",
        category="specialized",
        status=ScenarioPackStatus.PLACEHOLDER,
        description="Future brand-IP and character consistency specialist. Not active in the current foundation stage.",
        default_mode_id="coming_soon",
        supported_mode_ids=["coming_soon"],
        route_hint="/creative-agent-v3/brand-ip",
        ui_card={
            "label": "Brand IP",
            "state": "coming_soon",
            "primary_action": "show_placeholder",
        },
    )
