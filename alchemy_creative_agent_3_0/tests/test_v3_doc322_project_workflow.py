"""Source/anchor authority through native Project and Product service calls."""
from copy import deepcopy
import base64
from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import _general_project
from alchemy_creative_agent_3_0.tests.doc322_test_support import certify_output
from alchemy_creative_agent_3_0.app.reference_input_plan import PLAN_KEY, ReferenceInputPlan
from alchemy_creative_agent_3_0.app.creative_core import CentralCreativeBrain
from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
from alchemy_creative_agent_3_0.app.schemas import ProviderStrategy
from alchemy_creative_agent_3_0.tests.test_v3_doc73_first_output_identity_anchor import RecordingImageProvider


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


@pytest.mark.parametrize("count,index,retry,mock",[(1,0,0,False),(2,1,0,False),(2,0,1,False),(2,0,0,True)])
def test_first_accepted_output_can_claim_but_mock_cannot(tmp_path,count,index,retry,mock):
    handlers,project,_,_=_general_project(tmp_path)
    job,output=create_source(handlers,project,count=count,index=index,retry=retry,mock=mock)
    before=handlers.project_service.get_continuity_anchor(project["project_id"])
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"],job.job_id)
    after=handlers.project_service.get_continuity_anchor(project["project_id"])
    if mock:
        assert after==before
    else:
        assert after["active_continuity_anchor"]["output_id"]==output.output_id
        created=handlers.post_project_job(project["project_id"],{"user_input":"Another view of the same character."})
        plan=handlers.service.get_job_record(created["job_id"]).request.metadata[PLAN_KEY]
        assert plan["continuity_anchor"]["output_id"]==output.output_id


def test_stylized_character_candidate_binds_first_accepted_output_and_reuses_it(tmp_path):
    handlers, project, _, _ = _general_project(tmp_path)
    created = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Create one adult stylized character portrait.", "metadata": {"requested_image_count": 1}},
    )
    job = handlers.service.get_job_record(created["job_id"])
    image_provider = RecordingImageProvider(tmp_path / "brain-output")
    brain = CentralCreativeBrain(generation_router=GenerationRouter(provider=image_provider))
    brain_result = brain.run_generation_loop(
        "Create one adult stylized character portrait.",
        provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
        runtime_metadata={
            "requested_image_count": 1,
            "requested_image_size": "1024x1024",
            "project_id": project["project_id"],
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "variation_mode": "creative_exploration",
            "effective_variation_mode": "creative_exploration",
            PLAN_KEY: ReferenceInputPlan.freeze(
                job_id=job.job_id,
                project_id=project["project_id"],
                mode="standard",
                inputs=[],
            ).as_dict(),
            "llm_brain": {
                "visual_task_profile": {
                    "subject_entities": [{"entity_type": "stylized_character"}],
                }
            },
        },
    )
    assert brain_result.metadata["doc322_auto_anchor_candidate"] is True
    generated_asset = brain_result.asset_pack.assets[0]
    output = handlers.service.output_store.save_base64_output(
        job_id=job.job_id,
        candidate_id=brain_result.metadata["selected_candidate_ids"][0],
        asset_id=job.planning_result.series_plan.assets[0].asset_id,
        provider="recording_image_provider",
        model="doc73-test",
        encoded_image=base64.b64encode(Path(generated_asset.file_path).read_bytes()).decode("ascii"),
        metadata={"project_id": project["project_id"]},
    )
    certified_job = certify_output(handlers.service, output)
    certified_job.generation_result.metadata["doc322_auto_anchor_candidate"] = brain_result.metadata[
        "doc322_auto_anchor_candidate"
    ]
    handlers.service.job_store.save(certified_job)
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"], job.job_id)

    anchor = handlers.project_service.get_continuity_anchor(project["project_id"])["active_continuity_anchor"]
    assert anchor["output_id"] == output.output_id
    next_job = handlers.post_project_job(
        project["project_id"],
        {"user_input": "Create another view of the same character.", "metadata": {"requested_image_count": 1}},
    )
    next_plan = handlers.service.get_job_record(next_job["job_id"]).request.metadata[PLAN_KEY]
    assert next_plan["continuity_anchor"]["output_id"] == output.output_id


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
    assert [item["asset_id"] for item in newplan["direct_references"]] == ids


@pytest.mark.parametrize("case,expected", [
    ("both_pass_reversed", 0), ("first_failed", 1), ("all_failed", None),
    ("selected_retry", 2), ("ambiguous_selected", None),
])
def test_auto_anchor_uses_reviewed_winner_in_planned_order(tmp_path, case, expected):
    handlers,project,_,_=_general_project(tmp_path)
    job,first=create_source(handlers,project)
    assets=[deepcopy(job.generation_result.asset_pack.assets[0])]
    rows=deepcopy(job.generation_result.metadata["post_generation_review_package"]["inspections"])
    outputs=[first]
    for index in (1, 0):
        out=handlers.service.output_store.save_base64_output(
            job_id=job.job_id,candidate_id=f"candidate_extra_{len(outputs)}",
            asset_id=job.planning_result.series_plan.assets[index].asset_id,
            provider="controlled_pixel_fixture",model="test",
            encoded_image=base64.b64encode(Path(first.file_path).read_bytes()).decode(),
            metadata={"project_id":project["project_id"]})
        outputs.append(out)
        certified=certify_output(handlers.service,out)
        assets.append(deepcopy(certified.generation_result.asset_pack.assets[0]))
        rows.extend(deepcopy(certified.generation_result.metadata["post_generation_review_package"]["inspections"]))
    assets[2].metadata["candidate_metadata"]["retry_attempt"]=1
    # Retain original and retry pixels, but expose only the canonical selected review.
    selected_rows=rows[:2]
    if case=="selected_retry":
        selected_rows=[rows[2], rows[1]]
    elif case=="ambiguous_selected":
        selected_rows=rows
    elif case in {"first_failed", "all_failed"}:
        rows[0]["status"]="fail_final"
        if case=="all_failed":
            rows[1]["status"]="fail_final"
    job.generation_result.asset_pack.assets=list(reversed(assets))
    job.generation_result.metadata["doc322_auto_anchor_candidate"]=True
    job.generation_result.metadata["post_generation_review_package"]={
        "review_evidence_receipt_status":"complete","inspections":selected_rows,
        "recommended_output_ids":[r["output_id"] for r in selected_rows if r["status"]=="pass"]}
    handlers.service.job_store.save(job)
    assert handlers.service.get_job_record(job.job_id).generation_result.metadata["doc322_auto_anchor_candidate"] is True
    handlers.project_service._maybe_claim_continuity_anchor(project["project_id"],job.job_id)
    anchor=handlers.project_service.get_continuity_anchor(project["project_id"])["active_continuity_anchor"]
    if expected is None:
        assert anchor is None
    else:
        assert anchor["output_id"]==outputs[expected].output_id
    assert len(handlers.service.output_store.list_by_job(job.job_id))==3


@pytest.mark.parametrize("outcome", ["pass", "pending", "finalizer_error"])
def test_resumed_review_finalizes_anchor_only_after_saved_completion(tmp_path, monkeypatch, outcome):
    from alchemy_creative_agent_3_0.app.product_api.contracts import GenerateJobRequest, ProductJobStatusValue
    handlers,project,_,_=_general_project(tmp_path)
    job,output=create_source(handlers,project,count=1)
    service=handlers.service
    job.generation_result.metadata["post_generation_review_recheck_required"]=True
    job.status=ProductJobStatusValue.BLOCKED
    if outcome=="pending":
        job.generation_result.metadata["post_generation_review_package"]={"inspections":[]}
    service.job_store.save(job)
    # Stub only external review and unrelated auxiliary projections; execute real resume.
    monkeypatch.setattr(service,"_attach_post_generation_review",lambda record,result,request: result)
    monkeypatch.setattr(service,"_apply_text_pixel_delivery",lambda record,result: result)
    monkeypatch.setattr(service,"_persist_output_store_job_closure",lambda *args: True)
    monkeypatch.setattr(service,"_post_generation_review_package_requires_resume",lambda package: outcome=="pending")
    seen=[]
    original=service._continuity_anchor_finalizer
    def finalize(project_id,job_id):
        saved=service.get_job_record(job_id)
        assert saved.status==ProductJobStatusValue.GENERATED
        assert saved.generation_result.metadata.get("post_generation_review_recheck_required") is None
        seen.append(job_id)
        if outcome=="finalizer_error":
            raise OSError("fixture unavailable")
        original(project_id,job_id)
    monkeypatch.setattr(service,"_continuity_anchor_finalizer",finalize)
    status=service._resume_finalizing_generation_review(job,GenerateJobRequest(),review_only=True)
    anchor=handlers.project_service.get_continuity_anchor(project["project_id"])["active_continuity_anchor"]
    if outcome=="pending":
        assert not seen and anchor is None
        assert status.status==ProductJobStatusValue.BLOCKED
    else:
        assert seen==[job.job_id]
        assert status.status==ProductJobStatusValue.GENERATED
        if outcome=="pass":
            assert anchor["output_id"]==output.output_id
        else:
            assert anchor is None
            assert any("Continuity anchor was not updated" in w for w in service.get_job_record(job.job_id).warnings)


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
