from alchemy_creative_agent_3_0.app.creative_core import CentralCreativeBrain, run_creative_planning
from alchemy_creative_agent_3_0.app.schemas import PlanningResult


def test_end_to_end_planning_chain_contains_every_required_stage() -> None:
    result = run_creative_planning("帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。")

    assert isinstance(result, PlanningResult)
    assert result.creative_job
    assert result.commercial_brief
    assert result.brand_profile
    assert result.creative_plan
    assert result.series_plan
    assert len(result.layout_plans) == len(result.series_plan.assets)
    assert len(result.prompt_compilations) == len(result.series_plan.assets)
    assert len(result.condition_plans) == len(result.series_plan.assets)
    assert len(result.generation_plans) == len(result.series_plan.assets)
    assert len(result.evaluation_reports) == len(result.series_plan.assets)
    assert len(result.asset_pack.assets) == len(result.series_plan.assets)
    assert result.metadata["selected_vertical_pack"]
    assert result.metadata["v3_independent_runtime"] is True


def test_central_creative_brain_orchestrates_pipeline() -> None:
    result = CentralCreativeBrain().run_creative_planning("帮我做一个活动宣传图，适合小红书，风格要高级。")

    assert result.planning_result_id.startswith("planning_result_")
    assert result.creative_job.job_id.startswith("job_")
    assert result.asset_pack.manifest["asset_count"] == len(result.series_plan.assets)

