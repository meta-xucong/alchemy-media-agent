from urllib.parse import urlsplit
import json
from app.config import settings
from app.services.runtime_model_settings import apply_persisted_runtime_model_settings,refresh_runtime_gateway_credentials
from app.services.claude_orchestrator import _claude_code_source_selection
from app.services.model_routing import resolve_claude_model
from app.services.visual_review_agent import get_visual_review_agent_status

apply_persisted_runtime_model_settings()
refresh_runtime_gateway_credentials()
alias = "claude-sonnet-5-5-alchemy-structured"
text = _claude_code_source_selection().model
multimodal = resolve_claude_model(settings, settings.claude_orchestrator_multimodal_model or "")
review = get_visual_review_agent_status()
assert urlsplit(settings.llm_gateway_base_url).hostname == "aiself.vip"
assert text == multimodal == review["model"] == alias
assert review["enabled"] is True and review["model_queue"][1] == "kimi-k3" and review["model_queue"][-1].startswith("gpt-")
print(json.dumps({"live_routes":{"v2_text":text,"v2_multimodal":multimodal,"v2_vision":review["model_queue"]}}))
