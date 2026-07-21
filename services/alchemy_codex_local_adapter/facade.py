"""Explicit, disabled-by-default facade for legacy canonical prompt planning.

Materialized MCP handoffs are handled by the separate localhost bridge and
the shared V3 runtime; this facade remains conversation-only by design.
"""

from __future__ import annotations

from .contracts import (
    CodexNativeImageGenDisabledError,
    NativeImageGenPlanRequest,
    NativeProfessionalImageGenPlanRequest,
    NativeSpecializedImageGenPlanRequest,
)
from .native_planner import CodexNativeImageGenPlanner
from .professional_binding import persistent_professional_binding_resolver


class CodexNativeImageGenFacade:
    """Legacy planner state only; it never owns materialized V3 delivery."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        planner: CodexNativeImageGenPlanner | None = None,
        professional_binding_resolver=None,
        professional_asset_catalog_root=None,
    ) -> None:
        self.enabled = bool(enabled)
        if planner is not None and (
            professional_binding_resolver is not None
            or professional_asset_catalog_root is not None
        ):
            raise ValueError("planner and Professional binding configuration are mutually exclusive")
        if planner is not None:
            self._planner = planner
        else:
            resolver = professional_binding_resolver
            if resolver is None and professional_asset_catalog_root is not None:
                resolver = persistent_professional_binding_resolver(professional_asset_catalog_root)
            self._planner = CodexNativeImageGenPlanner(
                professional_binding_resolver=resolver,
            )

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
