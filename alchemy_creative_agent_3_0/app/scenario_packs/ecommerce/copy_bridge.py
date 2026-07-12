"""Prepare optional provider-native text intent without writing an overlay."""

from __future__ import annotations

from .contracts import CommerceIntelligenceBrief
from .localization import LocalizationProfile
from .product_truth import claim_review_required
from .utils import clean_text


class EcommerceCopyBridge:
    """Keep approved wording intact and leave creative typography to the LLM/provider."""

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
        """Return a text intent, never a local overlay or auto-written promotion."""

        if slot in (text_forbidden_slots or set()):
            return {
                "text": None,
                "policy": "text_forbidden",
                "source": "marketplace_profile",
                "needs_localization_review": False,
                "claim_review_required": False,
                "provider_native_text": False,
                "final_pixel_review_required": True,
                **localization.metadata(),
            }

        supplied = self._supplied_copy(slot, parameters)
        if supplied:
            return {
                "text": supplied,
                "policy": "text_requested",
                "source": "user_supplied",
                "needs_localization_review": False,
                "truncated": False,
                "claim_review_required": claim_review_required(supplied, unsupported_claims),
                "provider_native_text": True,
                "final_pixel_review_required": True,
                **localization.metadata(),
            }

        return {
            "text": None,
            "policy": "text_optional",
            "source": "llm_creative_direction",
            "needs_localization_review": False,
            "truncated": False,
            "claim_review_required": False,
            "provider_native_text": False,
            "final_pixel_review_required": False,
            "creative_direction": clean_text(selling_point),
            **localization.metadata(),
        }

    def _supplied_copy(self, slot: str, parameters: dict) -> str:
        values = parameters.get("overlay_copy") or parameters.get("localized_copy") or parameters.get("copy")
        if isinstance(values, dict):
            return clean_text(values.get(slot) or values.get("default"))
        return clean_text(values)
