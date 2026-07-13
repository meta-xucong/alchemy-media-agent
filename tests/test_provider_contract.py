import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.providers.base import (
    ProviderCapabilityMismatchError,
    ProviderNotConfiguredError,
    ProviderRateLimitError,
    ProviderRuntimeError,
)
import app.providers.doubao_image as doubao_image_provider
import app.providers.gemini_image as gemini_image_provider
import app.providers.openai_image as openai_image_provider
from app.providers.registry import registry
from app.schemas import ImageGenerationRequest, ImagePromptPlan
from app.config import openai_sdk_client_kwargs, settings
from app.services.prompting import build_prompt_plan
from app.services.work_intensity import apply_work_intensity
from app.storage import media_store


def test_openai_image_provider_capabilities():
    caps = asyncio.run(registry.image("openai_gpt_image").capabilities())
    assert caps.provider == "openai_gpt_image"
    assert "generate" in caps.operations
    assert "edit" in caps.operations
    assert caps.models == ["gpt-image-2"]
    assert "custom_dimensions" in caps.limits["sizes"]
    assert caps.limits["custom_size"]["max_width"] == 3840
    assert caps.limits["qualities"] == ["auto", "low", "medium", "high"]


def test_openai_image_provider_cost_uses_runtime_model():
    estimate = asyncio.run(
        registry.image("openai_gpt_image").estimate_cost(
            ImageGenerationRequest(prompt_plan=ImagePromptPlan(main_subject="咖啡海报", count=1))
        )
    )
    assert estimate.provider == "openai_gpt_image"
    assert estimate.model == "gpt-image-2"


def test_openai_image_provider_closes_async_client_after_generate(monkeypatch):
    provider = registry.image("openai_gpt_image")
    original_key = settings.openai_api_key
    original_base_url = settings.openai_base_url
    closed = {"value": False}
    captured = {}

    class FakeImages:
        async def generate(self, **kwargs):
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class FakeAsyncOpenAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)
            self.images = FakeImages()

        async def close(self):
            closed["value"] = True

    try:
        settings.openai_api_key = "sk-test"
        settings.openai_base_url = "https://aiself.example.test/v1"
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeAsyncOpenAI))
        asyncio.run(provider.generate(ImageGenerationRequest(prompt_plan=ImagePromptPlan(main_subject="test", count=1))))
    finally:
        settings.openai_api_key = original_key
        settings.openai_base_url = original_base_url
        sys.modules.pop("openai", None)
        openai_image_provider._openai_image_rate_limiter.reset()

    assert closed["value"] is True
    assert captured["max_retries"] == 0


def test_v3_threaded_handler_does_not_block_event_loop():
    from app.main import _run_v3_handler_threaded

    async def probe():
        def slow_handler():
            time.sleep(0.15)
            return {"ok": True}

        task = asyncio.create_task(_run_v3_handler_threaded(slow_handler))
        await asyncio.sleep(0.02)
        loop_was_free = not task.done()
        result = await task
        return loop_was_free, result

    loop_was_free, result = asyncio.run(probe())

    assert loop_was_free is True
    assert result == {"ok": True}


def test_doubao_image_provider_generates_via_openai_compatible_endpoint(monkeypatch):
    provider = registry.image("doubao_image")
    captured = {}
    original_key = settings.doubao_image_api_key
    original_base_url = settings.doubao_image_base_url
    original_model = settings.doubao_image_model

    class FakeResponse:
        status_code = 200
        text = "{}"

        def json(self):
            return {"data": [{"b64_json": base64.b64encode(b"fake-png").decode("ascii"), "size": "1024x1024"}]}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    try:
        settings.doubao_image_api_key = "sk-doubao-test"
        settings.doubao_image_base_url = "https://aiself.example.test/v1"
        settings.doubao_image_model = "doubao-seedream-4-0-250828"
        monkeypatch.setattr(doubao_image_provider.httpx, "AsyncClient", FakeAsyncClient)

        result = asyncio.run(
            provider.generate(
                ImageGenerationRequest(
                    prompt_plan=ImagePromptPlan(
                        main_subject="精品咖啡海报",
                        count=1,
                        size="1024x1024",
                        quality="high",
                    )
                )
            )
        )
    finally:
        settings.doubao_image_api_key = original_key
        settings.doubao_image_base_url = original_base_url
        settings.doubao_image_model = original_model

    assert captured["url"] == "https://aiself.example.test/v1/images/generations"
    assert captured["headers"]["Authorization"] == "Bearer sk-doubao-test"
    assert captured["payload"]["model"] == "doubao-seedream-4-0-250828"
    assert captured["payload"]["response_format"] == "b64_json"
    assert result.provider == "doubao_image"
    assert result.model == "doubao-seedream-4-0-250828"
    assert result.outputs[0]["format"] == "png"
    assert result.raw_response_summary["supports_reference_images"] is False


def test_doubao_image_provider_requires_dedicated_key_even_when_openai_is_configured():
    provider = registry.image("doubao_image")
    original_doubao_key = settings.doubao_image_api_key
    original_openai_key = settings.openai_api_key

    try:
        settings.openai_api_key = "sk-openai-only"
        settings.doubao_image_api_key = None

        caps = asyncio.run(provider.capabilities())
        assert caps.configured is False
        assert "OPENAI_API_KEY" not in (caps.reason or "")

        with pytest.raises(ProviderNotConfiguredError):
            asyncio.run(
                provider.generate(
                    ImageGenerationRequest(prompt_plan=ImagePromptPlan(main_subject="豆包隔离测试", count=1))
                )
            )
    finally:
        settings.doubao_image_api_key = original_doubao_key
        settings.openai_api_key = original_openai_key


def test_openai_image_provider_detects_concurrency_limit():
    provider = registry.image("openai_gpt_image")
    exc = Exception("Error code: 429 - {'error': {'message': 'Concurrency limit exceeded for account, please retry later', 'type': 'rate_limit_error'}}")

    assert provider._is_retryable_error(exc) is True
    assert provider._is_concurrency_limit_error(exc) is True
    assert provider._retry_delay_seconds(exc, 3) == 36.0


def test_openai_image_provider_detects_image_quota_limit():
    provider = registry.image("openai_gpt_image")
    exc = Exception(
        "Error code: 429 - Rate limit reached for gpt-image-2-codex in organization org on input-images per min: Limit 4000, Used 4000"
    )

    assert provider._is_retryable_error(exc) is True
    assert provider._is_image_quota_limit_error(exc) is True


def test_openai_image_provider_retries_gateway_wrapped_openai_error():
    provider = registry.image("openai_gpt_image")
    exc = Exception(
        "OpenAI image reference generation failed. Error code: 400 - "
        "{'error': {'code': 'bad_response_status_code', 'message': 'openai_error', 'type': 'bad_response_status_code'}}"
    )

    assert provider._is_retryable_error(exc) is True
    assert provider._is_transient_image_edit_error(exc) is True


def test_openai_image_provider_surfaces_upstream_text_reply_without_retry():
    provider = registry.image("openai_gpt_image")
    exc = Exception(
        "OpenAI image generation failed. Error code: 400 - "
        "{'error': {'code': 'upstream_text_reply', 'message': 'requires a usable image target'}}"
    )

    assert provider._is_retryable_error(exc) is False


def test_openai_image_provider_retries_html_gateway_timeout():
    provider = registry.image("openai_gpt_image")
    exc = Exception(
        "<html><head><title>504 Gateway Time-out</title></head>"
        "<body><center><h1>504 Gateway Time-out</h1></center><hr><center>nginx/1.22.1</center></body></html>"
    )

    assert provider._is_retryable_error(exc) is True
    assert provider._is_transient_image_edit_error(exc) is True


def test_openai_image_provider_gateway_managed_failover_keeps_one_request_in_flight(monkeypatch):
    provider = registry.image("openai_gpt_image")
    calls = {"count": 0}

    class FailingImages:
        async def generate(self, **kwargs):
            calls["count"] += 1
            raise TimeoutError("upstream request timed out after its own failover budget")

    monkeypatch.setattr(settings, "openai_image_gateway_managed_failover", True)
    monkeypatch.setattr(settings, "openai_image_gateway_managed_failover_timeout_seconds", 420.0)
    monkeypatch.setattr(settings, "openai_image_request_timeout_seconds", 240.0)
    monkeypatch.setattr(settings, "openai_image_edit_request_timeout_seconds", 420.0)
    openai_image_provider._openai_image_rate_limiter.reset()

    with pytest.raises(ProviderRuntimeError) as error:
        asyncio.run(
            provider._generate_one(  # noqa: SLF001
                SimpleNamespace(images=FailingImages()),
                "single managed request",
                ImagePromptPlan(main_subject="台灯", count=1),
                index=0,
            )
        )

    assert calls["count"] == 1
    assert error.value.detail["attempts"] == 1
    assert error.value.detail["runtime_transport"] == {
        "gateway_managed_failover": True,
        "gateway_managed_failover_timeout_seconds": 420.0,
        "effective_client_timeout_seconds": 660.0,
        "sdk_max_retries": 0,
        "environment_proxy_bypassed": True,
        "operation": "image_generate",
    }
    capabilities = asyncio.run(provider.capabilities())
    assert capabilities.limits["gateway_managed_failover"] is True
    assert capabilities.limits["effective_client_timeout_seconds"] == 660.0
    assert capabilities.limits["effective_image_edit_client_timeout_seconds"] == 660.0
    assert capabilities.limits["sdk_max_retries"] == 0
    assert capabilities.limits["environment_proxy_bypassed"] is True
    transport_client = provider._gateway_managed_transport_client(timeout_seconds=660.0)  # noqa: SLF001
    try:
        assert transport_client is not None
        assert transport_client._trust_env is False  # noqa: SLF001
    finally:
        asyncio.run(transport_client.aclose())
    assert provider._client_timeout_seconds(image_edit=False) == 660.0  # noqa: SLF001
    assert provider._client_timeout_seconds(image_edit=True) == 660.0  # noqa: SLF001
    assert provider._sdk_max_retries() == 0  # noqa: SLF001


def test_openai_image_provider_compresses_large_reference_png(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "large-reference.png"
    Image.frombytes("RGB", (1024, 1536), os.urandom(1024 * 1536 * 3)).save(source, format="PNG")
    original_size = source.stat().st_size
    provider = registry.image("openai_gpt_image")
    original_root = settings.media_storage_root
    original_max_bytes = settings.openai_image_reference_max_upload_bytes
    original_max_edge = settings.openai_image_reference_max_edge

    try:
        settings.media_storage_root = tmp_path / "media"
        settings.openai_image_reference_max_upload_bytes = 1_200_000
        settings.openai_image_reference_max_edge = 1024

        prepared = provider._provider_reference_path(source)
    finally:
        settings.media_storage_root = original_root
        settings.openai_image_reference_max_upload_bytes = original_max_bytes
        settings.openai_image_reference_max_edge = original_max_edge

    assert prepared != source
    assert prepared.suffix == ".jpg"
    assert prepared.exists()
    assert prepared.stat().st_size <= 1_200_000
    assert source.stat().st_size == original_size
    with Image.open(prepared) as image:
        assert max(image.size) <= 1024


def test_openai_image_provider_reuses_provider_reference_cache(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "uploaded-reference.png"
    Image.frombytes("RGB", (1024, 1536), os.urandom(1024 * 1536 * 3)).save(source, format="PNG")
    provider = registry.image("openai_gpt_image")
    original_root = settings.media_storage_root
    original_max_bytes = settings.openai_image_reference_max_upload_bytes

    try:
        settings.media_storage_root = tmp_path / "media"
        settings.openai_image_reference_max_upload_bytes = 1_200_000
        first = provider._provider_reference_path(source)
        second = provider._provider_reference_path(source)
    finally:
        settings.media_storage_root = original_root
        settings.openai_image_reference_max_upload_bytes = original_max_bytes

    assert first == second
    assert first.exists()
    assert first.parent.name == "provider_reference_cache"
    assert first.stat().st_size <= 1_200_000


def test_openai_image_provider_keeps_small_supported_reference_unchanged(tmp_path):
    Image = pytest.importorskip("PIL.Image")
    source = tmp_path / "small-upload.jpg"
    Image.new("RGB", (320, 320), (235, 236, 238)).save(source, format="JPEG", quality=90)
    provider = registry.image("openai_gpt_image")

    prepared = provider._provider_reference_path(source)

    assert prepared == source


def test_openai_sdk_client_kwargs_ignores_empty_environment_base_url(monkeypatch):
    monkeypatch.setenv("OPENAI_BASE_URL", "")

    kwargs = openai_sdk_client_kwargs(api_key="sk-test", base_url=None)

    assert kwargs["api_key"] == "sk-test"
    assert kwargs["base_url"] == "https://api.openai.com/v1"


@pytest.mark.parametrize(
    ("configured", "expected"),
    [
        ("https://gateway.example/v1/images/generations", "https://gateway.example/v1"),
        ("https://gateway.example/v1/images/edits/", "https://gateway.example/v1"),
        ("https://gateway.example/openai/v1/images/generations", "https://gateway.example/openai/v1"),
    ],
)
def test_openai_sdk_client_kwargs_normalizes_pasted_images_endpoint_to_api_root(configured, expected):
    kwargs = openai_sdk_client_kwargs(api_key="sk-test", base_url=configured)

    assert kwargs["base_url"] == expected


def test_openai_image_provider_passes_quality_to_sdk_call():
    provider = registry.image("openai_gpt_image")
    captured = {}

    class CapturingImages:
        async def generate(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class CapturingClient:
        images = CapturingImages()

    asyncio.run(
        provider._generate_one(
            CapturingClient(),
            "prompt",
            ImagePromptPlan(main_subject="咖啡海报", count=1, quality="low"),
            index=0,
        )
    )

    assert captured["quality"] == "low"
    assert captured["model"] == "gpt-image-2"


def test_openai_image_provider_generation_only_square_transport_is_explicit(monkeypatch):
    provider = registry.image("openai_gpt_image")
    monkeypatch.setattr(settings, "openai_image_transport_profile", "generation_only_square_b64")

    kwargs = provider._image_kwargs(  # noqa: SLF001
        ImagePromptPlan(main_subject="咖啡海报", count=1, size="1024x1024", quality="medium", output_format="png")
    )

    assert kwargs == {"size": "1024x1024", "response_format": "b64_json"}
    capabilities = asyncio.run(provider.capabilities())
    assert capabilities.operations == ["generate"]
    assert capabilities.limits["sizes"] == ["1024x1024"]
    with pytest.raises(ProviderCapabilityMismatchError, match="1024x1024 images"):
        provider._image_kwargs(ImagePromptPlan(main_subject="咖啡海报", count=1, size="1024x1536"))  # noqa: SLF001
    with pytest.raises(ProviderCapabilityMismatchError, match="text-to-image generation only"):
        provider._assert_reference_transport_supported(1)  # noqa: SLF001


def test_openai_image_provider_square_b64_reference_edit_transport_is_explicit(monkeypatch):
    provider = registry.image("openai_gpt_image")
    monkeypatch.setattr(settings, "openai_image_transport_profile", "square_b64_reference_edit")

    kwargs = provider._image_kwargs(  # noqa: SLF001
        ImagePromptPlan(main_subject="咖啡海报", count=1, size="1024x1024", quality="medium", output_format="png")
    )

    assert kwargs == {"size": "1024x1024", "response_format": "b64_json"}
    capabilities = asyncio.run(provider.capabilities())
    assert capabilities.operations == ["generate", "edit", "image_reference", "image_edit"]
    assert capabilities.limits["sizes"] == ["1024x1024"]
    provider._assert_reference_transport_supported(1)  # noqa: SLF001
    assert provider._supports_input_fidelity() is False  # noqa: SLF001


def test_openai_image_provider_accepts_url_response(monkeypatch):
    provider = registry.image("openai_gpt_image")
    tiny_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")

    class FakeResponse:
        content = tiny_png
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url):
            assert url == "https://image.example.test/out.png"
            return FakeResponse()

    monkeypatch.setattr(openai_image_provider.httpx, "Client", FakeClient)

    result = provider._outputs_from_response(
        SimpleNamespace(data=[SimpleNamespace(url="https://image.example.test/out.png")]),
        ImagePromptPlan(main_subject="咖啡海报", count=1, quality="low"),
        request_index=0,
    )

    assert base64.b64decode(result[0]["b64_json"]) == tiny_png
    assert result[0]["api_response_source"] == "url"


def test_openai_image_provider_accepts_data_url_response(monkeypatch):
    provider = registry.image("openai_gpt_image")
    encoded = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="

    class FailingClient:
        def __init__(self, **kwargs):
            raise AssertionError("data URL output should not use HTTP download")

    monkeypatch.setattr(openai_image_provider.httpx, "Client", FailingClient)

    result = provider._outputs_from_response(
        SimpleNamespace(data=[{"url": f"data:image/png;base64,{encoded}"}]),
        ImagePromptPlan(main_subject="咖啡海报", count=1, quality="low"),
        request_index=0,
    )

    assert result[0]["b64_json"] == encoded
    assert result[0]["api_response_source"] == "url"


def test_openai_image_provider_downloads_relative_proxy_url_with_auth(monkeypatch):
    provider = registry.image("openai_gpt_image")
    tiny_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")
    captured = {}
    monkeypatch.setattr(settings, "openai_api_key", "sk-proxy-test")
    monkeypatch.setattr(settings, "openai_base_url", "https://aiself.vip/v1")

    class FakeResponse:
        content = tiny_png
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url, headers=None):
            captured["url"] = url
            captured["headers"] = headers or {}
            return FakeResponse()

    monkeypatch.setattr(openai_image_provider.httpx, "Client", FakeClient)

    result = provider._outputs_from_response(
        SimpleNamespace(data=[{"url": "/v1/files/file-image/content"}]),
        ImagePromptPlan(main_subject="咖啡海报", count=1, quality="low"),
        request_index=0,
    )

    assert captured["url"] == "https://aiself.vip/v1/files/file-image/content"
    assert captured["headers"] == {"Authorization": "Bearer sk-proxy-test"}
    assert base64.b64decode(result[0]["b64_json"]) == tiny_png


def test_openai_image_provider_retries_slow_image_url_download(monkeypatch):
    provider = registry.image("openai_gpt_image")
    tiny_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")
    calls = {"count": 0}

    class FakeResponse:
        content = tiny_png
        headers = {"content-type": "image/png"}

        def raise_for_status(self):
            return None

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def get(self, url, headers=None):
            calls["count"] += 1
            if calls["count"] == 1:
                raise openai_image_provider.httpx.ReadTimeout("slow proxy image content")
            return FakeResponse()

    monkeypatch.setattr(openai_image_provider.httpx, "Client", FakeClient)
    monkeypatch.setattr(openai_image_provider.time, "sleep", lambda seconds: None)

    result = provider._outputs_from_response(
        SimpleNamespace(data=[{"url": "https://image.example.test/slow.png"}]),
        ImagePromptPlan(main_subject="咖啡海报", count=1, quality="low"),
        request_index=0,
    )

    assert calls["count"] == 2
    assert base64.b64decode(result[0]["b64_json"]) == tiny_png


def test_v1_prompting_does_not_require_deleted_or_replaced_quoted_text():
    delete_plan = build_prompt_plan(prompt='把左上角的“ALCOEN”logo去掉，保持整体风格。')
    replace_plan = build_prompt_plan(prompt='把“江苏纯安科技有限公司”改成“华斐达集团”，英文换成“HUAFEIDA GROUP”。')

    assert delete_plan.text.get("content") is None
    assert replace_plan.text["content"] == "华斐达集团；HUAFEIDA GROUP"


def test_v1_prompting_infers_size_from_default_prompt_language():
    a4_plan = build_prompt_plan(prompt="尺寸不变，A4大小。生成高清4K图片。")
    landscape_a4_plan = build_prompt_plan(prompt="生成横版A4商业海报。")
    portrait_plan = build_prompt_plan(prompt="生成一张竖版节日海报。")
    landscape_plan = build_prompt_plan(prompt="做成16:9横向封面。")
    square_plan = build_prompt_plan(prompt="生成正方形头像。")
    explicit_plan = build_prompt_plan(prompt="生成A4海报。", size="1024x1024")

    assert a4_plan.size == "2400x3392"
    assert "竖版构图" in a4_plan.composition
    assert landscape_a4_plan.size == "3392x2400"
    assert portrait_plan.size == "1024x1536"
    assert landscape_plan.size == "1536x1024"
    assert square_plan.size == "1024x1024"
    assert explicit_plan.size == "1024x1024"


def test_openai_image_provider_uses_edit_endpoint_for_reference_images(tmp_path):
    provider = registry.image("openai_gpt_image")
    captured = {}
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))

    class CapturingImages:
        async def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class CapturingClient:
        images = CapturingImages()

    result = asyncio.run(
        provider._generate_one_with_references(
            CapturingClient(),
            "prompt with material constraints",
            ImagePromptPlan(main_subject="咖啡海报", count=1, quality="medium", output_format="png"),
            [reference_path],
            index=0,
        )
    )

    assert captured["model"] == "gpt-image-2"
    assert captured["prompt"] == "prompt with material constraints"
    assert captured["quality"] == "medium"
    assert captured["output_format"] == "png"
    assert len(captured["image"]) == 1
    assert result[0]["api_operation"] == "images.edit"
    assert result[0]["reference_image_count"] == 1


def test_doc96_openai_image_provider_applies_high_input_fidelity(tmp_path):
    provider = registry.image("openai_gpt_image")
    openai_image_provider._image_edit_capability_cache.reset()
    captured = {}
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))

    class CapturingImages:
        async def edit(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")])

    result = asyncio.run(
        provider._generate_one_with_references(
            SimpleNamespace(images=CapturingImages()),
            "identity edit",
            ImagePromptPlan(
                main_subject="portrait",
                count=1,
                variables={"input_fidelity": "high"},
            ),
            [reference_path],
            index=0,
        )
    )

    assert captured["input_fidelity"] == "high"
    assert result[0]["input_fidelity_requested"] == "high"
    assert result[0]["input_fidelity_applied"] == "high"
    assert result[0]["input_fidelity_support_state"] == "supported"


def test_doc96_input_fidelity_specific_400_falls_back_once(tmp_path):
    provider = registry.image("openai_gpt_image")
    openai_image_provider._image_edit_capability_cache.reset()
    captured = []
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))

    class UnsupportedFidelityError(Exception):
        status_code = 400

    class CapturingImages:
        async def edit(self, **kwargs):
            captured.append(dict(kwargs))
            if len(captured) == 1:
                raise UnsupportedFidelityError("unknown parameter input_fidelity: not supported")
            return SimpleNamespace(data=[SimpleNamespace(b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")])

    result = asyncio.run(
        provider._generate_one_with_references(
            SimpleNamespace(images=CapturingImages()),
            "identity edit",
            ImagePromptPlan(main_subject="portrait", variables={"input_fidelity": "high"}),
            [reference_path],
            index=0,
        )
    )

    assert len(captured) == 2
    assert captured[0]["input_fidelity"] == "high"
    assert "input_fidelity" not in captured[1]
    assert result[0]["input_fidelity_applied"] is None
    assert result[0]["input_fidelity_support_state"] == "unsupported"
    assert "not supported" in result[0]["input_fidelity_fallback_reason"]


def test_doc96_identity_local_repair_sends_same_size_mask(tmp_path):
    provider = registry.image("openai_gpt_image")
    openai_image_provider._image_edit_capability_cache.reset()
    captured = {}
    reference_path = tmp_path / "reference.png"
    mask_path = tmp_path / "mask.png"
    tiny_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=")
    reference_path.write_bytes(tiny_png)
    mask_path.write_bytes(tiny_png)

    class CapturingImages:
        async def edit(self, **kwargs):
            captured.update(kwargs)
            captured["mask_name"] = getattr(kwargs.get("mask"), "name", "")
            return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(tiny_png).decode("ascii"))])

    result = asyncio.run(
        provider._generate_one_with_references(
            SimpleNamespace(images=CapturingImages()),
            "identity-local repair",
            ImagePromptPlan(main_subject="portrait", variables={"input_fidelity": "high"}),
            [reference_path],
            index=0,
            mask_path=mask_path,
        )
    )

    assert captured["input_fidelity"] == "high"
    assert captured["mask_name"].endswith("mask.png")
    assert result[0]["identity_local_repair"] is True


def test_openai_image_provider_retries_gateway_image_edit_500_once(tmp_path, monkeypatch):
    provider = registry.image("openai_gpt_image")
    captured = {"attempts": 0}
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    original_base_url = settings.openai_base_url
    original_cooldown = settings.openai_image_edit_transient_cooldown_seconds

    class Gateway500Error(Exception):
        status_code = 500

    class FlakyImages:
        async def edit(self, **kwargs):
            captured["attempts"] += 1
            if captured["attempts"] == 1:
                raise Gateway500Error("500 internal_server_error from aiai image edit")
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class FlakyClient:
        images = FlakyImages()

    try:
        settings.openai_base_url = "https://aiself.vip/v1"
        settings.openai_image_edit_transient_cooldown_seconds = 0.0
        result = asyncio.run(
            provider._generate_one_with_references(
                FlakyClient(),
                "prompt",
                ImagePromptPlan(main_subject="portrait", count=1, quality="medium", output_format="png"),
                [reference_path],
                index=0,
            )
        )
    finally:
        settings.openai_base_url = original_base_url
        settings.openai_image_edit_transient_cooldown_seconds = original_cooldown
        openai_image_provider._openai_image_rate_limiter.reset()

    assert captured["attempts"] == 2
    assert result[0]["api_operation"] == "images.edit"
    assert result[0]["image_edit_transient_retries"] == 1


def test_openai_image_provider_retries_gateway_image_edit_403_once(tmp_path):
    provider = registry.image("openai_gpt_image")
    captured = {"attempts": 0}
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    original_base_url = settings.openai_base_url
    original_cooldown = settings.openai_image_edit_transient_cooldown_seconds

    class Gateway403Error(Exception):
        status_code = 403

    class FlakyImages:
        async def edit(self, **kwargs):
            captured["attempts"] += 1
            if captured["attempts"] == 1:
                raise Gateway403Error("403 upstream account aicodexvip temporarily forbidden")
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class FlakyClient:
        images = FlakyImages()

    try:
        settings.openai_base_url = "https://aiself.vip/v1"
        settings.openai_image_edit_transient_cooldown_seconds = 0.0
        result = asyncio.run(
            provider._generate_one_with_references(
                FlakyClient(),
                "prompt",
                ImagePromptPlan(main_subject="portrait", count=1, quality="medium", output_format="png"),
                [reference_path],
                index=0,
            )
        )
    finally:
        settings.openai_base_url = original_base_url
        settings.openai_image_edit_transient_cooldown_seconds = original_cooldown
        openai_image_provider._openai_image_rate_limiter.reset()

    assert captured["attempts"] == 2
    assert result[0]["image_edit_transient_retries"] == 1


def test_openai_image_provider_image_edit_has_total_timeout_guard(tmp_path):
    provider = registry.image("openai_gpt_image")
    captured = {"attempts": 0}
    reference_path = tmp_path / "reference.png"
    reference_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))
    original_timeout = provider._client_timeout_seconds
    original_cooldown = settings.openai_image_edit_transient_cooldown_seconds

    class SlowImages:
        async def edit(self, **kwargs):
            captured["attempts"] += 1
            await asyncio.sleep(1.0)

    class SlowClient:
        images = SlowImages()

    try:
        provider._client_timeout_seconds = lambda *, image_edit: 0.05
        settings.openai_image_edit_transient_cooldown_seconds = 0.0
        with pytest.raises(ProviderRuntimeError) as exc_info:
            asyncio.run(
                provider._generate_one_with_references(
                    SlowClient(),
                    "prompt",
                    ImagePromptPlan(main_subject="portrait", count=1, quality="medium", output_format="png"),
                    [reference_path],
                    index=0,
                )
            )
    finally:
        provider._client_timeout_seconds = original_timeout
        settings.openai_image_edit_transient_cooldown_seconds = original_cooldown
        openai_image_provider._openai_image_rate_limiter.reset()

    assert captured["attempts"] == 1
    assert exc_info.value.detail["operation_timeout_exhausted"] is True
    assert exc_info.value.detail["operation_timeout_seconds"] == 0.05


def test_openai_image_provider_does_not_treat_official_403_as_gateway_transient():
    provider = registry.image("openai_gpt_image")
    original_base_url = settings.openai_base_url

    class Official403Error(Exception):
        status_code = 403

    try:
        settings.openai_base_url = "https://api.openai.com/v1"
        exc = Official403Error("403 permission denied")
        assert provider._is_transient_image_edit_error(exc) is False
    finally:
        settings.openai_base_url = original_base_url


def test_openai_image_provider_edit_uses_stored_source_output(tmp_path, monkeypatch):
    provider = registry.image("openai_gpt_image")
    captured = {}
    source_dir = tmp_path / "generated_images" / "job_source"
    source_dir.mkdir(parents=True)
    source_path = source_dir / "out_source.png"
    source_path.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="))

    class CapturingImages:
        async def edit(self, **kwargs):
            captured.update(kwargs)
            captured["image_file_names"] = [getattr(handle, "name", "") for handle in kwargs["image"]]
            return SimpleNamespace(
                data=[
                    SimpleNamespace(
                        b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
                    )
                ]
            )

    class CapturingClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.images = CapturingImages()

    monkeypatch.setattr(media_store, "root", tmp_path)
    monkeypatch.setattr(settings, "openai_api_key", "sk-test-openai-image")
    monkeypatch.setattr(settings, "openai_base_url", "https://openai.example.test/v1")
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=CapturingClient))

    result = asyncio.run(
        provider.edit(
            ImageGenerationRequest(
                prompt_plan=ImagePromptPlan(main_subject="精品咖啡海报", count=4, quality="high", output_format="png"),
                source_output_id="out_source",
            )
        )
    )

    assert captured["client_kwargs"]["base_url"] == "https://openai.example.test/v1"
    assert captured["client_kwargs"]["max_retries"] == 0
    assert captured["model"] == "gpt-image-2"
    assert captured["prompt"].startswith("Main subject: 精品咖啡海报")
    assert captured["quality"] == "high"
    assert captured["output_format"] == "png"
    assert len(captured["image"]) == 1
    assert captured["image_file_names"][0].endswith("out_source.png")
    assert len(result.outputs) == 1
    assert result.outputs[0]["api_operation"] == "images.edit"
    assert result.raw_response_summary["api_style"] == "images.edit"
    assert result.raw_response_summary["source_output_id"] == "out_source"
    assert result.raw_response_summary["source_job_id"] == "job_source"
    assert result.raw_response_summary["source_output_format"] == "png"


def test_gemini_image_provider_generates_from_inline_data(monkeypatch):
    provider = registry.image("gemini_image")
    captured = {}
    original_key = settings.gemini_image_api_key
    original_base_url = settings.gemini_image_base_url
    original_model = settings.gemini_image_model
    original_enabled = settings.gemini_image_generation_enabled

    class FakeResponse:
        status_code = 200

        @property
        def text(self):
            return "{}"

        def json(self):
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "inlineData": {
                                        "mimeType": "image/png",
                                        "data": base64.b64encode(b"fake-png").decode("ascii"),
                                    }
                                }
                            ]
                        }
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return FakeResponse()

    try:
        settings.gemini_image_api_key = "sk-gemini-test"
        settings.gemini_image_base_url = "https://gemini.example.test"
        settings.gemini_image_model = "gemini-3-pro-image-preview"
        settings.gemini_image_generation_enabled = True
        monkeypatch.setattr(gemini_image_provider.httpx, "AsyncClient", FakeAsyncClient)

        result = asyncio.run(
            provider.generate(
                ImageGenerationRequest(
                    prompt_plan=ImagePromptPlan(
                        main_subject="精品咖啡海报",
                        count=1,
                        size="1024x1536",
                        quality="high",
                    )
                )
            )
        )
    finally:
        settings.gemini_image_api_key = original_key
        settings.gemini_image_base_url = original_base_url
        settings.gemini_image_model = original_model
        settings.gemini_image_generation_enabled = original_enabled

    assert captured["url"] == "https://gemini.example.test/models/gemini-3-pro-image-preview:generateContent?key=sk-gemini-test"
    assert captured["headers"]["x-goog-api-key"] == "sk-gemini-test"
    assert captured["payload"]["generationConfig"]["responseModalities"] == ["Image"]
    assert captured["payload"]["generationConfig"]["responseFormat"]["image"]["aspectRatio"] == "2:3"
    assert captured["payload"]["generationConfig"]["responseFormat"]["image"]["imageSize"] == "2K"
    assert result.provider == "gemini_image"
    assert result.model == "gemini-3-pro-image-preview"
    assert result.outputs[0]["format"] == "png"
    assert result.outputs[0]["b64_json"]


def test_work_intensity_llm_planner_passes_reasoning_effort(monkeypatch):
    captured = {}
    original_key = settings.openai_api_key
    original_base_url = settings.openai_base_url
    original_model = settings.default_llm_model
    original_provider = settings.default_llm_provider
    original_openai_llm_model = settings.openai_llm_model
    original_enabled = settings.llm_prompt_planning_enabled

    class FakeResponses:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "main_subject": "精品咖啡海报",
                        "scene": "安静的精品咖啡馆",
                        "style": "高级商业摄影",
                        "composition": "竖版主视觉",
                        "brand_constraints": ["premium tone"],
                        "negative_constraints": ["avoid clutter"],
                        "text": {"required": False, "language": "zh-CN"},
                        "generation_prompt": "LLM refined premium coffee poster prompt. Style reference: asset_ref color harmony.",
                        "planning_notes": ["checked composition"],
                    }
                )
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    try:
        settings.openai_api_key = "sk-test-planner"
        settings.openai_base_url = "https://example.test/v1"
        settings.default_llm_provider = "openai"
        settings.default_llm_model = "gpt-5.5-test"
        settings.openai_llm_model = "gpt-5.5-test"
        settings.llm_prompt_planning_enabled = True
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeClient))

        plan, summary = asyncio.run(
            apply_work_intensity(
                ImagePromptPlan(main_subject="生成 1 张精品咖啡海报", count=1),
                original_prompt="生成 1 张精品咖啡海报",
                work_intensity="atelier",
                provider_preference="openai_gpt_image",
                asset_context={
                    "provider_input_plan": {"operation": "image_edit_with_reference_images", "reference_image_count": 1},
                    "assets": [{"asset_id": "asset_ref", "role": "style_reference", "vision_profile": {"summary": "暖色咖啡风格参考"}}],
                },
            )
        )
    finally:
        settings.openai_api_key = original_key
        settings.openai_base_url = original_base_url
        settings.default_llm_model = original_model
        settings.default_llm_provider = original_provider
        settings.openai_llm_model = original_openai_llm_model
        settings.llm_prompt_planning_enabled = original_enabled

    assert captured["reasoning"]["effort"] == "high"
    assert captured["model"] == "gpt-5.5-test"
    planner_payload = json.loads(captured["input"][1]["content"])
    assert planner_payload["asset_context"]["provider_input_plan"]["reference_image_count"] == 1
    assert planner_payload["asset_context_rule"].startswith("Use structured asset context")
    assert summary["planner"] == "llm"
    assert summary["llm_used"] is True
    assert plan.variables["planner"] == "llm"
    assert "asset_ref" not in plan.variables["generation_prompt"]
    assert "上传参考图" in plan.variables["generation_prompt"]


def test_work_intensity_guard_removes_unrequested_no_text_for_reference(monkeypatch):
    original_key = settings.openai_api_key
    original_base_url = settings.openai_base_url
    original_provider = settings.default_llm_provider
    original_openai_llm_model = settings.openai_llm_model
    original_enabled = settings.llm_prompt_planning_enabled

    class FakeResponses:
        async def create(self, **kwargs):
            return SimpleNamespace(
                output_text=json.dumps(
                    {
                        "main_subject": "商业海报",
                        "scene": "商业棚拍",
                        "style": "高级商业视觉",
                        "composition": "竖版构图",
                        "brand_constraints": [],
                        "negative_constraints": [],
                        "text": {"required": False, "language": "zh-CN"},
                        "generation_prompt": "以上传参考图为原型，生成高级商业海报。无文字。",
                        "planning_notes": ["clean layout"],
                    }
                )
            )

    class FakeClient:
        def __init__(self, **kwargs):
            self.responses = FakeResponses()

    try:
        settings.openai_api_key = "sk-test-planner"
        settings.openai_base_url = "https://example.test/v1"
        settings.default_llm_provider = "openai"
        settings.openai_llm_model = "gpt-5.5-test"
        settings.llm_prompt_planning_enabled = True
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeClient))

        plan, summary = asyncio.run(
            apply_work_intensity(
                ImagePromptPlan(main_subject="以这张图为原型，生成一张极具商业化风格的海报", count=1),
                original_prompt="以这张图为原型，生成一张极具商业化风格的海报",
                work_intensity="balanced",
                provider_preference="openai_gpt_image",
                asset_context={
                    "provider_input_plan": {"operation": "image_edit_with_reference_images", "reference_image_count": 1, "requires_image_reference": True},
                    "assets": [{"role": "composition_reference", "provider_input_mode": "reference_image"}],
                },
            )
        )
    finally:
        settings.openai_api_key = original_key
        settings.openai_base_url = original_base_url
        settings.default_llm_provider = original_provider
        settings.openai_llm_model = original_openai_llm_model
        settings.llm_prompt_planning_enabled = original_enabled

    prompt = plan.variables["generation_prompt"]
    assert summary["planner"] == "llm"
    assert "无文字" not in prompt
    assert "可读文字" in prompt
    assert "默认属于用户提供的有效信息" in prompt
    assert "反向改变用户根本意图" in prompt
    assert "removed_unrequested_no_text_constraint" in plan.variables["intent_preservation_guard"]


def test_work_intensity_uses_backup_llm_when_primary_fails(monkeypatch):
    captured = {}
    original_key = settings.openai_api_key
    original_base_url = settings.openai_base_url
    original_model = settings.default_llm_model
    original_provider = settings.default_llm_provider
    original_backup_provider = settings.backup_llm_provider
    original_backup_model = settings.backup_llm_model
    original_openai_llm_model = settings.openai_llm_model
    original_kimi_llm_model = settings.kimi_llm_model
    original_deepseek_llm_api_key = settings.deepseek_llm_api_key
    original_deepseek_llm_base_url = settings.deepseek_llm_base_url
    original_deepseek_llm_model = settings.deepseek_llm_model
    original_lab_doubao_vision_api_key = settings.lab_doubao_vision_api_key
    original_lab_doubao_vision_base_url = settings.lab_doubao_vision_base_url
    original_lab_doubao_vision_model = settings.lab_doubao_vision_model
    original_anthropic_base_url = settings.anthropic_base_url
    original_anthropic_api_key = settings.anthropic_api_key
    original_anthropic_auth_token = settings.anthropic_auth_token
    original_enabled = settings.llm_prompt_planning_enabled

    class FailingResponses:
        async def create(self, **kwargs):
            raise RuntimeError("primary planner unavailable")

    class FailingClient:
        def __init__(self, **kwargs):
            self.responses = FailingResponses()

    class FakeHTTPResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "main_subject": "备用规划咖啡海报",
                                "scene": "明亮咖啡吧台",
                                "style": "日系清爽商业摄影",
                                "composition": "手机竖屏主视觉",
                                "brand_constraints": ["fresh tone"],
                                "negative_constraints": ["avoid clutter"],
                                "text": {"required": False, "language": "zh-CN"},
                                "generation_prompt": "Kimi backup refined coffee poster prompt",
                                "planning_notes": ["backup checked composition"],
                            }
                        ),
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url, *, headers, json):
            captured["url"] = url
            captured["header_names"] = sorted(headers)
            captured["payload"] = json
            return FakeHTTPResponse()

    try:
        settings.openai_api_key = "sk-primary-test"
        settings.openai_base_url = "https://primary.example.test/v1"
        settings.default_llm_provider = "openai"
        settings.default_llm_model = "gpt-5.5-test"
        settings.openai_llm_model = "gpt-5.5-test"
        settings.backup_llm_provider = "anthropic"
        settings.backup_llm_model = "kimi-for-coding-test"
        settings.kimi_llm_model = "kimi-for-coding-test"
        settings.deepseek_llm_api_key = None
        settings.deepseek_llm_base_url = None
        settings.deepseek_llm_model = "deepseek-test-disabled"
        settings.lab_doubao_vision_api_key = None
        settings.lab_doubao_vision_base_url = None
        settings.lab_doubao_vision_model = "doubao-test-disabled"
        settings.anthropic_base_url = "https://backup.example.test"
        settings.anthropic_api_key = None
        settings.anthropic_auth_token = "sk-backup-test"
        settings.llm_prompt_planning_enabled = True
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FailingClient))
        monkeypatch.setattr("app.services.work_intensity.httpx.AsyncClient", FakeAsyncClient)

        plan, summary = asyncio.run(
            apply_work_intensity(
                ImagePromptPlan(main_subject="生成 1 张精品咖啡海报", count=1),
                original_prompt="生成 1 张精品咖啡海报",
                work_intensity="studio",
                provider_preference="openai_gpt_image",
            )
        )
    finally:
        settings.openai_api_key = original_key
        settings.openai_base_url = original_base_url
        settings.default_llm_model = original_model
        settings.default_llm_provider = original_provider
        settings.backup_llm_provider = original_backup_provider
        settings.backup_llm_model = original_backup_model
        settings.openai_llm_model = original_openai_llm_model
        settings.kimi_llm_model = original_kimi_llm_model
        settings.deepseek_llm_api_key = original_deepseek_llm_api_key
        settings.deepseek_llm_base_url = original_deepseek_llm_base_url
        settings.deepseek_llm_model = original_deepseek_llm_model
        settings.lab_doubao_vision_api_key = original_lab_doubao_vision_api_key
        settings.lab_doubao_vision_base_url = original_lab_doubao_vision_base_url
        settings.lab_doubao_vision_model = original_lab_doubao_vision_model
        settings.anthropic_base_url = original_anthropic_base_url
        settings.anthropic_api_key = original_anthropic_api_key
        settings.anthropic_auth_token = original_anthropic_auth_token
        settings.llm_prompt_planning_enabled = original_enabled

    assert captured["url"] == "https://backup.example.test/v1/messages"
    assert captured["payload"]["model"] == "kimi-for-coding-test"
    assert "authorization" in captured["header_names"]
    assert "x-api-key" in captured["header_names"]
    assert summary["planner"] == "llm"
    assert summary["llm_used"] is True
    assert summary["llm_provider"] == "anthropic"
    assert summary["llm_model"] == "kimi-for-coding-test"
    assert summary["fallback_used"] is True
    assert plan.variables["llm_provider"] == "anthropic"
    assert plan.variables["llm_model"] == "kimi-for-coding-test"
    assert plan.variables["generation_prompt"] == "Kimi backup refined coffee poster prompt"


def test_openai_image_provider_raises_retryable_rate_limit_after_retries(monkeypatch):
    provider = registry.image("openai_gpt_image")
    attempts = 0

    class FailingImages:
        async def generate(self, **kwargs):
            nonlocal attempts
            attempts += 1
            raise Exception("Error code: 429 - {'error': {'message': 'Concurrency limit exceeded for account, please retry later', 'type': 'rate_limit_error'}}")

    class FailingClient:
        images = FailingImages()

    async def no_sleep(seconds):
        return None

    monkeypatch.setattr("app.providers.openai_image.asyncio.sleep", no_sleep)

    with pytest.raises(ProviderRateLimitError) as raised:
        asyncio.run(
            provider._generate_one(
                FailingClient(),
                "prompt",
                ImagePromptPlan(main_subject="咖啡海报", count=1),
                index=0,
            )
        )

    assert attempts == 6
    assert raised.value.retryable is True
    assert raised.value.detail["upstream_concurrency_limited"] is True


def test_openai_image_provider_cools_down_after_image_quota_limit(monkeypatch):
    provider = registry.image("openai_gpt_image")
    attempts = 0
    original_queue_timeout = settings.openai_image_local_queue_timeout_seconds
    settings.openai_image_local_queue_timeout_seconds = 0.01

    class QuotaResponse:
        headers = {"Retry-After": "120"}

    class QuotaError(Exception):
        status_code = 429
        response = QuotaResponse()

    class QuotaImages:
        async def generate(self, **kwargs):
            nonlocal attempts
            attempts += 1
            raise QuotaError(
                "Rate limit reached for gpt-image-2-codex on input-images per min: Limit 4000, Used 4000"
            )

    class SuccessImages:
        async def generate(self, **kwargs):
            raise AssertionError("OpenAI SDK should not be called during local cooldown.")

    class QuotaClient:
        images = QuotaImages()

    class SuccessClient:
        images = SuccessImages()

    try:
        with pytest.raises(ProviderRateLimitError) as first:
            asyncio.run(
                provider._generate_one(
                    QuotaClient(),
                    "prompt",
                    ImagePromptPlan(main_subject="咖啡海报", count=1),
                    index=0,
                )
            )
        assert attempts == 1
        assert first.value.detail["rate_limit_scope"] == "openai_image_input_images_per_minute"
        assert first.value.detail["retry_after_seconds"] == 120

        with pytest.raises(ProviderRateLimitError) as second:
            asyncio.run(
                provider._generate_one(
                    SuccessClient(),
                    "prompt",
                    ImagePromptPlan(main_subject="咖啡海报", count=1),
                    index=0,
                )
            )
        assert second.value.detail["rate_limit_scope"] == "upstream_openai_image_rate_limit_cooldown"
    finally:
        openai_image_provider._openai_image_rate_limiter.reset()
        settings.openai_image_local_queue_timeout_seconds = original_queue_timeout


def test_mock_image_provider_contract():
    provider = registry.image("mock_image")
    caps = asyncio.run(provider.capabilities())
    assert caps.configured is True
    assert caps.is_mock is True

    result = asyncio.run(
        provider.generate(
            ImageGenerationRequest(
                prompt_plan=ImagePromptPlan(main_subject="生成 2 张咖啡海报", count=2, size="1024x1536")
            )
        )
    )

    assert result.provider == "mock_image"
    assert result.model == "mock-image-v1"
    assert len(result.outputs) == 2
    assert "b64_json" in result.outputs[0]


def test_default_image_selection_falls_back_to_mock_when_openai_unconfigured():
    original_provider = settings.default_image_provider
    original_openai_key = settings.openai_api_key
    original_gemini_key = settings.gemini_image_api_key
    original_gemini_enabled = settings.gemini_image_generation_enabled
    try:
        settings.default_image_provider = "openai_gpt_image"
        settings.openai_api_key = None
        settings.gemini_image_api_key = None
        settings.gemini_image_generation_enabled = False
        provider = asyncio.run(registry.select_image())
        assert provider.name == "mock_image"
    finally:
        settings.default_image_provider = original_provider
        settings.openai_api_key = original_openai_key
        settings.gemini_image_api_key = original_gemini_key
        settings.gemini_image_generation_enabled = original_gemini_enabled
