from __future__ import annotations

import asyncio
import json

import pytest

from app.schemas import ImagePromptPlan
from app.services import alchemy_lab as lab, alchemy_lab_quality, work_intensity


def test_v1_planning_removes_only_exact_duplicate_context():
    user = "Preserve every label and the uploaded product. " * 40
    assets = {"provider_input_plan": {"requires_image_reference": True},
              "visible_details": ["unique packaging and logo detail"] * 40}
    plan = ImagePromptPlan(main_subject="Product", variables={
        "original_prompt": user, "asset_context": assets,
        "generation_prompt": "Unique scaffold and fallback lighting",
        "custom_constraint": "Keep this custom input",
    })
    before = plan.model_dump()
    payload = work_intensity._planner_user_payload(
        plan, user, "studio", work_intensity.INTENSITY_PROFILES["studio"], assets,
    )
    assert payload["user_prompt"] == user
    assert payload["asset_context"] == assets
    variables = payload["current_plan"]["variables"]
    assert "original_prompt" not in variables
    assert "asset_context" not in variables
    assert variables == {key: value for key, value in before["variables"].items()
                         if key not in {"original_prompt", "asset_context"}}
    assert plan.model_dump() == before
    assert {k: v for k, v in payload["current_plan"].items() if k != "variables"} == {
        k: v for k, v in before.items() if k != "variables"
    }
    old_payload = {**payload, "current_plan": before}
    assert len(json.dumps(payload)) < len(json.dumps(old_payload))


def test_v1_planning_preserves_nonduplicate_variables():
    plan = ImagePromptPlan(main_subject="Portrait", variables={
        "original_prompt": "Earlier user context", "asset_context": {"unique": "reference notes"},
    })
    payload = work_intensity._planner_user_payload(
        plan, "Current user request", "balanced", work_intensity.INTENSITY_PROFILES["balanced"], {},
    )
    assert payload["current_plan"] == plan.model_dump()


def _session(count=4):
    styles = [lab.StylePreset(id=f"style-{i}", display_name=f"Style {i}",
                              short_description="Keep unique visual direction", family="test", category="test")
              for i in range(count)]
    return lab.ExplorationSession(
        id="planning-only", status="running", created_at="2026-11-09T00:00:00Z",
        updated_at="2026-11-09T00:00:00Z",
        request=lab.ExplorationRequest(idea="Exact user text and reference intent", quality_enhancement="curated"),
        style_presets=styles,
        prompts=[lab.ComposedPrompt(id=f"prompt-{i}", session_id="planning-only", style_preset_id=s.id,
                                    style_preset_version="1", idea="Full intent", final_prompt=f"Exact input {i}")
                 for i, s in enumerate(styles)],
    )


def test_lab_quality_payload_retains_idea_once():
    session = _session(1)
    payload = alchemy_lab_quality._planner_payload(
        request=session.request, style=session.style_presets[0], base_prompt="Exact base prompt",
        strategy="curated", selected_styles=session.style_presets,
    )
    assert payload["original_idea"] == session.request.idea
    assert "normalized_idea" not in payload
    assert payload["base_rare_style_prompt"] == "Exact base prompt"
    assert payload["style_preset_snapshot"]["display_name"] == "Style 0"


def test_lab_quality_planning_overlaps_two_without_changing_inputs_or_order(monkeypatch):
    session = _session()
    before = [p.model_dump() for p in session.prompts]
    calls, finished, active = [], [], set()
    gates = {}

    async def save(current):
        return current

    async def enhance(**kwargs):
        index = int(kwargs["prompt"].id.split("-")[-1])
        assert kwargs["request"] is session.request
        assert kwargs["style"] is session.style_presets[index]
        assert kwargs["selected_styles"] is session.style_presets
        assert kwargs["composer_factory"] is lab.local_quality_prompt
        assert kwargs["prompt"].model_dump() == before[index]
        calls.append(index)
        active.add(index)
        assert len(active) <= 2
        gate = gates.setdefault(index // 2, asyncio.Event())
        if len([i for i in calls if i // 2 == index // 2]) == 2:
            gate.set()
        await gate.wait()
        # The second call completes first; published ordering must still match inputs.
        if index % 2 == 0:
            await asyncio.sleep(0)
        finished.append(index)
        active.remove(index)
        assert [p.model_dump() for p in session.prompts] == before
        return kwargs["prompt"].model_copy(update={"final_prompt": f"Enhanced {index}",
                                                   "prompt_metadata": {"quality_enhancement": {"applied": True}}})

    monkeypatch.setattr(lab, "_save_runner_state", save)
    monkeypatch.setattr(lab, "enhance_lab_prompt", enhance)

    async def exercise():
        async with asyncio.timeout(2):
            await lab._ensure_session_prompts_enhanced(session)

    asyncio.run(exercise())
    assert calls == [0, 1, 2, 3]
    assert finished == [1, 0, 3, 2]
    assert not active
    assert [p.final_prompt for p in session.prompts] == [f"Enhanced {i}" for i in range(4)]
    asyncio.run(lab._ensure_session_prompts_enhanced(session))
    assert calls == [0, 1, 2, 3]  # Existing completion metadata still avoids replanning.


def test_lab_planning_cancellation_joins_inflight_calls(monkeypatch):
    session = _session(3)
    before = [p.model_dump() for p in session.prompts]
    entered, exited = [], []

    async def exercise():
        both_started = asyncio.Event()

        async def save(current):
            return current

        async def enhance(**kwargs):
            name = kwargs["prompt"].id
            entered.append(name)
            if len(entered) == 2:
                both_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                exited.append(name)

        monkeypatch.setattr(lab, "_save_runner_state", save)
        monkeypatch.setattr(lab, "enhance_lab_prompt", enhance)
        task = asyncio.create_task(lab._ensure_session_prompts_enhanced(session))
        try:
            async with asyncio.timeout(2):
                await both_started.wait()
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    asyncio.run(exercise())
    assert sorted(entered) == sorted(exited) == ["prompt-0", "prompt-1"]
    assert [p.model_dump() for p in session.prompts] == before
