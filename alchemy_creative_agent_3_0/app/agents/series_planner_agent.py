"""Asset series planning agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.rules import (
    RULE_VERSION,
    asset_type_for_platform,
    default_platforms_for_industry,
    detect_platforms,
    is_single_image_request,
    platform_aspect_ratio,
    purpose_for_asset,
    stable_id,
    wants_series,
)
from ..schemas import AssetSpec, BrandProfile, CommercialBrief, CreativeJob, Platform, SeriesPlan


class SeriesPlannerAgent(BaseAgent):
    agent_name = "SeriesPlannerAgent"

    def create_series_plan(
        self,
        job: CreativeJob,
        brief: CommercialBrief,
        brand_profile: BrandProfile,
    ) -> AgentResult[SeriesPlan]:
        normalized = str(job.metadata.get("normalized_input", ""))
        detected = detect_platforms(normalized)
        single = is_single_image_request(normalized) and not wants_series(normalized)
        platforms = detected or default_platforms_for_industry(brief.industry)
        if single:
            platforms = [platforms[0] if platforms else Platform.GENERIC_SOCIAL]
        elif detected and len(platforms) > 3:
            platforms = platforms[:3]
        elif brief.industry == "ecommerce_product" and wants_series(normalized) and len(platforms) == 1:
            platforms = [platforms[0], platforms[0]]

        assets: list[AssetSpec] = []
        for index, platform in enumerate(platforms):
            asset_type = asset_type_for_platform(platform, index, brief.industry, single=single)
            asset_id = stable_id("asset", job.job_id, platform.value, asset_type.value, index)
            assets.append(
                AssetSpec(
                    asset_id=asset_id,
                    asset_type=asset_type,
                    platform=platform,
                    aspect_ratio=platform_aspect_ratio(platform),
                    purpose=purpose_for_asset(platform, asset_type, brief.industry),
                    priority=index + 1,
                    metadata={
                        "source_agent": self.agent_name,
                        "rules_version": RULE_VERSION,
                        "brand_id": brand_profile.brand_id,
                    },
                )
            )
        series = SeriesPlan(
            series_plan_id=stable_id("series_plan", job.job_id, ",".join(asset.asset_id for asset in assets)),
            job_id=job.job_id,
            assets=assets,
            series_strategy="coherent commercial asset series with platform-specific ratios",
            metadata=self.metadata(rules_version=RULE_VERSION, selected_platforms=[asset.platform for asset in assets]),
        )
        return AgentResult(output=series, reasoning_summary="Planned deterministic platform asset series.")
