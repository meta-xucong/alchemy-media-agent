from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime, ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import build_task_profile_and_intent
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


def test_runtime_bound_general_suite_survives_remote_intent_omission(monkeypatch) -> None:
    """A valid remote plan cannot deactivate the frozen multi-output contract."""

    runtime = ScenarioRuntime()
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    request = ScenarioRuntimeRequest.model_validate(
        {
            "user_input": "Create a coherent two-image supermarket photo set.",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "parameters": {"requested_image_count": 2},
            },
            "metadata": {"requested_image_count": 2},
        }
    )
    resolution = runtime.scenario_registry.resolve(request.scenario_selection)
    normalized = runtime._normalize_v3_job_intent(request, resolution)  # noqa: SLF001
    request = runtime._bind_initial_general_variation_contract(  # noqa: SLF001
        request,
        resolution,
        normalized,
    )
    policy = runtime._resolve_template_capability_policy(request, resolution)  # noqa: SLF001
    profile, intent = build_task_profile_and_intent(
        user_input=request.user_input,
        job_id="job_remote_omission",
        project_id=None,
        template_id="general_template",
        scenario_id="general_creative",
        uploaded_assets=[],
        reference_assets=[],
        product_profile={},
        metadata=dict(request.metadata),
        template_policy=policy,
    )
    remote_intent = intent.model_copy(
        update={
            "requested_capabilities": [
                item
                for item in intent.requested_capabilities
                if item.capability_id != "suite_direction"
            ],
        }
    )
    brain_result = SimpleNamespace(
        visual_task_profile=profile,
        capability_activation_intent=remote_intent,
        fallback_used=False,
    )
    catalog = runtime.visual_capability_registry.catalog_snapshot(
        "general_template",
        "general_creative",
    )

    plan = runtime._build_activation_plan(  # noqa: SLF001
        request,
        resolution,
        brain_result,
        policy,
        catalog.catalog_version,
        "enforced",
    )

    suite = plan.active("suite_direction")
    assert suite is not None
    assert suite.activation_mode == "required"
    assert "runtime_bound_variation_contract" in suite.reason_codes
    assert any(
        item.capability_id == "suite_direction"
        for item in brain_result.capability_activation_intent.requested_capabilities
    )


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
