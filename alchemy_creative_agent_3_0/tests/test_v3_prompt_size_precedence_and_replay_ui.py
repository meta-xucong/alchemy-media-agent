import json
from pathlib import Path
from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest, V3LLMBrainAdapter
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

    assert resolved.effective_image_size == "2048x1152"
    assert request.metadata["requested_image_size"] == "2048x1152"
    assert request.metadata["requested_image_size_source"] == "remote_brain_user_intent"
    assert request.metadata["web_selected_image_size"] == "1024x1024"


def test_brain_explicit_wide_canvas_size_overrides_web_selection() -> None:
    request = SimpleNamespace(metadata={"requested_image_size": "1024x1024"})
    brain_result = SimpleNamespace(image_set_plan=SimpleNamespace(size="2048x1152"))

    resolved = ScenarioRuntime()._apply_brain_image_size_precedence(  # noqa: SLF001
        request,
        _normalized_intent("1024x1024"),
        brain_result,
    )

    assert resolved.effective_image_size == "2048x1152"
    assert request.metadata["requested_image_size"] == "2048x1152"
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
    assert "2048x1152" in payload["canvas_resolution_instructions"]
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


def test_brain_aspect_ratio_resolves_to_supported_landscape_canvas() -> None:
    request = SimpleNamespace(metadata={"requested_image_size": "1024x1024"})
    brain_result = SimpleNamespace(
        image_set_plan=SimpleNamespace(size=None, aspect_ratio="2.35:1")
    )

    resolved = ScenarioRuntime()._apply_brain_image_size_precedence(  # noqa: SLF001
        request,
        _normalized_intent("1024x1024"),
        brain_result,
    )

    assert resolved.effective_image_size == "1536x1024"
    assert request.metadata["requested_image_aspect_ratio"] == "2.35:1"
    assert request.metadata["requested_image_size_source"] == "remote_brain_user_intent"


def test_brain_aspect_ratio_overrides_echoed_browser_canvas() -> None:
    request = SimpleNamespace(metadata={"requested_image_size": "1024x1024"})
    brain_result = SimpleNamespace(
        image_set_plan=SimpleNamespace(size="1024x1024", aspect_ratio="2.35:1")
    )

    resolved = ScenarioRuntime()._apply_brain_image_size_precedence(  # noqa: SLF001
        request,
        _normalized_intent("1024x1024"),
        brain_result,
    )

    assert resolved.effective_image_size == "1536x1024"
    assert request.metadata["requested_image_aspect_ratio_source"] == "remote_brain_user_intent"


def test_compact_brain_payload_carries_active_human_realism_contract() -> None:
    adapter = V3LLMBrainAdapter()
    request = adapter.build_request(
        user_input="A real person in a cinematic scene.",
        stage="plan",
        scenario_id="general_creative",
        template_id="general_template",
        metadata={
            "requested_image_count": 1,
            "requested_image_size": "1536x1024",
            "require_real_images": True,
        },
        shared_capabilities={
            "visual_cluster": {
                "human_photorealism_guidance": {
                    "applies": True,
                    "subject_type": "person",
                    "realism_level": "natural_photoreal",
                    "metadata": {"human_subject_kind": "person"},
                    "semantic_contract": {
                        "rendering_goal": "photographic_real_person",
                        "physical_coherence": "required",
                    },
                }
            }
        },
    )

    payload = json.loads(build_remote_payload(request))

    contract = payload["human_realism_execution_contract"]
    assert contract["applies"] is True
    assert contract["semantic_contract"]["physical_coherence"] == "required"


def test_finalizer_payload_declares_lossless_user_direction_boundary() -> None:
    adapter = V3LLMBrainAdapter()
    request = BrainRunRequest(
        user_input="Create a wide cinematic photographic scene with the supplied subject and warm evening light.",
        stage="provider_prompt_finalize",
        scenario_id="general_creative",
        template_id="general_template",
        requested_image_count=1,
        metadata={"require_lossless_user_direction": True},
    )

    payload = json.loads(build_remote_payload(request))

    assert payload["protected_user_direction"] == request.user_input
    assert "complete user-owned semantic source" in payload["user_direction_contract"]
    assert payload["return_schema"]["canonical_provider_prompts"][0]["user_direction_integrity"]["owner"] == (
        "remote_v3_llm_brain"
    )


def test_terminal_replay_loads_project_outputs_before_success_notice() -> None:
    desktop = (ROOT / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    mobile = (ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js").read_text(encoding="utf-8")

    desktop_terminal = desktop.split("if (v3IsTerminalJob(created))", 1)[1].split("updateV3Notice", 1)[0]
    mobile_terminal = mobile.split("if (mobileV3IsTerminalJob(created))", 1)[1].split("await refreshMobileV3ProjectDetail", 1)[0]

    assert "await loadV3ProjectOutputs" in desktop_terminal
    assert "force: true" in desktop_terminal
    assert "await loadMobileV3ProjectOutputs" in mobile_terminal


def test_terminal_retry_payload_includes_generated_jobs_without_visible_images() -> None:
    desktop = (ROOT / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")
    mobile = (ROOT / "src_skeleton" / "app" / "mobile_static" / "mobile.js").read_text(encoding="utf-8")

    assert "v3_retry_after_terminal_job_id" in desktop
    assert "v3_user_initiated_generation: true" in desktop
    assert '"generated", "selected", "ready", "blocked", "failed", "not_found"' in desktop
    assert "v3_retry_after_terminal_job_id" in mobile
    assert "v3_user_initiated_generation: true" in mobile
    assert '"generated", "selected", "ready", "blocked", "failed", "not_found"' in mobile


def test_desktop_continuation_defaults_to_one_image() -> None:
    desktop = (ROOT / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert "function setV3ContinuationGenerationDefaults()" in desktop
    assert "supported.includes(1) ? 1" in desktop
    continuation = desktop.split('if (action === "continue_same_style")', 1)[1].split(
        'if (action === "upload_reference_continue")', 1
    )[0]
    assert "setV3ContinuationGenerationDefaults();" in continuation
    assert continuation.index("setV3ContinuationGenerationDefaults();") < continuation.index("els.v3PromptInput.value")
