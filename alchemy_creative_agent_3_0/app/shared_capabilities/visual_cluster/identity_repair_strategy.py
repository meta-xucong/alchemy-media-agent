"""Doc100 whole-image GPT Image 2 rerender routing for identity repair."""

from __future__ import annotations

from typing import Any

from ...creative_core.rules import stable_id
from .contracts import IdentityRepairStrategyPlan, SubjectContinuityAssetPackage


IDENTITY_REPAIR_STRATEGY_MODULE_ID = "identity_repair_strategy_router"


class IdentityRepairStrategyRouter:
    capability_key = "gpt_image_2_rerender"

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
        return IdentityRepairStrategyPlan(
            plan_id=stable_id(
                IDENTITY_REPAIR_STRATEGY_MODULE_ID,
                project_id,
                job_id,
                package.package_id,
                "gpt_image_2_only",
            ),
            project_id=project_id,
            job_id=job_id,
            applies=True,
            subject_type=package.subject_type,
            strategy="regenerate_from_ranked_identity_pack",
            allow_face_local_repair=False,
            identity_native_provider_required=False,
            provider_capability_key=self.capability_key,
            fallback_strategy="hold_best_reviewed_result",
            reason_codes=["gpt_image_2_whole_image_rerender_only"],
            user_visible_summary=["系统会优先保留人物一致性更好的结果。"],
            metadata={
                "doc": "100",
                "sole_renderer": "gpt-image-2",
                "non_gpt_local_pixel_repair_forbidden": True,
                "stale_provider_capabilities_ignored": True,
            },
        )
