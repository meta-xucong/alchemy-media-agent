from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class SceneContinuityPlugin(BaseVisualCapabilityPlugin):
    capability_id = "scene_continuity"

    def contribute(self, context: VisualPluginContext):
        consistency = as_dict(context.cluster.get("consistency_guard"))
        issues = ["scene_identity_drift", "background_space_drift", "camera_mood_drift"]
        return self.contribution(
            context,
            prompt=[
                "preserve requested spatial layout, landmarks, background identity, depth relationships, and camera relation while letting the current prompt own lighting and style",
                *string_list(consistency.get("keep_rules")),
            ],
            negative=["avoid scene replacement, landmark drift, or incompatible spatial relationships"],
            review={"issue_codes": issues, "score_dimensions": ["scene_continuity"]},
            retry={"issue_codes": issues},
            stages=["generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
        )
