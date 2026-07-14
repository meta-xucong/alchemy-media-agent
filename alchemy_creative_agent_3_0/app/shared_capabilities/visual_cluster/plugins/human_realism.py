from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class HumanRealismPlugin(BaseVisualCapabilityPlugin):
    capability_id = "human_realism"

    def contribute(self, context: VisualPluginContext):
        guidance = as_dict(context.cluster.get("human_photorealism_guidance"))
        if not guidance.get("applies"):
            return self.contribution(context)
        plugin_metadata = as_dict(as_dict(guidance.get("metadata")).get("human_realism_plugin"))
        hand_detail = plugin_metadata.get("human_subject_kind") == "hand_or_skin_detail"
        issues = (
            ["plastic_skin", "bad_hands_or_body", "flat_scene_lighting", "airbrushed_background_texture"]
            if hand_detail
            else [
                "ai_face_render",
                "plastic_skin",
                "bad_hands_or_body",
                "flat_scene_lighting",
                "airbrushed_background_texture",
                "synthetic_material_response",
                "frozen_centered_pose",
            ]
        )
        return self.contribution(
            context,
            prompt=string_list(guidance.get("positive_prompt_fragments")),
            negative=string_list(guidance.get("negative_prompt_fragments")),
            review={"issue_codes": issues, "score_dimensions": ["human_realism", "anatomy"]},
            retry={
                "templates": as_dict(guidance.get("retry_patch_templates")),
                # The broad template remains only for frozen historical plans.
                # New enforced envelopes select one of these frozen, issue-scoped
                # maps so a skin finding cannot rewrite anatomy, age, or scene.
                "templates_by_issue": as_dict(guidance.get("retry_patch_templates_by_issue")),
            },
            stages=["generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )
