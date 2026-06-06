from __future__ import annotations

from app.main import app


def test_main_v2_routes_are_registered() -> None:
    registered_paths = {route.path for route in app.routes}
    expected_paths = {
        "/api/v2/health",
        "/api/v2/creative/runs",
        "/api/v2/creative/runs/{run_id}",
        "/api/v2/prompt-cases/search",
        "/api/v2/prompt-cases/{case_id}",
        "/api/v2/templates",
        "/api/v2/resource-providers",
        "/api/v2/resource-providers/{provider_id}/sync",
        "/api/v2/resource-providers/{provider_id}/sync-runs/{sync_run_id}",
        "/api/v2/image/jobs",
        "/api/v2/image/history",
        "/api/v2/image/jobs/{job_id}",
        "/api/v2/outputs/{output_id}/feedback",
    }
    assert expected_paths.issubset(registered_paths)
