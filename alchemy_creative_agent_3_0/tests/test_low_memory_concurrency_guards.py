"""Regression tests for the low-memory process-wide concurrency guards."""

from __future__ import annotations

from typing import Any

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import vision_inspector
from app import main


def test_v3_generation_executor_uses_single_worker_by_default() -> None:
    assert main._V3_BACKGROUND_GENERATION_WORKERS == 1
    assert main._v3_generation_executor._max_workers == 1


def test_worker_count_parser_has_safe_bounds(monkeypatch) -> None:
    monkeypatch.delenv("TEST_WORKERS", raising=False)
    assert main._positive_worker_count("TEST_WORKERS", default=1) == 1

    monkeypatch.setenv("TEST_WORKERS", "3")
    assert main._positive_worker_count("TEST_WORKERS", default=1) == 3

    monkeypatch.setenv("TEST_WORKERS", "0")
    assert main._positive_worker_count("TEST_WORKERS", default=1) == 1

    monkeypatch.setenv("TEST_WORKERS", "not-a-number")
    assert main._positive_worker_count("TEST_WORKERS", default=1) == 1


def test_vision_review_defaults_to_one_and_never_exceeds_two(monkeypatch) -> None:
    monkeypatch.delenv("V3_VISION_INSPECTION_CONCURRENCY", raising=False)
    assert vision_inspector._vision_inspection_concurrency_limit() == 1

    monkeypatch.setenv("V3_VISION_INSPECTION_CONCURRENCY", "2")
    assert vision_inspector._vision_inspection_concurrency_limit() == 2

    monkeypatch.setenv("V3_VISION_INSPECTION_CONCURRENCY", "99")
    assert vision_inspector._vision_inspection_concurrency_limit() == 2

    monkeypatch.setenv("V3_VISION_INSPECTION_CONCURRENCY", "invalid")
    assert vision_inspector._vision_inspection_concurrency_limit() == 1


def test_queued_generation_does_not_start_watchdog_before_worker_claim(monkeypatch) -> None:
    events: list[str] = []
    watchdog_calls: list[tuple[str, str, str, float | None]] = []

    class Handler:
        def mark_project_job_generating(self, project_id: str, job_id: str, **kwargs: Any) -> dict:
            events.append("claim")
            return {}

        def post_project_job_generate(self, *args: Any, **kwargs: Any) -> dict:
            events.append("generate")
            return {}

    monkeypatch.setattr(main, "v3_route_handlers", Handler())
    monkeypatch.setattr(
        main,
        "_start_v3_project_generation_watchdog",
        lambda project_id, job_id, attempt_id, timeout: watchdog_calls.append(
            (project_id, job_id, attempt_id, timeout)
        ),
    )

    main._run_v3_project_generation_background(
        "project_claim",
        "job_claim",
        {"quality_mode": "standard"},
        "attempt_claim",
        timeout_seconds=255.0,
        timeout_owner="direct_provider",
    )

    assert events == ["claim", "generate"]
    assert watchdog_calls == [("project_claim", "job_claim", "attempt_claim", 255.0)]


def test_second_generation_is_queued_without_a_running_deadline(monkeypatch) -> None:
    class SingleWorkerProbe:
        def __init__(self) -> None:
            self.active: tuple[Any, tuple[Any, ...]] | None = None
            self.queued: list[tuple[Any, tuple[Any, ...]]] = []

        def submit(self, fn: Any, *args: Any) -> object:
            entry = (fn, args)
            if self.active is None:
                self.active = entry
            else:
                self.queued.append(entry)
            return object()

    probe = SingleWorkerProbe()
    monkeypatch.setattr(main, "_v3_generation_executor", probe)
    keys = [("project_queue", "job_one"), ("project_queue", "job_two")]
    try:
        assert main._start_v3_project_generation_background(keys[0][0], keys[0][1], {"quality_mode": "standard"})
        assert main._start_v3_project_generation_background(keys[1][0], keys[1][1], {"quality_mode": "standard"})
        assert probe.active is not None
        assert len(probe.queued) == 1
        assert len(main._v3_background_generation_jobs) >= 2
        # No worker has claimed either job in this probe, so neither has a
        # watchdog and the second job remains queued rather than generating.
        assert main._v3_background_generation_watchdogs.get("project_queue:job_two") is None
    finally:
        with main._v3_background_generation_jobs_lock:
            for project_id, job_id in keys:
                main._v3_background_generation_jobs.pop(f"{project_id}:{job_id}", None)
