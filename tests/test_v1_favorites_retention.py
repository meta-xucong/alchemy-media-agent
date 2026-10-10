import io
import json

from app.services.favorites import delete_favorite, list_favorite_ids, set_favorite
from app.storage import media_store
from app.services.favorites import _StreamingJSONReader


def test_v1_favorites_reader_buffer_stays_bounded_for_many_small_items():
    items = [{"output_id": f"out_{index:05d}", "note": "x" * 120} for index in range(3000)]
    payload = "[" + ",".join(json.dumps(item, separators=(",", ":")) for item in items) + "]"
    reader = _StreamingJSONReader(io.StringIO(payload))
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


def test_v1_favorites_reader_waits_for_number_token_split_at_chunk_boundary():
    token = "12345678901234567890"
    number_start = 64 * 1024 - 4
    payload = "[" + (" " * (number_start - 1)) + token + ",0]"
    reader = _StreamingJSONReader(io.StringIO(payload))

    assert list(reader.array_items()) == [int(token), 0]


def test_v1_favorites_migrate_streaming_and_query_only_requested_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(media_store, "root", tmp_path)
    legacy = tmp_path / "favorites" / "image_favorites.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(
        json.dumps(
            {
                "items": [
                    {"output_id": "public", "veyra_user_id": None},
                    {"output_id": "owned", "veyra_user_id": 7},
                    {"output_id": "other", "veyra_user_id": 8},
                ]
            }
        ),
        encoding="utf-8",
    )

    def forbidden_read_text(*_args, **_kwargs):
        raise AssertionError("V1 favorites migration must stream the old JSON")

    monkeypatch.setattr(type(legacy), "read_text", forbidden_read_text)

    assert list_favorite_ids(veyra_user_id=7, output_ids=["public", "owned", "other"]) == {
        "public",
        "owned",
    }
    assert list_favorite_ids(veyra_user_id=8, output_ids=["owned", "other"]) == {"other"}
    assert set_favorite("new", True, veyra_user_id=7)["favorite"] is True
    assert list_favorite_ids(veyra_user_id=7, output_ids=["new"]) == {"new"}
    assert delete_favorite("new") == 1
    assert legacy.exists()
