import asyncio,json,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from PIL import Image,ImageDraw
import httpx
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import OpenAIVisionInspectionProvider
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import GeneratedOutputResolution
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import VisionOutputInspector,_grounded_lighting_finding
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import OutputQualityReviewMerger
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from app.config import settings
from app.services import alchemy_lab_llm as lab
alias="claude-sonnet-5-5-alchemy-structured"
def v3(path):
    p=OpenAIVisionInspectionProvider(timeout_seconds=85)
    if p.model_chain[0]!=alias:
        raise RuntimeError("review_route_mismatch")
    u=urlsplit(p._base_url() or "")
    assert (u.scheme,u.hostname)==("https","aiself.vip")
    goal="A geometric studio product illustration of a gray cube on a gray table."
    facts={
        "match":"Cast shadow must extend to the right of the cube from the light at upper left.",
        "mismatch":"Cast shadow must extend to the left of the cube from the light at upper right.",
    }
    findings={}; signals=[]
    for label,direction in facts.items():
        start=time.monotonic()
        r=GeneratedOutputResolution(resolution_id=label,file_path=str(path),output_id=label,status="ready",mime_type="image/png")
        ctx={"user_input":goal,"template_id":"general_template","reviewed_output_direction":{"source":"persisted_output_record","output_id":label,"prompt":goal+" "+direction}}
        raw=p.inspect(r,metadata=ctx)
        report=VisionOutputInspector()._from_provider_payload(r,raw,mode="hybrid",provider_name="synthetic_wokey",metadata=ctx)
        s=OutputQualityReviewMerger()._candidate_signal(report)
        evidence=_grounded_lighting_finding(raw,ctx,label)
        row={"probe":"v3_light_"+label,"seconds":round(time.monotonic()-start,2),"model":raw.get("_vision_route_receipt",{}).get("selected_model"),
             "status":report.status,"action":s.recommended_action,"literal_evidence":bool(evidence),
             "issue":("lighting_mismatch" in (raw.get("issue_codes") or [])),
             "field_lengths":{k:len(v) for k,v in (raw.get("lighting_mismatch_evidence") or {}).items() if isinstance(v,str) and k in {"region","expected_excerpt","observed"}}}
        print(json.dumps(row),flush=True)
        findings[label]=row
        signals.append(s.model_dump(mode="json"))
    review={"inspections":[{"output_id":x,"asset_id":"asset_"+x} for x in facts],"real_review_signal_package":{"candidate_signals":signals}}
    result=SimpleNamespace(metadata={"post_generation_review_package":review,"visual_cluster":review},
        series_plan=SimpleNamespace(assets=[SimpleNamespace(asset_id="asset_match",priority=1),
                                            SimpleNamespace(asset_id="asset_mismatch",priority=2)]))
    targeted=V3ProductApiService()._brain_retry_review_observations(result,["asset_mismatch"])
    print(json.dumps({"probe":"v3_single_repair_handoff","targeted_observations":len(targeted),"all_output_2":bool(targeted) and all(t.startswith("Output 2:") for t in targeted)}),flush=True)
async def lab_fallback(path):
    start=time.monotonic()
    candidates=lab._planner_candidates(image_paths=True)
    assert any(item=={"provider":"anthropic","model":alias} for item in candidates)
    assert urlsplit(settings.llm_gateway_base_url or "").hostname=="aiself.vip"
    async def primary_unavailable(**_kwargs):
        raise httpx.ConnectError("synthetic primary failure")
    lab._ask_openai_json=primary_unavailable
    result,receipt=await lab.plan_lab_json(
        system_prompt='Read the actual center of the attached synthetic swatch. Return only one JSON object {"center_color":"blue|red|white"}.',
        user_payload={"task":"Name the visible center color exactly."},image_paths=[path],max_tokens=700,timeout_seconds=65)
    print(json.dumps({"probe":"lab_native_visual_fallback","seconds":round(time.monotonic()-start,2),
        "correct_color":str(result.get("center_color") or "").lower()=="blue",
        "route":receipt.get("selected_model"),"protocol":receipt.get("selected_provider"),"fallback":receipt.get("fallback_used")}),flush=True)
with tempfile.TemporaryDirectory() as d:
    cube=Path(d)/"cube.png"
    im=Image.new("RGB",(384,384),"#9da2a6")
    draw=ImageDraw.Draw(im)
    draw.rectangle((0,210,384,384),fill="#8b8e90")
    draw.polygon([(128,268),(185,273),(318,328),(217,321)],fill="#42464a")
    draw.polygon([(114,165),(175,130),(242,160),(178,193)],fill="#dedede")
    draw.polygon([(114,165),(178,193),(178,287),(114,255)],fill="#bababa")
    draw.polygon([(178,193),(242,160),(242,251),(178,287)],fill="#646464")
    im.save(cube)
    v3(cube)
    swatch=Path(d)/"swatch.png"
    im=Image.new("RGB",(224,224),"white")
    ImageDraw.Draw(im).rectangle((50,50,170,170),fill="#194ef8")
    im.save(swatch)
    asyncio.run(lab_fallback(swatch))
