"""Explicit, disabled-by-default facade for Doc130 canonical prompt planning."""

from __future__ import annotations

from .contracts import (
    CodexNativeImageGenDisabledError,
    NativeImageGenPlanRequest,
    NativeProfessionalImageGenPlanRequest,
    NativeSpecializedImageGenPlanRequest,
)
from .native_planner import CodexNativeImageGenPlanner


class CodexNativeImageGenFacade:
    """No artifact, candidate, review, retry, or delivery state exists here."""

    def __init__(self, *, enabled: bool = False, planner: CodexNativeImageGenPlanner | None = None) -> None:
        self.enabled = bool(enabled)
        self._planner = planner or CodexNativeImageGenPlanner()

    def prepare_native_imagegen_plan(self, request: NativeImageGenPlanRequest) -> dict:
        if not self.enabled:
            raise CodexNativeImageGenDisabledError()
        return self._planner.prepare_native_imagegen_plan(request)

    def prepare_frozen_specialized_native_imagegen_plan(
        self,
        request: NativeSpecializedImageGenPlanRequest,
    ) -> dict:
        """Explicit specialist-only relay; never a General fallback."""

        if not self.enabled:
            raise CodexNativeImageGenDisabledError()
        return self._planner.prepare_frozen_specialized_native_imagegen_plan(request)

    def prepare_frozen_professional_native_imagegen_plan(
        self,
        request: NativeProfessionalImageGenPlanRequest,
    ) -> dict:
        """Explicit Professional relay; no Standard/General fallback."""

        if not self.enabled:
            raise CodexNativeImageGenDisabledError()
        return self._planner.prepare_frozen_professional_native_imagegen_plan(request)
