"""Registry and deterministic runner for shared capabilities."""

from __future__ import annotations

from collections.abc import Iterable

from .base import SharedCapabilityModule
from .contracts import (
    CapabilityInput,
    CapabilityResult,
    CapabilityRunResult,
    CapabilityRunStatus,
    CapabilityStatus,
    CapabilityWarning,
)


class SharedCapabilityRegistry:
    """Register and execute shared capability modules in deterministic order."""

    def __init__(self, modules: Iterable[SharedCapabilityModule] | None = None) -> None:
        self._modules: dict[str, SharedCapabilityModule] = {}
        for module in modules or []:
            self.register(module)

    @classmethod
    def with_default_modules(cls) -> "SharedCapabilityRegistry":
        from .asset_binding_planner import AssetBindingPlanner
        from .asset_role_analyzer import AssetRoleAnalyzer
        from .case_library import CaseLibraryRetriever
        from .history_reference import HistoryReferenceModule
        from .information_integrity import InformationIntegrityLockModule
        from .output_review import OutputReviewModule
        from .prompt_constraint_compiler import PromptConstraintCompiler
        from .visual_grammar_lock import VisualGrammarLockModule

        return cls(
            [
                AssetRoleAnalyzer(),
                AssetBindingPlanner(),
                CaseLibraryRetriever(),
                VisualGrammarLockModule(),
                InformationIntegrityLockModule(),
                PromptConstraintCompiler(),
                OutputReviewModule(),
                HistoryReferenceModule(),
            ]
        )

    def register(self, module: SharedCapabilityModule) -> None:
        self._modules[module.module_id] = module

    def get(self, module_id: str) -> SharedCapabilityModule | None:
        return self._modules.get(module_id)

    def list_modules(self) -> list[SharedCapabilityModule]:
        return sorted(self._modules.values(), key=lambda module: (module.order, module.module_id))

    def run(
        self,
        capability_input: CapabilityInput,
        module_ids: list[str] | None = None,
        required_module_ids: list[str] | None = None,
    ) -> CapabilityRunResult:
        required = set(required_module_ids or [])
        selected = self._select_modules(module_ids)
        results: list[CapabilityResult] = []
        warnings: list[CapabilityWarning] = []
        required_failures: list[str] = []
        prior_results = list(capability_input.prior_results)

        missing_ids = [module_id for module_id in (module_ids or []) if module_id not in self._modules]
        for module_id in missing_ids:
            warning = CapabilityWarning(
                code="capability_not_registered",
                message=f"Shared capability '{module_id}' is not registered.",
                severity="error" if module_id in required else "warning",
            )
            warnings.append(warning)
            if module_id in required:
                required_failures.append(module_id)

        for module in selected:
            run_input = capability_input.model_copy(update={"prior_results": list(prior_results)})
            result = module.run(run_input)
            results.append(result)
            prior_results.append(result)
            warnings.extend(result.warnings)
            if result.status == CapabilityStatus.ERROR and module.module_id in required:
                required_failures.append(module.module_id)

        if required_failures:
            status = CapabilityRunStatus.FAILED
        elif any(result.status == CapabilityStatus.ERROR for result in results) or missing_ids:
            status = CapabilityRunStatus.DEGRADED
        else:
            status = CapabilityRunStatus.COMPLETE

        return CapabilityRunResult(
            status=status,
            results=results,
            warnings=warnings,
            required_failures=sorted(set(required_failures)),
            metadata={
                "module_ids": [result.module_id for result in results],
                "required_module_ids": sorted(required),
            },
        )

    def _select_modules(self, module_ids: list[str] | None) -> list[SharedCapabilityModule]:
        if module_ids is None:
            return self.list_modules()
        selected = [self._modules[module_id] for module_id in module_ids if module_id in self._modules]
        return sorted(selected, key=lambda module: (module.order, module.module_id))
