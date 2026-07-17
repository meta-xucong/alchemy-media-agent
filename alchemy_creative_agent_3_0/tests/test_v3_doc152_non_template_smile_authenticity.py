"""Doc152: smiles stay Brain-owned, situation-grounded and generically reviewed."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import _inspection_prompt
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _plan_metadata() -> dict:
    result = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    ).plan_job(
        {
            "user_input": "Create a candid real-camera photograph of an adult person smiling while greeting a friend outdoors.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )
    assert result.status.value == "planned"
    return dict(result.metadata)


def test_doc152_brain_preserves_situation_owned_smiles_without_a_local_expression_recipe() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create a candid real-camera photograph of an adult person smiling while greeting a friend outdoors.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer)))

    assert "A smile is allowed when it is user-owned or emerges from that individual's situation" in SYSTEM_PROMPT
    assert "not a prohibition on smiling and not an instruction to force a neutral face" in SYSTEM_PROMPT
    assert "generic presentational smile is not approved merely because it looks friendly" in SYSTEM_PROMPT
    assert "smile may remain when user-owned or situation-grounded" in payload["remote_response_contract"]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "prompt_additions" not in serialized
    assert "expression_catalogue" not in serialized
    assert "child" not in serialized.lower()


def test_doc152_enforced_review_uses_only_the_generic_expression_dimension() -> None:
    prompt = _inspection_prompt(_plan_metadata())

    assert "A genuine smile may pass when it belongs to the person and visible situation" in prompt
    assert "human_expression_context dimension" in prompt
    for legacy in ("template_smile", "perfect_smile_repetition", "frozen_child_smile"):
        assert legacy not in prompt
