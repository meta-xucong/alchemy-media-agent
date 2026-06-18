from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


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


def test_default_cors_allows_local_frontend_ports() -> None:
    assert "http://127.0.0.1:8017" in settings.cors_allow_origins
    assert "http://localhost:8017" in settings.cors_allow_origins
    assert "http://127.0.0.1:8027" in settings.cors_allow_origins
    assert "http://localhost:8027" in settings.cors_allow_origins


def test_v2_cors_preflight_allows_local_8027_frontend() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v2/health",
        headers={
            "Origin": "http://127.0.0.1:8027",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:8027"
    assert response.headers["access-control-allow-credentials"] == "true"
