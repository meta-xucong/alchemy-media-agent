import json
import pytest
from copy import deepcopy
from fractions import Fraction
from alchemy_creative_agent_3_0.app.generation_router import ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.tests.test_v3_provider_output_production import _generation_request
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

    assert resolved.effective_image_size == "3008x1280"
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

    assert resolved.effective_image_size == "3008x1280"
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


def test_desktop_continuation_preserves_project_image_count() -> None:
    desktop = (ROOT / "src_skeleton" / "app" / "static" / "app.js").read_text(encoding="utf-8")

    assert "function setV3ContinuationGenerationDefaults()" in desktop
    assert "stored?.general?.requested_image_count" in desktop
    assert "supported.includes(2) ? 2" in desktop
    continuation = desktop.split('if (action === "continue_same_style")', 1)[1].split(
        'if (action === "upload_reference_continue")', 1
    )[0]
    assert "setV3ContinuationGenerationDefaults();" in continuation
    assert continuation.index("setV3ContinuationGenerationDefaults();") < continuation.index("els.v3PromptInput.value")


@pytest.mark.parametrize("initial_size", ["1024x1536", "2048x1152"])
def test_prompt_canvas_synchronizes_typed_option_and_frozen_provider_plan(initial_size, monkeypatch):
    runtime = ScenarioRuntime()
    request = SimpleNamespace(metadata={
        "requested_image_size": initial_size,
        "provider_image_options": {"size": "1024x1536", "quality": "high"},
    })
    resolved = runtime._apply_brain_image_size_precedence(
        request, _normalized_intent(initial_size),
        SimpleNamespace(image_set_plan=SimpleNamespace(size="2048x1152", aspect_ratio="16:9")),
    )
    assert resolved.effective_image_size == "2048x1152"
    assert request.metadata["provider_image_options"] == {"size": "2048x1152", "quality": "high"}
    assert request.metadata["manual_provider_image_size"] == "1024x1536"
    assert resolved.provenance[-1]["manual_provider_image_size"] == "1024x1536"

    # Exercise the real planning freeze with dependency outputs stubbed, then
    # consume its per-output metadata at the real provider size boundary.
    class Record(SimpleNamespace):
        def model_copy(self, *, update):
            return Record(**{**vars(self), **update})
    generation = _generation_request()
    result = Record(creative_job=Record(metadata={}), generation_plans=[generation.generation_plan], metadata={})
    monkeypatch.setattr(runtime, "_activation_metadata", lambda _: {})
    monkeypatch.setattr(runtime, "_specialized_metadata", lambda _: {})
    preparation = SimpleNamespace(normalized_job_intent=resolved, activation_plan=None)
    frozen = runtime._enrich_activation_result(result, preparation, request)
    generation.generation_plan = frozen.generation_plans[0]
    generation.metadata = {}
    provider = ProductionImageGenerationProvider()
    assert generation.generation_plan.metadata["requested_image_size"] == "2048x1152"
    assert generation.generation_plan.metadata["requested_image_size_source"] == "remote_brain_user_intent"
    assert provider._size_for_request(generation) == "2048x1152"
    assert "aspect ratio: 16:9" in provider._asset_canvas_instruction(generation, generation.asset_spec)
    assert "2:3" not in provider._asset_canvas_instruction(generation, generation.asset_spec)


@pytest.mark.parametrize("size,ratio,expected", [
    ("1536x864", "16:9", "1536x864"),
    ("2048x1152", "16:9", "2048x1152"),
    ("1920x1080", "16:9", "auto"),
    ("auto", "16:9", "auto"),
    ("1024x1536", "16:9", "2048x1152"),
    (None, "4:1", "auto"),
    ("17x17", None, "auto"),
])
def test_explicit_canvas_preserves_exact_dimensions_or_uses_auto(size, ratio, expected):
    request = SimpleNamespace(metadata={"provider_image_options": {"size": "1024x1536"}})
    resolved = ScenarioRuntime()._apply_brain_image_size_precedence(
        request, _normalized_intent("1024x1536"),
        SimpleNamespace(image_set_plan=SimpleNamespace(size=size, aspect_ratio=ratio)),
    )
    assert resolved.effective_image_size == expected
    generation = _generation_request()
    generation.generation_plan.metadata.update(request.metadata)
    provider = ProductionImageGenerationProvider()
    assert provider._size_for_request(generation) == expected
    hint = provider._asset_canvas_instruction(generation, generation.asset_spec)
    if expected == "auto":
        assert "aspect ratio" not in hint
        assert "requested_image_aspect_ratio" not in request.metadata
        assert resolved.provenance[-1]["requested_canvas_aspect_ratio"] == ratio
    elif ratio == "16:9":
        assert "16:9" in hint


@pytest.mark.parametrize("ratio", ["2.35:1", "2.39:1", "9:16", "4:5", "7:5", "11:8"])
def test_structured_ratio_resolution_is_exact_not_nearest(ratio):
    _, size = ScenarioRuntime._canonical_brain_aspect_ratio(ratio)
    width, height = map(int, size.split("x"))
    numerator, denominator = ratio.split(":")
    assert Fraction(width, height) == Fraction(numerator) / Fraction(denominator)
    assert ScenarioRuntime._canonical_brain_image_size(size) == size


def test_absent_prompt_canvas_keeps_manual_options_unchanged():
    metadata = {"requested_image_size": "1024x1536", "provider_image_options": {"size": "1024x1536"}}
    request = SimpleNamespace(metadata=deepcopy(metadata))
    normalized = _normalized_intent("1024x1536")
    assert ScenarioRuntime()._apply_brain_image_size_precedence(
        request, normalized, SimpleNamespace(image_set_plan=SimpleNamespace(size=None, aspect_ratio=None)),
    ) is normalized
    assert request.metadata == metadata


def test_trusted_frozen_replay_never_reinterprets_historical_canvas():
    normalized = _normalized_intent("1024x1536")
    metadata = {"normalized_v3_job_intent": normalized.model_dump(mode="json"),
                "provider_image_options": {"size": "1024x1536"}}
    request = SimpleNamespace(metadata=deepcopy(metadata), trusted_capability_plan_reuse=True)
    assert ScenarioRuntime()._apply_brain_image_size_precedence(
        request, normalized, SimpleNamespace(image_set_plan=SimpleNamespace(size="2048x1152", aspect_ratio="16:9")),
    ) is normalized
    assert request.metadata == metadata


@pytest.mark.parametrize("size,expected", [("2048x1152", "2048x1152"), ("1920x1080", "auto")])
def test_prompt_owned_canvas_reaches_materialization_without_rewriting_prompt(size, expected):
    user_prompt = f"Create a landscape image at exactly {size}, 16:9."
    request = SimpleNamespace(metadata={"requested_image_size": "1024x1536",
                                        "provider_image_options": {"size": "1024x1536"}})
    ScenarioRuntime()._apply_brain_image_size_precedence(
        request, _normalized_intent("1024x1536"),
        SimpleNamespace(image_set_plan=SimpleNamespace(size=size, aspect_ratio="16:9")),
    )
    generation = _generation_request()
    generation.metadata["user_input"] = user_prompt
    generation.metadata["llm_brain"]["canonical_provider_prompts"][0]["prompt"] = user_prompt
    generation.generation_plan.metadata.update(request.metadata)
    materialized = ProductionImageGenerationProvider().materialize_final_prompt(generation)
    assert materialized.size == expected
    assert materialized.generation_prompt == user_prompt


def test_native_auto_clears_stale_frozen_plan_crop_requirement(monkeypatch):
    runtime = ScenarioRuntime()
    request = SimpleNamespace(metadata={
        "requested_image_size": "1024x1536",
        "requested_image_aspect_ratio": "2:3",
        "provider_image_options": {"size": "1024x1536"},
    })
    resolved = runtime._apply_brain_image_size_precedence(
        request, _normalized_intent("1024x1536"),
        SimpleNamespace(image_set_plan=SimpleNamespace(size="1920x1080", aspect_ratio="16:9")),
    )
    class Record(SimpleNamespace):
        def model_copy(self, *, update):
            return Record(**{**vars(self), **update})
    generation = _generation_request()
    generation.generation_plan.metadata["requested_image_aspect_ratio"] = "2:3"
    generation.generation_plan.metadata["requested_image_aspect_ratio_source"] = "remote_brain_user_intent"
    result = Record(creative_job=Record(metadata={}), generation_plans=[generation.generation_plan], metadata={})
    monkeypatch.setattr(runtime, "_activation_metadata", lambda _: {})
    monkeypatch.setattr(runtime, "_specialized_metadata", lambda _: {})
    frozen = runtime._enrich_activation_result(
        result, SimpleNamespace(normalized_job_intent=resolved, activation_plan=None), request,
    )
    metadata = frozen.generation_plans[0].metadata
    assert metadata["provider_image_options"]["size"] == "auto"
    assert not metadata["requested_image_aspect_ratio"]
    assert not metadata["requested_image_aspect_ratio_source"]
