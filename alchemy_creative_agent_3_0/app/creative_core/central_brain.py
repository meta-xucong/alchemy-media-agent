"""Central Creative Brain for V3.0 planning foundation."""

from __future__ import annotations

from .context import PipelineContext
from .rules import RULE_VERSION, stable_id
from ..agents import (
    AssetPackagerAgent,
    BrandMemoryAgent,
    CommercialStrategyAgent,
    CreativeDirectorAgent,
    GenerationRouterAgent,
    IntentAgent,
    LayoutAgent,
    PromptCompilerAgent,
    SeriesPlannerAgent,
)
from ..brand_memory.profile_service import BrandProfileService
from ..evaluation import MockScoringProvider, RuleBasedPlanningScorer, RuleBasedRefinementProvider
from ..generation_router import GenerationRequest, GenerationRouter, select_best_candidate
from ..schemas import CandidateResult, EvaluationReport, PlanningResult, ProviderStrategy, Recommendation, ReferenceAsset
from ..vertical_agents import VerticalAgentRegistry


class CentralCreativeBrain:
    """Orchestrates the V3 planning-only commercial creative pipeline."""

    def __init__(
        self,
        brand_profile_service: BrandProfileService | None = None,
        vertical_registry: VerticalAgentRegistry | None = None,
    ) -> None:
        self.intent_agent = IntentAgent()
        self.commercial_strategy_agent = CommercialStrategyAgent()
        self.brand_memory_agent = BrandMemoryAgent(brand_profile_service)
        self.creative_director_agent = CreativeDirectorAgent()
        self.series_planner_agent = SeriesPlannerAgent()
        self.layout_agent = LayoutAgent()
        self.prompt_compiler_agent = PromptCompilerAgent()
        self.generation_router_agent = GenerationRouterAgent()
        self.asset_packager_agent = AssetPackagerAgent()
        self.scorer = RuleBasedPlanningScorer()
        self.generation_scorer = MockScoringProvider()
        self.refinement_provider = RuleBasedRefinementProvider()
        self.generation_router = GenerationRouter()
        self.vertical_registry = vertical_registry or VerticalAgentRegistry()

    def run_creative_planning(self, user_input: str, optional_brand_id: str | None = None) -> PlanningResult:
        context = self._create_base_context(user_input, optional_brand_id)
        job = context.creative_job
        brand_profile = context.brand_profile
        selected_pack = context.selected_vertical_pack

        for asset in context.series_plan.assets:
            layout_plan = self.layout_agent.create_layout_plan(
                job,
                asset,
                context.commercial_brief,
                context.creative_plan,
                brand_profile,
            ).output
            layout_plan = selected_pack.refine_layout_plan(context, layout_plan)
            prompt = self.prompt_compiler_agent.compile_prompt(
                context.commercial_brief,
                context.creative_plan,
                layout_plan,
                brand_profile,
            ).output
            prompt = selected_pack.refine_prompt_compilation(context, prompt)
            condition_plan, generation_plan = self.generation_router_agent.create_generation_contracts(
                asset,
                brand_profile,
                prompt,
                layout_plan=layout_plan,
                creative_plan=context.creative_plan,
            ).output
            evaluation = self.scorer.score(
                asset_spec=asset,
                commercial_brief=context.commercial_brief,
                brand_profile=brand_profile,
                creative_plan=context.creative_plan,
                layout_plan=layout_plan,
                prompt_compilation=prompt,
            )
            context.layout_plans.append(layout_plan)
            context.prompt_compilations.append(prompt)
            context.condition_plans.append(condition_plan)
            context.generation_plans.append(generation_plan)
            context.evaluation_reports.append(evaluation)

        memory_update = self.brand_memory_agent.propose_memory_update(
            brand_profile,
            accepted_asset_ids=[asset.asset_id for asset in context.series_plan.assets],
            style_tags=context.creative_plan.color_strategy + context.commercial_brief.visual_tone,
            planning_only=True,
        )
        asset_pack = self.asset_packager_agent.create_asset_pack(
            job,
            brand_profile,
            context.series_plan,
            context.layout_plans,
            context.prompt_compilations,
            context.evaluation_reports,
            memory_update,
        ).output
        context.asset_pack = asset_pack

        return PlanningResult(
            planning_result_id=stable_id("planning_result", job.job_id, context.series_plan.series_plan_id),
            creative_job=job,
            commercial_brief=context.commercial_brief,
            brand_profile=brand_profile,
            creative_plan=context.creative_plan,
            series_plan=context.series_plan,
            layout_plans=context.layout_plans,
            prompt_compilations=context.prompt_compilations,
            condition_plans=context.condition_plans,
            generation_plans=context.generation_plans,
            evaluation_reports=context.evaluation_reports,
            asset_pack=asset_pack,
            metadata={
                "source_agent": "CentralCreativeBrain",
                "rules_version": RULE_VERSION,
                "selected_vertical_pack": selected_pack.name,
                "vertical_pack_metadata": selected_pack.metadata(),
                "planning_only": True,
                "v3_independent_runtime": True,
            },
        )

    def run_generation_loop(
        self,
        user_input: str,
        optional_brand_id: str | None = None,
        mock_profile: str = "balanced",
        apply_memory_update: bool = False,
    ) -> PlanningResult:
        context = self._create_base_context(user_input, optional_brand_id)
        job = context.creative_job
        brand_profile = context.brand_profile
        selected_pack = context.selected_vertical_pack
        pack_warnings: list[str] = []

        for asset in context.series_plan.assets:
            layout_plan = self.layout_agent.create_layout_plan(
                job,
                asset,
                context.commercial_brief,
                context.creative_plan,
                brand_profile,
            ).output
            layout_plan = selected_pack.refine_layout_plan(context, layout_plan)
            prompt = self.prompt_compiler_agent.compile_prompt(
                context.commercial_brief,
                context.creative_plan,
                layout_plan,
                brand_profile,
            ).output
            prompt = selected_pack.refine_prompt_compilation(context, prompt)
            condition_plan, generation_plan = self.generation_router_agent.create_generation_contracts(
                asset,
                brand_profile,
                prompt,
                provider_strategy=ProviderStrategy.MOCK_GENERATION,
                layout_plan=layout_plan,
                creative_plan=context.creative_plan,
            ).output
            generation_plan.metadata = {**generation_plan.metadata, "mock_profile": mock_profile}
            context.layout_plans.append(layout_plan)
            context.prompt_compilations.append(prompt)
            context.condition_plans.append(condition_plan)
            context.generation_plans.append(generation_plan)

            selected_candidate, selected_evaluation, asset_warnings = self._run_asset_generation_loop(
                context,
                asset,
                layout_plan,
                prompt,
                condition_plan,
                generation_plan,
            )
            pack_warnings.extend(asset_warnings)
            if selected_candidate is not None:
                context.selected_candidates.append(selected_candidate)
            if selected_evaluation is not None and selected_evaluation.recommendation != Recommendation.ACCEPT:
                pack_warnings.append(
                    f"asset {asset.asset_id} packaged with {selected_evaluation.recommendation} recommendation"
                )

        accepted_candidates = [
            candidate
            for candidate in context.selected_candidates
            if self._evaluation_for_candidate(context.evaluation_reports, candidate)
            and self._evaluation_for_candidate(context.evaluation_reports, candidate).recommendation == Recommendation.ACCEPT
        ]
        memory_update = None
        if accepted_candidates:
            assets_by_id = {asset.asset_id: asset for asset in context.series_plan.assets}
            memory_update = self.brand_memory_agent.propose_memory_update(
                brand_profile,
                accepted_asset_ids=[candidate.asset_id for candidate in accepted_candidates],
                style_tags=context.creative_plan.color_strategy + context.commercial_brief.visual_tone,
                planning_only=False,
            )
            memory_update.new_reference_assets = [
                ReferenceAsset(
                    asset_id=f"ref_{candidate.candidate_id}",
                    asset_type="accepted_mock_candidate",
                    source="v3_generation_loop",
                    purpose="style continuation reference proposal",
                    style_tags=list(dict.fromkeys(context.commercial_brief.visual_tone + context.creative_plan.color_strategy)),
                    uri=candidate.uri,
                    score=self._evaluation_for_candidate(context.evaluation_reports, candidate).overall_score,
                    metadata={
                        "candidate_id": candidate.candidate_id,
                        "asset_id": candidate.asset_id,
                        "platform": assets_by_id[candidate.asset_id].platform.value,
                        "provider": candidate.provider,
                        "selected_vertical_pack": selected_pack.name,
                    },
                )
                for candidate in accepted_candidates
                if candidate.asset_id in assets_by_id
            ]
            memory_update.metadata = {
                **memory_update.metadata,
                "candidate_rejected": False,
                "selected_candidate_ids": [candidate.candidate_id for candidate in accepted_candidates],
                "apply_configured": apply_memory_update,
            }
            if apply_memory_update:
                self.brand_memory_agent.profile_service.apply_memory_update(memory_update)

        asset_pack = self.asset_packager_agent.create_generated_asset_pack(
            job,
            brand_profile,
            context.series_plan,
            context.layout_plans,
            context.prompt_compilations,
            context.selected_candidates,
            context.evaluation_reports,
            memory_update,
            warnings=list(dict.fromkeys(pack_warnings)),
        ).output
        context.asset_pack = asset_pack

        return PlanningResult(
            planning_result_id=stable_id("generation_result", job.job_id, context.series_plan.series_plan_id),
            creative_job=job,
            commercial_brief=context.commercial_brief,
            brand_profile=brand_profile,
            creative_plan=context.creative_plan,
            series_plan=context.series_plan,
            layout_plans=context.layout_plans,
            prompt_compilations=context.prompt_compilations,
            condition_plans=context.condition_plans,
            generation_plans=context.generation_plans,
            evaluation_reports=context.evaluation_reports,
            asset_pack=asset_pack,
            metadata={
                "source_agent": "CentralCreativeBrain",
                "rules_version": RULE_VERSION,
                "selected_vertical_pack": selected_pack.name,
                "vertical_pack_metadata": selected_pack.metadata(),
                "vertical_evaluation_policy": selected_pack.refine_evaluation_policy(context),
                "planning_only": False,
                "candidate_loop": True,
                "candidate_count": len(context.candidate_results),
                "selected_candidate_ids": [candidate.candidate_id for candidate in context.selected_candidates],
                "refinement_plan_count": len(context.refinement_plans),
                "refinement_plans": [plan.model_dump(mode="json") for plan in context.refinement_plans],
                "v3_independent_runtime": True,
            },
        )

    def _create_base_context(self, user_input: str, optional_brand_id: str | None) -> PipelineContext:
        context = PipelineContext(
            user_input=user_input,
            optional_brand_id=optional_brand_id,
            metadata={"source_agent": "CentralCreativeBrain", "rules_version": RULE_VERSION},
        )
        job = self.intent_agent.create_job(user_input, optional_brand_id=optional_brand_id).output
        brief = self.commercial_strategy_agent.create_brief(job).output
        selected_pack = self.vertical_registry.select_pack(job, brief)
        job.metadata["selected_vertical_pack"] = selected_pack.name
        brief.metadata["selected_vertical_pack"] = selected_pack.name
        context.creative_job = job
        context.commercial_brief = brief
        context.commercial_brief = selected_pack.refine_commercial_brief(context)
        context.selected_vertical_pack = selected_pack

        brand_profile = self.brand_memory_agent.resolve_profile(job, context.commercial_brief).output
        creative_plan = self.creative_director_agent.create_plan(job, context.commercial_brief, brand_profile).output
        context.brand_profile = brand_profile
        context.creative_plan = creative_plan
        context.creative_plan = selected_pack.refine_creative_plan(context)

        series_plan = self.series_planner_agent.create_series_plan(job, context.commercial_brief, brand_profile).output
        context.series_plan = series_plan
        context.series_plan = selected_pack.refine_series_plan(context)
        return context

    def _run_asset_generation_loop(
        self,
        context: PipelineContext,
        asset,
        layout_plan,
        prompt,
        condition_plan,
        generation_plan,
    ) -> tuple[CandidateResult | None, EvaluationReport | None, list[str]]:
        selected_candidate: CandidateResult | None = None
        selected_evaluation: EvaluationReport | None = None
        warnings: list[str] = []
        for refine_round in range(generation_plan.max_refine_rounds + 1):
            request = GenerationRequest(
                asset_spec=asset,
                layout_plan=layout_plan,
                prompt_compilation=prompt,
                condition_plan=condition_plan,
                generation_plan=generation_plan,
                metadata={
                    "refine_round": refine_round,
                    "mock_profile": generation_plan.metadata.get("mock_profile", "balanced"),
                },
            )
            response = self.generation_router.generate(request)
            warnings.extend(response.warnings)
            round_evaluations: list[EvaluationReport] = []
            retry_budget_exhausted = refine_round >= generation_plan.max_refine_rounds
            evaluation_policy = (
                context.selected_vertical_pack.refine_evaluation_policy(context)
                if context.selected_vertical_pack
                else {"pack": "none", "mode": "noop"}
            )
            for candidate in response.candidates:
                evaluation = self.generation_scorer.score_candidate(
                    candidate=candidate,
                    asset_spec=asset,
                    commercial_brief=context.commercial_brief,
                    brand_profile=context.brand_profile,
                    creative_plan=context.creative_plan,
                    layout_plan=layout_plan,
                    prompt_compilation=prompt,
                    refine_round=refine_round,
                    retry_budget_exhausted=retry_budget_exhausted,
                    evaluation_policy=evaluation_policy,
                )
                round_evaluations.append(evaluation)
                context.evaluation_reports.append(evaluation)
            context.candidate_results.extend(response.candidates)
            selected_candidate, selected_evaluation = select_best_candidate(response.candidates, round_evaluations)
            if selected_evaluation is None:
                warnings.append(f"asset {asset.asset_id} produced no evaluated candidates")
                break
            if selected_evaluation.recommendation == Recommendation.ACCEPT:
                break
            if retry_budget_exhausted:
                warnings.append(f"asset {asset.asset_id} exhausted refine budget")
                break
            refinement_plan = self.refinement_provider.propose_refinement(selected_evaluation)
            if refinement_plan is None:
                warnings.append(f"asset {asset.asset_id} had no available refinement plan")
                break
            refinement_plan.metadata = {
                **refinement_plan.metadata,
                "next_refine_round": refine_round + 1,
                "selected_candidate_id": selected_candidate.candidate_id if selected_candidate else None,
            }
            context.refinement_plans.append(refinement_plan)
            self._apply_refinement_metadata(generation_plan, prompt, layout_plan, refinement_plan, refine_round + 1)
        return selected_candidate, selected_evaluation, warnings

    def _apply_refinement_metadata(self, generation_plan, prompt, layout_plan, refinement_plan, next_round: int) -> None:
        history_entry = {
            "refinement_plan_id": refinement_plan.refinement_plan_id,
            "source_evaluation_id": refinement_plan.source_evaluation_id,
            "prompt_modifications": refinement_plan.prompt_modifications,
            "layout_modifications": refinement_plan.layout_modifications,
            "condition_modifications": refinement_plan.condition_modifications,
            "provider_modifications": refinement_plan.provider_modifications,
            "next_refine_round": next_round,
        }
        generation_plan.metadata = {
            **generation_plan.metadata,
            "refine_round": next_round,
            "refinement_history": [*generation_plan.metadata.get("refinement_history", []), history_entry],
        }
        prompt.metadata = {
            **prompt.metadata,
            "refinement_history": [*prompt.metadata.get("refinement_history", []), history_entry],
        }
        layout_plan.metadata = {
            **layout_plan.metadata,
            "refinement_history": [*layout_plan.metadata.get("refinement_history", []), history_entry],
        }

    def _evaluation_for_candidate(
        self,
        reports: list[EvaluationReport],
        candidate: CandidateResult,
    ) -> EvaluationReport | None:
        matches = [report for report in reports if report.candidate_id == candidate.candidate_id]
        if not matches:
            return None
        return sorted(matches, key=lambda report: report.metadata.get("refine_round", 0), reverse=True)[0]
