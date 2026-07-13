"""Doc113 Phase 2/3 template ownership and count-contract regressions."""

from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import _bounded_requested_count
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus


def test_ecommerce_requested_count_keeps_declared_provider_capacity() -> None:
    assert _bounded_requested_count(1) == 1
    assert _bounded_requested_count(2) == 2
    assert _bounded_requested_count(4) == 4
    assert _bounded_requested_count(7) == 7


def test_ecommerce_template_binds_all_seven_remote_brain_outputs(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    )
    result = runtime.plan_job(
        {
            "user_input": "Create seven complete images for this supplied reusable bottle.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 7, "provider_max_requested_images": 7},
            },
            "product_profile": {"product_name": "reusable bottle", "material": "steel"},
            "metadata": {"requested_image_count": 7, "provider_max_requested_images": 7},
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    intent = result.metadata["normalized_v3_job_intent"]
    delivery = result.metadata["template_deliverable_plan"]
    assert intent["requested_image_count"] == intent["effective_image_count"] == 7
    assert delivery["owner"] == "ecommerce_template"
    assert delivery["creative_direction_owner"] == "remote_v3_llm_brain"
    assert len(delivery["deliverables"]) == 7
    assert [item["output_index"] for item in delivery["deliverables"]] == list(range(1, 8))


def test_declared_provider_capacity_blocks_instead_of_silent_count_truncation(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    )
    result = runtime.plan_job(
        {
            "user_input": "Create seven complete images for this supplied reusable bottle.",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "parameters": {"requested_image_count": 7, "provider_max_requested_images": 4},
            },
            "product_profile": {"product_name": "reusable bottle"},
            "metadata": {"requested_image_count": 7, "provider_max_requested_images": 4},
        }
    )

    assert result.status == ScenarioRuntimeStatus.BLOCKED
    assert "requested_image_count_not_supported_by_declared_contract" in " ".join(result.warnings)
