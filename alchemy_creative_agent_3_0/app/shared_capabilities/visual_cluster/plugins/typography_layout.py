from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class TypographyLayoutPlugin(BaseVisualCapabilityPlugin):
    capability_id = "typography_layout"

    def contribute(self, context: VisualPluginContext):
        profile = as_dict(context.cluster.get("profile"))
        issues = ["visible_text_artifact", "composition_mismatch"]
        return self.contribution(
            context,
            prompt=string_list(profile.get("layout_notes")) or ["preserve the requested layout hierarchy and crop-safe regions"],
            negative=["avoid incorrect, invented, duplicated, or unreadable visible text"],
            review={"issue_codes": issues, "score_dimensions": ["layout_integrity"]},
            retry={"issue_codes": issues},
            stages=["generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )
