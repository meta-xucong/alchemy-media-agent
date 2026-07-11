from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeStatus
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities import VISUAL_CAPABILITY_CLUSTER_ID


def _plan(monkeypatch, payload):
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    return ScenarioRuntime().plan_job(payload)


def test_enforced_runtime_persists_frozen_plan(monkeypatch) -> None:
    result = _plan(monkeypatch, {"user_input": "Create an anime illustration", "scenario_selection": {"scenario_id": "general_creative"}, "metadata": {"requested_image_count": 1}})
    assert result.status == ScenarioRuntimeStatus.PLANNED
    plan = result.metadata["capability_activation_plan"]
    assert plan["plan_id"] == result.metadata["capability_activation_plan_id"]
    assert plan["activation_mode"] == "enforced"
    assert result.planning_result.metadata["capability_activation_plan_id"] == plan["plan_id"]
    assert result.planning_result.creative_job.metadata["capability_activation_plan_id"] == plan["plan_id"]


def test_new_jobs_default_to_enforced_activation(monkeypatch) -> None:
    monkeypatch.delenv("V3_CAPABILITY_ACTIVATION_MODE", raising=False)
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")

    result = ScenarioRuntime().plan_job(
        {
            "user_input": "Create an anime illustration",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1},
        }
    )

    assert result.status == ScenarioRuntimeStatus.PLANNED
    assert result.metadata["capability_activation_mode"] == "enforced"
    assert result.metadata["capability_activation_plan"]["activation_mode"] == "enforced"


def test_product_only_job_excludes_human_and_portrait(monkeypatch) -> None:
    result = _plan(monkeypatch, {"user_input": "Create a premium product hero for a desk lamp", "scenario_selection": {"scenario_id": "general_creative"}, "uploaded_assets": [{"asset_id": "product", "role": "product_reference"}], "metadata": {"requested_image_count": 1}})
    active = set(result.metadata["capability_activation_plan"]["dependency_order"])
    assert "product_identity" in active
    assert "human_realism" not in active
    assert "portrait_identity" not in active


def test_product_job_does_not_execute_human_builder(monkeypatch) -> None:
    runtime = ScenarioRuntime()
    cluster = runtime.shared_capability_registry.get(VISUAL_CAPABILITY_CLUSTER_ID)

    class Bomb:
        def build(self, **kwargs):
            raise AssertionError("human builder must not execute")

    cluster.human_photorealism_layer = Bomb()
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = runtime.plan_job({"user_input": "Create a product image for a watch", "scenario_selection": {"scenario_id": "general_creative"}, "metadata": {"requested_image_count": 1}})
    assert result.status == ScenarioRuntimeStatus.PLANNED


def test_portrait_reference_activates_human_and_identity(monkeypatch) -> None:
    result = _plan(monkeypatch, {"user_input": "Create a real woman portrait", "scenario_selection": {"scenario_id": "general_creative"}, "uploaded_assets": [{"asset_id": "face", "role": "face_reference"}], "metadata": {"requested_image_count": 1}})
    active = set(result.metadata["capability_activation_plan"]["dependency_order"])
    assert {"human_realism", "portrait_identity"} <= active


def test_non_human_illustration_uses_universal_base_only(monkeypatch) -> None:
    result = _plan(monkeypatch, {"user_input": "Create an anime cartoon character illustration", "scenario_selection": {"scenario_id": "general_creative"}, "metadata": {"requested_image_count": 1}})
    active = set(result.metadata["capability_activation_plan"]["dependency_order"])
    assert "human_realism" not in active
    assert "portrait_identity" not in active
    assert {"visual_grammar", "universal_visual_quality"} <= active


def test_product_api_reuses_one_frozen_plan_for_generate(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create a real woman portrait",
            "scenario_selection": {"scenario_id": "general_creative"},
            "uploaded_asset_ids": ["face"],
            "metadata": {"requested_image_count": 1},
        }
    )
    record = service.job_store.get(created.job_id)
    first_plan_id = record.request.metadata["capability_activation_plan_id"]
    service.generate_job(created.job_id)
    record = service.job_store.get(created.job_id)
    assert record.generation_result.metadata["capability_activation_plan_id"] == first_plan_id
    assert record.request.metadata["capability_activation_plan"]["plan_id"] == first_plan_id
