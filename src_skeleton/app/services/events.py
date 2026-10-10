from __future__ import annotations

import json
from collections.abc import Iterable
from itertools import chain

from app.repositories import repository


def format_sse_events(session_id: str) -> Iterable[str]:
    events = iter(repository.iter_events(session_id))
    try:
        first_event = next(events)
    except StopIteration:
        yield 'event: heartbeat\ndata: {"ok": true}\n\n'
        return
    for event in chain((first_event,), events):
        yield f"event: {event['event']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
