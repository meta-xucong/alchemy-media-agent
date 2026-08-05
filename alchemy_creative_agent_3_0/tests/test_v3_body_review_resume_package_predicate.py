from __future__ import annotations

from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService


def test_existing_checkpointed_body_result_reenters_review_without_submitted_projection(
    monkeypatch,
) -> None:
    job_id = "job_body_checkpointed_review_resume"
    record = SimpleNamespace(
        job_id=job_id,
        status=ProductJobStatusValue.GENERATED,
        planning_result=SimpleNamespace(generation_plans=[]),
        generation_result=SimpleNamespace(
            metadata={
                "post_generation_review_package": {
                    "inspections": [
                        {
                            "status": "manual_review",
                            "verification_state": "unverified",
                            "issue_codes": [{"code": "provider_timeout"}],
                        }
                    ]
                }
            }
        ),
        request=SimpleNamespace(
            metadata={
                "professional_character_card_preparation": True,
                "professional_character_card_stage": "body_silhouette",
                "professional_character_card_slot": "body.rear_full",
                "generation_channel": "mcp",
                "mcp_operation_id": "visual_asset_body:body_silhouette:body.rear_full:2",
                "mcp_materialization": {
                    "handoff_id": "mcp_handoff_body_checkpointed",
                    "status": "job_checkpointed",
                    "generation_channel": "mcp",
                },
            }
        ),
    )

    class _Store:
        def get(self, requested_job_id: str):
            return record if requested_job_id == job_id else None

        def save(self, saved_record):
            return saved_record

    service = object.__new__(V3ProductApiService)
    service.job_store = _Store()
    monkeypatch.setattr(service, "_assert_photographer_profile_binding_immutable", lambda *_args: None)
    monkeypatch.setattr(service, "_is_professional_character_card_body_mcp_generation", lambda _record: True)
    monkeypatch.setattr(
        service,
        "_blocked_existing_submitted_body_mcp_projection",
        lambda _record, _exc: SimpleNamespace(status=ProductJobStatusValue.BLOCKED),
    )

    calls: list[dict[str, object]] = []

    def fake_resume(current_record, generate_request, *_args, **_kwargs):
        calls.append(
            {
                "job_id": current_record.job_id,
                "request_metadata": dict(generate_request.metadata),
            }
        )
        return SimpleNamespace(status=ProductJobStatusValue.GENERATED)

    monkeypatch.setattr(service, "_resume_finalizing_generation_review", fake_resume)

    status = service.generate_asset_series(
        job_id,
        {
            "quality_mode": "strict",
            "metadata": {"_v3_resume_finalizing_review": True},
        },
    )

    assert status.status == ProductJobStatusValue.GENERATED
    assert len(calls) == 1
    assert calls[0]["job_id"] == job_id
