"""Inactive Photography Scenario Pack boundary."""

from __future__ import annotations

from ..base import ScenarioPack
from .manifest import PHOTOGRAPHY_MANIFEST


class PhotographyScenarioPack(ScenarioPack):
    """Module-local pack that remains absent from the production registry."""

    manifest = PHOTOGRAPHY_MANIFEST
