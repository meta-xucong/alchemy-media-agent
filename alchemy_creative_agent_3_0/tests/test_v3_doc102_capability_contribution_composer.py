import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities import SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ActivatedCapability,
    CapabilityActivationPlan,
    CapabilityContribution,
    CapabilityContributionComposer,
    CapabilityContributionError,
    VisualCapabilityRegistry,
)


def _plan():
    active = ActivatedCapability(capability_id="visual_grammar", version="v1", confidence=1.0)
    return CapabilityActivationPlan(
        plan_id="plan",
        fingerprint="fingerprint",
        job_id="job",
        task_profile_id="profile",
        template_id="general_template",
        scenario_id="general_creative",
        active_capabilities=[active],
        dependency_order=["visual_grammar"],
        activation_mode="enforced",
    )


def _composer():
    execution = SharedCapabilityRegistry.with_default_modules()
    return CapabilityContributionComposer(VisualCapabilityRegistry.with_default_manifests(execution))


def test_composer_keeps_only_active_plan_contributions() -> None:
    contribution = CapabilityContribution(
        capability_id="visual_grammar",
        capability_version="v1",
        activation_plan_id="plan",
        prompt_additions=["clean light", "clean light"],
        stages=["generation_prompt"],
    )
    composed = _composer().compose(_plan(), [contribution])
    assert composed.prompt_additions == ["clean light"]
    assert composed.active_capability_ids == ["visual_grammar"]


def test_inactive_contribution_is_ignored() -> None:
    contribution = CapabilityContribution(
        capability_id="human_realism",
        capability_version="v1",
        activation_plan_id="plan",
        prompt_additions=["skin rules"],
        stages=["generation_prompt"],
    )
    composed = _composer().compose(_plan(), [contribution])
    assert "skin rules" not in composed.prompt_additions


def test_plan_id_mismatch_is_rejected() -> None:
    contribution = CapabilityContribution(
        capability_id="visual_grammar",
        capability_version="v1",
        activation_plan_id="wrong",
        stages=["generation_prompt"],
    )
    with pytest.raises(CapabilityContributionError, match="frozen plan"):
        _composer().compose(_plan(), [contribution])


def test_undeclared_stage_is_rejected() -> None:
    contribution = CapabilityContribution(
        capability_id="visual_grammar",
        capability_version="v1",
        activation_plan_id="plan",
        stages=["provider_input_plan"],
    )
    with pytest.raises(CapabilityContributionError, match="undeclared"):
        _composer().compose(_plan(), [contribution])
