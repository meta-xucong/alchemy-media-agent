from types import SimpleNamespace

import pytest

import app.main as main_module


class _RejectingExecutor:
    def submit(self, *args, **kwargs):
        raise RuntimeError("executor unavailable")


class _BackgroundHandlers:
    def __init__(self) -> None:
        self.generating = []
        self.failed = []

    def mark_project_job_generating(self, project_id, job_id, **kwargs):
        self.generating.append((project_id, job_id, kwargs))
        return {}

    def mark_project_job_generation_worker_failed(self, project_id, job_id, **kwargs):
        self.failed.append((project_id, job_id, kwargs))
        return {}


def test_generation_executor_rejection_closes_durable_attempt(monkeypatch):
    handlers = _BackgroundHandlers()
    project_id = "project-doc284-submit-failure"
    job_id = "job-doc284-submit-failure"
    key = f"{project_id}:{job_id}"
    monkeypatch.setattr(main_module, "v3_route_handlers", SimpleNamespace(
        mark_project_job_generating=handlers.mark_project_job_generating,
        mark_project_job_generation_worker_failed=handlers.mark_project_job_generation_worker_failed,
    ))
    monkeypatch.setattr(main_module, "_v3_generation_executor", _RejectingExecutor())
    monkeypatch.setattr(main_module, "_v3_background_generation_timeout_plan", lambda job_id, payload: (None, None))

    with pytest.raises(RuntimeError, match="executor unavailable"):
        main_module._start_v3_project_generation_background(project_id, job_id, {"metadata": {}})

    assert len(handlers.generating) == 1
    assert len(handlers.failed) == 1
    assert handlers.failed[0][0:2] == (project_id, job_id)
    assert handlers.failed[0][2]["failure_code"] == "background_generation_worker_error"
    assert key not in main_module._v3_background_generation_jobs
    assert key not in main_module._v3_background_generation_watchdogs
