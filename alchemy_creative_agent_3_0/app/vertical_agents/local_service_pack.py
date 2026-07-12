"""Local service vertical pack specialization."""

from .base import VerticalAgentPack
from ..creative_core.rules import _is_portrait_beauty_context
from ..schemas import Platform


class LocalServiceAgentFamily(VerticalAgentPack):
    name = "local_service_agent_family"
    supported_industries = ["local_service_beauty", "local_service_general"]
    supported_scenarios = ["opening_promotion", "generic_promotion", "brand_or_commercial_poster"]

    def match(self, creative_job, commercial_brief=None) -> float:
        score = 0.8 if self._industry_value(commercial_brief) in self.supported_industries else 0.0
        text = self._job_text(creative_job)
        if not _is_portrait_beauty_context(text) and self._contains_any(
            text,
            ("美甲", "美睫", "美容", "美发", "皮肤管理", "按摩", "到店", "预约", "开业优惠", "nail", "beauty", "salon"),
        ):
            score = max(score, 0.88)
        if commercial_brief and any(platform in {Platform.XIAOHONGSHU, Platform.WECHAT_MOMENTS} for platform in commercial_brief.target_platforms):
            if self._industry_value(commercial_brief).startswith("local_service"):
                score = max(score, 0.84)
        return score

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None:
            return brief
        return brief.model_copy(
            update={
                "target_audience": brief.target_audience or "nearby customers ready to book an appointment",
                "commercial_hooks": self._append_unique(
                    brief.commercial_hooks,
                    ["appointment intent", "trust cue", "local offer clarity"],
                ),
                "selling_points": self._append_unique(
                    brief.selling_points,
                    ["clean service detail", "easy booking"],
                ),
                "visual_tone": self._append_unique(brief.visual_tone, ["clean", "trustworthy", "service_detail"]),
                "copy_strategy": "short local service copy with clear benefit, location or booking CTA",
                "platform_notes": {
                    **brief.platform_notes,
                    "vertical_pack": self.name,
                    "local_service_rule": "show service result, trust cue, offer, and booking path",
                },
                "metadata": self._metadata(brief.metadata, "commercial_brief", priorities=["booking", "trust"]),
            }
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None:
            return plan
        return plan.model_copy(
            update={
                "visual_direction": f"{plan.visual_direction}; service-result hero with clean trustworthy environment",
                "composition_strategy": (
                    f"{plan.composition_strategy}; show the service result or environment clearly while preserving CTA space"
                ),
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["service result detail", "clean workspace", "booking cue"],
                ),
                "negative_direction": self._append_unique(
                    plan.negative_direction,
                    ["messy service room", "medical fear style", "unclear service result"],
                ),
                "metadata": self._metadata(plan.metadata, "creative_plan", priorities=["service_result", "trust"]),
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None:
            return series
        assets = [
            asset.model_copy(
                update={
                    "purpose": "local service conversion asset with clear result, trust cue, and booking CTA",
                    "requires_text_overlay": True,
                    "metadata": self._metadata(asset.metadata, "asset_spec", asset_role="service_conversion"),
                }
            )
            for asset in series.assets
        ]
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "local service sequence: result detail, trust cue, and booking conversion",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        product_area = layout_plan.product_area.model_copy(
            update={
                "position": "center_service_result",
                "priority": 1,
                "relative_box": {"x": 0.14, "y": 0.24, "w": 0.72, "h": 0.46},
                "notes": "clear service result or clean environment with trust cue",
                "metadata": self._metadata(layout_plan.product_area.metadata, "layout_region", region="service_result"),
            }
        )
        return layout_plan.model_copy(
            update={
                "product_area": product_area,
                "visual_hierarchy": ["service_result", "trust_cue", "offer", "booking_cta"],
                "background_strategy": "clean local-service environment with reliable booking-focused text space",
                "metadata": self._metadata(layout_plan.metadata, "layout_plan", layout_bias="service_conversion"),
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None:
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "visual_prompt": (
                    f"{prompt_compilation.visual_prompt} Local service specialization: show a trustworthy service result, "
                    "clean environment, and appointment-ready commercial mood."
                ),
                "hard_constraints": self._append_unique(
                    prompt_compilation.hard_constraints,
                    ["Service result or service environment must be clear, clean, and trustworthy."],
                ),
                "style_notes": self._append_unique(prompt_compilation.style_notes, ["trustworthy", "service_detail"]),
                "layout_notes": self._append_unique(
                    prompt_compilation.layout_notes,
                    ["service result visible", "provider-directed booking-ready visual mood", "avoid messy environment"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "service_result_required": True,
                    "booking_cta_space_required": False,
                    "provider_native_complete_image": True,
                },
                "metadata": self._metadata(prompt_compilation.metadata, "prompt_compilation", prompt_bias="service_trust"),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "local_service_booking_trust",
            "commercial_score_delta": 0.02,
            "layout_score_delta": 0.015,
            "weighted_priorities": ["service_result", "trust_cue", "booking_cta"],
        }
