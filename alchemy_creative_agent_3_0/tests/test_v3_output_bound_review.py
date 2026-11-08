"""Output-specific review authority and advisory aesthetic findings."""

from copy import deepcopy

import pytest

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import VisionOutputInspector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import OutputQualityReviewMerger
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_provider
from alchemy_creative_agent_3_0.tests.test_v3_post_generation_vision_review import (
    _ready_resolution, _StaticVisionProvider, _png_base64,
)


@pytest.mark.parametrize("provider_status", ["pass", "warning"])
@pytest.mark.parametrize("scene", ["portrait", "product", "landscape"])
def test_usable_aesthetic_advice_does_not_trigger_generation(tmp_path, provider_status, scene):
    report = VisionOutputInspector(vision_provider=_StaticVisionProvider({
        "status": provider_status, "confidence": 0.9,
        "issue_codes": ["composition_mismatch", "weak_aesthetic_finish"],
        "summary": [f"The {scene} is polished and usable, with a minor framing suggestion."],
    })).inspect(_ready_resolution(tmp_path), metadata={"vision_inspection_mode": "vision_model"})
    assert report.status == "warning"
    assert not report.retryable
    signal = OutputQualityReviewMerger()._real_review_signal_package(
        job_id=report.job_id, project_id=report.project_id, inspections=[report],
    )
    assert signal.candidate_signals[0].recommended_action == "keep_with_warning"
    service = V3ProductApiService.__new__(V3ProductApiService)
    assert service._visual_retry_signal_from_real_review(signal.model_dump(mode="json")) == ([], {})


@pytest.mark.parametrize("status,extra", [
    ("fail_retryable", []),
    ("warning", ["visible_watermark"]),
    ("warning", ["identity_drift"]),
    ("warning", ["delivery_evidence_dimension_mismatch"]),
])
def test_aesthetic_advice_preserves_explicit_and_hard_failure(tmp_path, status, extra):
    report = VisionOutputInspector(vision_provider=_StaticVisionProvider({
        "status": status, "confidence": 0.95,
        "issue_codes": ["composition_mismatch", "weak_aesthetic_finish", *extra],
    })).inspect(_ready_resolution(tmp_path), metadata={"vision_inspection_mode": "vision_model"})
    assert report.status in {"fail_retryable", "fail_final"}


@pytest.mark.parametrize("enforced", [False, True])
def test_service_review_uses_each_durable_output_direction_including_retry(tmp_path, monkeypatch, enforced):
    base = _ready_resolution(tmp_path)
    directions = ["A wide full-body view with both hands visible.",
                  "An approved shoulder-up close-up with only one hand visible.",
                  "The repaired close-up retains one hand and improves the material finish."]
    resolutions = []
    for index, direction in enumerate(directions):
        output_id = f"output_{index}"
        asset_id = "asset_a" if index == 0 else "asset_b"
        resolutions.append(base.model_copy(update={
            "output_id": output_id, "asset_id": asset_id,
            "metadata": {"output_record": {
                "output_id": output_id, "asset_id": asset_id, "job_id": base.job_id,
                "metadata": {"final_provider_prompt": direction},
            }},
        }))
    contract = vision_provider.active_review_contract({})
    contract["enforced"] = enforced
    monkeypatch.setattr(vision_provider, "active_review_contract", lambda metadata: deepcopy(contract))

    class CaptureInspector:
        def inspect(self, resolution, *, metadata):
            return vision_provider._inspection_prompt(metadata)

    prompts = V3ProductApiService._inspect_outputs_in_order(
        CaptureInspector(), [(resolution, {}, None) for resolution in resolutions],
        base_metadata={
            "user_input": "Create complementary views while preserving the same subject and no text.",
            "reviewed_output_direction": {"prompt": "Client supplied fake direction."},
        },
    )
    for index, prompt in enumerate(prompts):
        assert directions[index] in prompt
        assert all(direction not in prompt for j, direction in enumerate(directions) if j != index)
        assert "Client supplied fake direction" not in prompt
        assert "global hard requirements" in prompt
        assert "rendering style" in prompt


def test_missing_durable_direction_does_not_use_request_override(tmp_path):
    class CaptureInspector:
        def inspect(self, resolution, *, metadata):
            return metadata.get("reviewed_output_direction")
    assert V3ProductApiService._inspect_outputs_in_order(
        CaptureInspector(), [(_ready_resolution(tmp_path), {}, None)],
        base_metadata={"reviewed_output_direction": {"prompt": "untrusted"}},
    ) == [None]


@pytest.mark.parametrize("advisory", [False, True])
def test_two_output_review_runs_only_required_generation_and_delivers_complete_set(tmp_path, monkeypatch, advisory):
    from alchemy_creative_agent_3_0.app.generation_router import GenerationRouter
    from alchemy_creative_agent_3_0.app.generation_router.providers import MockGenerationProvider
    from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
    from alchemy_creative_agent_3_0.app.product_api.output_resolver import GeneratedOutputResolver
    from alchemy_creative_agent_3_0.app.product_api.contracts import GenerateContinuation
    from alchemy_creative_agent_3_0.tests.test_v3_post_generation_vision_review import _service

    monkeypatch.setenv("ALCHEMY_RENDER_BRIDGE_PRIMARY_CONFIG", str(tmp_path / "absent-control.json"))
    store = V3GeneratedOutputStore(tmp_path / "outputs")

    class PersistedFixtureProvider(MockGenerationProvider):
        def __init__(self):
            self.requests = []

        def generate(self, request):
            self.requests.append(request)
            response = super().generate(request)
            candidate = response.candidates[0]
            saved = store.save_base64_output(
                job_id=request.metadata["job_id"], candidate_id=candidate.candidate_id,
                asset_id=candidate.asset_id, provider=self.provider_name, model="offline",
                encoded_image=_png_base64(), include_content_hash=False,
                metadata={"output_index": request.metadata["output_index"]},
            )
            response.candidates = [candidate.model_copy(update={
                "file_path": saved.file_path,
                "metadata": {**candidate.metadata, "output_id": saved.output_id,
                             "output_index": request.metadata["output_index"]},
            })]
            return response

    class PerOutputInspector(_StaticVisionProvider):
        def inspect(self, resolution, *, metadata=None):
            self.calls.append(resolution)
            second = resolution.metadata["output_record"]["metadata"]["output_index"] == 1
            retry = metadata.get("visual_auto_retry_active", False)
            failing = second and not retry
            return {
                "status": "warning" if advisory or not failing else "fail_retryable",
                "confidence": 0.95,
                "issue_codes": ["composition_mismatch", "weak_aesthetic_finish"] if failing else [],
                "human_naturalness_verdict": {"status": "pass", "issue_codes": []},
                "scores": {"overall": 0.6 if failing and not advisory else 0.95},
            }

    renderer = PersistedFixtureProvider()
    vision = PerOutputInspector({})
    service = _service(tmp_path, output_store=store, output_resolver=GeneratedOutputResolver(store),
                       vision_inspector=VisionOutputInspector(vision_provider=vision))
    service.scenario_runtime.generation_router = GenerationRouter(provider=renderer)
    mode_counts = []
    mode_review = service._mode_differentiation_review_for_result
    def capture_mode_review(**kwargs):
        mode_counts.append(len(kwargs["generation_result"].asset_pack.assets))
        return mode_review(**kwargs)
    monkeypatch.setattr(service, "_mode_differentiation_review_for_result", capture_mode_review)
    created = service.create_job({
        "user_input": "Create two complementary landscape views of the same mountain range.",
        "scenario_selection": {"scenario_id": "general_creative", "parameters": {"requested_image_count": 2}},
        "metadata": {"requested_image_count": 2},
    })
    # Model the existing server-issued Bridge identity binding, never a public
    # request override or a file checksum added by this regression.
    record = service.job_store.get(created.job_id)
    record.request.metadata["render_bridge_primary_no_image_sha"] = True
    service.job_store.save(record)
    service.generate_job_with_continuation(created.job_id, {"quality_mode": "standard"},
        continuation=GenerateContinuation(job_id=created.job_id, vision_inspection_mode="vision_model",
                                          max_visual_retry_attempts=1))
    result = service.job_store.get(created.job_id).generation_result
    assert result is not None
    assert vision.calls, [(row["status"], row["detected_issues"], row.get("evidence")) for row in result.metadata["post_generation_review_package"]["inspections"]]
    assert [request.metadata["output_index"] for request in renderer.requests] == ([0, 1] if advisory else [0, 1, 1])
    assert len(vision.calls) == (2 if advisory else 3)
    assert len(result.asset_pack.assets) == (2 if advisory else 3)
    assert mode_counts and set(mode_counts) == {2}
    delivery, output_ids, _ = service._public_final_delivery_projection(result)
    assert delivery["final_delivery_status"] == "ready"
    assert len(output_ids) == 2
    assert vision.calls[0].output_id in output_ids
    if not advisory:
        assert vision.calls[-1].output_id in output_ids
        assert vision.calls[1].output_id not in output_ids
        assert result.metadata["post_generation_review_package"]["review_evidence_receipt_status"] == "complete"
