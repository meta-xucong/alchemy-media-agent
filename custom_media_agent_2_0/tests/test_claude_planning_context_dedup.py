import json

import pytest

from app.services import claude_orchestrator as claude


@pytest.mark.parametrize("mode", ["stable", "enhanced", "exploration"])
@pytest.mark.parametrize("stage", ["intent", "visual", "inline"])
def test_transform_instruction_is_complete_and_present_once(tmp_path, mode, stage):
    instruction = claude._prompt_transform_claude_instruction(mode)
    profile = {"source": "output.prompt_transform_mode", "v2_mode": "template_customize",
               "transform_mode": mode, "fidelity_mode": "strict", "claude_instruction": instruction}
    context = {"request": {"user_prompt": "Preserve exact logo and packaging; follow selected template.",
                            "template_case_id": "selected-template", "output": {"count": 2}},
               "prompt_transform_profile": profile}
    (tmp_path / "context.json").write_text(json.dumps(context), encoding="utf-8")
    if stage == "inline":
        prompt = claude._build_inline_json_prompt(tmp_path)
    else:
        prompt = claude._build_checkpoint_stage_prompt(tmp_path, stage_name=stage)
    payload = json.loads(prompt.split("\n", 1)[1])
    assert payload["prompt_transform"] == profile
    assert instruction not in payload["rules"]
    assert "prompt_transform.claude_instruction" in payload["rules"]
    assert prompt.count(instruction) == 1
    if stage == "inline":
        assert payload["user_request"] == context["request"]["user_prompt"]
        assert payload["template_case_id"] == "selected-template"
    else:
        assert payload["request"]["user_prompt"] == context["request"]["user_prompt"]
        assert payload["request"]["template_case_id"] == "selected-template"
