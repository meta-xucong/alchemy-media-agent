import json
import sys
import time
import types

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    _ACTIVE_TRANSPORT_TRACE,
    _collect_openai_chat_completion_stream,
    _new_transport_trace,
    BrainInvalidJsonResponse,
    BrainOutputTruncated,
    BrainTransportTimeoutError,
    V3LLMBrainProvider,
)


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
    with pytest.raises(BrainTransportTimeoutError, match="timed out") as failure:
        provider.run(request)

    assert time.perf_counter() - started < 1.6
    assert failure.value.safe_metadata() == {
        "schema_version": "v3_brain_transport_failure_v1",
        "stage": "provider_prompt_finalize",
        "transport_error_class": "timeout",
        "timeout_phase": "unknown_transport_timeout",
        "timeout_seconds": 1.0,
        "elapsed_ms": failure.value.elapsed_ms,
        "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
    }
    assert 900 <= failure.value.elapsed_ms <= 1600


class _FakeTimeout:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _FakeStreamResponse:
    def __init__(self, lines):
        self._lines = list(lines)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None

    def iter_lines(self):
        return iter(self._lines)


class _FakeHttpClient:
    calls: list[dict] = []
    lines: list[str] = []

    def __init__(self, *, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def stream(self, method, url, *, headers, json):
        self.calls.append(
            {
                "method": method,
                "url": url,
                "headers": dict(headers),
                "json": dict(json),
                "timeout": self.timeout,
            }
        )
        return _FakeStreamResponse(self.lines)


def _install_fake_httpx(monkeypatch, lines: list[str]) -> type[_FakeHttpClient]:
    class FakeClient(_FakeHttpClient):
        calls: list[dict] = []

    FakeClient.lines = list(lines)

    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=FakeClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return FakeClient


def test_openai_chat_stream_collector_returns_complete_json_and_marks_trace(monkeypatch) -> None:
    fake_client = _install_fake_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"content":"{\\"image_set_plan\\":"}}]}',
            'data: {"choices":[{"delta":{"content":" {\\"outputs\\": []}"}}]}',
            'data: {"choices":[{"delta":{"content":"}"}}]}',
            "data: [DONE]",
        ],
    )
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    try:
        text = _collect_openai_chat_completion_stream(
            url="https://brain.example/v1/chat/completions",
            api_key="redacted",
            payload={
                "model": "deepseek-v4-pro-260425",
                "messages": [],
                "response_format": {"type": "json_object"},
                "temperature": 0,
                "max_tokens": 8000,
                "stream": True,
            },
            timeout_seconds=120,
        )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(token)

    assert json.loads(text) == {"image_set_plan": {"outputs": []}}
    assert fake_client.calls
    sent = fake_client.calls[0]["json"]
    assert sent["stream"] is True
    assert sent["response_format"] == {"type": "json_object"}
    assert "timeout" not in sent
    assert trace["response_started"] is True
    assert trace["first_content_observed"] is True
    assert trace["complete_response_observed"] is True


def test_openai_chat_stream_collector_rejects_incomplete_stream(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        ['data: {"choices":[{"delta":{"content":"{\\"image_set_plan\\":{}"}}]}'],
    )

    with pytest.raises(BrainInvalidJsonResponse, match="complete JSON response marker"):
        _collect_openai_chat_completion_stream(
            url="https://brain.example/v1/chat/completions",
            api_key="redacted",
            payload={"stream": True},
            timeout_seconds=120,
        )


def test_openai_chat_stream_collector_rejects_output_limit(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        ['data: {"choices":[{"delta":{},"finish_reason":"length"}]}'],
    )

    with pytest.raises(BrainOutputTruncated, match="output-token limit"):
        _collect_openai_chat_completion_stream(
            url="https://brain.example/v1/chat/completions",
            api_key="redacted",
            payload={"stream": True},
            timeout_seconds=120,
        )
