"""Reference asset binding and conditioning strategy."""

from __future__ import annotations

from typing import Any

from ..creative_core.mcp_reference_partition import (
    McpBodyReferencePartition,
    build_mcp_body_reference_partition,
)
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
    AssetRole.NONHUMAN_IDENTITY_REFERENCE.value: 86,
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
        try:
            body_mcp_partition = self._body_mcp_partition(capability_input)
        except Exception as exc:
            if self._is_strict_body_mcp(capability_input):
                failure_code = str(exc).strip() or "body_mcp_reference_partition_invalid"
                return CapabilityResult(
                    module_id=self.module_id,
                    version=self.version,
                    status=CapabilityStatus.ERROR,
                    facts={
                        "body_mcp_reference_partition_failure": {
                            "failure_code": failure_code,
                            "owner": "asset_binding_planner",
                        }
                    },
                    warnings=[
                        CapabilityWarning(
                            code="body_mcp_reference_partition_invalid",
                            message="Strict Body MCP reference partition admission failed.",
                            severity="error",
                            metadata={"failure_code": failure_code},
                        )
                    ],
                    audit_trail=["strict Body MCP partition admission blocked"],
                )
            body_mcp_partition = None
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
        if body_mcp_partition is not None:
            capability_input.metadata["body_mcp_reference_partition"] = body_mcp_partition.model_dump(
                mode="json"
            )
        warnings = self._conflict_warnings(
            bindings,
            body_mcp_partition=body_mcp_partition,
            professional_product_truth_pool=self._professional_product_truth_pool(
                capability_input,
                bindings,
            ),
        )
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
        strength = "strong" if role in {AssetRole.PRODUCT_REFERENCE.value, AssetRole.LOGO_REFERENCE.value, AssetRole.FACE_REFERENCE.value, AssetRole.NONHUMAN_IDENTITY_REFERENCE.value} else "medium" if priority >= 48 else "soft"
        allowed_transformations = {
            AssetRole.PRODUCT_REFERENCE.value: ["scene change", "lighting polish", "background replacement"],
            AssetRole.LOGO_REFERENCE.value: ["placement change only when readable"],
            AssetRole.FACE_REFERENCE.value: ["lighting polish", "pose-compatible styling"],
            AssetRole.NONHUMAN_IDENTITY_REFERENCE.value: ["habitat change", "action change", "camera change", "lighting change", "color and finish change"],
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
            AssetRole.NONHUMAN_IDENTITY_REFERENCE.value: ["individual morphology drift", "marking or pattern drift", "body proportion drift", "reference scene overinheritance"],
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
            "professional_anchor_lineage_evidence": bool(
                analysis.get("professional_anchor_lineage_evidence")
            ),
            "professional_anchor_lineage_role": analysis.get(
                "professional_anchor_lineage_role"
            ),
        }

    def _placement_for_role(self, role: str) -> str:
        if role == AssetRole.PRODUCT_REFERENCE.value:
            return "main product identity source"
        if role == AssetRole.LOGO_REFERENCE.value:
            return "brand mark exactness source"
        if role == AssetRole.BACKGROUND_REFERENCE.value:
            return "background environment source"
        if role == AssetRole.NONHUMAN_IDENTITY_REFERENCE.value:
            return "individual non-human subject identity source"
        if role == AssetRole.COMPOSITION_REFERENCE.value:
            return "layout and camera guide"
        if role == AssetRole.NEGATIVE_REFERENCE.value:
            return "avoidance reference"
        return "soft reference"

    @staticmethod
    def _is_strict_body_mcp(capability_input: CapabilityInput) -> bool:
        metadata = capability_input.metadata if isinstance(capability_input.metadata, dict) else {}
        return not (
            str(metadata.get("generation_channel") or "").strip().lower() != "mcp"
            or str(metadata.get("professional_character_card_stage") or "").strip() != "body_silhouette"
            or not str(metadata.get("professional_character_card_slot") or "").strip().startswith("body.")
            or not (
                metadata.get("professional_character_card_body_refresh_contract_required") is True
                or str(
                    metadata.get("professional_character_card_body_refresh_source_mode") or ""
                ).strip()
                in {"inference_first", "reference_assisted"}
            )
        )

    @classmethod
    def _body_mcp_partition(cls, capability_input: CapabilityInput) -> McpBodyReferencePartition | None:
        metadata = capability_input.metadata if isinstance(capability_input.metadata, dict) else {}
        if not cls._is_strict_body_mcp(capability_input):
            return None
        source_mode = str(
            metadata.get("professional_character_card_body_refresh_source_mode") or ""
        ).strip()
        raw = metadata.get("body_mcp_reference_partition")
        if source_mode == "inference_first":
            if raw is not None:
                raise ValueError("body_reference_partition_forbidden_for_inference")
            return None
        if source_mode != "reference_assisted":
            raise ValueError("body_refresh_source_mode_invalid")
        if raw is not None:
            if not isinstance(raw, dict):
                raise ValueError("body_mcp_reference_partition_invalid")
            return McpBodyReferencePartition.model_validate(raw)
        source_assets = metadata.get("professional_anchor_reference_assets")
        if not isinstance(source_assets, list):
            source_assets = metadata.get("reference_assets")
        if not isinstance(source_assets, list):
            raise ValueError("body_mcp_reference_partition_missing")
        return build_mcp_body_reference_partition(source_assets)

    def _conflict_warnings(
        self,
        bindings: list[dict[str, Any]],
        *,
        body_mcp_partition: McpBodyReferencePartition | None = None,
        professional_product_truth_pool: set[str] | None = None,
    ) -> list[CapabilityWarning]:
        warnings: list[CapabilityWarning] = []
        hard_roles = {AssetRole.PRODUCT_REFERENCE.value, AssetRole.LOGO_REFERENCE.value, AssetRole.FACE_REFERENCE.value, AssetRole.NONHUMAN_IDENTITY_REFERENCE.value}
        for role in hard_roles:
            role_bindings = [binding for binding in bindings if binding["role"] == role]
            competing_bindings = [
                binding
                for binding in role_bindings
                if not (
                    role == AssetRole.PRODUCT_REFERENCE.value
                    and professional_product_truth_pool is not None
                    and binding["asset_id"] in professional_product_truth_pool
                ) and not (
                    role == AssetRole.FACE_REFERENCE.value
                    and body_mcp_partition is not None
                ) and not (
                    role == AssetRole.FACE_REFERENCE.value
                    and binding.get("professional_anchor_lineage_evidence") is True
                    and binding.get("professional_anchor_lineage_role") == "prior_view_winner"
                )
            ]
            if len(competing_bindings) > 1:
                warnings.append(
                    CapabilityWarning(
                        code="asset_binding_role_conflict",
                        message=f"Multiple uploaded assets compete for hard role '{role}'.",
                        metadata={"asset_ids": [binding["asset_id"] for binding in competing_bindings]},
                    )
                )
        return warnings

    @staticmethod
    def _professional_product_truth_pool(
        capability_input: CapabilityInput,
        bindings: list[dict[str, Any]],
    ) -> set[str] | None:
        metadata = capability_input.metadata if isinstance(capability_input.metadata, dict) else {}
        if (
            capability_input.scenario_id != "ecommerce"
            or metadata.get("professional_product_truth_required") is not True
        ):
            return None
        raw_pool = metadata.get("professional_ecommerce_product_truth_pool_asset_ids")
        pool = [
            str(item).strip()
            for item in raw_pool
            if str(item).strip()
        ] if isinstance(raw_pool, list) else []
        actual = [
            str(binding.get("asset_id") or "").strip()
            for binding in bindings
            if binding.get("role") == AssetRole.PRODUCT_REFERENCE.value
            and str(binding.get("asset_id") or "").strip()
        ]
        if not pool or len(pool) != len(set(pool)) or set(actual) != set(pool):
            return None
        return set(pool)
