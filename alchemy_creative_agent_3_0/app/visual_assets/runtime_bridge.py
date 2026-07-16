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
from .authority import (
    ReferenceAdmissionResolver,
    ReferenceAdmissionResult,
    ReferenceChannelPlan,
    ReferenceEvidencePacket,
    VisualAssetBindingSet,
)
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

    def resolve_reference_admissions(
        self,
        binding: ProfessionalModeBinding,
        plans: list[ReferenceChannelPlan],
    ) -> ReferenceAdmissionResult:
        """Validate Brain/shared-evidence reference plans before Provider use."""

        binding_set = VisualAssetBindingSet.from_professional_binding(binding)
        return ReferenceAdmissionResolver().resolve(binding_set, plans)

    @staticmethod
    def validate_reference_evidence_parity(packet: ReferenceEvidencePacket) -> None:
        """Require Provider and Reviewer to consume one identical evidence set."""

        if set(packet.provider_evidence_ids) != set(packet.reviewer_evidence_ids):
            raise ValueError("Provider and Reviewer evidence sets must be identical")

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
    def planning_metadata(
        binding: ProfessionalModeBinding,
        *,
        canonical_prompt_hash: str | None = None,
        canonical_prompt_hashes: list[str] | None = None,
        reference_admissions: ReferenceAdmissionResult | None = None,
    ) -> dict[str, object]:
        binding_set = VisualAssetBindingSet.from_professional_binding(binding)
        metadata: dict[str, object] = {
            "professional_mode": True,
            "professional_mode_binding": binding.to_brain_evidence(),
            "asset_channel_authority_contract_version": binding_set.contract_version,
            "asset_channel_claims": binding_set.to_provenance()["claims"],
            "creative_direction_owner": "remote_v3_llm_brain",
            "reference_channel_owner": "shared_v3_reference_policy",
        }
        if canonical_prompt_hash is not None:
            if not canonical_prompt_hash.strip():
                raise ValueError("canonical prompt hash must be non-empty when supplied")
            metadata["canonical_prompt_hash"] = canonical_prompt_hash
        if canonical_prompt_hashes:
            if any(not str(item).strip() for item in canonical_prompt_hashes):
                raise ValueError("canonical prompt hashes must be non-empty")
            metadata["canonical_prompt_hashes"] = list(dict.fromkeys(str(item) for item in canonical_prompt_hashes))
        if reference_admissions is None:
            metadata.update(
                {
                    "reference_admission_contract_version": "visual_asset_reference_admission_v1",
                    "reference_admission_status": "not_requested",
                    "reference_evidence_packet_contract_version": "visual_asset_reference_evidence_packet_v1",
                    "admitted_evidence_ids": [],
                }
            )
        else:
            if reference_admissions.status != "admitted":
                raise ValueError("Professional Mode reference admission is blocked")
            metadata.update(reference_admissions.to_provenance())
        return metadata

    def validate_frozen_plan(
        self,
        plan: CapabilityActivationPlan,
        binding: ProfessionalModeBinding,
        prompt_receipt: CanonicalProviderPromptReceipt | list[CanonicalProviderPromptReceipt],
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
        binding_set = VisualAssetBindingSet.from_professional_binding(binding)
        if plan.metadata.get("asset_channel_authority_contract_version") != binding_set.contract_version:
            raise ValueError("Professional Mode asset authority contract is missing or unsupported")
        if plan.metadata.get("asset_channel_claims") != binding_set.to_provenance()["claims"]:
            raise ValueError("Professional Mode asset channel claims do not match selected asset")
        if plan.metadata.get("reference_evidence_packet_contract_version") != (
            "visual_asset_reference_evidence_packet_v1"
        ):
            raise ValueError("Professional Mode reference evidence packet contract is missing or unsupported")
        admission_status = str(plan.metadata.get("reference_admission_status") or "not_requested")
        if admission_status == "blocked":
            raise ValueError("Professional Mode frozen plan contains blocked reference admission")
        if admission_status not in {"admitted", "not_requested"}:
            raise ValueError("Professional Mode reference admission is incomplete")
        expected_hashes = [
            str(item).strip()
            for item in plan.metadata.get("canonical_prompt_hashes", [])
            if str(item).strip()
        ]
        if not expected_hashes:
            singular_hash = str(plan.metadata.get("canonical_prompt_hash") or "").strip()
            if singular_hash:
                expected_hashes = [singular_hash]
        receipts = prompt_receipt if isinstance(prompt_receipt, list) else [prompt_receipt]
        actual_hashes = [item.prompt_hash for item in receipts]
        if not expected_hashes or actual_hashes != expected_hashes:
            raise ValueError("canonical prompt hash is missing or mismatched")
        if any(item.signed_by != "remote_v3_llm_brain" or not item.signature_valid for item in receipts):
            raise ValueError("canonical prompt must be signed by the Remote Brain")
        if plan.metadata.get("human_realism_required") is True and not plan.is_active("human_realism"):
            raise ValueError("Professional Mode Human Realism activation is missing")
