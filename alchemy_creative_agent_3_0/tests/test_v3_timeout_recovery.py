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
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    OpenAIVisionInspectionProvider,
)


def test_provider_consumes_inner_timeout_budget(monkeypatch):
    monkeypatch.delenv("V3_VISION_INSPECTION_TIMEOUT_SECONDS", raising=False)
    provider = OpenAIVisionInspectionProvider()
    assert provider._timeout({}) == 300
    assert provider._timeout({
        "_inner_timeout_seconds": 0.5,
        "vision_inspection_timeout_seconds": 90,
    }) == 0.5
    assert provider._timeout({"vision_inspection_timeout_seconds": 12}) == 12
    assert provider._timeout({"_inner_timeout_seconds": 300}) == 300
    assert provider._timeout({"_inner_timeout_seconds": 600}) == 300


def test_inspector_passes_full_300_second_per_request_budget():
    observed = {}

    class _Provider:
        def inspect(self, _resolution, *, metadata):
            observed.update(metadata)
            return {"status": "pass"}

    result = vision_inspector._inspect_with_timeout(
        _Provider(),
        SimpleNamespace(),
        metadata={},
        timeout_seconds=300,
    )

    assert result["status"] == "pass"
    assert observed["_inner_timeout_seconds"] == 300


def test_review_queue_waits_for_real_slot_without_inventing_provider_timeout(monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    slots = threading.BoundedSemaphore(1)
    slots.acquire()
    monkeypatch.setattr(vision_inspector, "_vision_inspection_semaphore", slots)
    provider = SimpleNamespace(inspect=lambda resolution, metadata: {"status": "pass"})
    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(vision_inspector._inspect_with_timeout,
            provider, SimpleNamespace(), metadata={}, timeout_seconds=0.05)
        try:
            time.sleep(0.08)
            assert not pending.done()
        finally:
            slots.release()
        assert pending.result(timeout=1) == {"status": "pass"}


def test_provider_preserves_sdk_timeout_as_timeout_error(tmp_path, monkeypatch):
    image_path = tmp_path / "review.png"
    image_path.write_bytes(b"not-decoded-by-the-fake-provider")

    class _ChatCompletions:
        def create(self, **_kwargs):
            raise RuntimeError("Request timed out.")

    class _OpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=_ChatCompletions())
            self.responses = SimpleNamespace()

    monkeypatch.setitem(__import__("sys").modules, "openai", SimpleNamespace(OpenAI=_OpenAI))
    monkeypatch.setenv("V3_VISION_INSPECTION_ENABLED", "true")
    monkeypatch.setenv("LLM_GATEWAY_API_KEY", "test-key")
    monkeypatch.setenv("LLM_GATEWAY_BASE_URL", "https://vision.example/v1")
    monkeypatch.setenv("V3_VISION_INSPECTION_PROTOCOL", "chat_completions")

    provider = OpenAIVisionInspectionProvider()
    with pytest.raises(TimeoutError, match="request timed out"):
        provider.inspect(
            SimpleNamespace(file_path=str(image_path), mime_type="image/png"),
            metadata={"vision_inspection_timeout_seconds": 300},
        )




def test_timeout_issues_only_one_provider_request(monkeypatch):
    calls = []

    class FailingProvider:
        def available(self, *, force=False):
            return True

        def inspect(self, resolution, *, metadata):
            calls.append(resolution)
            raise TimeoutError("provider deadline")

    monkeypatch.setattr(vision_inspector.time, "sleep", lambda _seconds: None)
    inspector = vision_inspector.VisionOutputInspector(vision_provider=FailingProvider())
    monkeypatch.setattr(inspector, "_manual_report", lambda *args, **kw: kw["evidence_extra"])
    evidence = inspector._vision_model_report(SimpleNamespace(), mode="vision_model", metadata={})
    assert len(calls) == 1
    assert evidence["provider_review_attempts"] == 1
    assert evidence["provider_timeout_recovery_attempted"] is False
    assert evidence["provider_timeout_recovery_succeeded"] is False


def test_provider_exception_returns_semaphore_slot(monkeypatch):
    slots = threading.BoundedSemaphore(2)
    monkeypatch.setattr(vision_inspector, "_vision_inspection_semaphore", slots)
    def fail(resolution, *, metadata):
        raise RuntimeError("provider failed")
    with pytest.raises(RuntimeError, match="provider failed"):
        vision_inspector._inspect_with_timeout(
            SimpleNamespace(inspect=fail), SimpleNamespace(), metadata={}, timeout_seconds=0.05,
        )
    assert slots.acquire(blocking=False)
    assert slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)


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




def test_timeout_does_not_retry_same_image(monkeypatch):
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

    monkeypatch.setattr(
        inspector,
        "_manual_report",
        lambda *args, **kwargs: captured.update(kwargs["evidence_extra"]) or "manual_review",
    )
    result = inspector._vision_model_report(SimpleNamespace(), mode="vision_model", metadata={})

    assert result == "manual_review"
    assert calls == 1
    assert captured["provider_review_attempts"] == 1
    assert captured["provider_timeout_recovery_attempted"] is False
    assert captured["provider_timeout_recovery_succeeded"] is False


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
    assert captured["provider_review_attempts"] == 1
