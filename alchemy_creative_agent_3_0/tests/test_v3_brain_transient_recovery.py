"""Bounded recovery for transient shared-Brain transport failures."""

from __future__ import annotations

import httpx
import pytest

from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    BrainProviderError,
    BrainTransportTimeoutError,
    V3LLMBrainProvider,
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
