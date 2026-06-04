from __future__ import annotations

import json
from collections.abc import Iterable

from app.repositories import repository


def format_sse_events(session_id: str) -> Iterable[str]:
    events = repository.list_events(session_id)
    if not events:
        yield 'event: heartbeat\ndata: {"ok": true}\n\n'
        return
    for event in events:
        yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
