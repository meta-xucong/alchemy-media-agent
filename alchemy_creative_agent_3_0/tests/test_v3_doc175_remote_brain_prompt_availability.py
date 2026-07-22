"""Doc175: Remote-Brain prompt availability stays bounded and Brain-owned."""

from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    CANONICAL_FINALIZER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    system_prompt_for_stage,
)
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainExecutionBudgetExceeded,
    V3LLMBrainProvider,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import EcommerceRemoteBrainTestProvider
from services.alchemy_codex_local_adapter.native_planner import CodexNativeImageGenPlanner


def _request() -> BrainRunRequest:
    return BrainRunRequest(
        user_input="Create one complete real-camera portrait direction.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"require_real_images": True},
    )


def test_doc175_finalizer_uses_smaller_stage_instruction_without_local_prompt_author() -> None:
    assert system_prompt_for_stage("plan") == SYSTEM_PROMPT
    assert system_prompt_for_stage("provider_prompt_finalize") == CANONICAL_FINALIZER_SYSTEM_PROMPT
    assert len(CANONICAL_FINALIZER_SYSTEM_PROMPT) < len(SYSTEM_PROMPT)
    assert "sole final prompt author" in CANONICAL_FINALIZER_SYSTEM_PROMPT
    assert "local repair phrase" in CANONICAL_FINALIZER_SYSTEM_PROMPT
    assert "provider-admission safeguard" in CANONICAL_FINALIZER_SYSTEM_PROMPT
    assert "Do not repeat contrastive safety wording" in CANONICAL_FINALIZER_SYSTEM_PROMPT


def test_doc175_provider_shares_one_budget_and_blocks_before_a_late_remote_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No sleep: a deterministic clock proves a second call cannot overrun."""

    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    clock = [0.0]
    monkeypatch.setattr(providers_module.time, "perf_counter", lambda: clock[0])
    monkeypatch.setenv("V3_LLM_BRAIN_PROVIDER", "openai")
    monkeypatch.setenv("V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS", "1")
    provider = V3LLMBrainProvider()
    monkeypatch.setattr(provider, "_run_openai_compatible", lambda *_args, **_kwargs: {"ok": True})

    with provider.execution_scope():
        result = provider.run(_request())
        assert result["_alchemy_brain_transport"]["execution_budget"]["state"] == "within_budget"
        clock[0] = 1.1
        with pytest.raises(BrainExecutionBudgetExceeded):
            provider.run(_request())


def test_doc175_adapter_preserves_legacy_fake_providers_without_creative_fallback() -> None:
    class ContractProvider:
        provider = "fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            return True

        def run(self, _request: BrainRunRequest) -> dict:
            return {
                "intent_summary": {"primary_goal": "portrait", "requested_image_count": 1},
                "project_memory_digest": {},
                "image_set_plan": {"image_count": 1, "shot_plan": ["one portrait"]},
                "prompt_guidance": {"optimized_direction": "Remote Brain direction."},
                "prompt_review": {},
                "user_visible_summary": {"summary": "planned"},
                "visual_task_profile": {
                    "rendering_intent": {
                        "rendering_mode": "photoreal",
                        "stylization_scope": "none",
                        "decision_owner": "remote_brain",
                    },
                    "subject_entities": [],
                    "visual_intent_tags": [],
                    "unknown_requirements": [],
                    "confidence": 0.9,
                    "evidence": [],
                },
                "capability_activation_intent": {"requested_capability_ids": [], "rejected_capability_ids": []},
            }

    adapter = V3LLMBrainAdapter(provider=ContractProvider())
    with adapter.execution_scope():
        result = adapter.run(_request())
    assert result.llm_used is True
    assert result.fallback_used is False


def test_doc175_mcp_planning_receipt_projects_only_safe_aggregate_facts() -> None:
    receipt = CodexNativeImageGenPlanner._planning_receipt(  # noqa: SLF001 - contract projection
        {
            "audit": {
                "remote_brain_call_count": 2,
                "remote_brain_transports": [
                    {"stage": "plan", "elapsed_ms": 44},
                    {"stage": "provider_prompt_finalize", "elapsed_ms": 66},
                ],
                "remote_brain_execution_budget": {
                    "logical_budget_seconds": 260.0,
                    "remaining_ms": 150000,
                    "state": "within_budget",
                    "endpoint": "must-not-project",
                },
            }
        }
    )
    assert receipt == {
        "state": "planned",
        "remote_brain_call_count": 2,
        "stages": ["plan", "provider_prompt_finalize"],
        "total_elapsed_ms": 110,
        "execution_budget": {
            "logical_budget_seconds": 260.0,
            "remaining_ms": 150000,
            "state": "within_budget",
        },
    }


def test_doc175_finalizer_budget_exhaustion_blocks_before_any_image_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalizerBudgetFailure(EcommerceRemoteBrainTestProvider):
        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_finalize":
                raise BrainExecutionBudgetExceeded("budget exhausted")
            return super().run(request)

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=FinalizerBudgetFailure()))
    result = runtime.plan_job(
        {
            "user_input": "Create one real-camera portrait.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {
                "template_id": "general_template",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["remote_error_class"] == "execution_budget_exhausted"
    assert outcome["execution_budget"]["state"] == "exhausted"
    assert "provider" not in outcome
