import asyncio,json,os,tempfile,time
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlsplit
from PIL import Image,ImageDraw
from app.config import settings
from app.repositories.memory import utc_now
from app.schemas import CaseRetrievalPlan,CreateCreativeRunRequest,ImageJob,ImageOutput,ImagePromptPlan
from app.services.runtime_model_settings import apply_persisted_runtime_model_settings,refresh_runtime_gateway_credentials
from app.services import claude_orchestrator as cli,uploaded_assets
from app.services import visual_review_agent as vr
from app.services.output_review import review_image_job

apply_persisted_runtime_model_settings()
refresh_runtime_gateway_credentials()
u=urlsplit(settings.llm_gateway_base_url or "")
assert (u.scheme,u.hostname)==("https","aiself.vip")
alias="claude-sonnet-5-5-alchemy-structured"
brief="Design a calm editorial poster for a fictional pottery exhibition. Show CLAY WEEK and 12 MAY, with open space around both lines."
with tempfile.TemporaryDirectory() as d:
    workspace=Path(d)
    for field,value in {
        "data_dir":workspace, "claude_orchestrator_workspace_dir":workspace/"planning",
        "claude_orchestrator_cache_path":workspace/"cache.json","storage_dir":workspace,
        "claude_orchestrator_enabled":True,"claude_checkpoint_orchestrator_enabled":True,
        "output_review_agent_enabled":True,
    }.items():
        object.__setattr__(settings,field,value)
    assert cli._claude_code_source_selection().model == alias
    def plan():
        start=time.monotonic()
        result=cli.orchestrate_creative_request(request=CreateCreativeRunRequest(user_prompt=brief),
            fallback_mode="smart_enhance",fallback_retrieval_plan=CaseRetrievalPlan(query_text=brief),candidate_cases=[])
        print(json.dumps({"probe":"v2_full_checkpoint","seconds":round(time.monotonic()-start,2),
            "status":result.invocation_status,"provider":result.provider,
            "trace":[{k:row.get(k) for k in ("stage","status","model","duration_ms","failure_code")} for row in (result.claude_stage_trace or [])]}),flush=True)
    async def review():
        start=time.monotonic()
        ref=workspace/"reference.png"; out=workspace/"result.png"
        for path,color in ((ref,"#174184"),(out,"#a12932")):
            image=Image.new("RGB",(512,512),"#fff7ea")
            draw=ImageDraw.Draw(image)
            draw.rounded_rectangle((110,100,400,390),radius=50,fill=color)
            draw.ellipse((210,180,300,270),fill="#f4f4f4")
            image.save(path)
        uploaded_assets.get_uploaded_asset=lambda asset_id: SimpleNamespace(veyra_user_id=99831) if asset_id=="synthetic_asset" else None
        uploaded_assets.uploaded_asset_path=lambda asset_id: ref if asset_id=="synthetic_asset" else None
        goal="Show the attached blue ceramic object as the only object. Preserve the source's blue body color; the backdrop can change."
        now=utc_now()
        output=ImageOutput(output_id="synthetic_out",job_id="synthetic_v2",url="/synthetic-original",
            metadata={"live":True,"storage_path":str(out),"input_images":[{"asset_id":"synthetic_asset","role":"product","reference_mode":"preserve_product","prompt_instruction":"Preserve the blue object color."}]},created_at=now)
        job=ImageJob(job_id="synthetic_v2",run_id="synthetic_run",status="completed",provider_id="synthetic",
            model="synthetic",veyra_user_id=99831,prompt_plan=ImagePromptPlan(plan_id="synthetic_plan",mode="smart_enhance",prompt=goal,
            negative_prompt="watermark",user_variables={"user_prompt":goal,"provider_input_plan":{"requires_image_reference":True,"reference_image_count":1}}),
            outputs=[output],created_at=now,updated_at=now)
        reviewed=await vr.review_generated_job(review_image_job(job))
        item=reviewed.outputs[0]
        rep=item.review
        receipt=item.metadata.get("visual_review_route") or item.metadata.get("vision_review_route") or {}
        keys=[k for k in item.metadata if k.startswith(("visual_","vision_","review_"))]
        print(json.dumps({"probe":"v2_reference_review","seconds":round(time.monotonic()-start,2),
            "mode":rep.analysis_mode,"decision":getattr(rep,"decision",None),"image_preserved":item.url==output.url,
            "model":getattr(rep,"model",None),"receipt":{k:receipt.get(k) for k in ("selected_model","primary_model","fallback_used")},"metadata_keys":keys,
            "color_evidence":any(t in "".join(rep.revision_directives or []).lower() for t in ("blue","red","\u84dd","\u7ea2"))}),flush=True)
    plan()
    asyncio.run(review())
