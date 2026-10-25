"""Offline failover authority, ownership fencing, and progress projection."""
import asyncio
from contextvars import ContextVar
from dataclasses import replace
from unittest.mock import AsyncMock, Mock

import pytest

from app.agents.runtime import _claude_progress_summary
from app.config import DEFAULT_CLAUDE_CODE_FALLBACK_MODELS
from app.schemas import CaseRetrievalPlan, CreateCreativeRunRequest
from app.services import claude_orchestrator as c, task_queue


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setattr(c, "settings", replace(c.settings,
        claude_orchestrator_enabled=True, claude_orchestrator_model="primary",
        claude_orchestrator_fallback_model=None,
        claude_orchestrator_fallback_models=("custom-backup",),
        llm_gateway_api_key="offline-dummy", llm_gateway_base_url="https://invalid.test",
        claude_orchestrator_fallback_stage_timeout_seconds=90,
        claude_orchestrator_fallback_max_models_per_stage=3))
    monkeypatch.setattr(c, "_claude_code_source_selection", lambda _: c.ClaudeSourceSelection(
        "claude-code", "primary", {}, "offline"))


@pytest.mark.parametrize("models,legacy,expected", [
    (("custom-backup",), None, ["custom-backup"]),
    ((), None, []),
    (("gpt-6.1-sol", "kimi-k3"), None, ["gpt-6.1-sol", "kimi-k3"]),
    (("primary", " custom ", "custom", ""), "legacy", ["custom", "legacy"]),
    ((), "kimi-k3", ["kimi-k3"]),
    (DEFAULT_CLAUDE_CODE_FALLBACK_MODELS, None, list(DEFAULT_CLAUDE_CODE_FALLBACK_MODELS)),
])
def test_queue_respects_configured_order_and_empty(monkeypatch, configured, models, legacy, expected):
    monkeypatch.setattr(c, "settings", replace(c.settings,
        claude_orchestrator_fallback_models=models, claude_orchestrator_fallback_model=legacy))
    assert c._claude_code_model_fallback_queue() == expected


def test_observer_claim_loss_prevents_next_stage_invocation(monkeypatch, configured, tmp_path):
    stale = task_queue.StaleTaskClaim("revoked")
    observer = Mock(side_effect=stale)
    invoke = Mock(side_effect=AssertionError("Must not invoke after claim loss"))
    monkeypatch.setattr(c, "_invoke_claude_stage_json", invoke)
    with pytest.raises(task_queue.StaleTaskClaim) as caught:
        c._invoke_checkpoint_stage_with_micro(command=["never"], workspace=tmp_path,
            stage_name="intent", schema={}, prompt="dummy", micro_prompt="dummy",
            trace=[], progress_callback=observer)
    assert caught.value is stale
    invoke.assert_not_called()


def test_ordinary_observer_error_is_still_best_effort():
    c._emit_claude_progress(Mock(side_effect=RuntimeError("observer unavailable")), stage="intent")


@pytest.mark.parametrize("checkpoint", [True, False])
def test_orchestrator_propagates_claim_loss_without_retry(monkeypatch, configured, checkpoint):
    monkeypatch.setattr(c, "settings", replace(c.settings, claude_checkpoint_orchestrator_enabled=checkpoint))
    monkeypatch.setattr("app.services.runtime_model_settings.refresh_runtime_gateway_credentials", lambda: None)
    monkeypatch.setattr(c, "_read_cached_decision", lambda *_: None)
    monkeypatch.setattr(c, "_read_semantic_cached_decision", lambda *_: None)
    stale = task_queue.StaleTaskClaim("revoked")
    invoke = Mock(side_effect=stale)
    monkeypatch.setattr(c, "_invoke_claude_checkpoint_mode" if checkpoint else "_invoke_claude_file_mode_compat", invoke)
    with pytest.raises(task_queue.StaleTaskClaim) as caught:
        c.orchestrate_creative_request(request=CreateCreativeRunRequest(user_prompt="dummy"),
            fallback_mode="smart_enhance", fallback_retrieval_plan=CaseRetrievalPlan(query_text="dummy"), candidate_cases=[])
    assert caught.value is stale
    assert invoke.call_count == 1


def test_subprocess_boundary_checks_claim_without_observer(monkeypatch, tmp_path):
    stale = task_queue.StaleTaskClaim("revoked")
    monkeypatch.setattr(task_queue, "ensure_current_claim", Mock(side_effect=stale))
    popen = Mock(side_effect=AssertionError("Must not spawn"))
    monkeypatch.setattr(c.subprocess, "Popen", popen)
    with pytest.raises(task_queue.StaleTaskClaim) as caught:
        c._run_claude_subprocess(["never"], input_text="dummy", timeout_seconds=10, cwd=tmp_path, env={})
    assert caught.value is stale
    popen.assert_not_called()


@pytest.mark.parametrize("running_loop", [False, True])
def test_openai_boundary_preserves_claim_context_and_stops_post(monkeypatch, configured, tmp_path, running_loop):
    marker = ContextVar("test_claim_marker", default=None)
    token = marker.set("owned")
    stale = task_queue.StaleTaskClaim("revoked")
    checked = []
    def fence():
        checked.append(marker.get())
        assert marker.get() == "owned", "Worker thread must retain caller ContextVars"
        raise stale
    monkeypatch.setattr(task_queue, "ensure_current_claim", fence)
    post = AsyncMock(side_effect=AssertionError("Must not send HTTP"))
    class OfflineClient:
        def __init__(self, **_):
            self.post = post
        async def __aenter__(self):
            return self
        async def __aexit__(self, *_):
            return False
    monkeypatch.setattr(c.httpx, "AsyncClient", OfflineClient)
    def invoke():
        return c._invoke_openai_compatible_stage_json(workspace=tmp_path, stage_name="intent",
            prompt="dummy", schema={}, model="gpt-custom")
    async def in_loop():
        return invoke()
    try:
        with pytest.raises(task_queue.StaleTaskClaim) as caught:
            asyncio.run(in_loop()) if running_loop else invoke()
        assert caught.value is stale
        assert checked == ["owned"]
        post.assert_not_called()
    finally:
        marker.reset(token)


def test_summary_counts_leaf_starts_not_group_or_duplicate_events():
    events = [
        dict(stage="intent_model_fallback", provider="claude-code-model-fallback", status="running", models=["one"]),
        dict(stage="intent_model_fallback_1", provider="claude-code-model-fallback", model="one", attempt=1, status="running"),
        dict(stage="intent_model_fallback_1", provider="claude-code-model-fallback", model="one", attempt=1, status="success", duration_ms=10),
        dict(stage="intent_model_fallback", provider="claude-code-model-fallback", model="one", attempt=2, status="success", duration_ms=10),
    ]
    retry = [dict(stage="visual_strategy_micro_retry_1", provider="claude-code", model="primary", attempt=2, status=status, duration_ms=20) for status in ("running", "success")]
    summary = _claude_progress_summary(events + events + retry + retry)
    assert summary["fallback_count"] == 1
    assert summary["retry_count"] == 1
    assert summary["finished_stage_count"] == 2
    assert summary["elapsed_ms"] == 30


def test_policy_refusal_is_neutral_and_never_falls_back(configured):
    label = c._claude_failure_label("claude_policy_refusal")
    assert "误拒" not in label and "备用" not in label
    assert not c._should_try_claude_code_model_fallback("claude_policy_refusal")
    assert not c._should_try_claude_code_model_fallback("claude_policy_refusal", after_compression_retries=True)


@pytest.mark.parametrize("parent_budget,expected", [(180, 90), (60, 60)])
def test_fallback_candidates_share_one_relay_budget(monkeypatch, configured, tmp_path, parent_budget, expected):
    monkeypatch.setattr(c, "settings", replace(c.settings, claude_orchestrator_fallback_models=("gpt-a", "gpt-b", "gpt-c")))
    clock = [100.0]
    timeouts = []
    monkeypatch.setattr(c.time, "perf_counter", lambda: clock[0])
    def timeout(**kwargs):
        timeouts.append(kwargs["timeout_seconds"])
        clock[0] += kwargs["timeout_seconds"]
        raise c.ClaudeInvocationError("openai_fallback_timeout", retryable=True)
    monkeypatch.setattr(c, "_invoke_openai_compatible_stage_json", timeout)
    result, meta = c._invoke_claude_code_model_fallbacks(command=["never"], workspace=tmp_path,
        stage_name="intent", prompt="dummy", schema={}, deadline=clock[0] + parent_budget)
    assert result is None and meta["attempts"] == 3
    assert timeouts == pytest.approx([expected / 3] * 3)
    assert clock[0] - 100 == pytest.approx(expected)


@pytest.mark.parametrize("cleanup_succeeds", [True, False])
def test_subprocess_timeout_cleanup_is_bounded(monkeypatch, tmp_path, cleanup_succeeds):
    expired = c.subprocess.TimeoutExpired(["never"], 10)
    process = Mock()
    process.communicate.side_effect = [expired, expired, ("partial", "")] if cleanup_succeeds else [expired] * 3
    monkeypatch.setattr(c.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(c, "_terminate_process_tree", Mock())
    monkeypatch.setattr(task_queue, "ensure_current_claim", lambda: None)
    error_type = c.subprocess.TimeoutExpired if cleanup_succeeds else c.ClaudeInvocationError
    with pytest.raises(error_type) as caught:
        c._run_claude_subprocess(["never"], input_text="dummy", timeout_seconds=10, cwd=tmp_path, env={})
    assert [call.kwargs["timeout"] for call in process.communicate.call_args_list] == [10, 5, 5]
    if not cleanup_succeeds:
        assert str(caught.value) == "claude_process_cleanup_unconfirmed"
        assert caught.value.retryable is False
        assert not c._should_try_claude_code_model_fallback(str(caught.value))
        assert str(caught.value) in c._NON_RETRYABLE_CLAUDE_FAILURES


def test_subprocess_normal_completion_unchanged(monkeypatch, tmp_path):
    process = Mock(returncode=0)
    process.communicate.return_value = ("ok", "")
    monkeypatch.setattr(c.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(task_queue, "ensure_current_claim", lambda: None)
    result = c._run_claude_subprocess(["never"], input_text="dummy", timeout_seconds=180, cwd=tmp_path, env={})
    assert result.stdout == "ok" and result.returncode == 0
    process.communicate.assert_called_once_with(input="dummy", timeout=180)
    process.kill.assert_not_called()


def test_unconfirmed_cleanup_stops_checkpoint_before_relay(monkeypatch, configured, tmp_path):
    invoke = Mock(side_effect=c.ClaudeInvocationError("claude_process_cleanup_unconfirmed", retryable=False))
    backup = Mock(side_effect=AssertionError("Must not relay"))
    monkeypatch.setattr(c, "_invoke_claude_stage_json", invoke)
    monkeypatch.setattr(c, "_invoke_claude_code_model_fallbacks", backup)
    with pytest.raises(c.ClaudeInvocationError, match="claude_process_cleanup_unconfirmed"):
        c._invoke_checkpoint_stage_with_micro(command=["never"], workspace=tmp_path,
            stage_name="intent", schema={}, prompt="dummy", micro_prompt="micro", trace=[])
    assert invoke.call_count == 1
    backup.assert_not_called()


def test_summary_distinguishes_repeated_relay_starts_with_same_stage_name():
    first = dict(stage="intent_model_fallback_1", provider="claude-code-model-fallback",
        model="backup", attempt=1, status="running", created_at="2026-10-25T00:00:01+00:00")
    second = {**first, "created_at": "2026-10-25T00:00:02+00:00"}
    assert _claude_progress_summary([first, first, second, second])["fallback_count"] == 2


@pytest.mark.parametrize("failure,protocol", [
    ("claude_process_cleanup_unconfirmed", "anthropic"),
    ("openai_fallback_policy_refusal", "openai"),
    ("openai_fallback_http_terminal", "openai"),
])
def test_terminal_backup_failure_does_not_restart_primary(monkeypatch, configured, tmp_path, failure, protocol):
    primary = Mock(side_effect=c.ClaudeInvocationError("claude_connection_error"))
    backup = Mock(side_effect=c.ClaudeInvocationError(failure, retryable=False))
    def claude(**kwargs):
        return backup(**kwargs) if kwargs.get("model_override") else primary(**kwargs)
    monkeypatch.setattr(c, "_invoke_claude_stage_json", claude)
    monkeypatch.setattr(c, "_invoke_openai_compatible_stage_json", backup)
    monkeypatch.setattr(c, "_fallback_protocol_for_model", lambda _: protocol)
    with pytest.raises(c.ClaudeInvocationError, match=failure):
        c._invoke_checkpoint_stage_with_micro(command=["never"], workspace=tmp_path,
            stage_name="intent", schema={}, prompt="dummy", micro_prompt="micro", ultra_micro_prompt="ultra", trace=[])
    assert primary.call_count == backup.call_count == 1
