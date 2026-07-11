import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ActivationEvidence,
    CapabilityActivationIntent,
    CapabilityPlanAmendment,
    RequestedCapability,
    VisualSubjectEntity,
    VisualTaskProfile,
)


def _profile(**updates):
    payload = {
        "profile_id": "profile_1",
        "job_id": "job_1",
        "template_id": "general_template",
        "scenario_id": "general_creative",
        "subject_entities": [
            VisualSubjectEntity(entity_id="entity_1", entity_type="future_custom_subject", confidence=0.8)
        ],
        "evidence": [
            ActivationEvidence(evidence_id="evidence_1", evidence_type="declared", source="test")
        ],
        "confidence": 0.8,
    }
    payload.update(updates)
    return VisualTaskProfile(**payload)


def test_task_profile_accepts_open_future_entity_types_and_serializes() -> None:
    profile = _profile()
    assert profile.subject_entities[0].entity_type == "future_custom_subject"
    assert VisualTaskProfile.model_validate_json(profile.model_dump_json()) == profile


def test_task_profile_rejects_duplicate_evidence_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate evidence_id"):
        _profile(
            evidence=[
                ActivationEvidence(evidence_id="same", evidence_type="a", source="test"),
                ActivationEvidence(evidence_id="same", evidence_type="b", source="test"),
            ]
        )


def test_activation_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ActivationEvidence(evidence_id="bad", evidence_type="x", source="test", confidence=1.2)


def test_intent_rejects_duplicate_capability_ids() -> None:
    with pytest.raises(ValidationError, match="duplicate requested capability_id"):
        CapabilityActivationIntent(
            intent_id="intent",
            task_profile_id="profile",
            requested_capabilities=[
                RequestedCapability(capability_id="human_realism"),
                RequestedCapability(capability_id="human_realism"),
            ],
        )


def test_plan_amendment_is_bounded_to_one() -> None:
    with pytest.raises(ValidationError):
        CapabilityPlanAmendment(
            amendment_id="amendment_2",
            original_plan_id="plan_1",
            amended_plan_id="plan_2",
            reason_code="new_entity",
            amendment_index=2,
        )
