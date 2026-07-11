import base64
from io import BytesIO
from pathlib import Path

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.product_api import ProductJobStatusValue, V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.output_resolver import GeneratedOutputResolver
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.schemas import AssetType, PackagedAsset, Platform
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import GeneratedOutputResolution, VisionOutputInspector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    VisionInspectionProviderError,
    _is_timeout_error,
)


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


class _SequencedVisionProvider(_StaticVisionProvider):
    def __init__(self, payloads: list[dict]) -> None:
        super().__init__({})
        self.payloads = list(payloads)

    def inspect(self, resolution: GeneratedOutputResolution, *, metadata: dict | None = None) -> dict:
        self.calls.append(resolution)
        index = min(len(self.calls) - 1, len(self.payloads) - 1)
        return dict(self.payloads[index])


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


def test_identity_vision_provider_failures_use_bounded_default_attempts(tmp_path, monkeypatch) -> None:
    class FailingVisionProvider:
        provider_name = "failing_vision"

        def __init__(self) -> None:
            self.calls = 0

        def available(self, *, force: bool = False) -> bool:
            return True

        def inspect(self, resolution, *, metadata=None):  # noqa: ANN001
            self.calls += 1
            raise VisionInspectionProviderError("Request timed out.")

    monkeypatch.delenv("V3_VISION_INSPECTION_MAX_ATTEMPTS", raising=False)
    monkeypatch.setattr(
        "alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector.time.sleep",
        lambda _seconds: None,
    )
    provider = FailingVisionProvider()
    inspector = VisionOutputInspector(vision_provider=provider)

    report = inspector.inspect(
        _ready_resolution(tmp_path),
        metadata={
            "vision_inspection_mode": "hybrid",
            "require_real_images": True,
            "uploaded_assets": [{"asset_id": "face", "role": "face_reference"}],
        },
    )

    assert provider.calls == 2
    assert report.status == "manual_review"
    assert report.evidence["provider_review_attempts"] == 2


def test_vision_timeout_detection_covers_sdk_and_gateway_messages() -> None:
    assert _is_timeout_error(TimeoutError("request stalled")) is True
    assert _is_timeout_error(RuntimeError("Request timed out.")) is True
    assert _is_timeout_error(RuntimeError("unsupported endpoint")) is False


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
    assert review["final_review"]["status"] == "failed_after_retry"
    assert review["final_review"]["additional_retry_allowed"] is False
    assert [attempt["stage"] for attempt in review["review_attempts"]] == ["initial", "final_retry"]


def test_product_api_retry_review_becomes_authoritative_and_preserves_initial_failure(tmp_path) -> None:
    provider = _SequencedVisionProvider(
        [
            {
                "status": "fail_retryable",
                "confidence": 0.91,
                "issue_codes": ["visible_text_artifact"],
                "summary": ["V3 found extra text in the first output."],
            },
            {
                "status": "pass",
                "confidence": 0.93,
                "issue_codes": [],
                "summary": ["The retry output passed the visual review."],
            },
        ]
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

    review = generated.metadata["post_generation_review"]
    history = review["review_attempts"]
    final_review = review["final_review"]

    assert len(provider.calls) == 2
    assert [attempt["stage"] for attempt in history] == ["initial", "final_retry"]
    assert history[0]["statuses"] == ["fail_retryable"]
    assert history[0]["issue_codes"] == ["visible_text_artifact"]
    assert history[1]["statuses"] == ["pass"]
    assert review["inspections"][0]["status"] == "pass"
    assert final_review["status"] == "pass"
    assert final_review["additional_retry_allowed"] is False
    assert generated.metadata["visual_auto_retry"]["executed_count"] == 1
    cluster_review = generated.metadata["shared_capabilities"]["visual_cluster"][
        "post_generation_review_package"
    ]
    assert cluster_review["final_review"]["status"] == "pass"


def test_doc95_worse_retry_does_not_replace_stronger_initial_attempt(tmp_path) -> None:
    provider = _SequencedVisionProvider(
        [
            {
                "status": "fail_retryable",
                "confidence": 0.94,
                "issue_codes": ["visible_text_artifact"],
                "scores": {
                    "same_person_readability": 0.96,
                    "prompt_owned_channel_obedience": 0.95,
                    "human_realism": 0.91,
                    "commercial_finish": 0.90,
                },
            },
            {
                "status": "fail_retryable",
                "confidence": 0.92,
                "issue_codes": ["visible_text_artifact"],
                "scores": {
                    "same_person_readability": 0.55,
                    "prompt_owned_channel_obedience": 0.72,
                    "human_realism": 0.67,
                    "commercial_finish": 0.70,
                },
            },
        ]
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

    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    preference = record.generation_result.metadata["reviewed_delivery_preference"]
    assert preference["preferred_attempt_index"] == 0
    assert preference["latest_attempt_won"] is False
    assert preference["ranked_attempts"][0]["score"] > preference["ranked_attempts"][1]["score"]


def test_doc95_delivery_selection_compares_each_suite_role_independently(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)
    service.generate_job(created.job_id, {"quality_mode": "standard", "metadata": {}})
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None
    generated = record.generation_result

    def inspection(output_id: str, asset_id: str, score: float, issue_code: str | None = None) -> dict:
        return {
            "output_id": output_id,
            "asset_id": asset_id,
            "status": "fail_retryable" if issue_code else "warning",
            "detected_issues": [{"code": issue_code}] if issue_code else [],
            "score_card": {
                "same_person_readability": score,
                "prompt_owned_channel_obedience": score,
                "human_realism": score,
                "commercial_finish": score,
            },
        }

    package = {
        "review_attempts": [
            {
                "stage": "initial",
                "attempt_index": 0,
                "output_ids": ["initial_a", "initial_b"],
                "statuses": ["warning"],
                "issue_codes": [],
                "inspections": [inspection("initial_a", "role_a", 0.94), inspection("initial_b", "role_b", 0.62)],
            },
            {
                "stage": "final_retry",
                "attempt_index": 1,
                "output_ids": ["retry_a", "retry_b"],
                "statuses": ["warning"],
                "issue_codes": [],
                "inspections": [
                    inspection("retry_a", "role_a", 0.99, "same_type_not_same_person"),
                    inspection("retry_b", "role_b", 0.91),
                ],
            },
        ]
    }
    candidate = generated.model_copy(
        update={"metadata": {**dict(generated.metadata), "post_generation_review_package": package}}
    )

    preferred = service._apply_reviewed_delivery_preference(candidate)  # noqa: SLF001
    preference = preferred.metadata["reviewed_delivery_preference"]

    assert preference["selection_scope"] == "per_asset_role"
    assert set(preference["preferred_output_ids"]) == {"initial_a", "retry_b"}
    assert preference["preferred_attempt_index"] is None
    retry_a = next(item for item in preference["ranked_outputs"] if item["output_id"] == "retry_a")
    assert retry_a["hard_gate_passed"] is False
    assert retry_a["hard_gate_failures"] == ["identity_truth_not_respected"]


def test_doc96_unreviewed_retry_cannot_replace_reviewed_initial_output(tmp_path) -> None:
    service = _service(tmp_path)
    created = _create_general_job(service)
    service.generate_job(created.job_id, {"quality_mode": "standard", "metadata": {}})
    record = service.job_store.get(created.job_id)
    assert record is not None and record.generation_result is not None

    package = {
        "review_attempts": [
            {
                "stage": "initial",
                "attempt_index": 0,
                "output_ids": ["reviewed_initial"],
                "statuses": ["fail_retryable"],
                "issue_codes": ["identity_drift"],
                "inspections": [
                    {
                        "output_id": "reviewed_initial",
                        "asset_id": "same_role",
                        "status": "fail_retryable",
                        "detected_issues": [{"code": "identity_drift"}],
                        "score_card": {
                            "same_person_readability": 0.76,
                            "prompt_owned_channel_obedience": 0.86,
                            "human_realism": 0.78,
                            "commercial_finish": 0.82,
                        },
                    }
                ],
            },
            {
                "stage": "final_retry",
                "attempt_index": 1,
                "output_ids": ["unreviewed_retry"],
                "statuses": ["manual_review"],
                "issue_codes": ["provider_error"],
                "inspections": [
                    {
                        "output_id": "unreviewed_retry",
                        "asset_id": "same_role",
                        "status": "manual_review",
                        "detected_issues": [{"code": "provider_error"}],
                        "score_card": {"overall": 0.90},
                    }
                ],
            },
        ]
    }
    candidate = record.generation_result.model_copy(
        update={"metadata": {**dict(record.generation_result.metadata), "post_generation_review_package": package}}
    )

    preferred = service._apply_reviewed_delivery_preference(candidate)  # noqa: SLF001
    preference = preferred.metadata["reviewed_delivery_preference"]

    assert preference["preferred_output_ids"] == ["reviewed_initial"]
    retry = next(item for item in preference["ranked_outputs"] if item["output_id"] == "unreviewed_retry")
    assert retry["review_unavailable"] is True
    assert "review_unavailable" in retry["hard_gate_failures"]


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
