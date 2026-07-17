from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HumanPhotorealismLayer,
)


def _guidance(user_input: str):
    return HumanPhotorealismLayer().build(
        project_id="project_doc159",
        job_id="job_doc159",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=user_input,
        subject_type="person",
        variation_mode="single_hero",
        has_identity_reference=False,
        metadata={
            "brain_owned_forward_execution": True,
            "human_realism_execution_required": True,
            "frozen_rendering_intent": {
                "rendering_mode": "photoreal",
                "stylization_scope": "none",
                "decision_owner": "remote_brain",
            },
        },
    )


def test_doc159_brain_instruction_honors_market_brightness_without_bleaching() -> None:
    assert "target-market presentation preference" in SYSTEM_PROMPT
    assert "brighter and fairer complexion" in SYSTEM_PROMPT
    assert "Do not infer a preferred complexion from ethnicity alone" in SYSTEM_PROMPT
    assert "Do not bleach" in SYSTEM_PROMPT
    assert "restrained matte highlights" in SYSTEM_PROMPT
    assert "neutral-to-slightly-warm scene white balance" in SYSTEM_PROMPT
    assert "muddy yellow or green cast" in SYSTEM_PROMPT


def test_doc159_keeps_frozen_contract_demographic_neutral_and_brain_owned() -> None:
    guidance = _guidance(
        "Commercial kidswear photograph of an East Asian child model in a bright studio."
    )
    contract = guidance.semantic_contract
    serialized = json.dumps(contract, ensure_ascii=False).lower()

    assert "east asian" not in serialized
    assert "fair" not in serialized
    assert "white" not in serialized
    assert "yellow" not in serialized
    assert "green cast" not in serialized
    assert contract["complexion_rendering_requirement"] == (
        "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
    )
    assert guidance.positive_prompt_fragments == []
    assert guidance.negative_prompt_fragments == []


def test_doc159_does_not_force_commercial_brightness_into_low_key_work() -> None:
    guidance = _guidance(
        "Low-key documentary photograph of an adult ceramic artist in an old workshop."
    )
    serialized = json.dumps(guidance.semantic_contract, ensure_ascii=False).lower()

    assert "commercial" not in serialized
    assert "fair" not in serialized
    assert "white" not in serialized
    assert "yellow" not in serialized
    assert guidance.semantic_contract["complexion_rendering_requirement"] == (
        "preserve_reference_or_user_owned_complexion_with_scene_balanced_color"
    )
