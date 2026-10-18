from app.config import Settings


def test_v1_image_request_timeout_default_is_at_least_five_minutes():
    assert Settings().openai_image_request_timeout_seconds >= 300.0
