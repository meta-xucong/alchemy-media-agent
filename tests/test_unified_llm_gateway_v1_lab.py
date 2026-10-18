from __future__ import annotations

import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.config import settings
from app.schemas import ImagePromptPlan, RuntimeProviderSettingsRequest, RuntimeProviderSettingsResponse
from app.services import alchemy_lab_llm, work_intensity
from app.services import image_service


@pytest.fixture(autouse=True)
def _configured_unified_gateway_url(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_base_url", "https://gateway.test/v1")


def test_v1_and_lab_text_candidates_share_one_unified_key(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "default_llm_model", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "backup_llm_model", "gpt-6.1-sol")
    monkeypatch.setattr(settings, "lab_llm_model", "claude-sonnet-5-5")

    assert work_intensity._planner_candidates() == [  # noqa: SLF001 - contract assertion
        {"provider": "anthropic", "model": "claude-sonnet-5-5"},
        {"provider": "openai", "model": "kimi-k3"},
        {"provider": "openai", "model": "gpt-6.1-sol"},
    ]
    assert alchemy_lab_llm._planner_candidates(image_paths=False) == [  # noqa: SLF001
        {"provider": "anthropic", "model": "claude-sonnet-5-5"},
        {"provider": "openai", "model": "kimi-k3"},
        {"provider": "openai", "model": "gpt-6.1-sol"},
    ]
    assert work_intensity._anthropic_token() == "test-unified-key"  # noqa: SLF001
    assert alchemy_lab_llm.lab_llm_status()["configured"] is True
    request_fields = RuntimeProviderSettingsRequest.model_fields
    assert "llm_gateway_api_key" in request_fields
    assert not {"anthropic_api_key", "anthropic_auth_token", "deepseek_llm_api_key", "lab_kimi_api_key"} & set(request_fields)
    assert "llm_gateway_api_key_configured" in RuntimeProviderSettingsResponse.model_fields
    assert work_intensity.LLM_LOGICAL_TIMEOUT_SECONDS == 210.0
    assert work_intensity.LLM_CANDIDATE_TIMEOUT_SECONDS == 90.0
    assert alchemy_lab_llm.LAB_TEXT_LOGICAL_TIMEOUT_SECONDS == 210.0
    assert alchemy_lab_llm.LAB_CANDIDATE_TIMEOUT_SECONDS == 90.0


def test_candidate_wall_clock_caps_leave_a_fallback_slice() -> None:
    assert work_intensity._candidate_timeout_seconds(210.0, 2) == 90.0  # noqa: SLF001
    assert work_intensity._candidate_timeout_seconds(20.0, 2) == 10.0  # noqa: SLF001
    assert alchemy_lab_llm._lab_candidate_timeout_seconds(20.0, 2) == 10.0  # noqa: SLF001


def test_v1_and_lab_slow_primary_is_cancelled_before_fallback(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    monkeypatch.setattr(settings, "lab_llm_enabled", True)
    monkeypatch.setattr(settings, "default_llm_model", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "backup_llm_model", "gpt-6.1-sol")
    monkeypatch.setattr(work_intensity, "LLM_CANDIDATE_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr(alchemy_lab_llm, "LAB_CANDIDATE_TIMEOUT_SECONDS", 0.01)

    v1_calls: list[str] = []

    async def slow_v1_primary(_provider, model, *_args, **_kwargs):
        v1_calls.append(model)
        if model == "claude-sonnet-5-5":
            await asyncio.sleep(0.03)
            raise AssertionError("primary should have been cancelled by the hard deadline")
        return {"main_subject": "fallback result"}

    monkeypatch.setattr(work_intensity, "_ask_provider_for_prompt_plan", slow_v1_primary)
    _plan, summary = asyncio.run(
        work_intensity.apply_work_intensity(
            ImagePromptPlan(main_subject="test"),
            original_prompt="test",
            work_intensity="balanced",
            provider_preference=None,
        )
    )
    assert v1_calls == ["claude-sonnet-5-5", "kimi-k3"]
    assert summary["fallback_used"] is True

    v1_json_calls: list[str] = []

    async def slow_v1_json_primary(**kwargs):
        v1_json_calls.append(kwargs["model"])
        await asyncio.sleep(0.03)
        raise AssertionError("primary should have been cancelled by the hard deadline")

    async def fast_v1_json_backup(**kwargs):
        v1_json_calls.append(kwargs["model"])
        return {"ok": True}

    monkeypatch.setattr(work_intensity, "_ask_anthropic_for_json_plan", slow_v1_json_primary)
    monkeypatch.setattr(work_intensity, "_ask_openai_for_json_plan", fast_v1_json_backup)
    (json_result, _meta) = asyncio.run(
        work_intensity.ask_llm_json_plan(system_prompt="test", user_payload={})
    )
    assert json_result == {"ok": True}
    assert v1_json_calls == ["claude-sonnet-5-5", "kimi-k3"]

    lab_calls: list[str] = []

    async def slow_lab_primary(**kwargs):
        lab_calls.append(kwargs["model"])
        if kwargs["model"] == "claude-sonnet-5-5":
            await asyncio.sleep(0.03)
            raise AssertionError("primary should have been cancelled by the hard deadline")
        return {"ok": True}

    monkeypatch.setattr(alchemy_lab_llm, "_ask_provider_for_json", slow_lab_primary)
    lab_result, lab_meta = asyncio.run(
        alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={})
    )
    assert lab_result == {"ok": True}
    assert lab_calls == ["claude-sonnet-5-5", "kimi-k3"]
    assert lab_meta["fallback_used"] is True


def test_v1_selected_models_determine_protocol_and_unknown_models_fail_closed(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "default_llm_model", "deepseek-v4-pro")
    monkeypatch.setattr(settings, "backup_llm_model", "claude-sonnet-5-5")

    assert work_intensity._planner_candidates() == [  # noqa: SLF001
        {"provider": "openai", "model": "deepseek-v4-pro"},
        {"provider": "openai", "model": "kimi-k3"},
        {"provider": "anthropic", "model": "claude-sonnet-5-5"},
        {"provider": "openai", "model": "gpt-6.1-sol"},
    ]
    assert work_intensity._text_model_protocol("unknown-model") == "unsupported"  # noqa: SLF001
    monkeypatch.setattr(settings, "lab_llm_model", "claude-sonnet-5-5")
    assert alchemy_lab_llm._planner_candidates(image_paths=False) == [  # noqa: SLF001
        {"provider": "openai", "model": "deepseek-v4-pro"},
        {"provider": "openai", "model": "kimi-k3"},
        {"provider": "anthropic", "model": "claude-sonnet-5-5"},
        {"provider": "openai", "model": "gpt-6.1-sol"},
    ]
    assert alchemy_lab_llm._text_model_protocol("unknown-model") == "unsupported"  # noqa: SLF001


def test_v1_and_lab_unknown_text_models_fail_closed_before_dispatch(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    monkeypatch.setattr(settings, "default_llm_model", "unknown-primary")
    monkeypatch.setattr(settings, "backup_llm_model", "gpt-6.1-sol")
    monkeypatch.setattr(settings, "image_work_intensity", "balanced")

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("unknown models must not be sent to a provider")

    monkeypatch.setattr(work_intensity, "_ask_provider_for_prompt_plan", fail_if_called)
    try:
        asyncio.run(
            work_intensity.apply_work_intensity(
                ImagePromptPlan(main_subject="test"),
                original_prompt="test",
                work_intensity="balanced",
                provider_preference=None,
            )
        )
    except work_intensity.LLMPlanningUnavailableError as error:
        assert "no supported gateway protocol" in str(error)
    else:
        raise AssertionError("unknown primary models must stop V1 planning")

    monkeypatch.setattr(settings, "lab_llm_enabled", True)
    monkeypatch.setattr(settings, "default_llm_model", "unknown-primary")
    monkeypatch.setattr(settings, "lab_llm_model", "claude-sonnet-5-5")
    monkeypatch.setattr(alchemy_lab_llm, "_ask_provider_for_json", fail_if_called)
    try:
        asyncio.run(alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={}))
    except alchemy_lab_llm.LabLLMError as error:
        assert "no supported gateway protocol" in str(error)
    else:
        raise AssertionError("unknown LAB primary models must stop planning")


def test_openai_refusals_are_terminal_for_v1_and_lab(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    monkeypatch.setattr(settings, "default_llm_model", "gpt-6.1-sol")
    monkeypatch.setattr(settings, "backup_llm_model", "claude-sonnet-5-5")
    monkeypatch.setattr(settings, "lab_llm_enabled", True)
    monkeypatch.setattr(settings, "lab_llm_model", "gpt-6.1-sol")
    provider_calls: list[str] = []

    def refusal(*_args, **_kwargs):
        raise PermissionError("model refusal")

    async def v1_openai_refusal(*_args, **_kwargs):
        provider_calls.append("v1-openai")
        return refusal()

    async def v1_backup(*_args, **_kwargs):
        provider_calls.append("v1-backup")
        return {"main_subject": "should not happen"}

    monkeypatch.setattr(work_intensity, "_ask_openai_for_prompt_plan", v1_openai_refusal)
    monkeypatch.setattr(work_intensity, "_ask_anthropic_for_prompt_plan", v1_backup)
    try:
        asyncio.run(
            work_intensity.apply_work_intensity(
                ImagePromptPlan(main_subject="test"),
                original_prompt="test",
                work_intensity="balanced",
                provider_preference=None,
            )
        )
    except work_intensity.LLMPlanningUnavailableError:
        pass
    else:
        raise AssertionError("V1 must stop after an OpenAI-compatible refusal")

    async def lab_openai_refusal(**_kwargs):
        provider_calls.append("lab-openai")
        return refusal()

    async def lab_backup(**_kwargs):
        provider_calls.append("lab-backup")
        return {"should_not_happen": True}

    monkeypatch.setattr(alchemy_lab_llm, "_ask_openai_json", lab_openai_refusal)
    monkeypatch.setattr(alchemy_lab_llm, "_ask_anthropic_compatible_json", lab_backup)
    try:
        asyncio.run(alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={}))
    except alchemy_lab_llm.LabLLMError:
        pass
    else:
        raise AssertionError("LAB must stop after an OpenAI-compatible refusal")
    assert provider_calls == ["v1-openai", "lab-openai"]


def test_openai_response_refusal_markers_raise_terminal_permission_error() -> None:
    response = SimpleNamespace(
        status="incomplete",
        output_text="",
        incomplete_details=SimpleNamespace(reason="content_filter"),
        output=[SimpleNamespace(type="message", content=[SimpleNamespace(type="refusal", refusal="blocked", text=None)])],
    )
    for parser in (work_intensity._response_text, alchemy_lab_llm._response_text):  # noqa: SLF001
        try:
            parser(response)
        except PermissionError:
            pass
        else:
            raise AssertionError("refusal markers must be terminal")


def test_v1_and_lab_only_fail_over_for_classified_route_failures() -> None:
    unavailable = httpx.Response(503, request=httpx.Request("POST", "https://gateway.test"))
    unauthorized = httpx.Response(401, request=httpx.Request("POST", "https://gateway.test"))
    candidate_denied = httpx.Response(
        403,
        json={"error": {"code": "model_not_available", "scope": "model"}},
        request=httpx.Request("POST", "https://gateway.test"),
    )
    unscoped_denied = httpx.Response(403, json={"error": {"message": "model_not_available"}}, request=httpx.Request("POST", "https://gateway.test"))
    assert work_intensity._is_failover_eligible(httpx.HTTPStatusError("503", request=unavailable.request, response=unavailable))  # noqa: SLF001
    assert alchemy_lab_llm._is_failover_eligible(httpx.HTTPStatusError("503", request=unavailable.request, response=unavailable))  # noqa: SLF001
    assert work_intensity._is_failover_eligible(httpx.HTTPStatusError("403", request=candidate_denied.request, response=candidate_denied))  # noqa: SLF001
    assert not work_intensity._is_failover_eligible(httpx.HTTPStatusError("403", request=unscoped_denied.request, response=unscoped_denied))  # noqa: SLF001
    assert not alchemy_lab_llm._is_failover_eligible(httpx.HTTPStatusError("403", request=unscoped_denied.request, response=unscoped_denied))  # noqa: SLF001
    assert not alchemy_lab_llm._is_failover_eligible(httpx.HTTPStatusError("401", request=unauthorized.request, response=unauthorized))  # noqa: SLF001
    assert work_intensity._is_failover_eligible(work_intensity.LLMStructuredOutputError("bad JSON"))  # noqa: SLF001
    assert alchemy_lab_llm._is_failover_eligible(alchemy_lab_llm.LabStructuredOutputError("bad JSON"))  # noqa: SLF001


def test_lab_vision_route_stays_independent_of_text_gateway(monkeypatch) -> None:
    monkeypatch.setattr(settings, "lab_vision_provider", "doubao")
    monkeypatch.setattr(settings, "lab_doubao_vision_api_key", "vision-only-key")
    monkeypatch.setattr(settings, "lab_doubao_vision_base_url", "https://vision.test/v1")
    monkeypatch.setattr(settings, "lab_doubao_vision_model", "doubao-vision")

    assert alchemy_lab_llm.lab_llm_status()["vision_provider"] == "doubao"
    assert alchemy_lab_llm.lab_llm_status()["vision_configured"] is True


def test_lab_kimi_vision_alias_keeps_legacy_route_and_model(monkeypatch) -> None:
    monkeypatch.setattr(settings, "lab_vision_provider", "kimi")
    monkeypatch.setattr(settings, "lab_kimi_api_key", "vision-only-key")
    monkeypatch.setattr(settings, "lab_kimi_base_url", "https://kimi-vision.test/v1")
    monkeypatch.setattr(settings, "kimi_llm_model", "kimi-for-coding")
    monkeypatch.setattr(settings, "lab_doubao_vision_api_key", None)
    monkeypatch.setattr(settings, "lab_openai_api_key", None)
    monkeypatch.setattr(settings, "deepseek_llm_api_key", None)

    assert alchemy_lab_llm._normalize_lab_provider("kimi") == "kimi"  # noqa: SLF001
    assert alchemy_lab_llm._planner_candidates(image_paths=True) == [  # noqa: SLF001
        {"provider": "kimi", "model": "kimi-for-coding"}
    ]


def test_text_routes_fail_closed_when_unified_gateway_url_is_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_gateway_base_url", None)

    with pytest.raises(work_intensity.LLMPlanningUnavailableError, match="key and base URL"):
        work_intensity._require_unified_gateway()  # noqa: SLF001
    assert work_intensity._planner_candidates() == []  # noqa: SLF001
    with pytest.raises(alchemy_lab_llm.LabLLMError, match="key and base URL"):
        asyncio.run(alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={}))
    assert alchemy_lab_llm.lab_llm_status()["configured"] is False


def test_v1_planning_enabled_fails_closed_when_gateway_credentials_are_missing(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", None)
    monkeypatch.setattr(settings, "llm_gateway_base_url", None)
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    provider_calls: list[str] = []

    async def fake_provider(*_args, **_kwargs):
        provider_calls.append("called")
        return {"main_subject": "unexpected local bypass"}

    monkeypatch.setattr(work_intensity, "_ask_provider_for_prompt_plan", fake_provider)
    with pytest.raises(work_intensity.LLMPlanningUnavailableError, match="no candidate configured"):
        asyncio.run(
            work_intensity.apply_work_intensity(
                ImagePromptPlan(main_subject="test"),
                original_prompt="test",
                work_intensity="balanced",
                provider_preference=None,
            )
        )
    assert provider_calls == []


def test_v1_json_planner_returns_model_attempt_receipt(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_gateway_base_url", "https://gateway.test/v1")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    calls: list[str] = []

    async def fail_primary(**_kwargs):
        calls.append("claude-sonnet-5-5")
        raise httpx.ConnectError("gateway route unavailable")

    async def accept_kimi(**_kwargs):
        calls.append("kimi-k3")
        return {"ok": True}

    monkeypatch.setattr(work_intensity, "_ask_anthropic_for_json_plan", fail_primary)
    monkeypatch.setattr(work_intensity, "_ask_openai_for_json_plan", accept_kimi)
    result, provenance = asyncio.run(work_intensity.ask_llm_json_plan(system_prompt="test", user_payload={}))
    assert result == {"ok": True}
    assert calls == ["claude-sonnet-5-5", "kimi-k3"]
    assert provenance["selected_model"] == "kimi-k3"
    assert [item["outcome"] for item in provenance["model_attempts"]] == ["failed", "accepted"]


def test_lab_refusal_is_terminal_even_for_image_conditioned_requests() -> None:
    try:
        alchemy_lab_llm._anthropic_response_text(  # noqa: SLF001 - refusal boundary assertion
            {"stop_reason": "refusal", "content": [{"type": "text", "text": "not allowed"}]}
        )
    except PermissionError as error:
        assert not alchemy_lab_llm._is_failover_eligible(error)  # noqa: SLF001
    else:
        raise AssertionError("a refusal must not be converted into a fallback-eligible parse failure")


def test_v1_and_lab_advance_to_kimi_after_primary_transport_failure(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    monkeypatch.setattr(settings, "lab_llm_enabled", True)
    calls: list[tuple[str, str]] = []

    async def fake_v1(provider, model, *_args, **_kwargs):
        calls.append((provider, model))
        if provider == "anthropic":
            raise httpx.ConnectError("gateway route unavailable")
        return {"main_subject": "validated"}

    monkeypatch.setattr(work_intensity, "_ask_provider_for_prompt_plan", fake_v1)
    plan, provenance = asyncio.run(
        work_intensity.apply_work_intensity(
            ImagePromptPlan(main_subject="test"),
            original_prompt="test",
            work_intensity="balanced",
            provider_preference=None,
        )
    )
    assert plan.main_subject == "validated"
    assert provenance["llm_model"] == "kimi-k3"
    assert provenance["fallback_used"] is True
    assert [item["outcome"] for item in provenance["model_attempts"]] == ["failed", "accepted"]
    assert provenance["primary_model"] == "claude-sonnet-5-5"
    assert provenance["selected_model"] == "kimi-k3"

    lab_calls: list[tuple[str, str]] = []

    async def fake_lab(**kwargs):
        lab_calls.append((kwargs["provider"], kwargs["model"]))
        if kwargs["provider"] == "anthropic":
            raise httpx.ConnectError("gateway route unavailable")
        return {"validated": True}

    monkeypatch.setattr(alchemy_lab_llm, "_ask_provider_for_json", fake_lab)
    result, lab_provenance = asyncio.run(
        alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={})
    )
    assert result == {"validated": True}
    assert lab_provenance["llm_model"] == "kimi-k3"
    assert lab_provenance["fallback_used"] is True
    assert [item["outcome"] for item in lab_provenance["model_attempts"]] == ["failed", "accepted"]
    assert lab_provenance["selected_model"] == "kimi-k3"
    assert calls == [("anthropic", "claude-sonnet-5-5"), ("openai", "kimi-k3")]
    assert lab_calls == [("anthropic", "claude-sonnet-5-5"), ("openai", "kimi-k3")]


def test_v1_and_lab_advance_to_gpt_when_kimi_also_fails(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)
    monkeypatch.setattr(settings, "lab_llm_enabled", True)
    calls: list[str] = []

    async def fail_primary_and_kimi(provider, model, *_args, **_kwargs):
        calls.append(model)
        if model != "gpt-6.1-sol":
            raise httpx.ConnectError(f"{provider} route unavailable")
        return {"main_subject": "gpt recovery"}

    monkeypatch.setattr(work_intensity, "_ask_provider_for_prompt_plan", fail_primary_and_kimi)
    _plan, meta = asyncio.run(
        work_intensity.apply_work_intensity(
            ImagePromptPlan(main_subject="test"), original_prompt="test", work_intensity="balanced", provider_preference=None
        )
    )
    assert calls == ["claude-sonnet-5-5", "kimi-k3", "gpt-6.1-sol"]
    assert meta["llm_model"] == "gpt-6.1-sol"
    assert [item["outcome"] for item in meta["model_attempts"]] == ["failed", "failed", "accepted"]

    lab_calls: list[str] = []

    async def fail_lab_primary_and_kimi(**kwargs):
        lab_calls.append(kwargs["model"])
        if kwargs["model"] != "gpt-6.1-sol":
            raise httpx.ConnectError("route unavailable")
        return {"ok": True}

    monkeypatch.setattr(alchemy_lab_llm, "_ask_provider_for_json", fail_lab_primary_and_kimi)
    _result, lab_meta = asyncio.run(alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={}))
    assert lab_calls == ["claude-sonnet-5-5", "kimi-k3", "gpt-6.1-sol"]
    assert lab_meta["llm_model"] == "gpt-6.1-sol"
    assert [item["outcome"] for item in lab_meta["model_attempts"]] == ["failed", "failed", "accepted"]


def test_v1_stops_before_image_generation_when_both_text_candidates_fail(monkeypatch) -> None:
    monkeypatch.setattr(settings, "llm_gateway_api_key", "test-unified-key")
    monkeypatch.setattr(settings, "llm_prompt_planning_enabled", True)

    async def fail_candidate(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(work_intensity, "_ask_provider_for_prompt_plan", fail_candidate)
    try:
        asyncio.run(
            work_intensity.apply_work_intensity(
                ImagePromptPlan(main_subject="test"),
                original_prompt="test",
                work_intensity="balanced",
                provider_preference=None,
            )
        )
    except work_intensity.LLMPlanningUnavailableError as error:
        assert [item["outcome"] for item in error.model_attempts] == ["failed", "failed", "failed"]
        assert {item["failure_class"] for item in error.model_attempts} == {"retryable_upstream"}
    else:
        raise AssertionError("planning failure must stop before image generation")

    monkeypatch.setattr(settings, "lab_llm_enabled", True)
    async def fail_lab_candidate(**_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(alchemy_lab_llm, "_ask_provider_for_json", fail_lab_candidate)
    try:
        asyncio.run(alchemy_lab_llm.plan_lab_json(system_prompt="test", user_payload={}))
    except alchemy_lab_llm.LabLLMError as error:
        assert [item["outcome"] for item in error.model_attempts] == ["failed", "failed", "failed"]
        assert {item["failure_class"] for item in error.model_attempts} == {"retryable_upstream"}
    else:
        raise AssertionError("terminal LAB failure must retain its bounded model-attempt receipt")


def test_v1_image_service_never_calls_image_provider_after_planning_error(monkeypatch) -> None:
    provider_calls: list[str] = []

    async def fail_planning(*_args, **_kwargs):
        raise work_intensity.LLMPlanningUnavailableError("both text routes failed")

    async def spy_image_request(*_args, **_kwargs):
        provider_calls.append("called")
        raise AssertionError("image provider must not be reached")

    monkeypatch.setattr(image_service, "apply_work_intensity", fail_planning)
    monkeypatch.setattr(image_service, "_run_image_request", spy_image_request)
    try:
        asyncio.run(
            image_service.create_image_job(
                session_id="failover-regression",
                prompt="A simple blue ceramic cup on a white table",
                work_intensity="balanced",
            )
        )
    except work_intensity.LLMPlanningUnavailableError:
        pass
    else:
        raise AssertionError("failed planning must abort image service")
    assert provider_calls == []


def test_v1_image_service_never_calls_image_provider_after_planning_failure(monkeypatch) -> None:
    provider_calls: list[str] = []

    async def fail_planning(*_args, **_kwargs):
        raise work_intensity.LLMPlanningUnavailableError("both text routes failed")

    async def spy_image_request(*_args, **_kwargs):
        provider_calls.append("called")
        raise AssertionError("image provider must not be reached")

    monkeypatch.setattr(image_service, "apply_work_intensity", fail_planning)
    monkeypatch.setattr(image_service, "_run_image_request", spy_image_request)
    try:
        asyncio.run(
            image_service.create_image_job(
                session_id="failover-regression",
                prompt="A simple blue ceramic cup on a white table",
                work_intensity="balanced",
            )
        )
    except work_intensity.LLMPlanningUnavailableError:
        pass
    else:
        raise AssertionError("failed planning must abort image service")
    assert provider_calls == []


def test_empty_successful_v1_responses_are_classified_as_structured_output_failures() -> None:
    response = SimpleNamespace(output_text="", output=[], status="completed", incomplete_details=None)
    for invoke in (work_intensity._response_text, work_intensity._anthropic_response_text):
        try:
            invoke(response if invoke is work_intensity._response_text else {})
        except work_intensity.LLMStructuredOutputError as exc:
            assert work_intensity._is_failover_eligible(exc)  # noqa: SLF001
        else:
            raise AssertionError("empty successful response must be eligible for the selected backup model")


def test_empty_successful_lab_responses_are_classified_as_structured_output_failures() -> None:
    response = SimpleNamespace(output_text="", output=[], status="completed", incomplete_details=None)
    for invoke in (alchemy_lab_llm._response_text, alchemy_lab_llm._anthropic_response_text):
        try:
            invoke(response if invoke is alchemy_lab_llm._response_text else {})
        except alchemy_lab_llm.LabStructuredOutputError as exc:
            assert alchemy_lab_llm._is_failover_eligible(exc)  # noqa: SLF001
        else:
            raise AssertionError("empty successful response must be eligible for the selected backup model")
