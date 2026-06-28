"""Visual grammar lock from references or selected cases."""

from __future__ import annotations

from .base import SharedCapabilityModule
from .contracts import CapabilityConstraint, CapabilityInput, CapabilityResult, CapabilityStatus, CapabilityTargetStage
from .utils import prior_fact


LOCKED_VISUAL_GRAMMAR_ELEMENTS = [
    "composition_framework",
    "main_visual_presence",
    "spatial_hierarchy",
    "layout_rhythm",
    "lighting_logic",
    "mood",
    "background_density",
    "design_language",
    "typography_or_information_treatment",
]

REPLACEABLE_SEMANTIC_ELEMENTS = [
    "subject_identity",
    "product_or_service_content",
    "brand_or_campaign_copy",
    "logo",
    "minor_props",
    "business_offer",
]


class VisualGrammarLockModule(SharedCapabilityModule):
    module_id = "visual_grammar_lock"
    version = "v3_shared_capability_001"
    order = 40

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        cases = prior_fact(capability_input.prior_results, "case_library_retriever", "selected_cases", [])
        bindings = prior_fact(capability_input.prior_results, "asset_binding_planner", "asset_binding_plan", {}).get("bindings", [])
        if not cases and not bindings:
            return CapabilityResult(
                module_id=self.module_id,
                version=self.version,
                status=CapabilityStatus.SKIPPED,
                audit_trail=["no selected cases or reference bindings for visual grammar lock"],
            )
        primary_case = cases[0] if cases else None
        lock_strength = "medium_strong" if primary_case else "medium"
        contract = {
            "lock_strength": lock_strength,
            "primary_case_id": primary_case.get("case_id") if primary_case else None,
            "primary_case_title": primary_case.get("title") if primary_case else None,
            "locked_visual_grammar": LOCKED_VISUAL_GRAMMAR_ELEMENTS,
            "replaceable_semantic_content": REPLACEABLE_SEMANTIC_ELEMENTS,
            "visual_signal_brief": primary_case.get("visual_signals", []) if primary_case else [],
            "reference_binding_count": len(bindings),
            "conflict_policy": "product and information integrity constraints win over style grammar",
        }
        constraints = [
            CapabilityConstraint(
                target_stage=CapabilityTargetStage.LAYOUT_PLAN,
                constraint_type="visual_grammar_lock",
                strength=lock_strength,
                value=contract,
                source=self.module_id,
            ),
            CapabilityConstraint(
                target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                constraint_type="visual_grammar_prompt_guard",
                strength=lock_strength,
                value={
                    "locked": LOCKED_VISUAL_GRAMMAR_ELEMENTS,
                    "replaceable": REPLACEABLE_SEMANTIC_ELEMENTS,
                    "conflict_policy": contract["conflict_policy"],
                },
                source=self.module_id,
            ),
        ]
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.SUCCESS,
            confidence=0.72,
            facts={"visual_grammar_lock": contract},
            constraints=constraints,
            audit_trail=["built visual grammar lock contract"],
        )
