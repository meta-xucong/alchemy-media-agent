import time

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import BrainProviderError, V3LLMBrainProvider


class _HangingBrainProvider(V3LLMBrainProvider):
    def _run_openai_compatible(self, request: BrainRunRequest, *, json_recovery: bool = False):
        time.sleep(2.0)
        return {"image_set_plan": {"outputs": []}}


def test_brain_provider_request_timeout_is_outer_hard_cap(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_PROVIDER", "openai")
    provider = _HangingBrainProvider()

    request = BrainRunRequest(
        user_input="Prepare a bounded Brain request.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        transport_timeout_seconds=1.0,
        metadata={"canonical_prompt_context": {}},
    )

    started = time.perf_counter()
    with pytest.raises(BrainProviderError, match="timed out"):
        provider.run(request)

    assert time.perf_counter() - started < 1.6
