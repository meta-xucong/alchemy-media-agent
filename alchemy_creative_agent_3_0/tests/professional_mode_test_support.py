"""Shared Professional Mode fixtures for root-level relay and evidence tests."""

from __future__ import annotations

from ..app.visual_assets import (
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    InMemoryVisualAssetCatalog,
    PeopleAsset,
    RootSourceProvenance,
)


def catalog_with_active_face_identity_pack() -> InMemoryVisualAssetCatalog:
    """Return an intentionally opaque, active three-view fixture catalog."""

    catalog = InMemoryVisualAssetCatalog()
    project_id = "project_professional"
    people_asset_id = "person_1"
    pack_id = "pack_1"
    views = [
        AnchorView(
            view_id=view_id,
            view_role=role,
            output_id=f"output_{role}",
            source_candidate_ids=[f"candidate_{role}"],
            identity_scores=IdentityScoreSummary(
                same_face_score=0.95,
                visual_quality_score=0.9,
                distinctive_feature_score=0.94,
                human_realism_score=0.9,
            ),
        )
        for view_id, role in (
            ("front_1", "standard_front"),
            ("three_quarter_1", "three_quarter"),
            ("profile_1", "profile"),
        )
    ]
    pack = IdentityAnchorPackVersion(
        pack_version_id=pack_id,
        people_asset_id=people_asset_id,
        status="active",
        anchor_views=views,
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="portrait_root",
            project_id=project_id,
        ),
        user_activation_confirmed=True,
    )
    asset = PeopleAsset(
        people_asset_id=people_asset_id,
        project_id=project_id,
        subject_kind="human_person",
        face_identity_module=FaceIdentityModule(
            module_id="face_1",
            people_asset_id=people_asset_id,
            active_version_id=pack_id,
            status="active",
        ),
        active_pack_version_id=pack_id,
        status="active",
    )
    catalog.save_pack(pack, project_id=project_id, event_type="activate")
    catalog.save(asset, project_id=project_id, event_type="activate")
    return catalog
