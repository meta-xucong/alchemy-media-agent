import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.history_counts import HistoryCountIndexError


@pytest.mark.parametrize("endpoint", ["/api/v2/image/history", "/api/v2/veyra/history"])
def test_count_index_failure_is_sanitized_unavailable_not_empty(monkeypatch, endpoint):
    private_detail = "fixture-private-owner-path-and-payload"

    def fail(*args, **kwargs):
        raise HistoryCountIndexError(private_detail)

    monkeypatch.setattr(main, "list_image_history", fail)
    original = main.settings.veyra_auth_enabled
    object.__setattr__(main.settings, "veyra_auth_enabled", False)
    try:
        # No context manager: application lifespan/provider startup is not run.
        response = TestClient(main.app).get(endpoint)
    finally:
        object.__setattr__(main.settings, "veyra_auth_enabled", original)
    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == "history_index_unavailable"
    assert response.json()["detail"]["retryable"] is False
    assert "Retry-After" not in response.headers
    assert "items" not in response.json()
    assert private_detail not in response.text
