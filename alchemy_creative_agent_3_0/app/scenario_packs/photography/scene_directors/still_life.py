"""Still-life-specific Photography direction."""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographySceneDomain
from .base import PhotographySceneDirector


class StillLifePhotographyDirector(PhotographySceneDirector):
    scene_domain = PhotographySceneDomain.STILL_LIFE
    capability_id = "still_life_photography_direction"
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
        return self.contribution(
            activation_plan_id=activation_plan_id,
            facts={
                "decisive_moment": (
                    "object grouping, negative space and set light reach an intentional final arrangement"
                ),
                "framing": (
                    "object edges, surface relation and negative space remain controlled and readable"
                ),
                "subject_direction": (
                    "arrange objects by visual weight, material contrast and spatial relationship"
                ),
                "material_realism": (
                    "surface, edge, reflection, translucency and contact-shadow cues stay physically coherent"
                ),
                "reference_ownership": (
                    "declared object truth remains immutable; grouping, surface, background, lighting and finish "
                    "remain prompt-owned unless explicitly preserved"
                ),
                "deliverable_boundary": (
                    "still-life photography only; no marketplace listing, A+ or commerce package roles"
                ),
                "profile_binding_id": profile_binding.profile_id,
            },
            prompt_additions=[
                "Arrange objects by visual weight, material contrast and intentional negative space.",
                "Use controlled set light to reveal edges, reflections, translucency and contact shadows.",
                "Preserve only declared object truth; keep prompt-owned set and finish channels changeable.",
            ],
            negative_additions=[
                "floating objects or contact shadows detached from the set",
                "impossible reflection, translucency or material-edge behavior",
                "silent inheritance of source grouping, surface, background, lighting or finish",
            ],
            issue_codes=[
                "still_life_grouping_negative_space_error",
                "still_life_material_edge_reflection_error",
                "still_life_object_truth_contract_error",
            ],
        )
