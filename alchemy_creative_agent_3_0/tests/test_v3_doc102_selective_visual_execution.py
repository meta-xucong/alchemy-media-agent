from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities import VISUAL_CAPABILITY_CLUSTER_ID


def test_inactive_suite_director_is_not_executed_for_single_image(monkeypatch) -> None:
    runtime = ScenarioRuntime()
    cluster = runtime.shared_capability_registry.get(VISUAL_CAPABILITY_CLUSTER_ID)

    class BombSuiteDirector:
        def build(self, **kwargs):
            raise AssertionError("suite director must remain inactive")

    cluster.suite_director = BombSuiteDirector()
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = runtime.plan_job(
        {
            "user_input": "Create one anime illustration",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1},
        }
    )
    assert result.status.value == "planned"
    assert "suite_direction" not in result.metadata["capability_activation_plan"]["dependency_order"]


def test_active_suite_director_runs_for_multiple_outputs(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create a coherent image set",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 3},
        }
    )
    assert "suite_direction" in result.metadata["capability_activation_plan"]["dependency_order"]


def test_illustration_skips_identity_and_reference_builders(monkeypatch) -> None:
    runtime = ScenarioRuntime()
    cluster = runtime.shared_capability_registry.get(VISUAL_CAPABILITY_CLUSTER_ID)

    class BombBuilder:
        def build(self, **kwargs):
            raise AssertionError("inactive identity builder executed")

    class BombReference:
        def resolve(self, **kwargs):
            raise AssertionError("inactive reference policy executed")

    cluster.identity_drift_guard = BombBuilder()
    cluster.subject_asset_pack_builder = BombBuilder()
    cluster.identity_anchor_builder = BombBuilder()
    cluster.identity_repair_strategy_router = BombBuilder()
    cluster.reference_channel_policy_module = BombReference()
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = runtime.plan_job(
        {
            "user_input": "Create one anime illustration",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1},
        }
    )
    assert result.status.value == "planned"
