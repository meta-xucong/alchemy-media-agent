"""Retired local E-Commerce visual-planning compatibility surface.

Earlier versions generated a fixed marketplace/category slot map here.  New
jobs must send factual context to the remote V3 Central Brain instead.  The
class remains only so archived callers fail safely without reintroducing local
creative direction.
"""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief, EcommerceAssetRecipe, MarketplaceRuleProfile, ProductTruthLock


class SellingPointToImagePlanner:
    """Compatibility shim that deliberately creates no image recipe."""

    def plan(
        self,
        *,
        truth: ProductTruthLock,
        brief: CommerceIntelligenceBrief,
        marketplace_profile: MarketplaceRuleProfile,
        uploaded_asset_ids: list[str],
        category_profile: object | None = None,
        scenario_parameters: dict | None = None,
    ) -> list[EcommerceAssetRecipe]:
        del truth, brief, marketplace_profile, uploaded_asset_ids, category_profile, scenario_parameters
        return []
