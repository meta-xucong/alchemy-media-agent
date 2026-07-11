from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict, string_list


class PortraitIdentityPlugin(BaseVisualCapabilityPlugin):
    capability_id = "portrait_identity"

    def contribute(self, context: VisualPluginContext):
        card = as_dict(context.cluster.get("subject_identity_card"))
        lock = as_dict(context.cluster.get("portrait_bone_structure_lock"))
        styling = as_dict(context.cluster.get("styling_delta_policy"))
        issues = ["identity_drift", "bone_structure_drift", "identity_feature_drift"]
        return self.contribution(
            context,
            prompt=[
                *string_list(card.get("prompt_additions")),
                *string_list(lock.get("prompt_rules")),
                *string_list(styling.get("prompt_rules")),
            ],
            negative=[
                *string_list(card.get("negative_additions")),
                *string_list(lock.get("forbidden_geometry_drift")),
            ],
            review={"issue_codes": issues, "score_dimensions": ["identity_fidelity"]},
            retry={"issue_codes": issues, "require_reference_image": True},
            stages=["generation_prompt", "negative_prompt", "provider_input_plan", "post_generation_review", "retry_patch"],
        )
