"""Doc173 red-to-green contracts for the library-first Visual Asset model.

These tests are deliberately domain-level.  They lock ownership, explicit
project binding, immutable job snapshots and fail-closed behaviour before the
browser/API adapters are allowed to expose the new workflow.
"""

from __future__ import annotations

import base64

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.project_mode import InMemoryProjectStore
from alchemy_creative_agent_3_0.app.app_shell.routes import get_route_contracts
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    FrozenVisualAssetBindingSet,
    LibraryVisualAssetCreateRequest,
    PersistentProjectVisualAssetBindingService,
    PersistentVisualAssetLibraryCatalog,
    ProjectVisualAssetBindingRequest,
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
)
from alchemy_creative_agent_3_0.app.visual_assets.authority import VisualAssetBindingSet
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
    ecommerce_test_service,
)


_ONE_PIXEL_PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="


def _active_people_asset(catalog: VisualAssetLibraryCatalog):
    asset = catalog.create(
        owner_scope="local_default",
        request=LibraryVisualAssetCreateRequest(
            display_name="童模 A",
            asset_type="people",
            root_source_asset_id="v3_asset_ready_source",
            consent_reference="user-authorized-source",
            preparation_intent="建立这个人物的中性、可复用人物标准参考。",
        ),
    )
    return catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        version_id="pack_people_a_v1",
        approved_evidence_ids=["front", "three_quarter", "profile"],
    )


def test_doc173_library_asset_is_owned_by_library_not_a_project() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _active_people_asset(catalog)

    assert asset.owner_scope == "local_default"
    assert asset.asset_type == "people"
    assert asset.active_version_id == "pack_people_a_v1"
    assert not hasattr(asset, "project_id")


def test_doc173_first_release_rejects_future_asset_types_fail_closed() -> None:
    catalog = VisualAssetLibraryCatalog()

    with pytest.raises(ValueError, match="visual_asset_type_not_available"):
        catalog.create(
            owner_scope="local_default",
            request=LibraryVisualAssetCreateRequest(
                display_name="未来产品资产",
                asset_type="product",
                root_source_asset_id="v3_asset_ready_product",
                consent_reference="user-authorized-source",
                preparation_intent="建立产品资产。",
            ),
        )


def test_doc173_one_active_library_asset_can_bind_two_projects_explicitly() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _active_people_asset(catalog)
    bindings = ProjectVisualAssetBindingService(catalog)

    first = bindings.bind(
        owner_scope="local_default",
        project_id="project_general",
        request=ProjectVisualAssetBindingRequest(
            visual_asset_id=asset.visual_asset_id,
            selected_version_id=asset.active_version_id,
            confirm_binding=True,
        ),
    )
    second = bindings.bind(
        owner_scope="local_default",
        project_id="project_photography",
        request=ProjectVisualAssetBindingRequest(
            visual_asset_id=asset.visual_asset_id,
            selected_version_id=asset.active_version_id,
            confirm_binding=True,
        ),
    )

    assert first.visual_asset_id == second.visual_asset_id == asset.visual_asset_id
    assert first.project_id != second.project_id
    assert bindings.current(project_id="project_general").state == "valid"
    assert bindings.current(project_id="project_photography").state == "valid"


def test_doc173_invalid_or_unconfirmed_binding_blocks_without_standard_fallback() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _active_people_asset(catalog)
    bindings = ProjectVisualAssetBindingService(catalog)

    with pytest.raises(ValueError, match="visual_asset_binding_confirmation_required"):
        bindings.bind(
            owner_scope="local_default",
            project_id="project_general",
            request=ProjectVisualAssetBindingRequest(
                visual_asset_id=asset.visual_asset_id,
                selected_version_id=asset.active_version_id,
                confirm_binding=False,
            ),
        )
    with pytest.raises(ValueError, match="visual_asset_version_not_active"):
        bindings.bind(
            owner_scope="local_default",
            project_id="project_general",
            request=ProjectVisualAssetBindingRequest(
                visual_asset_id=asset.visual_asset_id,
                selected_version_id="obsolete_pack",
                confirm_binding=True,
            ),
        )


def test_doc173_job_snapshot_is_immutable_after_project_binding_changes() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _active_people_asset(catalog)
    bindings = ProjectVisualAssetBindingService(catalog)
    binding = bindings.bind(
        owner_scope="local_default",
        project_id="project_general",
        request=ProjectVisualAssetBindingRequest(
            visual_asset_id=asset.visual_asset_id,
            selected_version_id=asset.active_version_id,
            confirm_binding=True,
        ),
    )
    frozen = bindings.freeze_for_job(project_id="project_general", job_id="job_first")
    bindings.remove(
        project_id="project_general",
        binding_id=binding.binding_id,
        confirm_removal=True,
    )

    assert frozen.job_id == "job_first"
    assert frozen.bindings[0].visual_asset_id == asset.visual_asset_id
    assert bindings.current(project_id="project_general").state == "empty"


def test_doc173_unbound_project_is_standard_by_default() -> None:
    catalog = VisualAssetLibraryCatalog()
    bindings = ProjectVisualAssetBindingService(catalog)

    assert bindings.current(project_id="project_without_assets").state == "empty"
    assert catalog.list_assets(owner_scope="local_default") == []


def test_doc173_library_and_frozen_project_binding_survive_restart(tmp_path) -> None:
    root = tmp_path / "visual-asset-library"
    catalog = PersistentVisualAssetLibraryCatalog(root)
    asset = _active_people_asset(catalog)
    bindings = PersistentProjectVisualAssetBindingService(catalog, root)
    binding = bindings.bind(
        owner_scope="local_default",
        project_id="project_general",
        request=ProjectVisualAssetBindingRequest(
            visual_asset_id=asset.visual_asset_id,
            selected_version_id=asset.active_version_id,
            confirm_binding=True,
        ),
    )
    frozen = bindings.freeze_for_job(project_id="project_general", job_id="job_restart")

    restarted_catalog = PersistentVisualAssetLibraryCatalog(root)
    restarted_bindings = PersistentProjectVisualAssetBindingService(restarted_catalog, root)
    restored_asset = restarted_catalog.get(owner_scope="local_default", visual_asset_id=asset.visual_asset_id)
    restored_current = restarted_bindings.current(project_id="project_general")
    restored_frozen = restarted_bindings.frozen_for_job(project_id="project_general", job_id="job_restart")

    assert restored_asset is not None
    assert restored_asset.active_version_id == asset.active_version_id
    assert restored_current.state == "valid"
    assert restored_current.bindings[0].binding_id == binding.binding_id
    assert restored_frozen is not None
    assert restored_frozen.binding_set_id == frozen.binding_set_id


def test_doc173_library_routes_create_assets_and_bind_projects_without_legacy_write() -> None:
    legacy_service = V3ProductApiService()
    library_catalog = VisualAssetLibraryCatalog()
    bindings = ProjectVisualAssetBindingService(library_catalog)
    handlers = V3ProductRouteHandlers(
        service=legacy_service,
        project_store=InMemoryProjectStore(),
        visual_asset_library_catalog=library_catalog,
        project_visual_asset_binding_service=bindings,
    )
    project_id = handlers.post_projects({"user_goal": "使用人物资产制作一张创意图"})["project"]["project_id"]
    content = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    upload = handlers.post_uploads(
        {
            "filename": "person.png",
            "mime_type": "image/png",
            "size_bytes": len(content),
            "role": "face_reference",
        }
    )
    handlers.put_upload_content(
        upload["asset_id"],
        {"content_base64": base64.b64encode(content).decode("ascii"), "mime_type": "image/png"},
    )
    handlers.post_upload_complete(upload["asset_id"])
    created = handlers.post_visual_assets(
        {
            "display_name": "童模 A",
            "asset_type": "people",
            "root_source_asset_id": upload["asset_id"],
            "consent_reference": "user-authorized-source",
            "preparation_intent": "建立这个人物的中性、可复用人物标准参考。",
        }
    )["visual_asset"]
    # The ready-source check belongs to the lifecycle prepare path. This unit
    # test activates a reviewed library version directly to exercise only the
    # public library/project binding separation.
    active = library_catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=created["visual_asset_id"],
        version_id="pack_people_a_v1",
        approved_evidence_ids=["front", "three_quarter", "profile"],
    )
    bound = handlers.post_project_visual_asset_binding(
        project_id,
        {
            "visual_asset_id": active.visual_asset_id,
            "selected_version_id": active.active_version_id,
            "confirm_binding": True,
        },
    )

    assert bound["state"] == "valid"
    assert bound["bindings"][0]["visual_asset_id"] == active.visual_asset_id
    assert "root_source_asset_id" not in created
    assert "preparation_intent" not in created
    # New library creates never touch the legacy project-scoped catalog.
    assert legacy_service.visual_asset_catalog.list_assets(project_id) == []


def test_doc173_legacy_project_people_asset_writes_are_read_only_compatibility() -> None:
    handlers = V3ProductRouteHandlers(project_store=InMemoryProjectStore())
    project_id = handlers.post_projects({"user_goal": "历史项目兼容读取"})["project"]["project_id"]

    with pytest.raises(ValueError, match="legacy_project_people_asset_forward_write_forbidden"):
        handlers.post_project_people_asset(project_id, {})
    with pytest.raises(ValueError, match="legacy_project_people_asset_forward_write_forbidden"):
        handlers.post_project_people_asset_prepare(project_id, "people_asset_legacy", {})
    with pytest.raises(ValueError, match="legacy_project_people_asset_forward_write_forbidden"):
        handlers.post_project_people_asset_activate(project_id, "people_asset_legacy", {})


def test_doc173_public_job_rejects_legacy_professional_mode_forward_write() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="legacy_professional_mode_forward_write_forbidden"):
        service.create_creative_job(
            {
                "user_input": "制作人物创意图",
                "professional_mode": "professional",
                "people_asset_id": "people_asset_legacy",
            }
        )


def test_doc173_public_routes_expose_library_and_project_binding_surfaces() -> None:
    routes = get_route_contracts()
    assert routes["visual_assets"].endswith("/visual-assets")
    assert routes["prepare_visual_asset"].endswith("/prepare")
    assert routes["activate_visual_asset"].endswith("/activate")
    assert routes["project_visual_asset_bindings"].endswith("/visual-asset-bindings")


def test_doc173_public_library_projection_exposes_only_lifecycle_activation_facts() -> None:
    catalog = VisualAssetLibraryCatalog()
    asset = _active_people_asset(catalog)
    handlers = V3ProductRouteHandlers(visual_asset_library_catalog=catalog)

    public = handlers._visual_asset_public_record(asset)

    assert public["visual_asset_id"] == asset.visual_asset_id
    assert public["available_for_projects"] is True
    assert public["latest_preparation"] == {
        "status": "active",
        "version_id": "pack_people_a_v1",
        "user_activation_confirmed": True,
        "anchor_views": [],
    }
    assert "root_source_asset_id" not in public
    assert "preparation_intent" not in public
    assert "approved_evidence_ids" not in public


def test_doc173_new_project_job_freezes_library_binding_and_strips_legacy_mode_from_brain(tmp_path) -> None:
    provider = EcommerceRemoteBrainTestProvider()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    service = ecommerce_test_service(brain_provider=provider, output_store=output_store)
    catalog = VisualAssetLibraryCatalog()
    bindings = ProjectVisualAssetBindingService(catalog)
    handlers = V3ProductRouteHandlers(
        service=service,
        project_store=InMemoryProjectStore(),
        visual_asset_library_catalog=catalog,
        project_visual_asset_binding_service=bindings,
    )
    rendered_anchor = output_store.save_base64_output(
        job_id="job_anchor",
        candidate_id="candidate_anchor",
        asset_id="asset_anchor",
        provider="fixture",
        model="fixture",
        encoded_image=_ONE_PIXEL_PNG,
    )
    asset = _active_people_asset(catalog)
    asset = catalog.activate_version(
        owner_scope="local_default",
        visual_asset_id=asset.visual_asset_id,
        version_id="pack_people_a_v2",
        approved_evidence_ids=[rendered_anchor.output_id],
    )
    project_id = handlers.post_projects({"user_goal": "制作一张人物品牌肖像"})["project"]["project_id"]
    handlers.post_project_visual_asset_binding(
        project_id,
        {
            "visual_asset_id": asset.visual_asset_id,
            "selected_version_id": asset.active_version_id,
            "confirm_binding": True,
        },
    )

    status = handlers.post_project_job(
        project_id,
        {"template_id": "general_template", "user_input": "制作一张自然、简洁的人物肖像"},
    )
    record = service.get_job_record(status["job_id"])

    assert record is not None
    frozen = record.request.metadata["frozen_visual_asset_binding_set"]
    assert frozen["job_id"] == status["job_id"]
    assert frozen["bindings"][0]["visual_asset_id"] == asset.visual_asset_id
    assert record.request.metadata["visual_asset_library_reference_assets"][0]["output_id"] == rendered_anchor.output_id
    assert "professional_mode" not in record.request.metadata
    assert "people_asset_id" not in record.request.metadata
    brain_metadata = provider.requests[0]["metadata"]
    assert brain_metadata["visual_asset_library_binding"]["claims"][0]["asset_id"] == asset.visual_asset_id
    assert "frozen_visual_asset_binding_set" not in brain_metadata
    assert "visual_asset_library_reference_assets" not in brain_metadata
    assert "professional_mode" not in brain_metadata


def test_doc173_browser_cannot_inject_a_frozen_library_snapshot() -> None:
    service = V3ProductApiService()

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service.create_job(
            {
                "user_input": "创建一张图",
                "metadata": {"frozen_visual_asset_binding_set": {"state": "empty"}},
            }
        )


def test_doc173_historical_library_snapshot_remains_readable_but_cannot_execute_without_evidence() -> None:
    snapshot = FrozenVisualAssetBindingSet.model_validate(
        {
            "binding_set_id": "frozen_legacy",
            "project_id": "project_legacy",
            "job_id": "job_legacy",
            "state": "valid",
            "bindings": [
                {
                    "binding_id": "binding_legacy",
                    "project_id": "project_legacy",
                    "visual_asset_id": "visual_asset_legacy",
                    "selected_version_id": "version_legacy",
                    "owner_scope": "local_default",
                    "user_confirmed": True,
                    "created_at": "2026-07-19T00:00:00+00:00",
                }
            ],
        }
    )

    assert snapshot.bindings[0].approved_evidence_ids == []
    with pytest.raises(ValueError, match="at least 1 item"):
        VisualAssetBindingSet.from_library_snapshot(snapshot)
