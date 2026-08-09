import base64
from io import BytesIO
from pathlib import Path

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.llm_brain.fallback import build_fallback_result
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.assets import V3UploadedAssetStore
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.output_resolver import GeneratedOutputResolver
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
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
    def __init__(self, resolution: GeneratedOutputResolution) -> None:
        self.resolution = resolution

    def resolve_result(self, result, project_id: str | None = None):  # noqa: ANN001
        packaged = result.asset_pack.assets[0]
        candidate_metadata = packaged.metadata.get("candidate_metadata", {})
        return [
            self.resolution.model_copy(
                update={
                    "project_id": project_id or self.resolution.project_id,
                    "asset_id": packaged.asset_id,
                    "candidate_id": packaged.metadata.get("selected_candidate_id"),
                    "output_id": candidate_metadata.get("output_id") or self.resolution.output_id,
                }
            )
        ]


def _ready_resolution(tmp_path: Path, *, output_id: str = "output_doc260") -> GeneratedOutputResolution:
    image_path = tmp_path / f"{output_id}.png"
    image_path.write_bytes(base64.b64decode(_png_base64()))
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
    plan = package.get("review_evidence_plan")
    assert isinstance(plan, dict), "Doc260 requires an internal typed ReviewEvidencePlan on the review package"
    assert package.get("review_evidence_plan_digest"), "Doc260 requires a safe plan digest in the review package"
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
    report = VisionOutputInspector(vision_provider=provider).inspect(
        _ready_resolution(tmp_path),
        metadata={
            "vision_inspection_mode": "hybrid",
            "review_evidence_plan": {
                "contract_version": "review_evidence_plan_v1",
                "channels": {
                    "person_identity": {
                        "applicability": "required",
                        "evidence_state": "unavailable",
                        "evidence_ids": ["v3_asset_missing"],
                        "comparison_allowed": False,
                    },
                    "selected_output": {
                        "applicability": "required",
                        "evidence_state": "available",
                        "evidence_ids": ["output_doc260"],
                        "comparison_allowed": False,
                    },
                },
            },
        },
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
