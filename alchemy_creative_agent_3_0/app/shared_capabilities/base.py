"""Base class for deterministic shared capability modules."""

from __future__ import annotations

from .contracts import CapabilityInput, CapabilityResult, CapabilityStatus, CapabilityWarning


class SharedCapabilityModule:
    module_id = "shared_capability"
    version = "v1"
    order = 100

    def run(self, capability_input: CapabilityInput) -> CapabilityResult:
        try:
            return self.execute(capability_input)
        except Exception as exc:
            return CapabilityResult(
                module_id=self.module_id,
                version=self.version,
                status=CapabilityStatus.ERROR,
                confidence=0.0,
                warnings=[
                    CapabilityWarning(
                        code="capability_execution_failed",
                        message=f"{self.module_id} failed: {type(exc).__name__}: {str(exc)[:180]}",
                        severity="error",
                    )
                ],
                audit_trail=[f"{self.module_id}: execution failed"],
                metadata={"exception_type": type(exc).__name__},
            )

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        raise NotImplementedError
