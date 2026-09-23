"""Brand facts reach both Brain stages; signed prompts remain Brain-owned."""
import json
from types import SimpleNamespace
import pytest
from alchemy_creative_agent_3_0.app.llm_brain.adapter import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.context_digest import compact_brand_visual_context
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload, system_prompt_for_stage

BRAND = {"brand_name": "CELISIA", "visual_tone": ["luminous silver", "clean luxury"],
    "color_palette": ["white", "silver"], "reference_assets": [{"file_path": "private-path"}],
    "metadata": {"private": "must-not-be-sent"}}


def test_brand_fact_projection_excludes_private_reference_history():
    assert compact_brand_visual_context(BRAND) == {key: BRAND[key] for key in ("brand_name", "visual_tone", "color_palette")}


@pytest.mark.parametrize("real_images", [False, True])
def test_planning_request_carries_brand_visual_context(real_images):
    adapter = V3LLMBrainAdapter(provider=SimpleNamespace(provider="test", model="fixture"))
    request = adapter.build_request(user_input="product photo", stage="plan", scenario_id="general_creative",
        template_id="general_template", metadata={"require_real_images": real_images}, brand_context=BRAND)
    payload = json.loads(build_remote_payload(request))
    assert payload["brand_visual_context"] == compact_brand_visual_context(BRAND)
    assert "private-path" not in json.dumps(payload)
    assert "must-not-be-sent" not in json.dumps(payload)

def test_finalizer_receives_same_brand_facts_and_ownership_instruction():
    request = BrainRunRequest(user_input="product photo", stage="provider_prompt_finalize",
        scenario_id="general_creative", template_id="general_template", requested_image_count=1,
        brand_visual_context=compact_brand_visual_context(BRAND), metadata={"canonical_prompt_context": {}})
    payload = json.loads(build_remote_payload(request))
    assert payload["frozen_render_context"]["brand_visual_context"] == compact_brand_visual_context(BRAND)
    assert "brand_visual_context" in system_prompt_for_stage("provider_prompt_finalize")


def test_frozen_brand_context_takes_precedence_over_later_defaults():
    frozen = {"visual_tone": ["frozen tone"]}
    request = BrainRunRequest(user_input="product photo", stage="provider_prompt_finalize",
        requested_image_count=1, brand_visual_context={"visual_tone": ["later default"]},
        metadata={"canonical_prompt_context": {"brand_visual_context": frozen}})
    assert json.loads(build_remote_payload(request))["frozen_render_context"]["brand_visual_context"] == frozen
