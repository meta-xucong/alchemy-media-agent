"""Doc175: Remote-Brain prompt availability stays bounded and Brain-owned."""

from __future__ import annotations

import json

import httpx
import pytest

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    CANONICAL_FINALIZER_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    system_prompt_for_stage,
)
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainExecutionBudgetExceeded,
    BrainInvalidJsonResponse,
    BrainOutputTruncated,
    BrainProviderError,
    BrainProviderUnavailable,
    BrainTransportTimeoutError,
    V3LLMBrainProvider,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import _safe_remote_brain_execution_budget
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import ecommerce_capability_policy
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


def _finalizer_request(*, stage: str = "provider_prompt_finalize") -> BrainRunRequest:
    return BrainRunRequest(
        user_input="Sign one remote-owned renderer prompt.",
        stage=stage,
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {}},
        template_capability_policy=ecommerce_capability_policy(),
    )


@pytest.mark.parametrize(
    ("failure", "terminal_reason", "expected"),
    [
        (
            BrainTransportTimeoutError(
                stage="provider_prompt_finalize",
                timeout_seconds=114.371,
                elapsed_ms=5688,
                timeout_phase="read_timeout",
                response_started=True,
                first_content_observed=False,
                complete_response_observed=False,
                json_parse_started=False,
                json_parse_completed=False,
            ),
            "timeout",
            {
                "transport_error_class": "timeout",
                "timeout_phase": "read_timeout",
                "timeout_seconds": 114.371,
                "response_started": True,
            },
        ),
        (
            BrainExecutionBudgetExceeded("budget exhausted D:/unsafe/provider_payload"),
            "execution_budget_exhausted",
            {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 114371,
                "state": "within_budget",
            },
        ),
        (
            BrainProviderError("upstream status code 502 D:/unsafe/provider_payload prompt secret"),
            "upstream_http_error",
            {"remote_http_status_code": 502},
        ),
        (
            BrainProviderUnavailable("D:/unsafe/provider_payload unavailable"),
            "provider_error",
            {"state": "within_budget"},
        ),
        (
            BrainInvalidJsonResponse(
                "malformed D:/unsafe/provider_payload",
                stage="provider_prompt_finalize",
                attempts=2,
                json_recovery_attempted=True,
                json_recovery_succeeded=False,
                json_failure_kind="malformed_json",
            ),
            "invalid_response",
            {
                "transport_error_class": "invalid_json_response",
                "error_family": "json_decode",
                "json_failure_kind": "malformed_json",
                "attempts": 2,
            },
        ),
        (
            BrainOutputTruncated(
                "truncated D:/unsafe/provider_payload",
                stage="provider_prompt_finalize",
                attempts=2,
                json_recovery_attempted=True,
                json_recovery_succeeded=False,
            ),
            "truncated_response",
            {
                "transport_error_class": "truncated_response",
                "error_family": "output_truncated",
                "json_failure_kind": "output_truncated",
                "attempts": 2,
            },
        ),
    ],
)
def test_doc175_finalizer_provider_error_trace_is_public_safe(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
    failure: Exception,
    terminal_reason: str,
    expected: dict[str, object],
) -> None:
    class FinalizerFailureProvider:
        provider = "fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            return True

        def execution_budget_receipt(self) -> dict[str, object]:
            return {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 114371,
                "state": "within_budget",
                "provider_payload": "must-not-leak",
            }

        def run(self, _request: BrainRunRequest) -> dict:
            raise failure

    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))
    adapter = V3LLMBrainAdapter(provider=FinalizerFailureProvider())

    with pytest.raises(type(failure)):
        adapter.finalize_canonical_provider_prompts(_finalizer_request())

    events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    error_events = [event for event in events if event.get("event") == "canonical_finalizer_provider_error"]
    assert len(error_events) == 1
    event = error_events[0]
    assert event["stage"] == "provider_prompt_finalize"
    assert event["terminal_reason"] == terminal_reason
    for key, value in expected.items():
        assert event[key] == value
    serialized = json.dumps(events, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "provider_payload" not in serialized
    assert "prompt secret" not in serialized
    assert "https://" not in serialized


def test_doc175_provider_failure_audit_sanitizes_untrusted_stage() -> None:
    class Provider:
        provider = "fixture"
        model = "fixture"

        def execution_budget_receipt(self) -> dict[str, object]:
            return {"logical_budget_seconds": 1.0, "remaining_ms": 0, "state": "exhausted"}

    adapter = V3LLMBrainAdapter(provider=Provider())  # type: ignore[arg-type]

    audit = adapter.provider_failure_audit(
        BrainProviderError("status code 502 D:/unsafe/provider_payload"),
        stage="D:/unsafe/original.png?provider_payload=secret",
    )

    assert audit["remote_provider_error_class"] == "upstream_http_error"
    assert audit["remote_brain_stage"] == "unknown"
    assert audit["remote_provider_http_status_code"] == 502
    serialized = json.dumps(audit, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "provider_payload" not in serialized


def test_doc175_provider_failure_audit_classifies_chained_http_status_safely() -> None:
    class Provider:
        provider = "fixture"
        model = "fixture"

        def execution_budget_receipt(self) -> dict[str, object]:
            return {"logical_budget_seconds": 520.0, "remaining_ms": 272178, "state": "within_budget"}

    request = httpx.Request("POST", "https://must-not-leak.example/v1/messages")
    response = httpx.Response(429, request=request)
    try:
        raise httpx.HTTPStatusError(
            "HTTP status text with D:/unsafe/provider_payload",
            request=request,
            response=response,
        )
    except httpx.HTTPStatusError as cause:
        failure = BrainProviderError("remote brain provider failed")  # no status text on the wrapper
        failure.__cause__ = cause

    audit = V3LLMBrainAdapter(provider=Provider()).provider_failure_audit(  # type: ignore[arg-type]
        failure,
        stage="provider_prompt_finalize",
    )

    assert audit["remote_provider_error_class"] == "upstream_http_error"
    assert audit["remote_provider_http_status_code"] == 429
    assert audit["remote_brain_stage"] == "provider_prompt_finalize"
    assert "remote_provider_transport_kind" not in audit
    serialized = json.dumps(audit, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "must-not-leak" not in serialized
    assert "provider_payload" not in serialized


def test_doc175_provider_failure_audit_classifies_chained_protocol_error_safely() -> None:
    class Provider:
        provider = "fixture"
        model = "fixture"

        def execution_budget_receipt(self) -> dict[str, object]:
            return {"logical_budget_seconds": 520.0, "remaining_ms": 272178, "state": "within_budget"}

    try:
        raise httpx.RemoteProtocolError("D:/unsafe/provider_payload peer closed stream")
    except httpx.RemoteProtocolError as cause:
        failure = BrainProviderError("remote brain provider failed")  # generic wrapper only
        failure.__cause__ = cause

    audit = V3LLMBrainAdapter(provider=Provider()).provider_failure_audit(  # type: ignore[arg-type]
        failure,
        stage="provider_prompt_finalize",
    )

    assert audit["remote_provider_error_class"] == "upstream_transport_error"
    assert audit["remote_provider_transport_kind"] == "protocol_error"
    serialized = json.dumps(audit, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "provider_payload" not in serialized


def test_doc175_execution_budget_projection_rejects_bool_values() -> None:
    assert _safe_remote_brain_execution_budget(
        {"logical_budget_seconds": True, "remaining_ms": 0, "state": "within_budget"}
    ) == {}
    assert _safe_remote_brain_execution_budget(
        {"logical_budget_seconds": 520.0, "remaining_ms": False, "state": "within_budget"}
    ) == {}


def test_doc175_finalizer_generic_provider_failure_reaches_blocked_outcome_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalizerGenericProviderFailure(EcommerceRemoteBrainTestProvider):
        def execution_budget_receipt(self) -> dict[str, object]:
            return {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 114371,
                "state": "within_budget",
                "raw": "must-not-leak",
            }

        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_finalize":
                raise BrainProviderError(
                    "remote provider failed with status code 502 D:/unsafe/provider_payload prompt secret"
                )
            return super().run(request)

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=FinalizerGenericProviderFailure())
    )
    result = runtime.plan_job(
        {
            "user_input": "Create one real-camera product image.",
            "scenario_selection": {"scenario_id": "ecommerce"},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "remote_creative_brain_prompt_signoff_unavailable"
    assert outcome["outcome_class"] == "remote_prompt_signoff_unavailable"
    assert outcome["remote_error_class"] == "upstream_http_error"
    assert outcome["remote_brain_stage"] == "provider_prompt_finalize"
    assert outcome["remote_http_status_code"] == 502
    assert outcome["execution_budget"] == {
        "logical_budget_seconds": 520.0,
        "remaining_ms": 114371,
        "state": "within_budget",
    }
    serialized = json.dumps(outcome, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "provider_payload" not in serialized
    assert "prompt secret" not in serialized
    assert "raw" not in serialized


def test_doc175_finalizer_chained_transport_failure_reaches_trace_and_outcome_safely(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    class FinalizerProtocolProviderFailure(EcommerceRemoteBrainTestProvider):
        def execution_budget_receipt(self) -> dict[str, object]:
            return {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 272178,
                "state": "within_budget",
            }

        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_finalize":
                try:
                    raise httpx.RemoteProtocolError("D:/unsafe/provider_payload peer closed stream")
                except httpx.RemoteProtocolError as cause:
                    raise BrainProviderError("remote brain provider failed") from cause
            return super().run(request)

    trace_file = tmp_path / "brain-stage-trace.jsonl"
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    monkeypatch.setenv("V3_BRAIN_STAGE_TRACE_FILE", str(trace_file))
    runtime = ScenarioRuntime(
        llm_brain_adapter=V3LLMBrainAdapter(provider=FinalizerProtocolProviderFailure())
    )
    result = runtime.plan_job(
        {
            "user_input": "Create one real-camera product image.",
            "scenario_selection": {"scenario_id": "ecommerce"},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["reason_code"] == "remote_creative_brain_prompt_signoff_unavailable"
    assert outcome["remote_error_class"] == "upstream_transport_error"
    assert outcome["remote_brain_stage"] == "provider_prompt_finalize"
    assert outcome["remote_provider_transport_kind"] == "protocol_error"
    assert outcome["execution_budget"] == {
        "logical_budget_seconds": 520.0,
        "remaining_ms": 272178,
        "state": "within_budget",
    }

    events = [
        json.loads(line)
        for line in trace_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    error_events = [event for event in events if event.get("event") == "canonical_finalizer_provider_error"]
    assert len(error_events) == 1
    assert error_events[0]["terminal_reason"] == "upstream_transport_error"
    assert error_events[0]["remote_provider_transport_kind"] == "protocol_error"

    serialized = json.dumps({"outcome": outcome, "events": events}, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "provider_payload" not in serialized


def test_doc175_finalizer_generic_error_after_successful_plan_needs_stage_scoped_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalizerGenericProviderFailure(EcommerceRemoteBrainTestProvider):
        def __init__(self) -> None:
            super().__init__()
            self.finalizer_requests = 0

        def execution_budget_receipt(self) -> dict[str, object]:
            return {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 309892,
                "state": "within_budget",
                "raw_provider_payload": "must-not-leak",
            }

        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_finalize":
                self.finalizer_requests += 1
                raise BrainProviderError(
                    "generic finalizer provider error D:/unsafe/raw_prompt provider_payload"
                )
            return super().run(request)

    provider = FinalizerGenericProviderFailure()
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": "Create one real-camera product image.",
            "scenario_selection": {"scenario_id": "ecommerce"},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    assert provider.finalizer_requests == 1
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["remote_brain_stage"] == "provider_prompt_finalize"
    assert outcome["remote_error_class"] == "provider_error"
    assert outcome["llm_used"] is True
    assert outcome["fallback_used"] is False
    assert outcome["remote_provider_available"] is True
    assert outcome["remote_brain_finalizer_lifecycle"] == {
        "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
        "stage": "provider_prompt_finalize",
        "provider_available": True,
        "remote_brain_request_started": True,
        "response_started": False,
        "status": "blocked",
        "failure_family": "remote_brain_signoff",
        "failure_code": "provider_error",
    }
    serialized = json.dumps(outcome, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "raw_prompt" not in serialized
    assert "provider_payload" not in serialized


def test_doc175_finalizer_preflight_availability_is_separate_from_planning_availability(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FinalizerUnavailableAfterPlan(EcommerceRemoteBrainTestProvider):
        def __init__(self) -> None:
            super().__init__()
            self.available_calls = 0

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            self.available_calls += 1
            return self.available_calls == 1

    provider = FinalizerUnavailableAfterPlan()
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))

    result = runtime.plan_job(
        {
            "user_input": "Create one real-camera product image.",
            "scenario_selection": {"scenario_id": "ecommerce"},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    outcome = result.metadata["remote_creative_brain_outcome"]
    assert outcome["remote_provider_available"] is True
    assert outcome["remote_brain_finalizer_lifecycle"] == {
        "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
        "stage": "provider_prompt_finalize",
        "provider_available": False,
        "remote_brain_request_started": False,
        "response_started": False,
        "status": "blocked",
        "failure_family": "remote_brain_signoff",
        "failure_code": "provider_unavailable",
    }


def test_doc175_finalizer_configuration_preflight_failures_carry_closed_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Provider:
        provider = "fixture"
        model = "fixture"

        def available(self, *, force: bool = False) -> bool:  # noqa: ARG002
            return True

    request = _finalizer_request()
    adapter = V3LLMBrainAdapter(provider=Provider())  # type: ignore[arg-type]

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    with pytest.raises(BrainProviderUnavailable) as disabled:
        adapter.finalize_canonical_provider_prompts(request)
    disabled_audit = adapter.provider_failure_audit(disabled.value, stage="provider_prompt_finalize")
    assert disabled_audit["remote_brain_finalizer_lifecycle"] == {
        "schema_version": "v3_remote_brain_finalizer_lifecycle_v1",
        "stage": "provider_prompt_finalize",
        "provider_available": False,
        "remote_brain_request_started": False,
        "response_started": False,
        "status": "blocked",
        "failure_family": "remote_brain_signoff",
        "failure_code": "provider_unavailable",
    }

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    no_scope_request = request.model_copy(
        update={
            "template_capability_policy": ecommerce_capability_policy().model_copy(
                update={"brain_activation_enabled": False}
            )
        }
    )
    with pytest.raises(BrainProviderUnavailable) as no_scope:
        adapter.finalize_canonical_provider_prompts(no_scope_request)
    no_scope_audit = adapter.provider_failure_audit(no_scope.value, stage="provider_prompt_finalize")
    assert no_scope_audit["remote_brain_finalizer_lifecycle"] == disabled_audit[
        "remote_brain_finalizer_lifecycle"
    ]


@pytest.mark.parametrize(
    ("failure", "expected_lifecycle"),
    [
        (
            BrainTransportTimeoutError(
                stage="provider_prompt_finalize",
                timeout_seconds=210.0,
                elapsed_ms=210016,
                timeout_phase="read_timeout",
                response_started=True,
                first_content_observed=False,
                complete_response_observed=False,
                json_parse_started=False,
                json_parse_completed=False,
            ),
            {
                "remote_brain_request_started": True,
                "response_started": True,
                "failure_code": "timeout",
            },
        ),
        (
            BrainInvalidJsonResponse(
                "invalid finalizer JSON D:/unsafe/provider_payload",
                stage="provider_prompt_finalize",
                attempts=2,
                json_recovery_attempted=True,
                json_recovery_succeeded=False,
                json_failure_kind="malformed_json",
            ),
            {
                "remote_brain_request_started": True,
                "response_started": True,
                "failure_code": "invalid_response",
            },
        ),
    ],
)
def test_doc175_finalizer_transport_or_serialization_receipt_keeps_stage_scoped_lifecycle(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
    expected_lifecycle: dict[str, object],
) -> None:
    class FinalizerTypedFailure(EcommerceRemoteBrainTestProvider):
        def execution_budget_receipt(self) -> dict[str, object]:
            return {
                "logical_budget_seconds": 520.0,
                "remaining_ms": 114371,
                "state": "within_budget",
            }

        def run(self, request):  # noqa: ANN001
            if request.stage == "provider_prompt_finalize":
                raise failure
            return super().run(request)

    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    runtime = ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=FinalizerTypedFailure()))

    result = runtime.plan_job(
        {
            "user_input": "Create one real-camera product image.",
            "scenario_selection": {"scenario_id": "ecommerce"},
            "metadata": {
                "template_id": "ecommerce_template",
                "requested_image_count": 1,
                "require_real_images": True,
            },
        }
    )

    assert result.status.value == "blocked"
    outcome = result.metadata["remote_creative_brain_outcome"]
    lifecycle = outcome["remote_brain_finalizer_lifecycle"]
    assert lifecycle["schema_version"] == "v3_remote_brain_finalizer_lifecycle_v1"
    assert lifecycle["stage"] == "provider_prompt_finalize"
    assert lifecycle["provider_available"] is True
    assert lifecycle["status"] == "blocked"
    for key, value in expected_lifecycle.items():
        assert lifecycle[key] == value
    assert outcome["remote_brain_execution_budget"] == {
        "logical_budget_seconds": 520.0,
        "remaining_ms": 114371,
        "state": "within_budget",
    }
    if isinstance(failure, BrainTransportTimeoutError):
        assert outcome["remote_brain_transport_failure"]["timeout_phase"] == "read_timeout"
    else:
        assert outcome["remote_brain_serialization_failure"]["json_failure_kind"] == "malformed_json"
    serialized = json.dumps(outcome, sort_keys=True)
    assert "D:/unsafe" not in serialized
    assert "provider_payload" not in serialized
