"""M3 seam from explicit People Asset evidence to the shared frozen plan."""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict

from ..shared_capabilities.activation.contracts import (
    ActivationEvidence,
    CapabilityActivationPlan,
    VisualTaskProfile,
)
from ..schemas.models import V3BaseModel
from .contracts import ProfessionalModeBinding


class CanonicalProviderPromptReceipt(V3BaseModel):
    """Receipt for a complete Brain-signed prompt; prompt text is not stored here."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    prompt_hash: str
    signed_by: Literal["remote_v3_llm_brain", "local_adapter"]
    signature_valid: bool
    renderer_model: str = "gpt-image-2"

class ProfessionalModeRuntimeBridge:
    """Prepare typed planning evidence and validate the frozen handoff."""

    def bind_task_profile(
        self,
        profile: VisualTaskProfile,
        binding: ProfessionalModeBinding,
    ) -> VisualTaskProfile:
        if profile.project_id not in {None, binding.project_id}:
            raise ValueError("Professional Mode binding project does not match task profile")
        if profile.job_id != binding.job_id:
            raise ValueError("Professional Mode binding job does not match task profile")
        evidence = ActivationEvidence(
            evidence_id=f"professional_people_asset:{binding.people_asset_id}:{binding.pack_version_id}",
            evidence_type="professional_people_asset_binding",
            source="visual_asset_library",
            value=binding.to_brain_evidence(),
            confidence=1.0,
            metadata={"identity_only": True},
        )
        controls = dict(profile.explicit_user_controls)
        controls.update(
            {
                "professional_mode_selected": True,
                "professional_mode_binding": binding.to_brain_evidence(),
            }
        )
        existing = [item for item in profile.evidence if item.evidence_id != evidence.evidence_id]
        return profile.model_copy(update={"explicit_user_controls": controls, "evidence": [*existing, evidence]})

    @staticmethod
    def planning_metadata(binding: ProfessionalModeBinding, *, canonical_prompt_hash: str) -> dict[str, object]:
        if not canonical_prompt_hash.strip():
            raise ValueError("canonical prompt hash is required before plan freeze")
        return {
            "professional_mode": True,
            "professional_mode_binding": binding.to_brain_evidence(),
            "canonical_prompt_hash": canonical_prompt_hash,
            "creative_direction_owner": "remote_v3_llm_brain",
            "reference_channel_owner": "shared_v3_reference_policy",
        }

    def validate_frozen_plan(
        self,
        plan: CapabilityActivationPlan,
        binding: ProfessionalModeBinding,
        prompt_receipt: CanonicalProviderPromptReceipt,
    ) -> None:
        if plan.activation_mode != "enforced":
            raise ValueError("Professional Mode requires an enforced frozen capability plan")
        if plan.fallback_used:
            raise ValueError("Professional Mode cannot use a local or legacy activation fallback")
        if plan.job_id != binding.job_id or plan.project_id != binding.project_id:
            raise ValueError("Professional Mode frozen plan binding job/project mismatch")
        if not plan.is_active("portrait_identity"):
            raise ValueError("Professional Mode frozen plan must activate portrait_identity")
        if plan.metadata.get("professional_mode") is not True:
            raise ValueError("Professional Mode binding was not frozen before planning")
        if plan.metadata.get("professional_mode_binding") != binding.to_brain_evidence():
            raise ValueError("Professional Mode frozen plan binding does not match selected asset")
        expected_hash = str(plan.metadata.get("canonical_prompt_hash") or "")
        if not expected_hash or prompt_receipt.prompt_hash != expected_hash:
            raise ValueError("canonical prompt hash is missing or mismatched")
        if prompt_receipt.signed_by != "remote_v3_llm_brain" or not prompt_receipt.signature_valid:
            raise ValueError("canonical prompt must be signed by the Remote Brain")
        if plan.metadata.get("human_realism_required") is True and not plan.is_active("human_realism"):
            raise ValueError("Professional Mode Human Realism activation is missing")
