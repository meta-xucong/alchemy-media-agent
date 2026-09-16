import json
import sys
import threading
import time
import types

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.contracts import (
    BRAIN_EXECUTION_BUDGET_HANDOFF_SECONDS,
    BrainRunRequest,
)
from alchemy_creative_agent_3_0.app.llm_brain.providers import (
    _ACTIVE_EXECUTION_BUDGET,
    _ACTIVE_TRANSPORT_TRACE,
    _BrainExecutionBudget,
    _call_with_timeout,
    _collect_openai_chat_completion_stream,
    _new_transport_trace,
    _transport_timeout_phase,
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
            "request_acceptance": "not_started",
            "response_started": False,
        "first_content_observed": False,
        "complete_response_observed": False,
        "json_parse_started": False,
        "json_parse_completed": False,
    }
    assert 900 <= failure.value.elapsed_ms <= 1600


def test_transport_timeout_phase_distinguishes_complete_response_and_json_parse() -> None:
    complete = _new_transport_trace(stage="plan", json_recovery=False)
    complete["complete_response_started"] = True
    assert _transport_timeout_phase(complete) == "complete_response_timeout"

    parsing = _new_transport_trace(stage="plan", json_recovery=False)
    parsing["json_parse_started"] = True
    assert _transport_timeout_phase(parsing) == "json_parse_timeout"


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


class _SemanticStallStreamResponse:
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
        yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":"}}]}'
        yield ""
        self.closed.wait(5.0)
        self.finished.set()


class _SemanticStallHttpClient:
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
        type(self).response = _SemanticStallStreamResponse()
        self.response = type(self).response
        return self.response


class _SemanticThenRoleNoiseStreamResponse:
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
        yield 'data: {"choices":[{"delta":{"content":"{\\"ok\\":"}}]}'
        yield ""
        for _ in range(20):
            if self.closed.is_set():
                self.finished.set()
                return
            yield 'data: {"choices":[{"delta":{"role":"assistant"}}]}'
            yield ""
            time.sleep(0.02)
        self.closed.wait(5.0)
        self.finished.set()


class _SemanticThenRoleNoiseHttpClient:
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
        type(self).response = _SemanticThenRoleNoiseStreamResponse()
        self.response = type(self).response
        return self.response


class _FastProgressingStreamResponse:
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
                time.sleep(0.04)


class _FastProgressingHttpClient:
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
        type(self).response = _FastProgressingStreamResponse()
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


def _install_semantic_stall_httpx(monkeypatch) -> type[_SemanticStallHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_SemanticStallHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _SemanticStallHttpClient


def _install_semantic_role_noise_httpx(monkeypatch) -> type[_SemanticThenRoleNoiseHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_SemanticThenRoleNoiseHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _SemanticThenRoleNoiseHttpClient


def _install_fast_progressing_httpx(monkeypatch) -> type[_FastProgressingHttpClient]:
    fake_httpx = types.SimpleNamespace(Timeout=_FakeTimeout, Client=_FastProgressingHttpClient)
    monkeypatch.setitem(sys.modules, "httpx", fake_httpx)
    return _FastProgressingHttpClient


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


def test_semantic_idle_watchdog_stops_after_first_content_inside_shared_deadline(monkeypatch) -> None:
    _install_semantic_stall_httpx(monkeypatch)
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.setattr(providers_module, "_stream_semantic_idle_timeout_seconds", lambda: 0.08)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    trace_token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    budget = _BrainExecutionBudget(total_seconds=0.35, started_at=time.perf_counter())
    budget_token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    started = time.perf_counter()
    try:
        with pytest.raises(BrainTransportTimeoutError) as failure:
            _call_with_timeout(
                lambda: _collect_openai_chat_completion_stream(
                    url="https://brain.example/v1/chat/completions",
                    api_key="redacted",
                    payload={"stream": True},
                    timeout_seconds=0.3,
                ),
                timeout_seconds=0.3,
                trace=trace,
            )
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(budget_token)
        _ACTIVE_TRANSPORT_TRACE.reset(trace_token)

    elapsed = time.perf_counter() - started
    assert 0.05 <= elapsed < 0.25
    assert trace["semantic_progress_event_count"] == 1
    assert trace["first_content_observed"] is True
    assert trace["semantic_idle_timeout_triggered"] is True
    assert trace["transport_cancel_requested"] is True
    assert trace["transport_worker_stopped"] is True
    assert failure.value.timeout_phase == "read_timeout"
    assert "semantic_idle_timeout_triggered" not in failure.value.safe_metadata()
    assert _SemanticStallHttpClient.response is not None
    assert _SemanticStallHttpClient.response.closed.is_set()
    assert _SemanticStallHttpClient.response.finished.wait(0.5)


def test_first_semantic_watchdog_stops_stream_without_any_semantic_delta(monkeypatch) -> None:
    _install_blocking_httpx(monkeypatch)
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.setattr(providers_module, "_stream_first_semantic_timeout_seconds", lambda: 0.08)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    trace_token = _ACTIVE_TRANSPORT_TRACE.set(trace)
    started = time.perf_counter()
    try:
        with pytest.raises(BrainTransportTimeoutError) as failure:
            _call_with_timeout(
                lambda: _collect_openai_chat_completion_stream(
                    url="https://brain.example/v1/chat/completions",
                    api_key="redacted",
                    payload={"stream": True},
                    timeout_seconds=0.5,
                ),
                timeout_seconds=0.5,
                trace=trace,
            )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(trace_token)

    elapsed = time.perf_counter() - started
    assert 0.05 <= elapsed < 0.25
    assert trace["response_started"] is True
    assert trace["semantic_progress_event_count"] == 0
    assert trace["first_content_observed"] is False
    assert trace["first_semantic_timeout_triggered"] is True
    assert trace["transport_cancel_requested"] is True
    assert trace["transport_worker_stopped"] is True
    assert failure.value.timeout_phase == "read_timeout"
    assert _BlockingHttpClient.response is not None
    assert _BlockingHttpClient.response.closed.is_set()
    assert _BlockingHttpClient.response.finished.wait(0.5)


def test_first_semantic_watchdog_is_stream_only(monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.setattr(providers_module, "_stream_first_semantic_timeout_seconds", lambda: 0.05)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    trace["response_kind"] = "complete"
    trace["response_started"] = True
    trace["response_started_at"] = time.perf_counter()

    result = _call_with_timeout(
        lambda: {"ok": True},
        timeout_seconds=0.2,
        trace=trace,
    )

    assert result == {"ok": True}
    assert trace["first_semantic_timeout_triggered"] is False


def test_semantic_idle_watchdog_does_not_kill_continuous_semantic_chunks(monkeypatch) -> None:
    _install_fast_progressing_httpx(monkeypatch)
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.setattr(providers_module, "_stream_semantic_idle_timeout_seconds", lambda: 0.08)
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    trace_token = _ACTIVE_TRANSPORT_TRACE.set(trace)
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
        _ACTIVE_TRANSPORT_TRACE.reset(trace_token)

    assert json.loads(result["text"]) == {"ok": True}
    assert trace["semantic_progress_event_count"] == 3
    assert trace["semantic_idle_timeout_triggered"] is False
    assert trace["transport_worker_stopped"] is True


def test_role_noise_after_content_does_not_reset_semantic_idle(monkeypatch) -> None:
    _install_semantic_role_noise_httpx(monkeypatch)
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.setattr(providers_module, "_stream_semantic_idle_timeout_seconds", lambda: 0.08)
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
                    timeout_seconds=0.5,
                ),
                timeout_seconds=0.5,
                trace=trace,
            )
    finally:
        _ACTIVE_TRANSPORT_TRACE.reset(trace_token)

    assert time.perf_counter() - started < 0.25
    assert trace["progress_event_count"] > trace["semantic_progress_event_count"]
    assert trace["semantic_progress_event_count"] == 1
    assert trace["semantic_idle_timeout_triggered"] is True
    assert trace["transport_worker_stopped"] is True
    assert _SemanticThenRoleNoiseHttpClient.response is not None
    assert _SemanticThenRoleNoiseHttpClient.response.finished.wait(0.5)


def test_semantic_idle_setting_defaults_to_grace_and_stays_bounded(monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.delenv("V3_LLM_BRAIN_STREAM_IDLE_TIMEOUT_SECONDS", raising=False)
    assert providers_module._stream_semantic_idle_timeout_seconds() == 30.0  # noqa: SLF001
    monkeypatch.setenv("V3_LLM_BRAIN_STREAM_IDLE_TIMEOUT_SECONDS", "45")
    assert providers_module._stream_semantic_idle_timeout_seconds() == 45.0  # noqa: SLF001
    monkeypatch.setenv("V3_LLM_BRAIN_STREAM_IDLE_TIMEOUT_SECONDS", "999")
    assert providers_module._stream_semantic_idle_timeout_seconds() == 45.0  # noqa: SLF001
    monkeypatch.setenv("V3_LLM_BRAIN_STREAM_IDLE_TIMEOUT_SECONDS", "nan")
    assert providers_module._stream_semantic_idle_timeout_seconds() == 30.0  # noqa: SLF001


def test_first_semantic_setting_defaults_and_stays_bounded(monkeypatch) -> None:
    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    monkeypatch.delenv("V3_LLM_BRAIN_STREAM_FIRST_SEMANTIC_TIMEOUT_SECONDS", raising=False)
    assert providers_module._stream_first_semantic_timeout_seconds() == 60.0  # noqa: SLF001
    monkeypatch.setenv("V3_LLM_BRAIN_STREAM_FIRST_SEMANTIC_TIMEOUT_SECONDS", "5")
    assert providers_module._stream_first_semantic_timeout_seconds() == 5.0  # noqa: SLF001
    monkeypatch.setenv("V3_LLM_BRAIN_STREAM_FIRST_SEMANTIC_TIMEOUT_SECONDS", "999")
    assert providers_module._stream_first_semantic_timeout_seconds() == 120.0  # noqa: SLF001
    monkeypatch.setenv("V3_LLM_BRAIN_STREAM_FIRST_SEMANTIC_TIMEOUT_SECONDS", "nan")
    assert providers_module._stream_first_semantic_timeout_seconds() == 60.0  # noqa: SLF001


def test_timeout_retry_requires_the_previous_transport_worker_to_stop() -> None:
    provider = object.__new__(V3LLMBrainProvider)
    provider.provider = "openai"
    provider.timeout = 0.1
    provider.max_tokens = 8_000
    release = threading.Event()
    finished = threading.Event()
    started = threading.Event()
    calls = 0

    def uncooperative_call(request: BrainRunRequest, *, json_recovery: bool = False):
        nonlocal calls
        calls += 1
        started.set()
        try:
            release.wait(0.5)
        finally:
            finished.set()
        raise BrainTransportTimeoutError(
            stage=request.stage,
            timeout_seconds=0.1,
            elapsed_ms=100,
            timeout_phase="read_timeout",
            response_started=True,
            first_content_observed=True,
        )

    provider._run_openai_compatible = uncooperative_call
    request = BrainRunRequest(
        user_input="Prepare one bounded Brain request.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {}},
    )
    budget = _BrainExecutionBudget(total_seconds=2.0, started_at=time.perf_counter())
    budget_token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    worker_finished = False
    try:
        with pytest.raises(BrainTransportTimeoutError):
            provider.run(request)
        assert started.is_set()
        assert calls == 1
    finally:
        release.set()
        worker_finished = finished.wait(0.5)
        _ACTIVE_EXECUTION_BUDGET.reset(budget_token)
    assert worker_finished is True


def test_stopped_timeout_gets_only_one_bounded_retry() -> None:
    provider = object.__new__(V3LLMBrainProvider)
    provider.provider = "openai"
    provider.timeout = 0.1
    provider.max_tokens = 8_000
    calls = 0

    def one_transient_timeout(request: BrainRunRequest, *, json_recovery: bool = False):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise BrainTransportTimeoutError(
                stage=request.stage,
                timeout_seconds=0.1,
                elapsed_ms=100,
                timeout_phase="read_timeout",
            )
        return {"ok": True}

    provider._run_openai_compatible = one_transient_timeout
    request = BrainRunRequest(
        user_input="Prepare one bounded Brain request.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {}},
    )
    budget = _BrainExecutionBudget(total_seconds=2.0, started_at=time.perf_counter())
    budget_token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        result = provider.run(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(budget_token)

    assert result["ok"] is True
    assert calls == 2
    assert result["_alchemy_brain_transport"]["transient_recovery_attempted"] is True


def test_brain_progress_grace_cannot_cross_logical_execution_budget() -> None:
    trace = _new_transport_trace(stage="plan", json_recovery=False)
    stop = threading.Event()
    finished = threading.Event()

    def continuously_progressing_call():
        try:
            while not stop.is_set():
                trace["semantic_progress_event_count"] += 1
                trace["last_semantic_progress_at"] = time.perf_counter()
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


def test_real_image_provider_run_preserves_timeout_when_retry_hits_handoff_window() -> None:
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
                response_started=True,
                first_content_observed=True,
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
        with pytest.raises(BrainTransportTimeoutError) as failure:
            provider.run(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)
    assert provider.calls == 1
    assert failure.value.response_started is True
    assert failure.value.first_content_observed is True
    assert isinstance(failure.value.__cause__, BrainExecutionBudgetExceeded)


def test_real_image_provider_run_keeps_budget_when_shared_deadline_is_exhausted() -> None:
    provider = object.__new__(V3LLMBrainProvider)
    provider.provider = "openai"
    provider.timeout = 0.1
    provider.max_tokens = 8_000
    provider.calls = 0

    def expires_shared_budget(request: BrainRunRequest, *, json_recovery: bool = False):
        provider.calls += 1
        budget = _ACTIVE_EXECUTION_BUDGET.get()
        assert budget is not None
        object.__setattr__(budget, "started_at", time.perf_counter() - 3.0)
        raise BrainTransportTimeoutError(
            stage=request.stage,
            timeout_seconds=0.1,
            elapsed_ms=100,
            timeout_phase="read_timeout",
            response_started=True,
            first_content_observed=True,
        )

    provider._run_openai_compatible = expires_shared_budget
    request = BrainRunRequest(
        user_input="Prepare one bounded Brain request.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"canonical_prompt_context": {}},
    )
    budget = _BrainExecutionBudget(total_seconds=2.0, started_at=time.perf_counter())
    token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        with pytest.raises(BrainExecutionBudgetExceeded) as failure:
            provider.run(request)
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)

    assert provider.calls == 1
    assert isinstance(failure.value.__cause__, BrainTransportTimeoutError)


@pytest.mark.parametrize("stage", ["plan", "generate"])
def test_real_image_pre_finalizer_progress_ceiling_is_handoff_bounded(monkeypatch, stage) -> None:
    """The outer worker deadline must receive the narrowed plan ceiling."""

    import alchemy_creative_agent_3_0.app.llm_brain.providers as providers_module

    provider = object.__new__(V3LLMBrainProvider)
    provider.timeout = 300.0
    request = BrainRunRequest(
        user_input="Prepare a real image.",
        stage=stage,
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"require_real_images": True},
    )
    budget = _BrainExecutionBudget(
        total_seconds=520.0,
        started_at=time.perf_counter() - 250.0,
    )
    captured: dict[str, float | None] = {}

    def fake_call(callable_obj, *, timeout_seconds, trace, maximum_deadline=None):  # noqa: ANN001
        captured["timeout_seconds"] = timeout_seconds
        captured["maximum_deadline"] = maximum_deadline
        return {"ok": True}

    monkeypatch.setattr(providers_module, "_call_with_timeout", fake_call)
    token = _ACTIVE_EXECUTION_BUDGET.set(budget)
    try:
        assert provider._run_remote_attempt(  # noqa: SLF001
            lambda _request, *, json_recovery: {"ignored": json_recovery},
            request,
            json_recovery=False,
        ) == {"ok": True}
    finally:
        _ACTIVE_EXECUTION_BUDGET.reset(token)

    assert captured["timeout_seconds"] is not None
    assert 15.0 <= float(captured["timeout_seconds"]) <= 25.0
    assert captured["maximum_deadline"] is not None
    expected_ceiling = budget.deadline - BRAIN_EXECUTION_BUDGET_HANDOFF_SECONDS
    assert abs(float(captured["maximum_deadline"]) - expected_ceiling) < 0.1


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


def test_openai_chat_stream_collector_flushes_multiline_sse_event_at_blank_line(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        [
            "data: {\"choices\":[",
            'data: {\"delta\":{\"content\":\"{\\\"ok\\\":true}\"}}]}',
            "",
            "data: [DONE]",
            "",
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


def test_openai_chat_stream_collector_accepts_unprefixed_done_marker(monkeypatch) -> None:
    _install_fake_httpx(
        monkeypatch,
        [
            '{"choices":[{"delta":{"content":"{\\"ok\\":true}"}}]}',
            "[DONE]",
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
