"""Offline controller diagnostics: attempts are not subprocess/HTTP receipts."""
from dataclasses import replace
from unittest.mock import Mock
import pytest
from app.services import claude_orchestrator as orchestrator
from app.schemas import CaseRetrievalPlan, CreateCreativeRunRequest


@pytest.fixture
def controller(monkeypatch, tmp_path):
    monkeypatch.setattr(orchestrator, "settings", replace(orchestrator.settings,
        claude_orchestrator_enabled=True, claude_checkpoint_orchestrator_enabled=True))
    monkeypatch.setattr(orchestrator, "_read_cached_decision", lambda *_: None)
    monkeypatch.setattr(orchestrator, "_read_semantic_cached_decision", lambda *_: None)
    monkeypatch.setattr("app.services.runtime_model_settings.refresh_runtime_gateway_credentials", lambda: None)
    monkeypatch.setattr(orchestrator, "_resolve_claude_command", lambda: ["mock-never-executed"])
    monkeypatch.setattr(orchestrator, "_build_workspace", lambda **_: tmp_path)
    monkeypatch.setattr(orchestrator, "_build_checkpoint_stage_prompt", lambda *_, **__: "dummy")
    monkeypatch.setattr(orchestrator, "_claude_code_source_selection", lambda _: orchestrator.ClaudeSourceSelection(
        "claude-code", "mock-model", {}, "test"))
    forbidden = Mock(side_effect=AssertionError("External execution forbidden"))
    monkeypatch.setattr(orchestrator, "_run_claude_subprocess", forbidden)
    monkeypatch.setattr(orchestrator, "_invoke_openai_compatible_stage_json", forbidden)
    monkeypatch.setattr(orchestrator, "_write_cached_decision", Mock())
    monkeypatch.setattr(orchestrator, "_record_invocation", Mock())
    events = []
    def run():
        return orchestrator.orchestrate_creative_request(
            request=CreateCreativeRunRequest(user_prompt="dummy"), fallback_mode="smart_enhance",
            fallback_retrieval_plan=CaseRetrievalPlan(query_text="dummy"),
            candidate_cases=[], progress_callback=events.append)
    yield run, events, tmp_path
    forbidden.assert_not_called()


def test_nonretryable_stage_error_retains_attempt_and_failure(monkeypatch, controller):
    run, events, _ = controller
    invoke = Mock(side_effect=orchestrator.ClaudeInvocationError("llm_gateway_not_configured"))
    monkeypatch.setattr(orchestrator, "_invoke_claude_stage_json", invoke)
    decision = run()
    assert invoke.call_count == decision.attempts == 1
    assert decision.invocation_status == "checkpoint_fallback"
    assert decision.provider == "deterministic-fallback"
    assert decision.fallback_reason == "claude_checkpoint_error:llm_gateway_not_configured"
    assert [(t["stage"], t["status"], t["failure_code"]) for t in decision.claude_stage_trace] == [
        ("intent", "error", "llm_gateway_not_configured")]
    assert [(e["status"], e["attempt"]) for e in events] == [("running", 1), ("error", 1)]


@pytest.mark.parametrize("failure", [orchestrator.ClaudeInvocationError("llm_gateway_not_configured"), RuntimeError("mock-local-error")])
def test_completed_checkpoint_survives_later_exception(monkeypatch, controller, failure):
    run, events, workspace = controller
    invoke = Mock(side_effect=[{"stage": "intent"}, failure])
    monkeypatch.setattr(orchestrator, "_invoke_claude_stage_json", invoke)
    decision = run()
    assert invoke.call_count == decision.attempts == 2
    assert decision.invocation_status == "checkpoint_fallback"
    assert decision.provider == "deterministic-fallback"
    assert decision.fallback_reason.startswith("claude_checkpoint_error:")
    assert decision.claude_stage_trace[0]["stage"] == "intent"
    assert decision.claude_stage_trace[0]["status"] == "success"
    assert (workspace / "stage_01_intent_checkpoint.json").exists()
    assert len([e for e in events if e["status"] == "running"]) == 2
    if isinstance(failure, orchestrator.ClaudeInvocationError):
        assert decision.claude_stage_trace[-1]["failure_code"] == str(failure)


def test_missing_cli_remains_zero_without_execution(monkeypatch, controller):
    run, events, _ = controller
    monkeypatch.setattr(orchestrator, "_resolve_claude_command", lambda: None)
    invoke = Mock(side_effect=AssertionError("Stage must not run"))
    monkeypatch.setattr(orchestrator, "_invoke_claude_stage_json", invoke)
    decision = run()
    assert decision.attempts == 0
    assert decision.claude_stage_trace == events == []
    assert decision.invocation_status == "checkpoint_fallback"
    invoke.assert_not_called()


def test_success_keeps_existing_metadata_and_valid_decision(monkeypatch, controller):
    run, events, _ = controller
    invoke = Mock(side_effect=[{"stage": "intent"}, {"stage": "visual_strategy"}, {"stage": "decision"}])
    monkeypatch.setattr(orchestrator, "_invoke_claude_stage_json", invoke)
    monkeypatch.setattr(orchestrator, "_compress_checkpoint_decision", lambda *_, **__: {"valid": True})
    monkeypatch.setattr(orchestrator, "_normalize_decision", lambda _, **kw: kw["fallback"].model_copy(
        update={"provider": "claude-code", "fallback_reason": None}))
    decision = run()
    assert invoke.call_count == decision.attempts == 3
    assert decision.invocation_status == "checkpoint_success"
    assert decision.provider == "claude-code" and decision.fallback_reason is None
    assert [t["status"] for t in decision.claude_stage_trace] == ["success"] * 3
    assert len(events) == 6


def test_model_fallback_attempt_survives_unexpected_exception(monkeypatch, controller):
    run, events, _ = controller
    invoke = Mock(side_effect=[orchestrator.ClaudeInvocationError("claude_upstream_unavailable"), RuntimeError("mock-local-error")])
    monkeypatch.setattr(orchestrator, "_invoke_claude_stage_json", invoke)
    monkeypatch.setattr(orchestrator, "_should_try_claude_code_model_fallback", lambda *_, **__: True)
    monkeypatch.setattr(orchestrator, "_claude_code_model_fallback_queue", lambda **_: ["mock-fallback"])
    monkeypatch.setattr(orchestrator, "_claude_code_fallback_env_overrides", lambda: {})
    monkeypatch.setattr(orchestrator, "_fallback_protocol_for_model", lambda _: "anthropic")
    decision = run()
    assert invoke.call_count == decision.attempts == 2
    assert decision.invocation_status == "checkpoint_fallback"
    assert decision.claude_stage_trace[0]["failure_code"] == "claude_upstream_unavailable"
    assert any(e["stage"] == "intent_model_fallback_1" and e["status"] == "running" for e in events)
