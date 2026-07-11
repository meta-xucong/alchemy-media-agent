from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


def _cluster(monkeypatch, payload):
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(payload)
    return result.planning_result.metadata["visual_cluster"]


def test_product_cluster_has_zero_human_contribution(monkeypatch) -> None:
    cluster = _cluster(monkeypatch, {"user_input": "Create a product hero for a shoe", "scenario_selection": {"scenario_id": "general_creative"}, "metadata": {"requested_image_count": 1}})
    composed = cluster["composed_visual_contribution"]
    joined = " ".join([*composed["prompt_additions"], *composed["negative_additions"]]).lower()
    assert "human_realism" not in composed["active_capability_ids"]
    assert "skin texture" not in joined
    assert "same person" not in joined


def test_landscape_cluster_has_zero_product_and_portrait_contribution(monkeypatch) -> None:
    cluster = _cluster(monkeypatch, {"user_input": "Create a wide mountain landscape photograph", "scenario_selection": {"scenario_id": "general_creative"}, "metadata": {"requested_image_count": 1}})
    active = set(cluster["composed_visual_contribution"]["active_capability_ids"])
    assert "product_identity" not in active
    assert "portrait_identity" not in active
    assert "human_realism" not in active


def test_product_on_model_activates_both_compatible_plugins(monkeypatch) -> None:
    cluster = _cluster(monkeypatch, {"user_input": "Real woman model wearing the supplied product for an ecommerce campaign", "scenario_selection": {"scenario_id": "ecommerce"}, "uploaded_assets": [{"asset_id": "sku", "role": "product_reference"}], "metadata": {"requested_image_count": 1}})
    active = set(cluster["composed_visual_contribution"]["active_capability_ids"])
    assert {"product_identity", "human_realism"} <= active
