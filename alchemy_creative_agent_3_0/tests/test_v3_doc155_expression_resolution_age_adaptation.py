"""Doc155: shared expression resolution works across ages without local recipes."""

from __future__ import annotations

import json

from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS,
    SYSTEM_PROMPT,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def _guidance(user_input: str):
    return HumanPhotorealismLayer().build(
        project_id="project_doc155",
        job_id="job_doc155",
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


def test_doc155_same_shared_contract_adapts_explicit_six_and_ten_year_old_people() -> None:
    six = _guidance(
        "Create a real-camera photograph of a visible East Asian girl, about 6 years old, "
        "wearing the user-selected dress in a garden."
    ).semantic_contract
    ten = _guidance(
        "Create a real-camera photograph of a visible East Asian girl, about 10 years old, "
        "wearing the user-selected dress in a garden."
    ).semantic_contract

    assert six.keys() == ten.keys()
    assert six["contract_version"] == ten["contract_version"] == "v3_human_realism_semantic_v7"
    assert six["identity_age_fidelity"] == ten["identity_age_fidelity"] == "explicit_or_reference_backed"
    assert six["ordinary_age_appropriate_context"] is True
    assert ten["ordinary_age_appropriate_context"] is True
    assert six["expression_resolution_requirement"] == ten["expression_resolution_requirement"] == (
        "individual_situation_not_stock_geometry"
    )
    serialized = json.dumps(six, ensure_ascii=False).lower()
    assert "child" not in serialized
    assert "smile" not in serialized


def test_doc155_adult_uses_same_expression_semantics_without_child_branch() -> None:
    adult = _guidance(
        "Create a real-camera photograph of a visible adult person reading beside a window at home."
    ).semantic_contract

    assert adult["contract_version"] == "v3_human_realism_semantic_v7"
    assert adult["ordinary_age_appropriate_context"] is False
    assert adult["expression_resolution_requirement"] == "individual_situation_not_stock_geometry"
    assert "child" not in json.dumps(adult, ensure_ascii=False).lower()


def test_doc155_brain_receives_semantic_resolution_not_a_local_expression_recipe() -> None:
    combined = f"{SYSTEM_PROMPT}\n{HUMAN_EXPRESSION_AUTHENTICITY_INSTRUCTIONS}"

    assert "expression_resolution_requirement" in combined
    assert "individual_situation_not_stock_geometry" in combined
    assert "same open-mouth or tooth geometry" in combined
    assert "expression_catalogue" not in combined
    assert "fixed alternate-expression catalogue" in combined
    assert "prompt_additions" not in combined
    assert "negative_additions" not in combined
