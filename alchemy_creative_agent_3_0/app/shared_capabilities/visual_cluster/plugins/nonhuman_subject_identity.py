from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext


class NonhumanSubjectIdentityPlugin(BaseVisualCapabilityPlugin):
    """Scene-neutral individual-subject identity contract for typed references."""

    capability_id = "nonhuman_subject_identity"

    def contribute(self, context: VisualPluginContext):
        issues = [
            "nonhuman_subject_identity_drift",
            "nonhuman_subject_marking_drift",
            "nonhuman_subject_proportion_drift",
            "nonhuman_reference_used_as_style",
        ]
        return self.contribution(
            context,
            prompt=[
                "preserve the individual non-human subject's stable morphology, head geometry, body proportions, distinctive markings or pattern, and visible coat, feather, scale, or surface character from the typed reference",
                "the current prompt owns habitat, action, camera, lighting, color treatment, and finish; do not recreate the reference frame as a style template",
            ],
            negative=[
                "avoid replacing the referenced individual with a generic subject",
                "avoid changed stable markings, pattern, morphology, or proportions",
                "avoid inheriting the reference habitat, lighting, or whole-image style unless the prompt explicitly requests it",
            ],
            provider_requirements=[
                {
                    "requirement": "native_nonhuman_identity_reference",
                    "input_fidelity": "high",
                    "on_unsupported": "block",
                }
            ],
            review={"issue_codes": issues, "score_dimensions": ["nonhuman_subject_fidelity"]},
            retry={"issue_codes": issues, "max_attempts": 1, "preserve_frozen_evidence": True},
            stages=["generation_prompt", "negative_prompt", "provider_input_plan", "post_generation_review", "retry_patch"],
        )
