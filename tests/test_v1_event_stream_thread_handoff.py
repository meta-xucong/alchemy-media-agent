from __future__ import annotations

import threading

from app.repositories.memory import MemoryRepository


def test_event_iterator_does_not_reuse_sqlite_cursor_across_worker_threads(tmp_path):
    repository = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    for index in range(3):
        repository.append_event("session-1", f"event-{index}", {"index": index})
    events = repository.iter_events("session-1")
    results = []
    errors = []

    def take_next():
        try:
            results.append(next(events))
        except Exception as exc:  # capture the actual cross-thread iterator failure
            errors.append(exc)

    for _ in range(3):
        worker = threading.Thread(target=take_next)
        worker.start()
        worker.join(timeout=2)
        assert not worker.is_alive()

    assert errors == []
    assert [event["event"] for event in results] == ["event-0", "event-1", "event-2"]


def test_event_iterator_batches_more_than_128_and_excludes_events_after_snapshot(tmp_path):
    repository = MemoryRepository(database_path=tmp_path / "v1.sqlite3")
    snapshot_count = 130
    for index in range(snapshot_count):
        repository.append_event("session-snapshot", f"event-{index}", {"index": index})

    events = repository.iter_events("session-snapshot")
    first = next(events)  # Captures the upper event ID for this stream snapshot.
    repository.append_event("session-snapshot", "event-after-snapshot", {"index": snapshot_count})
    collected = [first, *events]

    assert len(collected) == snapshot_count
    assert [event["data"]["index"] for event in collected] == list(range(snapshot_count))
    assert collected[-1]["event"] == "event-129"
