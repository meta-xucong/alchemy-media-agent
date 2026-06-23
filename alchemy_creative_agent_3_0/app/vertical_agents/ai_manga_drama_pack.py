"""Original sequential story-scene vertical pack specialization."""

from .base import VerticalAgentPack
from ..schemas import AssetType, Platform


class AIMangaDramaAgentFamily(VerticalAgentPack):
    name = "ai_manga_drama_agent_family"
    supported_industries: list[str] = []
    supported_scenarios = ["story_scene", "character_series"]

    def match(self, creative_job, commercial_brief=None) -> float:
        score = super().match(creative_job, commercial_brief)
        text = self._job_text(creative_job)
        if self._contains_any(
            text,
            (
                "漫剧",
                "漫画",
                "短剧",
                "分镜",
                "角色设定",
                "连续剧情",
                "story scene",
                "storyboard",
                "comic",
                "drama scene",
                "episode cover",
            ),
        ):
            score = max(score, 0.9)
        return score

    def refine_commercial_brief(self, context):
        brief = context.commercial_brief
        if brief is None:
            return brief
        return brief.model_copy(
            update={
                "scenario": "story_scene" if brief.scenario == "brand_or_commercial_poster" else brief.scenario,
                "target_audience": brief.target_audience or "story-driven social and short-video viewers",
                "commercial_hooks": self._append_unique(
                    brief.commercial_hooks,
                    ["scene continuity", "character recognition", "episode curiosity"],
                ),
                "selling_points": self._append_unique(
                    brief.selling_points,
                    ["consistent character sheet", "clear story moment"],
                ),
                "visual_tone": self._append_unique(brief.visual_tone, ["cinematic", "sequential", "character_consistent"]),
                "copy_strategy": "short episode-style hook with clear story tension and CTA",
                "platform_notes": {
                    **brief.platform_notes,
                    "vertical_pack": self.name,
                    "story_scene_rule": "preserve original character continuity and scene-to-scene readability",
                },
                "metadata": self._metadata(brief.metadata, "commercial_brief", priorities=["continuity", "episode_hook"]),
            }
        )

    def refine_creative_plan(self, context):
        plan = context.creative_plan
        if plan is None:
            return plan
        return plan.model_copy(
            update={
                "concept": f"{plan.concept}; sequential story key visual",
                "visual_direction": f"{plan.visual_direction}; cinematic original story-scene treatment",
                "composition_strategy": (
                    f"{plan.composition_strategy}; maintain character continuity, readable action, "
                    "and episode-cover framing"
                ),
                "materials_and_props": self._append_unique(
                    plan.materials_and_props,
                    ["character continuity notes", "scene props", "episode mood cue"],
                ),
                "consistency_strategy": (
                    f"{plan.consistency_strategy or ''} Preserve original character identity and scene continuity across outputs.".strip()
                ),
                "negative_direction": self._append_unique(
                    plan.negative_direction,
                    ["off-model character", "confusing panel order", "unreadable scene action"],
                ),
                "metadata": self._metadata(plan.metadata, "creative_plan", priorities=["character_continuity", "scene_readability"]),
            }
        )

    def refine_series_plan(self, context):
        series = context.series_plan
        if series is None:
            return series
        assets = []
        for index, asset in enumerate(series.assets):
            asset_type = AssetType.BRAND_STYLE_SAMPLE if index == 0 else AssetType.SOCIAL_COVER
            platform = Platform.DOUYIN if asset.platform == Platform.GENERIC_SOCIAL and index > 0 else asset.platform
            assets.append(
                asset.model_copy(
                    update={
                        "asset_type": asset_type,
                        "platform": platform,
                        "aspect_ratio": "9:16" if platform == Platform.DOUYIN else asset.aspect_ratio,
                        "purpose": "story-scene continuity asset with original character consistency",
                        "requires_brand_consistency": True,
                        "metadata": self._metadata(
                            asset.metadata,
                            "asset_spec",
                            asset_role="character_sheet" if index == 0 else "episode_scene",
                        ),
                    }
                )
            )
        return series.model_copy(
            update={
                "assets": assets,
                "series_strategy": "story sequence: character identity anchor plus episode-scene key visuals",
                "metadata": self._metadata(series.metadata, "series_plan", asset_count=len(assets)),
            }
        )

    def refine_layout_plan(self, context, layout_plan):
        if layout_plan is None:
            return layout_plan
        product_area = layout_plan.product_area.model_copy(
            update={
                "position": "center_story_scene",
                "priority": 1,
                "relative_box": {"x": 0.12, "y": 0.18, "w": 0.76, "h": 0.60},
                "notes": "original character and key scene action remain readable without protected references",
                "metadata": self._metadata(layout_plan.product_area.metadata, "layout_region", region="story_scene"),
            }
        )
        return layout_plan.model_copy(
            update={
                "product_area": product_area,
                "visual_hierarchy": ["character_action", "scene_context", "episode_hook", "brand_or_series_mark"],
                "background_strategy": "cinematic story background that clarifies the scene and preserves text-safe regions",
                "metadata": self._metadata(layout_plan.metadata, "layout_plan", layout_bias="scene_continuity"),
            }
        )

    def refine_prompt_compilation(self, context, prompt_compilation):
        if prompt_compilation is None:
            return prompt_compilation
        return prompt_compilation.model_copy(
            update={
                "visual_prompt": (
                    f"{prompt_compilation.visual_prompt} Sequential story specialization: render an original character "
                    "and clear scene moment with continuity-safe details and episode-cover energy."
                ),
                "hard_constraints": self._append_unique(
                    prompt_compilation.hard_constraints,
                    ["Use original characters only; preserve character continuity and readable scene action."],
                ),
                "style_notes": self._append_unique(prompt_compilation.style_notes, ["cinematic", "sequential", "character_continuity"]),
                "layout_notes": self._append_unique(
                    prompt_compilation.layout_notes,
                    ["scene action readable", "character identity unobstructed", "episode hook text area reserved"],
                ),
                "provider_notes": {
                    **prompt_compilation.provider_notes,
                    "vertical_pack": self.name,
                    "character_continuity_required": True,
                    "original_characters_only": True,
                },
                "metadata": self._metadata(prompt_compilation.metadata, "prompt_compilation", prompt_bias="story_continuity"),
            }
        )

    def refine_evaluation_policy(self, context):
        return {
            **super().refine_evaluation_policy(context),
            "mode": "story_scene_continuity",
            "brand_consistency_score_delta": 0.025,
            "layout_score_delta": 0.02,
            "weighted_priorities": ["character_continuity", "scene_readability", "episode_hook"],
        }
