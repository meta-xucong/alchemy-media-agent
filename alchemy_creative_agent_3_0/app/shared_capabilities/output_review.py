"""Metadata-based output review capability."""

from __future__ import annotations

from .base import SharedCapabilityModule
from .contracts import CapabilityInput, CapabilityResult, CapabilityStatus, CapabilityWarning
from .utils import prior_fact


class OutputReviewModule(SharedCapabilityModule):
    module_id = "output_review"
    version = "v3_shared_capability_001"
    order = 90

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        compiled = prior_fact(capability_input.prior_results, "prompt_constraint_compiler", "compiled_constraints", {})
        evaluation_checks = compiled.get("evaluation_checks", []) if isinstance(compiled, dict) else []
        candidates = capability_input.metadata.get("candidates", [])
        issues: list[dict] = []
        if not candidates:
            issues.append({"code": "metadata_only_review", "message": "No candidate pixels supplied; review is metadata-only."})
        if evaluation_checks:
            issues.append({"code": "evaluation_obligations_present", "message": f"{len(evaluation_checks)} review obligation(s) should be checked."})
        warnings = [
            CapabilityWarning(code="output_review_metadata_only", message="Output review ran without live image inspection.")
        ]
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.WARNING,
            confidence=0.45,
            facts={"output_review": {"issues": issues, "evaluation_check_count": len(evaluation_checks)}},
            warnings=warnings,
            audit_trail=["completed metadata-only output review"],
        )
