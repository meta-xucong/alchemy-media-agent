import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities import SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ActivationEvidence,
    CapabilityActivationError,
    CapabilityActivationIntent,
    CapabilityActivationPlanner,
    RequestedCapability,
    RenderingIntent,
    VisualCapabilityRegistry,
    VisualSubjectEntity,
    VisualTaskProfile,
    build_task_profile_and_intent,
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


def test_visible_real_person_is_a_shared_activation_invariant_even_when_brain_omits_it() -> None:
    plan = _plan([])
    assert {"visual_grammar", "universal_visual_quality", "commercial_quality"} <= set(plan.dependency_order)
    human = plan.active("human_realism")
    assert human is not None
    assert human.activation_mode == "required"
    assert human.reason_codes == ["visible_real_person_execution_invariant"]
    assert human.evidence_ids == ["person_evidence"]


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


def test_explicitly_stylized_person_does_not_force_photorealism() -> None:
    profile = _profile().model_copy(
        update={
            "rendering_intent": RenderingIntent(
                rendering_mode="stylized",
                stylization_scope="whole_image",
                decision_owner="remote_brain",
            )
        }
    )
    plan = _planner().plan(
        task_profile=profile,
        intent=CapabilityActivationIntent(intent_id="intent", task_profile_id="profile", confidence=0.9),
        template_policy=general_capability_policy(),
        catalog_version="catalog",
        activation_mode="enforced",
    )
    assert "human_realism" not in plan.dependency_order


def test_visible_real_person_fails_closed_if_a_template_forbids_shared_realism() -> None:
    policy = general_capability_policy().model_copy(update={"forbidden_capabilities": ["human_realism"]})
    with pytest.raises(CapabilityActivationError, match="required shared capability is forbidden"):
        _planner().plan(
            task_profile=_profile(),
            intent=CapabilityActivationIntent(intent_id="intent", task_profile_id="profile", confidence=0.9),
            template_policy=policy,
            catalog_version="catalog",
            activation_mode="enforced",
        )


def test_explicit_young_person_direction_is_shared_visible_person_evidence() -> None:
    profile, intent = build_task_profile_and_intent(
        user_input=(
            "Create one fully dressed school-age child wearing the supplied blue dress "
            "in an ordinary daytime garden."
        ),
        job_id="young-person",
        project_id=None,
        template_id="general_template",
        scenario_id="general_creative",
        uploaded_assets=[{"asset_id": "dress", "role": "product_reference"}],
        reference_assets=[],
        product_profile={},
        metadata={"requested_image_count": 1},
        template_policy=general_capability_policy(),
    )

    assert {"person", "product"} <= {entity.entity_type for entity in profile.subject_entities}
    assert any(item.evidence_type == "visible_person" for item in profile.evidence)

    plan = _planner().plan(
        task_profile=profile,
        intent=intent,
        template_policy=general_capability_policy(),
        catalog_version="catalog",
        activation_mode="enforced",
    )
    human = plan.active("human_realism")
    assert human is not None
    assert human.activation_mode == "required"
    assert human.reason_codes == ["visible_real_person_execution_invariant"]


def test_children_garment_flat_lay_does_not_infer_a_visible_person() -> None:
    profile, intent = build_task_profile_and_intent(
        user_input="Create a flat-lay catalog photo of a children's blue dress, no people.",
        job_id="children-garment-flat-lay",
        project_id=None,
        template_id="general_template",
        scenario_id="general_creative",
        uploaded_assets=[{"asset_id": "dress", "role": "product_reference"}],
        reference_assets=[],
        product_profile={},
        metadata={"requested_image_count": 1},
        template_policy=general_capability_policy(),
    )

    assert "person" not in {entity.entity_type for entity in profile.subject_entities}
    assert not any(item.evidence_type == "visible_person" for item in profile.evidence)
    plan = _planner().plan(
        task_profile=profile,
        intent=intent,
        template_policy=general_capability_policy(),
        catalog_version="catalog",
        activation_mode="enforced",
    )
    assert plan.active("human_realism") is None
