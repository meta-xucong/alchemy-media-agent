"""Planning-only commercial asset packager."""

from __future__ import annotations

from .manifest import manifest_entry
from .render_manifest import render_manifest, render_manifest_entry
from ..creative_core.rules import RULE_VERSION, stable_id
from ..schemas import (
    BrandProfile,
    CandidateResult,
    CommercialAssetPack,
    CreativeJob,
    EvaluationReport,
    LayoutPlan,
    MemoryUpdate,
    PackagedAsset,
    PromptCompilationResult,
    SeriesPlan,
)


class AssetPackager:
    def package(
        self,
        job: CreativeJob,
        brand_profile: BrandProfile,
        series_plan: SeriesPlan,
        layout_plans: list[LayoutPlan],
        prompt_compilations: list[PromptCompilationResult],
        evaluation_reports: list[EvaluationReport],
        memory_update: MemoryUpdate | None = None,
    ) -> CommercialAssetPack:
        layouts_by_asset = {layout.asset_id: layout for layout in layout_plans}
        prompts_by_asset = {prompt.asset_id: prompt for prompt in prompt_compilations}
        evals_by_asset = {report.asset_id: report for report in evaluation_reports}
        render_entries_by_asset = {layout.asset_id: render_manifest_entry(layout) for layout in layout_plans}
        assets: list[PackagedAsset] = []
        for asset in series_plan.assets:
            layout = layouts_by_asset.get(asset.asset_id)
            prompt = prompts_by_asset.get(asset.asset_id)
            report = evals_by_asset.get(asset.asset_id)
            render_entry = render_entries_by_asset.get(asset.asset_id)
            packaged = PackagedAsset(
                asset_id=asset.asset_id,
                asset_type=asset.asset_type,
                platform=asset.platform,
                aspect_ratio=asset.aspect_ratio,
                purpose=asset.purpose,
                layout_plan_id=layout.layout_plan_id if layout else None,
                prompt_compilation_id=prompt.prompt_compilation_id if prompt else None,
                evaluation_id=report.evaluation_id if report else None,
                metadata={
                    "planning_only": True,
                    "rendering_required": asset.requires_text_overlay,
                    "render_manifest": render_entry,
                    "asset_metadata": dict(asset.metadata),
                    "ecommerce_slot": asset.metadata.get("ecommerce_slot"),
                    "ecommerce_recipe": asset.metadata.get("ecommerce_recipe"),
                    "source_agent": "AssetPackager",
                },
            )
            assets.append(packaged)
        manifest = {
            "job_id": job.job_id,
            "planning_only": True,
            "asset_count": len(assets),
            "assets": [manifest_entry(asset) for asset in assets],
            "render_manifest": render_manifest(layout_plans),
            "rules_version": RULE_VERSION,
        }
        return CommercialAssetPack(
            asset_pack_id=stable_id("asset_pack", job.job_id, series_plan.series_plan_id),
            job_id=job.job_id,
            brand_id=brand_profile.brand_id,
            assets=assets,
            manifest=manifest,
            brand_memory_update=memory_update,
            planning_only=True,
            metadata={
                "source_agent": "AssetPackager",
                "rules_version": RULE_VERSION,
                "selected_vertical_pack": job.metadata.get("selected_vertical_pack"),
            },
        )

    def package_generated(
        self,
        job: CreativeJob,
        brand_profile: BrandProfile,
        series_plan: SeriesPlan,
        layout_plans: list[LayoutPlan],
        prompt_compilations: list[PromptCompilationResult],
        selected_candidates: list[CandidateResult],
        evaluation_reports: list[EvaluationReport],
        memory_update: MemoryUpdate | None = None,
        warnings: list[str] | None = None,
    ) -> CommercialAssetPack:
        layouts_by_asset = {layout.asset_id: layout for layout in layout_plans}
        prompts_by_asset = {prompt.asset_id: prompt for prompt in prompt_compilations}
        candidates_by_asset = {candidate.asset_id: candidate for candidate in selected_candidates}
        evals_by_candidate_id = {report.candidate_id: report for report in evaluation_reports if report.candidate_id}
        render_entries_by_asset = {layout.asset_id: render_manifest_entry(layout) for layout in layout_plans}
        pack_warnings = warnings or []
        assets: list[PackagedAsset] = []
        for asset in series_plan.assets:
            layout = layouts_by_asset.get(asset.asset_id)
            prompt = prompts_by_asset.get(asset.asset_id)
            candidate = candidates_by_asset.get(asset.asset_id)
            report = evals_by_candidate_id.get(candidate.candidate_id) if candidate else None
            render_entry = render_entries_by_asset.get(asset.asset_id)
            asset_warnings = list(pack_warnings)
            if report and report.recommendation != "accept":
                asset_warnings.append(f"selected candidate recommendation is {report.recommendation}")
            packaged = PackagedAsset(
                asset_id=asset.asset_id,
                asset_type=asset.asset_type,
                platform=asset.platform,
                aspect_ratio=asset.aspect_ratio,
                purpose=asset.purpose,
                file_path=candidate.file_path if candidate else None,
                uri=candidate.uri if candidate else None,
                layout_plan_id=layout.layout_plan_id if layout else None,
                prompt_compilation_id=prompt.prompt_compilation_id if prompt else None,
                evaluation_id=report.evaluation_id if report else None,
                metadata={
                    "planning_only": False,
                    "rendering_required": asset.requires_text_overlay,
                    "render_manifest": render_entry,
                    "asset_metadata": dict(asset.metadata),
                    "ecommerce_slot": asset.metadata.get("ecommerce_slot"),
                    "ecommerce_recipe": asset.metadata.get("ecommerce_recipe"),
                    "source_agent": "AssetPackager",
                    "selected_candidate_id": candidate.candidate_id if candidate else None,
                    "selected_candidate_provider": candidate.provider if candidate else None,
                    "selected_candidate_is_mock": candidate.is_mock if candidate else None,
                    "candidate_metadata": candidate.metadata if candidate else {},
                    "warnings": asset_warnings,
                },
            )
            assets.append(packaged)
        manifest = {
            "job_id": job.job_id,
            "planning_only": False,
            "asset_count": len(assets),
            "selected_candidate_count": len([asset for asset in assets if asset.metadata.get("selected_candidate_id")]),
            "assets": [manifest_entry(asset) for asset in assets],
            "render_manifest": render_manifest(layout_plans),
            "warnings": pack_warnings,
            "rules_version": RULE_VERSION,
            "selected_vertical_pack": job.metadata.get("selected_vertical_pack"),
        }
        return CommercialAssetPack(
            asset_pack_id=stable_id("asset_pack", job.job_id, series_plan.series_plan_id, "generated"),
            job_id=job.job_id,
            brand_id=brand_profile.brand_id,
            assets=assets,
            manifest=manifest,
            brand_memory_update=memory_update,
            planning_only=False,
            metadata={
                "source_agent": "AssetPackager",
                "rules_version": RULE_VERSION,
                "selected_vertical_pack": job.metadata.get("selected_vertical_pack"),
                "candidate_loop": True,
            },
        )
