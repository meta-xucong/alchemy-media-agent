"""Trusted template capability policies for Project and direct API paths."""

from __future__ import annotations

from .contracts import TemplateCapabilityBinding, TemplateCapabilityPolicy


UNIVERSAL_REQUIRED = [
    TemplateCapabilityBinding(capability_id="visual_grammar", profile="balanced"),
    TemplateCapabilityBinding(capability_id="universal_visual_quality", profile="balanced"),
    TemplateCapabilityBinding(capability_id="commercial_quality", profile="balanced"),
]


def general_capability_policy() -> TemplateCapabilityPolicy:
    return TemplateCapabilityPolicy(
        policy_id="general_template_capabilities",
        required_capabilities=UNIVERSAL_REQUIRED,
        recommended_capabilities=[
            TemplateCapabilityBinding(capability_id="reference_channel_policy"),
            TemplateCapabilityBinding(capability_id="suite_direction"),
        ],
        optional_capabilities=[
            TemplateCapabilityBinding(capability_id="human_realism"),
            TemplateCapabilityBinding(capability_id="portrait_identity"),
            TemplateCapabilityBinding(capability_id="product_identity"),
            TemplateCapabilityBinding(capability_id="scene_continuity"),
            TemplateCapabilityBinding(capability_id="typography_layout"),
        ],
        deliverable_role_owner="general_template",
        review_threshold_profile="balanced",
    )


def ecommerce_capability_policy() -> TemplateCapabilityPolicy:
    return TemplateCapabilityPolicy(
        policy_id="ecommerce_template_capabilities",
        required_capabilities=[
            TemplateCapabilityBinding(capability_id="visual_grammar", profile="balanced"),
            TemplateCapabilityBinding(capability_id="universal_visual_quality", profile="strict"),
            TemplateCapabilityBinding(capability_id="commercial_quality", profile="commercial_strict"),
        ],
        recommended_capabilities=[
            TemplateCapabilityBinding(capability_id="product_identity", profile="described_concept"),
            TemplateCapabilityBinding(capability_id="reference_channel_policy"),
            TemplateCapabilityBinding(capability_id="suite_direction"),
        ],
        optional_capabilities=[
            TemplateCapabilityBinding(capability_id="human_realism"),
            TemplateCapabilityBinding(capability_id="portrait_identity"),
            TemplateCapabilityBinding(capability_id="scene_continuity"),
            TemplateCapabilityBinding(capability_id="typography_layout"),
        ],
        deliverable_role_owner="ecommerce_scenario_pack",
        review_threshold_profile="commercial_strict",
    )


def compatibility_policy(template_id: str | None, scenario_id: str | None) -> TemplateCapabilityPolicy:
    if template_id == "ecommerce_template" or scenario_id == "ecommerce":
        return ecommerce_capability_policy()
    return general_capability_policy()
