from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain.prompts import SYSTEM_PROMPT
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HumanPhotorealismLayer,
)


def _guidance(user_input: str, *, subject_type: str = "person"):
    return HumanPhotorealismLayer().build(
        project_id="project_doc170",
        job_id="job_doc170",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=user_input,
        subject_type=subject_type,
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


def test_doc170_brain_requires_aesthetic_and_material_to_survive_together() -> None:
    assert "explicit user-owned aesthetic appeal and camera-observed human material as a conjunction" in SYSTEM_PROMPT
    assert "rejecting generic beauty never authorizes making the person bland or less attractive" in SYSTEM_PROMPT
    assert "commercial beauty never authorizes cosmetic smoothing or synthetic perfection" in SYSTEM_PROMPT
    assert "not through a facial recipe, demographic template or retouched surface" in SYSTEM_PROMPT
    assert "not materially resolved when it becomes one uniform pale or polished surface" in SYSTEM_PROMPT
    assert "A word such as unretouched is no more sufficient than photorealistic" in SYSTEM_PROMPT
    assert "keep the owned color and the scene-observed, light-dependent human material together" in SYSTEM_PROMPT
    assert "Preserve the same aesthetic-material conjunction during this stage" in SYSTEM_PROMPT
    assert "never authorizes dropping explicit user-owned aesthetic appeal" in SYSTEM_PROMPT


def test_doc170_uses_existing_universal_semantic_contract_without_prompt_fragments() -> None:
    guidance = _guidance(
        "A naturally beautiful adult musician photographed honestly after a rehearsal."
    )
    contract = guidance.semantic_contract

    assert contract["aesthetic_boundary"] == "preserve_user_style_without_generic_beauty_substitution"
    assert contract["photographic_material_requirement"] == "camera_observed_human_materiality"
    assert guidance.positive_prompt_fragments == []
    assert guidance.negative_prompt_fragments == []


def test_doc170_contract_remains_demographic_and_template_neutral() -> None:
    guidance = _guidance(
        "A naturally beautiful six-year-old East Asian child in a clean casting portrait."
    )
    serialized = json.dumps(guidance.semantic_contract, ensure_ascii=False).lower()

    for forbidden in ("child", "east asian", "casting", "cheek", "jaw", "eye shape", "pore"):
        assert forbidden not in serialized


def test_doc170_no_person_control_does_not_create_local_human_prompting() -> None:
    guidance = _guidance(
        "A clean photograph of a handmade ceramic cup on a linen table.",
        subject_type="product",
    )

    assert guidance.positive_prompt_fragments == []
    assert guidance.negative_prompt_fragments == []
    assert "child" not in json.dumps(guidance.semantic_contract, ensure_ascii=False).lower()


def test_doc170_developmental_signoff_does_not_invent_a_face_recipe() -> None:
    assert "does not authorize the renderer prompt to explain age through inferred facial morphology" in SYSTEM_PROMPT
    assert "do not manufacture facial parts merely to make the label redundant" in SYSTEM_PROMPT
