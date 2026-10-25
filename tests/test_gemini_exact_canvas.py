from app.providers.gemini_image import _supported_aspect_ratio

import pytest


@pytest.mark.parametrize("value,expected", [
    ("16:9", "16:9"), ("1536x864", "16:9"), ("1920x1080", "16:9"),
    ("9:16", "9:16"), ("7:3", "21:9"), ("42:18", "21:9"),
    ("1024x1536", "2:3"), ("4:1", None), ("2048x512", None),
    ("0x0", None), ("-1:2", None), ("auto", None), (None, None),
])
def test_exact_declared_ratio_only(value, expected):
    assert _supported_aspect_ratio(value) == expected
