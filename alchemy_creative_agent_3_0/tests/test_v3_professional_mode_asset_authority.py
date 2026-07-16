from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.authority import (
    AssetChannelClaim,
    ReferenceAdmissionResolver,
    ReferenceChannelEvidence,
    ReferenceChannelPlan,
    ReferenceEvidencePacket,
    VisualAssetBindingSet,
)
from alchemy_creative_agent_3_0.app.visual_assets.contracts import ProfessionalModeBinding
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


def _plan(
    reference_id: str,
    channels: list[str],
    *,
    representation: str = "channel_isolated",
    evidence_prefix: str | None = None,
) -> ReferenceChannelPlan:
    prefix = evidence_prefix or reference_id
    return ReferenceChannelPlan(
        project_id="project_1",
        job_id="job_1",
        reference_id=reference_id,
        declared_channels=channels,
        channel_evidence=[
            ReferenceChannelEvidence(
                channel=channel,
                evidence_ids=[f"evidence_{prefix}_{channel}"],
                representation=representation,
            )
            for channel in channels
        ],
    )


def test_people_binding_adapts_to_generic_claim_and_preserves_face_authority() -> None:
    binding_set = VisualAssetBindingSet.from_professional_binding(_binding())

    claim = binding_set.claims[0]
    assert claim.asset_type == "people"
    assert claim.asset_id == "person_1"
    assert {"face_geometry", "face_feature_relationships", "same_person_continuity"} <= set(
        claim.owned_channels
    )
    assert claim.evidence_ids == ["front_1", "three_quarter_1", "profile_1"]


def test_active_asset_claims_cannot_overlap_on_owned_channels() -> None:
    with pytest.raises(ValueError, match="overlap"):
        VisualAssetBindingSet(
            project_id="project_1",
            job_id="job_1",
            claims=[
                AssetChannelClaim(
                    project_id="project_1",
                    asset_type="people",
                    asset_id="person_1",
                    asset_version_id="pack_1",
                    owned_channels=["face_geometry"],
                    evidence_ids=["face_1"],
                ),
                AssetChannelClaim(
                    project_id="project_1",
                    asset_type="product",
                    asset_id="product_1",
                    asset_version_id="product_v1",
                    owned_channels=["face_identity"],
                    evidence_ids=["product_1"],
                ),
            ],
        )


def test_asset_claims_are_project_scoped() -> None:
    with pytest.raises(ValueError, match="job project"):
        VisualAssetBindingSet(
            project_id="project_1",
            job_id="job_1",
            claims=[
                AssetChannelClaim(
                    project_id="project_other",
                    asset_type="people",
                    asset_id="person_1",
                    asset_version_id="pack_1",
                    owned_channels=["face_geometry"],
                    evidence_ids=["face_1"],
                )
            ],
        )


def test_other_person_identity_is_suppressed_while_safe_style_channels_remain() -> None:
    result = ReferenceAdmissionResolver().resolve(
        VisualAssetBindingSet.from_professional_binding(_binding()),
        [_plan("person_photo", ["face_identity", "lighting", "pose"])],
    )

    assert result.status == "admitted"
    decision = result.decisions[0]
    assert decision.status == "partial"
    assert decision.suppressed_channels == ["face_identity"]
    assert decision.admitted_channels == ["lighting", "pose"]
    assert all("face_identity" not in item for item in decision.admitted_evidence_ids)


def test_identity_only_competing_reference_is_blocked() -> None:
    result = ReferenceAdmissionResolver().resolve(
        VisualAssetBindingSet.from_professional_binding(_binding()),
        [_plan("other_person", ["face_identity"])],
    )

    assert result.status == "blocked"
    assert result.decisions[0].status == "blocked"
    assert "reference_owned_channel_conflict" in result.decisions[0].reason_codes


def test_unsafe_full_frame_non_identity_reference_is_not_silently_admitted() -> None:
    result = ReferenceAdmissionResolver().resolve(
        VisualAssetBindingSet.from_professional_binding(_binding()),
        [_plan("mixed_person_and_cup", ["lighting"], representation="full_frame")],
    )

    assert result.status == "blocked"
    assert "unsafe_full_frame_reference" in result.decisions[0].reason_codes
    assert "channel_isolation_unproven" in result.decisions[0].reason_codes


def test_verified_non_person_object_and_logo_references_are_admitted() -> None:
    result = ReferenceAdmissionResolver().resolve(
        VisualAssetBindingSet.from_professional_binding(_binding()),
        [
            _plan("cup", ["object"], representation="verified_non_person_derivative"),
            _plan("logo", ["logo"], representation="channel_isolated"),
        ],
    )

    assert result.status == "admitted"
    assert [decision.status for decision in result.decisions] == ["admitted", "admitted"]


def test_one_blocked_reference_blocks_the_entire_professional_batch() -> None:
    result = ReferenceAdmissionResolver().resolve(
        VisualAssetBindingSet.from_professional_binding(_binding()),
        [
            _plan("cup", ["object"], representation="verified_non_person_derivative"),
            _plan("other_person", ["face_identity"]),
        ],
    )

    assert result.status == "blocked"
    assert [decision.status for decision in result.decisions] == ["admitted", "blocked"]


def test_reference_plan_requires_one_typed_evidence_item_per_declared_channel() -> None:
    with pytest.raises(ValidationError, match="every declared reference channel"):
        ReferenceChannelPlan(
            project_id="project_1",
            job_id="job_1",
            reference_id="mixed_1",
            declared_channels=["lighting", "pose"],
            channel_evidence=[
                ReferenceChannelEvidence(
                    channel="lighting",
                    evidence_ids=["lighting_1"],
                    representation="channel_isolated",
                )
            ],
        )


def test_reference_ids_must_not_repeat() -> None:
    with pytest.raises(ValueError, match="unique reference IDs"):
        ReferenceAdmissionResolver().resolve(
            VisualAssetBindingSet.from_professional_binding(_binding()),
            [_plan("same", ["object"]), _plan("same", ["logo"])],
        )


def test_reference_plan_cannot_cross_project_or_job_boundary() -> None:
    plan = _plan("cup", ["object"])
    plan = plan.model_copy(update={"project_id": "project_other"})

    with pytest.raises(ValueError, match="project/job"):
        ReferenceAdmissionResolver().resolve(
            VisualAssetBindingSet.from_professional_binding(_binding()),
            [plan],
        )


def test_alias_face_identity_is_protected_by_current_face_channels() -> None:
    result = ReferenceAdmissionResolver().resolve(
        VisualAssetBindingSet.from_professional_binding(_binding()),
        [_plan("other_person", ["same_face_identity"])],
    )

    assert result.status == "blocked"
    assert result.decisions[0].suppressed_channels == ["same_face_identity"]


def test_runtime_bridge_rejects_blocked_admission_and_records_admitted_provenance() -> None:
    bridge = ProfessionalModeRuntimeBridge()
    binding = _binding()
    admitted = bridge.resolve_reference_admissions(binding, [_plan("cup", ["object"])])
    metadata = bridge.planning_metadata(
        binding,
        canonical_prompt_hash="sha256:canonical_1",
        reference_admissions=admitted,
    )

    assert metadata["reference_admission_status"] == "admitted"
    assert metadata["reference_admission_contract_version"] == "visual_asset_reference_admission_v1"
    assert metadata["reference_evidence_packet_contract_version"] == "visual_asset_reference_evidence_packet_v1"
    assert metadata["asset_channel_authority_contract_version"] == "visual_asset_authority_v1"
    assert metadata["asset_channel_claims"][0]["asset_id"] == "person_1"
    assert "path" not in str(metadata).lower()
    assert "prompt_additions" not in str(metadata).lower()
    assert "negative_prompt" not in str(metadata).lower()

    blocked = bridge.resolve_reference_admissions(binding, [_plan("other_person", ["face_identity"])])
    with pytest.raises(ValueError, match="reference admission"):
        bridge.planning_metadata(
            binding,
            canonical_prompt_hash="sha256:canonical_1",
            reference_admissions=blocked,
        )


def test_provider_and_reviewer_receive_the_same_admitted_evidence_packet() -> None:
    bridge = ProfessionalModeRuntimeBridge()
    admitted = bridge.resolve_reference_admissions(_binding(), [_plan("cup", ["object"])])
    packet = admitted.to_evidence_packet()

    bridge.validate_reference_evidence_parity(packet)
    assert packet.evidence_ids == packet.provider_evidence_ids == packet.reviewer_evidence_ids

    with pytest.raises(ValidationError, match="identical admitted evidence IDs"):
        ReferenceEvidencePacket(
            evidence_ids=["cup_1"],
            provider_evidence_ids=["cup_1"],
            reviewer_evidence_ids=["different_1"],
        )
