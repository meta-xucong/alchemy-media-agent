from urllib.parse import urlsplit
import json
from app.config import settings
from app.services import alchemy_lab_llm,work_intensity
from alchemy_creative_agent_3_0.app.llm_brain.adapter import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import V3LLMBrainProvider
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import OpenAIVisionInspectionProvider

alias = "claude-sonnet-5-5-alchemy-structured"
brain = V3LLMBrainProvider()
signoff = BrainRunRequest(user_input="Synthetic route check.",
    scenario_id="general_creative",template_id="general_template",stage="provider_prompt_finalize")
v1 = [entry["model"] for entry in work_intensity._planner_candidates()]
lab_text = [entry["model"] for entry in alchemy_lab_llm._planner_candidates(image_paths=False)]
lab_vision = alchemy_lab_llm._planner_candidates(image_paths=True)
v3_vision = OpenAIVisionInspectionProvider().model_chain
assert urlsplit(settings.llm_gateway_base_url).hostname == "aiself.vip"
assert v1[0] == lab_text[0] == brain.model == brain._primary_model_for_request(signoff) == v3_vision[0] == alias
assert lab_vision[0]["model"].startswith("gpt-") and {"provider": "anthropic", "model": alias} in lab_vision
assert all(queue[1] == "kimi-k3" and queue[-1].startswith("gpt-") for queue in (v1,lab_text,v3_vision))
print(json.dumps({"live_routes":{"v1":v1,"v3_brain":brain.model,"v3_signoff":brain._primary_model_for_request(signoff),
     "v3_vision":v3_vision,"lab_text":lab_text,"lab_vision":lab_vision}}))
