from types import SimpleNamespace

from alchemy_creative_agent_3_0.app.product_api.contracts import ProductJobStatusValue
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import ecommerce_test_service


def test_general_safe_status_keeps_allowlisted_review_projection_only(monkeypatch) -> None:
    service = ecommerce_test_service()
    monkeypatch.setattr(service, "_project_mode_status_metadata", lambda _record: {})
    created = service.create_job({"user_input": "Create one reviewed general image."})
    record = service.job_store.get(created.job_id)
    assert record is not None
    record.request.metadata["doc270_general_source_activation_receipts"] = [{"state": "prompt_only"}]
    record.status = ProductJobStatusValue.GENERATED
    record.generation_result = SimpleNamespace(
        metadata={
            "post_generation_review_package": {
                "review_evidence_receipt_status": "complete",
                "inspections": [
                    {
                        "output_id": "output_safe",
                        "mode": "metadata_only",
                        "status": "fail_retryable",
                        "verification_state": "unverified",
                        "file_path": "D:/private/review.png",
                        "retry_patch": {"prompt_additions": ["private repair prompt"]},
                        "detected_issues": [
                            {
                                "code": "visible_text_artifact",
                                "message": "A safe public issue summary.",
                                "provider_reason": "private provider detail",
                            }
                        ],
                    }
                ],
            },
            "visual_auto_retry": {
                "enabled": True,
                "executed_count": 0,
                "max_attempts": 1,
                "records": [
                    {
                        "attempt_index": 1,
                        "status": "failed",
                        "reason_codes": ["visible_text_artifact"],
                        "retry_patch": {"negative_additions": ["private retry prompt"]},
                    }
                ],
            },
        }
    )

    public = service._doc270_general_phase3_safe_status(record)  # noqa: SLF001

    assert public is not None
    assert public.metadata["doc270_general_source_activation"] == {"state": "prompt_only"}
    assert public.metadata["post_generation_review"]["inspections"][0]["output_id"] == "output_safe"
    assert public.metadata["visual_auto_retry"]["records"] == [
        {"attempt_index": 1, "status": "failed", "reason_codes": ["visible_text_artifact"]}
    ]
    public_text = str(public.metadata)
    assert "file_path" not in public_text
    assert "retry_patch" not in public_text
    assert "private provider detail" not in public_text
    assert "private repair prompt" not in public_text
