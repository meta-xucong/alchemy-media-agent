from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    GeneratedOutputResolution,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    OpenAIVisionInspectionProvider,
)


def test_review_only_resume_projects_explicit_vision_timeout_before_existing_result_branch(
    monkeypatch,
) -> None:
    job_id = "job_review_timeout_projection"
    record = SimpleNamespace(
        job_id=job_id,
        status=ProductJobStatusValue.BLOCKED,
        planning_result=None,
        generation_result=SimpleNamespace(),
        request=SimpleNamespace(metadata={}),
    )

    class _Store:
        def get(self, requested_job_id: str):
            return record if requested_job_id == job_id else None

        def save(self, saved_record):
            return saved_record

    service = object.__new__(V3ProductApiService)
    service.job_store = _Store()
    monkeypatch.setattr(service, "_assert_photographer_profile_binding_immutable", lambda *_args: None)
    monkeypatch.setattr(service, "_is_professional_character_card_body_mcp_generation", lambda _record: False)

    captured: dict[str, object] = {}

    def fake_resume(current_record, generate_request, *_args, **_kwargs):
        captured["request_metadata"] = dict(generate_request.metadata)
        captured["record_metadata"] = dict(current_record.request.metadata)
        return SimpleNamespace(status=current_record.status)

    monkeypatch.setattr(service, "_resume_finalizing_generation_review", fake_resume)

    status = service.generate_asset_series(
        job_id,
        {
            "quality_mode": "strict",
            "metadata": {
                "_v3_resume_finalizing_review": True,
                "vision_inspection_timeout_seconds": 180,
            },
        },
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    assert captured["request_metadata"]["vision_inspection_timeout_seconds"] == 180
    assert captured["record_metadata"]["vision_inspection_timeout_seconds"] == 180


def test_openai_vision_provider_uses_review_timeout_for_upstream_request(
    tmp_path: Path,
    monkeypatch,
) -> None:
    image_path = tmp_path / "review.png"
    image = Image.new("RGB", (16, 16), color=(120, 140, 160))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    image_path.write_bytes(buffer.getvalue())

    captured: dict[str, object] = {}

    class _Responses:
        def create(self, **kwargs):  # noqa: ANN003
            captured.update(kwargs)
            return SimpleNamespace(output_text='{"status":"pass","confidence":0.95,"issue_codes":[]}')

    class _OpenAI:
        def __init__(self, **kwargs):  # noqa: ANN003
            self.responses = _Responses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=_OpenAI))
    monkeypatch.setenv("V3_VISION_INSPECTION_ENABLED", "true")
    monkeypatch.setenv("V3_VISION_INSPECTION_API_KEY", "test-key")
    monkeypatch.setenv("V3_VISION_INSPECTION_BASE_URL", "https://vision.example/v1")

    provider = OpenAIVisionInspectionProvider()
    payload = provider.inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_timeout_projection",
            project_id="project_timeout_projection",
            job_id="job_timeout_projection",
            candidate_id="candidate_timeout_projection",
            asset_id="asset_timeout_projection",
            output_id="output_timeout_projection",
            file_path=str(image_path),
            mime_type="image/png",
            width=16,
            height=16,
            status="ready",
        ),
        metadata={"vision_inspection_timeout_seconds": 180},
    )

    assert payload["status"] == "pass"
    assert captured["timeout"] == 180
