import base64
from io import BytesIO
from pathlib import Path

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.output_resolver import GeneratedOutputResolver
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.schemas import AssetType, PackagedAsset, Platform
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import GeneratedOutputResolution, VisionOutputInspector


def _png_base64(width: int = 96, height: int = 72) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(110, 170, 210))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _asset(output_id: str | None = None, candidate_id: str = "candidate_doc55") -> PackagedAsset:
    candidate_metadata = {"output_id": output_id, "candidate_id": candidate_id} if output_id else {}
    return PackagedAsset(
        asset_id="asset_doc55",
        asset_type=AssetType.SINGLE_IMAGE,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="doc55 generated image",
        metadata={
            "selected_candidate_id": candidate_id,
            "candidate_metadata": candidate_metadata,
        },
    )


def _service(tmp_path: Path, **overrides) -> V3ProductApiService:
    return V3ProductApiService(
        brand_profile_service=BrandProfileService(BrandProfileStore(tmp_path / "brand_memory")),
        **overrides,
    )


def _create_general_job(service: V3ProductApiService):
    return service.create_job(
        {
            "user_input": "生成一张夏日清凉东方美女写真，干净明亮，适合社媒封面",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "mode_id": "social_cover",
                "preset_id": "social_cover",
            },
            "metadata": {"requested_image_count": 1},
        }
    )


def _ready_resolution(tmp_path: Path) -> GeneratedOutputResolution:
    image_path = tmp_path / "ready.png"
    image_path.write_bytes(base64.b64decode(_png_base64()))
    return GeneratedOutputResolution(
        resolution_id="resolution_ready",
        project_id="project_doc55",
        job_id="job_doc55",
        candidate_id="candidate_doc55",
        asset_id="asset_doc55",
        output_id="output_doc55",
        file_path=str(image_path),
        mime_type="image/png",
        width=96,
        height=72,
        status="ready",
    )


def _openai_resolution_with_aigc_metadata(tmp_path: Path) -> GeneratedOutputResolution:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo

    image_path = tmp_path / "openai_with_aigc_metadata.png"
    image = Image.new("RGB", (128, 128), color=(235, 244, 248))
    png_info = PngInfo()
    png_info.add_text(
        "UserComment",
        '{"AIGC":{"Label":"1","ContentProducer":"third_party","ReservedCode1":"{\\"Type\\":\\" TC260PG\\"}"}}',
    )
    image.save(image_path, pnginfo=png_info)
    return GeneratedOutputResolution(
        resolution_id="resolution_openai_aigc",
        project_id="project_doc55",
        job_id="job_doc55",
        candidate_id="candidate_openai_aigc",
        asset_id="asset_doc55",
        output_id="output_openai_aigc",
        file_path=str(image_path),
        mime_type="image/png",
        width=128,
        height=128,
        provider="openai_gpt_image",
        model="gpt-image-2",
        status="ready",
    )


class _StaticVisionProvider:
    provider_name = "static_test_vision"

    def __init__(self, payload: dict, *, available: bool = True) -> None:
        self.payload = payload
        self.available_flag = available
        self.calls: list[GeneratedOutputResolution] = []

    def available(self, *, force: bool = False) -> bool:
        return self.available_flag

    def inspect(self, resolution: GeneratedOutputResolution, *, metadata: dict | None = None) -> dict:
        self.calls.append(resolution)
        return dict(self.payload)


class _StaticReadyResolver:
    def __init__(self, resolution: GeneratedOutputResolution) -> None:
        self.resolution = resolution

    def resolve_result(self, result, project_id: str | None = None):
        return [self.resolution.model_copy(update={"project_id": project_id or self.resolution.project_id})]


def test_generated_output_resolver_finds_original_file_by_output_id(tmp_path) -> None:
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_doc55",
        candidate_id="candidate_doc55",
        asset_id="asset_doc55",
        provider="test_provider",
        model="test-model",
        encoded_image=_png_base64(),
        mime_type="image/png",
        output_format="png",
    )
    resolver = GeneratedOutputResolver(store)

    resolution = resolver.resolve_asset("job_doc55", _asset(record.output_id), project_id="project_doc55")

    assert resolution.status == "ready"
    assert resolution.output_id == record.output_id
    assert resolution.file_path == record.file_path
    assert Path(resolution.file_path).exists()
    assert resolution.width == 96
    assert resolution.height == 72


def test_generated_output_resolver_missing_output_becomes_safe_missing(tmp_path) -> None:
    resolver = GeneratedOutputResolver(V3GeneratedOutputStore(tmp_path / "outputs"))

    resolution = resolver.resolve_asset("job_doc55", _asset(None), project_id="project_doc55")

    assert resolution.status == "missing"
    assert resolution.warnings


def test_vision_inspector_fake_visible_text_becomes_retryable(tmp_path) -> None:
    resolver = GeneratedOutputResolver(V3GeneratedOutputStore(tmp_path / "outputs"))
    resolution = resolver.resolve_asset("job_doc55", _asset(None), project_id="project_doc55")
    inspector = VisionOutputInspector()

    report = inspector.inspect(
        resolution,
        metadata={"post_generation_fake_issue_codes": ["visible_text_artifact"]},
    )

    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert report.retry_patch["negative_additions"]
    assert report.detected_issues[0]["code"] == "visible_text_artifact"


def test_vision_inspector_corner_watermark_trace_becomes_retryable(tmp_path) -> None:
    inspector = VisionOutputInspector()

    report = inspector.inspect(
        _ready_resolution(tmp_path),
        metadata={"post_generation_fake_issue_codes": ["faint_corner_watermark", "lower_right_mark_artifact"]},
    )

    assert report.status == "fail_retryable"
    assert report.retryable is True
    patch_text = " ".join(
        [
            *report.retry_patch["negative_additions"],
            *report.retry_patch["artifact_repair"],
        ]
    )
    assert "lower-right logo" in patch_text
    assert "semi-transparent mark" in patch_text
    assert any(issue["code"] == "faint_corner_watermark" for issue in report.detected_issues)


def test_vision_inspector_product_label_issue_becomes_retryable(tmp_path) -> None:
    inspector = VisionOutputInspector()

    report = inspector.inspect(
        _ready_resolution(tmp_path),
        metadata={"post_generation_fake_issue_codes": ["product_label_unreadable"]},
    )

    patch_text = " ".join(
        [
            *report.retry_patch["negative_additions"],
            *report.retry_patch["artifact_repair"],
            *report.retry_patch["product_reinforcement"],
        ]
    )
    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert report.detected_issues[0]["code"] == "product_label_unreadable"
    assert "readable" in patch_text
    assert "product label" in patch_text


def test_vision_inspector_ai_face_issue_becomes_retryable(tmp_path) -> None:
    inspector = VisionOutputInspector()

    report = inspector.inspect(
        _ready_resolution(tmp_path),
        metadata={"post_generation_fake_issue_codes": ["plastic_skin", "template_smile"]},
    )

    patch_text = " ".join(
        [
            *report.retry_patch["negative_additions"],
            *report.retry_patch["artifact_repair"],
            *report.retry_patch["identity_reinforcement"],
            *report.retry_patch["prompt_additions"],
        ]
    )
    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert [issue["code"] for issue in report.detected_issues] == ["plastic_skin", "template_smile"]
    assert "over-smoothed skin" in patch_text
    assert "real photographed skin" in patch_text
    assert "varying expression" in patch_text


def test_vision_inspector_flags_openai_gpt_image_aigc_provenance_mismatch(tmp_path) -> None:
    inspector = VisionOutputInspector()

    report = inspector.inspect(_openai_resolution_with_aigc_metadata(tmp_path))

    issue_codes = [issue["code"] for issue in report.detected_issues]
    patch_text = " ".join(
        [
            *report.retry_patch["negative_additions"],
            *report.retry_patch["artifact_repair"],
        ]
    )
    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert "third_party_aigc_metadata" in issue_codes
    assert "provider_provenance_mismatch" in issue_codes
    assert "ai_generated_badge_trace" in issue_codes
    assert report.evidence["expected_openai_gpt_image"] is True
    assert report.evidence["has_aigc_metadata"] is True
    assert "third-party AIGC label" in patch_text


def test_vision_inspector_low_confidence_does_not_retry(tmp_path) -> None:
    resolver = GeneratedOutputResolver(V3GeneratedOutputStore(tmp_path / "outputs"))
    resolution = resolver.resolve_asset("job_doc55", _asset(None), project_id="project_doc55")
    inspector = VisionOutputInspector()

    report = inspector.inspect(
        resolution,
        metadata={"post_generation_fake_issue_codes": ["visible_text_artifact"], "post_generation_fake_confidence": 0.4},
    )

    assert report.status == "manual_review"
    assert report.retryable is False
    assert report.retry_patch == {}


def test_vision_inspector_unreadable_file_becomes_manual_review(tmp_path) -> None:
    broken = tmp_path / "broken.png"
    broken.write_text("not an image", encoding="utf-8")
    resolution = GeneratedOutputResolution(
        resolution_id="resolution_broken",
        job_id="job_doc55",
        candidate_id="candidate_broken",
        asset_id="asset_broken",
        output_id="output_broken",
        file_path=str(broken),
        status="ready",
    )
    inspector = VisionOutputInspector()

    report = inspector.inspect(resolution)

    assert report.status == "manual_review"
    assert report.retryable is False
    assert report.detected_issues[0]["code"] == "file_unreadable"


def test_vision_inspector_fake_provider_error_does_not_retry(tmp_path) -> None:
    inspector = VisionOutputInspector()

    report = inspector.inspect(
        _ready_resolution(tmp_path),
        metadata={"post_generation_fake_issue_codes": ["provider_error"]},
    )

    assert report.status == "manual_review"
    assert report.retryable is False
    assert report.retry_patch == {}


def test_vision_inspector_calls_injected_real_provider_for_ready_file(tmp_path) -> None:
    provider = _StaticVisionProvider(
        {
            "status": "fail_retryable",
            "confidence": 0.91,
            "issue_codes": ["watermark_or_signature"],
            "scores": {"overall": 0.44},
            "summary": ["V3 发现图片里有不该出现的标记"],
        }
    )
    inspector = VisionOutputInspector(vision_provider=provider)

    report = inspector.inspect(_ready_resolution(tmp_path), metadata={"vision_inspection_mode": "vision_model"})

    assert provider.calls
    assert report.mode == "vision_model"
    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert "watermark" in " ".join(report.retry_patch["negative_additions"])


def test_vision_inspector_provider_unavailable_becomes_manual_review(tmp_path) -> None:
    inspector = VisionOutputInspector(vision_provider=_StaticVisionProvider({}, available=False))

    report = inspector.inspect(_ready_resolution(tmp_path), metadata={"vision_inspection_mode": "vision_model"})

    assert report.status == "manual_review"
    assert report.retryable is False
    assert report.detected_issues[0]["code"] == "vision_provider_unavailable"


def test_vision_inspector_real_provider_low_confidence_does_not_retry(tmp_path) -> None:
    provider = _StaticVisionProvider(
        {
            "status": "fail_retryable",
            "confidence": 0.44,
            "issue_codes": ["visible_text_artifact"],
        }
    )
    inspector = VisionOutputInspector(vision_provider=provider)

    report = inspector.inspect(_ready_resolution(tmp_path), metadata={"vision_inspection_mode": "hybrid"})

    assert report.status == "manual_review"
    assert report.retryable is False
    assert report.retry_patch == {}
    assert any(issue["code"] == "low_confidence_review" for issue in report.detected_issues)


def test_product_api_doc55_signal_triggers_doc53_retry_without_force_retry_metadata(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "post_generation_fake_issue_codes": ["visible_text_artifact"],
                "max_visual_retry_attempts": 1,
            },
        },
    )

    retry_summary = generated.metadata["visual_auto_retry"]
    review = generated.metadata["post_generation_review"]
    retry_candidates = [candidate for candidate in generated.candidates if candidate.metadata.get("visual_auto_retry_output")]

    assert generated.status == ProductJobStatusValue.GENERATED
    assert review["inspections"][0]["status"] == "fail_retryable"
    assert review["real_review_signal_package"]["retryable_candidate_ids"]
    assert retry_summary["executed_count"] == 1
    assert retry_candidates
    assert retry_summary["records"][0]["source"] == "real_review_signal_package"
    assert retry_summary["records"][0]["retry_patch"]["target_candidate_ids"]


def test_product_api_aigc_provenance_issue_retries_by_default_in_standard_mode(tmp_path) -> None:
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_openai_resolution_with_aigc_metadata(tmp_path)),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {},
        },
    )

    retry_summary = generated.metadata["visual_auto_retry"]
    review = generated.metadata["post_generation_review"]
    retry_candidates = [candidate for candidate in generated.candidates if candidate.metadata.get("visual_auto_retry_output")]
    issue_codes = review["inspections"][0]["detected_issues"]
    issue_codes = [issue["code"] for issue in issue_codes]

    assert generated.status == ProductJobStatusValue.GENERATED
    assert review["inspections"][0]["status"] == "fail_retryable"
    assert "third_party_aigc_metadata" in issue_codes
    assert "provider_provenance_mismatch" in issue_codes
    assert retry_summary["enabled"] is True
    assert retry_summary["max_attempts"] == 1
    assert retry_summary["executed_count"] == 1
    assert retry_candidates


def test_product_api_low_confidence_doc55_signal_does_not_retry(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "post_generation_fake_issue_codes": ["visible_text_artifact"],
                "post_generation_fake_confidence": 0.4,
                "max_visual_retry_attempts": 1,
            },
        },
    )

    retry_summary = generated.metadata["visual_auto_retry"]
    review = generated.metadata["post_generation_review"]

    assert generated.status == ProductJobStatusValue.GENERATED
    assert review["inspections"][0]["status"] == "manual_review"
    assert retry_summary["executed_count"] == 0
    assert not any(candidate.metadata.get("visual_auto_retry_output") for candidate in generated.candidates)


def test_product_api_real_vision_signal_triggers_retry_and_inspects_retry_output(tmp_path) -> None:
    provider = _StaticVisionProvider(
        {
            "status": "fail_retryable",
            "confidence": 0.88,
            "issue_codes": ["visible_text_artifact"],
            "summary": ["V3 发现图片里有多余文字"],
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
            "metadata": {
                "vision_inspection_mode": "vision_model",
                "max_visual_retry_attempts": 1,
            },
        },
    )

    retry_summary = generated.metadata["visual_auto_retry"]
    review = generated.metadata["post_generation_review"]

    assert generated.status == ProductJobStatusValue.GENERATED
    assert review["inspections"][0]["mode"] == "vision_model"
    assert review["inspections"][0]["status"] == "fail_retryable"
    assert retry_summary["executed_count"] == 1
    assert len(provider.calls) >= 2


def test_product_api_provider_unavailable_does_not_retry(tmp_path) -> None:
    service = _service(
        tmp_path,
        output_resolver=_StaticReadyResolver(_ready_resolution(tmp_path)),
        vision_inspector=VisionOutputInspector(vision_provider=_StaticVisionProvider({}, available=False)),
    )
    created = _create_general_job(service)

    generated = service.generate_job(
        created.job_id,
        {
            "quality_mode": "standard",
            "metadata": {
                "vision_inspection_mode": "vision_model",
                "max_visual_retry_attempts": 1,
            },
        },
    )

    retry_summary = generated.metadata["visual_auto_retry"]
    review = generated.metadata["post_generation_review"]

    assert review["inspections"][0]["status"] == "manual_review"
    assert review["inspections"][0]["detected_issues"][0]["code"] == "vision_provider_unavailable"
    assert retry_summary["executed_count"] == 0
