"""Regression coverage for the recovered Doc350/353 behavior, without jobs."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
import threading
import time

import pytest

from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode.service import V3ProjectModeService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_inspector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.identity_metric import SFaceIdentityMetricProvider


def test_canonical_mixed_attempt_winners_survive_project_annotation():
    service = V3ProjectModeService.__new__(V3ProjectModeService)
    def output(identity, attempt, preferred):
        return SimpleNamespace(output_id=identity, created_at=str(attempt),
            download_url=f"/media/{identity}", preview_url="", thumbnail_url="",
            metadata={"retry_attempt": attempt, "requested_image_count": 2,
                      "delivery_preferred_output": preferred})
    records = [output("original-winner", 0, True), output("unused-original", 0, False),
               output("retry-winner", 1, True), output("unused-retry", 1, False)]
    annotations = service._delivery_annotations_for_records(
        records, final_output_ids={"original-winner", "retry-winner"},
    )
    assert annotations["original-winner"]["delivery_state"] == "final_delivery"
    assert annotations["retry-winner"]["delivery_state"] == "final_delivery"
    assert annotations["original-winner"]["retry_superseded"] is False
    assert annotations["unused-original"]["delivery_state"] == "superseded"
    assert annotations["unused-retry"]["delivery_state"] == "superseded"


@pytest.mark.parametrize("limit", [1, 2, 99])
def test_review_scheduler_bounds_workers_and_preserves_result_order(limit):
    lock = threading.Lock()
    active = maximum = 0
    first_two = threading.Event()
    class Inspector:
        max_concurrent_inspections = limit
        def inspect(self, resolution, *, metadata):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
                if active == 2:
                    first_two.set()
            if limit > 1:
                assert first_two.wait(2)
            time.sleep(0.02 if resolution == 0 else 0.005)
            with lock:
                active -= 1
            return (resolution, metadata["evidence"], metadata["frozen_output_review_contract"])
    inputs = [(i, {"evidence": i}, {"role": i}) for i in range(4)]
    result = V3ProductApiService._inspect_outputs_in_order(Inspector(), inputs, base_metadata={})
    assert result == [(i, i, {"role": i}) for i in range(4)]
    assert maximum == min(limit, 2)
    assert active == 0


def test_provider_wait_owns_live_call_until_completion(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(vision_inspector, "_vision_inspection_semaphore", slots)
    entered, release = threading.Event(), threading.Event()
    def inspect(_resolution, *, metadata):
        assert metadata["_inner_timeout_seconds"] == 0.05
        entered.set()
        assert release.wait(2)
        return {"status": "pass"}
    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(vision_inspector._inspect_with_timeout,
            SimpleNamespace(inspect=inspect), SimpleNamespace(), metadata={}, timeout_seconds=0.05)
        try:
            assert entered.wait(1)
            time.sleep(0.08)
            assert not pending.done(), "caller must still own the provider call"
            assert not slots.acquire(blocking=False)
        finally:
            release.set()
        assert pending.result(timeout=1) == {"status": "pass"}
    assert slots.acquire(blocking=False)
    slots.release()


def test_provider_error_releases_its_slot_and_keeps_transport_receipt(monkeypatch):
    slots = threading.BoundedSemaphore(1)
    monkeypatch.setattr(vision_inspector, "_vision_inspection_semaphore", slots)
    error = TimeoutError("transport stopped")
    error.vision_route_receipt = {"model_attempts": [{"outcome": "failed"}]}
    def inspect(_resolution, *, metadata):
        raise error
    with pytest.raises(vision_inspector.VisionInspectionTimeoutError) as captured:
        vision_inspector._inspect_with_timeout(SimpleNamespace(inspect=inspect), SimpleNamespace(),
            metadata={}, timeout_seconds=0.05)
    assert captured.value.worker_stopped is True
    assert captured.value.vision_route_receipt == error.vision_route_receipt
    assert slots.acquire(blocking=False)
    slots.release()


def test_native_detection_waits_for_actual_completion(tmp_path, monkeypatch):
    monkeypatch.setenv("V3_IDENTITY_METRIC_OPERATION_TIMEOUT_SECONDS", "0.05")
    provider = SFaceIdentityMetricProvider(model_dir=tmp_path)
    entered, release = threading.Event(), threading.Event()
    def detect(_image):
        entered.set()
        assert release.wait(2)
        return None, ["face"]
    provider._detector = SimpleNamespace(setInputSize=lambda size: None, detect=detect)
    with ThreadPoolExecutor(max_workers=1) as worker:
        pending = worker.submit(provider._detect, SimpleNamespace(shape=(32, 32)))
        try:
            assert entered.wait(1)
            time.sleep(0.08)
            assert not pending.done()
        finally:
            release.set()
        assert pending.result(timeout=1) == ["face"]


def test_native_model_initialization_is_serialized(tmp_path, monkeypatch):
    calls = []
    def create(*args):
        calls.append(args)
        time.sleep(0.02)
        return object()
    monkeypatch.setitem(__import__("sys").modules, "cv2", SimpleNamespace(
        FaceDetectorYN=SimpleNamespace(create=create), FaceRecognizerSF=SimpleNamespace(create=create)))
    provider = SFaceIdentityMetricProvider(model_dir=tmp_path)
    with ThreadPoolExecutor(max_workers=2) as workers:
        list(workers.map(lambda _: provider._load(), range(2)))
    assert len(calls) == 2
