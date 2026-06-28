"""Reference asset binding and conditioning strategy."""

from __future__ import annotations

from typing import Any

from .base import SharedCapabilityModule
from .contracts import (
    AssetRole,
    CapabilityConstraint,
    CapabilityInput,
    CapabilityResult,
    CapabilityStatus,
    CapabilityTargetStage,
    CapabilityWarning,
)
from .utils import prior_fact, role_value


ROLE_PRIORITY = {
    AssetRole.PRODUCT_REFERENCE.value: 90,
    AssetRole.FACE_REFERENCE.value: 82,
    AssetRole.LOGO_REFERENCE.value: 78,
    AssetRole.BACKGROUND_REFERENCE.value: 68,
    AssetRole.STYLE_REFERENCE.value: 52,
    AssetRole.COMPOSITION_REFERENCE.value: 48,
    AssetRole.COLOR_REFERENCE.value: 42,
    AssetRole.NEGATIVE_REFERENCE.value: 20,
    AssetRole.UNKNOWN_REFERENCE.value: 5,
}


class AssetBindingPlanner(SharedCapabilityModule):
    module_id = "asset_binding_planner"
    version = "v3_shared_capability_001"
    order = 20

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        analyses = prior_fact(capability_input.prior_results, "asset_role_analyzer", "asset_analyses", [])
        if not analyses:
            analyses = [
                {
                    "asset_id": asset.asset_id,
                    "role": role_value(asset.role or AssetRole.UNKNOWN_REFERENCE),
                    "identity_requirements": [],
                    "provider_input_required": False,
                }
                for asset in capability_input.uploaded_assets
            ]
        if not analyses:
            return CapabilityResult(
                module_id=self.module_id,
                version=self.version,
                status=CapabilityStatus.SKIPPED,
                audit_trail=["no uploaded assets available for binding"],
            )

        bindings = sorted((self._binding_for(item) for item in analyses), key=lambda item: (-item["priority"], item["asset_id"]))
        warnings = self._conflict_warnings(bindings)
        constraints = [
            CapabilityConstraint(
                target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                constraint_type="reference_asset_binding",
                strength=binding["constraint_strength"],
                value=binding,
                source=self.module_id,
            )
            for binding in bindings
        ]
        status = CapabilityStatus.WARNING if warnings else CapabilityStatus.SUCCESS
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=status,
            confidence=0.75,
            facts={"asset_binding_plan": {"bindings": bindings, "binding_count": len(bindings)}},
            constraints=constraints,
            warnings=warnings,
            audit_trail=[f"created {len(bindings)} asset binding(s)"],
        )

    def _binding_for(self, analysis: dict[str, Any]) -> dict[str, Any]:
        role = str(analysis.get("role") or AssetRole.UNKNOWN_REFERENCE.value)
        priority = ROLE_PRIORITY.get(role, 5)
        strength = "strong" if role in {AssetRole.PRODUCT_REFERENCE.value, AssetRole.LOGO_REFERENCE.value, AssetRole.FACE_REFERENCE.value} else "medium" if priority >= 48 else "soft"
        allowed_transformations = {
            AssetRole.PRODUCT_REFERENCE.value: ["scene change", "lighting polish", "background replacement"],
            AssetRole.LOGO_REFERENCE.value: ["placement change only when readable"],
            AssetRole.FACE_REFERENCE.value: ["lighting polish", "pose-compatible styling"],
            AssetRole.BACKGROUND_REFERENCE.value: ["compatible product insertion"],
            AssetRole.STYLE_REFERENCE.value: ["palette and finish adaptation"],
            AssetRole.COMPOSITION_REFERENCE.value: ["abstract layout guidance"],
            AssetRole.COLOR_REFERENCE.value: ["palette adaptation"],
            AssetRole.NEGATIVE_REFERENCE.value: ["avoidance only"],
        }.get(role, ["soft inspiration"])
        forbidden_transformations = {
            AssetRole.PRODUCT_REFERENCE.value: ["product shape drift", "material invention", "logo removal"],
            AssetRole.LOGO_REFERENCE.value: ["logo distortion", "unreadable brand mark"],
            AssetRole.FACE_REFERENCE.value: ["identity drift"],
            AssetRole.BACKGROUND_REFERENCE.value: ["background overriding product truth"],
            AssetRole.NEGATIVE_REFERENCE.value: ["using negative reference as positive style"],
        }.get(role, [])
        return {
            "asset_id": analysis.get("asset_id"),
            "role": role,
            "priority": priority,
            "constraint_strength": strength,
            "provider_input_required": bool(analysis.get("provider_input_required")) or strength == "strong",
            "allowed_transformations": allowed_transformations,
            "forbidden_transformations": forbidden_transformations,
            "placement_intent": self._placement_for_role(role),
            "review_expectations": analysis.get("identity_requirements", []),
        }

    def _placement_for_role(self, role: str) -> str:
        if role == AssetRole.PRODUCT_REFERENCE.value:
            return "main product identity source"
        if role == AssetRole.LOGO_REFERENCE.value:
            return "brand mark exactness source"
        if role == AssetRole.BACKGROUND_REFERENCE.value:
            return "background environment source"
        if role == AssetRole.COMPOSITION_REFERENCE.value:
            return "layout and camera guide"
        if role == AssetRole.NEGATIVE_REFERENCE.value:
            return "avoidance reference"
        return "soft reference"

    def _conflict_warnings(self, bindings: list[dict[str, Any]]) -> list[CapabilityWarning]:
        warnings: list[CapabilityWarning] = []
        hard_roles = {AssetRole.PRODUCT_REFERENCE.value, AssetRole.LOGO_REFERENCE.value, AssetRole.FACE_REFERENCE.value}
        for role in hard_roles:
            role_bindings = [binding for binding in bindings if binding["role"] == role]
            if len(role_bindings) > 1:
                warnings.append(
                    CapabilityWarning(
                        code="asset_binding_role_conflict",
                        message=f"Multiple uploaded assets compete for hard role '{role}'.",
                        metadata={"asset_ids": [binding["asset_id"] for binding in role_bindings]},
                    )
                )
        return warnings
