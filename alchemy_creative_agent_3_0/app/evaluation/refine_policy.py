"""Rule-based refinement plan provider."""

from __future__ import annotations

from ..creative_core.rules import RULE_VERSION, stable_id
from ..schemas import EvaluationReport, Recommendation, RefinementPlan, Severity


class RuleBasedRefinementProvider:
    provider_name = "rule_based_refinement_provider"
    provider_version = "v3.0-foundation"

    def propose_refinement(self, evaluation: EvaluationReport) -> RefinementPlan | None:
        if evaluation.recommendation == Recommendation.PLANNING_ONLY and not evaluation.problems:
            return None
        prompt_modifications: list[str] = []
        layout_modifications: list[str] = []
        condition_modifications: list[str] = []
        provider_modifications: list[str] = []
        for problem in evaluation.problems:
            if problem.code == "missing_text_region":
                layout_modifications.append("reserve top and bottom clean text regions")
                prompt_modifications.append("request clean negative space for external text overlay")
            elif problem.code == "fake_text_risk":
                prompt_modifications.append("add provider note to avoid fake final Chinese text")
            elif problem.code == "platform_ratio_mismatch":
                layout_modifications.append("replace aspect ratio with platform default")
            elif problem.code == "brand_style_missing":
                prompt_modifications.append("inject BrandProfile visual tone and color palette")
                condition_modifications.append("enable style condition if references exist")
            elif problem.code == "missing_product_area":
                layout_modifications.append("increase product_area priority and set it to center_large")
                prompt_modifications.append("emphasize clear product hero shot")
            elif problem.code == "commercial_hook_missing":
                prompt_modifications.append("add commercial hook and conversion cue from CommercialBrief")
                layout_modifications.append("add or strengthen CTA region")
            elif problem.code == "provider_failure":
                provider_modifications.append("discard failed candidate and retry with mock fallback")
        action = Recommendation.RETRY
        if any(problem.severity == Severity.HARD_FAILURE for problem in evaluation.problems):
            action = Recommendation.RETRY
        return RefinementPlan(
            refinement_plan_id=stable_id("refinement", evaluation.asset_id, evaluation.evaluation_id),
            asset_id=evaluation.asset_id,
            source_evaluation_id=evaluation.evaluation_id,
            action=action,
            prompt_modifications=prompt_modifications,
            layout_modifications=layout_modifications,
            condition_modifications=condition_modifications,
            provider_modifications=provider_modifications,
            reason="Rule-based repair proposal for planning structure issues.",
            metadata={
                "source_agent": self.provider_name,
                "provider_version": self.provider_version,
                "rules_version": RULE_VERSION,
                "problem_codes": [problem.code for problem in evaluation.problems],
                "refine_round": evaluation.metadata.get("refine_round", 0),
            },
        )
