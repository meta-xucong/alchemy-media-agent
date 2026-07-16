from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities.activation.contracts import (
    ActivatedCapability,
    CapabilityActivationPlan,
    VisualTaskProfile,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import ProfessionalModeBinding
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import (
    CanonicalProviderPromptReceipt,
    ProfessionalModeRuntimeBridge,
)


def _binding() -> ProfessionalModeBinding:
    return ProfessionalModeBinding(
        job_id="job_1",
        project_id="project_1",
        people_asset_id="person_1",
        face_module_id="face_module_1",
        pack_version_id="pack_1",
        identity_view_ids=["front_1", "three_quarter_1", "profile_1"],
    )


def _profile() -> VisualTaskProfile:
    return VisualTaskProfile(
        profile_id="profile_1",
        project_id="project_1",
        job_id="job_1",
        template_id="general_template",
        scenario_id="general_creative",
        protected_user_intent="Create a portrait in a rainy city at night.",
    )


def _plan(*active_ids: str, metadata: dict | None = None) -> CapabilityActivationPlan:
    active = [
        ActivatedCapability(
            capability_id=capability_id,
            version="v1",
            activation_mode="required",
            confidence=1.0,
        )
        for capability_id in active_ids
    ]
    return CapabilityActivationPlan(
        plan_id="plan_1",
        fingerprint="fingerprint_1",
        project_id="project_1",
        job_id="job_1",
        task_profile_id="profile_1",
        template_id="general_template",
        scenario_id="general_creative",
        active_capabilities=active,
        dependency_order=list(active_ids),
        activation_mode="enforced",
        metadata=metadata or {},
    )


def test_professional_binding_enters_task_profile_as_typed_evidence_only() -> None:
    bridge = ProfessionalModeRuntimeBridge()
    profile = _profile()
    bound = bridge.bind_task_profile(profile, _binding())

    assert bound.protected_user_intent == profile.protected_user_intent
    controls = bound.explicit_user_controls
    assert controls["professional_mode_selected"] is True
    assert controls["professional_mode_binding"]["people_asset_id"] == "person_1"
    assert all("prompt" not in str(value).lower() for value in controls.values())
    assert any(item.evidence_type == "professional_people_asset_binding" for item in bound.evidence)


def test_professional_planning_metadata_has_no_local_creative_fields() -> None:
    metadata = ProfessionalModeRuntimeBridge().planning_metadata(
        _binding(), canonical_prompt_hash="sha256:canonical_1"
    )

    assert metadata["professional_mode"] is True
    assert metadata["canonical_prompt_hash"] == "sha256:canonical_1"
    assert "prompt_additions" not in metadata
    assert "negative_prompt" not in metadata
    assert metadata["creative_direction_owner"] == "remote_v3_llm_brain"


def test_frozen_plan_requires_portrait_identity_and_matching_binding() -> None:
    bridge = ProfessionalModeRuntimeBridge()
    binding = _binding()
    metadata = bridge.planning_metadata(binding, canonical_prompt_hash="sha256:canonical_1")
    receipt = CanonicalProviderPromptReceipt(
        prompt_hash="sha256:canonical_1",
        signed_by="remote_v3_llm_brain",
        signature_valid=True,
        renderer_model="gpt-image-2",
    )

    with pytest.raises(ValueError, match="portrait_identity"):
        bridge.validate_frozen_plan(_plan("human_realism", metadata=metadata), binding, receipt)
    with pytest.raises(ValueError, match="binding"):
        bridge.validate_frozen_plan(_plan("portrait_identity"), binding, receipt)


def test_provider_handoff_requires_brain_signed_matching_canonical_prompt() -> None:
    bridge = ProfessionalModeRuntimeBridge()
    binding = _binding()
    metadata = bridge.planning_metadata(binding, canonical_prompt_hash="sha256:canonical_1")
    plan = _plan("portrait_identity", metadata=metadata)

    with pytest.raises(ValueError, match="canonical prompt"):
        bridge.validate_frozen_plan(
            plan,
            binding,
            CanonicalProviderPromptReceipt(
                prompt_hash="sha256:other",
                signed_by="remote_v3_llm_brain",
                signature_valid=True,
                renderer_model="gpt-image-2",
            ),
        )
    with pytest.raises(ValueError, match="Brain"):
        bridge.validate_frozen_plan(
            plan,
            binding,
            CanonicalProviderPromptReceipt(
                prompt_hash="sha256:canonical_1",
                signed_by="local_adapter",
                signature_valid=True,
                renderer_model="gpt-image-2",
            ),
        )


def test_valid_frozen_plan_can_pass_to_shared_provider_handoff() -> None:
    bridge = ProfessionalModeRuntimeBridge()
    binding = _binding()
    metadata = bridge.planning_metadata(binding, canonical_prompt_hash="sha256:canonical_1")
    receipt = CanonicalProviderPromptReceipt(
        prompt_hash="sha256:canonical_1",
        signed_by="remote_v3_llm_brain",
        signature_valid=True,
        renderer_model="gpt-image-2",
    )

    assert bridge.validate_frozen_plan(_plan("portrait_identity", metadata=metadata), binding, receipt) is None
