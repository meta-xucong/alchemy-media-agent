from __future__ import annotations

from app.config import Settings


def test_v2_defaults_do_not_hide_live_provider_failures_with_mock_output() -> None:
    settings = Settings()

    assert settings.allow_mock_fallback is False


def test_mock_provider_remains_an_explicit_test_choice() -> None:
    settings = Settings(allow_mock_fallback=True)

    assert settings.allow_mock_fallback is True
