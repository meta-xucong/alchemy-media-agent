from __future__ import annotations

from typing import Any

import httpx


async def _check_claim_before_request(_request: httpx.Request) -> None:
    # Import lazily so the provider transport can be imported without loading
    # the queue service (which itself imports provider-independent services).
    from app.services import task_queue

    task_queue.ensure_current_claim()


def claim_fenced_async_client(**kwargs: Any) -> httpx.AsyncClient:
    """Build an HTTPX client that fences each outbound request by its V2 claim."""

    event_hooks = dict(kwargs.pop("event_hooks", {}) or {})
    request_hooks = list(event_hooks.get("request", ()))
    event_hooks["request"] = [_check_claim_before_request, *request_hooks]
    return httpx.AsyncClient(event_hooks=event_hooks, **kwargs)


def raise_if_stale_task_claim(exc: BaseException) -> None:
    """Recover the queue exception if an SDK wraps it as a connection error."""

    from app.services.task_queue import StaleTaskClaim

    current: BaseException | None = exc
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        if isinstance(current, StaleTaskClaim):
            raise current
        seen.add(id(current))
        current = current.__cause__ or current.__context__
