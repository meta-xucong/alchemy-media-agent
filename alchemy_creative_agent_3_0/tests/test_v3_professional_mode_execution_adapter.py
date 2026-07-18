from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.authority import (
    ReferenceChannelEvidence,
    ReferenceChannelPlan,
)
from alchemy_creative_agent_3_0.app.visual_assets.consumers import ProfessionalConsumerRequest
from alchemy_creative_agent_3_0.app.visual_assets.contracts import ProfessionalModeBinding
from alchemy_creative_agent_3_0.app.visual_assets.execution import (
    ProfessionalModeExecutionAdapter,
    ProfessionalModeExecutionRequest,
)
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import ProfessionalModeRuntimeBridge


def _binding() -> ProfessionalModeBinding:
    return ProfessionalModeBinding(
        job_id="job_1",
        project_id="project_1",
        people_asset_id="person_1",
        face_module_id="face_module_1",
        pack_version_id="pack_1",
        identity_view_ids=["front_1", "three_quarter_1", "profile_1"],
    )


def _request(
    *,
    mode: str = "professional",
    plans: list[ReferenceChannelPlan] | None = None,
) -> ProfessionalModeExecutionRequest:
    binding = _binding() if mode == "professional" else None
    return ProfessionalModeExecutionRequest(
        consumer_request=ProfessionalConsumerRequest(
            template_id="general_template",
            mode=mode,
            binding=binding,
        ),
        canonical_prompt_hash="sha256:canonical_1",
        reference_plans=plans or [],
    )


def _plan(reference_id: str, channel: str, representation: str = "channel_isolated") -> ReferenceChannelPlan:
    return ReferenceChannelPlan(
        project_id="project_1",
        job_id="job_1",
        reference_id=reference_id,
        declared_channels=[channel],
        channel_evidence=[
            ReferenceChannelEvidence(
                channel=channel,
                evidence_ids=[f"evidence_{reference_id}_{channel}"],
                representation=representation,
            )
        ],
    )


def test_standard_mode_returns_no_professional_execution_context() -> None:
    assert ProfessionalModeExecutionAdapter().prepare(_request(mode="standard")) is None


def test_standard_mode_rejects_professional_reference_plans_before_execution() -> None:
    with pytest.raises(ValueError, match="Standard Mode"):
        _request(mode="standard", plans=[_plan("cup", "object")])


def test_professional_adapter_prepares_provider_reviewer_parity_context() -> None:
    result = ProfessionalModeExecutionAdapter().prepare(_request(plans=[_plan("cup", "object")]))

    assert result is not None
    assert result.status == "ready"
    assert result.context is not None
    assert result.context.template_id == "general_template"
    assert result.context.evidence_packet.evidence_ids == result.context.evidence_packet.provider_evidence_ids
    assert result.context.evidence_packet.evidence_ids == result.context.evidence_packet.reviewer_evidence_ids
    assert result.context.planning_metadata["reference_admission_status"] == "admitted"
    assert "path" not in str(result.context).lower()
    assert "prompt_additions" not in str(result.context).lower()


def test_professional_adapter_allows_no_uploaded_reference_with_empty_packet() -> None:
    result = ProfessionalModeExecutionAdapter().prepare(_request())

    assert result is not None
    assert result.status == "ready"
    assert result.context is not None
    assert result.context.evidence_packet.evidence_ids == []
    assert result.context.planning_metadata["admitted_evidence_ids"] == []


def test_professional_adapter_returns_structured_block_for_identity_conflict() -> None:
    result = ProfessionalModeExecutionAdapter().prepare(_request(plans=[_plan("other_person", "face_identity")]))

    assert result is not None
    assert result.status == "blocked"
    assert result.context is None
    assert result.reason_codes == ["owned_channel_suppressed", "reference_owned_channel_conflict"]
    assert result.blocked_decisions[0].reference_id == "other_person"


def test_professional_planning_metadata_exposes_typed_anchor_quality_contract() -> None:
    metadata = ProfessionalModeRuntimeBridge.planning_metadata(_binding())

    contract = metadata["professional_face_identity_quality_contract"]
    assert contract["contract_version"] == "professional_face_identity_quality_v2"
    assert contract["priority_order"][0] == "same_person_likeness"
    assert contract["anti_overperfection_boundary"] == "reject_generic_perfect_beauty_surface"
    assert contract["developmental_age_coherence"] == "whole_person_when_age_owned"
    assert "capture_presentation" not in contract
    assert contract["owner"] == "remote_v3_llm_brain"
    assert contract["review_owner"] == "v3_shared_vision"


def test_professional_adapter_blocks_unsafe_full_frame_instead_of_dropping_it() -> None:
    result = ProfessionalModeExecutionAdapter().prepare(
        _request(plans=[_plan("mixed_person_and_cup", "object", representation="full_frame")])
    )

    assert result is not None
    assert result.status == "blocked"
    assert "unsafe_full_frame_reference" in result.reason_codes


def test_execution_request_rejects_raw_prompt_or_provider_fields() -> None:
    with pytest.raises(ValidationError):
        ProfessionalModeExecutionRequest(
            consumer_request=ProfessionalConsumerRequest(
                template_id="general_template",
                mode="professional",
                binding=_binding(),
            ),
            canonical_prompt_hash="sha256:canonical_1",
            reference_plans=[],
            prompt="do not persist this",
        )
