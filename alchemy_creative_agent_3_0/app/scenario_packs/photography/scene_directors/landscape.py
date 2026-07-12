"""Landscape-specific Photography direction."""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographySceneDomain
from .base import PhotographySceneDirector


class LandscapePhotographyDirector(PhotographySceneDirector):
    scene_domain = PhotographySceneDomain.LANDSCAPE
    capability_id = "landscape_photography_direction"
    foundation_capabilities_reused = (
        "reference_channel_policy",
        "scene_continuity",
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
                    "viewpoint, weather, atmosphere and light window express a specific sense of place"
                ),
                "framing": (
                    "foreground, middle distance and background establish scale, depth and visual rhythm"
                ),
                "subject_direction": (
                    "use natural land, water, sky and weather behavior as the scene's decisive action"
                ),
                "material_realism": (
                    "rock, foliage, water, sky and atmosphere keep location-plausible structure and depth"
                ),
                "reference_ownership": (
                    "declared landmark or scene geometry remains immutable; weather, time, lighting and color "
                    "remain prompt-owned unless explicitly preserved"
                ),
                "profile_binding_id": profile_binding.profile_id,
            },
            prompt_additions=[
                "Choose a viewpoint that makes foreground, middle distance and background read as real depth.",
                "Coordinate weather, atmosphere and light into one location-plausible moment.",
                "Preserve only declared landmark or scene truth; keep prompt-owned conditions changeable.",
            ],
            negative_additions=[
                "decorative foreground with no scale relationship",
                "weather, sky light and landform shadows that contradict each other",
                "silent inheritance of source weather, time, lighting, color or finish",
            ],
            issue_codes=[
                "landscape_viewpoint_depth_error",
                "landscape_atmosphere_light_coherence_error",
                "landscape_scene_truth_contract_error",
            ],
        )
