import json

from app.services.favorites import delete_favorite, list_favorite_ids, set_favorite
from app.storage import media_store


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
