"""Doc97 provider-capability routing for identity repair."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import IdentityRepairStrategyPlan, SubjectContinuityAssetPackage


IDENTITY_REPAIR_STRATEGY_MODULE_ID = "identity_repair_strategy_router"


class IdentityRepairStrategyRouter:
    capability_key = "identity_native_local_repair"

    def build(
        self,
        *,
        project_id: str | None,
        job_id: str | None,
        package: SubjectContinuityAssetPackage,
        metadata: dict[str, Any],
    ) -> IdentityRepairStrategyPlan:
        if not package.applies or package.subject_type != "character":
            return IdentityRepairStrategyPlan(
                plan_id=stable_id(IDENTITY_REPAIR_STRATEGY_MODULE_ID, project_id, job_id),
                project_id=project_id,
                job_id=job_id,
                subject_type=package.subject_type,
            )
        native_capability = _capability_enabled(metadata, self.capability_key)
        experimental_generic = bool(metadata.get("allow_generic_face_local_repair"))
        allow_local = native_capability or experimental_generic
        return IdentityRepairStrategyPlan(
            plan_id=stable_id(
                IDENTITY_REPAIR_STRATEGY_MODULE_ID,
                project_id,
                job_id,
                package.package_id,
                str(native_capability),
            ),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=package.subject_type,
            strategy="identity_native_local_repair" if allow_local else "regenerate_from_ranked_identity_pack",
            allow_face_local_repair=allow_local,
            identity_native_provider_required=not experimental_generic,
            provider_capability_key=self.capability_key,
            fallback_strategy="hold_best_reviewed_result",
            reason_codes=(
                ["identity_native_provider_available"]
                if native_capability
                else ["experimental_generic_repair_override"]
                if experimental_generic
                else ["generic_mask_edit_not_identity_native"]
            ),
            user_visible_summary=["系统会优先保留人物一致性更好的结果。"],
            metadata={
                "doc": "97",
                "identity_native_capability": native_capability,
                "experimental_generic_override": experimental_generic,
                "generic_mask_support_is_not_identity_native": True,
            },
        )


def _capability_enabled(metadata: dict[str, Any], key: str) -> bool:
    if bool(metadata.get(key)):
        return True
    for container_key in ("provider_capabilities", "image_edit_capabilities", "visual_provider_capabilities"):
        container = metadata.get(container_key)
        if isinstance(container, dict) and bool(container.get(key)):
            return True
    return False
