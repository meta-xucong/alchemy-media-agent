"""Source/anchor authority through native Project and Product service calls."""
from copy import deepcopy
import base64
from io import BytesIO
import pytest
from PIL import Image
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project
from alchemy_creative_agent_3_0.tests.doc322_test_support import certify_output
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY


def create_source(handlers, project, *, count=2, index=0, retry=0, mock=False):
    created=handlers.post_project_job(project["project_id"],{"user_input":"A photographic continuity set.","metadata":{"requested_image_count":count}})
    job=handlers.service.get_job_record(created["job_id"])
    image=Image.new("RGB",(256,256),(45+index*50,110,130))
    data=BytesIO();image.save(data,format="PNG")
    output=handlers.service.output_store.save_base64_output(job_id=job.job_id,candidate_id="candidate_"+job.job_id,
        asset_id=job.planning_result.series_plan.assets[index].asset_id,provider="controlled_pixel_fixture",model="test",
        encoded_image=base64.b64encode(data.getvalue()).decode(),metadata={"project_id":project["project_id"],"mock_contract_fixture":mock})
    record=certify_output(handlers.service,output)
    record.generation_result.metadata["doc322_auto_anchor_candidate"]=True
    record.generation_result.asset_pack.assets[0].metadata["candidate_metadata"]["retry_attempt"]=retry
    handlers.service.job_store.save(record)
    return record,output


def test_auto_first_formal_then_manual_unbind_survives_late_completion(tmp_path):
    handlers,project,ids,_=_general_project(tmp_path)
    first,output=create_source(handlers,project)
    delayed,late=create_source(handlers,project)
    before=handlers.project_service.get_continuity_anchor(project["project_id"])
    assert before["active_continuity_anchor"] is None
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"],first.job_id)
    active=handlers.project_service.get_continuity_anchor(project["project_id"])
    assert active["active_continuity_anchor"]["output_id"]==output.output_id
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"],first.job_id)
    assert handlers.project_service.get_continuity_anchor(project["project_id"])["version"]==active["version"]
    unbound=handlers.project_service.unbind_continuity_anchor(project["project_id"],{"expected_version":active["version"],"confirm_unbind":True})
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"],delayed.job_id)
    assert handlers.project_service.get_continuity_anchor(project["project_id"])==unbound
    assert unbound["auto_enabled"] is False


@pytest.mark.parametrize("index,retry,mock",[(1,0,False),(0,1,False),(0,0,True)])
def test_later_retry_and_mock_outputs_cannot_auto_claim(tmp_path,index,retry,mock):
    handlers,project,_,_=_general_project(tmp_path)
    job,output=create_source(handlers,project,index=index,retry=retry,mock=mock)
    before=handlers.project_service.get_continuity_anchor(project["project_id"])
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"],job.job_id)
    assert handlers.project_service.get_continuity_anchor(project["project_id"])==before


def test_three_uploads_plus_one_anchor_freeze_four_sources_and_retry_does_not_rebind(tmp_path):
    handlers,project,ids,_=_general_project(tmp_path)
    source,output=create_source(handlers,project)
    before=handlers.project_service.get_continuity_anchor(project["project_id"])
    active=handlers.project_service.bind_continuity_anchor(project["project_id"],{"output_id":output.output_id,
        "expected_job_id":source.job_id,"expected_version":before["version"],"confirm_binding":True})
    created=handlers.post_project_job(project["project_id"],{"user_input":"Use the same subject and these current three references.",
        "uploaded_asset_ids":ids,"metadata":{"requested_image_count":1}})
    job=handlers.service.get_job_record(created["job_id"])
    plan=deepcopy(job.request.metadata[PLAN_KEY])
    assert [item["asset_id"] for item in plan["direct_references"]]==ids
    assert plan["continuity_anchor"]["output_id"]==output.output_id
    assert plan["physical_provider_reference_count"]==4
    public=handlers.get_project(project["project_id"])
    assert len(public["project"]["metadata"]["current_job_reference_inputs"])==3
    assert public["project"]["metadata"]["continuity_anchor"]["active_continuity_anchor"]["output_id"]==output.output_id
    assert "project_source_library" not in public["metadata"]
    handlers.project_service.unbind_continuity_anchor(project["project_id"],{"expected_version":active["version"],"confirm_unbind":True})
    retry=handlers.service._runtime_request_payload(job.request)
    assert retry["metadata"][PLAN_KEY]==plan
    assert len(retry["uploaded_assets"])==3  # Anchor remains a different typed channel.
    assert len(retry["metadata"]["reference_assets"])==4
    next_job=handlers.post_project_job(project["project_id"],{"user_input":"A new shot without uploads.","metadata":{"requested_image_count":1}})
    newplan=handlers.service.get_job_record(next_job["job_id"]).request.metadata[PLAN_KEY]
    assert newplan["continuity_anchor"] is None
    assert newplan["direct_references"]==[]


def test_manual_replace_has_one_active_source_and_history_is_preserved(tmp_path):
    handlers,project,_,_=_general_project(tmp_path)
    first,a=create_source(handlers,project)
    second,b=create_source(handlers,project)
    state=handlers.project_service.get_continuity_anchor(project["project_id"])
    for job,out in [(first,a),(second,b)]:
        state=handlers.project_service.bind_continuity_anchor(project["project_id"],{"output_id":out.output_id,
            "expected_job_id":job.job_id,"expected_version":state["version"],"confirm_binding":True})
    assert state["active_continuity_anchor"]["output_id"]==b.output_id
    assert handlers.service.output_store.get_output(a.output_id) is not None
    public=handlers.get_project(project["project_id"])
    assert [r["output_id"] for r in public["project"]["selected_output_refs"]]==[b.output_id]


@pytest.mark.parametrize("field",["reference_input_plan","active_continuity_anchor","continuity_snapshot"])
def test_browser_cannot_construct_authoritative_reference_state(tmp_path,field):
    handlers,project,_,_=_general_project(tmp_path)
    with pytest.raises(ValueError,match="server_owned"):
        handlers.post_project_job(project["project_id"],{"user_input":"test","metadata":{field:{"pretend":True}}})


def test_first_reference_upload_is_not_an_anchor_fact(tmp_path):
    from types import SimpleNamespace
    from alchemy_creative_agent_3_0.app.creative_core.central_brain import CentralCreativeBrain
    handlers,project,ids,_=_general_project(tmp_path)
    created=handlers.post_project_job(project["project_id"],{"user_input":"Use these three original images.","uploaded_asset_ids":ids})
    record=handlers.service.get_job_record(created["job_id"])
    context=SimpleNamespace(metadata=record.request.metadata)
    assert CentralCreativeBrain.__new__(CentralCreativeBrain)._has_explicit_user_reference_assets(context) is False
    assert record.request.metadata["reference_input_summary"]["has_direct_reference_inputs"] is True
