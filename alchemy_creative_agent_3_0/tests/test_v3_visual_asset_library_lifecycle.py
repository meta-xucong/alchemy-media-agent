from __future__ import annotations

import base64

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.visual_assets import (
    AnchorPackPreparationResult,
    AnchorView,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PersistentVisualAssetLibraryCatalog,
    RootSourceProvenance,
)


PREPARATION_INTENT = (
    "Establish a reusable, age-appropriate identity asset with natural human "
    "materiality while each future project owns its presentation and styling."
)


def _pack(visual_asset_id: str, staging_scope: str, root_source_asset_id: str) -> IdentityAnchorPackVersion:
    return IdentityAnchorPackVersion(
        pack_version_id="pack_library_child_v1",
        people_asset_id=visual_asset_id,
        status="review",
        anchor_views=[
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
        ],
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id=root_source_asset_id,
            project_id=staging_scope,
            consent_reference="user-authorized-source-20260719",
        ),
        user_activation_confirmed=False,
    )


class _PreparationHost:
    def __init__(self, root_source_asset_id: str) -> None:
        self.root_source_asset_id = root_source_asset_id
        self.calls: list[tuple[str, str, str, str]] = []

    def prepare(self, *, project_id, people_asset, root_source_provenance):
        self.calls.append(
            (
                project_id,
                people_asset.people_asset_id,
                root_source_provenance.source_asset_id,
                people_asset.preparation_intent,
            )
        )
        return AnchorPackPreparationResult(
            status="review",
            pack=_pack(people_asset.people_asset_id, project_id, self.root_source_asset_id),
            attempts=[],
            winner_candidate_id="candidate_standard_front_3",
        )

    def activate(self, pack, *, confirmed: bool):
        assert confirmed is True
        return pack.model_copy(update={"status": "active", "user_activation_confirmed": True})


def _handlers(tmp_path, *, anchor_pack_preparation_host=None):
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path / "visual-asset-library")
    service = V3ProductApiService()
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
        visual_asset_library_catalog=catalog,
    )
    project = handlers.post_projects({"user_goal": "Bind one reusable visual asset"})["project"]
    return handlers, catalog, project["project_id"], upload.asset_id


def _create_library_asset(handlers: V3ProductRouteHandlers, root_source_asset_id: str) -> dict[str, object]:
    return handlers.post_visual_assets(
        {
            "display_name": "童模 A",
            "asset_type": "people",
            "root_source_asset_id": root_source_asset_id,
            "consent_reference": "user-authorized-source-20260719",
            "preparation_intent": PREPARATION_INTENT,
        }
    )["visual_asset"]


def test_library_asset_formal_entry_persists_user_scoped_draft(tmp_path) -> None:
    handlers, catalog, _, root_source_asset_id = _handlers(tmp_path)

    created = _create_library_asset(handlers, root_source_asset_id)
    visual_asset_id = str(created["visual_asset_id"])

    assert created["lifecycle_status"] == "draft"
    restored = PersistentVisualAssetLibraryCatalog(tmp_path / "visual-asset-library")
    asset = restored.get(owner_scope="local_default", visual_asset_id=visual_asset_id)
    assert asset is not None
    assert asset.lifecycle_status == "draft"
    assert asset.root_source_provenance.source_asset_id == root_source_asset_id
    assert asset.preparation_intent == PREPARATION_INTENT
    assert catalog.list_assets(owner_scope="local_default")[0].visual_asset_id == visual_asset_id


def test_library_asset_rejects_non_ready_root_source(tmp_path) -> None:
    handlers, _, _, _ = _handlers(tmp_path)

    with pytest.raises(ValueError, match="root_source_asset_not_ready"):
        _create_library_asset(handlers, "v3_asset_not_ready")


def test_library_asset_requires_immutable_preparation_intent(tmp_path) -> None:
    handlers, _, _, root_source_asset_id = _handlers(tmp_path)

    with pytest.raises(ValueError, match="preparation_intent"):
        handlers.post_visual_assets(
            {
                "display_name": "童模 A",
                "asset_type": "people",
                "root_source_asset_id": root_source_asset_id,
                "consent_reference": "user-authorized-source-20260719",
            }
        )


def test_library_prepare_fails_closed_without_shared_host(tmp_path) -> None:
    handlers, _, _, root_source_asset_id = _handlers(tmp_path)
    created = _create_library_asset(handlers, root_source_asset_id)

    with pytest.raises(RuntimeError, match="visual_asset_prepare_unavailable"):
        handlers.post_visual_asset_prepare(str(created["visual_asset_id"]), {})


def test_library_prepare_activate_and_project_binding_reuse_shared_host(tmp_path) -> None:
    handlers, _, project_id, root_source_asset_id = _handlers(tmp_path)
    host = _PreparationHost(root_source_asset_id)
    handlers = V3ProductRouteHandlers(
        service=handlers.service,
        project_store=handlers.project_service.project_store,
        anchor_pack_preparation_host=host,
        visual_asset_library_catalog=handlers.visual_asset_library_catalog,
    )
    created = _create_library_asset(handlers, root_source_asset_id)
    visual_asset_id = str(created["visual_asset_id"])

    with pytest.raises(ValueError, match="visual_asset_prepare_payload_must_be_empty"):
        handlers.post_visual_asset_prepare(visual_asset_id, {"prompt": "caller input is not accepted"})
    prepared = handlers.post_visual_asset_prepare(visual_asset_id, {})["visual_asset"]
    preparation = prepared["latest_preparation"]
    assert preparation["status"] == "review"
    assert len(host.calls) == 1
    staging_scope, host_asset_id, host_root_asset_id, host_intent = host.calls[0]
    assert staging_scope.startswith("library_")
    assert host_asset_id == visual_asset_id
    assert host_root_asset_id == root_source_asset_id
    assert host_intent == PREPARATION_INTENT

    activated = handlers.post_visual_asset_activate(
        visual_asset_id,
        {"version_id": preparation["version_id"], "confirm_activation": True},
    )["visual_asset"]
    assert activated["lifecycle_status"] == "active"
    binding = handlers.post_project_visual_asset_binding(
        project_id,
        {
            "visual_asset_id": visual_asset_id,
            "selected_version_id": preparation["version_id"],
            "confirm_binding": True,
        },
    )
    assert binding["state"] == "valid"
    assert binding["bindings"][0]["visual_asset_id"] == visual_asset_id


def test_library_activation_requires_explicit_confirmation_and_known_review_version(tmp_path) -> None:
    handlers, _, _, root_source_asset_id = _handlers(tmp_path)
    host = _PreparationHost(root_source_asset_id)
    handlers = V3ProductRouteHandlers(
        service=handlers.service,
        project_store=handlers.project_service.project_store,
        anchor_pack_preparation_host=host,
        visual_asset_library_catalog=handlers.visual_asset_library_catalog,
    )
    created = _create_library_asset(handlers, root_source_asset_id)
    visual_asset_id = str(created["visual_asset_id"])

    with pytest.raises(ValueError, match="visual_asset_version_not_ready_for_activation"):
        handlers.post_visual_asset_activate(
            visual_asset_id,
            {"version_id": "missing", "confirm_activation": True},
        )
    prepared = handlers.post_visual_asset_prepare(visual_asset_id, {})["visual_asset"]
    with pytest.raises(ValueError, match="visual_asset_activation_confirmation_required"):
        handlers.post_visual_asset_activate(
            visual_asset_id,
            {"version_id": prepared["latest_preparation"]["version_id"], "confirm_activation": False},
        )


def test_legacy_project_people_asset_surface_is_read_only(tmp_path) -> None:
    handlers, _, project_id, _ = _handlers(tmp_path)

    assert handlers.get_project_people_assets(project_id)["people_assets"] == []
    with pytest.raises(ValueError, match="legacy_project_people_asset_forward_write_forbidden"):
        handlers.post_project_people_asset(project_id, {})
    with pytest.raises(ValueError, match="legacy_project_people_asset_forward_write_forbidden"):
        handlers.post_project_people_asset_prepare(project_id, "legacy_asset", {})
    with pytest.raises(ValueError, match="legacy_project_people_asset_forward_write_forbidden"):
        handlers.post_project_people_asset_activate(project_id, "legacy_asset", {})


def test_standard_job_does_not_consult_visual_asset_library(tmp_path) -> None:
    handlers, _, project_id, _ = _handlers(tmp_path)

    result = handlers.post_jobs({"user_input": "Create a simple still life."})
    assert result["status"] == "planned"
    assert handlers.get_project_visual_asset_bindings(project_id)["state"] == "empty"
