"""Doc173 red-to-green contracts for the library-first Visual Asset model.

These tests are deliberately domain-level.  They lock ownership, explicit
project binding, immutable job snapshots and fail-closed behaviour before the
browser/API adapters are allowed to expose the new workflow.
"""

from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryVisualAssetCreateRequest,
    ProjectVisualAssetBindingRequest,
    ProjectVisualAssetBindingService,
    VisualAssetLibraryCatalog,
)


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
