from __future__ import annotations

from pathlib import Path
import base64
from io import BytesIO
from types import SimpleNamespace

from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.providers import ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    IdentityMetricResult,
    VisionOutputInspector,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.identity_metric import _calibrate_sface_cosine
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import VisionInspectionProviderError


def test_doc96_identity_truth_requests_high_input_fidelity() -> None:
    provider = ProductionImageGenerationProvider(output_store=object())
    asset_plan = {
        "provider_input_plan": {
            "reference_truth_layers": [
                {"truth_layer": "portrait_identity_truth"},
            ]
        }
    }
    assert provider._input_fidelity_for_asset_plan(asset_plan) == "high"  # noqa: SLF001


def test_doc96_product_truth_requests_high_input_fidelity() -> None:
    provider = ProductionImageGenerationProvider(output_store=object())
    asset_plan = {
        "provider_input_plan": {
            "reference_truth_layers": [
                {"truth_layer": "product_identity_truth"},
            ]
        }
    }
    assert provider._input_fidelity_for_asset_plan(asset_plan) == "high"  # noqa: SLF001


def test_doc96_style_only_reference_does_not_force_high_fidelity() -> None:
    provider = ProductionImageGenerationProvider(output_store=object())
    asset_plan = {
        "provider_input_plan": {
            "reference_truth_layers": [
                {"truth_layer": "style_context_truth"},
            ]
        }
    }
    assert provider._input_fidelity_for_asset_plan(asset_plan) is None  # noqa: SLF001


def test_doc96_governance_is_universal_and_not_scene_named() -> None:
    runtime_files = [
        Path(__file__).resolve().parents[1] / "app/generation_router/providers.py",
        Path(__file__).resolve().parents[1] / "app/shared_capabilities/visual_cluster/portrait_identity.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in runtime_files)
    for forbidden in ("ancient_identity", "kidswear_identity", "east_asian_identity", "hanfu_identity"):
        assert forbidden not in source


class _StaticVisionProvider:
    provider_name = "doc96_static_vision"

    def available(self, *, force: bool = False) -> bool:
        return True

    def inspect(self, resolution, *, metadata=None):
        return {
            "status": "fail_retryable",
            "confidence": 0.9,
            "issue_codes": ["identity_drift", "same_type_not_same_person"],
            "scores": {
                "same_person_readability": 0.70,
                "identity_consistency": 0.70,
                "prompt_owned_channel_obedience": 0.90,
                "human_realism": 0.82,
                "commercial_finish": 0.86,
                "overall": 0.78,
            },
        }


class _StaticIdentityMetric:
    def __init__(self, score: float, geometry: float) -> None:
        self.score = score
        self.geometry = geometry

    def evaluate(self, output_path, reference_paths):
        return IdentityMetricResult(
            status="pass" if self.score >= 0.82 else "warning",
            calibrated_score=self.score,
            raw_cosine_similarity=0.65,
            geometry_score=self.geometry,
            detection_confidence=0.9,
            metric_confidence=0.9,
            reference_face_count=1,
            output_face_count=1,
            selected_reference_index=0,
            selected_output_index=0,
            output_face_box=[0.25, 0.2, 0.5, 0.55],
            metadata={"embedding_persisted": False},
        )


class _UnavailableVisionProvider:
    provider_name = "doc96_unavailable_vision"

    def available(self, *, force: bool = False) -> bool:
        return False


class _FlakyVisionProvider(_StaticVisionProvider):
    def __init__(self) -> None:
        self.calls = 0

    def inspect(self, resolution, *, metadata=None):
        self.calls += 1
        if self.calls < 3:
            raise VisionInspectionProviderError("temporary reviewer failure")
        return {
            "status": "pass",
            "confidence": 0.90,
            "issue_codes": [],
            "scores": {
                "same_person_readability": 0.84,
                "prompt_owned_channel_obedience": 0.88,
                "human_realism": 0.82,
                "commercial_finish": 0.86,
            },
        }


def _identity_review_metadata(reference_path: Path) -> dict:
    return {
        "enable_real_vision_inspection": True,
        "uploaded_assets": [
            {
                "asset_id": "uploaded_face",
                "file_path": str(reference_path),
                "role": "portrait_identity",
                "use_policy": "identity",
            }
        ],
    }


def _resolution(path: Path) -> GeneratedOutputResolution:
    return GeneratedOutputResolution(
        resolution_id="resolution_doc96",
        project_id="project_doc96",
        job_id="job_doc96",
        candidate_id="candidate_doc96",
        asset_id="asset_doc96",
        output_id="output_doc96",
        file_path=str(path),
        mime_type="image/png",
        width=512,
        height=512,
        status="ready",
    )


def test_doc96_fused_metric_can_clear_subjective_same_type_identity_issue(tmp_path) -> None:
    reference = tmp_path / "reference.png"
    output = tmp_path / "output.png"
    Image.new("RGB", (512, 512), (220, 210, 200)).save(reference)
    Image.new("RGB", (512, 512), (210, 205, 200)).save(output)
    inspector = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(),
        identity_metric_provider=_StaticIdentityMetric(0.90, 0.90),
    )

    report = inspector.inspect(_resolution(output), metadata=_identity_review_metadata(reference))

    assert report.score_card["same_person_readability"] == 0.86
    assert not {"identity_drift", "same_type_not_same_person"} & {
        str(issue.get("code") if isinstance(issue, dict) else issue.code) for issue in report.detected_issues
    }
    assert report.evidence["identity_metric"]["metadata"]["embedding_persisted"] is False


def test_doc96_mid_band_metric_emits_local_repair_signal(tmp_path) -> None:
    reference = tmp_path / "reference.png"
    output = tmp_path / "output.png"
    Image.new("RGB", (512, 512), (220, 210, 200)).save(reference)
    Image.new("RGB", (512, 512), (210, 205, 200)).save(output)
    inspector = VisionOutputInspector(
        vision_provider=_StaticVisionProvider(),
        identity_metric_provider=_StaticIdentityMetric(0.76, 0.80),
    )

    report = inspector.inspect(_resolution(output), metadata=_identity_review_metadata(reference))

    assert 0.72 <= report.score_card["same_person_readability"] < 0.82
    assert "identity_metric_below_commercial_target" in {
        str(issue.get("code") if isinstance(issue, dict) else issue.code) for issue in report.detected_issues
    }
    assert report.evidence["identity_metric"]["output_face_box"] == [0.25, 0.2, 0.5, 0.55]


def test_doc96_objective_identity_survives_multimodal_reviewer_outage(tmp_path) -> None:
    reference = tmp_path / "reference.png"
    output = tmp_path / "output.png"
    Image.new("RGB", (512, 512), (220, 210, 200)).save(reference)
    Image.new("RGB", (512, 512), (210, 205, 200)).save(output)
    inspector = VisionOutputInspector(
        vision_provider=_UnavailableVisionProvider(),
        identity_metric_provider=_StaticIdentityMetric(0.88, 0.86),
    )

    report = inspector.inspect(_resolution(output), metadata=_identity_review_metadata(reference))

    assert report.status == "manual_review"
    assert report.score_card["objective_identity_metric"] == 0.88
    assert report.score_card["same_person_readability"] >= 0.86
    assert report.evidence["identity_review_fusion"]["hard_gate_passed"] is True


def test_doc96_reference_conditioned_review_retries_transient_provider_error(tmp_path, monkeypatch) -> None:
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_inspector as inspector_module

    reference = tmp_path / "reference.png"
    output = tmp_path / "output.png"
    Image.new("RGB", (512, 512), (220, 210, 200)).save(reference)
    Image.new("RGB", (512, 512), (210, 205, 200)).save(output)
    provider = _FlakyVisionProvider()
    inspector = VisionOutputInspector(
        vision_provider=provider,
        identity_metric_provider=_StaticIdentityMetric(0.88, 0.86),
    )
    metadata = {**_identity_review_metadata(reference), "require_real_images": True}
    monkeypatch.setattr(inspector_module.time, "sleep", lambda _seconds: None)

    report = inspector.inspect(_resolution(output), metadata=metadata)

    assert provider.calls == 3
    assert report.status == "pass"
    assert report.score_card["same_person_readability"] >= 0.82


def test_doc96_local_repair_metadata_uses_failed_output_and_mask(tmp_path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (512, 512), (218, 208, 202)).save(buffer, format="PNG")
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_doc96",
        candidate_id="candidate_doc96",
        asset_id="asset_doc96",
        provider="openai_gpt_image",
        model="gpt-image-2",
        encoded_image=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )
    service = object.__new__(V3ProductApiService)
    service.output_store = store
    result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "inspections": [
                    {
                        "output_id": record.output_id,
                        "score_card": {
                            "prompt_owned_channel_obedience": 0.90,
                            "commercial_finish": 0.86,
                            "human_realism": 0.80,
                        },
                        "evidence": {
                            "identity_review_fusion": {"fused_identity_score": 0.77},
                            "identity_metric": {"output_face_box": [0.25, 0.18, 0.5, 0.58]},
                        },
                    }
                ]
            }
        }
    )

    metadata = service._identity_local_repair_metadata(  # noqa: SLF001
        result,
        attempt_index=1,
        reason_codes=["identity_metric_below_commercial_target"],
    )

    assert metadata["identity_local_repair_active"] is True
    assert metadata["identity_local_repair_source_output_id"] == record.output_id
    canvas = Path(metadata["identity_local_repair_canvas_path"])
    mask = Path(metadata["identity_local_repair_mask_path"])
    assert canvas.is_file() and mask.is_file()
    with Image.open(canvas) as canvas_image, Image.open(mask) as mask_image:
        assert canvas_image.size == mask_image.size
        assert mask_image.mode == "RGBA"


def test_doc96_post_retry_closeout_requires_strong_objective_mid_band(tmp_path) -> None:
    buffer = BytesIO()
    Image.new("RGB", (512, 512), (218, 208, 202)).save(buffer, format="PNG")
    store = V3GeneratedOutputStore(tmp_path / "outputs")
    record = store.save_base64_output(
        job_id="job_doc96_closeout",
        candidate_id="candidate_doc96_closeout",
        asset_id="asset_doc96_closeout",
        provider="openai_gpt_image",
        model="gpt-image-2",
        encoded_image=base64.b64encode(buffer.getvalue()).decode("ascii"),
    )
    service = object.__new__(V3ProductApiService)
    service.output_store = store

    def result(objective: float):
        return SimpleNamespace(
            metadata={
                "post_generation_review_package": {
                    "inspections": [
                        {
                            "output_id": record.output_id,
                            "score_card": {
                                "prompt_owned_channel_obedience": 0.68,
                                "commercial_finish": 0.83,
                                "human_realism": 0.72,
                            },
                            "detected_issues": [{"code": "source_hair_overinherited"}],
                            "evidence": {
                                "identity_review_fusion": {"fused_identity_score": 0.7908},
                                "identity_metric": {
                                    "calibrated_score": objective,
                                    "geometry_score": 0.8678,
                                    "output_face_box": [0.25, 0.18, 0.5, 0.58],
                                },
                            },
                        }
                    ]
                }
            }
        )

    metadata = service._identity_local_repair_metadata(  # noqa: SLF001
        result(0.8542),
        attempt_index=2,
        reason_codes=["identity_metric_below_commercial_target", "source_hair_overinherited"],
        post_retry_closeout=True,
    )
    rejected = service._identity_local_repair_metadata(  # noqa: SLF001
        result(0.79),
        attempt_index=2,
        reason_codes=["identity_metric_below_commercial_target"],
        post_retry_closeout=True,
    )

    assert metadata["identity_local_repair_stage"] == "post_retry_closeout"
    assert metadata["identity_local_repair_active"] is True
    assert rejected == {}


def test_doc96_sface_calibration_is_monotonic_and_not_threshold_gamed() -> None:
    values = [_calibrate_sface_cosine(value) for value in (0.2, 0.363, 0.48, 0.59, 0.65, 0.8)]
    assert values == sorted(values)
    assert values[1] == 0.5
    assert values[-1] == 0.97


def test_doc96_local_repair_must_improve_identity_without_quality_regression() -> None:
    service = object.__new__(V3ProductApiService)
    baseline = {
        "attempt_index": 0,
        "identity_local_repair": False,
        "identity_score": 0.77,
        "prompt_score": 0.90,
        "human_score": 0.82,
        "commercial_score": 0.86,
        "hard_gate_failures": ["identity_truth_not_respected"],
    }
    good_repair = {
        "attempt_index": 1,
        "identity_local_repair": True,
        "identity_score": 0.84,
        "prompt_score": 0.89,
        "human_score": 0.81,
        "commercial_score": 0.85,
        "hard_gate_failures": [],
    }
    weak_repair = {**good_repair, "identity_score": 0.80}
    damaging_repair = {**good_repair, "prompt_score": 0.84}

    assert service._identity_local_repair_candidate_accepted(good_repair, [baseline, good_repair]) is True  # noqa: SLF001
    assert service._identity_local_repair_candidate_accepted(weak_repair, [baseline, weak_repair]) is False  # noqa: SLF001
    assert service._identity_local_repair_candidate_accepted(damaging_repair, [baseline, damaging_repair]) is False  # noqa: SLF001


def test_doc96_framework_prompt_budget_preserves_user_direction_losslessly() -> None:
    provider = ProductionImageGenerationProvider(output_store=object())
    user_direction = "用户原始要求：保留全部动作、服装、环境、镜头、光影与情绪细节。" * 40
    raw = "\n".join(
        [
            "Create a camera-real image.",
            "Primary operation: identity-preserving portrait edit.",
            "Visual direction:",
            f"User request (verbatim): {user_direction}",
            "Reference channel policy:",
            "Current prompt owns its explicit visual channels.",
            *[f"Framework guidance {index}: " + ("same person realism detail " * 20) for index in range(120)],
            "Avoid: watermark; plastic skin; different person",
        ]
    )

    prompt = provider._provider_prompt_for_delivery(  # noqa: SLF001
        raw,
        protected_user_direction=user_direction,
    )
    audit = provider._provider_prompt_audit(prompt, user_direction)  # noqa: SLF001

    assert user_direction in prompt
    assert "Primary operation: identity-preserving portrait edit" in prompt
    assert "Current prompt owns its explicit visual channels" in prompt
    assert len(prompt) <= len(user_direction) + 6000
    assert audit["user_direction_lossless"] is True
    assert audit["internal_guidance_chars"] <= 6000
