import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities import SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    CapabilityActivationError,
    CapabilityActivationIntent,
    CapabilityActivationPlanner,
    TemplateCapabilityBinding,
    TemplateCapabilityPolicy,
    VisualCapabilityRegistry,
    VisualTaskProfile,
)


def test_missing_required_capability_blocks_instead_of_enabling_everything() -> None:
    execution = SharedCapabilityRegistry.with_default_modules()
    planner = CapabilityActivationPlanner(VisualCapabilityRegistry.with_default_manifests(execution))
    profile = VisualTaskProfile(
        profile_id="profile",
        job_id="job",
        template_id="general_template",
        scenario_id="general_creative",
    )
    policy = TemplateCapabilityPolicy(
        policy_id="broken",
        required_capabilities=[TemplateCapabilityBinding(capability_id="missing_required")],
    )
    with pytest.raises(CapabilityActivationError, match="required capability"):
        planner.plan(
            task_profile=profile,
            intent=CapabilityActivationIntent(intent_id="intent", task_profile_id="profile"),
            template_policy=policy,
            catalog_version="catalog",
            activation_mode="enforced",
        )
