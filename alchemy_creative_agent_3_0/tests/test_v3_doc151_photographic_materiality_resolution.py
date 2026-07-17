"""Doc151: photographic materiality remains a Brain-owned whole-image decision."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def test_doc151_finalizer_receives_shared_materiality_duty_without_local_recipe() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create a candid real-camera photograph of a visible adult person reading in a softly lit room.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    finalizer = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer)))
    contract = payload["frozen_render_context"]["active_semantic_capability_contracts"][0]

    assert contract["photographic_material_requirement"] == "camera_observed_human_materiality"
    assert "generic assertion such as photorealistic detail is not material resolution" in SYSTEM_PROMPT
    assert "without adding a face/skin micro-detail or beauty checklist" in SYSTEM_PROMPT
    assert "generic photorealistic-detail label does not resolve materiality" in SYSTEM_PROMPT
    assert "generic photorealistic-detail label does not by itself resolve photographic materiality" in payload[
        "remote_response_contract"
    ]
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "prompt_additions" not in serialized
    assert "skin_recipe" not in serialized
    assert "child" not in serialized.lower()
