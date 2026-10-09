from __future__ import annotations

import json
import sqlite3
import threading

import pytest

from app.services import favorites
from app.storage import media_store


def test_v1_truncated_favorites_import_can_be_repaired_and_retried(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    path = tmp_path / "favorites" / "image_favorites.json"
    path.parent.mkdir(parents=True)
    output_id = "outprivate123456789"
    path.write_text(json.dumps({"items": [{"output_id": output_id, "veyra_user_id": 41}]})[:-1], encoding="utf-8")

    with pytest.raises(ValueError):
        favorites.list_favorite_ids(veyra_user_id=41, include_legacy_public=True)

    path.write_text(json.dumps({"items": [{"output_id": output_id, "veyra_user_id": 41}]}), encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41, include_legacy_public=True) == {output_id}


def test_v1_parallel_first_favorites_reads_import_once_without_losing_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    path = tmp_path / "favorites" / "image_favorites.json"
    path.parent.mkdir(parents=True)
    output_ids = ["out_parallel_import_a", "out_parallel_import_b"]
    path.write_text(json.dumps({"items": [{"output_id": item, "veyra_user_id": 41} for item in output_ids]}), encoding="utf-8")
    favorites.list_favorite_ids(veyra_user_id=41, include_legacy_public=True)
    database_path = media_store.root / "repository.sqlite3"
    connection = sqlite3.connect(database_path)
    try:
        connection.execute("DELETE FROM v1_favorite_state")
        connection.execute("DELETE FROM v1_favorites")
        connection.commit()
    finally:
        connection.close()
    results = []
    errors = []

    def read():
        try:
            results.append(favorites.list_favorite_ids(veyra_user_id=41, include_legacy_public=True))
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
