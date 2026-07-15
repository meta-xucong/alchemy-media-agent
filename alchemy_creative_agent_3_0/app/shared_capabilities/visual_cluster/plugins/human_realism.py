from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list
from ..human_photorealism import HUMAN_REALISM_REVIEW_DIMENSIONS


class HumanRealismPlugin(BaseVisualCapabilityPlugin):
    capability_id = "human_realism"

    def contribute(self, context: VisualPluginContext):
        guidance = as_dict(context.cluster.get("human_photorealism_guidance"))
        if not guidance.get("applies"):
            return self.contribution(context)
        plugin_metadata = as_dict(as_dict(guidance.get("metadata")).get("human_realism_plugin"))
        hand_detail = plugin_metadata.get("human_subject_kind") == "hand_or_skin_detail"
        return self.contribution(
            context,
            prompt=string_list(guidance.get("positive_prompt_fragments")),
            negative=string_list(guidance.get("negative_prompt_fragments")),
            review={
                "issue_codes": list(HUMAN_REALISM_REVIEW_DIMENSIONS),
                "score_dimensions": ["human_realism"],
            },
            retry={"templates": as_dict(guidance.get("retry_patch_templates"))},
            stages=["generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )
