"""Deployment-gated Photography Scenario Pack boundary."""

from __future__ import annotations

from ..base import ScenarioPack
from .manifest import photography_manifest


class PhotographyScenarioPack(ScenarioPack):
    """Planning-only pack registered only by the mainline deployment gate."""

    def __init__(self) -> None:
        super().__init__(photography_manifest())
