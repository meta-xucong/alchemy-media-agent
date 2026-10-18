from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.config import settings
from app.schemas import OrchestratorStatusResponse, V2RuntimeModelSettingsResponse
from app.schemas import V2RuntimeModelSettingsRequest
from app.services import runtime_model_settings
from app.services import claude_orchestrator


def test_v2_fallback_uses_selected_model_and_unified_gateway(monkeypatch) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(
            claude_orchestrator_model="claude-sonnet-5-5",
            claude_orchestrator_fallback_model=None,
            claude_orchestrator_fallback_models=("gpt-6.1-sol", "gpt-custom-backup"),
            llm_gateway_api_key="one-gateway-key",
            llm_gateway_base_url="https://gateway.test/v1",
        ),
    )

    assert claude_orchestrator._claude_code_model_fallback_queue() == ["kimi-k3", "gpt-custom-backup", "gpt-6.1-sol"]  # noqa: SLF001
    assert claude_orchestrator._claude_code_model_fallback_queue(exclude_model="gpt-6.1-sol") == ["kimi-k3", "gpt-custom-backup"]  # noqa: SLF001
    assert claude_orchestrator._is_openai_compatible_fallback_model("gpt-custom-backup")  # noqa: SLF001
    assert claude_orchestrator._is_openai_compatible_fallback_model("kimi-for-coding")  # noqa: SLF001
    assert not claude_orchestrator._is_openai_compatible_fallback_model("claude-sonnet-5-5")  # noqa: SLF001
    assert claude_orchestrator._fallback_protocol_for_model("claude-sonnet-5-5") == "anthropic"  # noqa: SLF001
    assert claude_orchestrator._fallback_protocol_for_model("custom-model") is None  # noqa: SLF001
    assert claude_orchestrator._claude_code_fallback_env_overrides() == {  # noqa: SLF001
        "OPENAI_BASE_URL": "https://gateway.test/v1",
        "OPENAI_API_KEY": "one-gateway-key",
    }
    assert claude_orchestrator._claude_cli_gateway_base_url("https://gateway.test/v1") == "https://gateway.test"  # noqa: SLF001


def test_v2_claude_primary_requires_unified_gateway_before_cli_dispatch(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(llm_gateway_api_key="one-gateway-key", llm_gateway_base_url=None),
    )

    def unexpected_dispatch(*_args, **_kwargs):
        raise AssertionError("Claude CLI must not dispatch without the unified gateway URL")

    monkeypatch.setattr(claude_orchestrator, "_run_claude_subprocess", unexpected_dispatch)
    with pytest.raises(claude_orchestrator.ClaudeInvocationError, match="llm_gateway_not_configured"):
        claude_orchestrator._invoke_claude_stage_json(
            command=["claude"],
            workspace=tmp_path,
            stage_name="gateway_guard",
            prompt="test",
            schema={"type": "object"},
        )


def test_v2_legacy_fallback_keeps_kimi_before_gpt_default(monkeypatch) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(
            claude_orchestrator_model="claude-sonnet-5-5",
            claude_orchestrator_fallback_model="gpt-4.1-legacy",
            claude_orchestrator_fallback_models=("gpt-6.1-sol",),
        ),
    )

    assert claude_orchestrator._claude_code_model_fallback_queue() == [  # noqa: SLF001
        "kimi-k3",
        "gpt-6.1-sol",
        "gpt-4.1-legacy",
    ]


def test_v2_falls_through_kimi_to_gpt_after_eligible_kimi_failure(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(
            claude_orchestrator_fallback_max_models_per_stage=3,
            claude_orchestrator_fallback_stage_timeout_seconds=30.0,
        ),
    )
    monkeypatch.setattr(claude_orchestrator, "_claude_code_source_selection", lambda _workspace: SimpleNamespace(model="claude-sonnet-5-5"))
    monkeypatch.setattr(claude_orchestrator, "_claude_code_model_fallback_queue", lambda **_kwargs: ["kimi-k3", "gpt-6.1-sol"])
    monkeypatch.setattr(claude_orchestrator, "_claude_code_fallback_env_overrides", lambda: {})
    calls: list[str] = []

    def invoke(*, model, **_kwargs):
        calls.append(model)
        if model == "kimi-k3":
            raise claude_orchestrator.ClaudeInvocationError("openai_fallback_http_retryable", status_code=503, retryable=True)
        return {"decision": "accepted"}

    monkeypatch.setattr(claude_orchestrator, "_invoke_openai_compatible_stage_json", invoke)
    result, meta = claude_orchestrator._invoke_claude_code_model_fallbacks(  # noqa: SLF001
        command=[], workspace=tmp_path, stage_name="test", prompt="x", schema={"type": "object"}
    )
    assert calls == ["kimi-k3", "gpt-6.1-sol"]
    assert result == {"decision": "accepted"}
    assert meta["model"] == "gpt-6.1-sol"


def test_v2_kimi_timeout_keeps_a_bounded_slice_for_gpt(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(
            claude_orchestrator_fallback_max_models_per_stage=2,
            claude_orchestrator_fallback_stage_timeout_seconds=30.0,
        ),
    )
    monkeypatch.setattr(claude_orchestrator, "_claude_code_source_selection", lambda _workspace: SimpleNamespace(model="claude-sonnet-5-5"))
    monkeypatch.setattr(claude_orchestrator, "_claude_code_model_fallback_queue", lambda **_kwargs: ["kimi-k3", "gpt-6.1-sol"])
    monkeypatch.setattr(claude_orchestrator, "_claude_code_fallback_env_overrides", lambda: {})
    calls: list[tuple[str, float]] = []
    fake_clock = [0.0]
    monkeypatch.setattr(claude_orchestrator.time, "perf_counter", lambda: fake_clock[0])

    def invoke(*, model, timeout_seconds, **_kwargs):
        calls.append((model, timeout_seconds))
        if model == "kimi-k3":
            fake_clock[0] += timeout_seconds
            raise claude_orchestrator.ClaudeInvocationError("openai_fallback_timeout", retryable=True)
        return {"decision": "accepted"}

    monkeypatch.setattr(claude_orchestrator, "_invoke_openai_compatible_stage_json", invoke)
    result, meta = claude_orchestrator._invoke_claude_code_model_fallbacks(  # noqa: SLF001
        command=[], workspace=tmp_path, stage_name="test", prompt="x", schema={"type": "object"}, deadline=30.0
    )
    assert [model for model, _timeout in calls] == ["kimi-k3", "gpt-6.1-sol"]
    assert all(timeout <= 15.0 for _model, timeout in calls)
    assert result == {"decision": "accepted"}
    assert meta["model"] == "gpt-6.1-sol"


def test_v2_status_reports_one_gateway_without_per_route_key_status() -> None:
    assert "llm_gateway_configured" in OrchestratorStatusResponse.model_fields
    assert "llm_gateway_api_key_configured" in V2RuntimeModelSettingsResponse.model_fields
    assert "llm_gateway_base_url" in V2RuntimeModelSettingsResponse.model_fields
    assert "fallback_auth_token_configured" not in OrchestratorStatusResponse.model_fields
    assert "claude_orchestrator_fallback_auth_token_configured" not in V2RuntimeModelSettingsResponse.model_fields
    assert "llm_gateway_api_key" in V2RuntimeModelSettingsRequest.model_fields


def test_v2_403_fallback_requires_structured_model_scope() -> None:
    assert claude_orchestrator._structured_model_scoped_denial('{"error":{"code":"model_access_denied","scope":"model"}}')  # noqa: SLF001
    assert not claude_orchestrator._structured_model_scoped_denial('403 model_access_denied')  # noqa: SLF001
    assert not claude_orchestrator._structured_model_scoped_denial('{"error":{"message":"model_access_denied"}}')  # noqa: SLF001


def test_v2_gpt_fallback_has_an_absolute_wall_clock_deadline(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(llm_gateway_api_key="one-gateway-key", llm_gateway_base_url="https://gateway.test/v1"),
    )

    class SlowClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            await asyncio.sleep(0.05)

    monkeypatch.setattr(claude_orchestrator.httpx, "AsyncClient", lambda **_kwargs: SlowClient())
    with pytest.raises(claude_orchestrator.ClaudeInvocationError, match="openai_fallback_timeout") as failure:
        claude_orchestrator._invoke_openai_compatible_stage_json(  # noqa: SLF001
            workspace=tmp_path,
            stage_name="deadline_test",
            prompt="small test prompt",
            schema={"type": "object"},
            model="gpt-6.1-sol",
            timeout_seconds=0.01,
        )
    assert failure.value.retryable is True


def test_v2_fallback_connection_errors_are_retryable() -> None:
    error = claude_orchestrator.ClaudeInvocationError("openai_fallback_connection_error", retryable=True)
    assert claude_orchestrator._is_openai_fallback_failure_retryable(error)  # noqa: SLF001


def test_v2_failure_categories_preserve_permission_and_refusal_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(
            claude_orchestrator_model="claude-sonnet-5-5",
            claude_orchestrator_fallback_models=("gpt-6.1-sol",),
            llm_gateway_api_key="one-gateway-key",
            llm_gateway_base_url="https://gateway.test/v1",
        ),
    )
    assert claude_orchestrator._should_try_claude_code_model_fallback("claude_timeout")  # noqa: SLF001
    assert claude_orchestrator._should_try_claude_code_model_fallback("claude_candidate_access_denied")  # noqa: SLF001
    assert not claude_orchestrator._should_try_claude_code_model_fallback("claude_policy_refusal")  # noqa: SLF001


@pytest.mark.parametrize(
    ("failure", "expected_calls"),
    [
        (claude_orchestrator.ClaudeInvocationError("openai_fallback_http_terminal", status_code=401, retryable=False), ["gpt-6.1-sol"]),
        (claude_orchestrator.ClaudeInvocationError("openai_fallback_http_retryable", status_code=503, retryable=True), ["gpt-6.1-sol", "gpt-custom-backup"]),
    ],
)
def test_v2_model_fallback_stops_on_terminal_status_and_continues_on_transient(
    monkeypatch, tmp_path, failure, expected_calls
) -> None:
    monkeypatch.setattr(
        claude_orchestrator,
        "settings",
        SimpleNamespace(claude_orchestrator_fallback_max_models_per_stage=2,
                        claude_orchestrator_fallback_stage_timeout_seconds=30.0),
    )
    monkeypatch.setattr(claude_orchestrator, "_claude_code_source_selection", lambda _workspace: SimpleNamespace(model="claude-sonnet-5-5"))
    monkeypatch.setattr(claude_orchestrator, "_claude_code_model_fallback_queue", lambda **_kwargs: ["gpt-6.1-sol", "gpt-custom-backup"])
    monkeypatch.setattr(claude_orchestrator, "_claude_code_fallback_env_overrides", lambda: {})
    calls = []

    def invoke(*, model, **_kwargs):
        calls.append(model)
        if len(calls) == 1:
            raise failure
        return {"checkpoint": True}

    monkeypatch.setattr(claude_orchestrator, "_invoke_openai_compatible_stage_json", invoke)
    result, _meta = claude_orchestrator._invoke_claude_code_model_fallbacks(  # noqa: SLF001
        command=[], workspace=tmp_path, stage_name="test", prompt="x", schema={"type": "object"}
    )
    assert calls == expected_calls
    assert bool(result) is (len(expected_calls) == 2)


@pytest.mark.parametrize(
    "payload",
    [
        {"choices": [{"finish_reason": "content_filter", "message": {"content": "{}"}}]},
        {"choices": [{"finish_reason": "stop", "message": {"refusal": "no", "content": "{}"}}]},
    ],
)
def test_v2_openai_response_refusal_is_explicit(payload) -> None:
    assert claude_orchestrator._openai_chat_policy_refusal(payload)  # noqa: SLF001


def test_v2_runtime_gateway_key_is_write_only_and_persisted_outside_json(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(
        runtime_model_settings,
        "settings",
        SimpleNamespace(llm_gateway_api_key=None, llm_gateway_base_url="https://gateway.test/v1", data_dir=tmp_path),
    )
    monkeypatch.setattr(runtime_model_settings, "get_runtime_model_settings", lambda: SimpleNamespace(llm_gateway_api_key_configured=True))
    response = runtime_model_settings.update_runtime_model_settings(
        V2RuntimeModelSettingsRequest(llm_gateway_api_key="one-shared-key")
    )
    assert response.llm_gateway_api_key_configured is True
    assert not hasattr(response, "llm_gateway_api_key")
    env_text = (tmp_path / "llm_gateway.env").read_text(encoding="utf-8")
    assert "LLM_GATEWAY_API_KEY=one-shared-key" in env_text
    object.__setattr__(runtime_model_settings.settings, "llm_gateway_api_key", "stale-worker-key")
    runtime_model_settings.refresh_runtime_gateway_credentials()
    assert runtime_model_settings.settings.llm_gateway_api_key == "one-shared-key"
    assert runtime_model_settings.settings.llm_gateway_base_url == "https://gateway.test/v1"
    persisted = runtime_model_settings.runtime_model_settings_path()
    if persisted.exists():
        assert "one-shared-key" not in persisted.read_text(encoding="utf-8")
