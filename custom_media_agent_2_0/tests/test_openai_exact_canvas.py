from types import SimpleNamespace

import pytest

from app.providers.images import openai_gpt_image_2 as provider


@pytest.fixture(autouse=True)
def official_image2(monkeypatch):
    monkeypatch.setattr(provider, "settings", SimpleNamespace(
        openai_base_url=None, openai_image_model="gpt-image-2",
    ))


def plan(value, key="size"):
    return SimpleNamespace(provider_parameters={key: value})


@pytest.mark.parametrize("requested,expected", [
    ("16:9", "1536x864"), ("9:16", "864x1536"),
    ("4:3", "1536x1152"), ("3:4", "1152x1536"),
    ("1536x864", "1536x864"), ("3840x2160", "3840x2160"),
    ("2160x3840", "2160x3840"), ("1024x1024", "1024x1024"),
])
def test_exact_supported_canvas(requested, expected):
    assert provider._size(plan(requested)) == expected
    assert provider._size(plan(requested, "aspect_ratio")) == expected


@pytest.mark.parametrize("requested", [
    "1920x1080", "4096x2048", "512x512", "16x1600", "3840x3840",
    "garbage", "21:1", "0x1024", "auto", "default",
])
def test_unsupported_canvas_uses_native_default_without_approximation(requested):
    assert provider._size(plan(requested)) is None
    assert "size" not in provider._openai_image_kwargs(plan(requested))


@pytest.mark.parametrize("model", ["gpt-image-1", "gpt-image-1.5"])
def test_legacy_models_never_approximate_wide_canvas(model):
    provider.settings.openai_image_model = model
    assert provider._size(plan("16:9")) is None
    assert provider._size(plan("1536x864")) is None
    assert provider._size(plan("3:2")) == "1536x1024"
    assert "custom_dimensions" not in provider._canvas_capabilities()["sizes"]


def test_configured_compatible_gateway_keeps_custom_canvas_contract():
    provider.settings.openai_base_url = "https://gateway.example/v1"
    assert provider._size(plan("16:9")) == "1536x864"
    assert provider._size(plan("1024x1536")) == "1024x1536"
    assert "custom_size" in provider._canvas_capabilities()


def test_official_api_host_and_limits():
    provider.settings.openai_base_url = "https://api.openai.com/v1"
    assert provider._size(plan("16:9")) == "1536x864"
    limits = provider._canvas_capabilities()["custom_size"]
    assert limits["edge_multiple"] == 16
    assert limits["min_pixels"] == 655360
    assert "min_width" not in limits
