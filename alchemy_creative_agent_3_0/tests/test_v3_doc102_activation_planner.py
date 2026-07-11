import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities import SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ActivationEvidence,
    CapabilityActivationIntent,
    CapabilityActivationPlanner,
    RequestedCapability,
    VisualCapabilityRegistry,
    VisualSubjectEntity,
    VisualTaskProfile,
    general_capability_policy,
)


def _planner():
    execution = SharedCapabilityRegistry.with_default_modules()
    return CapabilityActivationPlanner(VisualCapabilityRegistry.with_default_manifests(execution))


def _profile():
    return VisualTaskProfile(
        profile_id="profile",
        job_id="job",
        template_id="general_template",
        scenario_id="general_creative",
        subject_entities=[VisualSubjectEntity(entity_id="person", entity_type="person", confidence=0.9)],
        evidence=[ActivationEvidence(evidence_id="person_evidence", evidence_type="visible_person", source="test")],
        confidence=0.9,
    )


def _plan(requested):
    return _planner().plan(
        task_profile=_profile(),
        intent=CapabilityActivationIntent(
            intent_id="intent",
            task_profile_id="profile",
            requested_capabilities=requested,
            confidence=0.9,
        ),
        template_policy=general_capability_policy(),
        catalog_version="catalog",
        activation_mode="enforced",
    )


def test_required_universal_capabilities_are_always_present() -> None:
    plan = _plan([])
    assert {"visual_grammar", "universal_visual_quality", "commercial_quality"} <= set(plan.dependency_order)
    assert "human_realism" not in plan.dependency_order


def test_evidence_backed_human_capability_activates() -> None:
    plan = _plan([
        RequestedCapability(
            capability_id="human_realism",
            reason_codes=["visible_person"],
            evidence_ids=["person_evidence"],
            confidence=0.9,
        )
    ])
    assert "human_realism" in plan.dependency_order


def test_unknown_capability_is_audited_but_not_executed() -> None:
    plan = _plan([RequestedCapability(capability_id="unknown_plugin", confidence=1.0)])
    assert "unknown_plugin" not in plan.dependency_order
    assert any(item.capability_id == "unknown_plugin" for item in plan.inactive_capabilities)


def test_low_confidence_optional_capability_is_not_activated() -> None:
    plan = _plan([RequestedCapability(capability_id="scene_continuity", confidence=0.1)])
    assert "scene_continuity" not in plan.dependency_order


def test_plan_fingerprint_and_order_are_stable() -> None:
    request = [RequestedCapability(capability_id="human_realism", evidence_ids=["person_evidence"], confidence=0.9)]
    first = _plan(request)
    second = _plan(request)
    assert first.fingerprint == second.fingerprint
    assert first.dependency_order == second.dependency_order


def test_requested_product_reference_profile_overrides_concept_default() -> None:
    plan = _plan([
        RequestedCapability(capability_id="product_identity", requested_profile="reference_truth", confidence=0.95)
    ])
    assert plan.active("product_identity").selected_profile == "reference_truth"
