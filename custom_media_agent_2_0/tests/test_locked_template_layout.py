from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from PIL import Image

from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CreateCreativeRunRequest, ImageJob, ImageOutput, PromptCase
from app.services import claude_orchestrator as brain, visual_review_agent as vision
from app.services.output_review import review_image_job
from app.services.prompting import compose_prompt_plan


@pytest.fixture
def template() -> PromptCase:
    return PromptCase(
        case_id="case_multi_panel",
        title="Grain powder ad board",
        category="ecommerce",
        provider_id="test",
        index_version="test",
        source_url="https://example.test/case",
        raw_prompt=json.dumps({
            "product": {"name": "Old Brand", "description": "hero product " * 65},
            "layout": {"sections": [
                {"title": "Main image", "position": "top-left", "labels": ["Old Brand"]},
                {"title": "Details page", "position": "top-right", "labels": ["Old Slogan"]},
                {"title": "冲泡方式", "position": "mid-left lower"},
                {"title": "Storyboard", "position": "bottom full width"},
            ]},
        }),
    )


@pytest.fixture
def plan(template):
    return compose_prompt_plan(
        mode="template_customize",
        user_prompt="Make a green grain powder main image; keep the template's layout. No prices.",
        cases=[template],
        output={"count": 1},
        asset_context={"template_lock_contract": {"locked_case_id": template.case_id}},
    )


def test_manual_layout_survives_claude_compression_and_provider_prompt(template, plan, tmp_path, monkeypatch):
    grammar = plan.user_variables["visual_grammar_contract"]
    regions = grammar["template_layout_regions"]
    assert regions == [
        {"position": "top-left", "role": "primary visual"},
        {"position": "top-right", "role": "product details"},
        {"position": "mid-left lower", "role": "preparation or process"},
        {"position": "bottom full width", "role": "storyboard strip"},
    ]
    monkeypatch.setattr(brain, "settings", replace(brain.settings, claude_orchestrator_workspace_dir=tmp_path))
    request = CreateCreativeRunRequest(user_prompt=plan.user_variables["user_prompt"], template_case_id=template.case_id)
    (tmp_path / "context.json").write_text(json.dumps({"request": request.model_dump()}), encoding="utf-8")
    (tmp_path / "visual_grammar_contract.json").write_text(json.dumps(grammar), encoding="utf-8")
    for stage in ("visual_strategy_micro", "visual_strategy_ultra_micro", "generation_decision_micro"):
        payload = json.loads(brain._build_checkpoint_stage_prompt(tmp_path, stage_name=stage).split("\n", 1)[1])
        assert payload.get("visual_grammar_contract", {})["template_layout_regions"] == regions
        assert "keep every region" in payload["rules"].lower()
    inline = json.loads(brain._build_inline_json_prompt(tmp_path).split("\n", 1)[1])
    assert inline["visual_grammar_contract"]["template_layout_regions"] == regions

    compiled_layout = plan.prompt.split("LOCKED TEMPLATE LAYOUT:", 1)[1].split("\n\n", 1)[0]
    assert all(region["position"] in compiled_layout for region in regions)
    assert "Old Brand" not in compiled_layout and "Old Slogan" not in compiled_layout
    assert "intent_locked_template_layout" in plan.user_variables["prompt_integrity"]["manifest"]["required_intent_ids"]


def test_auto_retrieval_does_not_lock_layout(template):
    plan = compose_prompt_plan(mode="smart_enhance", user_prompt="Make a grain powder image.", cases=[template], output={})
    assert "template_layout_regions" not in plan.user_variables["visual_grammar_contract"]
    assert "LOCKED TEMPLATE LAYOUT" not in plan.prompt


@pytest.mark.parametrize(("matches", "issues", "expected"), [
    (True, [], "pass"),
    (False, ["The top-right product details area is missing."], "needs_review"),
    (None, [], "needs_review"),
])
def test_review_checks_locked_regions_in_same_call_and_keeps_image(plan, tmp_path, monkeypatch, matches, issues, expected):
    monkeypatch.setattr(vision, "settings", replace(
        settings, output_review_agent_enabled=True, output_review_agent_model="test-vision",
        claude_orchestrator_model="test-vision", claude_orchestrator_multimodal_model="test-vision",
        storage_dir=tmp_path,
    ))
    path = tmp_path / "result.png"
    Image.new("RGB", (80, 120), "green").save(path)
    now = utc_now()
    output = ImageOutput(output_id="output", job_id="job", url="/result.png", created_at=now,
                         metadata={"live": True, "storage_path": str(path)})
    job = ImageJob(job_id="job", status="completed", provider_id="render_bridge", model="image",
                   prompt_plan=plan, outputs=[output], created_at=now, updated_at=now)
    calls = []

    async def fake_verdict(content, model, *, timeout):
        calls.append(content)
        values = {"decision": "needs_review" if issues else "pass", "references_match": True,
                  "notes": [], "issues": issues}
        if matches is not None:
            values["template_layout_matches"] = matches
        return vision.VisionVerdict.model_validate(values)

    monkeypatch.setattr(vision, "_request_verdict", fake_verdict)
    reviewed = asyncio.run(vision.review_generated_job(review_image_job(job)))
    assert len(calls) == 1 and len(calls[0]) == 2
    instruction, data = calls[0][0]["text"].split("\n", 1)
    assert "template_layout_matches" in instruction
    assert json.loads(data)["template_layout_regions"] == plan.user_variables["visual_grammar_contract"]["template_layout_regions"]
    result, = reviewed.outputs
    assert reviewed.status == "completed" and result.url == output.url
    assert result.review.decision == expected
    if expected == "needs_review":
        assert result.review.revision_directives
        assert set(issues).issubset(result.review.revision_directives)
