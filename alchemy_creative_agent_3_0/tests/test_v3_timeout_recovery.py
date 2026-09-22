"""Batch 4 Tests: D02 + D03 Timeout Recovery
Tests timeout retry mechanism with concurrency control.

Verification targets:
- R8: Timeout retry logic exists (concurrency control added)
- R9: Concurrency limit enforced (semaphore implementation)
- R9b: provider_timeout is retryable (_retry_eligible logic)
"""
from __future__ import annotations

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import (
    OutputQualityReviewMerger,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    VisualInspectionReport,
)


def test_concurrency_semaphore_exists():
    """R9: Verify concurrency control semaphore is defined"""
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_inspector

    # D02: Semaphore should exist
    assert hasattr(vision_inspector, '_vision_inspection_semaphore')
    assert hasattr(vision_inspector, '_VISION_INSPECTION_CONCURRENCY_LIMIT')
    assert vision_inspector._VISION_INSPECTION_CONCURRENCY_LIMIT == 2


def test_provider_timeout_retry_eligible_with_detected_issues():
    """R9b: provider_timeout in detected_issues makes inspection retryable"""
    # D03: Create inspection with provider_timeout in detected_issues
    inspection = VisualInspectionReport(
        inspection_id="test_timeout_1",
        output_id="output_1",
        status="manual_review",  # D03: status is manual_review for timeout
        verification_state="verification_failed",  # D13: new state for timeout
        retryable=True,
        detected_issues=[
            {"code": "provider_timeout", "message": "Vision inspection timed out"}
        ],
    )

    # Test retry eligibility
    merger = OutputQualityReviewMerger()
    eligible = merger._retry_eligible(inspection)

    assert eligible is True, "provider_timeout should be retryable"


def test_provider_timeout_not_retryable_when_retryable_false():
    """R9b: provider_timeout with retryable=False is not eligible"""
    inspection = VisualInspectionReport(
        inspection_id="test_timeout_2",
        output_id="output_2",
        status="manual_review",
        verification_state="verification_failed",
        retryable=False,  # Explicitly not retryable
        detected_issues=[
            {"code": "provider_timeout", "message": "Vision inspection timed out"}
        ],
    )

    merger = OutputQualityReviewMerger()
    eligible = merger._retry_eligible(inspection)

    assert eligible is False, "provider_timeout with retryable=False should not be eligible"


def test_manual_review_without_timeout_not_retryable():
    """R9b: manual_review without provider_timeout is not retryable"""
    inspection = VisualInspectionReport(
        inspection_id="test_manual_1",
        output_id="output_3",
        status="manual_review",
        verification_state="unverified",
        retryable=True,
        detected_issues=[
            {"code": "hard_semantic_contract_unverified", "message": "Requires human review"}
        ],
    )

    merger = OutputQualityReviewMerger()
    eligible = merger._retry_eligible(inspection)

    assert eligible is False, "manual_review without provider_timeout should not be retryable"


def test_fail_retryable_still_works():
    """R9b: Original fail_retryable logic still works"""
    inspection = VisualInspectionReport(
        inspection_id="test_fail_1",
        output_id="output_4",
        status="fail_retryable",
        verification_state="verified",
        retryable=True,
        detected_issues=[
            {"code": "watermark_detected", "message": "Detected watermark"}
        ],
    )

    merger = OutputQualityReviewMerger()
    eligible = merger._retry_eligible(inspection)

    assert eligible is True, "fail_retryable with verified should be retryable"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
