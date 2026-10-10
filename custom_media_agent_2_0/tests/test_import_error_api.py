import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.favorites import LegacyFavoritesImportError
from app.services.image_history import LegacyHistoryImportError


@pytest.mark.parametrize("kind", ["history", "favorites"])
def test_stored_import_failure_is_safe_operator_repair_response(monkeypatch, kind):
    secret = "synthetic-private-legacy-record"
    error_type = LegacyHistoryImportError if kind == "history" else LegacyFavoritesImportError

    def fail(*_args, **_kwargs):
        raise error_type(secret)

    monkeypatch.setattr(main, "list_image_history", fail)
    original = main.settings.veyra_auth_enabled
    object.__setattr__(main.settings, "veyra_auth_enabled", False)
    try:
        response = TestClient(main.app).get("/api/v2/image/history")
    finally:
        object.__setattr__(main.settings, "veyra_auth_enabled", original)

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == f"{kind}_import_blocked"
    assert response.json()["detail"]["retryable"] is False
    assert "Retry-After" not in response.headers
    assert secret not in response.text
