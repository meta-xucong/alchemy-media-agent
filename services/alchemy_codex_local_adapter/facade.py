"""Explicit, disabled-by-default facade for Doc126 prompt planning only."""

from __future__ import annotations

from .contracts import (
    CodexNativeImageGenDisabledError,
    NativeImageGenPlanRequest,
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
