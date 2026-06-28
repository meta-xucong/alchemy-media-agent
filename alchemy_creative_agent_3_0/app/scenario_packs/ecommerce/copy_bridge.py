"""Visual-copy bridge for concise e-commerce overlays."""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief
from .utils import clean_text


class EcommerceCopyBridge:
    """Suggest short overlay copy from commerce intent without forcing listing copy workflows."""

    def overlay_for_slot(self, *, slot: str, selling_point: str, brief: CommerceIntelligenceBrief) -> str | None:
        if slot in {"main_image", "hero_image"}:
            return None
        point = clean_text(selling_point)
        if not point:
            return None
        if point.lower().startswith("matches shopper intent:"):
            point = point.split(":", 1)[-1].strip()
        words = point.split()
        if len(words) > 7:
            point = " ".join(words[:7])
        if slot in {"trust_image", "trust_comparison_image"} and brief.trust_drivers:
            return clean_text(brief.trust_drivers[0])[:42]
        if slot in {"size_spec_image", "detail_image"}:
            return point[:46]
        if slot in {"ad_cover", "benefit_hook", "store_banner", "collection_cover"}:
            return point[:38]
        return point[:44]
