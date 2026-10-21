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
    monkeypatch.setenv("V3_VISION_INSPECTION_API_KEY", "test-key")
    monkeypatch.setenv("V3_VISION_INSPECTION_BASE_URL", "https://vision.example/v1")
    monkeypatch.setenv("V3_VISION_INSPECTION_PROTOCOL", "chat_completions")

    provider = OpenAIVisionInspectionProvider()
    with pytest.raises(TimeoutError, match="request timed out"):
        provider.inspect(
            SimpleNamespace(file_path=str(image_path), mime_type="image/png"),
            metadata={"vision_inspection_timeout_seconds": 300},
        )


def test_live_worker_blocks_retry_even_with_a_free_global_slot(monkeypatch):
    release = threading.Event()
    slots = threading.BoundedSemaphore(2)
    calls = []

    class BlockingProvider:
        def available(self, *, force=False):
            return True

        def inspect(self, resolution, *, metadata):
            calls.append(resolution)
            release.wait(timeout=5)
            return {"status": "pass"}

    monkeypatch.setattr(vision_inspector, "_vision_inspection_semaphore", slots)
    monkeypatch.setattr(vision_inspector.time, "sleep", lambda _seconds: None)
    inspector = vision_inspector.VisionOutputInspector(vision_provider=BlockingProvider())
    monkeypatch.setattr(inspector, "_manual_report", lambda *args, **kw: kw["evidence_extra"])
    try:
        evidence = inspector._vision_model_report(
            SimpleNamespace(), mode="vision_model", metadata={
                "vision_inspection_timeout_seconds": 0.05,
                "vision_inspection_max_attempts": 2,
            },
        )
        assert len(calls) == 1
        assert evidence["provider_worker_stopped"] is False
        assert evidence["provider_review_attempts"] == 1
        assert evidence["provider_timeout_recovery_attempted"] is False
        assert evidence["provider_timeout_recovery_succeeded"] is False
    finally:
        release.set()
        # Wait for actual worker cleanup, not just the timed-out caller.
        for _ in range(2):
            assert slots.acquire(timeout=2)
        for _ in range(2):
            slots.release()


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


def test_thread_start_failure_returns_semaphore_slot(monkeypatch):
    slots = threading.BoundedSemaphore(2)
    monkeypatch.setattr(vision_inspector, "_vision_inspection_semaphore", slots)

    def fail_start(self):
        raise RuntimeError("cannot start thread")

    monkeypatch.setattr(threading.Thread, "start", fail_start)
    with pytest.raises(RuntimeError, match="cannot start thread"):
        vision_inspector._inspect_with_timeout(
            SimpleNamespace(), SimpleNamespace(), metadata={}, timeout_seconds=0.05,
        )
    assert slots.acquire(blocking=False)
    assert slots.acquire(blocking=False)
    assert not slots.acquire(blocking=False)


def test_concurrency_limit_and_failure_states_are_contract_values():
    assert vision_inspector._VISION_INSPECTION_CONCURRENCY_LIMIT == 1
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
