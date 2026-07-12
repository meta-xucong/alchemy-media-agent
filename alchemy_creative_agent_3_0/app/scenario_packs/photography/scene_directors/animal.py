"""Animal-specific Photography direction."""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographySceneDomain
from .base import PhotographySceneDirector


class AnimalPhotographyDirector(PhotographySceneDirector):
    scene_domain = PhotographySceneDomain.ANIMAL
    capability_id = "animal_photography_direction"
    foundation_capabilities_reused = (
        "reference_channel_policy",
        "universal_visual_quality",
    )

    def _build(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        activation_plan_id: str,
    ) -> CapabilityContribution:
        has_reference = bool(brief.reference_policy_summary.get("source_asset_ids"))
        return self.contribution(
            activation_plan_id=activation_plan_id,
            facts={
                "decisive_moment": (
                    "gaze, posture, behavior or movement creates a species-plausible decisive moment"
                ),
                "framing": (
                    "camera height and crop respect animal scale, anatomy, gaze and habitat relation"
                ),
                "subject_direction": (
                    "use safe, natural behavior and body language rather than a human glamour pose"
                ),
                "material_realism": (
                    "fur, feather, scale, eye, limb and motion cues remain species-plausible"
                ),
                "reference_ownership": (
                    "declared non-human subject identity remains immutable; habitat, action, lighting and finish "
                    "remain prompt-owned unless explicitly preserved"
                ),
                "specific_identity_execution_status": (
                    "shared_nonhuman_subject_identity_required_before_production"
                    if has_reference
                    else "not_required_for_text_only_subject"
                ),
                "profile_binding_id": profile_binding.profile_id,
            },
            prompt_additions=[
                "Build the decisive moment from species-plausible gaze, posture, behavior or movement.",
                "Choose camera height and crop from animal scale, anatomy and habitat relationship.",
                "Preserve only declared non-human identity truth; keep prompt-owned scene channels changeable.",
            ],
            negative_additions=[
                "human glamour posing imposed on animal behavior",
                "crop or camera angle that obscures behavior-critical anatomy",
                "silent inheritance of source habitat, action, lighting, color or finish",
            ],
            issue_codes=[
                "animal_behavior_decisive_moment_error",
                "animal_anatomy_motion_material_error",
                "animal_reference_identity_contract_error",
            ],
        )
