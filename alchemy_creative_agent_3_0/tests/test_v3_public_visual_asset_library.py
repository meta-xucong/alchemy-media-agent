from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.product_api.route_handlers import (
    PUBLIC_VISUAL_ASSET_OWNER_SCOPE,
    V3ProductRouteHandlers,
)
from alchemy_creative_agent_3_0.app.visual_assets.library import (
    LibraryRootSourceProvenance,
    PersistentVisualAssetLibraryCatalog,
    VisualAsset,
    VisualAssetVersion,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import CharacterCardState


def _active_asset(*, owner_scope: str, visual_asset_id: str) -> VisualAsset:
    provenance = LibraryRootSourceProvenance(
        source_asset_id=f"source_{visual_asset_id}",
        consent_reference="server_published_visual_asset",
    )
    version = VisualAssetVersion(
        version_id=f"version_{visual_asset_id}",
        visual_asset_id=visual_asset_id,
        lifecycle_status="active",
        approved_evidence_ids=["published_review_receipt"],
        activation_confirmed=True,
        immutable_source_provenance=provenance,
    )
    return VisualAsset(
        visual_asset_id=visual_asset_id,
        asset_type="people",
        display_name="Published Character Card",
        owner_scope=owner_scope,
        lifecycle_status="active",
        root_source_provenance=provenance,
        preparation_intent="Server-published reviewed character card",
        active_version_id=version.version_id,
        versions=[version],
        created_at="2026-08-07T00:00:00Z",
        updated_at="2026-08-07T00:00:00Z",
        character_card=CharacterCardState.initial(card_version_id="published_card"),
    )


def test_authenticated_asset_list_includes_public_card_without_cross_user_assets(tmp_path):
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    public_asset = _active_asset(
        owner_scope=PUBLIC_VISUAL_ASSET_OWNER_SCOPE,
        visual_asset_id="visual_asset_public_card",
    )
    private_asset = _active_asset(
        owner_scope="v3_user_8",
        visual_asset_id="visual_asset_private_card",
    )
    catalog._assets[(public_asset.owner_scope, public_asset.visual_asset_id)] = public_asset
    catalog._assets[(private_asset.owner_scope, private_asset.visual_asset_id)] = private_asset
    routes = V3ProductRouteHandlers(visual_asset_library_catalog=catalog)

    visible = routes.get_visual_assets(owner_scope="v3_user_8")

    assert {item["visual_asset_id"] for item in visible["visual_assets"]} == {
        "visual_asset_public_card",
        "visual_asset_private_card",
    }
    assert "visual_asset_private_card" not in {
        item["visual_asset_id"]
        for item in routes.get_visual_assets(owner_scope="v3_user_9")["visual_assets"]
    }


def test_public_card_detail_is_readable_but_mutation_stays_owner_scoped(tmp_path):
    catalog = PersistentVisualAssetLibraryCatalog(tmp_path)
    public_asset = _active_asset(
        owner_scope=PUBLIC_VISUAL_ASSET_OWNER_SCOPE,
        visual_asset_id="visual_asset_public_card",
    )
    catalog._assets[(public_asset.owner_scope, public_asset.visual_asset_id)] = public_asset
    routes = V3ProductRouteHandlers(
        visual_asset_library_catalog=catalog,
        anchor_pack_preparation_host=object(),
    )

    detail = routes.get_visual_asset(
        "visual_asset_public_card",
        owner_scope="v3_user_8",
    )

    assert detail["visual_asset"]["available_for_projects"] is True
    with pytest.raises(KeyError, match="visual_asset_not_found"):
        routes.post_visual_asset_prepare(
            "visual_asset_public_card",
            {},
            owner_scope="v3_user_8",
        )
