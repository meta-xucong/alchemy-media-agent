"""Ecommerce vertical pack specialization."""

from .base import VerticalAgentPack
from ..schemas import AssetType, Platform


class EcommerceAgentFamily(VerticalAgentPack):
    name = "ecommerce_agent_family"
    supported_industries = ["ecommerce_product"]
    supported_scenarios = ["new_product_promotion", "generic_promotion", "brand_or_commercial_poster"]

    def match(self, creative_job, commercial_brief=None) -> float:
        score = 0.8 if self._industry_value(commercial_brief) in self.supported_industries else 0.0
        text = self._job_text(creative_job)
        if self._contains_any(
            text,
            (
                "淘宝",
                "天猫",
                "京东",
                "拼多多",
                "电商",
                "主图",
                "详情页",
                "商品图",
                "sku",
                "ecommerce",
                "product image",
                "main image",
            ),
        ):
            score = max(score, 0.9)
        if commercial_brief and any(
            platform
            in {
                Platform.TAOBAO,
                Platform.JD,
                Platform.ECOMMERCE_GENERIC,
            }
            for platform in commercial_brief.target_platforms
        ):
            score = max(score, 0.86)
        return score

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None:
            return brief
        return brief.model_copy(
            update={
                "target_audience": brief.target_audience or "platform shoppers comparing product value quickly",
                "commercial_hooks": self._append_unique(
                    brief.commercial_hooks,
                    ["product clarity", "feature proof", "platform conversion"],
                ),
                "selling_points": self._append_unique(
                    brief.selling_points,
                    ["clear product hero", "visible feature benefits"],
                ),
                "visual_tone": self._append_unique(brief.visual_tone, ["product_focused", "clean", "conversion_ready"]),
                "copy_strategy": "short feature-led product copy with clear benefit labels and purchase cue",
                "platform_notes": {
                    **brief.platform_notes,
                    "vertical_pack": self.name,
                    "ecommerce_rule": "prioritize main image clarity, SKU consistency, and feature callout space",
                },
                "metadata": self._metadata(brief.metadata, "commercial_brief", priorities=["product_clarity", "feature_labels"]),
            }
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None:
            return plan
        return plan.model_copy(
            update={
                "visual_direction": f"{plan.visual_direction}; product-first ecommerce hero with crisp edge definition",
                "composition_strategy": (
                    f"{plan.composition_strategy}; center the product, preserve empty feature-callout lanes, "
                    "and keep SKU identity consistent across assets"
                ),
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["feature callout panels", "clean platform background", "SKU consistency references"],
                ),
                "negative_direction": self._append_unique(
                    plan.negative_direction,
                    ["cropped product", "ambiguous product scale", "busy marketplace clutter"],
                ),
                "metadata": self._metadata(plan.metadata, "creative_plan", priorities=["hero_product", "conversion"]),
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None:
            return series
        assets = []
        for index, asset in enumerate(series.assets):
            asset_type = asset.asset_type
            purpose = asset.purpose
            if asset.platform in {Platform.TAOBAO, Platform.JD, Platform.ECOMMERCE_GENERIC}:
                asset_type = AssetType.ECOMMERCE_MAIN_IMAGE if index == 0 else AssetType.PRODUCT_DETAIL_BANNER
                purpose = "ecommerce conversion asset with product clarity and feature proof"
            assets.append(
                asset.model_copy(
                    update={
                        "asset_type": asset_type,
                        "purpose": purpose,
                        "requires_text_overlay": True,
                        "requires_brand_consistency": True,
                        "metadata": self._metadata(asset.metadata, "asset_spec", asset_role=asset_type.value),
                    }
                )
            )
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "ecommerce sequence: main product hero followed by feature-led conversion support",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        product_area = layout_plan.product_area.model_copy(
            update={
                "position": "center_product_hero",
                "priority": 1,
                "relative_box": {"x": 0.16, "y": 0.22, "w": 0.68, "h": 0.50},
                "notes": "large unobstructed product hero with visible shape, material, and scale",
                "metadata": self._metadata(layout_plan.product_area.metadata, "layout_region", region="product_area"),
            }
        )
        reserved_regions = list(layout_plan.reserved_text_regions)
        if layout_plan.headline_area:
            reserved_regions = [layout_plan.headline_area, *[region for region in reserved_regions if region.name != "headline_area"]]
        return layout_plan.model_copy(
            update={
                "product_area": product_area,
                "visual_hierarchy": ["product_hero", "feature_benefit", "price_or_cta", "brand_mark"],
                "reserved_text_regions": reserved_regions,
                "background_strategy": "clean ecommerce background with low clutter and space for feature labels",
                "metadata": self._metadata(layout_plan.metadata, "layout_plan", layout_bias="product_hero"),
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None:
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "visual_prompt": (
                    f"{prompt_compilation.visual_prompt} Ecommerce specialization: make the product silhouette, "
                    "materials, and key feature areas immediately readable for a platform shopper."
                ),
                "hard_constraints": self._append_unique(
                    prompt_compilation.hard_constraints,
                    ["Product shape, color, and visible functional details must remain clear."],
                ),
                "style_notes": self._append_unique(prompt_compilation.style_notes, ["product_focused", "conversion_ready"]),
                "layout_notes": self._append_unique(
                    prompt_compilation.layout_notes,
                    ["large centered product hero", "clean feature callout lanes", "no clutter over product"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "product_visibility_required": True,
                    "feature_callout_space_required": True,
                },
                "metadata": self._metadata(prompt_compilation.metadata, "prompt_compilation", prompt_bias="product_clarity"),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "ecommerce_product_clarity",
            "commercial_score_delta": 0.03,
            "layout_score_delta": 0.02,
            "weighted_priorities": ["product_visibility", "feature_label_space", "platform_conversion"],
        }
