import json

from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.schemas import (
    BrandProfile,
    CandidateResult,
    CommercialAssetPack,
    ConditionPlan,
    CreativeJob,
    EvaluationReport,
    GenerationPlan,
    LayoutPlan,
    PromptCompilationResult,
    ProviderStrategy,
    Recommendation,
)


def test_schema_planning_result_serializes_to_json() -> None:
    result = run_creative_planning("帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。")

    payload = result.model_dump(mode="json")
    encoded = result.model_dump_json()

    assert json.loads(encoded)["creative_job"]["raw_user_input"] == result.creative_job.raw_user_input
    assert payload["generation_plans"][0]["provider_strategy"] == "planning_only"
    assert result.asset_pack.planning_only is True


def test_core_schema_classes_exist() -> None:
    assert CreativeJob
    assert BrandProfile
    assert LayoutPlan
    assert PromptCompilationResult
    assert ConditionPlan
    assert GenerationPlan
    assert CandidateResult
    assert EvaluationReport
    assert CommercialAssetPack
    assert ProviderStrategy.PLANNING_ONLY == "planning_only"
    assert Recommendation.PLANNING_ONLY == "planning_only"


def test_scores_are_normalized() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书，风格要高级。")

    for report in result.evaluation_reports:
        assert 0.0 <= report.aesthetic_score <= 1.0
        assert 0.0 <= report.commercial_score <= 1.0
        assert 0.0 <= report.brand_consistency_score <= 1.0
        assert 0.0 <= report.layout_score <= 1.0
        assert 0.0 <= report.text_region_score <= 1.0
        assert 0.0 <= report.platform_fit_score <= 1.0
        assert 0.0 <= report.overall_score <= 1.0

