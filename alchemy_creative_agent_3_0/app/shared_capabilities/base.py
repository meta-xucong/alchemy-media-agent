"""Base class for deterministic shared capability modules."""

from __future__ import annotations

import os
import traceback

from .contracts import CapabilityInput, CapabilityResult, CapabilityStatus, CapabilityWarning


class SharedCapabilityModule:
    module_id = "shared_capability"
    version = "v1"
    order = 100

    def run(self, capability_input: CapabilityInput) -> CapabilityResult:
        try:
            return self.execute(capability_input)
        except Exception as exc:
            traceback_frames = traceback.extract_tb(exc.__traceback__)
            failure_frame = traceback_frames[-1] if traceback_frames else None
            exception_frame = (
                {
                    "source": os.path.basename(failure_frame.filename),
                    "line": int(failure_frame.lineno),
                    "function": str(failure_frame.name)[:100],
                }
                if failure_frame is not None
                else {}
            )
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
                metadata={
                    "exception_type": type(exc).__name__,
                    "exception_frame": exception_frame,
                },
            )

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        raise NotImplementedError
