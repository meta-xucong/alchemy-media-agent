"""Compile capability facts into prompt/layout/evaluation constraint fragments."""

from __future__ import annotations

from .base import SharedCapabilityModule
from .contracts import CapabilityConstraint, CapabilityInput, CapabilityResult, CapabilityStatus
from .utils import all_prior_constraints


class PromptConstraintCompiler(SharedCapabilityModule):
    module_id = "prompt_constraint_compiler"
    version = "v3_shared_capability_001"
    order = 80

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        constraints = self._dedupe_constraints(all_prior_constraints(capability_input.prior_results))
        prompt_constraints = [item for item in constraints if item.target_stage.value == "prompt_compilation"]
        layout_constraints = [item for item in constraints if item.target_stage.value == "layout_plan"]
        evaluation_checks = [item for item in constraints if item.target_stage.value == "evaluation"]
        negative_constraints = [
            item
            for item in prompt_constraints
            if "negative" in item.constraint_type or "forbidden" in item.constraint_type
        ]
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.SUCCESS if constraints else CapabilityStatus.SKIPPED,
            confidence=0.76 if constraints else 0.0,
            facts={
                "compiled_constraints": {
                    "prompt_constraints": [item.model_dump(mode="json") for item in prompt_constraints],
                    "layout_constraints": [item.model_dump(mode="json") for item in layout_constraints],
                    "evaluation_checks": [item.model_dump(mode="json") for item in evaluation_checks],
                    "negative_constraints": [item.model_dump(mode="json") for item in negative_constraints],
                }
            },
            constraints=constraints,
            audit_trail=[f"compiled {len(constraints)} unique capability constraint(s)"],
        )

    def _dedupe_constraints(self, constraints: list[CapabilityConstraint]) -> list[CapabilityConstraint]:
        seen: set[tuple[str, str, str]] = set()
        unique: list[CapabilityConstraint] = []
        for item in constraints:
            key = (item.target_stage.value, item.constraint_type, str(item.value))
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
        return unique
