import pytest
from fastapi.testclient import TestClient

from app import main
from app.services.favorites import LegacyFavoritesImportError
from app.storage.local import LegacyHistoryImportError


@pytest.mark.parametrize("kind", ["history", "favorites"])
def test_stored_import_failure_is_safe_operator_repair_response(monkeypatch, kind):
    secret = "synthetic-private-legacy-record"

    async def context(*_args, **_kwargs):
        return {"user_id": None, "is_admin": False}

    def fail(*_args, **_kwargs):
        if kind == "history":
            raise LegacyHistoryImportError(2, secret)
        raise LegacyFavoritesImportError(secret)

    monkeypatch.setattr(main, "_veyra_history_context", context)
    monkeypatch.setattr(main, "_list_image_history_sync", fail)
    response = TestClient(main.app).get("/v1/image/history")

    assert response.status_code == 503
    assert response.json()["detail"]["error_code"] == f"{kind}_import_blocked"
    assert response.json()["detail"]["retryable"] is False
    assert "Retry-After" not in response.headers
    assert secret not in response.text
