"""Frozen human scope stays distinct from optional face/identity obligations."""
from types import SimpleNamespace
import pytest
from alchemy_creative_agent_3_0.app.shared_capabilities.contracts import CapabilityInput
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.module import VisualCapabilityClusterModule
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.human_realism import HumanRealismPlugin
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import active_review_contract
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.llm_brain.prompts import _compact_human_realism_execution_contract
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime


def scoped_guidance(entities):
    source = CapabilityInput(job_id="scope_job", scenario_id="general_creative", user_input="product photo", metadata={
        "visual_task_profile": {"subject_entities": entities},
        "capability_activation_plan": {"dependency_order": ["human_realism"]},
    })
    module = VisualCapabilityClusterModule.__new__(VisualCapabilityClusterModule)
    metadata = module._human_realism_plugin_metadata(capability_input=source, project_context={},
        template_policy={}, subject_type="product", variation_mode="selection_candidates")
    guidance = HumanPhotorealismLayer().build(project_id="scope_project", job_id="scope_job",
        scenario_id="general_creative", template_id="general_template", user_input="product photo",
        subject_type="product", variation_mode="selection_candidates", has_identity_reference=False, metadata=metadata)
    return guidance.model_dump(mode="json")


def entity(kind, **attrs):
    return {"entity_id": kind, "entity_type": kind, "visible_in_target": True, "attributes": attrs}

def review_metadata(guidance):
    context = SimpleNamespace(plan=SimpleNamespace(plan_id="scope_plan"),
        active=SimpleNamespace(capability_id="human_realism", version="1", selected_profile="default"),
        cluster={"human_photorealism_guidance": guidance})
    contribution = HumanRealismPlugin().contribute(context)
    review = {"capability_id": "human_realism", **contribution.review_contract}
    return {"visual_cluster": {"composed_visual_contribution": {
        "active_capability_ids": ["human_realism"], "review_contracts": [review]}}}


@pytest.mark.parametrize("detail", [entity("hands"), entity("person", face_visible=False, visible_body_parts=["hands"]), entity("arm")])
def test_hand_detail_does_not_expand_to_whole_person_or_require_face(detail, monkeypatch):
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    guidance = scoped_guidance([entity("product"), detail])
    assert guidance["applies"] is True
    assert guidance["semantic_contract"]["rendering_goal"] == "photographic_human_detail"
    assert guidance["semantic_contract"]["identity_age_fidelity"] == "not_applicable"
    metadata = review_metadata(guidance)
    assert active_review_contract(metadata)["human_naturalness_verdict_required"] is False
    service = V3ProductApiService.__new__(V3ProductApiService)
    assert service._doc276_face_integrity_review_required(metadata, {"primary_face_visibility_expected": True}) is False
    cluster = {"human_photorealism_guidance": guidance}
    assert _compact_human_realism_execution_contract({"visual_cluster": cluster})["human_subject_kind"] == "hand_or_skin_detail"
    assert ScenarioRuntime._human_realism_execution_contract({"capability_projection": cluster})["human_subject_kind"] == "hand_or_skin_detail"

def test_product_only_does_not_invent_a_visible_person():
    guidance = scoped_guidance([entity("product")])
    assert guidance["applies"] is False
    assert active_review_contract(review_metadata(guidance))["human_naturalness_verdict_required"] is False


def test_portrait_still_requires_face_certification(monkeypatch):
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    guidance = scoped_guidance([entity("person", face_visible=True)])
    assert guidance["semantic_contract"]["rendering_goal"] == "photographic_real_person"
    metadata = review_metadata(guidance)
    service = V3ProductApiService.__new__(V3ProductApiService)
    assert service._doc276_face_integrity_review_required(metadata, {"primary_face_visibility_expected": True}) is True


def test_explicit_frozen_no_face_survives_whole_person_review(monkeypatch):
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    guidance = scoped_guidance([entity("person", face_visible=False)])
    metadata = review_metadata(guidance)
    service = V3ProductApiService.__new__(V3ProductApiService)
    assert service._doc276_face_integrity_review_required(metadata, {"primary_face_visibility_expected": True}) is False

@pytest.mark.parametrize("subjects,face_required", [
    ([entity("product")], False),
    ([entity("product"), entity("hands", face_visible=False, material="white_gloves")], False),
    ([entity("person", face_visible=True)], True),
])
def test_pixel_inspector_requires_face_receipt_only_in_applicable_scope(tmp_path, monkeypatch, subjects, face_required):
    from alchemy_creative_agent_3_0.tests import test_v3_doc276_face_integrity_delivery_certification as t
    monkeypatch.setenv("V3_DOC276_FACE_INTEGRITY_DELIVERY_ENABLED", "true")
    resolution = t._resolution(tmp_path)
    metadata = {**review_metadata(scoped_guidance(subjects)),
        **t._server_review_evidence_metadata(resolution, identity_required=False),
        "enable_real_vision_inspection": True,
        "frozen_output_review_contract": {"primary_face_visibility_expected": True}}
    service = V3ProductApiService.__new__(V3ProductApiService)
    required = service._doc276_face_integrity_review_required(metadata, metadata["frozen_output_review_contract"])
    assert required is face_required
    metadata["doc276_face_integrity_review_required"] = required
    if required:
        metadata["doc276_expected_face_binding"] = t._server_review_binding(resolution, metadata=metadata)
    provider = t._StaticVisionProvider(t._passing_human_payload())
    report = t.VisionOutputInspector(vision_provider=provider).inspect(resolution, metadata=metadata)
    assert report.status == ("manual_review" if face_required else "pass")
    assert ("face_integrity_unverified" in {issue["code"] for issue in report.detected_issues}) is face_required
    assert metadata["review_evidence_plan"]["channels"]["person_identity"]["applicability"] == "not_applicable"

@pytest.mark.parametrize("kind", ["product", "animal", "landscape"])
def test_nonhuman_scope_remains_neutral_across_different_scenes(kind):
    from alchemy_creative_agent_3_0.app.shared_capabilities.activation.human_scope import frozen_human_scope
    scope = frozen_human_scope({"subject_entities": [entity(kind)]})
    assert scope["known"] is True
    assert scope["human_present"] is False
    assert scope["face_visible"] is False


@pytest.mark.parametrize("entities", [[entity("unrecognized_subject")], ["malformed"], [entity("hands"), entity("unknown_actor")]])
def test_unknown_or_malformed_scope_cannot_self_exempt_a_required_face(entities):
    from alchemy_creative_agent_3_0.app.shared_capabilities.activation.human_scope import frozen_human_scope
    assert frozen_human_scope({"subject_entities": entities}) == {"known": False}
