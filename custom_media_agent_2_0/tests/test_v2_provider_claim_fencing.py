from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import httpx
import pytest

from app.config import settings
from app.providers.images import claim_fenced_http
from app.providers.images import doubao_image as doubao_module
from app.providers.images import gemini_image as gemini_module
from app.providers.images import openai_gpt_image_2 as openai_module
from app.providers.images import response_payloads
from app.providers.images.base import V2ImageProviderRequest
from app.repositories.memory import utc_now
from app.schemas import CreativeRun, ImagePromptPlan
from app.services import task_queue


def _configure_claim(tmp_path: Path, monkeypatch) -> task_queue.QueuedTask:
    monkeypatch.setattr(
        task_queue,
        "settings",
        replace(
            settings,
            task_queue_db_path=tmp_path / "provider-claim.sqlite3",
            task_queue_claim_timeout_seconds=1.0,
            task_queue_max_attempts=4,
            task_queue_max_pending=10,
        ),
    )
    task_queue.initialize_task_queue()
    now = utc_now()
    run = CreativeRun(
        run_id="run_provider_claim_fence",
        status="generating",
        mode="smart_enhance",
        intent_summary="offline provider claim fence test",
        trace_id="trace_provider_claim_fence",
        created_at=now,
        updated_at=now,
    )
    task_queue.enqueue_creative_task(
        kind="creative_run",
        request_payload={"user_prompt": "offline fake"},
        queued_run=run,
    )
    claim = task_queue.claim_next_task("provider-worker-old")
    assert claim is not None
    return claim


def _supersede(claim: task_queue.QueuedTask) -> task_queue.QueuedTask:
    stale_locked_at = (utc_now() - timedelta(days=1)).isoformat()
    with task_queue._connect() as connection:
        connection.execute(
            "UPDATE v2_tasks SET locked_at = ? WHERE task_id = ?",
            (stale_locked_at, claim.task_id),
        )
    replacement = task_queue.claim_next_task("provider-worker-replacement")
    assert replacement is not None
    assert replacement.task_id == claim.task_id
    assert replacement.claim_token != claim.claim_token
    return replacement


class _FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, response):
        self.response = response
        self.sent: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.sent.append(request)
        return self.response(request, len(self.sent))

    async def aclose(self) -> None:
        return None


def _install_transport(monkeypatch, transport: _FakeTransport) -> None:
    def client_factory(**kwargs):
        return claim_fenced_http.claim_fenced_async_client(transport=transport, **kwargs)

    monkeypatch.setattr(openai_module, "claim_fenced_async_client", client_factory)
    monkeypatch.setattr(doubao_module, "claim_fenced_async_client", client_factory)
    monkeypatch.setattr(gemini_module, "claim_fenced_async_client", client_factory)
    monkeypatch.setattr(response_payloads, "claim_fenced_async_client", client_factory)


def _openai_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        openai_module,
        "settings",
        replace(
            openai_module.settings,
            openai_api_key="fake-test-key",
            openai_base_url="https://openai.invalid/v1",
            openai_image_model="gpt-image-test",
            openai_image_local_max_requests_per_minute=100,
            openai_image_local_max_outputs_per_minute=100,
            openai_image_local_queue_timeout_seconds=0.1,
        ),
    )
    openai_module._openai_image_rate_limiter.reset()


def _doubao_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        doubao_module,
        "settings",
        replace(
            doubao_module.settings,
            doubao_image_api_key="fake-test-key",
            doubao_image_base_url="https://doubao.invalid/v1",
            doubao_image_model="doubao-test",
            doubao_image_timeout_seconds=2.0,
        ),
    )


def _request(count: int = 1) -> V2ImageProviderRequest:
    return V2ImageProviderRequest(
        run_id="run_provider_claim_fence",
        prompt_plan=ImagePromptPlan(
            plan_id="plan_provider_claim_fence",
            mode="smart_enhance",
            prompt="Offline fake image request.",
            provider_parameters={"count": count},
        ),
    )


def _openai_response(request: httpx.Request, _index: int) -> httpx.Response:
    return httpx.Response(
        200,
        json={"created": 1, "data": [{"b64_json": "ZmFrZS1wbmc="}]},
        request=request,
    )


def test_openai_sdk_blocks_second_image_request_after_claim_takeover(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _openai_settings(monkeypatch)

    def first_image_then_takeover(request: httpx.Request, index: int) -> httpx.Response:
        assert index == 1
        _supersede(claim)
        return _openai_response(request, index)

    transport = _FakeTransport(first_image_then_takeover)
    _install_transport(monkeypatch, transport)
    provider = openai_module.V2OpenAIGPTImage2Provider()

    try:
        with task_queue.claimed_task(claim):
            with pytest.raises(task_queue.StaleTaskClaim):
                asyncio.run(provider.generate(_request(count=2)))
    finally:
        openai_module._openai_image_rate_limiter.reset()

    assert len(transport.sent) == 1
    assert transport.sent[0].url.path.endswith("/images/generations")


def test_openai_sdk_checks_claim_after_rate_limiter_wait(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _openai_settings(monkeypatch)
    transport = _FakeTransport(_openai_response)
    _install_transport(monkeypatch, transport)
    claim_checks = 0
    ensure_claim = task_queue.ensure_current_claim

    def count_claim_check() -> None:
        nonlocal claim_checks
        claim_checks += 1
        ensure_claim()

    monkeypatch.setattr(task_queue, "ensure_current_claim", count_claim_check)

    async def limiter_wait_then_takeover(**_kwargs):
        _supersede(claim)
        return {"wait_seconds": 0.0}

    monkeypatch.setattr(openai_module._openai_image_rate_limiter, "acquire", limiter_wait_then_takeover)
    provider = openai_module.V2OpenAIGPTImage2Provider()

    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(provider.generate(_request()))

    assert transport.sent == []
    assert claim_checks == 1


def test_openai_sdk_checks_claim_after_generation_lock_wait(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _openai_settings(monkeypatch)
    transport = _FakeTransport(_openai_response)
    _install_transport(monkeypatch, transport)
    provider = openai_module.V2OpenAIGPTImage2Provider()

    async def exercise() -> None:
        class ObservedLock(asyncio.Lock):
            def __init__(self) -> None:
                super().__init__()
                self.waiting = asyncio.Event()

            async def acquire(self) -> bool:
                if self.locked():
                    self.waiting.set()
                return await super().acquire()

        lock = ObservedLock()
        monkeypatch.setattr(openai_module, "_openai_generation_lock", lock)
        await lock.acquire()
        generation = asyncio.create_task(provider.generate(_request()))
        await lock.waiting.wait()
        _supersede(claim)
        lock.release()
        await generation

    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(exercise())

    assert transport.sent == []


def test_openai_sdk_checks_claim_after_transient_retry_backoff(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _openai_settings(monkeypatch)

    def gateway_then_takeover(request: httpx.Request, index: int) -> httpx.Response:
        assert index == 1
        return httpx.Response(502, json={"error": {"message": "fake gateway error"}}, request=request)

    transport = _FakeTransport(gateway_then_takeover)
    _install_transport(monkeypatch, transport)
    sleep_calls = 0

    async def backoff_then_takeover(_delay: float) -> None:
        nonlocal sleep_calls
        sleep_calls += 1
        _supersede(claim)

    monkeypatch.setattr(openai_module.asyncio, "sleep", backoff_then_takeover)
    provider = openai_module.V2OpenAIGPTImage2Provider()

    try:
        with task_queue.claimed_task(claim):
            with pytest.raises(task_queue.StaleTaskClaim):
                asyncio.run(provider.generate(_request()))
    finally:
        openai_module._openai_image_rate_limiter.reset()

    assert sleep_calls == 1
    assert len(transport.sent) == 1


def test_doubao_adapter_blocks_next_http_request_after_takeover(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _doubao_settings(monkeypatch)

    def first_image_then_takeover(request: httpx.Request, index: int) -> httpx.Response:
        assert index == 1
        _supersede(claim)
        return httpx.Response(
            200,
            json={"data": [{"b64_json": "ZmFrZS1wbmc="}]},
            request=request,
        )

    transport = _FakeTransport(first_image_then_takeover)
    _install_transport(monkeypatch, transport)
    provider = doubao_module.V2DoubaoImageProvider()

    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(provider.generate(_request(count=2)))

    assert len(transport.sent) == 1
    assert transport.sent[0].url.path.endswith("/images/generations")


def test_doubao_redirect_hop_is_blocked_after_claim_takeover(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _doubao_settings(monkeypatch)

    def redirect_then_takeover(request: httpx.Request, index: int) -> httpx.Response:
        assert index == 1
        _supersede(claim)
        return httpx.Response(
            302,
            headers={"Location": "https://doubao.invalid/v1/images/generations-redirected"},
            request=request,
        )

    transport = _FakeTransport(redirect_then_takeover)
    _install_transport(monkeypatch, transport)
    provider = doubao_module.V2DoubaoImageProvider()

    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(provider.generate(_request()))

    assert len(transport.sent) == 1
    assert transport.sent[0].url.path.endswith("/images/generations")


def test_doubao_output_url_download_is_claim_fenced(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    _doubao_settings(monkeypatch)

    def generation_response_then_takeover(request: httpx.Request, index: int) -> httpx.Response:
        assert index == 1
        _supersede(claim)
        return httpx.Response(
            200,
            json={"data": [{"url": "https://output.invalid/image.png"}]},
            request=request,
        )

    transport = _FakeTransport(generation_response_then_takeover)
    _install_transport(monkeypatch, transport)
    provider = doubao_module.V2DoubaoImageProvider()

    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(provider.generate(_request()))

    assert len(transport.sent) == 1
    assert transport.sent[0].url.path.endswith("/images/generations")


def test_gemini_candidate_fallback_checks_claim_before_next_request(tmp_path: Path, monkeypatch) -> None:
    claim = _configure_claim(tmp_path, monkeypatch)
    monkeypatch.setattr(
        gemini_module,
        "settings",
        replace(
            gemini_module.settings,
            gemini_image_generation_enabled=True,
            gemini_api_key="fake-test-key",
            gemini_image_model="gemini-image-test",
        ),
    )
    monkeypatch.setattr(
        gemini_module,
        "_generate_content_candidates",
        lambda: [
            ("https://gemini.invalid/candidate-one", "model-one"),
            ("https://gemini.invalid/candidate-two", "model-two"),
        ],
    )

    def not_found_then_takeover(request: httpx.Request, index: int) -> httpx.Response:
        assert index == 1
        _supersede(claim)
        return httpx.Response(404, json={"error": {"message": "fake missing model"}}, request=request)

    transport = _FakeTransport(not_found_then_takeover)
    _install_transport(monkeypatch, transport)
    provider = gemini_module.V2GeminiImageProvider()

    with task_queue.claimed_task(claim):
        with pytest.raises(task_queue.StaleTaskClaim):
            asyncio.run(provider.generate(_request()))

    assert len(transport.sent) == 1
