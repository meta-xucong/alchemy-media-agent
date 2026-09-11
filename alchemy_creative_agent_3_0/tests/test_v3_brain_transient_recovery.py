"""Bounded recovery for transient shared-Brain transport failures."""

from __future__ import annotations

import httpx
import pytest

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainExecutionBudgetExceeded,
    BrainOutputTruncated,
    BrainProviderError,
    BrainTransportTimeoutError,
    V3LLMBrainProvider,
    transport_failure_receipt,
)


def _configure_brain(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_PROVIDER", "deepseek")
    monkeypatch.setenv("V3_LLM_BRAIN_MODEL", "deepseek-test")
    monkeypatch.setenv("V3_LLM_BRAIN_API_KEY", "brain-test-key")
    monkeypatch.setenv("V3_LLM_BRAIN_BASE_URL", "https://brain.example.test/v1")
    monkeypatch.setenv("V3_LLM_BRAIN_EXECUTION_BUDGET_SECONDS", "20")
    monkeypatch.setenv("V3_LLM_BRAIN_TIMEOUT_SECONDS", "7")


def test_transient_upstream_http_failure_retries_same_frozen_request(monkeypatch) -> None:
    _configure_brain(monkeypatch)
    calls: list[dict[str, object]] = []

    def fake_stream(**kwargs):  # noqa: ANN003
        calls.append(kwargs)
        if len(calls) == 1:
            request = httpx.Request("POST", kwargs["url"])
            response = httpx.Response(502, request=request)
            raise httpx.HTTPStatusError("upstream unavailable", request=request, response=response)
        return '{"remote": true}'

    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    provider = V3LLMBrainProvider()
    with provider.execution_scope():
        result = provider.run(BrainRunRequest(user_input="Create one natural portrait."))

    assert result["remote"] is True
    assert len(calls) == 2
    assert calls[0]["payload"] == calls[1]["payload"]
    receipt = result["_alchemy_brain_transport"]
    assert {
        key: receipt[key]
        for key in (
            "attempts",
            "json_serialization_recovery_attempted",
            "json_serialization_recovery_succeeded",
            "transient_recovery_attempted",
            "transient_recovery_succeeded",
        )
    } == {
        "attempts": 2,
        "json_serialization_recovery_attempted": False,
        "json_serialization_recovery_succeeded": False,
        "transient_recovery_attempted": True,
        "transient_recovery_succeeded": True,
    }
    assert receipt["execution_budget"]["logical_budget_seconds"] == 20.0


def test_authentication_failure_is_not_retried(monkeypatch) -> None:
    _configure_brain(monkeypatch)
    calls = 0

    def fake_stream(**kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        request = httpx.Request("POST", kwargs["url"])
        response = httpx.Response(401, request=request)
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)

    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    with pytest.raises(BrainProviderError):
        V3LLMBrainProvider().run(BrainRunRequest(user_input="Create one natural portrait."))
    assert calls == 1


def test_timeout_gets_one_retry_without_resetting_shared_budget(monkeypatch) -> None:
    _configure_brain(monkeypatch)
    calls = 0

    def fake_stream(**kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            raise BrainTransportTimeoutError(
                stage="generate",
                timeout_seconds=7,
                elapsed_ms=7000,
                timeout_phase="read_timeout",
            )
        return '{"remote": true}'

    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    provider = V3LLMBrainProvider()
    with provider.execution_scope() as budget:
        result = provider.run(BrainRunRequest(user_input="Create one natural portrait."))
        assert budget.remaining_seconds() > 0

    assert calls == 2
    assert result["_alchemy_brain_transport"]["transient_recovery_attempted"] is True
    assert result["_alchemy_brain_transport"]["execution_budget"]["logical_budget_seconds"] == 20.0


def test_wrapped_upstream_status_message_gets_one_retry(monkeypatch) -> None:
    _configure_brain(monkeypatch)
    calls = 0

    def fake_stream(**kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        if calls == 1:
            raise BrainProviderError("remote brain provider failed: upstream status code 502")
        return '{"remote": true}'

    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    provider = V3LLMBrainProvider()
    with provider.execution_scope():
        result = provider.run(BrainRunRequest(user_input="Create one natural portrait."))

    assert result["remote"] is True
    assert calls == 2
    assert result["_alchemy_brain_transport"]["transient_recovery_succeeded"] is True


def test_nested_transport_timeout_is_normalized_and_retried(monkeypatch) -> None:
    """An SDK wrapper must not hide a typed upstream timeout from the retry gate."""

    _configure_brain(monkeypatch)
    calls = 0

    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    def fake_stream(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        brain_providers._mark_transport_event("response_started")  # noqa: SLF001
        try:
            raise httpx.ReadTimeout("upstream read timed out")
        except httpx.ReadTimeout as cause:
            wrapped = BrainProviderError("SDK wrapper hid the transport timeout")
            wrapped.__cause__ = cause
            raise wrapped

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    provider = V3LLMBrainProvider()
    with pytest.raises(BrainTransportTimeoutError) as failure:
        with provider.execution_scope():
            provider.run(BrainRunRequest(user_input="Create one natural portrait."))

    assert calls == 2
    assert failure.value.timeout_phase == "read_timeout"
    receipt = transport_failure_receipt(failure.value)
    assert receipt["attempts"] == 2
    assert receipt["request_dispatched"] is True
    assert receipt["transient_recovery_attempted"] is True


def test_pre_dispatch_serialization_failure_keeps_request_started_false(monkeypatch) -> None:
    """A local request-construction error must not be reported as upstream dispatch."""

    _configure_brain(monkeypatch)
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "true")
    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    def fake_stream(**_kwargs):  # noqa: ANN003
        raise TypeError("cannot serialize https://unsafe.example/private-body")

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    provider = V3LLMBrainProvider()
    with pytest.raises(BrainProviderError) as failure:
        provider.run(BrainRunRequest(user_input="Create one natural portrait."))

    audit = V3LLMBrainAdapter(provider=provider).provider_failure_audit(
        failure.value,
        stage="plan",
    )
    assert audit["remote_brain_request_started"] is False
    assert audit["remote_brain_transport_attempt"]["request_dispatched"] is False
    assert "unsafe.example" not in str(audit)

    result = V3LLMBrainAdapter(provider=provider).run(
        BrainRunRequest(user_input="Create one natural portrait.")
    )
    safe_metadata = result.safe_metadata()
    assert "remote_provider_error" not in safe_metadata["audit"]
    assert "unsafe.example" not in str(safe_metadata)
    assert all("unsafe.example" not in warning for warning in result.warnings)


def test_initial_budget_exhaustion_has_bounded_stage_receipt(monkeypatch) -> None:
    """Budget preflight failures still carry a valid zero-attempt receipt."""

    _configure_brain(monkeypatch)
    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    clock = iter((0.0, 21.0))
    monkeypatch.setattr(brain_providers.time, "perf_counter", lambda: next(clock))
    provider = V3LLMBrainProvider()
    with pytest.raises(BrainExecutionBudgetExceeded) as failure:
        with provider.execution_scope():
            provider.run(BrainRunRequest(user_input="Create one natural portrait.", stage="plan"))

    receipt = transport_failure_receipt(failure.value)
    assert receipt["schema_version"] == "v3_brain_transport_attempt_v1"
    assert receipt["stage"] == "plan"
    assert receipt["attempts"] == 0
    assert receipt["request_dispatched"] is False


def test_failed_serialization_recovery_preserves_bounded_attempt_receipt(monkeypatch) -> None:
    """A truncated first reply plus timeout recovery remains diagnosable."""

    _configure_brain(monkeypatch)
    calls = 0

    from alchemy_creative_agent_3_0.app.llm_brain import providers as brain_providers

    def fake_stream(**_kwargs):  # noqa: ANN003
        nonlocal calls
        calls += 1
        brain_providers._mark_transport_event("request_dispatched")  # noqa: SLF001
        brain_providers._mark_transport_event("response_started")  # noqa: SLF001
        if calls == 1:
            raise BrainOutputTruncated("first response hit the output limit")
        raise BrainTransportTimeoutError(
            stage="plan",
            timeout_seconds=7,
            elapsed_ms=7000,
            timeout_phase="read_timeout",
            response_started=True,
        )

    monkeypatch.setattr(brain_providers, "_collect_openai_chat_completion_stream", fake_stream)
    provider = V3LLMBrainProvider()
    with pytest.raises(BrainTransportTimeoutError) as failure:
        with provider.execution_scope():
            provider.run(BrainRunRequest(user_input="Create one natural portrait.", stage="plan"))

    receipt = transport_failure_receipt(failure.value)
    assert receipt == {
            "schema_version": "v3_brain_transport_attempt_v1",
            "stage": "plan",
            "attempts": 2,
            "request_acceptance": "dispatched",
            "request_dispatched": True,
        "response_started": True,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
            "json_recovery": True,
            "json_serialization_recovery_attempted": True,
            "transient_recovery_attempted": False,
            "protocol_fallback_attempted": False,
        }

    audit = V3LLMBrainAdapter(provider=provider).provider_failure_audit(failure.value, stage="plan")
    assert audit["remote_brain_request_started"] is True
    assert audit["remote_brain_transport_attempt"] == receipt


def test_budget_guard_keeps_dispatch_evidence_from_the_prior_attempt(monkeypatch) -> None:
    """A terminal local budget guard must not erase a dispatched upstream call."""

    _configure_brain(monkeypatch)
    import alchemy_creative_agent_3_0.app.llm_brain.providers as brain_providers

    clock = [0.0]
    monkeypatch.setattr(brain_providers.time, "perf_counter", lambda: clock[0])
    provider = V3LLMBrainProvider()

    def failed_attempt(_request, *, json_recovery=False):  # noqa: ANN001, ARG001
        brain_providers._mark_transport_event("request_dispatched")  # noqa: SLF001
        clock[0] = 21.0
        raise BrainTransportTimeoutError(
            stage="plan",
            timeout_seconds=7,
            elapsed_ms=7000,
            timeout_phase="read_timeout",
        )

    monkeypatch.setattr(provider, "_run_openai_compatible", failed_attempt)
    with pytest.raises(BrainExecutionBudgetExceeded) as failure:
        with provider.execution_scope():
            provider.run(BrainRunRequest(user_input="Create one natural portrait.", stage="plan"))

    receipt = transport_failure_receipt(failure.value)
    assert receipt["attempts"] == 1
    assert receipt["stage"] == "plan"
    assert receipt["request_dispatched"] is True
    assert receipt["transient_recovery_attempted"] is False
