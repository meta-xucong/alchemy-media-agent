"""Restaurant vertical pack specialization."""

from .base import VerticalAgentPack
from ..schemas import AssetType, Platform


class RestaurantAgentFamily(VerticalAgentPack):
    name = "restaurant_agent_family"
    supported_industries = ["restaurant_barbecue", "restaurant_hotpot", "restaurant_general"]
    supported_scenarios = ["set_meal_promotion", "winter_set_meal_promotion", "festival_set_meal_promotion", "opening_promotion"]

    def match(self, creative_job, commercial_brief=None) -> float:
        industry = self._industry_value(commercial_brief)
        if industry and industry != "unknown" and industry not in self.supported_industries:
            return 0.0
        score = 0.8 if industry in self.supported_industries else 0.0
        text = self._job_text(creative_job)
        if self._contains_any(
            text,
            ("餐厅", "饭店", "火锅", "烧烤", "外卖", "团购", "套餐", "美团", "饿了么", "restaurant", "food", "hotpot", "bbq"),
        ):
            score = max(score, 0.88)
        return score

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None:
            return brief
        return brief.model_copy(
            update={
                "target_audience": brief.target_audience or "nearby diners and delivery app shoppers",
                "commercial_hooks": self._append_unique(
                    brief.commercial_hooks,
                    ["appetite trigger", "local visit intent", "offer clarity"],
                ),
                "selling_points": self._append_unique(
                    brief.selling_points,
                    ["fresh ingredients", "clean dining impression"],
                ),
                "visual_tone": self._append_unique(brief.visual_tone, ["appetite", "clean", "warm"]),
                "copy_strategy": "short appetite-led Chinese headline with clear offer and local CTA",
                "platform_notes": {
                    **brief.platform_notes,
                    "vertical_pack": self.name,
                    "restaurant_rule": "balance appetite appeal, cleanliness, and platform conversion",
                },
                "metadata": self._metadata(brief.metadata, "commercial_brief", priorities=["appetite", "cleanliness"]),
            }
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None:
            return plan
        return plan.model_copy(
            update={
                "visual_direction": f"{plan.visual_direction}; appetizing food hero with clean commercial plating",
                "composition_strategy": (
                    f"{plan.composition_strategy}; make food the sensory center, keep steam controlled, "
                    "and reserve clear promotional copy zones"
                ),
                "lighting_strategy": plan.lighting_strategy or "warm restaurant light with clean highlights",
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["fresh ingredients", "controlled steam", "clean serving surface"],
                ),
                "negative_direction": self._append_unique(
                    plan.negative_direction,
                    ["dirty table", "greasy low-end look", "chaotic food pile"],
                ),
                "metadata": self._metadata(plan.metadata, "creative_plan", priorities=["appetite", "local_conversion"]),
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None:
            return series
        assets = []
        for asset in series.assets:
            asset_type = asset.asset_type
            purpose = asset.purpose
            if asset.platform in {Platform.DELIVERY_APP, Platform.MEITUAN, Platform.ELEME}:
                asset_type = AssetType.GROUP_BUYING_IMAGE if asset.platform == Platform.MEITUAN else AssetType.DELIVERY_COVER
                purpose = "delivery or group-buying food conversion image with appetizing hero dish"
            assets.append(
                asset.model_copy(
                    update={
                        "asset_type": asset_type,
                        "purpose": purpose,
                        "metadata": self._metadata(asset.metadata, "asset_spec", asset_role=asset_type.value),
                    }
                )
            )
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "restaurant sequence: appetite hero, platform offer clarity, and clean brand memory",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        product_area = layout_plan.product_area.model_copy(
            update={
                "position": "center_food_hero",
                "priority": 1,
                "relative_box": {"x": 0.12, "y": 0.28, "w": 0.76, "h": 0.44},
                "notes": "appetizing hero dish or set meal with clean edges and controlled steam",
                "metadata": self._metadata(layout_plan.product_area.metadata, "layout_region", region="food_hero"),
            }
        )
        return layout_plan.model_copy(
            update={
                "product_area": product_area,
                "visual_hierarchy": ["food_hero", "offer", "store_or_brand", "cta"],
                "background_strategy": "warm clean restaurant setting with uncluttered offer regions",
                "metadata": self._metadata(layout_plan.metadata, "layout_plan", layout_bias="food_appetite"),
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None:
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "visual_prompt": (
                    f"{prompt_compilation.visual_prompt} Restaurant specialization: emphasize freshness, appetite, "
                    "clean serving surfaces, and a local promotion atmosphere."
                ),
                "hard_constraints": self._append_unique(
                    prompt_compilation.hard_constraints,
                    ["Food must look fresh, clean, edible, and commercially appetizing."],
                ),
                "style_notes": self._append_unique(prompt_compilation.style_notes, ["appetite", "clean_food", "local_conversion"]),
                "layout_notes": self._append_unique(
                    prompt_compilation.layout_notes,
                    ["hero dish remains unobstructed", "clean offer space", "controlled steam only"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "food_appetite_required": True,
                    "clean_food_surface_required": True,
                },
                "metadata": self._metadata(prompt_compilation.metadata, "prompt_compilation", prompt_bias="appetite"),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "restaurant_appetite_cleanliness",
            "commercial_score_delta": 0.025,
            "layout_score_delta": 0.015,
            "weighted_priorities": ["appetite", "clean_food_surface", "offer_clarity"],
        }
