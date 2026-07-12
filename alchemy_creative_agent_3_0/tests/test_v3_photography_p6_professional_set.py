from __future__ import annotations

import json

import pytest

from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileCatalog,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographerProfileSelectionSource,
    PhotographyDeliveryMode,
    PhotographyInputMode,
    PhotographyReshootStrength,
    PhotographyScenarioPackPlanner,
    PhotographyTechniquePackage,
    PhotographyUserControls,
    photography_manifest,
)


def _operator_catalog() -> PhotographerProfileCatalog:
    return PhotographerProfileCatalog(
        profiles=[
            PhotographerProfile(
                profile_id="licensed_editorial_session_v1",
                profile_version="2026.07",
                profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
                public_display_name="Licensed Editorial Session Profile",
                supported_scene_ids=["portrait"],
                supported_commission_ids=["professional_session"],
                technique_package=PhotographyTechniquePackage(
                    composition=["asymmetric frame with deliberate negative space"],
                    lighting=["soft directional window light with restrained fill"],
                    color_response=["muted natural palette with gentle highlight rolloff"],
                    forbidden_techniques=["imitative signature or watermark"],
                ),
                rights_status=PhotographerProfileRightsStatus.APPROVED,
                availability_status=PhotographerProfileAvailability.ACTIVE,
                allowed_regions=["CN"],
                review_owner="photography-operator",
                reviewed_at="2026-07-13T00:00:00+08:00",
            )
        ],
        catalog_version="photography-p6-operator-test-v1",
    )


def _set_controls(**overrides: object) -> PhotographyUserControls:
    payload: dict[str, object] = {
        "delivery_mode": PhotographyDeliveryMode.PROFESSIONAL_SET,
        "explicit_scene_id": "portrait",
    }
    payload.update(overrides)
    return PhotographyUserControls(**payload)


def test_p6_shadow_set_is_not_exposed_by_the_current_gated_runtime_manifest() -> None:
    manifest = photography_manifest(enabled=True)

    assert manifest.default_mode_id == "single_hero"
    assert manifest.supported_mode_ids == ["single_hero", "reference_reshoot"]
    assert "professional_set" not in manifest.supported_mode_ids


def test_p6_professional_set_has_differentiated_roles_and_shared_coherence() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a professional portrait session of a ceramic artist in her studio.",
        controls=_set_controls(),
        job_key="p6_portrait_session",
    )

    assert [shot.role for shot in output.shot_specs] == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert output.professional_set_plan is not None
    assert output.professional_set_plan.role_order == [shot.role for shot in output.shot_specs]
    assert output.professional_set_plan.shot_ids_by_role == {
        shot.role: shot.shot_id for shot in output.shot_specs
    }
    assert output.professional_set_plan.selection_contract["owner"] == "shared_final_delivery_resolver"
    assert output.professional_set_plan.delivery_package["beginner_surface"] == "final_role_winners_only"
    assert output.metadata["phase"] == "P6_professional_set_planning"
    assert output.metadata["direct_provider_call"] is False
    assert output.professional_set_plan.metadata["shared_execution_required"] is True

    hero, context, detail = output.shot_specs
    for shot in (context, detail):
        changed = {
            field
            for field in (
                "framing_and_crop",
                "camera_position_and_perspective_effect",
                "subject_and_decisive_moment",
                "subject_direction",
            )
            if getattr(shot, field) != getattr(hero, field)
        }
        assert len(changed) >= 2
        assert shot.metadata["differentiated_dimensions"]
    assert hero.palette_and_tone_curve == context.palette_and_tone_curve == detail.palette_and_tone_curve
    assert hero.immutable_reference_truth == context.immutable_reference_truth == detail.immutable_reference_truth
    checks = {item["id"]: item["status"] for item in output.review.checks}
    assert checks["professional_set_scope"] == "done"


@pytest.mark.parametrize(
    ("scene_id", "prompt"),
    [
        ("portrait", "Create a professional portrait session in a working studio."),
        ("landscape", "Create a professional landscape set of a coastal valley at dawn."),
        ("still_life", "Create a professional still-life set of glass and stone."),
        ("animal", "Create a professional animal photography set of a horse in a meadow."),
    ],
)
def test_p6_first_wave_scenes_share_set_roles_without_sharing_scene_direction(
    scene_id: str,
    prompt: str,
) -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input=prompt,
        controls=PhotographyUserControls(
            delivery_mode=PhotographyDeliveryMode.PROFESSIONAL_SET,
            explicit_scene_id=scene_id,
        ),
        job_key=f"p6_{scene_id}_set_matrix",
    )

    assert output.brief.scene_domain.value == scene_id
    assert [item.capability_id for item in output.scene_contributions] == [
        f"{scene_id}_photography_direction"
    ]
    assert output.professional_set_plan is not None
    assert output.professional_set_plan.role_order == [
        "session_hero",
        "environmental_context",
        "detail_or_moment",
    ]
    assert output.review.status == "ready"


def test_p6_reference_truth_is_frozen_across_every_professional_set_role() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Professionally reshoot this portrait as one coherent session.",
        controls=PhotographyUserControls(
            delivery_mode=PhotographyDeliveryMode.PROFESSIONAL_SET,
            explicit_scene_id="portrait",
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.PROFESSIONAL_RESHOOT,
            preservation_controls={
                "person_identity": "preserve",
                "wardrobe": "prompt_owned",
            },
        ),
        uploaded_asset_ids=["portrait_identity_reference"],
        job_key="p6_reference_truth_set",
    )

    assert {tuple(shot.immutable_reference_truth) for shot in output.shot_specs} == {
        ("person_identity:preserve",)
    }
    assert all("wardrobe" in shot.allowed_changes for shot in output.shot_specs)
    assert output.professional_set_plan is not None
    assert output.professional_set_plan.coherence_contract["immutable_reference_truth"] == [
        "person_identity:preserve"
    ]


def test_p6_set_keeps_named_profile_explicit_and_never_places_its_name_in_guidance() -> None:
    output = PhotographyScenarioPackPlanner(
        profile_catalog=_operator_catalog(), named_profiles_enabled=True
    ).plan(
        user_input="Create an editorial portrait session of a ceramic artist in her studio.",
        controls=_set_controls(
            photographer_profile_id="licensed_editorial_session_v1",
            photographer_profile_selection_source=PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
        ),
        job_key="p6_named_session",
    )

    assert output.profile_binding.binding_mode == "named"
    assert output.professional_set_plan is not None
    assert output.professional_set_plan.profile_binding_snapshot["profile_id"] == "licensed_editorial_session_v1"
    payload = json.dumps(output.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "licensed editorial session profile" not in " ".join(
        item for contribution in output.technique_contributions for item in contribution.prompt_additions
    ).lower()
    assert output.professional_set_plan.coherence_contract["profile_binding_locked_across_roles"] is True
    assert "provider_id" not in payload


def test_p6_set_continuation_requires_same_explicit_named_profile_and_preserves_coherence() -> None:
    planner = PhotographyScenarioPackPlanner(
        profile_catalog=_operator_catalog(), named_profiles_enabled=True
    )
    parent = planner.plan(
        user_input="Create an editorial portrait session of a ceramic artist in her studio.",
        controls=_set_controls(
            photographer_profile_id="licensed_editorial_session_v1",
            photographer_profile_selection_source=PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
        ),
        job_key="p6_named_parent",
    )

    with pytest.raises(
        ValueError,
        match="named_profile_continuation_requires_explicit_ui_reconfirmation",
    ):
        planner.plan_set_continuation(
            parent_output=parent,
            request={
                "parent_shot_id": parent.shot_specs[1].shot_id,
                "target_role": "environmental_context",
                "reconfirmed_profile_id": parent.profile_binding.profile_id,
                "reconfirmed_profile_version": parent.profile_binding.profile_version,
                "reconfirmed_technique_package_checksum": (
                    parent.profile_binding.technique_package_checksum
                ),
            },
            job_key="p6_named_child_without_explicit_reconfirmation",
        )

    continuation = planner.plan_set_continuation(
        parent_output=parent,
        request={
            "parent_shot_id": parent.shot_specs[1].shot_id,
            "target_role": "environmental_context",
            "correction_note": "Capture a new environmental moment from the same session.",
            "reconfirmed_profile_id": parent.profile_binding.profile_id,
            "reconfirmed_profile_version": parent.profile_binding.profile_version,
            "reconfirmed_technique_package_checksum": parent.profile_binding.technique_package_checksum,
            "profile_selection_source": "user_explicit_ui",
        },
        job_key="p6_named_child",
    )

    assert continuation.root_set_id == parent.professional_set_plan.set_id
    assert continuation.parent_shot_id == parent.shot_specs[1].shot_id
    assert continuation.profile_binding_snapshot["profile_id"] == parent.profile_binding.profile_id
    assert continuation.coherence_contract == parent.professional_set_plan.coherence_contract
    assert continuation.metadata["append_only_child_required"] is True
    assert continuation.metadata["shared_generation_only"] is True
    assert continuation.metadata["shared_final_delivery_only"] is True

    with pytest.raises(ValueError, match="photography_continuation_profile_binding_mismatch"):
        planner.plan_set_continuation(
            parent_output=parent,
            request={
                "parent_shot_id": parent.shot_specs[0].shot_id,
                "target_role": "session_hero",
                "reconfirmed_profile_id": parent.profile_binding.profile_id,
                "reconfirmed_profile_version": "2026.08",
                "reconfirmed_technique_package_checksum": parent.profile_binding.technique_package_checksum,
                "profile_selection_source": "user_explicit_ui",
            },
            job_key="p6_named_profile_drift",
        )


def test_p6_general_set_continuation_never_inherits_a_named_profile_or_calls_runtime() -> None:
    planner = PhotographyScenarioPackPlanner()
    parent = planner.plan(
        user_input="Create a professional landscape photography session of a misty coast at sunrise.",
        controls=PhotographyUserControls(
            delivery_mode=PhotographyDeliveryMode.PROFESSIONAL_SET,
            explicit_scene_id="landscape",
        ),
        job_key="p6_general_parent",
    )

    continuation = planner.plan_set_continuation(
        parent_output=parent,
        request={
            "parent_shot_id": parent.shot_specs[0].shot_id,
            "target_role": "session_hero",
        },
        job_key="p6_general_child",
    )

    assert continuation.profile_binding_snapshot["profile_id"] == "general_photography"
    assert continuation.metadata["direct_provider_call"] is False
    assert continuation.metadata["shared_generation_only"] is True
    payload = json.dumps(continuation.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "ecommerce" not in payload
    assert "general_template" not in payload


def test_p6_continuation_with_new_reference_requires_shared_capability_revalidation() -> None:
    planner = PhotographyScenarioPackPlanner()
    parent = planner.plan(
        user_input="Create a professional animal photography set.",
        controls=PhotographyUserControls(
            delivery_mode=PhotographyDeliveryMode.PROFESSIONAL_SET,
            explicit_scene_id="animal",
        ),
        job_key="p6_animal_parent",
    )

    continuation = planner.plan_set_continuation(
        parent_output=parent,
        request={
            "parent_shot_id": parent.shot_specs[1].shot_id,
            "target_role": "environmental_context",
            "new_reference_asset_ids": ["new_nonhuman_identity_reference"],
        },
        job_key="p6_animal_new_reference_continuation",
    )

    assert continuation.metadata["new_evidence_requires_shared_capability_revalidation"] is True
    assert continuation.metadata["shared_generation_only"] is True
    assert continuation.metadata["direct_provider_call"] is False
