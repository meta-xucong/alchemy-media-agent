import json

import pytest

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.schemas import AssetType, Platform
from alchemy_creative_agent_3_0.app.llm_brain import BrainRunRequest
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result


@pytest.mark.parametrize(
    "user_input",
    [
        "Give this cup a summer background",
        "Generate one product atmosphere image for this desk lamp",
        "Make one social-media cover for this drink bottle",
        "Show this product in use on a desk",
    ],
)
def test_general_light_product_requests_do_not_become_ecommerce_suites(monkeypatch, user_input: str) -> None:
    monkeypatch.delenv("V3_CAPABILITY_ACTIVATION_MODE", raising=False)
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")

    result = ScenarioRuntime().plan_job(
        {
            "user_input": user_input,
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_assets": [{"asset_id": "product", "role": "product_reference"}],
            "metadata": {"requested_image_count": 1},
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.metadata["capability_activation_mode"] == "enforced"
    assert result.planning_result is not None
    planning = result.planning_result
    assert planning.metadata["scenario_id"] == "general_creative"
    assert planning.metadata["selected_vertical_pack"] == "default_commercial_pack"
    assert len(planning.series_plan.assets) == 1
    assert planning.series_plan.assets[0].asset_type == AssetType.SINGLE_IMAGE
    assert planning.series_plan.assets[0].platform == Platform.GENERIC_SOCIAL

    active = set(result.metadata["capability_activation_plan"]["dependency_order"])
    assert "product_identity" in active
    assert "suite_direction" not in active
    assert "typography_layout" not in active

    delivery = json.dumps(
        {
            "assets": [item.model_dump(mode="json") for item in planning.series_plan.assets],
            "layouts": [item.model_dump(mode="json") for item in planning.layout_plans],
            "prompts": [item.model_dump(mode="json") for item in planning.prompt_compilations],
        }
    ).lower()
    for ecommerce_only_term in ("amazon", "ozon", "marketplace", "listing", "a+", "size chart", "detail page"):
        assert ecommerce_only_term not in delivery


def test_general_nonperson_scene_has_no_local_service_or_portrait_review_leakage(monkeypatch) -> None:
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")

    result = ScenarioRuntime().plan_job(
        {
            "user_input": (
                "Create one photoreal wide cinematic landscape of a remote glacial alpine lake at blue hour after rain. "
                "Natural atmospheric perspective, wet foreground rocks, no buildings, no people, no text, and no fantasy objects."
            ),
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "blank"},
            "metadata": {
                "requested_image_count": 1,
                "requested_image_size": "1536x1024",
                "template_id": "general_template",
                "variation_mode": "selection_candidates",
                "effective_variation_mode": "selection_candidates",
            },
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.planning_result is not None
    planning = result.planning_result
    assert planning.metadata["selected_vertical_pack"] == "default_commercial_pack"
    active = set(result.metadata["capability_activation_plan"]["dependency_order"])
    assert "human_realism" not in active
    assert "portrait_identity" not in active

    cluster = result.metadata["shared_capabilities"]["visual_cluster"]
    assert cluster["template_consistency_policy"]["policy_id"] == "general_visual_grammar"
    assert cluster["role_specific_generation_plan"]["subject_type"] == "generic"
    strict_policy = cluster["strict_visual_review_policy"]
    assert strict_policy["subject_type"] == "generic"
    mode_profile = cluster["mode_quality_profile"]

    prompt = planning.prompt_compilations[0].visual_prompt.lower()
    for forbidden in (
        "local service specialization",
        "appointment-ready",
        "reference person's own attractiveness",
        "facial-feature integrity",
        "jaw/chin direction",
        "poreless glass-like skin",
        "gaze, hand placement",
        "micro-expression",
        "same expression and head angle",
        "cinematic portrait request",
        "generic beauty portrait",
    ):
        assert forbidden not in prompt
        assert forbidden not in " ".join(cluster["role_specific_generation_plan"]["prompt_additions"]).lower()
        assert forbidden not in " ".join(strict_policy["prompt_additions"]).lower()
        assert forbidden not in " ".join(strict_policy["negative_additions"]).lower()
        assert forbidden not in " ".join(strict_policy["review_focus"]).lower()
        assert forbidden not in " ".join(strict_policy["user_visible_summary"]).lower()
        assert forbidden not in " ".join(mode_profile["review_priorities"]).lower()
        assert forbidden not in " ".join(mode_profile["pass_conditions"]).lower()
        assert forbidden not in " ".join(mode_profile["retry_triggers"]).lower()
        assert forbidden not in " ".join(mode_profile["prompt_guidance"]).lower()
        assert forbidden not in " ".join(mode_profile["negative_guidance"]).lower()
        assert forbidden not in " ".join(planning.prompt_compilations[0].hard_constraints).lower()


def test_general_nonperson_fallback_brain_uses_subject_neutral_candidate_language() -> None:
    result = build_fallback_result(
        BrainRunRequest(
            user_input=(
                "Create an empty contemporary museum atrium with fair-faced concrete, pale terrazzo, warm oak, "
                "a broad staircase, and a long skylight."
            ),
            scenario_id="general_creative",
            template_id="general_template",
            requested_image_count=1,
            requested_image_size="1024x1536",
            metadata={"variation_mode": "selection_candidates"},
        )
    )

    direction = " ".join(result.prompt_guidance.visual_direction_addons).lower()
    assert "same core subject, same style, small differences in framing, viewpoint, lighting, or scene depth" in direction
    for person_only_term in ("pose", "expression", "gaze", "hand placement", "micro-expression"):
        assert person_only_term not in direction
