from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext


class TextPixelDeliveryPlugin(BaseVisualCapabilityPlugin):
    """Declare only the frozen shared review/retry vocabulary.

    Composition itself is a post-generation delivery stage.  It has no prompt
    contribution and therefore cannot cause a model to claim that it rendered
    final copy pixels.
    """

    capability_id = "text_pixel_delivery"

    def contribute(self, context: VisualPluginContext):
        return self.contribution(
            context,
            review={
                "issue_codes": [
                    "ocr_text_mismatch",
                    "layout_overflow",
                    "safe_area_violation",
                    "text_low_contrast",
                    "forbidden_text_detected",
                ],
                "final_pixel_required": True,
            },
            retry={
                "issue_codes": ["text_background_readability_failure"],
                "max_generation_retries": 1,
                "requires_existing_shared_retry": True,
            },
            stages=["post_generation_review", "retry_patch", "deterministic_composition"],
        )
