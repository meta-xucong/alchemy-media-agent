"""Visual-copy bridge for concise e-commerce overlays."""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief
from .localization import LocalizationProfile
from .product_truth import claim_review_required
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

    def plan_for_slot(
        self,
        *,
        slot: str,
        selling_point: str,
        brief: CommerceIntelligenceBrief,
        localization: LocalizationProfile,
        parameters: dict,
        unsupported_claims: list[str] | None = None,
        text_forbidden_slots: set[str] | None = None,
    ) -> dict[str, object]:
        """Return a reviewable copy plan without pretending to translate text."""

        if slot in (text_forbidden_slots or set()):
            return {
                "text": None,
                "policy": "text_forbidden",
                "source": "marketplace_profile",
                "needs_localization_review": False,
                "claim_review_required": False,
                **localization.metadata(),
            }

        supplied = self._supplied_copy(slot, parameters)
        if supplied:
            text = self._truncate(supplied, localization.character_limit(slot))
            return {
                "text": text,
                "policy": "text_allowed",
                "source": "user_supplied",
                "needs_localization_review": False,
                "truncated": text != supplied,
                "claim_review_required": claim_review_required(text, unsupported_claims),
                **localization.metadata(),
            }

        derived = self.overlay_for_slot(slot=slot, selling_point=selling_point, brief=brief)
        text = self._truncate(derived or "", localization.character_limit(slot)) or None
        return {
            "text": text,
            "policy": "text_allowed",
            "source": "derived",
            "needs_localization_review": bool(text and localization.language != "en"),
            "truncated": bool(derived and text != derived),
            "claim_review_required": claim_review_required(text or "", unsupported_claims),
            **localization.metadata(),
        }

    def _supplied_copy(self, slot: str, parameters: dict) -> str:
        values = parameters.get("overlay_copy") or parameters.get("localized_copy") or parameters.get("copy")
        if isinstance(values, dict):
            return clean_text(values.get(slot) or values.get("default"))
        return clean_text(values)

    def _truncate(self, text: str, limit: int) -> str:
        return clean_text(text)[:limit]
