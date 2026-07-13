"""Doc113 red-to-green architecture regression coverage.

These tests protect execution truth rather than a prompt recipe.  They are
deliberately small so every later phase can prove the same public invariant
without depending on a real provider.
"""

from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.generation_router.providers import GenerationProvider
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
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


def test_direct_product_and_project_entries_normalize_one_count_size_and_text_contract() -> None:
    user_input = "Create two wide editorial still-life images with no visible text."
    runtime = ScenarioRuntime()
    direct = runtime.plan_job(
        {
            "user_input": user_input,
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 2}},
            "metadata": {"requested_image_count": 2, "requested_image_size": "1536x1024"},
        }
    )
    product_service = V3ProductApiService()
    product = product_service.create_job(
        {
            "user_input": user_input,
            "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 2}},
            "metadata": {"requested_image_count": 2, "requested_image_size": "1536x1024"},
        }
    )
    product_record = product_service.get_job_record(product.job_id)
    assert product_record is not None

    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": user_input})["project"]
    project_job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "general_template",
            "user_input": user_input,
            "metadata": {"requested_image_count": 2, "requested_image_size": "1536x1024"},
        },
    )
    project_record = handlers.service.get_job_record(project_job["job_id"])
    assert project_record is not None

    intents = [
        direct.metadata["normalized_v3_job_intent"],
        product_record.request.metadata["normalized_v3_job_intent"],
        project_record.request.metadata["normalized_v3_job_intent"],
    ]
    deliveries = [
        direct.metadata["template_deliverable_plan"],
        product_record.request.metadata["template_deliverable_plan"],
        project_record.request.metadata["template_deliverable_plan"],
    ]

    for intent, delivery in zip(intents, deliveries, strict=True):
        assert intent["effective_image_count"] == 2
        assert intent["effective_image_size"] == "1536x1024"
        assert intent["visible_text_policy"] == "forbidden"
        assert intent["text_policy"] == "provider_native_text_forbidden"
        assert delivery["effective_image_count"] == 2
        assert len(delivery["deliverables"]) == 2


def test_generation_reuses_the_server_frozen_intent_when_later_parameters_drift() -> None:
    runtime = ScenarioRuntime()
    planning_payload = {
        "user_input": "Create one clean wide still-life image with no visible text.",
        "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 1}},
        "metadata": {"requested_image_count": 1, "requested_image_size": "1536x1024"},
    }
    planned = runtime.plan_job(planning_payload)
    assert planned.status.value == "planned"

    frozen_plan = planned.metadata["capability_activation_plan"]
    frozen_intent = planned.metadata["normalized_v3_job_intent"]
    generation_payload = {
        **planning_payload,
        # This simulates stale per-stage/default transport.  It must not
        # overwrite the immutable job decision made above.
        "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 2}},
        "metadata": {
            **planning_payload["metadata"],
            "requested_image_count": 2,
            "capability_activation_plan": frozen_plan,
            "capability_plan_provenance": {
                "authority": "v3_product_api",
                "issued_for_job_id": "doc113-frozen-intent-job",
                "plan_id": frozen_plan["plan_id"],
                "plan_fingerprint": frozen_plan["fingerprint"],
            },
            "normalized_v3_job_intent": frozen_intent,
        },
        "trusted_capability_plan_reuse": True,
    }

    generated = runtime.generate_job(generation_payload)

    assert generated.status.value == "generated"
    assert generated.metadata["normalized_v3_job_intent"]["effective_image_count"] == 1
    assert generated.metadata["template_deliverable_plan"]["effective_image_count"] == 1
    assert len(generated.metadata["template_deliverable_plan"]["deliverables"]) == 1


def test_direct_runtime_rejects_untrusted_frozen_normalized_intent() -> None:
    runtime = ScenarioRuntime()
    planned = runtime.plan_job(
        {
            "user_input": "Create one still life",
            "metadata": {"requested_image_count": 1},
        }
    )
    result = runtime.plan_job(
        {
            "user_input": "Create one still life",
            "metadata": {"normalized_v3_job_intent": planned.metadata["normalized_v3_job_intent"]},
        }
    )

    assert result.status.value == "blocked"
    assert any("untrusted_normalized_v3_job_intent" in warning for warning in result.warnings)


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
