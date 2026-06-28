"""Layout planning agent."""

from __future__ import annotations

from .base import AgentResult, BaseAgent
from ..creative_core.rules import RULE_VERSION, extract_explicit_chinese_text, stable_id
from ..schemas import AssetSpec, BrandProfile, CommercialBrief, CreativeJob, CreativePlan, LayoutPlan, LayoutRegion


class LayoutAgent(BaseAgent):
    agent_name = "LayoutAgent"

    def create_layout_plan(
        self,
        job: CreativeJob,
        asset: AssetSpec,
        brief: CommercialBrief,
        creative_plan: CreativePlan,
        brand_profile: BrandProfile,
    ) -> AgentResult[LayoutPlan]:
        explicit_text = extract_explicit_chinese_text(job.raw_user_input)
        headline_text = explicit_text.headline or self._headline_for(brief)
        cta_text = explicit_text.cta or self._cta_for(brief)
        product_area = LayoutRegion(
            name="product_area",
            position="center_large",
            priority=1,
            relative_box={"x": 0.18, "y": 0.26, "w": 0.64, "h": 0.46},
            notes=creative_plan.composition_strategy,
        )
        headline_area = LayoutRegion(
            name="headline_area",
            position="top_center",
            priority=1,
            relative_box={"x": 0.08, "y": 0.05, "w": 0.84, "h": 0.18},
            text=headline_text,
            notes="accurate external overlay text",
        )
        cta_area = LayoutRegion(
            name="cta_area",
            position="bottom_center",
            priority=2,
            relative_box={"x": 0.12, "y": 0.78, "w": 0.76, "h": 0.14},
            text=cta_text,
            notes="accurate external overlay CTA",
        )
        logo_area = LayoutRegion(
            name="logo_area",
            position="top_left",
            priority=3,
            relative_box={"x": 0.04, "y": 0.03, "w": 0.18, "h": 0.08},
            notes="reserved brand mark area",
        )
        layout = LayoutPlan(
            layout_plan_id=stable_id("layout_plan", asset.asset_id, asset.platform, asset.aspect_ratio),
            asset_id=asset.asset_id,
            platform=asset.platform,
            aspect_ratio=asset.aspect_ratio,
            visual_hierarchy=["headline", "product", "offer_or_cta", "brand_mark"],
            product_area=product_area,
            headline_area=headline_area,
            cta_area=cta_area,
            logo_area=logo_area,
            reserved_text_regions=[headline_area, cta_area],
            typography_strategy=brand_profile.typography_preference or "large readable Chinese commercial typography",
            background_strategy="clean, low clutter, preserves negative space for overlay text",
            metadata=self.metadata(
                rules_version=RULE_VERSION,
                explicit_text_preserved=bool(explicit_text.headline or explicit_text.cta),
                explicit_headline=explicit_text.headline,
                explicit_cta=explicit_text.cta,
                layout_preference_used=brand_profile.layout_preference,
                asset_metadata=dict(asset.metadata),
            ),
        )
        return AgentResult(output=layout, reasoning_summary="Created platform layout with external text regions.")

    def _headline_for(self, brief: CommercialBrief) -> str:
        if "new_product" in brief.scenario:
            return "新品上市 清爽来袭"
        if "opening" in brief.scenario:
            return "开业优惠 限时开启"
        if "festival" in brief.scenario:
            return "节日活动 限时优惠"
        if "set_meal" in brief.scenario:
            return "精选套餐 限时优惠"
        return "活动宣传 精选推荐"

    def _cta_for(self, brief: CommercialBrief) -> str:
        if brief.selling_points:
            return " / ".join(brief.selling_points[:2])
        if "promotion" in brief.scenario:
            return "立即下单 享受优惠"
        return "立即了解"

