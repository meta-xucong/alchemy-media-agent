"""Local immutable pixels plus explicit review receipts for workflow regressions."""
from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue


def certify_output(service, output):
    job=service.get_job_record(output.job_id)
    source=job.planning_result
    asset=source.asset_pack.assets[0].model_copy(update={
        "asset_id":output.asset_id,"file_path":output.file_path,"uri":output.download_url,
        "metadata":{"selected_candidate_id":output.candidate_id,"candidate_metadata":{"output_id":output.output_id}}})
    row={"output_id":output.output_id,"asset_id":output.asset_id,"candidate_id":output.candidate_id,
        "mode":"hybrid","verification_state":"verified","status":"pass",
        "evidence":{"provider_pixel_result_certified":True},"detected_issues":[]}
    package={"review_evidence_receipt_status":"complete","inspections":[row],"recommended_output_ids":[output.output_id]}
    job.generation_result=source.model_copy(update={"asset_pack":source.asset_pack.model_copy(update={"assets":[asset]}),
        "metadata":{**source.metadata,"post_generation_review_package":package}})
    job.status=ProductJobStatusValue.GENERATED
    service.job_store.save(job)
    return job


def install_offline_pixel_provider(service):
    """Explicit local image/reviewer doubles, never metadata-only mock acceptance."""
    import base64
    from io import BytesIO
    from PIL import Image
    from alchemy_creative_agent_3_0.app.generation_router import MockGenerationProvider, GenerationRouter
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import VisionOutputInspector
    class PixelProvider(MockGenerationProvider):
        def generate(self, request):
            response = super().generate(request)
            candidates=[]
            for index, candidate in enumerate(response.candidates):
                buffer=BytesIO();Image.new("RGB", (256,256), (100+index*10,120,140)).save(buffer,format="PNG")
                record=service.output_store.save_base64_output(
                    job_id=request.metadata["job_id"],candidate_id=candidate.candidate_id,asset_id=candidate.asset_id,
                    provider="offline_pixel_fixture",model="fixture",encoded_image=base64.b64encode(buffer.getvalue()).decode(),
                    metadata={"project_id":request.metadata.get("project_id"),"veyra_user_id":request.metadata.get("veyra_user_id")})
                candidates.append(candidate.model_copy(update={"is_mock":False,"uri":record.download_url,
                    "metadata":{**candidate.metadata,"output_id":record.output_id,"file_path":record.file_path,
                        "download_url":record.download_url,"preview_url":record.preview_url,"mime_type":record.mime_type}}))
            return response.model_copy(update={"candidates":candidates})
    class PixelReviewer:
        provider_name="offline_pixel_review_fixture"
        def available(self, *, force=False):return True
        def inspect(self, resolution, *, metadata=None):
            from alchemy_creative_agent_3_0.tests.test_v3_doc276_face_integrity_delivery_certification import (
                _passing_human_payload, _face_integrity_attestation, _reference_comparison_certification)
            payload=_passing_human_payload()
            binding=(metadata or {}).get("doc276_expected_face_binding")
            if isinstance(binding,dict):
                payload["face_integrity_attestation"]=_face_integrity_attestation("pass",binding=binding)
                payload["reference_comparison_certification"]=_reference_comparison_certification(binding=binding)
            return payload
    service.scenario_runtime.generation_router=GenerationRouter(provider=PixelProvider())
    service.vision_inspector=VisionOutputInspector(vision_provider=PixelReviewer())
