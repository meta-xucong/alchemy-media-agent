"""Regression tests for vision provider timeout recovery."""

from __future__ import annotations

import threading
import time
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_inspector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.contracts import (
    VisualInspectionReport,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.quality_review import (
    OutputQualityReviewMerger,
)


def test_concurrency_limit_and_failure_states_are_contract_values():
    assert vision_inspector._VISION_INSPECTION_CONCURRENCY_LIMIT == 2
    for state in ("verification_failed", "verification_skipped"):
        report = VisualInspectionReport(
            inspection_id=f"state-{state}",
            verification_state=state,
        )
        assert report.verification_state == state


def test_timeout_manual_review_is_not_auto_retry_eligible():
    """Exhausted provider retries require manual confirmation in the review layer."""
    inspection = VisualInspectionReport(
        inspection_id="timeout-review",
        status="manual_review",
        verification_state="verification_failed",
        retryable=True,
        detected_issues=[{"code": "provider_timeout"}],
    )
    assert OutputQualityReviewMerger()._retry_eligible(inspection) is False


def test_timeout_worker_keeps_semaphore_until_provider_returns():
    started = threading.Event()
    release = threading.Event()
    errors: list[BaseException] = []

    class BlockingProvider:
        def inspect(self, resolution, *, metadata):
            started.set()
            release.wait(timeout=2)
            return {"status": "pass"}

    provider = BlockingProvider()
    resolution = SimpleNamespace()

    def first_call():
        try:
            vision_inspector._inspect_with_timeout(
                provider, resolution, metadata={}, timeout_seconds=0.05
            )
        except BaseException as exc:
            errors.append(exc)

    workers = [threading.Thread(target=first_call) for _ in range(2)]
    for worker in workers:
        worker.start()
    assert started.wait(timeout=1)
    time.sleep(0.15)

    with pytest.raises(vision_inspector.VisionInspectionTimeoutError) as caught:
        vision_inspector._inspect_with_timeout(
            provider, resolution, metadata={}, timeout_seconds=0.05
        )
    assert "queue is full" in str(caught.value)
    assert len(errors) == 2
    assert all(isinstance(error, vision_inspector.VisionInspectionTimeoutError) for error in errors)

    release.set()
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()


def test_recovery_succeeded_only_after_timeout_then_success(monkeypatch):
    calls = 0

    class FlakyProvider:
        provider_name = "test"

        def available(self, *, force=False):
            return True

        def inspect(self, resolution, *, metadata):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise TimeoutError("first attempt timed out")
            return {"status": "pass"}

    captured: dict[str, object] = {}
    inspector = vision_inspector.VisionOutputInspector(vision_provider=FlakyProvider())

    def fake_from_provider_payload(resolution, payload, **kwargs):
        captured.update(kwargs)
        return "report"

    monkeypatch.setattr(inspector, "_from_provider_payload", fake_from_provider_payload)
    monkeypatch.setattr(vision_inspector.time, "sleep", lambda _seconds: None)
    result = inspector._vision_model_report(
        SimpleNamespace(), mode="vision_model", metadata={"vision_inspection_max_attempts": 2}
    )

    assert result == "report"
    assert calls == 2
    assert captured["provider_timeout_recovery_attempted"] is True
    assert captured["provider_timeout_recovery_succeeded"] is True


def test_first_attempt_success_is_not_recovery(monkeypatch):
    class HealthyProvider:
        provider_name = "test"

        def available(self, *, force=False):
            return True

        def inspect(self, resolution, *, metadata):
            return {"status": "pass"}

    captured: dict[str, object] = {}
    inspector = vision_inspector.VisionOutputInspector(vision_provider=HealthyProvider())
    monkeypatch.setattr(
        inspector,
        "_from_provider_payload",
        lambda resolution, payload, **kwargs: captured.update(kwargs) or "report",
    )

    assert inspector._vision_model_report(
        SimpleNamespace(), mode="vision_model", metadata={"vision_inspection_max_attempts": 2}
    ) == "report"
    assert captured["provider_timeout_recovery_attempted"] is False
    assert captured["provider_timeout_recovery_succeeded"] is False
