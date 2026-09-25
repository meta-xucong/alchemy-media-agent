"""Mode-scoped logical sources and exact Provider/MCP physical inputs."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import hashlib
import pytest
from PIL import Image
from alchemy_creative_agent_3_0.app.reference_input_plan import ReferenceInputPlan, plan_from_metadata, digest, PLAN_KEY
from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider, McpMaterializationProvider
from alchemy_creative_agent_3_0.app.schemas import PromptCompilationResult, ConditionPlan, GenerationPlan


@pytest.fixture
def sources(tmp_path):
    result=[]
    for i in range(3):
        path=tmp_path/f"source_{i}.png"
        Image.new("RGB",(256,256),(40+i*40,110,180)).save(path)
        result.append({"asset_id":f"source_{i}","file_path":str(path),"role":"product_reference","mime_type":"image/png"})
    return result


def request_for(plan):
    return GenerationRequest(prompt_compilation=PromptCompilationResult(prompt_compilation_id="prompt",asset_id="asset",visual_prompt="Three current images only.",text_policy="none"),
        condition_plan=ConditionPlan(condition_plan_id="condition",asset_id="asset"),
        generation_plan=GenerationPlan(generation_plan_id="generation",asset_id="asset"),
        metadata={PLAN_KEY:plan.as_dict(),"job_id":"job_test","project_id":"project_test"})


def test_three_current_sources_are_three_originals_not_six(sources, monkeypatch):
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    provider=ProductionImageGenerationProvider.__new__(ProductionImageGenerationProvider)
    monkeypatch.setattr(provider,"_reference_technical_admission",lambda path:(True,"accepted"))
    monkeypatch.setattr(provider,"_reference_capacity_limit",lambda request,refs:3)
    monkeypatch.setattr(provider,"_reference_truth_package",lambda *a,**k:{})
    monkeypatch.setattr(provider,"_reference_truth_derivatives",lambda *a,**k:pytest.fail("Standard constructed crop"))
    request=request_for(plan)
    request.metadata["reference_assets"]=[{"asset_id":"old-history","file_path":"must-not-read"}]
    refs=provider._reference_assets(request)
    assets=provider._asset_plan(request,refs)
    provider._bind_reference_materialization_receipt(request,assets)
    physical=provider._materialized_provider_reference_assets(assets)
    assert len(physical)==3
    assert [r["file_path"] for r in physical]==[str(Path(s["file_path"]).resolve()) for s in sources]
    assert not any(r["provider_reference_derivative"] for r in physical)
    receipt=assets["reference_input_plan_receipt"]
    assert receipt["logical_mode_input_count"]==3
    assert receipt["physical_provider_reference_count"]==3
    assert receipt["derived_evidence_count"]==0
    assert receipt["plan_digest"]==plan.as_dict()["plan_digest"]


def test_provider_and_mcp_use_same_source_and_representation_contract(sources, monkeypatch):
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    outcomes=[]
    for cls in [ProductionImageGenerationProvider,McpMaterializationProvider]:
        provider=cls.__new__(cls)
        monkeypatch.setattr(provider,"_reference_technical_admission",lambda path:(True,"accepted"))
        monkeypatch.setattr(provider,"_reference_capacity_limit",lambda request,refs:5)
        monkeypatch.setattr(provider,"_reference_truth_package",lambda *a,**k:{})
        request=request_for(plan)
        assets=provider._asset_plan(request,provider._reference_assets(request))
        provider._bind_reference_materialization_receipt(request,assets)
        outcomes.append(assets)
    assert outcomes[0]==outcomes[1]


def test_over_capacity_rejected_without_trimming(sources, monkeypatch):
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    provider=ProductionImageGenerationProvider.__new__(ProductionImageGenerationProvider)
    monkeypatch.setattr(provider,"_reference_technical_admission",lambda path:(True,"accepted"))
    monkeypatch.setattr(provider,"_reference_capacity_limit",lambda request,refs:2)
    with pytest.raises(Exception,match="capacity"):
        provider._reference_assets(request_for(plan))


def test_plan_is_independent_of_mutable_caller_arrays_and_retry_context(sources):
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    frozen=plan.as_dict()
    sources.clear()
    view=plan.as_dict();view["direct_references"].clear()
    assert plan.as_dict()==frozen
    assert len(plan.references())==3
    assert ReferenceInputPlan.from_dict(frozen,job_id="job_test").as_dict()==frozen
    with pytest.raises(ValueError,match="binding_mismatch"):
        ReferenceInputPlan.from_dict(frozen,job_id="other_job")


@pytest.mark.parametrize("mode",["standard","professional","ecommerce"])
def test_mode_counts_and_boolean_axes_are_independent(sources,mode):
    kwargs={"professional_binding":{"state":"valid","bindings":[{"binding_id":"exact"}]}} if mode=="professional" else {"ecommerce_contract":{"admission":"fixture"}} if mode=="ecommerce" else {}
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode=mode,inputs=sources,**kwargs)
    facts=plan.facts()
    assert facts["has_explicit_continuity_anchor"] is False
    assert facts["has_direct_reference_inputs"] is (mode=="standard")
    assert facts["has_professional_binding"] is (mode=="professional")
    assert facts["has_ecommerce_product_truth"] is (mode=="ecommerce")
    if mode!="standard":
        assert facts["physical_provider_reference_count"] is None
        assert facts["physical_count_state"]=="pending_specialized_materialization"


def test_recomputed_digest_does_not_allow_cross_mode_fields(sources):
    raw=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources).as_dict()
    raw["professional_binding_set"]={"references":sources}
    raw["plan_digest"]=digest({k:v for k,v in raw.items() if k!="plan_digest"})
    with pytest.raises(ValueError,match="mode_leak"):
        ReferenceInputPlan.from_dict(raw)


def test_changed_or_missing_source_bytes_never_substitute_other_history(sources):
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources)
    Path(sources[0]["file_path"]).write_bytes(b"changed")
    with pytest.raises(ValueError,match="integrity_mismatch"):
        plan.references()
    Path(sources[0]["file_path"]).unlink()
    with pytest.raises(ValueError,match="unavailable"):
        plan.references()


def test_duplicate_bytes_are_one_physical_input_with_logical_count_retained(sources):
    copied=deepcopy(sources[0]);copied["asset_id"]="alias"
    plan=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=[sources[0],copied])
    assert plan.facts()["logical_mode_input_count"]==2
    assert plan.facts()["physical_provider_reference_count"]==1


@pytest.mark.parametrize("field,value",[("physical_provider_reference_count",6),("physical_provider_reference_count",True),
    ("logical_mode_input_count",0),("logical_continuity_reference_count",1),("anchor_version",False),("anchor_auto_enabled","true")])
def test_recomputed_digest_cannot_forge_counts_or_boolean_flags(sources,field,value):
    raw=ReferenceInputPlan.freeze(job_id="job_test",project_id="project_test",mode="standard",inputs=sources).as_dict()
    raw[field]=value;raw["plan_digest"]=digest({k:v for k,v in raw.items() if k!="plan_digest"})
    with pytest.raises(ValueError):ReferenceInputPlan.from_dict(raw)


def test_handoff_fingerprint_preserves_both_reference_plan_hashes():
    from alchemy_creative_agent_3_0.app.generation_router.mcp_materialization import McpMaterializationHandoffStore
    contract={"renderer":"codex_builtin_imagegen","reference_input_plan_digest":"a"*64,"reference_input_receipt_digest":"b"*64}
    safe=McpMaterializationHandoffStore._safe_rendering_contract(contract)
    assert safe["reference_input_plan_digest"]=="a"*64
    assert safe["reference_input_receipt_digest"]=="b"*64
    contract["reference_input_plan_digest"]="wrong"
    with pytest.raises(Exception):McpMaterializationHandoffStore._safe_rendering_contract(contract)
