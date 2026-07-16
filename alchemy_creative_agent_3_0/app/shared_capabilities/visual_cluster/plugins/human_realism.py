from __future__ import annotations

from .base import BaseVisualCapabilityPlugin, VisualPluginContext, as_dict
from ..human_photorealism import HUMAN_REALISM_REVIEW_DIMENSIONS


class HumanRealismPlugin(BaseVisualCapabilityPlugin):
    capability_id = "human_realism"

    def contribute(self, context: VisualPluginContext):
        guidance = as_dict(context.cluster.get("human_photorealism_guidance"))
        if not guidance.get("applies"):
            return self.contribution(context)
        semantic_contract = as_dict(guidance.get("semantic_contract"))
        review_issue_codes = [
            str(item)
            for item in semantic_contract.get("quality_axes", [])
            if str(item) in HUMAN_REALISM_REVIEW_DIMENSIONS
        ]
        human_authenticity_contract = {
            key: semantic_contract.get(key)
            for key in (
                "contract_version",
                "personhood_requirement",
                "expression_ownership_requirement",
                "complexion_rendering_requirement",
                "photographic_material_requirement",
            )
        }
        return self.contribution(
            context,
            # The active capability preserves review ownership and evidence,
            # not a second local renderer prompt.  The remote Brain consumes
            # the frozen semantics and later signs the full image language.
            prompt=[],
            negative=[],
            review={
                "issue_codes": review_issue_codes,
                "score_dimensions": ["human_realism"],
                # This is a frozen review obligation, never provider prompt
                # prose.  It is copied from the active shared semantic
                # contract so stale mutable metadata cannot opt a job in.
                "human_authenticity_contract": human_authenticity_contract,
                "human_naturalness_verdict_required": (
                    semantic_contract.get("expression_ownership_requirement")
                    == "situation_owned_unless_explicit_user_direction"
                ),
            },
            retry={
                "issue_codes": review_issue_codes,
                "metadata": {"retry_evidence_only": True},
            },
            stages=["post_generation_review", "retry_patch"],
        )
