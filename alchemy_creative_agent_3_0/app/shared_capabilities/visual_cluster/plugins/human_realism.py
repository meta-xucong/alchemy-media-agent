from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict
from ..human_photorealism import HUMAN_REALISM_REVIEW_DIMENSIONS


class HumanRealismPlugin(BaseVisualCapabilityPlugin):
    capability_id = "human_realism"

    def contribute(self, context: VisualPluginContext):
        guidance = as_dict(context.cluster.get("human_photorealism_guidance"))
        if not guidance.get("applies"):
            return self.contribution(context)
        plugin_metadata = as_dict(as_dict(guidance.get("metadata")).get("human_realism_plugin"))
        hand_detail = plugin_metadata.get("human_subject_kind") == "hand_or_skin_detail"
        return self.contribution(
            context,
            # The active capability preserves review ownership and evidence,
            # not a second local renderer prompt.  The remote Brain consumes
            # the frozen semantics and later signs the full image language.
            prompt=[],
            negative=[],
            review={
                "issue_codes": list(HUMAN_REALISM_REVIEW_DIMENSIONS),
                "score_dimensions": ["human_realism"],
            },
            retry={
                "issue_codes": list(HUMAN_REALISM_REVIEW_DIMENSIONS),
                "metadata": {"retry_evidence_only": True},
            },
            stages=["post_generation_review", "retry_patch"],
        )
