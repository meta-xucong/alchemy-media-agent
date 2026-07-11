from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class SuiteDirectionPlugin(BaseVisualCapabilityPlugin):
    capability_id = "suite_direction"

    def contribute(self, context: VisualPluginContext):
        role_plan = as_dict(context.cluster.get("role_specific_generation_plan"))
        issues = ["role_collapse", "repeated_concept_or_prop", "same_pose_repetition"]
        return self.contribution(
            context,
            prompt=string_list(role_plan.get("prompt_additions")),
            negative=string_list(role_plan.get("negative_additions")),
            review={"issue_codes": issues, "score_dimensions": ["suite_coherence"]},
            retry={"issue_codes": issues},
            stages=["creative_strategy", "generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )
