"""Asset packager agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..asset_pack.packager import AssetPackager
from ..schemas import (
    BrandProfile,
    CandidateResult,
    CommercialAssetPack,
    CreativeJob,
    EvaluationReport,
    LayoutPlan,
    MemoryUpdate,
    PromptCompilationResult,
    SeriesPlan,
)


class AssetPackagerAgent(BaseAgent):
    agent_name = "AssetPackagerAgent"

    def __init__(self) -> None:
        self.packager = AssetPackager()

    def create_asset_pack(
        self,
        job: CreativeJob,
        brand_profile: BrandProfile,
        series_plan: SeriesPlan,
        layout_plans: list[LayoutPlan],
        prompt_compilations: list[PromptCompilationResult],
        evaluation_reports: list[EvaluationReport],
        memory_update: MemoryUpdate | None,
    ) -> AgentResult[CommercialAssetPack]:
        pack = self.packager.package(
            job=job,
            brand_profile=brand_profile,
            series_plan=series_plan,
            layout_plans=layout_plans,
            prompt_compilations=prompt_compilations,
            evaluation_reports=evaluation_reports,
            memory_update=memory_update,
        )
        return AgentResult(output=pack, reasoning_summary="Packaged planning-only commercial asset manifest.")

    def create_generated_asset_pack(
        self,
        job: CreativeJob,
        brand_profile: BrandProfile,
        series_plan: SeriesPlan,
        layout_plans: list[LayoutPlan],
        prompt_compilations: list[PromptCompilationResult],
        selected_candidates: list[CandidateResult],
        evaluation_reports: list[EvaluationReport],
        memory_update: MemoryUpdate | None,
        warnings: list[str] | None = None,
    ) -> AgentResult[CommercialAssetPack]:
        pack = self.packager.package_generated(
            job=job,
            brand_profile=brand_profile,
            series_plan=series_plan,
            layout_plans=layout_plans,
            prompt_compilations=prompt_compilations,
            selected_candidates=selected_candidates,
            evaluation_reports=evaluation_reports,
            memory_update=memory_update,
            warnings=warnings,
        )
        return AgentResult(output=pack, reasoning_summary="Packaged selected V3.2 generated candidates.")
