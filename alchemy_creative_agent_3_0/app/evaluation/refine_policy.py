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
                prompt_modifications.append(
                    "Regenerate the complete image through the image provider; let the creative brief determine natural composition instead of reserving an external text region"
                )
            elif problem.code in {"fake_text_risk", "provider_native_text_fidelity_failure"}:
                prompt_modifications.append(
                    "Regenerate through the provider-native complete-image path and verify final-pixel text fidelity; do not add a local overlay"
                )
            elif problem.code in {"legacy_external_overlay_requested", "legacy_text_rendering_contract"}:
                prompt_modifications.append(
                    "Remove the retired external-text contract and regenerate through the provider-native complete-image path"
                )
            elif problem.code == "platform_ratio_mismatch":
                layout_modifications.append("replace aspect ratio with platform default")
            elif problem.code == "brand_style_missing":
                prompt_modifications.append("inject BrandProfile visual tone and color palette")
                condition_modifications.append("enable style condition if references exist")
            elif problem.code == "missing_product_area":
                prompt_modifications.append("Strengthen the requested product or subject visibility in the provider-native creative brief")
            elif problem.code == "commercial_hook_missing":
                prompt_modifications.append(
                    "Strengthen the commercial story and conversion cue from CommercialBrief through the complete image, without a fixed CTA region"
                )
            elif problem.code == "provider_failure":
                provider_modifications.append("discard failed candidate and retry the selected image provider within the bounded retry policy")
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
