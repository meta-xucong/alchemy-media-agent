"""Doc137: Brain-owned whole-image Human Realism preflight receipts."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider


def _human_runtime(provider: EcommerceRemoteBrainTestProvider) -> ScenarioRuntime:
    return ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))


def _human_request() -> dict:
    return {
        "user_input": (
            "Create one natural real-camera photograph of an adult person in an ordinary outdoor setting. "
            "Keep the visible person age-appropriate and physically coherent."
        ),
        "scenario_selection": {"scenario_id": "general_creative"},
        "metadata": {"requested_image_count": 1, "require_real_images": True},
    }


def test_doc137_active_human_contract_requires_explicit_brain_preflight_receipt() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = _human_runtime(provider).plan_job(_human_request())

    assert result.status.value == "planned"
    assert result.metadata["llm_brain"]["audit"]["human_realism_semantic_preflight_required"] is True
    assert result.metadata["llm_brain"]["audit"]["human_realism_semantic_preflight_signed"] is True
    finalizer_request = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    context = finalizer_request["metadata"]["canonical_prompt_context"]
    assert context["final_prompt_semantic_preflight"] == {
        "required": True,
        "scope": "whole_image_human_photographic_plausibility",
        "owner": "remote_v3_llm_brain",
        "revision_mode": "rewrite_complete_canonical_prompt",
    }
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer_request)))
    prompt_schema = payload["return_schema"]["canonical_provider_prompts"][0]
    assert prompt_schema["semantic_preflight_status"] == "approved"
    serialized = json.dumps(payload, ensure_ascii=False)
    assert "positive_prompt_fragments" not in serialized
    assert "negative_prompt_fragments" not in serialized
    assert "retry_patch" not in serialized


def test_doc137_missing_human_preflight_receipt_blocks_before_materialization() -> None:
    class MissingReceiptProvider(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            payload = super().run(request)
            if request.stage == "provider_prompt_finalize":
                for item in payload["canonical_provider_prompts"]:
                    item.pop("semantic_preflight_status", None)
            return payload

    result = _human_runtime(MissingReceiptProvider()).plan_job(_human_request())

    assert result.status.value == "blocked"
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "human_realism_semantic_preflight_missing"
    assert outcome["outcome_class"] == "remote_prompt_signoff_unavailable"
    assert result.planning_result is None


def test_doc137_product_only_plan_does_not_require_a_human_preflight() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = _human_runtime(provider).plan_job(
        {
            "user_input": "Create one factual flat-lay product photograph of the supplied blue dress, with no people.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    assert result.metadata["llm_brain"]["audit"]["human_realism_semantic_preflight_required"] is False
    finalizer_request = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(finalizer_request)))
    prompt_schema = payload["return_schema"]["canonical_provider_prompts"][0]
    assert "semantic_preflight_status" not in prompt_schema


def test_doc137_receipt_does_not_modify_the_brain_signed_renderer_prompt() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = _human_runtime(provider).plan_job(_human_request())

    assert result.status.value == "planned"
    prompt = result.metadata["llm_brain"]["canonical_provider_prompts"][0]
    assert prompt["semantic_preflight_status"] == "approved"
    assert prompt["prompt"] == (
        "Remote Brain approved complete product image 1: preserve the supplied product facts, "
        "reference truth, and explicit user constraints in one coherent photographic image."
    )
    assert "semantic_preflight" not in prompt["prompt"]
