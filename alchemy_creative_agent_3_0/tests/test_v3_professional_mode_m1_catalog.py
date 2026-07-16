from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.visual_assets.catalog import PersistentVisualAssetCatalog
from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    FaceIdentityModule,
    PeopleAsset,
)


def _asset(asset_id: str, project_id: str, *, status: str = "draft") -> PeopleAsset:
    return PeopleAsset(
        people_asset_id=asset_id,
        project_id=project_id,
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id=f"module_{asset_id}",
            people_asset_id=asset_id,
            status="draft",
        ),
        status=status,
    )


def _active_asset(asset_id: str, project_id: str) -> PeopleAsset:
    asset = _asset(asset_id, project_id)
    module = asset.face_identity_module.model_copy(update={"status": "active", "active_version_id": "pack_1"})
    return asset.model_copy(
        update={
            "face_identity_module": module,
            "active_pack_version_id": "pack_1",
            "status": "active",
        }
    )


def test_project_catalog_allows_multiple_assets_but_isolates_projects(tmp_path) -> None:
    catalog = PersistentVisualAssetCatalog(tmp_path)
    first = _asset("person_1", "project_1")
    second = _asset("person_2", "project_1")

    catalog.save(first, event_type="create")
    catalog.save(second, event_type="create")

    assert [item.people_asset_id for item in catalog.list_assets("project_1")] == ["person_1", "person_2"]
    assert catalog.get("project_2", "person_1") is None
    with pytest.raises(ValueError, match="same project"):
        catalog.save(_asset("person_3", "project_2"), project_id="project_1", event_type="create")


def test_catalog_history_is_append_only_and_active_pointer_is_reversible(tmp_path) -> None:
    catalog = PersistentVisualAssetCatalog(tmp_path)
    draft = _asset("person_1", "project_1")
    active = _active_asset("person_1", "project_1")

    catalog.save(draft, event_type="create")
    catalog.save(active, event_type="activate")

    history = catalog.list_history("project_1", "person_1")
    assert [item.event_type for item in history] == ["create", "activate"]
    assert catalog.get("project_1", "person_1").status == "active"

    superseded = active.model_copy(update={"status": "superseded"})
    catalog.save(superseded, event_type="supersede")
    assert [item.event_type for item in catalog.list_history("project_1", "person_1")] == [
        "create",
        "activate",
        "supersede",
    ]


def test_catalog_persists_and_restores_metadata_only_records(tmp_path) -> None:
    catalog = PersistentVisualAssetCatalog(tmp_path)
    catalog.save(_asset("person_1", "project_1"), event_type="create")

    restored = PersistentVisualAssetCatalog(tmp_path)
    loaded = restored.get("project_1", "person_1")
    assert loaded is not None
    assert loaded.people_asset_id == "person_1"
    assert len(restored.list_history("project_1", "person_1")) == 1

    raw = "\n".join(path.read_text(encoding="utf-8") for path in tmp_path.rglob("*.json"))
    assert "image_bytes" not in raw
    assert "embedding" not in raw
    assert "provider_prompt" not in raw
    assert "file_path" not in raw


def test_catalog_does_not_accept_cross_project_pack_or_asset_history(tmp_path) -> None:
    catalog = PersistentVisualAssetCatalog(tmp_path)
    asset = _asset("person_1", "project_1")
    catalog.save(asset, event_type="create")

    with pytest.raises(ValueError, match="same project"):
        catalog.save(asset, project_id="project_other", event_type="update")

    assert catalog.list_history("project_other", "person_1") == []
