"""Doc138: Brain-owned natural presence is a frozen semantic priority."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityActivationError
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _guidance() -> dict:
    return HumanPhotorealismLayer().build(
        project_id="project_doc138",
        job_id="job_doc138",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a candid real-camera photograph of an adult ceramic artist in their sunlit workshop.",
        subject_type="person",
        variation_mode="single_hero",
        has_identity_reference=False,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        },
    ).model_dump(mode="json")


def test_doc138_natural_presence_is_typed_without_local_renderer_prose() -> None:
    guidance = _guidance()
    contract = guidance["semantic_contract"]

    assert contract["contract_version"] == "v3_human_realism_semantic_v2"
    assert contract["natural_presence_priority"] == "individual_human_presence"
    assert contract["aesthetic_boundary"] == "preserve_user_style_without_generic_beauty_substitution"
    serialized = json.dumps(contract, ensure_ascii=False)
    assert "prompt_additions" not in serialized
    assert "negative_additions" not in serialized
    assert "child" not in serialized


def test_doc138_rejects_the_old_contract_version_before_finalizer_projection() -> None:
    guidance = _guidance()
    guidance["semantic_contract"]["contract_version"] = "v3_human_realism_semantic_v1"
    plan = SimpleNamespace(dependency_order=["human_realism"])
    ledger = SimpleNamespace(
        provider_projection={"capability_projection": {"human_photorealism_guidance": guidance}}
    )

    with pytest.raises(CapabilityActivationError, match="human_realism_semantic_contract_missing"):
        ScenarioRuntime._active_semantic_capability_contracts(plan, ledger)


def test_doc138_remote_finalizer_receives_natural_presence_contract_and_owns_prompt() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create a candid real-camera portrait of an adult ceramic artist in their sunlit workshop.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(request for request in provider.requests if request["stage"] == "provider_prompt_finalize")
    context = finalizer["metadata"]["canonical_prompt_context"]
    assert context["active_semantic_capability_contracts"] == [
        {
            **context["active_semantic_capability_contracts"][0],
            "natural_presence_priority": "individual_human_presence",
            "aesthetic_boundary": "preserve_user_style_without_generic_beauty_substitution",
        }
    ]
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer)))
    assert payload["frozen_render_context"]["active_semantic_capability_contracts"] == context[
        "active_semantic_capability_contracts"
    ]
    assert "generic commercial-beauty archetype" in SYSTEM_PROMPT
    assert "merely repeats generic adjectives" in SYSTEM_PROMPT
    assert "local repair phrase" in SYSTEM_PROMPT
