from __future__ import annotations

import io
import json
import sqlite3
import threading

import pytest

from app.services import favorites


def test_v2_favorites_reader_buffer_stays_bounded_for_many_small_items():
    items = [{"output_id": f"out_{index:05d}", "note": "x" * 120} for index in range(3000)]
    payload = "[" + ",".join(json.dumps(item, separators=(",", ":")) for item in items) + "]"
    reader = favorites._StreamingJSONReader(io.StringIO(payload))
    maximum_buffer = 0
    original_fill = reader._fill

    def measured_fill():
        nonlocal maximum_buffer
        result = original_fill()
        maximum_buffer = max(maximum_buffer, len(reader.buffer))
        return result

    reader._fill = measured_fill
    reader_items = list(reader.array_items())

    assert len(payload) > 400_000
    assert len(reader_items) == len(items)
    assert maximum_buffer < 80_000


def test_v2_truncated_favorites_import_can_be_repaired_and_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "favorites_path", lambda: tmp_path / "image_favorites.json")
    path = tmp_path / "image_favorites.json"
    output_id = "outprivate123456789"
    path.write_text(json.dumps({"items": [{"output_id": output_id, "veyra_user_id": 41}]})[:-1], encoding="utf-8")

    with pytest.raises(ValueError):
        favorites.list_favorite_ids(include_all=True)

    path.write_text(json.dumps({"items": [{"output_id": output_id, "veyra_user_id": 41}]}), encoding="utf-8")
    assert favorites.list_favorite_ids(include_all=True) == {output_id}


def test_v2_parallel_first_favorites_reads_import_once_without_losing_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(favorites, "favorites_path", lambda: tmp_path / "image_favorites.json")
    path = tmp_path / "image_favorites.json"
    output_ids = ["out_parallel_import_a", "out_parallel_import_b"]
    path.write_text(json.dumps({"items": [{"output_id": item, "veyra_user_id": 41} for item in output_ids]}), encoding="utf-8")
    favorites.list_favorite_ids(include_all=True)
    connection = sqlite3.connect(favorites._database_path())
    try:
        connection.execute("DELETE FROM favorite_migrations")
        connection.execute("DELETE FROM favorites")
        connection.commit()
    finally:
        connection.close()
    results = []
    errors = []

    def read():
        try:
            results.append(favorites.list_favorite_ids(include_all=True))
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=read) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
        assert not thread.is_alive()

    assert errors == []
    assert results == [set(output_ids)] * 4
