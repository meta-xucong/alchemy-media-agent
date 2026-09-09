import json
import sys
import threading
import time
import types

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.contracts import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    _ACTIVE_EXECUTION_BUDGET,
    _ACTIVE_TRANSPORT_TRACE,
    _BrainExecutionBudget,
    _call_with_timeout,
    _collect_openai_chat_completion_stream,
    _new_transport_trace,
    BrainExecutionBudgetExceeded,
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


class _BlockingStreamResponse:
    def __init__(self):
        self.closed = threading.Event()
        self.finished = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed.set()

    def raise_for_status(self):
        return None

    def iter_lines(self):
        self.closed.wait(5.0)
        self.finished.set()
        raise RuntimeError("test stream closed")


class _BlockingHttpClient:
    response = None

    def __init__(self, *, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self.response is not None:
            self.response.close()

    def stream(self, method, url, *, headers, json):
        type(self).response = _BlockingStreamResponse()
        self.response = type(self).response
        return self.response


class _ProgressingStreamResponse:
    def __init__(self):
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed = True

    def raise_for_status(self):
        return None

    def iter_lines(self):
        lines = [
            'data: {"choices":[{"delta":{"content":"{\\"ok\\":"}}]}',
            'data: {"choices":[{"delta":{"content":"true"}}]}',
            'data: {"choices":[{"delta":{"content":"}"}}]}',
            "data: [DONE]",
        ]
        for index, line in enumerate(lines):
            yield line
            if index < len(lines) - 1:
                time.sleep(0.12)


class _ProgressingHttpClient:
    response = None

    def __init__(self, *, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self.response is not None:
            self.response.close()

    def stream(self, method, url, *, headers, json):
        type(self).response = _ProgressingStreamResponse()
        self.response = type(self).response
        return self.response


class _DelayedReasoningStreamResponse:
    def __init__(self):
        self.closed = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed.set()

    def raise_for_status(self):
        return None

    def iter_lines(self):
        lines = [
            'data: {"choices":[{"delta":{"reasoning_content":[{"text":"first"}]}}]}',
            'data: {"choices":[{"delta":{"reasoning_content":" second"}}]}',
            'data: {"choices":[{"delta":{"content":[{"text":"{\\"ok\\":true}"}]}}]}',
            "data: [DONE]",
        ]
        for index, line in enumerate(lines):
            if self.closed.is_set():
                return
            yield line
            if index < len(lines) - 1:
                time.sleep(0.08)


class _DelayedReasoningHttpClient:
    response = None

    def __init__(self, *, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self.response is not None:
            self.response.close()

    def stream(self, method, url, *, headers, json):
        type(self).response = _DelayedReasoningStreamResponse()
        self.response = type(self).response
        return self.response


class _NoiseBlockingStreamResponse:
    def __init__(self):
        self.closed = threading.Event()
        self.finished = threading.Event()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        self.closed.set()

    def raise_for_status(self):
        return None

    def iter_lines(self):
        for _ in range(20):
            if self.closed.is_set():
                self.finished.set()
                return
            yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}'
            time.sleep(0.02)
        self.closed.wait(5.0)
        self.finished.set()


class _NoiseBlockingHttpClient:
    response = None

    def __init__(self, *, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        if self.response is not None:
            self.response.close()

    def stream(self, method, url, *, headers, json):
        type(self).response = _NoiseBlockingStreamResponse()
        self.response = type(self).response
        return self.response


class _FakeHttpxReadTimeout(RuntimeError):
    __module__ = "httpx"


class _TimeoutStreamResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        return None

    def raise_for_status(self):
        return None

    def iter_lines(self):
        raise _FakeHttpxReadTimeout("read timed out")


class _TimeoutHttpClient:
    def __init__(self, *, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        return None

    def stream(self, method, url, *, headers, json):
        return _TimeoutStreamResponse()


def _install_fake_httpx(monkeypatch, lines: list[str]) -> type[_FakeHttpClient]:
    class FakeClient(_FakeHttpClient):
        calls: list[dict] = []

    FakeClient.lines = list(lines)

    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=FakeClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return FakeClient


def _install_blocking_httpx(monkeypatch) -> type[_BlockingHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_BlockingHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _BlockingHttpClient


def _install_progressing_httpx(monkeypatch) -> type[_ProgressingHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_ProgressingHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _ProgressingHttpClient


def _install_delayed_reasoning_httpx(monkeypatch) -> type[_DelayedReasoningHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_DelayedReasoningHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _DelayedReasoningHttpClient


def _install_noise_blocking_httpx(monkeypatch) -> type[_NoiseBlockingHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_NoiseBlockingHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _NoiseBlockingHttpClient


def _install_timeout_httpx(monkeypatch) -> type[_TimeoutHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_TimeoutHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _TimeoutHttpClient


def test_brain_timeout_closes_stream_and_stops_transport_worker(monkeypatch) -> None:
    _install_blocking_httpx(monkeypatch)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    started = time.perf_counter()
    try:
        with pytest.raises(BrainTransportTimeoutError, match="timed out"):
            _call_with_timeout(
                lambda: _collect_openai_chat_completion_stream(
                    url="https://brain.example/v1/chat/completions",
                    api_key="redacted",
                    payload={"stream": True},
                    timeout_seconds=0.2,
                ),
                timeout_seconds=0.2,
                trace=trace,
            )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(token)

    assert time.perf_counter() - started < 1.5
    response = _BlockingHttpClient.response
    assert response is not None
    assert response.closed.is_set()
    assert response.finished.wait(0.5)
    assert trace["transport_cancel_requested"] is True
    assert trace["transport_worker_stopped"] is True


def test_brain_timeout_allows_active_stream_progress_with_bounded_grace(monkeypatch) -> None:
    _install_progressing_httpx(monkeypatch)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    token = _ACTIVE_TRANSPORT_TRACE.set(trace)

    try:
        result = _call_with_timeout(
            lambda: {"text": _collect_openai_chat_completion_stream(
                url="https://brain.example/v1/chat/completions",
                api_key="redacted",
                payload={"stream": True},
                timeout_seconds=0.3,
            )},
            timeout_seconds=0.3,
            trace=trace,
        )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(token)

    assert json.loads(result["text"]) == {"ok": True}
    assert trace["progress_event_count"] == 4
    assert trace["semantic_progress_event_count"] == 3


def test_brain_timeout_allows_delayed_reasoning_until_content_within_budget(monkeypatch) -> None:
    _install_delayed_reasoning_httpx(monkeypatch)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    trace_token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    budget = _BrainExecutionBudget(total_seconds=0.5, started_at=time.perf_counter())
    budget_token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        result = _call_with_timeout(
            lambda: {"text": _collect_openai_chat_completion_stream(
                url="https://brain.example/v1/chat/completions",
                api_key="redacted",
                payload={"stream": True},
                timeout_seconds=0.1,
            )},
            timeout_seconds=0.1,
            trace=trace,
        )
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(budget_token)
        _ACTIVE_TRANSPORT_TRACE.reset(trace_token)

    assert json.loads(result["text"]) == {"ok": True}
    assert trace["reasoning_content_observed"] is True
    assert trace["reasoning_chunk_count"] == 2
    assert trace["first_content_observed"] is True
    assert trace["semantic_progress_event_count"] == 3


def test_transport_noise_does_not_extend_semantic_progress_grace(monkeypatch) -> None:
    _install_noise_blocking_httpx(monkeypatch)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    trace_token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    started = time.perf_counter()
    try:
        with pytest.raises(BrainTransportTimeoutError):
            _call_with_timeout(
                lambda: _collect_openai_chat_completion_stream(
                    url="https://brain.example/v1/chat/completions",
                    api_key="redacted",
                    payload={"stream": True},
                    timeout_seconds=0.1,
                ),
                timeout_seconds=0.1,
                trace=trace,
            )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(trace_token)

    assert time.perf_counter() - started < 0.3
    assert trace["progress_event_count"] > 0
    assert trace["semantic_progress_event_count"] == 0
    assert trace["first_content_observed"] is False
    assert _NoiseBlockingHttpClient.response is not None
    assert _NoiseBlockingHttpClient.response.finished.wait(0.5)


def test_brain_progress_grace_cannot_cross_logical_execution_budget() -> None:
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    stop = threading.Event()
    finished = threading.Event()

    def continuously_progressing_call():
        try:
            while not stop.is_set():
                trace["semantic_progress_event_count"] += 1
                time.sleep(0.02)
        finally:
            finished.set()
        return {"ok": True}

    budget_start = time.perf_counter()
    budget = _BrainExecutionBudget(total_seconds=0.35, started_at=budget_start)
    budget_token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    started = time.perf_counter()
    try:
        with pytest.raises(BrainTransportTimeoutError):
            _call_with_timeout(
                continuously_progressing_call,
                timeout_seconds=0.15,
                trace=trace,
            )
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(budget_token)
        stop.set()

    assert finished.wait(0.5)
    elapsed = time.perf_counter() - started
    assert 0.28 <= elapsed < 0.8


def test_real_image_plan_retry_preserves_canonical_finalizer_handoff_window() -> None:
    provider = object.__new__(V3LLMBrainProvider)
    provider.timeout = 300.0
    request = BrainRunRequest(
        user_input="Prepare a real image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"require_real_images": True},
    )
    # Model a plan attempt that has already consumed 250 seconds of the
    # default 520-second logical preparation budget.  The remaining timeout
    # must exclude the existing 220-second finalizer handoff window.
    budget = _BrainExecutionBudget(total_seconds=520.0, started_at=time.perf_counter() - 250.0)
    token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        timeout = provider._effective_timeout_seconds(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)
    # The 30-second progress grace is part of the plan's stage window, so
    # the returned hard timeout must leave both grace and the 220-second
    # canonical finalizer handoff untouched.
    assert 15.0 <= timeout <= 25.0

    exhausted_budget = _BrainExecutionBudget(total_seconds=520.0, started_at=time.perf_counter() - 291.0)
    token = _ACTIVE_EXECUTION_BUDGET.set(exhausted_budget)
    try:
        with pytest.raises(BrainExecutionBudgetExceeded, match="handoff window"):
            provider._effective_timeout_seconds(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)


def test_real_image_provider_run_does_not_retry_after_plan_budget_reaches_handoff_window() -> None:
    provider = object.__new__(V3LLMBrainProvider)
    provider.provider = "openai"
    provider.timeout = 300.0
    provider.max_tokens = 12000
    provider.calls = 0

    def fake_openai_call(request: BrainRunRequest, *, json_recovery: bool = False):
        provider.calls += 1
        assert not json_recovery
        if provider.calls == 1:
            budget = _ACTIVE_EXECUTION_BUDGET.get()
            assert budget is not None
            # Model a single transient plan timeout consuming the available
            # plan window without sleeping in the regression test.
            object.__setattr__(budget, "started_at", time.perf_counter() - 301.0)
            raise BrainTransportTimeoutError(
                stage=request.stage,
                timeout_seconds=20.0,
                elapsed_ms=20_000,
                timeout_phase="read_timeout",
            )
        return {"image_set_plan": {"image_count": 1, "shot_plan": ["complete"]}}

    provider._run_openai_compatible = fake_openai_call
    request = BrainRunRequest(
        user_input="Prepare a real image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"require_real_images": True},
    )
    budget = _BrainExecutionBudget(total_seconds=520.0, started_at=time.perf_counter())
    token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        with pytest.raises(BrainExecutionBudgetExceeded, match="handoff window"):
            provider.run(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)
    assert provider.calls == 1


def test_finalizer_receives_the_remaining_budget_without_plan_reservation() -> None:
    provider = object.__new__(V3LLMBrainProvider)
    provider.timeout = 300.0
    request = BrainRunRequest(
        user_input="Sign the final renderer prompt.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {}},
    )
    budget = _BrainExecutionBudget(total_seconds=520.0, started_at=time.perf_counter() - 250.0)
    token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        timeout = provider._effective_timeout_seconds(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)
    assert 265.0 <= timeout <= 275.0


def test_openai_chat_transport_timeout_is_normalized(monkeypatch) -> None:
    _install_timeout_httpx(monkeypatch)
    provider = object.__new__(V3LLMBrainProvider)
    provider.model = "test-brain"
    provider.timeout = 1.0
    provider.max_tokens = 8_000
    request = BrainRunRequest(
        user_input="Prepare a bounded Brain request.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {}},
    )
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    try:
        with pytest.raises(BrainTransportTimeoutError) as failure:
            provider._run_openai_chat_completions(
                api_key="redacted",
                base_url="https://brain.example",
                request=request,
            )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(token)

    assert failure.value.timeout_phase == "read_timeout"
    assert failure.value.safe_metadata()["transport_error_class"] == "timeout"


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


def test_openai_chat_stream_collector_keeps_reasoning_out_of_final_json(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"role":"assistant"}}]}',
            'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"}}]}',
            'data: {"choices":[{"delta":{"reasoning_content":" continues"}}]}',
            'data: {"choices":[{"delta":{"content":"{\\"ok\\":true}"}}]}',
            "data: [DONE]",
        ],
    )
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    try:
        text = _collect_openai_chat_completion_stream(
            url="https://brain.example/v1/chat/completions",
            api_key="redacted",
            payload={"stream": True},
            timeout_seconds=120,
        )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(token)

    assert json.loads(text) == {"ok": True}
    assert trace["reasoning_content_observed"] is True
    assert trace["reasoning_chunk_count"] == 2
    assert trace["first_content_observed"] is True
    assert trace["complete_response_observed"] is True


def test_openai_chat_stream_reasoning_only_never_marks_content(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        [
            'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"}}]}',
            "data: [DONE]",
        ],
    )
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    try:
        text = _collect_openai_chat_completion_stream(
            url="https://brain.example/v1/chat/completions",
            api_key="redacted",
            payload={"stream": True},
            timeout_seconds=120,
        )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(token)

    assert text == ""
    assert trace["reasoning_content_observed"] is True
    assert trace["first_content_observed"] is False
    assert trace["complete_response_observed"] is True


def test_openai_chat_stream_collector_rejects_incomplete_stream(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        ['data: {"choices":[{"delta":{"content":"{\\"image_set_plan\\":{}"}}]}'],
    )

    with pytest.raises(BrainInvalidJsonResponse, match="complete JSON response marker") as failure:
        _collect_openai_chat_completion_stream(
            url="https://brain.example/v1/chat/completions",
            api_key="redacted",
            payload={"stream": True},
            timeout_seconds=120,
        )
    assert failure.value.safe_metadata()["json_failure_kind"] == "missing_complete_marker"
    assert failure.value.safe_metadata()["json_parse_started"] is False
    assert failure.value.safe_metadata()["json_parse_completed"] is False


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
