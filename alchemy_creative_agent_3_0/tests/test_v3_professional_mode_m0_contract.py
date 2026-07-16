from __future__ import annotations

import pytest
from pydantic import ValidationError

from alchemy_creative_agent_3_0.app.visual_assets.contracts import (
    AnchorView,
    FaceIdentityModule,
    IdentityAnchorPackVersion,
    IdentityScoreSummary,
    PeopleAsset,
    ProfessionalModeBinding,
    RootSourceProvenance,
)
from alchemy_creative_agent_3_0.app.visual_assets.binding import bind_professional_mode, select_reference_views


def _view(view_id: str, role: str) -> AnchorView:
    return AnchorView(
        view_id=view_id,
        view_role=role,
        output_id=f"output_{view_id}",
        source_candidate_ids=[f"candidate_{view_id}"],
        identity_scores=IdentityScoreSummary(
            same_face_score=0.92,
            visual_quality_score=0.91,
            evidence_codes=["face_geometry_match"],
        ),
    )


def _active_asset() -> tuple[PeopleAsset, FaceIdentityModule, IdentityAnchorPackVersion]:
    module = FaceIdentityModule(
        module_id="face_module_1",
        people_asset_id="person_1",
        active_version_id="pack_1",
        status="active",
    )
    pack = IdentityAnchorPackVersion(
        pack_version_id="pack_1",
        people_asset_id="person_1",
        status="active",
        anchor_views=[
            _view("front_1", "standard_front"),
            _view("three_quarter_1", "three_quarter"),
            _view("profile_1", "profile"),
        ],
        root_source_provenance=RootSourceProvenance(
            source_type="uploaded_portrait",
            source_asset_id="asset_root_1",
            project_id="project_1",
        ),
        user_activation_confirmed=True,
    )
    asset = PeopleAsset(
        people_asset_id="person_1",
        project_id="project_1",
        subject_kind="human_person",
        face_identity_module=module,
        active_pack_version_id="pack_1",
        status="active",
    )
    return asset, module, pack


def test_professional_binding_requires_explicit_mode_and_active_pack() -> None:
    asset, module, pack = _active_asset()

    binding = bind_professional_mode(
        job_id="job_1",
        project_id="project_1",
        asset=asset,
        module=module,
        pack=pack,
        reference_view_ids=["front_1", "three_quarter_1", "profile_1"],
    )

    assert binding.mode == "professional"
    assert binding.people_asset_id == "person_1"
    assert binding.pack_version_id == "pack_1"
    assert binding.to_brain_evidence() == {
        "mode": "professional",
        "people_asset_id": "person_1",
        "pack_version_id": "pack_1",
        "face_module_id": "face_module_1",
        "identity_view_ids": ["front_1", "three_quarter_1", "profile_1"],
        "identity_channels": ["face_geometry", "face_feature_relationships"],
    }


def test_standard_mode_cannot_create_a_professional_binding() -> None:
    asset, module, pack = _active_asset()

    with pytest.raises(ValueError, match="explicit Professional Mode"):
        ProfessionalModeBinding(
            mode="standard",
            job_id="job_1",
            project_id="project_1",
            people_asset_id=asset.people_asset_id,
            face_module_id=module.module_id,
            pack_version_id=pack.pack_version_id,
            identity_view_ids=["front_1"],
        )


def test_active_pack_requires_user_activation_and_required_face_views() -> None:
    with pytest.raises(ValidationError, match="user activation"):
        IdentityAnchorPackVersion(
            pack_version_id="pack_bad",
            people_asset_id="person_1",
            status="active",
            anchor_views=[_view("front_1", "standard_front")],
            root_source_provenance=RootSourceProvenance(
                source_type="uploaded_portrait",
                source_asset_id="asset_root_1",
                project_id="project_1",
            ),
            user_activation_confirmed=False,
        )


def test_face_identity_rejects_non_face_channels_and_prompt_fields() -> None:
    with pytest.raises(ValidationError):
        FaceIdentityModule(
            module_id="face_module_bad",
            people_asset_id="person_1",
            active_version_id="pack_1",
            status="active",
            owned_channels=["face_geometry", "body_shape"],
        )

    with pytest.raises(ValidationError):
        FaceIdentityModule(
            module_id="face_module_bad",
            people_asset_id="person_1",
            active_version_id="pack_1",
            status="active",
            prompt_additions=["make the face beautiful"],
        )


def test_binding_is_project_scoped_and_reference_selection_is_bounded() -> None:
    asset, module, pack = _active_asset()

    with pytest.raises(ValueError, match="same project"):
        bind_professional_mode(
            job_id="job_1",
            project_id="project_other",
            asset=asset,
            module=module,
            pack=pack,
            reference_view_ids=["front_1"],
        )

    assert select_reference_views(pack, ["front_1", "three_quarter_1", "profile_1", "front_1"]) == [
        "front_1",
        "three_quarter_1",
        "profile_1",
    ]

    with pytest.raises(ValueError, match="at most three"):
        bind_professional_mode(
            job_id="job_1",
            project_id="project_1",
            asset=asset,
            module=module,
            pack=pack,
            reference_view_ids=["front_1", "three_quarter_1", "profile_1", "front_1"],
        )


def test_brain_evidence_has_no_prompt_provider_or_vertical_fields() -> None:
    asset, module, pack = _active_asset()
    binding = bind_professional_mode(
        job_id="job_1",
        project_id="project_1",
        asset=asset,
        module=module,
        pack=pack,
        reference_view_ids=["front_1"],
    )

    payload = binding.to_brain_evidence()
    forbidden = {"prompt", "prompt_additions", "negative_prompt", "provider", "slot", "platform", "marketplace"}
    assert forbidden.isdisjoint(payload)
