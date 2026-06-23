from alchemy_creative_agent_3_0.app.condition_engine import (
    NoopIdentityConditionProvider,
    NoopLayoutConditionProvider,
    NoopRendererProvider,
    NoopStyleConditionProvider,
)
from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.evaluation import RuleBasedRefinementProvider, weighted_overall
from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, PlanningOnlyGenerationProvider


def test_noop_providers_return_serializable_contracts() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")
    asset = result.series_plan.assets[0]

    assert NoopStyleConditionProvider().build_condition(result.brand_profile, asset).model_dump(mode="json")
    assert NoopLayoutConditionProvider().build_condition(asset).enabled is False
    assert NoopIdentityConditionProvider().build_condition(asset).enabled is False
    assert NoopRendererProvider().render_spec(asset)["runtime_mode"] == "no_render"
    assert NoopStyleConditionProvider().capabilities().model_dump(mode="json")["supports_style_conditioning"] is True


def test_planning_only_generation_provider_creates_mock_candidate() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")
    request = GenerationRequest(
        prompt_compilation=result.prompt_compilations[0],
        condition_plan=result.condition_plans[0],
        generation_plan=result.generation_plans[0],
    )
    response = PlanningOnlyGenerationProvider().generate(request)

    assert len(response.candidates) == 1
    assert response.candidates[0].is_mock is True
    assert response.candidates[0].provider == "planning_only_generation_provider"


def test_weighted_overall_formula_and_planning_evaluation() -> None:
    score = weighted_overall(0.75, 0.78, 0.78, 0.80, 0.82, 0.82)
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")

    assert score == 0.785
    assert result.evaluation_reports[0].recommendation == "planning_only"
    assert result.evaluation_reports[0].metadata["formula_version"] == "v3.0-eval-formula-001"


def test_refinement_provider_returns_none_for_clean_planning_report() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")

    assert RuleBasedRefinementProvider().propose_refinement(result.evaluation_reports[0]) is None
