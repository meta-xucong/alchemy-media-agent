"""Doc113 red-to-green architecture regression coverage.

These tests protect execution truth rather than a prompt recipe.  They are
deliberately small so every later phase can prove the same public invariant
without depending on a real provider.
"""

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.generation_router.providers import GenerationProvider
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.shared_capabilities import (
    CapabilityResult,
    CapabilityRunResult,
    CapabilityRunStatus,
    CapabilityStatus,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ActivatedCapability,
    CapabilityActivationPlan,
    ecommerce_capability_policy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import active_review_contract


def _frozen_enforced_plan() -> dict:
    return CapabilityActivationPlan(
        plan_id="doc113-plan",
        fingerprint="doc113-fingerprint",
        job_id="doc113-job",
        task_profile_id="generic_visual",
        template_id="general_template",
        scenario_id="general_creative",
        active_capabilities=[
            ActivatedCapability(capability_id="visual_grammar", version="v1"),
        ],
        dependency_order=["visual_grammar"],
        activation_mode="enforced",
    ).model_dump(mode="json")


def test_frozen_enforced_plan_cannot_be_downgraded_by_environment(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "shadow")
    runtime = ScenarioRuntime()
    request = ScenarioRuntimeRequest(
        user_input="Create one still life",
        metadata={"capability_activation_plan": _frozen_enforced_plan()},
    )

    assert runtime._capability_activation_mode(request) == "enforced"


def test_direct_runtime_rejects_a_frozen_plan_without_product_api_provenance() -> None:
    runtime = ScenarioRuntime()

    result = runtime.plan_job(
        {
            "user_input": "Create one still life",
            "metadata": {"capability_activation_plan": _frozen_enforced_plan()},
        }
    )

    assert result.status.value == "blocked"
    assert any("untrusted_frozen_capability_activation_plan" in warning for warning in result.warnings)


def test_public_product_api_rejects_runtime_owned_frozen_plan_metadata() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "Create one still life",
                "metadata": {"capability_activation_plan": _frozen_enforced_plan()},
            }
        )


def test_enforced_combined_run_preserves_an_accepted_executor_result() -> None:
    runtime = ScenarioRuntime()
    request = ScenarioRuntimeRequest(user_input="Create one still life")
    resolution = runtime.scenario_registry.resolve({"scenario_id": "general_creative"})
    plan = CapabilityActivationPlan.model_validate(_frozen_enforced_plan())
    accepted = CapabilityResult(
        module_id="future_accepted_executor",
        version="v1",
        status=CapabilityStatus.SUCCESS,
        facts={"accepted": True},
    )
    active_run = CapabilityRunResult(
        status=CapabilityRunStatus.COMPLETE,
        results=[accepted],
    )

    combined = runtime._combine_capability_runs(request, resolution, None, active_run, plan)

    assert combined is not None
    assert [item.module_id for item in combined.results] == ["future_accepted_executor"]


def test_enforced_provider_does_not_read_stale_visual_cluster_without_envelope() -> None:
    request = SimpleNamespace(
        metadata={
            "capability_activation_plan": _frozen_enforced_plan(),
            "visual_cluster": {"human_photorealism_guidance": {"applies": True}},
        }
    )

    assert GenerationProvider()._visual_cluster(request) == {}


def test_enforced_review_does_not_certify_or_read_stale_cluster_contract() -> None:
    metadata = {
        "capability_activation_plan": _frozen_enforced_plan(),
        "visual_cluster": {
            "composed_visual_contribution": {
                "activation_plan_id": "doc113-plan",
                "active_capability_ids": ["visual_grammar"],
                "review_contracts": [
                    {"capability_id": "visual_grammar", "issue_codes": ["stale_cluster_issue"]}
                ],
            }
        },
    }

    contract = active_review_contract(metadata)

    assert contract["legacy_fallback_rejected"] is True
    assert "stale_cluster_issue" not in contract["issue_codes"]


def test_ecommerce_policy_never_activates_general_suite_direction() -> None:
    policy = ecommerce_capability_policy()
    bindings = [
        binding.capability_id
        for group in (policy.required_capabilities, policy.recommended_capabilities, policy.optional_capabilities)
        for binding in group
    ]

    assert "suite_direction" not in bindings
