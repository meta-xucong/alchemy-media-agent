"""Deterministic planning scorers for V3.0."""

from __future__ import annotations

from ..condition_engine.providers import ProviderCapabilities
from ..creative_core.rules import RULE_VERSION, platform_aspect_ratio, stable_id
from ..schemas import (
    AssetSpec,
    BrandProfile,
    CandidateResult,
    CommercialBrief,
    CreativePlan,
    EvaluationProblem,
    EvaluationReport,
    LayoutPlan,
    PromptCompilationResult,
    Recommendation,
    Severity,
    TextRenderingMode,
)


FORMULA_VERSION = "v3.0-eval-formula-001"
ACCEPT_THRESHOLD = 0.78
RETRY_THRESHOLD = 0.55


def weighted_overall(
    aesthetic_score: float,
    commercial_score: float,
    brand_consistency_score: float,
    layout_score: float,
    text_region_score: float,
    platform_fit_score: float,
) -> float:
    return round(
        aesthetic_score * 0.20
        + commercial_score * 0.25
        + brand_consistency_score * 0.20
        + layout_score * 0.15
        + text_region_score * 0.10
        + platform_fit_score * 0.10,
        4,
    )


class RuleBasedPlanningScorer:
    scorer_name = "rule_based_planning_scorer"
    scorer_version = "v3.0-foundation"

    def score(
        self,
        asset_spec: AssetSpec,
        commercial_brief: CommercialBrief,
        brand_profile: BrandProfile,
        creative_plan: CreativePlan,
        layout_plan: LayoutPlan,
        prompt_compilation: PromptCompilationResult,
    ) -> EvaluationReport:
        problems = self._problems(asset_spec, layout_plan, prompt_compilation, brand_profile)
        aesthetic_score = 0.75 if creative_plan.visual_direction else 0.50
        commercial_score = 0.78 if commercial_brief.business_goal and commercial_brief.commercial_hooks else 0.60
        style_text = " ".join(prompt_compilation.style_notes + [prompt_compilation.visual_prompt])
        brand_consistency_score = (
            0.78 if brand_profile and any(tone in style_text for tone in brand_profile.visual_tone) else 0.65
        )
        layout_score = 0.80 if layout_plan.product_area else 0.55
        text_region_score = (
            0.76
            if layout_plan.text_rendering in {TextRenderingMode.MODEL_TEXT_ALLOWED, TextRenderingMode.NO_TEXT}
            and prompt_compilation.provider_notes.get("text_rendering_owner") == "image_provider"
            else 0.50
        )
        platform_fit_score = 0.82 if asset_spec.aspect_ratio == platform_aspect_ratio(asset_spec.platform) else 0.55
        if any(problem.severity == Severity.HARD_FAILURE for problem in problems):
            recommendation = Recommendation.REJECT
        else:
            recommendation = Recommendation.PLANNING_ONLY
        return EvaluationReport(
            evaluation_id=stable_id("evaluation", asset_spec.asset_id, prompt_compilation.prompt_compilation_id),
            asset_id=asset_spec.asset_id,
            aesthetic_score=aesthetic_score,
            commercial_score=commercial_score,
            brand_consistency_score=brand_consistency_score,
            layout_score=layout_score,
            text_region_score=text_region_score,
            platform_fit_score=platform_fit_score,
            overall_score=weighted_overall(
                aesthetic_score,
                commercial_score,
                brand_consistency_score,
                layout_score,
                text_region_score,
                platform_fit_score,
            ),
            recommendation=recommendation,
            problems=problems,
            metadata={
                "source_agent": self.scorer_name,
                "scorer_names": [self.scorer_name],
                "scorer_versions": [self.scorer_version],
                "rule_version": RULE_VERSION,
                "formula_version": FORMULA_VERSION,
                "thresholds": {"accept": 0.78, "retry": 0.55},
                "refine_round": 0,
                "planning_only": True,
            },
        )

    def _problems(
        self,
        asset_spec: AssetSpec,
        layout_plan: LayoutPlan,
        prompt_compilation: PromptCompilationResult,
        brand_profile: BrandProfile,
    ) -> list[EvaluationProblem]:
        problems: list[EvaluationProblem] = []
        if not layout_plan.product_area:
            problems.append(
                EvaluationProblem(
                    code="missing_product_area",
                    message="LayoutPlan is missing product or subject area.",
                    severity=Severity.HARD_FAILURE,
                    repair_hint="Strengthen the requested product or subject visibility in the provider-native creative brief.",
                )
            )
        if asset_spec.requires_text_overlay:
            problems.append(
                EvaluationProblem(
                    code="legacy_external_overlay_requested",
                    message="A legacy external-overlay flag was supplied; new jobs must use provider-native image text or no text.",
                    severity=Severity.WARNING,
                    repair_hint="Remove the overlay requirement and express approved copy in the provider-native creative brief.",
                )
            )
        if asset_spec.aspect_ratio != platform_aspect_ratio(asset_spec.platform):
            problems.append(
                EvaluationProblem(
                    code="platform_ratio_mismatch",
                    message="Asset aspect ratio does not match first-pass platform default.",
                    severity=Severity.ERROR,
                    repair_hint="Use platform default aspect ratio.",
                )
            )
        if prompt_compilation.provider_notes.get("text_rendering_owner") != "image_provider":
            problems.append(
                EvaluationProblem(
                    code="legacy_text_rendering_contract",
                    message="Prompt does not declare the image provider as the owner of final image text.",
                    severity=Severity.WARNING,
                    repair_hint="Use provider-native text or no-text policy; do not request a local overlay.",
                )
            )
        if brand_profile.visual_tone and not prompt_compilation.style_notes:
            problems.append(
                EvaluationProblem(
                    code="brand_style_missing",
                    message="Brand style was available but not included in prompt compilation.",
                    severity=Severity.WARNING,
                    repair_hint="Inject BrandProfile visual tone into style notes.",
                )
            )
        return problems


class MockScoringProvider(RuleBasedPlanningScorer):
    scorer_name = "mock_scoring_provider"
    scorer_version = "v3.2-generation-loop-mvp"

    def score_candidate(
        self,
        candidate: CandidateResult,
        asset_spec: AssetSpec,
        commercial_brief: CommercialBrief,
        brand_profile: BrandProfile,
        creative_plan: CreativePlan,
        layout_plan: LayoutPlan,
        prompt_compilation: PromptCompilationResult,
        refine_round: int = 0,
        retry_budget_exhausted: bool = False,
        evaluation_policy: dict | None = None,
    ) -> EvaluationReport:
        problems = self._problems(asset_spec, layout_plan, prompt_compilation, brand_profile)
        for code in candidate.metadata.get("forced_problem_codes", []):
            problem = self._problem_from_code(code)
            if problem and all(existing.code != problem.code for existing in problems):
                problems.append(problem)

        problem_codes = _problem_codes(problems)
        mock_quality = float(candidate.metadata.get("mock_quality_score", 0.78))
        aesthetic_score = _clamp(mock_quality if creative_plan.visual_direction else min(mock_quality, 0.50))
        commercial_score = _clamp(
            mock_quality
            if commercial_brief.business_goal and commercial_brief.commercial_hooks and "commercial_hook_missing" not in problem_codes
            else min(mock_quality, 0.60)
        )
        style_text = " ".join(prompt_compilation.style_notes + [prompt_compilation.visual_prompt])
        brand_present = bool(brand_profile and any(tone in style_text for tone in brand_profile.visual_tone))
        brand_consistency_score = _clamp(
            mock_quality if brand_present and "brand_style_missing" not in problem_codes else min(mock_quality, 0.62)
        )
        layout_score = _clamp(mock_quality if layout_plan.product_area and "missing_product_area" not in problem_codes else min(mock_quality, 0.45))
        text_region_score = _clamp(
            mock_quality
            if layout_plan.text_rendering in {TextRenderingMode.MODEL_TEXT_ALLOWED, TextRenderingMode.NO_TEXT}
            and prompt_compilation.provider_notes.get("text_rendering_owner") == "image_provider"
            and "legacy_text_rendering_contract" not in problem_codes
            else min(mock_quality, 0.50)
        )
        platform_fit_score = _clamp(
            mock_quality if asset_spec.aspect_ratio == platform_aspect_ratio(asset_spec.platform) else min(mock_quality, 0.55)
        )
        if evaluation_policy:
            commercial_score = _clamp(commercial_score + float(evaluation_policy.get("commercial_score_delta", 0.0)))
            brand_consistency_score = _clamp(
                brand_consistency_score + float(evaluation_policy.get("brand_consistency_score_delta", 0.0))
            )
            layout_score = _clamp(layout_score + float(evaluation_policy.get("layout_score_delta", 0.0)))

        overall_score = weighted_overall(
            aesthetic_score,
            commercial_score,
            brand_consistency_score,
            layout_score,
            text_region_score,
            platform_fit_score,
        )
        recommendation = self._recommendation(overall_score, problems, retry_budget_exhausted)
        if recommendation == Recommendation.RETRY and retry_budget_exhausted:
            problems.append(
                EvaluationProblem(
                    code="score_below_threshold",
                    message="Retry budget is exhausted before candidate reached acceptance threshold.",
                    severity=Severity.ERROR,
                    repair_hint="Package best available candidate with warnings or ask for manual review.",
                    metadata={"retry_budget_exhausted": True},
                )
            )
            recommendation = Recommendation.REJECT

        return EvaluationReport(
            evaluation_id=stable_id("evaluation", asset_spec.asset_id, candidate.candidate_id, refine_round),
            candidate_id=candidate.candidate_id,
            asset_id=asset_spec.asset_id,
            aesthetic_score=aesthetic_score,
            commercial_score=commercial_score,
            brand_consistency_score=brand_consistency_score,
            layout_score=layout_score,
            text_region_score=text_region_score,
            platform_fit_score=platform_fit_score,
            overall_score=overall_score,
            recommendation=recommendation,
            problems=problems,
            metadata={
                "source_agent": self.scorer_name,
                "scorer_names": [self.scorer_name],
                "scorer_versions": [self.scorer_version],
                "rule_version": RULE_VERSION,
                "formula_version": FORMULA_VERSION,
                "thresholds": {"accept": ACCEPT_THRESHOLD, "retry": RETRY_THRESHOLD},
                "refine_round": refine_round,
                "planning_only": False,
                "candidate_provider": candidate.provider,
                "evaluation_policy": evaluation_policy or {},
            },
        )

    def _recommendation(
        self,
        overall_score: float,
        problems: list[EvaluationProblem],
        retry_budget_exhausted: bool,
    ) -> Recommendation:
        if any(problem.severity == Severity.HARD_FAILURE for problem in problems):
            return Recommendation.REJECT if retry_budget_exhausted else Recommendation.RETRY
        if overall_score >= ACCEPT_THRESHOLD:
            return Recommendation.ACCEPT
        if overall_score >= RETRY_THRESHOLD:
            return Recommendation.REJECT if retry_budget_exhausted else Recommendation.RETRY
        return Recommendation.REJECT

    def _problem_from_code(self, code: str) -> EvaluationProblem | None:
        problem_map: dict[str, EvaluationProblem] = {
            "missing_product_area": EvaluationProblem(
                code="missing_product_area",
                message="Candidate does not preserve a clear product or subject hero area.",
                severity=Severity.HARD_FAILURE,
                repair_hint="Regenerate with clearer product or subject visibility from the creative brief.",
            ),
            "legacy_external_overlay_requested": EvaluationProblem(
                code="legacy_external_overlay_requested",
                message="Candidate originated from a retired external-overlay rendering request.",
                severity=Severity.WARNING,
                repair_hint="Regenerate through the provider-native complete-image path.",
            ),
            "legacy_text_rendering_contract": EvaluationProblem(
                code="legacy_text_rendering_contract",
                message="Candidate was planned with a retired external-text contract.",
                severity=Severity.WARNING,
                repair_hint="Use final-pixel provider-native text review instead of an external overlay.",
            ),
            "provider_native_text_fidelity_failure": EvaluationProblem(
                code="provider_native_text_fidelity_failure",
                message="Final pixels do not faithfully render the requested provider-native text.",
                severity=Severity.WARNING,
                repair_hint="Regenerate through the image provider with the approved literal text and re-check final pixels.",
            ),
            "platform_ratio_mismatch": EvaluationProblem(
                code="platform_ratio_mismatch",
                message="Candidate ratio does not fit the selected platform.",
                severity=Severity.ERROR,
                repair_hint="Replace aspect ratio with the platform default.",
            ),
            "brand_style_missing": EvaluationProblem(
                code="brand_style_missing",
                message="Candidate does not carry enough brand style evidence.",
                severity=Severity.WARNING,
                repair_hint="Inject brand tone and palette into prompt and condition notes.",
            ),
            "commercial_hook_missing": EvaluationProblem(
                code="commercial_hook_missing",
                message="Candidate lacks a clear commercial hook or conversion cue.",
                severity=Severity.WARNING,
                repair_hint="Strengthen the commercial story through the complete provider-rendered image.",
            ),
            "provider_failure": EvaluationProblem(
                code="provider_failure",
                message="Generation provider returned a failed candidate.",
                severity=Severity.HARD_FAILURE,
                repair_hint="Discard failed candidate and retry the selected provider within the bounded retry policy.",
            ),
        }
        return problem_map.get(code)


class ImageRewardProvider(MockScoringProvider):
    """Optional scoring sidecar facade with deterministic offline fallback behavior."""

    scorer_name = "image_reward_provider"
    scorer_version = "v3.4-reference-conditioning-sidecars"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.scorer_name,
            version=self.scorer_version,
            supports_scoring=True,
            requires_gpu=True,
            requires_network=False,
            is_deterministic=False,
            metadata={
                "optional": True,
                "runtime_mode": "sidecar_unavailable",
                "normalized_output": "EvaluationReport",
            },
        )

    def is_available(self) -> bool:
        return False

    def health_check(self) -> dict:
        return {
            "provider_name": self.scorer_name,
            "provider_version": self.scorer_version,
            "available": False,
            "runtime_mode": "sidecar_unavailable",
            "warnings": ["Optional scoring sidecar is not configured; deterministic mock scorer remains available."],
        }


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _problem_codes(problems: list[EvaluationProblem]) -> set[str]:
    return {problem.code for problem in problems}
