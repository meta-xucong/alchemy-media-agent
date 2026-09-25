"""Additional authority and physical-materialization regressions from re-audit."""
from copy import deepcopy
from pathlib import Path
import pytest
from alchemy_creative_agent_3_0.app.reference_input_plan import ReferenceInputPlan, digest
from alchemy_creative_agent_3_0.app.generation_router import ProductionImageGenerationProvider, McpMaterializationProvider
from alchemy_creative_agent_3_0.tests.test_v3_doc322_reference_plan import sources, request_for


@pytest.mark.parametrize("field,value", [("reference_channel","product_truth"), ("source_type","generated_output"), ("provider_input_required", "true")])
def test_recomputed_plan_cannot_change_standard_source_authority(sources, field, value):
    raw=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources).as_dict()
    raw["direct_references"][0][field]=value
    raw["plan_digest"]=digest({k:v for k,v in raw.items() if k!="plan_digest"})
    with pytest.raises(ValueError): ReferenceInputPlan.from_dict(raw)


@pytest.mark.parametrize("fault", ["repeat_source", "reverse_order"])
def test_same_count_does_not_certify_wrong_physical_sources(sources, monkeypatch, fault):
    frozen=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    request=request_for(frozen)
    provider=ProductionImageGenerationProvider.__new__(ProductionImageGenerationProvider)
    monkeypatch.setattr(provider,"_reference_technical_admission",lambda _: (True,"accepted"))
    monkeypatch.setattr(provider,"_reference_capacity_limit",lambda *a:5)
    monkeypatch.setattr(provider,"_reference_truth_package",lambda *a,**k:{})
    materialized=provider._asset_plan(request,provider._reference_assets(request))
    if fault=="repeat_source": materialized["assets"][1]=deepcopy(materialized["assets"][0])
    else: materialized["assets"].reverse()
    with pytest.raises(ValueError): provider._bind_reference_materialization_receipt(request,materialized)


def test_mcp_keeps_existing_ecommerce_physical_plan_owner(sources, monkeypatch):
    frozen=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="ecommerce",inputs=sources,
        ecommerce_contract={"admission":"fixture"})
    request=request_for(frozen)
    expected={"assets":[{"source_asset_id":"approved-only"}],"provider_input_plan":{"authority":"existing_doc269"}}
    mcp=McpMaterializationProvider.__new__(McpMaterializationProvider)
    monkeypatch.setattr(mcp,"_has_doc269_ecommerce_physical_plan",lambda _:True)
    monkeypatch.setattr(mcp,"_doc269_ecommerce_materialization_asset_plan",lambda _:expected)
    assert mcp._provider_materialization_asset_plan(request,{"assets":[]})==expected


def test_unfrozen_ecommerce_representation_cannot_duplicate_sources(sources,monkeypatch):
    frozen=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="ecommerce",inputs=sources,
        ecommerce_contract={"admission":"fixture"})
    provider=ProductionImageGenerationProvider.__new__(ProductionImageGenerationProvider)
    monkeypatch.setattr(provider,"_has_doc269_ecommerce_physical_plan",lambda _:False)
    with pytest.raises(Exception,match="plan"):
        provider._asset_plan(request_for(frozen),frozen.references())


def test_boolean_history_version_is_not_an_integer_sequence(tmp_path):
    from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore
    from alchemy_creative_agent_3_0.app.project_mode.continuity_anchor import ContinuityAnchorBindingService, NAMESPACE
    store=InMemoryProjectStore()
    service=ContinuityAnchorBindingService(store,lambda *args:{})
    service.finish_empty_migration("project_test")
    event=store._private_records["project_test"][NAMESPACE][0]
    event["version"]=True
    event["identity_digest"]=digest({k:v for k,v in event.items() if k!="identity_digest"})
    with pytest.raises(ValueError,match="history_invalid"):service.state("project_test")


def test_known_bad_history_state_is_not_silently_usable(tmp_path):
    from alchemy_creative_agent_3_0.app.project_mode.store import InMemoryProjectStore
    from alchemy_creative_agent_3_0.app.project_mode.continuity_anchor import ContinuityAnchorBindingService, NAMESPACE
    store=InMemoryProjectStore();service=ContinuityAnchorBindingService(store,lambda *args:{})
    service.finish_empty_migration("project_test")
    event=store._private_records["project_test"][NAMESPACE][0]
    event["state"]="active"
    event["identity_digest"]=digest({k:v for k,v in event.items() if k!="identity_digest"})
    with pytest.raises(ValueError,match="history_invalid"):service.state("project_test")


def test_new_ecommerce_binding_is_admitted_without_a_legacy_selected_array(tmp_path):
    from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project
    from alchemy_creative_agent_3_0.tests.test_v3_doc322_project_workflow import create_source
    handlers, project, _, _ = _general_project(tmp_path)
    job, output = create_source(handlers, project)
    state = handlers.project_service.get_continuity_anchor(project["project_id"])
    handlers.project_service.bind_continuity_anchor(project["project_id"], {
        "output_id":output.output_id,"expected_job_id":job.job_id,
        "expected_version":state["version"],"confirm_binding":True})
    stored = handlers.project_service.project_store.get_project(project["project_id"])
    assert not stored.selected_output_refs
    admitted = handlers.project_service._doc269_selected_continuation_admissions(stored)
    assert [item["output_id"] for item in admitted] == [output.output_id]
    assert admitted[0]["source_type"] == "generated_selected"


def test_invalid_legacy_unselect_payload_does_not_drop_current_anchor(tmp_path):
    from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project
    from alchemy_creative_agent_3_0.tests.test_v3_doc322_project_workflow import create_source
    handlers, project, _, _ = _general_project(tmp_path)
    job, output = create_source(handlers, project)
    state = handlers.project_service.get_continuity_anchor(project["project_id"])
    active = handlers.project_service.bind_continuity_anchor(project["project_id"], {
        "output_id":output.output_id,"expected_job_id":job.job_id,
        "expected_version":state["version"],"confirm_binding":True})
    with pytest.raises(ValueError):
        handlers.project_service.unselect_project_output(project["project_id"], output.output_id, {"plain_text": {"invalid": True}})
    assert handlers.project_service.get_continuity_anchor(project["project_id"]) == active


def test_explicit_brand_export_does_not_turn_saved_uploads_into_next_job_sources(tmp_path):
    from alchemy_creative_agent_3_0.tests.test_v3_project_mode import _project_handlers_with_brand_store, _ready_upload
    handlers, _ = _project_handlers_with_brand_store(tmp_path)
    asset_id=_ready_upload(handlers,tmp_path,role="style_reference",filename="brand-only.png")
    project=handlers.post_projects({"user_goal":"Brand reference"})["project"]
    handlers.post_project_reference(project["project_id"],{"source_type":"uploaded","asset_ref_id":asset_id})
    proposal=handlers.post_project_brand_memory_proposal(project["project_id"],{"mode":"create"})
    assert proposal["proposal"]["proposal_id"]
    job=handlers.post_project_job(project["project_id"],{"user_input":"New explicit task without references."})
    record=handlers.service.get_job_record(job["job_id"])
    assert record.request.metadata["reference_input_plan"]["direct_references"]==[]


def test_new_bind_can_reuse_previously_unselected_formal_output(tmp_path):
    from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project
    from alchemy_creative_agent_3_0.tests.test_v3_doc322_project_workflow import create_source
    handlers,project,_,_=_general_project(tmp_path)
    job,output=create_source(handlers,project)
    service=handlers.project_service
    state=service.get_continuity_anchor(project["project_id"])
    state=service.bind_continuity_anchor(project["project_id"],{"output_id":output.output_id,
      "expected_job_id":job.job_id,"expected_version":state["version"],"confirm_binding":True})
    service.unselect_project_output(project["project_id"],output.output_id,{})
    state=service.get_continuity_anchor(project["project_id"])
    service.bind_continuity_anchor(project["project_id"],{"output_id":output.output_id,
      "expected_job_id":job.job_id,"expected_version":state["version"],"confirm_binding":True})
    context=handlers.get_project_context(project["project_id"])
    assert [ref["output_id"] for ref in context["selected_output_assets"]]==[output.output_id]


def test_ecommerce_identity_stays_separate_from_product_truth(sources):
    inputs=[sources[0],{**sources[1],"role":"face_reference","source_type":"visual_asset_library"}]
    contract={"approved_product_asset_ids":[sources[0]["asset_id"]],
      "locked_identity_asset_ids":[sources[1]["asset_id"]],"locked_identity_binding":{"state":"valid"}}
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="ecommerce",inputs=inputs,ecommerce_contract=contract)
    raw=plan.as_dict()
    assert [item["asset_id"] for item in raw["ecommerce_product_truth"]["references"]]==[sources[0]["asset_id"]]
    assert [item["asset_id"] for item in raw["ecommerce_product_truth"]["identity_references"]]==[sources[1]["asset_id"]]
    assert plan.facts()["has_professional_binding"] is True
    assert plan.facts()["has_ecommerce_product_truth"] is True
    assert [item["reference_channel"] for item in plan.references()]==["product_truth","ecommerce_identity"]


def test_provider_rejects_conflicting_frozen_plan_copies(sources):
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    request=request_for(plan)
    different=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources[:1])
    request.generation_plan.metadata["reference_input_plan"]=different.as_dict()
    with pytest.raises(ValueError,match="conflict"):
        ProductionImageGenerationProvider._generation_request_metadata(request)
    request.generation_plan.metadata["reference_input_plan"]=plan.as_dict()
    assert ProductionImageGenerationProvider._generation_request_metadata(request)["reference_input_plan"]==plan.as_dict()
