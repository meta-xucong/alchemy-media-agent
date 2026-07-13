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
            TemplateCapabilityBinding(capability_id="nonhuman_subject_identity"),
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
        ],
        optional_capabilities=[
            TemplateCapabilityBinding(capability_id="human_realism"),
            TemplateCapabilityBinding(capability_id="portrait_identity"),
            TemplateCapabilityBinding(capability_id="nonhuman_subject_identity"),
            TemplateCapabilityBinding(capability_id="scene_continuity"),
            TemplateCapabilityBinding(capability_id="typography_layout"),
        ],
        # The template owns the auditable output binding.  The remote Brain
        # remains the sole owner of each natural-language image intention.
        deliverable_role_owner="ecommerce_template",
        review_threshold_profile="commercial_strict",
        requires_remote_creative_brain=True,
        metadata={"creative_direction_owner": "remote_v3_llm_brain"},
    )


def photography_capability_policy() -> TemplateCapabilityPolicy:
    """Photography freezes delivery contracts; the remote Brain owns direction."""

    return TemplateCapabilityPolicy(
        policy_id="photographer_template_capabilities",
        required_capabilities=[
            TemplateCapabilityBinding(capability_id="visual_grammar", profile="balanced"),
            TemplateCapabilityBinding(capability_id="universal_visual_quality", profile="strict"),
            TemplateCapabilityBinding(capability_id="commercial_quality", profile="commercial_strict"),
            TemplateCapabilityBinding(capability_id="photography_direction", profile="frozen_plan"),
        ],
        recommended_capabilities=[TemplateCapabilityBinding(capability_id="reference_channel_policy")],
        optional_capabilities=[
            TemplateCapabilityBinding(capability_id="human_realism"),
            TemplateCapabilityBinding(capability_id="portrait_identity"),
            TemplateCapabilityBinding(capability_id="nonhuman_subject_identity"),
            TemplateCapabilityBinding(capability_id="scene_continuity"),
        ],
        deliverable_role_owner="photography_scenario_pack",
        review_threshold_profile="commercial_strict",
        # A Photography role is an auditable delivery binding, not a local
        # camera/lighting/pose recipe.  Its natural-language image intention
        # must therefore come from the remote Central Brain just as it does
        # for the LLM-native E-Commerce path.
        requires_remote_creative_brain=True,
        metadata={
            "specialized_direction_capability": "photography_direction",
            "creative_direction_owner": "remote_v3_llm_brain",
        },
    )


def compatibility_policy(template_id: str | None, scenario_id: str | None) -> TemplateCapabilityPolicy:
    if template_id == "ecommerce_template" or scenario_id == "ecommerce":
        return ecommerce_capability_policy()
    if template_id == "photographer_template" or scenario_id == "photography":
        return photography_capability_policy()
    return general_capability_policy()
