"""Layout engine facade for V3 foundation."""

from __future__ import annotations

from ..agents.layout_agent import LayoutAgent
from ..schemas import AssetSpec, BrandProfile, CommercialBrief, CreativeJob, CreativePlan, LayoutPlan


class LayoutPlanner:
    def __init__(self) -> None:
        self.agent = LayoutAgent()

    def plan(
        self,
        job: CreativeJob,
        asset: AssetSpec,
        brief: CommercialBrief,
        creative_plan: CreativePlan,
        brand_profile: BrandProfile,
    ) -> LayoutPlan:
        return self.agent.create_layout_plan(job, asset, brief, creative_plan, brand_profile).output

