from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import threading

from app.providers.openai_image import (
    OpenAIGPTImageProvider,
    _CrossLoopAsyncSemaphore,
    _OPENAI_IMAGE_MAX_CONCURRENT_REQUESTS,
)
from alchemy_creative_agent_3_0.app.generation_router.providers import ProductionImageGenerationProvider


def test_openai_image_api_semaphore_allows_five_process_wide_requests() -> None:
    semaphore = _CrossLoopAsyncSemaphore(_OPENAI_IMAGE_MAX_CONCURRENT_REQUESTS)
    assert _OPENAI_IMAGE_MAX_CONCURRENT_REQUESTS == 5
    active = 0
    peak = 0
    state_lock = threading.Lock()
    first_five_entered = threading.Event()
    release = threading.Event()

    async def make_request() -> None:
        nonlocal active, peak
        async with semaphore:
            with state_lock:
                active += 1
                peak = max(peak, active)
                if active == 5:
                    first_five_entered.set()
            await asyncio.to_thread(release.wait)
            with state_lock:
                active -= 1

    def run_on_separate_loop() -> None:
        asyncio.run(make_request())

    with ThreadPoolExecutor(max_workers=7) as pool:
        futures = [pool.submit(run_on_separate_loop) for _ in range(7)]
        assert first_five_entered.wait(timeout=5)
        with state_lock:
            assert active == 5
        release.set()
        for future in futures:
            future.result(timeout=5)

    assert peak == 5
    assert active == 0


def test_openai_transport_retry_diagnostics_are_request_local() -> None:
    provider = OpenAIGPTImageProvider(model="gpt-image-2")

    async def record(label: str) -> list[dict[str, object]]:
        provider._begin_transport_attempt_tracking()
        provider._transport_attempt_history.append({"request": label})
        await asyncio.sleep(0)
        return list(provider._transport_attempt_history)

    async def run() -> list[list[dict[str, object]]]:
        return await asyncio.gather(record("first"), record("second"))

    assert asyncio.run(run()) == [[{"request": "first"}], [{"request": "second"}]]


def test_v3_provider_failure_retry_summary_is_thread_local() -> None:
    provider = ProductionImageGenerationProvider(output_store=object())
    both_written = threading.Barrier(2)

    def record(label: str) -> dict[str, str]:
        provider._last_provider_failure_retry_summary = {"owner": label}
        both_written.wait(timeout=5)
        return dict(provider._last_provider_failure_retry_summary)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(record, ("owner-a", "owner-b")))

    assert results == [{"owner": "owner-a"}, {"owner": "owner-b"}]
