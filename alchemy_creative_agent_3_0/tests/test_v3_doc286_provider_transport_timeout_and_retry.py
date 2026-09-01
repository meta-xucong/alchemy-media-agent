import asyncio
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest

from alchemy_creative_agent_3_0.app.generation_router import ProductionImageGenerationProvider
from app.providers import openai_image
from app.providers.base import ProviderRuntimeError
from app.schemas import ImagePromptPlan


def _png_base64(width: int = 64, height: int = 48) -> str:
    import base64

    from PIL import Image

    image = Image.new("RGB", (width, height), color=(70, 104, 138))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class _StatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"status {status_code}")
        self.status_code = status_code


def _plan() -> ImagePromptPlan:
    return ImagePromptPlan(main_subject="a test image", count=1, size="1024x1024")


def test_direct_adapter_retries_transient_failures_three_total_and_records_one_budget(monkeypatch) -> None:
    provider = openai_image.OpenAIGPTImageProvider(model="gpt-image-2")
    openai_image._openai_image_rate_limiter.reset()
    monkeypatch.setattr(openai_image.settings, "openai_image_gateway_managed_failover", False)

    class Images:
        calls = 0

        async def generate(self, **kwargs):  # noqa: ARG002
            self.calls += 1
            if self.calls < 3:
                raise _StatusError(502)
            return SimpleNamespace(data=[SimpleNamespace(b64_json=_png_base64())])

    client = SimpleNamespace(images=Images())
    async def no_sleep(_seconds):
        return None

    monkeypatch.setattr(openai_image.asyncio, "sleep", no_sleep)

    outputs = asyncio.run(provider._generate_one(client, "test", _plan(), index=0))  # noqa: SLF001

    assert len(outputs) == 1
    assert client.images.calls == 3
    summary = provider._transport_retry_summary()  # noqa: SLF001
    assert summary["max_attempts"] == 3
    assert summary["fresh_upstream_requests"] == 3
    assert [item["status"] for item in summary["attempts"]] == ["failed", "failed", "succeeded"]
    assert all("elapsed_ms" in item for item in summary["attempts"])


def test_direct_adapter_explicit_terminal_failure_does_not_wait_or_retry(monkeypatch) -> None:
    provider = openai_image.OpenAIGPTImageProvider(model="gpt-image-2")
    openai_image._openai_image_rate_limiter.reset()
    calls = 0

    class Images:
        async def generate(self, **kwargs):  # noqa: ARG002
            nonlocal calls
            calls += 1
            raise _StatusError(400)

    async def unexpected_sleep(_seconds):
        raise AssertionError("explicit terminal failures must not sleep")

    monkeypatch.setattr(openai_image.asyncio, "sleep", unexpected_sleep)

    with pytest.raises(ProviderRuntimeError) as raised:
        asyncio.run(provider._generate_one(SimpleNamespace(images=Images()), "test", _plan(), index=0))  # noqa: SLF001

    assert calls == 1
    detail = raised.value.detail
    assert detail["transport_retry_terminal"] is True
    assert detail["transport_outcome"]["request_state"] == "terminal_failed"
    assert detail["transport_outcome"]["retryability"] == "never"
    assert detail["fresh_upstream_requests"] == 1


def test_direct_adapter_timeout_with_unknown_acceptance_stops_at_one_attempt(monkeypatch) -> None:
    provider = openai_image.OpenAIGPTImageProvider(model="gpt-image-2")
    openai_image._openai_image_rate_limiter.reset()
    monkeypatch.setattr(openai_image.settings, "openai_image_gateway_managed_failover", False)
    monkeypatch.setattr(provider, "_client_timeout_seconds", lambda *, image_edit, plan=None: 0.01)
    calls = 0
    never = asyncio.Event()

    class Images:
        async def generate(self, **kwargs):  # noqa: ARG002
            nonlocal calls
            calls += 1
            await never.wait()

    async def unexpected_sleep(_seconds):
        raise AssertionError("an acceptance-ambiguous timeout must not blind-loop")

    monkeypatch.setattr(openai_image.asyncio, "sleep", unexpected_sleep)

    with pytest.raises(ProviderRuntimeError) as raised:
        asyncio.run(provider._generate_one(SimpleNamespace(images=Images()), "test", _plan(), index=0))  # noqa: SLF001

    assert calls == 1
    outcome = raised.value.detail["transport_outcome"]
    assert outcome["request_state"] == "accepted_unknown"
    assert outcome["retryability"] == "status_required"
    assert raised.value.detail["fresh_upstream_requests"] == 1


def test_reference_timeout_with_unknown_acceptance_is_not_replayed(monkeypatch, tmp_path: Path) -> None:
    provider = openai_image.OpenAIGPTImageProvider(model="gpt-image-2")
    openai_image._openai_image_rate_limiter.reset()
    monkeypatch.setattr(openai_image.settings, "openai_image_gateway_managed_failover", False)
    monkeypatch.setattr(provider, "_client_timeout_seconds", lambda *, image_edit, plan=None: 0.01)
    reference = tmp_path / "reference.png"
    import base64

    reference.write_bytes(base64.b64decode(_png_base64()))
    calls = 0
    never = asyncio.Event()

    class Images:
        async def edit(self, **kwargs):  # noqa: ARG002
            nonlocal calls
            calls += 1
            await never.wait()

    async def unexpected_sleep(_seconds):
        raise AssertionError("an acceptance-ambiguous edit timeout must not blind-loop")

    monkeypatch.setattr(openai_image.asyncio, "sleep", unexpected_sleep)

    with pytest.raises(ProviderRuntimeError) as raised:
        asyncio.run(
            provider._generate_one_with_references(  # noqa: SLF001
                SimpleNamespace(images=Images()),
                "test",
                _plan(),
                [reference],
                index=0,
            )
        )

    assert calls == 1
    outcome = raised.value.detail["transport_outcome"]
    assert outcome["phase"] == "image_edit"
    assert outcome["request_state"] == "accepted_unknown"
    assert outcome["retryability"] == "status_required"


def test_v3_wrapper_does_not_replay_an_adapter_terminal_outcome(monkeypatch) -> None:
    provider = ProductionImageGenerationProvider()
    calls = 0
    app_request = SimpleNamespace(
        prompt_plan=SimpleNamespace(variables={"generation_prompt": "test"}),
        metadata={},
    )

    async def terminal_provider(_provider_name, _app_request):
        nonlocal calls
        calls += 1
        raise ProviderRuntimeError(
            "adapter terminal failure",
            provider="openai_gpt_image",
            detail={
                "transport_retry_terminal": True,
                "transport_outcome": {
                    "schema_version": "v3_provider_transport_retry_v1",
                    "phase": "image_edit",
                    "request_state": "accepted_unknown",
                    "retryability": "status_required",
                    "failure_code": "provider_timeout",
                },
            },
        )

    monkeypatch.setattr(provider, "_generate_with_app_provider", terminal_provider)

    with pytest.raises(ProviderRuntimeError):
        provider._run_app_provider_with_timeout_retry(  # noqa: SLF001
            "openai_gpt_image",
            app_request,
            [],
            reference_input_execution={"admission_outcome": "admitted"},
            output_index=1,
        )

    assert calls == 1
