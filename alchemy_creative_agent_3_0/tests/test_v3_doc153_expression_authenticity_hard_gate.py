"""Doc153: generic smiles are affect intent; physical smiles stay user-owned."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS,
    SYSTEM_PROMPT,
    build_remote_payload,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    HUMAN_EXPRESSION_REVIEW_INSTRUCTIONS,
    _inspection_prompt,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _plan_metadata() -> dict:
    result = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=EcommerceRemoteBrainTestProvider())
    ).plan_job(
        {
            "user_input": "Create a real-camera photograph of a visible adult person with a natural smile outdoors.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )
    assert result.status.value == "planned"
    return dict(result.metadata)


def test_doc153_brain_separates_affect_intent_from_physical_smile_control() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create a real-camera photograph of a visible adult person with a natural smile outdoors.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer)))
    assert HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS in SYSTEM_PROMPT
    assert payload["human_expression_authenticity_instructions"] == HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS
    assert "generic affect request" in payload["human_expression_authenticity_instructions"]
    assert "explicit physical expression direction" in payload["human_expression_authenticity_instructions"]
    assert "prompt_additions" not in json.dumps(payload, ensure_ascii=False)
    assert "expression_catalogue" not in json.dumps(payload, ensure_ascii=False)
    assert "child" not in json.dumps(payload, ensure_ascii=False).lower()


def test_doc153_review_makes_generic_presenter_smile_a_shared_hard_retry_signal() -> None:
    prompt = _inspection_prompt(_plan_metadata())

    assert HUMAN_EXPRESSION_REVIEW_INSTRUCTIONS in prompt
    assert "human_naturalness_verdict.status=retry_recommended" in prompt
    assert "human_expression_context dimension" in prompt
    assert "A genuine smile may pass" in prompt
    for legacy in ("template_smile", "perfect_smile_repetition", "frozen_child_smile"):
        assert legacy not in prompt
