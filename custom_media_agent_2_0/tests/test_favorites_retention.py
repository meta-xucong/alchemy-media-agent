import json
from types import SimpleNamespace

import app.services.favorites as favorites


def test_favorites_import_is_streamed_and_queries_are_scoped(tmp_path, monkeypatch):
    legacy = tmp_path / "image_favorites.json"
    legacy.write_text(
        json.dumps(
            {
                "items": [
                    {"output_id": "shared", "veyra_user_id": None, "created_at": "old"},
                    {"output_id": "owned", "veyra_user_id": 7, "created_at": "old"},
                    {"output_id": "other", "veyra_user_id": 8, "created_at": "old"},
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        favorites,
        "settings",
        SimpleNamespace(data_dir=tmp_path, veyra_auth_enabled=True),
    )

    def forbidden_read_text(*_args, **_kwargs):
        raise AssertionError("favorites migration must stream the legacy file")

    monkeypatch.setattr(type(legacy), "read_text", forbidden_read_text)

    assert favorites.list_favorite_ids(veyra_user_id=7, output_ids=["shared", "owned", "other"]) == {
        "shared",
        "owned",
    }
    assert favorites.list_favorite_ids(veyra_user_id=8, output_ids=["owned", "other"]) == {"other"}
    assert legacy.exists()

    favorites.set_favorite("new", True, veyra_user_id=7)
    assert favorites.list_favorite_ids(veyra_user_id=7, output_ids=["new"]) == {"new"}
    assert favorites.delete_favorite("new") == 1
