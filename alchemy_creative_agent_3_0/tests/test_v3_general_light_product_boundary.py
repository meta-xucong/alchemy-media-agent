import json

import pytest

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.schemas import AssetType, Platform


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
