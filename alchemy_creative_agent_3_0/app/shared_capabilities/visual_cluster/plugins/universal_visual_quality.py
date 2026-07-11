from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class VisualGrammarPlugin(BaseVisualCapabilityPlugin):
    capability_id = "visual_grammar"

    def contribute(self, context: VisualPluginContext):
        profile = as_dict(context.cluster.get("profile"))
        prompt = [
            *string_list(profile.get("style_signals")),
            *string_list(profile.get("composition_rules")),
            *string_list(profile.get("lighting_notes")),
        ]
        return self.contribution(
            context,
            prompt=prompt,
            stages=["creative_strategy", "generation_prompt"] if prompt else [],
        )


class UniversalVisualQualityPlugin(BaseVisualCapabilityPlugin):
    capability_id = "universal_visual_quality"

    def contribute(self, context: VisualPluginContext):
        issues = [
            "unstable_composition_balance",
            "overexposed_washout",
            "uncanny_micro_detail",
            "watermark_or_signature",
        ]
        return self.contribution(
            context,
            prompt=[
                "clear subject hierarchy and intentional composition",
                "believable exposure, color, contrast, depth, and material response",
                "directly usable finish without rendering artifacts or accidental marks",
            ],
            negative=["avoid broken anatomy or geometry", "avoid random text, watermarks, and rendering artifacts"],
            review={"issue_codes": issues, "score_dimensions": ["composition", "technical_finish"]},
            retry={"issue_codes": issues},
            stages=["generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )


class CommercialQualityPlugin(BaseVisualCapabilityPlugin):
    capability_id = "commercial_quality"

    def contribute(self, context: VisualPluginContext):
        return self.contribution(
            context,
            review={"issue_codes": ["low_commercial_finish"], "score_dimensions": ["delivery_usability"]},
            stages=["post_generation_review", "export_validation"],
        )
