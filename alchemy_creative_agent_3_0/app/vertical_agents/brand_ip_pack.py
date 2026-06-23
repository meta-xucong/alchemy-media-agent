"""Brand character vertical pack specialization."""

from .base import VerticalAgentPack
from ..schemas import AssetType


class BrandIPAgentFamily(VerticalAgentPack):
    name = "brand_ip_agent_family"
    supported_industries = ["personal_brand"]
    supported_scenarios = ["brand_character", "mascot_campaign", "character_series"]

    def match(self, creative_job, commercial_brief=None) -> float:
        score = super().match(creative_job, commercial_brief)
        text = self._job_text(creative_job)
        if self._contains_any(
            text,
            ("品牌ip", "品牌 ip", "ip形象", "ip 形象", "吉祥物", "角色", "表情包", "mascot", "brand character", "character"),
        ):
            score = max(score, 0.9)
        return score

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None:
            return brief
        return brief.model_copy(
            update={
                "scenario": "brand_character" if brief.scenario == "brand_or_commercial_poster" else brief.scenario,
                "target_audience": brief.target_audience or "brand followers and social campaign viewers",
                "commercial_hooks": self._append_unique(
                    brief.commercial_hooks,
                    ["recognizable character identity", "brand storytelling", "social shareability"],
                ),
                "selling_points": self._append_unique(
                    brief.selling_points,
                    ["consistent mascot identity", "memorable expression system"],
                ),
                "visual_tone": self._append_unique(brief.visual_tone, ["character_consistent", "friendly", "brand_story"]),
                "copy_strategy": "short character-led brand copy with consistent tone and campaign CTA",
                "platform_notes": {
                    **brief.platform_notes,
                    "vertical_pack": self.name,
                    "brand_character_rule": "preserve mascot identity, expression logic, and brand story fit",
                },
                "metadata": self._metadata(brief.metadata, "commercial_brief", priorities=["identity", "storytelling"]),
            }
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None:
            return plan
        return plan.model_copy(
            update={
                "concept": f"{plan.concept}; brand character-led campaign visual",
                "visual_direction": f"{plan.visual_direction}; consistent mascot or character presence",
                "composition_strategy": (
                    f"{plan.composition_strategy}; keep character face, silhouette, pose language, "
                    "and brand props consistent across assets"
                ),
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["character expression guide", "brand props", "campaign story cues"],
                ),
                "consistency_strategy": (
                    f"{plan.consistency_strategy or ''} Preserve character proportions, expression family, and brand world rules.".strip()
                ),
                "negative_direction": self._append_unique(
                    plan.negative_direction,
                    ["off-model character", "inconsistent face", "unbranded generic mascot"],
                ),
                "metadata": self._metadata(plan.metadata, "creative_plan", priorities=["character_consistency", "brand_story"]),
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None:
            return series
        assets = [
            asset.model_copy(
                update={
                    "asset_type": AssetType.BRAND_STYLE_SAMPLE if index == 0 else asset.asset_type,
                    "purpose": "brand character campaign asset with reusable identity cues" if index == 0 else asset.purpose,
                    "requires_brand_consistency": True,
                    "metadata": self._metadata(asset.metadata, "asset_spec", asset_role="character_identity" if index == 0 else asset.asset_type.value),
                }
            )
            for index, asset in enumerate(series.assets)
        ]
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "brand character sequence: identity anchor plus social campaign variants",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        product_area = layout_plan.product_area.model_copy(
            update={
                "position": "center_character_anchor",
                "priority": 1,
                "relative_box": {"x": 0.18, "y": 0.18, "w": 0.64, "h": 0.58},
                "notes": "character anchor with preserved face, silhouette, pose, and brand props",
                "metadata": self._metadata(layout_plan.product_area.metadata, "layout_region", region="character_anchor"),
            }
        )
        return layout_plan.model_copy(
            update={
                "product_area": product_area,
                "visual_hierarchy": ["character_anchor", "brand_story", "campaign_copy", "brand_mark"],
                "background_strategy": "brand world background that supports the character without changing identity",
                "metadata": self._metadata(layout_plan.metadata, "layout_plan", layout_bias="character_identity"),
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None:
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "visual_prompt": (
                    f"{prompt_compilation.visual_prompt} Brand character specialization: preserve one original character "
                    "identity, expression family, silhouette, and story-world consistency."
                ),
                "hard_constraints": self._append_unique(
                    prompt_compilation.hard_constraints,
                    ["Keep character identity consistent across face, silhouette, pose language, and brand props."],
                ),
                "style_notes": self._append_unique(prompt_compilation.style_notes, ["character_consistent", "brand_story"]),
                "layout_notes": self._append_unique(
                    prompt_compilation.layout_notes,
                    ["character anchor unobstructed", "brand story background supports identity"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "character_identity_required": True,
                    "avoid_unlicensed_or_named_characters": True,
                },
                "metadata": self._metadata(prompt_compilation.metadata, "prompt_compilation", prompt_bias="character_consistency"),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "brand_character_consistency",
            "brand_consistency_score_delta": 0.04,
            "layout_score_delta": 0.01,
            "weighted_priorities": ["character_identity", "brand_story", "social_shareability"],
        }
