import json
from pathlib import Path
from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.prompts import build_remote_payload
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import NormalizedV3JobIntent


ROOT = Path(__file__).resolve().parents[2]


def _normalized_intent(size: str | None) -> NormalizedV3JobIntent:
    return NormalizedV3JobIntent(
        intent_id="intent-test",
        template_id="general_template",
        scenario_id="general_creative",
        protected_user_intent="Create an image.",
        requested_image_count=1,
        effective_image_count=1,
        requested_image_size=size,
        effective_image_size=size,
    )


def test_brain_explicit_canvas_size_overrides_web_selection() -> None:
    request = SimpleNamespace(metadata={"requested_image_size": "1024x1024"})
    brain_result = SimpleNamespace(image_set_plan=SimpleNamespace(size="16:9"))

    resolved = ScenarioRuntime()._apply_brain_image_size_precedence(  # noqa: SLF001
        request,
        _normalized_intent("1024x1024"),
        brain_result,
    )

    assert resolved.effective_image_size == "1536x1024"
    assert request.metadata["requested_image_size"] == "1536x1024"
    assert request.metadata["requested_image_size_source"] == "remote_brain_user_intent"
    assert request.metadata["web_selected_image_size"] == "1024x1024"


def test_missing_brain_canvas_size_keeps_web_selection_as_fallback() -> None:
    request = SimpleNamespace(metadata={"requested_image_size": "1024x1536"})
    brain_result = SimpleNamespace(image_set_plan=SimpleNamespace(size=None))

    resolved = ScenarioRuntime()._apply_brain_image_size_precedence(  # noqa: SLF001
        request,
        _normalized_intent("1024x1536"),
        brain_result,
    )

    assert resolved.effective_image_size == "1024x1536"
    assert request.metadata == {"requested_image_size": "1024x1536"}


def test_brain_payload_separates_web_size_fallback_from_prompt_size() -> None:
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a wide 16:9 landscape image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "requested_image_count": 1,
            "requested_image_size": "1024x1536",
            "require_real_images": True,
        },
    )

    payload = json.loads(build_remote_payload(request))

    assert payload["web_selected_image_size"] == "1024x1536"
    assert "user_input as the only authority" in payload["canvas_resolution_instructions"]
    assert "return image_set_plan.size as null" in payload["canvas_resolution_instructions"]


def test_brain_request_preserves_web_size_when_brain_size_wins() -> None:
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="Create a wide 16:9 landscape image.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "requested_image_count": 1,
            "requested_image_size": "1536x1024",
            "web_selected_image_size": "1024x1024",
            "require_real_images": True,
        },
    )

    payload = json.loads(build_remote_payload(request))

    assert payload["requested_image_size"] == "1536x1024"
    assert payload["web_selected_image_size"] == "1024x1024"


def test_terminal_replay_loads_project_outputs_before_success_notice() -> None:
    desktop = (ROOT / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    mobile = (ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js").read_text(encoding="utf-8")

    desktop_terminal = desktop.split("if (v3IsTerminalJob(created))", 1)[1].split("updateV3Notice", 1)[0]
    mobile_terminal = mobile.split("if (mobileV3IsTerminalJob(created))", 1)[1].split("await refreshMobileV3ProjectDetail", 1)[0]

    assert "await loadV3ProjectOutputs" in desktop_terminal
    assert "force: true" in desktop_terminal
    assert "await loadMobileV3ProjectOutputs" in mobile_terminal
