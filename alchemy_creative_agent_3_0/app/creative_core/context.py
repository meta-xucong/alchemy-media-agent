"""Pipeline context for V3 central brain orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..schemas import (
    BrandProfile,
    CommercialAssetPack,
    CommercialBrief,
    ConditionPlan,
    CreativeJob,
    CreativePlan,
    CandidateResult,
    EvaluationReport,
    GenerationPlan,
    LayoutPlan,
    PromptCompilationResult,
    RefinementPlan,
    SeriesPlan,
)
from ..vertical_agents import VerticalAgentPack


@dataclass
class PipelineContext:
    user_input: str
    optional_brand_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    creative_job: CreativeJob | None = None
    commercial_brief: CommercialBrief | None = None
    selected_vertical_pack: VerticalAgentPack | None = None
    brand_profile: BrandProfile | None = None
    creative_plan: CreativePlan | None = None
    series_plan: SeriesPlan | None = None
    layout_plans: list[LayoutPlan] = field(default_factory=list)
    prompt_compilations: list[PromptCompilationResult] = field(default_factory=list)
    condition_plans: list[ConditionPlan] = field(default_factory=list)
    generation_plans: list[GenerationPlan] = field(default_factory=list)
    candidate_results: list[CandidateResult] = field(default_factory=list)
    selected_candidates: list[CandidateResult] = field(default_factory=list)
    evaluation_reports: list[EvaluationReport] = field(default_factory=list)
    refinement_plans: list[RefinementPlan] = field(default_factory=list)
    asset_pack: CommercialAssetPack | None = None
