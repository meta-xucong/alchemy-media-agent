"""History and brand-memory reference preparation."""

from __future__ import annotations

from .base import SharedCapabilityModule
from .contracts import CapabilityConstraint, CapabilityInput, CapabilityResult, CapabilityStatus, CapabilityTargetStage
from .utils import dedupe_text


class HistoryReferenceModule(SharedCapabilityModule):
    module_id = "history_reference"
    version = "v3_shared_capability_001"
    order = 100

    def execute(self, capability_input: CapabilityInput) -> CapabilityResult:
        brand = capability_input.brand_context or {}
        successful_asset_ids = list(brand.get("successful_asset_ids") or [])
        rejected_style_tags = dedupe_text(list(brand.get("rejected_style_tags") or []))
        visual_tone = dedupe_text(list(brand.get("visual_tone") or []))
        reference_assets = list(brand.get("reference_assets") or [])
        if not successful_asset_ids and not rejected_style_tags and not visual_tone and not reference_assets:
            return CapabilityResult(
                module_id=self.module_id,
                version=self.version,
                status=CapabilityStatus.SKIPPED,
                audit_trail=["no brand history context supplied"],
            )
        constraints: list[CapabilityConstraint] = []
        if visual_tone or reference_assets:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.CREATIVE_DIRECTION,
                    constraint_type="brand_history_style_continuity",
                    strength="soft",
                    value={"visual_tone": visual_tone, "reference_asset_count": len(reference_assets)},
                    source=self.module_id,
                )
            )
        if rejected_style_tags:
            constraints.append(
                CapabilityConstraint(
                    target_stage=CapabilityTargetStage.PROMPT_COMPILATION,
                    constraint_type="avoid_rejected_history_styles",
                    strength="medium",
                    value={"rejected_style_tags": rejected_style_tags},
                    source=self.module_id,
                )
            )
        return CapabilityResult(
            module_id=self.module_id,
            version=self.version,
            status=CapabilityStatus.SUCCESS,
            confidence=0.7,
            facts={
                "history_reference": {
                    "successful_asset_ids": successful_asset_ids,
                    "rejected_style_tags": rejected_style_tags,
                    "visual_tone": visual_tone,
                    "reference_asset_count": len(reference_assets),
                }
            },
            constraints=constraints,
            audit_trail=["prepared brand/history reference context"],
        )
