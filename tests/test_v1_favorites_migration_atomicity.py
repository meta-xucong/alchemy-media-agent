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


@pytest.fixture
def legacy_source(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    path = tmp_path / "favorites" / "image_favorites.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    database_path = tmp_path / "repository.sqlite3"
    tables = ("v1_favorites", "v1_favorite_state")

    def snapshot():
        connection = sqlite3.connect(database_path)
        try:
            rows = connection.execute(
                f"SELECT output_id, owner_id, created_at, updated_at FROM {tables[0]} ORDER BY output_id"
            ).fetchall()
            markers = connection.execute(f"SELECT COUNT(*) FROM {tables[1]}").fetchone()[0]
            return rows, markers
        finally:
            connection.close()

    return path, snapshot


@pytest.mark.parametrize("invalid_item", [
    None, True, "private-invalid-item", 7, [], {},
    {"output_id": None}, {"output_id": ""}, {"output_id": " \t"}, {"output_id": "bad\x00id"},
    {"output_id": 7}, {"output_id": True}, {"output_id": ["private"]},
    {"output_id": {"private": "data"}},
    {"output_id": "invalid", "created_at": {"private": "data"}},
    {"output_id": "invalid", "updated_at": False},
])
def test_v1_invalid_item_rolls_back_entire_import_and_retries(legacy_source, invalid_item):
    path, snapshot = legacy_source
    good = {"output_id": "valid-first", "veyra_user_id": 41}
    last = {"output_id": "valid-last", "veyra_user_id": 41}
    source = json.dumps({"items": [good, invalid_item, last]}).encode("utf-8")
    path.write_bytes(source)

    with pytest.raises(favorites.LegacyFavoritesImportError) as failure:
        favorites.list_favorite_ids(veyra_user_id=41)

    assert "private" not in str(failure.value)
    assert snapshot() == ([], 0)
    assert path.read_bytes() == source
    path.write_text(json.dumps({"items": [good, last]}), encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41) == {"valid-first", "valid-last"}
    assert snapshot()[1] == 1


@pytest.mark.parametrize("invalid_owner", [
    True, False, -1, -0.5, 1.5, 0.0, 41.0, "-1", "41.5", "private-owner-token", "1_000",
    [], {}, 2**63, str(2**63), float("inf"), float("nan"),
])
def test_v1_invalid_owner_never_becomes_public(legacy_source, invalid_owner):
    path, snapshot = legacy_source
    items = [
        {"output_id": "valid-first", "veyra_user_id": 41},
        {"output_id": "private-row", "veyra_user_id": invalid_owner},
    ]
    path.write_text(json.dumps({"items": items}), encoding="utf-8")

    with pytest.raises(favorites.LegacyFavoritesImportError) as failure:
        favorites.list_favorite_ids(veyra_user_id=99, include_legacy_public=True)

    assert "private-owner-token" not in str(failure.value)
    assert "private-row" not in str(failure.value)
    assert snapshot() == ([], 0)
    items[1]["veyra_user_id"] = 41
    path.write_text(json.dumps({"items": items}), encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=99, include_legacy_public=True) == set()
    assert favorites.list_favorite_ids(veyra_user_id=41) == {"valid-first", "private-row"}
    assert snapshot()[1] == 1


def test_v1_legacy_ownerless_and_integral_owners_remain_compatible(legacy_source):
    path, snapshot = legacy_source
    public = [
        {"output_id": "missing-owner"},
        *[{"output_id": f"public-{index}", "veyra_user_id": owner}
          for index, owner in enumerate([None, 0, "0", "", "  "])],
    ]
    owned = [
        {"output_id": f"owned-{index}", "veyra_user_id": owner}
        for index, owner in enumerate([41, "41", " 41 "])
    ]
    path.write_text(json.dumps({"items": public + owned}), encoding="utf-8")

    assert favorites.list_favorite_ids(veyra_user_id=99) == {item["output_id"] for item in public}
    assert favorites.list_favorite_ids(veyra_user_id=41, include_legacy_public=False) == {
        item["output_id"] for item in owned
    }
    assert len(snapshot()[0]) == len(public + owned)
    assert snapshot()[1] == 1


def test_v1_absent_source_can_be_restored_without_losing_native_favorites(legacy_source):
    path, snapshot = legacy_source
    assert favorites.list_favorite_ids(veyra_user_id=41) == set()
    assert snapshot() == ([], 0)
    favorites.set_favorite("native", True, veyra_user_id=41)
    native_rows = snapshot()[0]
    assert snapshot()[1] == 0
    source = {"items": [{"output_id": "restored", "veyra_user_id": 41}, None]}
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(favorites.LegacyFavoritesImportError):
        favorites.list_favorite_ids(veyra_user_id=41)

    assert snapshot() == (native_rows, 0)
    source["items"].pop()
    path.write_text(json.dumps(source), encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41) == {"native", "restored"}
    assert snapshot()[1] == 1


@pytest.mark.parametrize("items", [[], [{"output_id": "removed", "veyra_user_id": 41}]])
def test_v1_completed_import_never_replays_the_legacy_source(legacy_source, items):
    path, snapshot = legacy_source
    path.write_text(json.dumps({"items": items}), encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41) == {item["output_id"] for item in items}
    assert snapshot()[1] == 1
    favorites.set_favorite("removed", False, veyra_user_id=41)
    path.write_text('{"items":[{"output_id":"removed","veyra_user_id":41},null]}', encoding="utf-8")

    assert favorites.list_favorite_ids(veyra_user_id=41) == set()
    assert snapshot() == ([], 1)


@pytest.mark.parametrize("source", [
    b'{"items":[{"output_id":"private-row"}]',
    b'{"items":[{"output_id":"private-row"}],"private-token":',
    b'{"items":[{"output_id":"private-row"}]}garbage',
    b'{"items":[{"output_id":"private-row"}]}\xff',
    b'{"items":[{"output_id":"private-row"}],"items":[]}',
])
def test_v1_parser_failures_are_safe_atomic_and_repairable(legacy_source, source):
    path, snapshot = legacy_source
    path.write_bytes(source)

    with pytest.raises(favorites.LegacyFavoritesImportError) as failure:
        favorites.list_favorite_ids(veyra_user_id=41)

    assert "private" not in str(failure.value)
    assert str(path) not in str(failure.value)
    assert snapshot() == ([], 0)
    assert path.read_bytes() == source
    path.write_text('{"items":[]}', encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41) == set()
    assert snapshot() == ([], 1)


@pytest.mark.parametrize("invalid_suffix", [
    '{"output_id":"private-row","veyra_user_id":41,"veyra_user_id":null}]}',
    '{"output_id":"private-row","note":{"private-token":NaN}}]}',
    '{"output_id":"private-row","note":[Infinity]}]}',
    '{"output_id":"private-row","note":-Infinity}]}',
    '{"output_id":"private-row","note":1e999}]}',
    '{"output_id":"private-row","note":"\\ud800"}]}',
    '{"output_id":"private-row","note":{"\\udfff":0}}]}',
    '{"output_id":"private-row","note":{"x":0,"x":1}}]}',
    '{"output_id":"private-row"}],"note":1e999}',
    '{"output_id":"private-row"}],"note":"\\ud800"}',
    '{"output_id":"private-row"}],"note":0,"note":1}',
    '\u00a0{"output_id":"private-row"}]}',
])
def test_v1_strict_json_failure_midstream_rolls_back_and_retries(legacy_source, invalid_suffix):
    path, snapshot = legacy_source
    source = '{"items":[{"output_id":"first","veyra_user_id":41},' + invalid_suffix
    path.write_text(source, encoding="utf-8")

    with pytest.raises(favorites.LegacyFavoritesImportError) as failure:
        favorites.list_favorite_ids(veyra_user_id=99)

    assert "private" not in str(failure.value)
    assert snapshot() == ([], 0)
    assert path.read_text(encoding="utf-8") == source
    path.write_text('{"items":[{"output_id":"first","veyra_user_id":41}]}', encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41) == {"first"}
    assert snapshot()[1] == 1


def test_v1_duplicate_output_across_owners_and_same_owner_merge_stays_supported(legacy_source):
    path, snapshot = legacy_source
    path.write_text(json.dumps({"items": [
        {"output_id": "shared-output", "veyra_user_id": 41, "created_at": "old", "updated_at": "middle"},
        {"output_id": "shared-output", "veyra_user_id": 42, "created_at": "other"},
        {"output_id": "shared-output", "veyra_user_id": 41, "created_at": "later", "updated_at": "new"},
    ]}), encoding="utf-8")

    assert favorites.list_favorite_ids(veyra_user_id=41, include_legacy_public=False) == {"shared-output"}
    assert favorites.list_favorite_ids(veyra_user_id=42, include_legacy_public=False) == {"shared-output"}
    assert favorites.list_favorite_ids(veyra_user_id=43) == set()
    rows, markers = snapshot()
    assert sorted(rows) == [
        ("shared-output", 41, "old", "new"),
        ("shared-output", 42, "other", "other"),
    ]
    assert markers == 1


@pytest.mark.parametrize("metadata", [
    {f"field-{index}": 0 for index in range(64)},
    {"x" * (64 * 1024): 0},
])
def test_v1_root_metadata_tracking_is_bounded(legacy_source, metadata):
    path, snapshot = legacy_source
    source = {"items": [{"output_id": "first", "veyra_user_id": 41}], **metadata}
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(favorites.LegacyFavoritesImportError):
        favorites.list_favorite_ids(veyra_user_id=41)

    assert snapshot() == ([], 0)
    source = {"items": [], **{f"field-{index}": 0 for index in range(63)}}
    path.write_text(json.dumps(source), encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=41) == set()
    assert snapshot() == ([], 1)


def test_v1_source_read_error_is_safe_and_repairable(legacy_source, monkeypatch):
    path, snapshot = legacy_source
    path.write_text('{"items":[]}', encoding="utf-8")
    original_open = type(path).open

    def unreadable(source, *args, **kwargs):
        if source == path:
            raise OSError("private-source-path")
        return original_open(source, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(type(path), "open", unreadable)
        with pytest.raises(favorites.LegacyFavoritesImportError) as failure:
            favorites.list_favorite_ids(veyra_user_id=41)
        assert "private" not in str(failure.value)
        assert snapshot() == ([], 0)

    assert favorites.list_favorite_ids(veyra_user_id=41) == set()
    assert snapshot() == ([], 1)


@pytest.mark.parametrize("owner_token", [
    "9007199254740993.0", "41.00000000000000001", "1e-999", "-1e-999",
])
def test_v1_float_owner_tokens_cannot_round_into_another_owner(legacy_source, owner_token):
    path, snapshot = legacy_source
    path.write_text(
        '{"items":[{"output_id":"first","veyra_user_id":41},'
        '{"output_id":"private-row","veyra_user_id":' + owner_token + ' }]}',
        encoding="utf-8",
    )

    with pytest.raises(favorites.LegacyFavoritesImportError):
        favorites.list_favorite_ids(veyra_user_id=99)

    assert snapshot() == ([], 0)
    path.write_text('{"items":[{"output_id":"private-row","veyra_user_id":41}]}', encoding="utf-8")
    assert favorites.list_favorite_ids(veyra_user_id=99) == set()
    assert favorites.list_favorite_ids(veyra_user_id=41) == {"private-row"}
