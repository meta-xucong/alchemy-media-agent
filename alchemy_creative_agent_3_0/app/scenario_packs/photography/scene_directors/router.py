"""Route a Photography brief to exactly its evidenced first-wave scene director."""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographySceneDomain
from .animal import AnimalPhotographyDirector
from .base import PhotographySceneDirector
from .landscape import LandscapePhotographyDirector
from .portrait import PortraitPhotographyDirector
from .still_life import StillLifePhotographyDirector


class FirstWavePhotographySceneDirectorRouter:
    """Module-local shadow router; it is not registered in the shared capability catalog."""

    def __init__(self, directors: list[PhotographySceneDirector] | None = None) -> None:
        configured = directors or [
            PortraitPhotographyDirector(),
            LandscapePhotographyDirector(),
            StillLifePhotographyDirector(),
            AnimalPhotographyDirector(),
        ]
        self._directors = {director.scene_domain: director for director in configured}
        if len(self._directors) != len(configured):
            raise ValueError("duplicate Photography scene director domain")

    def build_contributions(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        activation_plan_id: str,
    ) -> list[CapabilityContribution]:
        if brief.scene_domain == PhotographySceneDomain.GENERAL:
            return []
        director = self._directors.get(brief.scene_domain)
        if director is None:
            return []
        return [
            director.build_contribution(
                brief=brief,
                profile_binding=profile_binding,
                activation_plan_id=activation_plan_id,
            )
        ]
