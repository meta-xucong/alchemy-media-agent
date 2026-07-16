"""Doc139: Human Realism receives an independent remote Brain re-sign."""

from __future__ import annotations

import copy
import json

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from services.alchemy_codex_local_adapter.contracts import NativeImageGenPlanRequest
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


_HUMAN_REQUEST = {
    "user_input": (
        "Create one candid real-camera photograph of an adult ceramic artist working naturally in a sunlit studio. "
        "Keep the person physically credible and the mood ordinary rather than staged."
    ),
    "scenario_selection": {"scenario_id": "general_creative"},
    "metadata": {"requested_image_count": 1, "requested_image_size": "1024x1536", "require_real_images": True},
}


class _DistinctReSigningProvider(EcommerceRemoteBrainTestProvider):
    """Fixture that proves the last Brain pass, not a local patch, reaches output."""

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage == "provider_prompt_finalize":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A polished commercial portrait of an adult ceramic artist in a sunlit studio."
            )
        elif request.stage == "provider_prompt_human_naturalness_resign":
            payload["canonical_provider_prompts"][0]["prompt"] = (
                "A candid real-camera photograph of an adult ceramic artist absorbed in shaping clay at a worktable "
                "in their sunlit studio, preserving the ordinary working moment and the user's requested mood."
            )
        return payload


def test_doc139_active_human_jobs_use_one_finalizer_and_one_independent_resigner() -> None:
    provider = _DistinctReSigningProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(copy.deepcopy(_HUMAN_REQUEST))

    assert result.status.value == "planned"
    stages = [item["stage"] for item in provider.requests]
    assert stages.count("provider_prompt_finalize") == 1
    assert stages.count("provider_prompt_human_naturalness_resign") == 1
    first = next(item for item in provider.requests if item["stage"] == "provider_prompt_finalize")
    resign = next(item for item in provider.requests if item["stage"] == "provider_prompt_human_naturalness_resign")
    assert resign["metadata"]["candidate_canonical_provider_prompts"] == [
        {
            "output_index": 1,
            "prompt": "A polished commercial portrait of an adult ceramic artist in a sunlit studio.",
            "review_status": "approved",
            "semantic_preflight_status": "approved",
        }
    ]
    assert resign["metadata"]["canonical_prompt_context"] == {
        **{
            key: value
            for key, value in first["metadata"]["canonical_prompt_context"].items()
            if key != "retry_evidence"
        },
        "human_naturalness_decision": {
            "required": True,
            "contract_version": "v3_human_naturalness_decision_v1",
            "owner": "remote_v3_llm_brain",
            "frozen_binding": first["metadata"]["canonical_prompt_context"]["frozen_binding"],
        },
    }
    payload = json.loads(build_remote_payload(BrainRunRequest.model_validate(resign)))
    assert payload["candidate_canonical_provider_prompts"] == [
        {
            "output_index": 1,
            "prompt": "A polished commercial portrait of an adult ceramic artist in a sunlit studio.",
            "review_status": "approved",
        }
    ]
    serialized = json.dumps(
        {
            "candidate_canonical_provider_prompts": payload["candidate_canonical_provider_prompts"],
            "frozen_render_context": payload["frozen_render_context"],
        },
        ensure_ascii=False,
    )
    for forbidden in ("prompt_additions", "negative_prompt", "retry_patch", "issue_codes", "recipe"):
        assert forbidden not in serialized
    assert result.metadata["llm_brain"]["canonical_provider_prompts"][0]["prompt"] == (
        "A candid real-camera photograph of an adult ceramic artist absorbed in shaping clay at a worktable "
        "in their sunlit studio, preserving the ordinary working moment and the user's requested mood."
    )
    audit = result.metadata["llm_brain"]["audit"]
    assert audit["human_realism_natural_presence_resigned"] is True
    assert audit["canonical_provider_prompt_stages"] == [
        "provider_prompt_finalize",
        "provider_prompt_human_naturalness_resign",
    ]


def test_doc139_product_only_jobs_do_not_invoke_an_extra_resigning_call() -> None:
    provider = EcommerceRemoteBrainTestProvider()
    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider)).plan_job(
        {
            "user_input": "Create one factual flat-lay photograph of a ceramic vase with no people.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1, "require_real_images": True},
        }
    )

    assert result.status.value == "planned"
    assert [item["stage"] for item in provider.requests].count("provider_prompt_finalize") == 1
    assert not any(item["stage"] == "provider_prompt_human_naturalness_resign" for item in provider.requests)
    assert result.metadata["llm_brain"]["audit"]["canonical_provider_prompt_stages"] == ["provider_prompt_finalize"]


def test_doc139_malformed_resigning_response_blocks_before_a_plan_can_materialize() -> None:
    class _MalformedResigner(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_human_naturalness_resign":
                self.requests.append(copy.deepcopy(request.model_dump(mode="json")))
                return {"canonical_provider_prompts": []}
            return super().run(request)

    result = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=_MalformedResigner())).plan_job(
        copy.deepcopy(_HUMAN_REQUEST)
    )

    assert result.status.value == "blocked"
    assert result.planning_result is None
    assert result.metadata["remote_creative_brain_outcome"]["reason_code"] == (
        "human_realism_natural_presence_resigning_unavailable"
    )


def test_doc139_local_mcp_relays_the_re_signed_string_without_a_second_prompt_path(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_LLM_BRAIN_REMOTE_ENABLED", "true")
    provider = _DistinctReSigningProvider()
    planner = CodexNativeImageGenPlanner(
        runtime_factory=lambda: ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    )

    result = planner.prepare_native_imagegen_plan(
        NativeImageGenPlanRequest.from_mcp_arguments(
            {
                "user_input": _HUMAN_REQUEST["user_input"],
                "template_id": "general_template",
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "reference_inputs": [],
            }
        )
    )

    assert result["status"] == "planned_for_codex_native_imagegen"
    assert result["outputs"][0]["imagegen_prompt"] == (
        "A candid real-camera photograph of an adult ceramic artist absorbed in shaping clay at a worktable "
        "in their sunlit studio, preserving the ordinary working moment and the user's requested mood."
    )
    assert [item["stage"] for item in provider.requests].count("provider_prompt_human_naturalness_resign") == 1
    assert result["provenance"]["canonical_prompt_signing"] == {
        "stages": ["provider_prompt_finalize", "provider_prompt_human_naturalness_resign"],
        "human_realism_natural_presence_resigned": True,
        "human_realism_natural_presence_decision_statuses": ["approved"],
    }
