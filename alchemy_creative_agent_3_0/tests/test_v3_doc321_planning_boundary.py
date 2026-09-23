"""Metadata planning never becomes a pixel verdict or real-render retry driver."""
from types import SimpleNamespace as NS
from unittest.mock import Mock
from alchemy_creative_agent_3_0.app.evaluation.scorers import MockScoringProvider, RuleBasedPlanningScorer
from alchemy_creative_agent_3_0.app.creative_core import central_brain
from alchemy_creative_agent_3_0.app.schemas import Platform, TextRenderingMode, Recommendation
from alchemy_creative_agent_3_0.app.agents.prompt_compiler_agent import PromptCompilerAgent


def inputs():
    return dict(
        candidate=NS(candidate_id="candidate_real", asset_id="asset", is_mock=False, provider="real_provider", metadata={}),
        asset_spec=NS(asset_id="asset", aspect_ratio="1:1", platform=Platform.GENERIC_SOCIAL, requires_text_overlay=False),
        commercial_brief=NS(business_goal="show product", commercial_hooks=["true detail"], visual_tone=["bright"]),
        brand_profile=NS(brand_id="brand", visual_tone=["luminous silver"], color_palette=["white", "silver"]),
        creative_plan=NS(creative_plan_id="creative", visual_direction="clear product photograph"),
        layout_plan=NS(asset_id="asset", product_area=True, text_rendering=TextRenderingMode.NO_TEXT, metadata={}),
        prompt_compilation=NS(prompt_compilation_id="prompt", style_notes=[], visual_prompt="product", provider_notes={"text_rendering_owner":"image_provider"}),
    )


def test_mock_provider_cannot_claim_real_candidate_quality():
    report = MockScoringProvider().score_candidate(**inputs(), retry_budget_exhausted=True)
    assert report.recommendation == Recommendation.PLANNING_ONLY
    assert report.metadata["quality_failure"] is False
    assert report.metadata["quality_assessment"] == "not_assessed"
    assert report.metadata["source_agent"] == "rule_based_planning_scorer"

def test_real_generation_never_invokes_mock_scorer_or_metadata_retry(monkeypatch):
    fixture = inputs()
    brain = central_brain.CentralCreativeBrain.__new__(central_brain.CentralCreativeBrain)
    brain.scorer = RuleBasedPlanningScorer()
    brain.generation_scorer = Mock()
    brain.generation_scorer.score_candidate.side_effect = AssertionError("mock scorer received real pixels")
    brain.refinement_provider = Mock()
    brain.generation_router = NS(generate=Mock(return_value=NS(candidates=[fixture["candidate"]], warnings=[])))
    context = NS(selected_vertical_pack=None, creative_job=None, evaluation_reports=[], candidate_results=[],
        commercial_brief=fixture["commercial_brief"], brand_profile=fixture["brand_profile"], creative_plan=fixture["creative_plan"])
    monkeypatch.setattr(central_brain, "build_provider_generation_request", lambda **kw: NS())
    chosen, review, warnings = brain._run_asset_generation_loop(context, fixture["asset_spec"],
        fixture["layout_plan"], fixture["prompt_compilation"], NS(), NS(max_refine_rounds=3))
    assert chosen is fixture["candidate"]
    assert review.recommendation == Recommendation.PLANNING_ONLY
    assert not warnings
    brain.generation_router.generate.assert_called_once()
    brain.generation_scorer.score_candidate.assert_not_called()
    brain.refinement_provider.propose_refinement.assert_not_called()


def test_signed_shadow_keeps_brand_style_metadata_without_rewriting_signed_prompt():
    fixture = inputs()
    result = PromptCompilerAgent()._brain_owned_shadow_compilation(brief=fixture["commercial_brief"],
        creative_plan=fixture["creative_plan"], layout_plan=fixture["layout_plan"], brand_profile=fixture["brand_profile"], llm_brain={})
    assert "luminous silver" in result.style_notes
    assert result.visual_prompt == "[remote_brain_canonical_provider_prompt_bound_separately]"
