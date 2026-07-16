"""Doc144: only the remote Brain may reject a defaulted human portrait."""

from __future__ import annotations

import copy
import json

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT, build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


class _SituationOwnedResigner(EcommerceRemoteBrainTestProvider):
    """The fixture is the remote author; runtime code never supplies rewrite text."""

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_finalize":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A polished commercial portrait of a person in a bright room."
            )
        elif request.stage == "provider_prompt_human_naturalness_resign":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A candid real-camera photograph of a person pausing over a book by a window in their ordinary home, "
                "with the quiet, unperformed moment and requested daylight preserved."
            )
            payload["canonical_provider_prompts"][0]["human_naturalness_decision"] = {
                "contract_version": "v3_human_naturalness_decision_v1",
                "status": "rewritten",
                "owner": "remote_v3_llm_brain",
            }
        return payload


def test_doc144_resigner_gets_the_nondefault_approval_standard_without_local_prompt_words() -> None:
    provider = _SituationOwnedResigner()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create one candid real-camera photograph of a visible adult person reading near a window at home.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    resign = next(item for item in provider.requests if item["stage"] == "provider_prompt_human_naturalness_resign")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(resign)))
    assert payload["candidate_canonical_provider_prompts"][0]["prompt"] == (
        "A polished commercial portrait of a person in a bright room."
    )
    assert "default commercial-presentational" in payload["remote_response_contract"]
    assert "universally beautified portrait" in payload["remote_response_contract"]
    assert "child" not in payload["remote_response_contract"].lower()
    assert "prompt_additions" not in json.dumps(payload, ensure_ascii=False)
    assert result.metadata["llm_brain"]["canonical_provider_prompts"][0]["prompt"] == (
        "A candid real-camera photograph of a person pausing over a book by a window in their ordinary home, "
        "with the quiet, unperformed moment and requested daylight preserved."
    )
    assert result.metadata["llm_brain"]["audit"]["human_realism_natural_presence_decisions"] == [
        {
            "contract_version": "v3_human_naturalness_decision_v1",
            "status": "rewritten",
            "owner": "remote_v3_llm_brain",
        }
    ]


def test_doc144_brain_authority_forbids_a_default_portrait_substitution_without_prescribing_renderer_words() -> None:
    assert "default commercially posed expression" in SYSTEM_PROMPT
    assert "universally beautified portrait" in SYSTEM_PROMPT
    for forbidden in ("child smile", "mouth shape", "pore threshold", "negative prompt"):
        assert forbidden not in SYSTEM_PROMPT.lower()
