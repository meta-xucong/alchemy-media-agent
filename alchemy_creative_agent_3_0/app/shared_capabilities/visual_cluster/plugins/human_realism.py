from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class HumanRealismPlugin(BaseVisualCapabilityPlugin):
    capability_id = "human_realism"

    def contribute(self, context: VisualPluginContext):
        guidance = as_dict(context.cluster.get("human_photorealism_guidance"))
        if not guidance.get("applies"):
            return self.contribution(context)
        issues = ["ai_face_render", "plastic_skin", "bad_hands_or_body"]
        return self.contribution(
            context,
            prompt=string_list(guidance.get("positive_prompt_fragments")),
            negative=string_list(guidance.get("negative_prompt_fragments")),
            review={"issue_codes": issues, "score_dimensions": ["human_realism", "anatomy"]},
            retry={"templates": as_dict(guidance.get("retry_patch_templates"))},
            stages=["generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )
