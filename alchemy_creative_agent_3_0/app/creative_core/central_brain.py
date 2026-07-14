"""Central Creative Brain for V3.0 planning foundation."""

from __future__ import annotations

from typing import Any

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


def _bounded_requested_image_count(value: object) -> int:
    try:
        return max(1, int(value or 2))
    except (TypeError, ValueError):
        return 2


class CentralCreativeBrain:
    """Orchestrates the V3 planning-only commercial creative pipeline."""

    def __init__(
        self,
        brand_profile_service: BrandProfileService | None = None,
        vertical_registry: VerticalAgentRegistry | None = None,
        generation_router: GenerationRouter | None = None,
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
        self.generation_router = generation_router or GenerationRouter()
        self.vertical_registry = vertical_registry or VerticalAgentRegistry()

    def run_creative_planning(
        self,
        user_input: str,
        optional_brand_id: str | None = None,
        optional_template_id: str | None = None,
        runtime_metadata: dict | None = None,
    ) -> PlanningResult:
        context = self._create_base_context(
            user_input,
            optional_brand_id,
            optional_template_id=optional_template_id,
            runtime_metadata=runtime_metadata,
        )
        job = context.creative_job
        brand_profile = context.brand_profile
        selected_pack = context.selected_vertical_pack

        for index, asset in enumerate(context.series_plan.assets):
            asset = self._asset_with_mode_role(context, asset, index)
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
                llm_brain=self._llm_brain_metadata(context),
            ).output
            prompt = selected_pack.refine_prompt_compilation(context, prompt)
            condition_plan, generation_plan = self.generation_router_agent.create_generation_contracts(
                asset,
                brand_profile,
                prompt,
                layout_plan=layout_plan,
                creative_plan=context.creative_plan,
            ).output
            mode_role_recipe = self._mode_role_recipe_for_asset(context, asset, index)
            role_plan = self._role_specific_generation_plan_metadata(context)
            mode_policy = self._mode_execution_policy_metadata(context)
            generation_plan.metadata = {
                **generation_plan.metadata,
                "job_id": job.job_id,
                "uploaded_assets": context.metadata.get("uploaded_assets", []),
                "reference_assets": context.metadata.get("reference_assets", []),
                "shared_capabilities": context.metadata.get("shared_capabilities", {}),
                "visual_cluster": self._visual_cluster_metadata(context),
                "mode_execution_policy": mode_policy,
                "role_specific_generation_plan": role_plan,
                "mode_role_recipe": mode_role_recipe,
                "mode_role_key": mode_role_recipe.get("role_key") if mode_role_recipe else None,
                "mode_role_label": mode_role_recipe.get("label") if mode_role_recipe else None,
                "output_index": index,
                "project_id": context.metadata.get("project_id"),
                "template_id": context.metadata.get("template_id"),
                "scenario_id": context.metadata.get("scenario_id"),
                "visual_auto_retry_active": context.metadata.get("visual_auto_retry_active", False),
                "visual_auto_retry_attempt": context.metadata.get("visual_auto_retry_attempt"),
                "retry_attempt": context.metadata.get("retry_attempt"),
                "visual_retry_reason_codes": context.metadata.get("visual_retry_reason_codes", []),
                "visual_retry_patch": context.metadata.get("visual_retry_patch", {}),
                "industry": context.commercial_brief.industry.value if context.commercial_brief else None,
                "user_input": context.user_input,
                "normalized_input": context.commercial_brief.metadata.get("normalized_input")
                if context.commercial_brief
                else context.user_input,
            }
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
                "llm_brain": self._llm_brain_metadata(context),
                "scenario_id": context.metadata.get("scenario_id"),
                "template_id": context.metadata.get("template_id"),
                "shared_capabilities": context.metadata.get("shared_capabilities", {}),
                "visual_cluster": self._visual_cluster_metadata(context),
                "requested_image_count": len(context.series_plan.assets) if context.series_plan else None,
                "effective_variation_mode": context.metadata.get("effective_variation_mode")
                or context.metadata.get("variation_mode"),
            },
        )

    def run_generation_loop(
        self,
        user_input: str,
        optional_brand_id: str | None = None,
        optional_template_id: str | None = None,
        mock_profile: str = "balanced",
        apply_memory_update: bool = False,
        provider_strategy: ProviderStrategy = ProviderStrategy.MOCK_GENERATION,
        runtime_metadata: dict | None = None,
    ) -> PlanningResult:
        context = self._create_base_context(
            user_input,
            optional_brand_id,
            optional_template_id=optional_template_id,
            runtime_metadata=runtime_metadata,
        )
        job = context.creative_job
        brand_profile = context.brand_profile
        selected_pack = context.selected_vertical_pack
        pack_warnings: list[str] = []
        use_mock_generation = provider_strategy == ProviderStrategy.MOCK_GENERATION
        explicit_references_present = self._has_explicit_user_reference_assets(context)
        auto_identity_anchor_enabled = (
            not use_mock_generation
            and not explicit_references_present
            and self._is_human_identity_suite_context(context)
            and self._generated_output_reference_chain_allowed(context)
        )
        auto_identity_anchor_reference: dict[str, Any] | None = None
        role_execution_records: list[dict[str, Any]] = []
        require_independent_role_terminal_states = self._requires_independent_role_terminal_states(context)

        for index, asset in enumerate(context.series_plan.assets):
            asset = self._asset_with_mode_role(context, asset, index)
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
                llm_brain=self._llm_brain_metadata(context),
            ).output
            prompt = selected_pack.refine_prompt_compilation(context, prompt)
            condition_plan, generation_plan = self.generation_router_agent.create_generation_contracts(
                asset,
                brand_profile,
                prompt,
                provider_strategy=provider_strategy,
                layout_plan=layout_plan,
                creative_plan=context.creative_plan,
            ).output
            mode_role_recipe = self._mode_role_recipe_for_asset(context, asset, index)
            role_plan = self._role_specific_generation_plan_metadata(context)
            mode_policy = self._mode_execution_policy_metadata(context)
            generation_plan.metadata = {
                **generation_plan.metadata,
                "mock_profile": mock_profile,
                "job_id": job.job_id,
                "quality_mode": context.metadata.get("quality_mode", "standard"),
                "uploaded_assets": context.metadata.get("uploaded_assets", []),
                "reference_assets": context.metadata.get("reference_assets", []),
                "llm_brain": self._llm_brain_metadata(context),
                "shared_capabilities": context.metadata.get("shared_capabilities", {}),
                "visual_cluster": self._visual_cluster_metadata(context),
                # The Scenario Runtime freezes these five records before the
                # Central Brain starts materializing assets.  Keep the full
                # execution envelope with every provider request so enforced
                # providers do not fall back to mutable cluster/metadata
                # fields while rendering an individual asset.
                "normalized_v3_job_intent": context.metadata.get("normalized_v3_job_intent"),
                "template_deliverable_plan": context.metadata.get("template_deliverable_plan"),
                "resolved_constraint_ledger": context.metadata.get("resolved_constraint_ledger"),
                "capability_execution_envelope": context.metadata.get("capability_execution_envelope"),
                "requested_image_count": _bounded_requested_image_count(context.metadata.get("requested_image_count")),
                "requested_image_size": context.metadata.get("requested_image_size"),
                "mode_execution_policy": mode_policy,
                "role_specific_generation_plan": role_plan,
                "mode_role_recipe": mode_role_recipe,
                "mode_role_key": mode_role_recipe.get("role_key") if mode_role_recipe else None,
                "mode_role_label": mode_role_recipe.get("label") if mode_role_recipe else None,
                "output_index": index,
                "project_id": context.metadata.get("project_id"),
                "template_id": context.metadata.get("template_id"),
                "scenario_id": context.metadata.get("scenario_id"),
                "visual_auto_retry_active": context.metadata.get("visual_auto_retry_active", False),
                "visual_auto_retry_attempt": context.metadata.get("visual_auto_retry_attempt"),
                "retry_attempt": context.metadata.get("retry_attempt"),
                "visual_retry_reason_codes": context.metadata.get("visual_retry_reason_codes", []),
                "visual_retry_patch": context.metadata.get("visual_retry_patch", {}),
                "industry": context.commercial_brief.industry.value if context.commercial_brief else None,
                "user_input": context.user_input,
                "normalized_input": context.commercial_brief.metadata.get("normalized_input")
                if context.commercial_brief
                else context.user_input,
                "veyra_user_id": context.metadata.get("veyra_user_id"),
                "auto_batch_identity_anchor_policy": {
                    "doc": "73",
                    "enabled": auto_identity_anchor_enabled,
                    "user_reference_priority": True,
                    "explicit_references_present": explicit_references_present,
                    "source_rule": "first_generated_output_if_no_user_reference",
                },
            }
            if auto_identity_anchor_reference is not None:
                generation_plan.metadata = self._with_auto_identity_anchor_reference(
                    generation_plan.metadata,
                    auto_identity_anchor_reference,
                )
            if not use_mock_generation:
                generation_plan.candidate_count = 1
                generation_plan.max_refine_rounds = 0
            context.layout_plans.append(layout_plan)
            context.prompt_compilations.append(prompt)
            context.condition_plans.append(condition_plan)
            context.generation_plans.append(generation_plan)

            try:
                selected_candidate, selected_evaluation, asset_warnings = self._run_asset_generation_loop(
                    context,
                    asset,
                    layout_plan,
                    prompt,
                    condition_plan,
                    generation_plan,
                )
            except Exception as exc:
                if not require_independent_role_terminal_states:
                    raise
                role_execution_records.append(
                    self._role_execution_record(
                        asset,
                        mode_role_recipe,
                        status="failed",
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                    )
                )
                pack_warnings.append(
                    f"specialized role {mode_role_recipe.get('role_key') or asset.asset_id} failed: {str(exc)[:240]}"
                )
                continue
            pack_warnings.extend(asset_warnings)
            if selected_candidate is not None:
                context.selected_candidates.append(selected_candidate)
                if auto_identity_anchor_enabled and auto_identity_anchor_reference is None:
                    auto_identity_anchor_reference = self._auto_identity_anchor_reference_from_candidate(
                        selected_candidate,
                        asset=asset,
                        context=context,
                    )
            if require_independent_role_terminal_states:
                role_execution_records.append(
                    self._role_execution_record(
                        asset,
                        mode_role_recipe,
                        status="generated" if selected_candidate is not None else "failed",
                        candidate_id=selected_candidate.candidate_id if selected_candidate is not None else None,
                        error_type=None if selected_candidate is not None else "NoCandidateProduced",
                        error_message=None if selected_candidate is not None else "shared generation returned no selected candidate",
                    )
                )
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
                    asset_type="accepted_mock_candidate" if candidate.is_mock else "accepted_generated_candidate",
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
        if role_execution_records:
            role_execution_payload = {
                "schema_version": "specialized_role_execution_v1",
                "status": "complete" if all(item["status"] == "generated" for item in role_execution_records) else "incomplete",
                "roles": role_execution_records,
                "shared_execution_only": True,
            }
            asset_pack = asset_pack.model_copy(
                update={
                    "manifest": {**dict(asset_pack.manifest), "specialized_role_execution": role_execution_payload},
                    "metadata": {**dict(asset_pack.metadata), "specialized_role_execution": role_execution_payload},
                }
            )
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
                **({"specialized_role_execution": role_execution_payload} if role_execution_records else {}),
                "candidate_count": len(context.candidate_results),
                "selected_candidate_ids": [candidate.candidate_id for candidate in context.selected_candidates],
                "refinement_plan_count": len(context.refinement_plans),
                "refinement_plans": [plan.model_dump(mode="json") for plan in context.refinement_plans],
                "v3_independent_runtime": True,
                "llm_brain": self._llm_brain_metadata(context),
                "scenario_id": context.metadata.get("scenario_id"),
                "template_id": context.metadata.get("template_id"),
                "shared_capabilities": context.metadata.get("shared_capabilities", {}),
                "visual_cluster": self._visual_cluster_metadata(context),
                "requested_image_count": len(context.series_plan.assets) if context.series_plan else None,
                "effective_variation_mode": context.metadata.get("effective_variation_mode")
                or context.metadata.get("variation_mode"),
            },
        )

    def _create_base_context(
        self,
        user_input: str,
        optional_brand_id: str | None,
        optional_template_id: str | None = None,
        runtime_metadata: dict | None = None,
    ) -> PipelineContext:
        context = PipelineContext(
            user_input=user_input,
            optional_brand_id=optional_brand_id,
            metadata={
                "source_agent": "CentralCreativeBrain",
                "rules_version": RULE_VERSION,
                **(runtime_metadata or {}),
            },
        )
        job = self.intent_agent.create_job(
            user_input,
            optional_brand_id=optional_brand_id,
            optional_template_id=optional_template_id,
            job_instance_id=str((runtime_metadata or {}).get("v3_job_instance_id") or "") or None,
        ).output
        job.metadata = {
            **job.metadata,
            **{
                key: value
                for key, value in context.metadata.items()
                if key
                in {
                    "scenario_id",
                    "scenario_mode_id",
                    "scenario_preset_id",
                    "scenario_parameters",
                    "platform_profile",
                    "product_profile",
                    "uploaded_asset_ids",
                    "requested_image_count",
                    "requested_image_size",
                    "project_id",
                    "template_id",
                    "veyra_user_id",
                    "reference_assets",
                    "llm_brain",
                }
            },
        }
        brief = self.commercial_strategy_agent.create_brief(job).output
        brief.metadata = {
            **brief.metadata,
            "template_id": context.metadata.get("template_id") or job.optional_template_id,
            "scenario_id": context.metadata.get("scenario_id") or job.metadata.get("scenario_id"),
        }
        selected_pack = self.vertical_registry.select_pack(job, brief)
        job.metadata["selected_vertical_pack"] = selected_pack.name
        brief.metadata["selected_vertical_pack"] = selected_pack.name
        context.creative_job = job
        context.commercial_brief = brief
        context.commercial_brief = selected_pack.refine_commercial_brief(context)
        self._apply_llm_brain_to_brief(context)
        context.selected_vertical_pack = selected_pack

        brand_profile = self.brand_memory_agent.resolve_profile(job, context.commercial_brief).output
        creative_plan = self.creative_director_agent.create_plan(job, context.commercial_brief, brand_profile).output
        context.brand_profile = brand_profile
        context.creative_plan = creative_plan
        context.creative_plan = selected_pack.refine_creative_plan(context)
        self._apply_llm_brain_to_creative_plan(context)

        series_plan = self.series_planner_agent.create_series_plan(job, context.commercial_brief, brand_profile).output
        context.series_plan = series_plan
        context.series_plan = selected_pack.refine_series_plan(context)
        context.series_plan = context.series_plan.model_copy(
            update={
                "assets": [
                    self._asset_with_mode_role(context, asset, index)
                    for index, asset in enumerate(context.series_plan.assets)
                ],
                "metadata": {
                    **dict(context.series_plan.metadata),
                    "role_specific_generation_plan": self._role_specific_generation_plan_metadata(context),
                    "mode_execution_policy": self._mode_execution_policy_metadata(context),
                },
            }
        )
        return context

    def _llm_brain_metadata(self, context: PipelineContext) -> dict[str, Any]:
        value = context.metadata.get("llm_brain")
        return value if isinstance(value, dict) else {}

    def _visual_cluster_metadata(self, context: PipelineContext) -> dict[str, Any]:
        shared = context.metadata.get("shared_capabilities")
        if not isinstance(shared, dict):
            return {}
        visual_cluster = shared.get("visual_cluster")
        cluster = dict(visual_cluster) if isinstance(visual_cluster, dict) else {}
        if context.series_plan is not None:
            series_metadata = dict(getattr(context.series_plan, "metadata", {}) or {})
            role_plan = series_metadata.get("role_specific_generation_plan")
            mode_policy = series_metadata.get("mode_execution_policy")
            if isinstance(role_plan, dict):
                cluster["role_specific_generation_plan"] = dict(role_plan)
            if isinstance(mode_policy, dict):
                cluster["mode_execution_policy"] = dict(mode_policy)
        specialized_plan = context.metadata.get("specialized_role_execution_plan")
        if isinstance(specialized_plan, dict) and specialized_plan:
            # This is a server-frozen shared-runtime execution plan, never a
            # General Template deliverable map.  The generic role machinery
            # below is intentionally reused by active specialized templates.
            cluster["role_specific_generation_plan"] = dict(specialized_plan)
            policy = specialized_plan.get("policy")
            if isinstance(policy, dict):
                cluster["mode_execution_policy"] = dict(policy)
        return cluster

    def _apply_llm_brain_to_brief(self, context: PipelineContext) -> None:
        brain = self._llm_brain_metadata(context)
        if not brain or brain.get("skipped") or context.commercial_brief is None:
            return
        intent = brain.get("intent_summary")
        if not isinstance(intent, dict):
            return
        visual_mood = self._string_list(intent.get("visual_mood"))
        must_keep = self._string_list(intent.get("must_keep"))
        avoid = self._string_list(intent.get("avoid"))
        context.commercial_brief.visual_tone = self._dedupe([*context.commercial_brief.visual_tone, *visual_mood])
        context.commercial_brief.commercial_hooks = self._dedupe([*context.commercial_brief.commercial_hooks, *must_keep[:4]])
        context.commercial_brief.risks = self._dedupe([*context.commercial_brief.risks, *avoid[:4]])
        context.commercial_brief.metadata = {
            **context.commercial_brief.metadata,
            "llm_brain_intent_summary": intent,
            "llm_brain_user_visible_summary": brain.get("user_visible_summary")
            if isinstance(brain.get("user_visible_summary"), dict)
            else {},
        }

    def _apply_llm_brain_to_creative_plan(self, context: PipelineContext) -> None:
        brain = self._llm_brain_metadata(context)
        if not brain or brain.get("skipped") or context.creative_plan is None:
            return
        guidance = brain.get("prompt_guidance")
        if not isinstance(guidance, dict):
            return
        image_plan = brain.get("image_set_plan")
        memory_digest = brain.get("project_memory_digest")
        optimized = str(guidance.get("optimized_direction") or "").strip()
        addons = self._string_list(guidance.get("visual_direction_addons"))
        layout_notes = self._string_list(guidance.get("layout_notes"))
        style_notes = self._string_list(guidance.get("style_notes"))
        negatives = self._string_list(guidance.get("negative_prompt_addons"))
        if optimized and optimized not in context.creative_plan.visual_direction:
            context.creative_plan.visual_direction = f"{context.creative_plan.visual_direction}. {optimized}"
        if addons:
            context.creative_plan.materials_and_props = self._dedupe([*context.creative_plan.materials_and_props, *addons[:6]])
        if style_notes:
            context.creative_plan.color_strategy = self._dedupe([*context.creative_plan.color_strategy, *style_notes[:6]])
        if layout_notes:
            context.creative_plan.composition_strategy = (
                f"{context.creative_plan.composition_strategy}. Layout intent: {'; '.join(layout_notes[:4])}"
            )
        consistency = str(guidance.get("consistency_strategy") or "").strip()
        if consistency:
            context.creative_plan.consistency_strategy = consistency
        if negatives:
            context.creative_plan.negative_direction = self._dedupe([*context.creative_plan.negative_direction, *negatives])
        context.creative_plan.metadata = {
            **context.creative_plan.metadata,
            "llm_brain_prompt_guidance": guidance,
            "llm_brain_image_set_plan": image_plan if isinstance(image_plan, dict) else {},
            "llm_brain_project_memory_digest": memory_digest if isinstance(memory_digest, dict) else {},
        }

    def _string_list(self, values: Any) -> list[str]:
        if not isinstance(values, list):
            return []
        return [str(item).strip() for item in values if str(item).strip()]

    def _dedupe(self, values: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in values if item))

    def _role_specific_generation_plan_metadata(self, context: PipelineContext) -> dict[str, Any]:
        specialized = context.metadata.get("specialized_role_execution_plan")
        if isinstance(specialized, dict) and specialized:
            return dict(specialized)
        if context.series_plan is not None:
            series_plan = dict(getattr(context.series_plan, "metadata", {}) or {})
            plan = series_plan.get("role_specific_generation_plan")
            if isinstance(plan, dict):
                return dict(plan)
        cluster = self._visual_cluster_metadata(context)
        plan = cluster.get("role_specific_generation_plan")
        if isinstance(plan, dict):
            return dict(plan)
        suite = cluster.get("general_suite_role_plan")
        if isinstance(suite, dict):
            metadata = suite.get("metadata")
            if isinstance(metadata, dict) and isinstance(metadata.get("role_specific_generation_plan"), dict):
                return dict(metadata["role_specific_generation_plan"])
        return {}

    def _mode_execution_policy_metadata(self, context: PipelineContext) -> dict[str, Any]:
        specialized = context.metadata.get("specialized_role_execution_plan")
        if isinstance(specialized, dict) and self._requires_independent_role_terminal_states(context):
            policy = specialized.get("policy")
            if isinstance(policy, dict):
                return dict(policy)
        if context.series_plan is not None:
            series_plan = dict(getattr(context.series_plan, "metadata", {}) or {})
            policy = series_plan.get("mode_execution_policy")
            if isinstance(policy, dict):
                return dict(policy)
        cluster = self._visual_cluster_metadata(context)
        policy = cluster.get("mode_execution_policy")
        if isinstance(policy, dict):
            return dict(policy)
        plan = self._role_specific_generation_plan_metadata(context)
        policy = plan.get("policy")
        return dict(policy) if isinstance(policy, dict) else {}

    def _mode_role_recipe_for_asset(self, context: PipelineContext, asset, index: int) -> dict[str, Any]:
        metadata = dict(getattr(asset, "metadata", {}) or {})
        plan = self._role_specific_generation_plan_metadata(context)
        recipes = plan.get("role_recipes")
        if self._requires_independent_role_terminal_states(context) and isinstance(recipes, list) and recipes:
            recipe = recipes[min(index, len(recipes) - 1)]
            return dict(recipe) if isinstance(recipe, dict) else {}
        existing = metadata.get("mode_role_recipe")
        if isinstance(existing, dict):
            return dict(existing)
        if isinstance(recipes, list) and recipes:
            recipe = recipes[min(index, len(recipes) - 1)]
            return dict(recipe) if isinstance(recipe, dict) else {}
        return {}

    def _asset_with_mode_role(self, context: PipelineContext, asset, index: int):
        recipe = self._mode_role_recipe_for_asset(context, asset, index)
        if not recipe:
            return asset
        role_plan = self._role_specific_generation_plan_metadata(context)
        policy = self._mode_execution_policy_metadata(context)
        metadata = {
            **dict(asset.metadata),
            "mode_role_recipe": recipe,
            "mode_role_key": recipe.get("role_key"),
            "mode_role_label": recipe.get("label"),
            "mode_role_purpose": recipe.get("purpose"),
            "role_specific_prompt_pressure": recipe.get("prompt_pressure"),
            "role_specific_generation_plan": role_plan,
            "mode_execution_policy": policy,
            "variation_mode": role_plan.get("mode") or policy.get("mode") or dict(asset.metadata).get("variation_mode"),
        }
        return asset.model_copy(update={"metadata": metadata})

    def _has_explicit_user_reference_assets(self, context: PipelineContext) -> bool:
        metadata = dict(context.metadata or {})
        for key in ("reference_assets", "uploaded_assets"):
            if self._non_empty_dict_list(metadata.get(key)):
                return True
        project_context = metadata.get("project_context_snapshot")
        if isinstance(project_context, dict):
            for key in (
                "selected_output_assets",
                "selected_reference_assets",
                "uploaded_reference_assets",
                "selected_visual_references",
                "strong_reference_bindings",
            ):
                if self._non_empty_dict_list(project_context.get(key)):
                    return True
        shared = metadata.get("shared_capabilities")
        visual_cluster = shared.get("visual_cluster") if isinstance(shared, dict) else None
        if not isinstance(visual_cluster, dict):
            visual_cluster = metadata.get("visual_cluster")
        if isinstance(visual_cluster, dict):
            closure = visual_cluster.get("strong_reference_closure_package")
            if isinstance(closure, dict) and closure.get("active"):
                return True
        return False

    def _requires_independent_role_terminal_states(self, context: PipelineContext) -> bool:
        """Return the generic specialized-execution opt-in, if any.

        The Central Brain deliberately does not know Photography role names.
        An active specialized Scenario Pack can freeze this one execution
        property; General and inactive templates keep the pre-existing path.
        """

        plan = context.metadata.get("specialized_role_execution_plan")
        if not isinstance(plan, dict):
            return False
        metadata = plan.get("metadata")
        return isinstance(metadata, dict) and bool(metadata.get("require_independent_role_terminal_states"))

    def _generated_output_reference_chain_allowed(self, context: PipelineContext) -> bool:
        """Respect a frozen template policy before deriving image-edit inputs.

        A generated first output is never user reference evidence.  The
        policy gives a specialized set a way to require independent T2I roles
        while leaving the established General same-person suite behavior
        untouched.
        """

        policy = self._mode_execution_policy_metadata(context)
        return str(policy.get("generated_output_reference_chain") or "").strip().lower() not in {
            "disabled",
            "explicit_references_only",
        }

    @staticmethod
    def _role_execution_record(
        asset,
        role_recipe: dict[str, Any],
        *,
        status: str,
        candidate_id: str | None = None,
        error_type: str | None = None,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        return {
            "role_key": str(role_recipe.get("role_key") or getattr(asset, "asset_id", "")),
            "asset_id": getattr(asset, "asset_id", None),
            "status": status,
            "candidate_id": candidate_id,
            "error_type": error_type,
            "error_message": error_message[:500] if error_message else None,
        }

    def _is_human_identity_suite_context(self, context: PipelineContext) -> bool:
        if str(context.metadata.get("scenario_id") or "").strip().lower() == "ecommerce":
            return False
        requested_count = _bounded_requested_image_count(context.metadata.get("requested_image_count"))
        asset_count = len(context.series_plan.assets) if context.series_plan is not None else 0
        if max(requested_count, asset_count) < 2:
            return False
        profile_subject_types = self._llm_profile_subject_entity_types(context)
        if profile_subject_types:
            # The frozen task profile is the best available statement of what
            # the image set is about.  In particular, do not let incidental
            # words from generic prompt guidance (for example, "model") turn a
            # product or still-life delivery into an image-edit continuation.
            return bool(
                profile_subject_types
                & {"person", "human", "character", "portrait", "portrait_subject", "human_subject"}
            )
        role_plan = self._role_specific_generation_plan_metadata(context)
        recipes = role_plan.get("role_recipes")
        if isinstance(recipes, list):
            for recipe in recipes:
                if not isinstance(recipe, dict):
                    continue
                metadata = recipe.get("metadata")
                if isinstance(metadata, dict) and str(metadata.get("subject_type") or "").strip().lower() == "character":
                    return True
        text = " ".join(
            [
                str(context.user_input or ""),
                str(getattr(context.commercial_brief, "title", "") if context.commercial_brief else ""),
                str(getattr(context.commercial_brief, "description", "") if context.commercial_brief else ""),
                " ".join(getattr(context.commercial_brief, "visual_tone", []) if context.commercial_brief else []),
                str(getattr(context.creative_plan, "visual_direction", "") if context.creative_plan else ""),
            ]
        ).lower()
        human_terms = (
            "portrait",
            "human photo",
            "real person",
            "same young woman",
            "same woman",
            "woman",
            "girl",
            "beauty portrait",
            "face",
            "\u4eba\u50cf",
            "\u771f\u4eba",
            "\u5199\u771f",
            "\u7f8e\u5973",
            "\u5973\u751f",
            "\u5973\u5b69",
            "\u4eba\u7269",
            "\u8138",
        )
        stylized_terms = ("anime", "manga", "cartoon", "illustration", "\u52a8\u6f2b", "\u6f2b\u753b", "\u63d2\u753b", "\u5361\u901a")
        return any(term in text for term in human_terms) and not any(term in text for term in stylized_terms)

    def _llm_profile_subject_entity_types(self, context: PipelineContext) -> set[str]:
        """Return non-empty subject types from the frozen central-brain profile.

        Profiles are intentionally open-ended under Doc102.  This helper only
        exposes their normalized names; callers decide which known types are
        relevant to a particular shared capability.
        """

        profile = self._llm_brain_metadata(context).get("visual_task_profile")
        if not isinstance(profile, dict):
            return set()
        entities = profile.get("subject_entities")
        if not isinstance(entities, list):
            return set()
        return {
            str(entity.get("entity_type") or "").strip().lower()
            for entity in entities
            if isinstance(entity, dict) and str(entity.get("entity_type") or "").strip()
        }

    def _with_auto_identity_anchor_reference(
        self,
        metadata: dict[str, Any],
        auto_reference: dict[str, Any],
    ) -> dict[str, Any]:
        existing_refs = [dict(item) for item in metadata.get("reference_assets", []) if isinstance(item, dict)]
        return {
            **metadata,
            "reference_assets": self._dedupe_reference_assets([*existing_refs, auto_reference]),
            "auto_batch_identity_anchor_applied": True,
            "auto_batch_identity_anchor_source_output_id": auto_reference.get("output_id"),
            "auto_batch_identity_anchor_source_candidate_id": auto_reference.get("candidate_id"),
        }

    def _auto_identity_anchor_reference_from_candidate(
        self,
        candidate: CandidateResult,
        *,
        asset,
        context: PipelineContext,
    ) -> dict[str, Any] | None:
        file_path = str(candidate.file_path or "").strip()
        if not file_path:
            return None
        output_id = str(candidate.metadata.get("output_id") or candidate.candidate_id)
        return {
            "asset_id": output_id,
            "source_id": output_id,
            "output_id": output_id,
            "candidate_id": candidate.candidate_id,
            "source_type": "generated_first_output",
            "role": "identity_anchor",
            "use_policy": "identity",
            "strength": "hard",
            "provider_input_required": True,
            "file_path": file_path,
            "filename": f"{output_id}.png",
            "mime_type": str(candidate.metadata.get("mime_type") or "image/png"),
            "lock_targets": [
                "broad face shape",
                "eye shape and spacing",
                "nose-mouth relationship",
                "jawline direction",
                "age impression",
                "body type and proportions",
            ],
            "metadata": {
                "doc": "73",
                "auto_batch_identity_anchor": True,
                "source_asset_id": getattr(asset, "asset_id", None),
                "project_id": context.metadata.get("project_id"),
                "template_id": context.metadata.get("template_id"),
                "user_reference_priority": True,
                "doc93_reference_channel_safe": True,
            },
        }

    def _non_empty_dict_list(self, value: Any) -> bool:
        return isinstance(value, list) and any(isinstance(item, dict) and item for item in value)

    def _dedupe_reference_assets(self, references: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[str] = set()
        result: list[dict[str, Any]] = []
        for item in references:
            key = str(
                item.get("file_path")
                or item.get("output_id")
                or item.get("asset_id")
                or item.get("source_id")
                or item.get("candidate_id")
                or ""
            ).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

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
                    "job_id": context.creative_job.job_id if context.creative_job else generation_plan.metadata.get("job_id"),
                    "quality_mode": generation_plan.metadata.get("quality_mode", "standard"),
                    "uploaded_assets": generation_plan.metadata.get("uploaded_assets", []),
                    "reference_assets": generation_plan.metadata.get("reference_assets", []),
                    "shared_capabilities": generation_plan.metadata.get("shared_capabilities", {}),
                    "visual_cluster": generation_plan.metadata.get("visual_cluster", {}),
                    "llm_brain": generation_plan.metadata.get("llm_brain", {}),
                    "requested_image_count": generation_plan.metadata.get("requested_image_count"),
                    "requested_image_size": generation_plan.metadata.get("requested_image_size"),
                    "normalized_v3_job_intent": generation_plan.metadata.get("normalized_v3_job_intent"),
                    "template_deliverable_plan": generation_plan.metadata.get("template_deliverable_plan"),
                    "resolved_constraint_ledger": generation_plan.metadata.get("resolved_constraint_ledger"),
                    "capability_execution_envelope": generation_plan.metadata.get("capability_execution_envelope"),
                    "mode_execution_policy": generation_plan.metadata.get("mode_execution_policy", {}),
                    "role_specific_generation_plan": generation_plan.metadata.get("role_specific_generation_plan", {}),
                    "mode_role_recipe": generation_plan.metadata.get("mode_role_recipe", {}),
                    "mode_role_key": generation_plan.metadata.get("mode_role_key"),
                    "mode_role_label": generation_plan.metadata.get("mode_role_label"),
                    "project_id": generation_plan.metadata.get("project_id"),
                    "template_id": generation_plan.metadata.get("template_id"),
                    "scenario_id": generation_plan.metadata.get("scenario_id"),
                    "visual_auto_retry_active": generation_plan.metadata.get("visual_auto_retry_active", False),
                    "visual_auto_retry_attempt": generation_plan.metadata.get("visual_auto_retry_attempt"),
                    "retry_attempt": generation_plan.metadata.get("retry_attempt"),
                    "visual_retry_reason_codes": generation_plan.metadata.get("visual_retry_reason_codes", []),
                    "visual_retry_patch": generation_plan.metadata.get("visual_retry_patch", {}),
                    "auto_batch_identity_anchor_policy": generation_plan.metadata.get("auto_batch_identity_anchor_policy", {}),
                    "auto_batch_identity_anchor_applied": generation_plan.metadata.get("auto_batch_identity_anchor_applied", False),
                    "auto_batch_identity_anchor_source_output_id": generation_plan.metadata.get(
                        "auto_batch_identity_anchor_source_output_id"
                    ),
                    "auto_batch_identity_anchor_source_candidate_id": generation_plan.metadata.get(
                        "auto_batch_identity_anchor_source_candidate_id"
                    ),
                    "industry": generation_plan.metadata.get("industry"),
                    "user_input": generation_plan.metadata.get("user_input"),
                    "normalized_input": generation_plan.metadata.get("normalized_input"),
                    "veyra_user_id": generation_plan.metadata.get("veyra_user_id"),
                    "provider_strategy": generation_plan.provider_strategy.value,
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
