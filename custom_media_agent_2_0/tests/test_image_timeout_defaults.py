from app.config import Settings, load_settings


def test_v2_openai_image_timeout_defaults_to_at_least_five_minutes(monkeypatch):
    monkeypatch.delenv("V2_OPENAI_IMAGE_TIMEOUT_SECONDS", raising=False)

    assert Settings().openai_image_timeout_seconds == 600.0
    assert load_settings().openai_image_timeout_seconds >= 300.0
