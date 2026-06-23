"""Brand memory agent for temporary and V3-owned stored profiles."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..brand_memory.profile_service import BrandProfileService
from ..schemas import BrandProfile, CommercialBrief, CreativeJob, MemoryUpdate


class BrandMemoryAgent(BaseAgent):
    agent_name = "BrandMemoryAgent"

    def __init__(self, profile_service: BrandProfileService | None = None) -> None:
        self.profile_service = profile_service or BrandProfileService()

    def resolve_profile(self, job: CreativeJob, brief: CommercialBrief) -> AgentResult[BrandProfile]:
        profile = self.profile_service.resolve_for_job(job, brief)
        return AgentResult(
            output=profile,
            reasoning_summary="Resolved BrandProfile through V3-owned brand memory service.",
            metadata=self.metadata(brand_id=profile.brand_id, is_temporary=profile.is_temporary),
        )

    def propose_memory_update(
        self,
        brand_profile: BrandProfile,
        accepted_asset_ids: list[str],
        style_tags: list[str],
        planning_only: bool = True,
    ) -> MemoryUpdate:
        return self.profile_service.propose_memory_update(
            brand_profile=brand_profile,
            accepted_asset_ids=accepted_asset_ids,
            style_tags=style_tags,
            planning_only=planning_only,
        )

