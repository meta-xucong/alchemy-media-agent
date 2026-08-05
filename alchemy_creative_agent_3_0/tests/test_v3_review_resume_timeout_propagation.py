from __future__ import annotations

from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService


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
