from __future__ import annotations

import base64

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.visual_assets import (
    AnchorPackPreparationResult,
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PersistentVisualAssetCatalog,
    RootSourceProvenance,
)


def _pack(people_asset_id: str, project_id: str, root_source_asset_id: str) -> IdentityAnchorPackVersion:
    views = [
        AnchorView(
            view_id=f"view_{role}",
            view_role=role,
            output_id=f"output_{role}",
            source_candidate_ids=[f"candidate_{role}"],
            identity_scores=IdentityScoreSummary(
                same_face_score=0.98,
                distinctive_feature_score=0.96,
                human_realism_score=0.92,
                visual_quality_score=0.90,
            ),
        )
        for role in ("standard_front", "three_quarter", "profile")
    ]
    return IdentityAnchorPackVersion(
        pack_version_id="pack_child_v1",
        people_asset_id=people_asset_id,
        status="active",
        anchor_views=views,
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id=root_source_asset_id,
            project_id=project_id,
            consent_reference="user-authorized-child-source-20260718",
        ),
        user_activation_confirmed=True,
    )


def _handlers(tmp_path, *, anchor_pack_preparation_host=None):
    catalog = PersistentVisualAssetCatalog(tmp_path / "visual-assets")
    service = V3ProductApiService(visual_asset_catalog=catalog)
    content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    upload = service.create_uploaded_asset(
        {
            "filename": "child.png",
            "mime_type": "image/png",
            "size_bytes": len(content),
            "role": "face_reference",
        }
    )
    assert service.store_uploaded_asset_content(
        upload.asset_id,
        {"content_base64": base64.b64encode(content).decode("ascii"), "mime_type": "image/png"},
    ) is not None
    assert service.complete_uploaded_asset(upload.asset_id) is not None
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=InMemoryProjectStore(),
        anchor_pack_preparation_host=anchor_pack_preparation_host,
    )
    project = handlers.post_projects({"user_goal": "Professional child face asset"})["project"]
    return handlers, catalog, project["project_id"], upload.asset_id


class _PreparationHost:
    def __init__(self, root_source_asset_id: str, catalog: PersistentVisualAssetCatalog) -> None:
        self.root_source_asset_id = root_source_asset_id
        self.catalog = catalog
        self.calls = []

    def prepare(self, *, project_id, people_asset, root_source_provenance):
        self.calls.append((project_id, people_asset.people_asset_id, root_source_provenance.source_asset_id))
        result = AnchorPackPreparationResult(
            status="review",
            pack=_pack(people_asset.people_asset_id, project_id, self.root_source_asset_id).model_copy(
                update={"status": "review", "user_activation_confirmed": False}
            ),
            attempts=[],
            winner_candidate_id="candidate_standard_front_3",
        )
        self.catalog.save_pack(result.pack, project_id=project_id, event_type="review")
        return result

    def activate(self, pack, *, confirmed: bool):
        assert confirmed is True
        active = pack.model_copy(update={"status": "active", "user_activation_confirmed": True})
        self.catalog.save_pack(active, project_id=active.root_source_provenance.project_id, event_type="activate")
        return active


def test_people_asset_formal_entry_persists_project_scoped_draft(tmp_path) -> None:
    handlers, catalog, project_id, root_source_asset_id = _handlers(tmp_path)

    created = handlers.post_project_people_asset(
        project_id,
        {
            "people_asset_id": "child_asset",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-child-source-20260718",
        },
    )

    assert created["lifecycle_state"] == "draft"
    assert created["people_asset"]["status"] == "draft"
    restored = PersistentVisualAssetCatalog(tmp_path / "visual-assets")
    assert restored.get(project_id, "child_asset").status == "draft"
    assert restored.get(project_id, "child_asset").root_source_provenance.source_asset_id == root_source_asset_id
    assert restored.list_history(project_id, "child_asset")[0].event_type == "create"
    assert catalog.list_assets(project_id)[0].people_asset_id == "child_asset"


def test_people_asset_formal_entry_rejects_non_ready_root_source(tmp_path) -> None:
    handlers, _, project_id, _ = _handlers(tmp_path)
    with pytest.raises(ValueError, match="root_source_asset_not_ready"):
        handlers.post_project_people_asset(
            project_id,
            {
                "people_asset_id": "child_asset",
                "root_source_asset_id": "v3_asset_0000000000000000",
                "consent_reference": "user-authorized-child-source-20260718",
            },
        )


def test_people_asset_prepare_route_fails_closed_without_shared_host(tmp_path) -> None:
    handlers, _, project_id, root_source_asset_id = _handlers(tmp_path)
    handlers.post_project_people_asset(
        project_id,
        {
            "people_asset_id": "child_asset",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-child-source-20260718",
        },
    )
    with pytest.raises(RuntimeError, match="professional_anchor_pack_prepare_unavailable"):
        handlers.post_project_people_asset_prepare(project_id, "child_asset", {})


def test_people_asset_prepare_route_uses_injected_shared_host_and_preserves_binding(tmp_path) -> None:
    handlers, _, project_id, root_source_asset_id = _handlers(tmp_path)
    host = _PreparationHost(root_source_asset_id, handlers.service.visual_asset_catalog)
    # Recreate the facade with the same service/catalog and the explicit host;
    # no route is allowed to create candidates or prompt evidence itself.
    handlers = V3ProductRouteHandlers(
        service=handlers.service,
        project_store=handlers.project_service.project_store,
        anchor_pack_preparation_host=host,
    )
    handlers.post_project_people_asset(
        project_id,
        {
            "people_asset_id": "child_asset",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-child-source-20260718",
        },
    )
    prepared = handlers.post_project_people_asset_prepare(project_id, "child_asset", {})
    assert prepared["preparation"]["status"] == "review"
    assert prepared["preparation"]["pack"]["status"] == "review"
    assert host.calls == [(project_id, "child_asset", root_source_asset_id)]
    activated = handlers.post_project_people_asset_activate(
        project_id,
        "child_asset",
        {"pack_version_id": "pack_child_v1", "confirm_activation": True},
    )
    assert activated["lifecycle_state"] == "active"
    assert activated["people_asset"]["active_pack_version_id"] == "pack_child_v1"


def test_people_asset_activation_requires_a_complete_pack_and_explicit_confirmation(tmp_path) -> None:
    handlers, catalog, project_id, root_source_asset_id = _handlers(tmp_path)
    handlers.post_project_people_asset(
        project_id,
        {
            "people_asset_id": "child_asset",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-child-source-20260718",
        },
    )
    catalog.save_pack(_pack("child_asset", project_id, root_source_asset_id), project_id=project_id, event_type="activate")

    with pytest.raises(ValueError, match="explicit user confirmation"):
        handlers.post_project_people_asset_activate(
            project_id,
            "child_asset",
            {"pack_version_id": "pack_child_v1", "confirm_activation": False},
        )

    activated = handlers.post_project_people_asset_activate(
        project_id,
        "child_asset",
        {"pack_version_id": "pack_child_v1", "confirm_activation": True},
    )
    assert activated["lifecycle_state"] == "active"
    assert activated["people_asset"]["active_pack_version_id"] == "pack_child_v1"
    assert activated["people_asset"]["face_identity_module"]["status"] == "active"
    assert [item.event_type for item in catalog.list_history(project_id, "child_asset")] == [
        "create",
        "activate",
    ]


def test_people_asset_activation_rejects_missing_or_unreviewed_pack(tmp_path) -> None:
    handlers, _, project_id, root_source_asset_id = _handlers(tmp_path)
    handlers.post_project_people_asset(
        project_id,
        {
            "people_asset_id": "child_asset",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-child-source-20260718",
        },
    )

    with pytest.raises(KeyError, match="pack_not_found"):
        handlers.post_project_people_asset_activate(
            project_id,
            "child_asset",
            {"pack_version_id": "missing", "confirm_activation": True},
        )


def test_people_asset_activation_rejects_pack_with_different_root(tmp_path) -> None:
    handlers, catalog, project_id, root_source_asset_id = _handlers(tmp_path)
    handlers.post_project_people_asset(
        project_id,
        {
            "people_asset_id": "child_asset",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-child-source-20260718",
        },
    )
    wrong_root = _pack("child_asset", project_id, root_source_asset_id).model_copy(
        update={
            "root_source_provenance": RootSourceProvenance(
                source_type="uploaded_portrait",
                source_asset_id="other_portrait",
                project_id=project_id,
                consent_reference="other-consent",
            )
        }
    )
    catalog.save_pack(wrong_root, project_id=project_id, event_type="activate")

    with pytest.raises(ValueError, match="root does not match"):
        handlers.post_project_people_asset_activate(
            project_id,
            "child_asset",
            {"pack_version_id": "pack_child_v1", "confirm_activation": True},
        )


def test_standard_job_does_not_consult_people_asset_lifecycle(tmp_path) -> None:
    handlers, _, project_id, _ = _handlers(tmp_path)
    result = handlers.post_jobs({"user_input": "Create a simple still life."})
    assert result["status"] == "planned"
    assert handlers.get_project_people_assets(project_id)["people_assets"] == []
