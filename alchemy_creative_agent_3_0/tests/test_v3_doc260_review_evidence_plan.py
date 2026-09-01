import base64
import hashlib
from io import BytesIO
import json
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.contracts import GenerateJobRequest
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.output_resolver import GeneratedOutputResolver
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.review_evidence import review_plan_digest
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    ReviewEvidenceChannel,
    ReviewEvidencePlan,
    VisionOutputInspector,
)


def _png_base64(width: int = 96, height: int = 72) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(110, 170, 210))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _LocalBrainProvider:
    provider = "doc260_review_evidence_test_brain"
    model = "contract-fixture-v1"

    def available(self, *, force: bool = False) -> bool:
        return True

    def run(self, request):  # noqa: ANN001
        return build_fallback_result(request).model_dump(mode="json")


class _StaticVisionProvider:
    provider_name = "doc260_static_vision"

    def __init__(self, payload: dict) -> None:
        self.payload = dict(payload)
        self.calls: list[GeneratedOutputResolution] = []
        self.metadata_calls: list[dict] = []

    def available(self, *, force: bool = False) -> bool:
        return True

    def inspect(self, resolution: GeneratedOutputResolution, *, metadata: dict | None = None) -> dict:
        self.calls.append(resolution)
        self.metadata_calls.append(dict(metadata or {}))
        return dict(self.payload)


class _StaticReadyResolver:
    def __init__(self, resolution: GeneratedOutputResolution | list[GeneratedOutputResolution]) -> None:
        self.resolutions = [resolution] if isinstance(resolution, GeneratedOutputResolution) else list(resolution)

    def resolve_result(self, result, project_id: str | None = None):  # noqa: ANN001
        packaged = result.asset_pack.assets[0]
        candidate_metadata = packaged.metadata.get("candidate_metadata", {})
        resolved = []
        for resolution in self.resolutions:
            resolved.append(
                resolution.model_copy(
                    update={
                        "project_id": project_id or resolution.project_id,
                        "job_id": result.creative_job.job_id,
                        "asset_id": packaged.asset_id,
                        "candidate_id": packaged.metadata.get("selected_candidate_id"),
                        "output_id": resolution.output_id or candidate_metadata.get("output_id"),
                    }
                )
            )
        return resolved


def _ready_resolution(tmp_path: Path, *, output_id: str = "output_doc260") -> GeneratedOutputResolution:
    image_path = tmp_path / f"{output_id}.png"
    content = base64.b64decode(_png_base64())
    image_path.write_bytes(content)
    return GeneratedOutputResolution(
        resolution_id=f"resolution_{output_id}",
        project_id="project_doc260",
        job_id="job_doc260",
        candidate_id="candidate_doc260",
        asset_id="asset_doc260",
        output_id=output_id,
        file_path=str(image_path),
        mime_type="image/png",
        width=96,
        height=72,
        status="ready",
        metadata={"content_sha256": hashlib.sha256(content).hexdigest()},
    )


def _service(tmp_path: Path, **overrides) -> V3ProductApiService:
    overrides.setdefault(
        "scenario_runtime",
        ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=_LocalBrainProvider())),
    )
    return V3ProductApiService(
        brand_profile_service=BrandProfileService(BrandProfileStore(tmp_path / "brand_memory")),
        **overrides,
    )


def _create_general_job(service: V3ProductApiService, *, uploaded_asset_ids: list[str] | None = None):
    return service.create_job(
        {
            "user_input": "Create one clean real-camera social image with natural lighting.",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "mode_id": "social_cover",
                "preset_id": "social_cover",
            },
            "uploaded_asset_ids": list(uploaded_asset_ids or []),
            "metadata": {"requested_image_count": 1},
        }
    )


def _ready_uploaded_reference(
    service: V3ProductApiService,
    *,
    filename: str,
    role: str = "product_reference",
) -> str:
    content = base64.b64decode(_png_base64())
    upload = service.create_uploaded_asset(
        {
            "filename": filename,
            "mime_type": "image/png",
            "size_bytes": len(content),
            "role": role,
        }
    )
    stored = service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": base64.b64encode(content).decode("ascii"), "mime_type": "image/png"},
    )
    assert stored is not None
    completed = service.complete_uploaded_asset(upload.asset_id)
    assert completed is not None
    return upload.asset_id


def _internal_generation_metadata(service: V3ProductApiService, job_id: str) -> dict:
    record = service.job_store.get(job_id)
    assert record is not None and record.generation_result is not None
    return record.generation_result.metadata


def _review_evidence_plan(metadata: dict) -> dict:
    package = metadata.get("post_generation_review_package")
    assert isinstance(package, dict)
    plans = package.get("review_evidence_plans")
    digests = package.get("review_evidence_plan_digests")
    assert isinstance(plans, dict), "Doc260 requires output-scoped typed ReviewEvidencePlan collection"
    assert isinstance(digests, dict), "Doc260 requires output-scoped review plan digests"
    assert len(plans) == len(digests) == 1
    output_id, plan = next(iter(plans.items()))
    assert isinstance(plan, dict), "Doc260 requires an internal typed ReviewEvidencePlan on the review package"
    assert output_id == plan.get("output_id")
    assert digests[output_id] == plan.get("review_plan_digest")
    return plan


def _channel(plan: dict, name: str) -> dict:
    channels = plan.get("channels")
    assert isinstance(channels, dict), "ReviewEvidencePlan must preserve per-channel applicability"
    channel = channels.get(name)
    assert isinstance(channel, dict), f"missing ReviewEvidencePlan channel {name}"
    return channel


def test_doc260_no_product_reference_still_enters_real_pixel_review_with_channel_not_provided(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0},
        },
    )

    assert generated.status == ProductJobStatusValue.GENERATED
    assert len(provider.calls) == 1, "absence of product reference must not disable real-pixel review"
    internal = _internal_generation_metadata(service, created.job_id)
    plan = _review_evidence_plan(internal)

    product = _channel(plan, "product_truth")
    assert product["evidence_state"] in {"not_provided", "not_applicable"}
    assert product["comparison_allowed"] is False
    assert _channel(plan, "selected_output")["evidence_state"] == "available"
    assert internal["post_generation_review_package"]["real_pixel_review"] is True


def test_doc260_no_references_still_reviews_generic_pixels_and_marks_all_optional_channels(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "warning", "confidence": 0.93, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0},
        },
    )

    assert len(provider.calls) == 1
    assert generated.metadata["final_delivery"]["final_delivery_status"] == "ready"
    internal = _internal_generation_metadata(service, created.job_id)
    plan = _review_evidence_plan(internal)

    assert _channel(plan, "product_truth")["evidence_state"] in {"not_provided", "not_applicable"}
    assert _channel(plan, "person_identity")["evidence_state"] in {"not_provided", "not_applicable"}
    assert _channel(plan, "prompt_semantics")["evidence_state"] == "available"
    assert generated.metadata["visual_auto_retry"]["manual_confirmation_required"] is False


def test_doc260_default_no_reference_route_uses_available_vision_provider(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"max_visual_retry_attempts": 0},
        },
    )

    assert len(provider.calls) == 1
    package = _internal_generation_metadata(service, created.job_id)["post_generation_review_package"]
    inspection = package["inspections"][0]
    assert inspection["mode"] == "hybrid"
    assert inspection["verification_state"] == "verified"
    assert package["real_pixel_review"] is True
    assert generated.metadata["final_delivery"]["final_delivery_status"] == "ready"
    plan = _review_evidence_plan(_internal_generation_metadata(service, created.job_id))
    assert _channel(plan, "product_truth")["evidence_state"] in {"not_provided", "not_applicable"}
    assert _channel(plan, "person_identity")["evidence_state"] in {"not_provided", "not_applicable"}


def test_doc260_public_review_projects_safe_no_reference_real_pixel_facts(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)
    service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"max_visual_retry_attempts": 0},
        },
    )

    public = service.get_job(created.job_id)
    review = public.metadata["post_generation_review"]

    assert review["real_pixel_review_attempted"] is True
    assert review["real_pixel_review_certified"] is True
    assert review["review_evidence_receipt_status"] == "complete"
    assert review["reference_comparison"]["product_truth"] in {"not_provided", "not_applicable"}
    assert review["reference_comparison"]["person_identity"] in {"not_provided", "not_applicable"}
    assert "review_evidence_plan_digest" not in review
    assert "review_evidence_plans" not in review
    assert "evidence_ids" not in review


def test_doc260_public_review_projects_required_unavailable_without_source_ids(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    source_id = "v3_asset_missing_public_projection"
    resolution = _ready_resolution(tmp_path).model_copy(
        update={
            "metadata": {
                "candidate_metadata": {
                    "reference_truth_source_ids": [source_id],
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                }
            }
        }
    )
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(resolution),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service, uploaded_asset_ids=[source_id])
    service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"max_visual_retry_attempts": 0},
        },
    )

    public = service.get_job(created.job_id)
    review = public.metadata["post_generation_review"]

    assert provider.calls == []
    assert review["real_pixel_review_attempted"] is False
    assert review["real_pixel_review_certified"] is False
    assert review["review_evidence_receipt_status"] == "complete"
    assert review["reference_comparison"]["product_truth"] == "unavailable"
    assert public.metadata["final_delivery"]["automatic_delivery_available"] is False
    assert source_id not in str(review)
    assert "review_evidence_plan_digest" not in review


def test_doc260_public_review_distinguishes_pixels_not_reviewed(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    public = service.get_job(created.job_id)
    review = public.metadata["post_generation_review"]

    assert review["real_pixel_review_attempted"] is False
    assert review["real_pixel_review_certified"] is False
    assert review["review_evidence_receipt_status"] == "not_available"
    assert review["reference_comparison"] == {
        "product_truth": "not_reviewed",
        "person_identity": "not_reviewed",
    }


def test_doc260_public_review_requires_all_ready_outputs_for_certified_pixels() -> None:
    review = V3ProductApiService._public_post_generation_review(  # noqa: SLF001
        {
            "review_evidence_receipt_status": "complete",
            "resolutions": [
                {"output_id": "output_doc260_a", "status": "ready"},
                {"output_id": "output_doc260_b", "status": "ready"},
            ],
            "inspections": [
                {
                    "output_id": "output_doc260_a",
                    "mode": "hybrid",
                    "status": "pass",
                    "verification_state": "verified",
                    "evidence": {"provider_pixel_result_certified": True},
                },
                {
                    "output_id": "output_doc260_b",
                    "mode": "hybrid",
                    "status": "manual_review",
                    "verification_state": "unverified",
                    "evidence": {},
                },
            ],
            "review_evidence_plans": {
                "output_doc260_a": {
                    "channels": {
                        "product_truth": {"evidence_state": "not_applicable"},
                        "person_identity": {"evidence_state": "not_applicable"},
                    }
                },
                "output_doc260_b": {
                    "channels": {
                        "product_truth": {"evidence_state": "not_applicable"},
                        "person_identity": {"evidence_state": "not_applicable"},
                    }
                },
            },
        }
    )

    assert review["real_pixel_review_attempted"] is True
    assert review["real_pixel_review_certified"] is False


def test_doc260_optional_missing_reference_does_not_trigger_retry_or_manual_hold(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 1},
        },
    )

    assert len(provider.calls) == 1
    assert generated.metadata["visual_auto_retry"]["executed_count"] == 0
    assert generated.metadata["visual_auto_retry"]["manual_confirmation_required"] is False
    assert generated.metadata["final_delivery"]["final_delivery_status"] == "ready"
    plan = _review_evidence_plan(_internal_generation_metadata(service, created.job_id))
    assert _channel(plan, "product_truth")["evidence_state"] in {"not_provided", "not_applicable"}
    assert _channel(plan, "person_identity")["evidence_state"] in {"not_provided", "not_applicable"}


def test_doc260_verified_retryable_visual_defect_still_uses_existing_bounded_retry(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider(
        {
            "status": "fail_retryable",
            "confidence": 0.91,
            "issue_codes": ["visible_text_artifact"],
            "human_naturalness_verdict": {"status": "pass", "issue_codes": []},
        }
    )
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 1},
        },
    )

    assert generated.metadata["visual_auto_retry"]["executed_count"] == 1
    assert len(provider.calls) >= 2
    internal = _internal_generation_metadata(service, created.job_id)
    assert internal["post_generation_review_package"]["final_review"]["status"] == "failed_after_retry"
    plan = _review_evidence_plan(internal)
    assert _channel(plan, "selected_output")["evidence_state"] == "available"


def test_doc260_missing_required_reference_is_channel_unavailable_and_non_certifying(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    plan = _valid_plan().model_dump(mode="json")
    plan["channels"]["person_identity"] = ReviewEvidenceChannel(
        applicability="required",
        evidence_state="unavailable",
        evidence_ids=("v3_asset_missing",),
        comparison_allowed=False,
        reason_codes=("review_evidence_person_identity_unavailable",),
    ).model_dump(mode="json")
    plan["review_plan_digest"] = review_plan_digest(plan)
    report = VisionOutputInspector(vision_provider=provider).inspect(
        _ready_resolution(tmp_path),
        metadata={"vision_inspection_mode": "hybrid", "review_evidence_plan": plan, "review_evidence_plan_authority": "exact_review_evidence_resolver"},
    )

    assert provider.calls == []
    assert report.status == "manual_review"
    assert report.verification_state == "unverified"
    assert [issue["code"] for issue in report.detected_issues] == [
        "review_evidence_person_identity_unavailable"
    ]
    assert report.evidence["review_evidence_channels"]["person_identity"]["evidence_state"] == "unavailable"

def test_doc260_generated_output_reference_resolves_through_output_store_channel(
    tmp_path,
) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    reference = output_store.save_base64_output(
        job_id="job_reference",
        candidate_id="candidate_reference",
        asset_id="asset_reference",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )
    resolver = GeneratedOutputResolver(output_store)
    resolution = resolver.resolve_asset(
        "job_doc260",
        asset=type(
            "Asset",
            (),
            {
                "metadata": {
                    "candidate_metadata": {
                        "output_id": reference.output_id,
                        "candidate_id": "candidate_reference",
                    }
                },
                "asset_id": "asset_reference",
            },
        )(),
        project_id="project_doc260",
    )
    service = _service(tmp_path, output_store=output_store)
    created = _create_general_job(service)
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.request = record.request.model_copy(
        update={
            "metadata": {
                **dict(record.request.metadata),
                "professional_anchor_reference_assets": [{"asset_id": reference.output_id}],
            }
        }
    )
    job_scoped_resolution = resolution.model_copy(
        update={
            "metadata": {
                "candidate_metadata": {
                    "reference_truth_source_ids": [reference.output_id],
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                }
            }
        }
    )

    metadata = service._admitted_review_reference_metadata(record, job_scoped_resolution)  # noqa: SLF001

    assert metadata["review_evidence_plan"]["channels"]["person_identity"]["evidence_state"] == "available"
    assert metadata["review_evidence_plan"]["channels"]["person_identity"]["evidence_ids"] == [
        reference.output_id
    ]
    assert metadata["review_evidence_plan"]["channels"]["person_identity"]["source_type"] == "selected_output"

    unknown_claim = dict(job_scoped_resolution.metadata["candidate_metadata"])
    unknown_claim["reference_truth_channel"] = "unknown_channel"
    unknown_channel_resolution = job_scoped_resolution.model_copy(
        update={"metadata": {"candidate_metadata": unknown_claim}}
    )
    invalid_metadata = service._admitted_review_reference_metadata(record, unknown_channel_resolution)  # noqa: SLF001
    assert invalid_metadata["review_evidence_plan"]["channels"]["person_identity"]["evidence_state"] == "invalid"
    assert "unknown_channel" not in invalid_metadata["review_evidence_plan"]["channels"]


def test_doc260_general_selected_output_reference_uses_server_source_job_binding(
    tmp_path,
) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    reference = output_store.save_base64_output(
        job_id="job_reference_general",
        candidate_id="candidate_reference_general",
        asset_id="asset_reference_general",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )
    service = _service(tmp_path, output_store=output_store)
    created = _create_general_job(service)
    record = service.job_store.get(created.job_id)
    assert record is not None
    source_integrity_id = f"sha256:{hashlib.sha256(Path(reference.file_path).read_bytes()).hexdigest()}"
    original_source_bytes = Path(reference.file_path).read_bytes()

    def apply_context(
        *,
        source_job_id: str,
        canonical: bool = True,
        server_owned: bool = True,
        frozen_integrity_id: str | None = source_integrity_id,
        nested_integrity_id: str | None = None,
    ) -> None:
        integrity_fields = (
            {"source_integrity_id": frozen_integrity_id}
            if frozen_integrity_id is not None
            else {}
        )
        nested_integrity_fields = (
            {"source_integrity_id": nested_integrity_id}
            if nested_integrity_id is not None
            else {}
        )
        context = {
            "project_id": "project_doc260_general_reference",
            "metadata": {"source": "V3ProjectModeService"},
            "selected_output_assets": [
                {
                    "source_type": "generated_output",
                    "project_id": "project_doc260_general_reference",
                    "job_id": source_job_id,
                    "asset_id": reference.asset_id,
                    "candidate_id": reference.candidate_id,
                    "output_id": reference.output_id,
                    **integrity_fields,
                    "metadata": {"canonical_output_binding": canonical, **nested_integrity_fields},
                }
            ],
            "selected_reference_assets": [
                {
                    "source_type": "generated_selected",
                    "project_id": "project_doc260_general_reference",
                    "asset_ref_id": reference.output_id,
                    "created_from_job_id": source_job_id,
                    "created_from_output_id": reference.output_id,
                    **integrity_fields,
                    "metadata": {"canonical_output_binding": canonical, **nested_integrity_fields},
                }
            ],
            "selected_visual_references": [
                {
                    "source_type": "selected_output",
                    "project_id": "project_doc260_general_reference",
                    "output_id": reference.output_id,
                    "source_job_id": source_job_id,
                    **integrity_fields,
                    "metadata": {"canonical_output_binding": canonical, **nested_integrity_fields},
                }
            ],
            "strong_reference_bindings": [
                {
                    "source_type": "selected_output",
                    "source_id": reference.output_id,
                    "output_id": reference.output_id,
                    "source_job_id": source_job_id,
                    **integrity_fields,
                    "metadata": {"canonical_output_binding": canonical, **nested_integrity_fields},
                }
            ],
        }
        if not server_owned:
            context.pop("metadata")
        record.request = record.request.model_copy(
            update={
                "metadata": {
                    **dict(record.request.metadata),
                    "project_id": "project_doc260_general_reference",
                    "project_context_snapshot": context,
                }
            }
        )

    resolution = GeneratedOutputResolver(output_store).resolve_asset(
        "job_doc260",
        asset=type(
            "Asset",
            (),
            {
                "metadata": {
                    "candidate_metadata": {
                        "reference_truth_source_ids": [reference.output_id],
                        "reference_input_execution": {
                            "admission_outcome": "admitted",
                            "operation_outcome": "pixels_received",
                            "reference_count": 1,
                        },
                    }
                },
                "asset_id": "asset_generated_doc260",
                "file_path": reference.file_path,
            },
        )(),
        project_id="project_doc260_general_reference",
    )
    resolution = resolution.model_copy(
        update={
            "job_id": created.job_id,
            "metadata": {
                **dict(resolution.metadata),
                "candidate_metadata": {
                    "reference_truth_source_ids": [reference.output_id],
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                },
            },
        }
    )

    apply_context(source_job_id=reference.job_id)
    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    person_channel = metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert person_channel["evidence_state"] == "available"
    assert person_channel["comparison_allowed"] is True
    assert person_channel["source_type"] == "selected_output"
    assert "review_evidence_person_identity_source_job_binding" not in person_channel["reason_codes"]
    assert reference.job_id not in str(metadata)

    output_record_path = output_store.storage_root / reference.output_id / "output.json"
    legacy_record = json.loads(output_record_path.read_text(encoding="utf-8"))
    legacy_record["metadata"].pop("content_sha256", None)
    output_record_path.write_text(json.dumps(legacy_record, ensure_ascii=False, indent=2), encoding="utf-8")
    legacy_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    legacy_channel = legacy_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert legacy_channel["evidence_state"] == "available"
    assert legacy_channel["comparison_allowed"] is True

    stale_record = json.loads(output_record_path.read_text(encoding="utf-8"))
    stale_record["metadata"]["content_sha256"] = "0" * 64
    output_record_path.write_text(json.dumps(stale_record, ensure_ascii=False, indent=2), encoding="utf-8")
    stale_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    stale_channel = stale_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert stale_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_selected_output_content_integrity" in stale_channel["reason_codes"]

    restored_record = json.loads(output_record_path.read_text(encoding="utf-8"))
    restored_record["metadata"]["content_sha256"] = hashlib.sha256(original_source_bytes).hexdigest()
    output_record_path.write_text(json.dumps(restored_record, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(reference.file_path).write_bytes(original_source_bytes + b"tampered")
    mutated_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    mutated_channel = mutated_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert mutated_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_selected_output_source_integrity_binding" in mutated_channel["reason_codes"]

    Path(reference.file_path).write_bytes(original_source_bytes)
    apply_context(source_job_id=reference.job_id, frozen_integrity_id=None)
    missing_binding_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    missing_binding_channel = missing_binding_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert missing_binding_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_output_source_integrity_binding" in missing_binding_channel["reason_codes"]

    apply_context(source_job_id="")
    missing_job_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    missing_job_channel = missing_job_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert missing_job_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_output_source_job_binding" in missing_job_channel["reason_codes"]

    apply_context(
        source_job_id=reference.job_id,
        nested_integrity_id="1" * 64,
    )
    conflicting_binding_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    conflicting_binding_channel = conflicting_binding_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert conflicting_binding_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_output_source_integrity_binding" in conflicting_binding_channel["reason_codes"]

    apply_context(source_job_id="job_forged_general_reference")
    forged_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    forged_channel = forged_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert forged_channel["evidence_state"] == "invalid"
    assert forged_channel["comparison_allowed"] is False
    assert "review_evidence_person_identity_output_source_job_binding" in forged_channel["reason_codes"]

    apply_context(source_job_id=reference.job_id, canonical=False)
    noncanonical_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    noncanonical_channel = noncanonical_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert noncanonical_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_source_job_binding" in noncanonical_channel["reason_codes"]


    apply_context(source_job_id=reference.job_id, server_owned=False)
    untrusted_metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    untrusted_channel = untrusted_metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert untrusted_channel["evidence_state"] == "invalid"
    assert "review_evidence_person_identity_source_job_binding" in untrusted_channel["reason_codes"]


def test_doc260_current_job_selected_output_reference_remains_invalid(tmp_path) -> None:
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = _service(tmp_path, output_store=output_store)
    created = _create_general_job(service)
    record = service.job_store.get(created.job_id)
    assert record is not None
    current_output = output_store.save_base64_output(
        job_id=created.job_id,
        candidate_id="candidate_current_job",
        asset_id="asset_current_job",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )
    record.request = record.request.model_copy(
        update={
            "metadata": {
                **dict(record.request.metadata),
                "project_id": "project_doc260_current_job",
                "project_context_snapshot": {
                    "project_id": "project_doc260_current_job",
                    "metadata": {"source": "V3ProjectModeService"},
                    "selected_output_assets": [
                        {
                            "source_type": "generated_output",
                            "project_id": "project_doc260_current_job",
                            "job_id": created.job_id,
                            "output_id": current_output.output_id,
                            "metadata": {"canonical_output_binding": True},
                        }
                    ],
                },
            }
        }
    )
    resolution = GeneratedOutputResolver(output_store).resolve_asset(
        created.job_id,
        asset=type(
            "Asset",
            (),
            {
                "metadata": {
                    "candidate_metadata": {
                        "reference_truth_source_ids": [current_output.output_id],
                        "reference_input_execution": {
                            "admission_outcome": "admitted",
                            "operation_outcome": "pixels_received",
                            "reference_count": 1,
                        },
                    }
                },
                "asset_id": current_output.asset_id,
                "file_path": current_output.file_path,
            },
        )(),
        project_id="project_doc260_current_job",
    )

    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    person_channel = metadata["review_evidence_plan"]["channels"]["person_identity"]
    assert person_channel["evidence_state"] == "invalid"
    assert person_channel["comparison_allowed"] is False
    assert "review_evidence_person_identity_reference_output_job_binding" in person_channel["reason_codes"]


def test_doc260_wrong_job_source_binding_is_invalid_and_does_not_fallback(
    tmp_path,
) -> None:
    asset_store = V3UploadedAssetStore(tmp_path / "uploads")
    service = _service(tmp_path, asset_store=asset_store)
    admitted_asset_id = _ready_uploaded_reference(service, filename="admitted.png")
    unrelated_asset_id = _ready_uploaded_reference(service, filename="unrelated.png")
    created = _create_general_job(service, uploaded_asset_ids=[admitted_asset_id])
    record = service.job_store.get(created.job_id)
    assert record is not None
    wrong_binding_resolution = _ready_resolution(tmp_path).model_copy(
        update={
            "metadata": {
                "candidate_metadata": {
                    "reference_truth_source_ids": [unrelated_asset_id],
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                }
            }
        }
    )

    metadata = service._admitted_review_reference_metadata(record, wrong_binding_resolution)  # noqa: SLF001

    assert metadata["review_evidence_plan"]["channels"]["product_truth"]["evidence_state"] == "invalid"
    assert metadata["review_evidence_plan"]["channels"]["product_truth"]["evidence_ids"] == [
        unrelated_asset_id
    ]
    assert "uploaded_assets" not in metadata


def test_doc260_legacy_ambiguous_reference_booleans_remain_non_certifying(
    tmp_path,
) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.97, "issue_codes": []})
    report = VisionOutputInspector(vision_provider=provider).inspect(
        _ready_resolution(tmp_path),
        metadata={
            "vision_inspection_mode": "vision_model",
            "review_reference_evidence_required": True,
            "review_reference_evidence_available": True,
        },
    )

    assert provider.calls == []
    assert report.status == "manual_review"
    assert report.verification_state == "unverified"
    assert [issue["code"] for issue in report.detected_issues] == ["legacy_reference_evidence_ambiguous"]
    assert report.evidence["certification_state"] == "unverified"


def test_doc260_public_metadata_cannot_forge_review_evidence_plan(tmp_path) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.97, "issue_codes": []})
    report = VisionOutputInspector(vision_provider=provider).inspect(
        _ready_resolution(tmp_path),
        metadata={
            "vision_inspection_mode": "vision_model",
            "public_review_evidence_plan": {
                "channels": {"product_truth": {"evidence_state": "available"}}
            },
        },
    )

    assert provider.calls == []
    assert report.status == "manual_review"
    assert [issue["code"] for issue in report.detected_issues] == [
        "public_review_evidence_plan_rejected"
    ]


def _valid_plan(output_id: str = "output_doc260", job_id: str = "job_doc260") -> ReviewEvidencePlan:
    channel = ReviewEvidenceChannel(
        applicability="required",
        evidence_state="available",
        evidence_ids=(output_id,),
        comparison_allowed=True,
        source_type="generated_output",
    )
    return ReviewEvidencePlan(
        plan_id="plan_doc260",
        job_id=job_id,
        output_id=output_id,
        review_mode="real_pixel",
        channels={
            "product_truth": channel,
            "person_identity": channel,
            "prompt_semantics": channel,
            "selected_output": channel,
        },
        source_binding_digest="binding_doc260",
        review_plan_digest="digest_doc260",
    )


def test_doc260_plan_and_channel_contracts_are_closed_and_frozen() -> None:
    with pytest.raises(Exception):
        ReviewEvidenceChannel(
            applicability="required",
            evidence_state="available",
            comparison_allowed=False,
            unexpected="forged",
        )
    with pytest.raises(Exception):
        ReviewEvidencePlan.model_validate({"plan_id": "plan_doc260"})
    plan = _valid_plan()
    with pytest.raises(Exception):
        plan.job_id = "other_job"


def test_doc260_non_admitted_audit_emits_typed_unavailable_plan(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service, uploaded_asset_ids=["v3_asset_missing"])
    record = service.job_store.get(created.job_id)
    assert record is not None
    resolution = _ready_resolution(tmp_path).model_copy(
        update={
            "metadata": {
                "candidate_metadata": {
                    "reference_truth_source_ids": ["v3_asset_missing"],
                    "reference_input_execution": {
                        "admission_outcome": "rejected",
                        "operation_outcome": "no_pixels",
                        "reference_count": 1,
                    },
                }
            }
        }
    )
    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    assert metadata["review_evidence_plan"]["channels"]["product_truth"]["evidence_state"] == "unavailable"
    assert metadata["review_evidence_plan"]["output_id"] == resolution.output_id


def test_doc260_cross_job_resolution_binding_is_invalid(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)
    record = service.job_store.get(created.job_id)
    assert record is not None
    resolution = _ready_resolution(tmp_path).model_copy(update={"job_id": "other_job"})
    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    plan = metadata["review_evidence_plan"]
    assert plan["channels"]["selected_output"]["evidence_state"] == "invalid"
    assert "resolution_job_binding" in plan["channels"]["selected_output"]["reason_codes"]


def test_doc260_uploaded_file_digest_drift_is_invalid(tmp_path) -> None:
    asset_store = V3UploadedAssetStore(tmp_path / "uploads")
    service = _service(tmp_path, asset_store=asset_store)
    asset_id = _ready_uploaded_reference(service, filename="drift.png")
    upload = asset_store.get_upload(asset_id)
    assert upload is not None and upload.file_path
    Path(upload.file_path).write_bytes(base64.b64decode(_png_base64(48, 48)))
    created = _create_general_job(service, uploaded_asset_ids=[asset_id])
    record = service.job_store.get(created.job_id)
    assert record is not None
    resolution = _ready_resolution(tmp_path).model_copy(
        update={
            "metadata": {
                "candidate_metadata": {
                    "reference_truth_source_ids": [asset_id],
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                }
            }
        }
    )
    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    assert metadata["review_evidence_plan"]["channels"]["product_truth"]["evidence_state"] == "invalid"


def test_doc260_ready_output_plans_are_scoped_by_output_id(tmp_path) -> None:
    first = _ready_resolution(tmp_path, output_id="output_doc260_a")
    second = _ready_resolution(tmp_path, output_id="output_doc260_b")
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(first),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)
    generated = service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0}},
    )
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    service.output_resolver = _StaticReadyResolver([first, second])
    reviewed = service._attach_post_generation_review(  # noqa: SLF001
        record,
        record.generation_result,
        GenerateJobRequest.model_validate({"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model"}}),
    )
    package = reviewed.metadata["post_generation_review_package"]
    plans = package["review_evidence_plans"]
    digests = package["review_evidence_plan_digests"]
    assert set(plans) == {"output_doc260_a", "output_doc260_b"}
    assert set(digests) == set(plans)
    assert plans["output_doc260_a"]["output_id"] == "output_doc260_a"
    assert plans["output_doc260_b"]["output_id"] == "output_doc260_b"
    assert plans["output_doc260_a"]["plan_id"] != plans["output_doc260_b"]["plan_id"]

def test_doc260_non_admitted_existing_source_is_unavailable(tmp_path) -> None:
    service = _service(tmp_path)
    source_id = _ready_uploaded_reference(service, filename="submitted.png")
    created = _create_general_job(service, uploaded_asset_ids=[source_id])
    record = service.job_store.get(created.job_id)
    assert record is not None
    resolution = _ready_resolution(tmp_path).model_copy(
        update={
            "metadata": {
                "candidate_metadata": {
                    "reference_truth_source_ids": [source_id],
                    "reference_input_execution": {
                        "admission_outcome": "rejected",
                        "operation_outcome": "submitted",
                        "reference_count": 1,
                    },
                }
            }
        }
    )
    metadata = service._admitted_review_reference_metadata(record, resolution)  # noqa: SLF001
    channel = metadata["review_evidence_plan"]["channels"]["product_truth"]
    assert channel["evidence_state"] == "unavailable"
    assert channel["reason_codes"] == ["review_evidence_product_truth_reference_not_admitted"]
    assert "uploaded_assets" not in metadata


def test_doc260_resolution_readiness_and_output_digest_are_non_certifying(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)
    record = service.job_store.get(created.job_id)
    assert record is not None
    not_ready = _ready_resolution(tmp_path).model_copy(update={"job_id": created.job_id, "status": "unreadable"})
    not_ready_metadata = service._admitted_review_reference_metadata(record, not_ready)  # noqa: SLF001
    assert not_ready_metadata["review_evidence_plan"]["channels"]["selected_output"]["evidence_state"] == "unavailable"

    drifted = _ready_resolution(tmp_path).model_copy(update={"job_id": created.job_id, "metadata": {"content_sha256": "0" * 64}})
    drifted_metadata = service._admitted_review_reference_metadata(record, drifted)  # noqa: SLF001
    assert drifted_metadata["review_evidence_plan"]["channels"]["selected_output"]["evidence_state"] == "invalid"


def test_doc260_public_create_metadata_cannot_supply_trusted_plan(tmp_path) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = service.create_job(
        {
            "user_input": "Create one clean real-camera social image with natural lighting.",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "mode_id": "social_cover",
                "preset_id": "social_cover",
            },
            "metadata": {
                "requested_image_count": 1,
                "review_evidence_plan": {"plan_id": "forged_public_plan"},
                "review_evidence_plan_digest": "forged_public_digest",
            },
        }
    )
    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "vision_inspection_mode": "vision_model",
                "review_evidence_plan": {"plan_id": "forged_generate_plan"},
                "review_evidence_plan_digest": "forged_generate_digest",
                "max_visual_retry_attempts": 0,
            },
        },
    )
    plan = _review_evidence_plan(_internal_generation_metadata(service, created.job_id))
    assert plan["plan_id"] not in {"forged_public_plan", "forged_generate_plan"}
    assert plan["job_id"] == created.job_id

def test_doc260_channels_are_deeply_immutable() -> None:
    plan = _valid_plan()
    with pytest.raises(TypeError):
        plan.channels["product_truth"] = plan.channels["person_identity"]
    with pytest.raises(TypeError):
        plan.channels._items = ()  # noqa: SLF001
    with pytest.raises(Exception):
        plan.channels["product_truth"].evidence_ids = ("replaced",)


def test_doc260_mixed_admission_is_unavailable_and_digest_binds_all_claims(tmp_path) -> None:
    service = _service(tmp_path)
    admitted_id = _ready_uploaded_reference(service, filename="admitted-mixed.png")
    rejected_id = _ready_uploaded_reference(service, filename="rejected-mixed.png")
    created = _create_general_job(service, uploaded_asset_ids=[admitted_id, rejected_id])
    record = service.job_store.get(created.job_id)
    assert record is not None
    base = _ready_resolution(tmp_path).model_copy(update={"job_id": created.job_id})
    admitted_claim = {
        "reference_truth_source_ids": [admitted_id],
        "reference_input_execution": {
            "admission_outcome": "admitted",
            "operation_outcome": "pixels_received",
            "reference_count": 1,
        },
    }
    mixed = base.model_copy(
        update={
            "metadata": {
                "candidate_metadata": admitted_claim,
                "asset_metadata": {
                    "candidate_metadata": {
                        "reference_truth_source_ids": [rejected_id],
                        "reference_input_execution": {
                            "admission_outcome": "rejected",
                            "operation_outcome": "submitted",
                            "reference_count": 1,
                        },
                    }
                },
            }
        }
    )
    admitted_only = base.model_copy(update={"metadata": {"candidate_metadata": admitted_claim}})
    mixed_plan = service._admitted_review_reference_metadata(record, mixed)["review_evidence_plan"]  # noqa: SLF001
    admitted_plan = service._admitted_review_reference_metadata(record, admitted_only)["review_evidence_plan"]  # noqa: SLF001
    product = mixed_plan["channels"]["product_truth"]
    assert product["evidence_state"] == "unavailable"
    assert set(product["evidence_ids"]) == {admitted_id, rejected_id}
    assert mixed_plan["source_binding_digest"] != admitted_plan["source_binding_digest"]


def test_doc260_asset_metadata_role_and_operation_bindings_are_exact(tmp_path) -> None:
    service = _service(tmp_path)
    source_id = _ready_uploaded_reference(service, filename="role-binding.png")
    created = _create_general_job(service, uploaded_asset_ids=[source_id])
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.request = record.request.model_copy(
        update={"metadata": {**dict(record.request.metadata), "mcp_operation_id": "operation_expected"}}
    )
    resolution = _ready_resolution(tmp_path).model_copy(
        update={
            "job_id": created.job_id,
            "metadata": {
                "asset_metadata": {
                    "candidate_metadata": {
                        "job_id": "other_job",
                        "candidate_id": "other_candidate",
                        "mcp_operation_id": "operation_other",
                        "provider_delivery": {
                            "job_id": "other_delivery_job",
                            "output_id": "output_doc260",
                            "candidate_id": "other_delivery_candidate",
                        },
                        "reference_truth_source_ids": [source_id],
                        "reference_truth_role": "face_reference",
                        "reference_input_execution": {
                            "admission_outcome": "admitted",
                            "operation_outcome": "pixels_received",
                            "reference_count": 1,
                        },
                    }
                }
            },
        }
    )
    plan = service._admitted_review_reference_metadata(record, resolution)["review_evidence_plan"]  # noqa: SLF001
    assert plan["channels"]["product_truth"]["evidence_state"] == "invalid"
    selected = plan["channels"]["selected_output"]
    assert selected["evidence_state"] == "invalid"
    assert {"operation_job_binding", "operation_candidate_binding", "mcp_operation_binding"}.issubset(selected["reason_codes"])


def test_doc260_ready_plan_receipt_closes_for_absent_non_dict_mismatch_and_mixed_ready(tmp_path, monkeypatch) -> None:
    first = _ready_resolution(tmp_path, output_id="output_doc260_receipt_a")
    second = _ready_resolution(tmp_path, output_id="output_doc260_receipt_b")
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(first),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)
    service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0}},
    )
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    service.output_resolver = _StaticReadyResolver([first, second])
    original = service._admitted_review_reference_metadata  # noqa: SLF001

    for shape in ("absent", "non_dict", "mismatch"):
        def malformed(current_record, resolution, *, shape=shape):  # noqa: ANN001
            payload = original(current_record, resolution)
            if resolution.output_id != "output_doc260_receipt_b":
                return payload
            if shape == "absent":
                return {}
            if shape == "non_dict":
                return {"review_evidence_plan": "not-a-plan"}
            payload["review_evidence_plan"] = {**payload["review_evidence_plan"], "output_id": "other_output"}
            return payload

        monkeypatch.setattr(service, "_admitted_review_reference_metadata", malformed)
        reviewed = service._attach_post_generation_review(  # noqa: SLF001
            record,
            record.generation_result,
            GenerateJobRequest.model_validate({"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model"}}),
        )
        package = reviewed.metadata["post_generation_review_package"]
        assert package["review_evidence_receipt_status"] == "closed"
        assert package["review_evidence_receipt_errors"]
        assert package["real_pixel_review"] is False

    monkeypatch.setattr(service, "_admitted_review_reference_metadata", original)


def test_doc260_evidence_gate_without_provider_call_cannot_claim_real_pixel_review(tmp_path) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(tmp_path, vision_inspector=VisionOutputInspector(vision_provider=provider))
    source_id = _ready_uploaded_reference(service, filename="gate-drift.png")
    upload = service.asset_store.get_upload(source_id)
    assert upload is not None and upload.file_path
    Path(upload.file_path).write_bytes(base64.b64decode(_png_base64(48, 48)))
    resolution = _ready_resolution(tmp_path)
    resolution = resolution.model_copy(
        update={
            "metadata": {
                **resolution.metadata,
                "candidate_metadata": {
                    "reference_truth_source_ids": [source_id],
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                },
            }
        }
    )
    service.output_resolver = _StaticReadyResolver(resolution)
    created = _create_general_job(service, uploaded_asset_ids=[source_id])
    service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0}},
    )
    package = _internal_generation_metadata(service, created.job_id)["post_generation_review_package"]
    assert provider.calls == []
    assert package["real_pixel_review"] is False

def test_doc260_closed_ready_receipt_withholds_public_delivery_and_selection(tmp_path, monkeypatch) -> None:
    first = _ready_resolution(tmp_path, output_id="output_doc260_closed_a")
    second = _ready_resolution(tmp_path, output_id="output_doc260_closed_b")
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(first),
        vision_inspector=VisionOutputInspector(vision_provider=provider),
    )
    created = _create_general_job(service)
    service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0}},
    )
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    service.output_resolver = _StaticReadyResolver([first, second])
    original = service._admitted_review_reference_metadata  # noqa: SLF001

    def missing_second_plan(current_record, resolution):  # noqa: ANN001
        if resolution.output_id == second.output_id:
            return {}
        return original(current_record, resolution)

    monkeypatch.setattr(service, "_admitted_review_reference_metadata", missing_second_plan)
    reviewed = service._attach_post_generation_review(  # noqa: SLF001
        record,
        record.generation_result,
        GenerateJobRequest.model_validate({"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model"}}),
    )
    package = reviewed.metadata["post_generation_review_package"]
    assert package["review_evidence_receipt_status"] == "closed"
    delivery, output_ids, asset_ids = service._public_final_delivery_projection(reviewed)  # noqa: SLF001
    assert delivery["final_delivery_status"] != "ready"
    assert delivery["automatic_delivery_available"] is False
    assert output_ids == set()
    assert asset_ids == set()

    record.generation_result = reviewed
    service.job_store.save(record)
    public = service.get_job(created.job_id)
    selection = service.select_result(created.job_id, {})
    assert public.metadata["final_delivery"]["automatic_delivery_available"] is False
    assert public.asset_series == []
    assert selection.selected_result.metadata["selection_status"] == "final_delivery_withheld"


def test_doc260_unknown_claimed_channel_invalidates_server_owned_product_channel_and_blocks_vision(tmp_path) -> None:
    provider = _StaticVisionProvider({"status": "pass", "confidence": 0.96, "issue_codes": []})
    service = _service(tmp_path, vision_inspector=VisionOutputInspector(vision_provider=provider))
    source_id = _ready_uploaded_reference(service, filename="unknown-channel-product.png", role="product_reference")
    base_resolution = _ready_resolution(tmp_path)
    resolution = base_resolution.model_copy(
        update={
            "metadata": {
                **base_resolution.metadata,
                "candidate_metadata": {
                    "reference_truth_source_ids": [source_id],
                    "reference_truth_channel": "unknown_channel",
                    "reference_input_execution": {
                        "admission_outcome": "admitted",
                        "operation_outcome": "pixels_received",
                        "reference_count": 1,
                    },
                },
            }
        }
    )
    service.output_resolver = _StaticReadyResolver(resolution)
    created = _create_general_job(service, uploaded_asset_ids=[source_id])
    service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"vision_inspection_mode": "vision_model", "max_visual_retry_attempts": 0}},
    )
    package = _internal_generation_metadata(service, created.job_id)["post_generation_review_package"]
    plan = package["review_evidence_plans"][resolution.output_id]
    assert set(plan["channels"]) == {"product_truth", "person_identity", "prompt_semantics", "selected_output"}
    assert plan["channels"]["product_truth"]["evidence_state"] == "invalid"
    assert plan["channels"]["selected_output"]["evidence_state"] == "available"
    assert provider.calls == []
    assert package["real_pixel_review"] is False
