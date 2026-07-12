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
    PhotographyInputMode,
    PhotographyReshootStrength,
    PhotographyScenarioPackPlanner,
    PhotographyTechniquePackage,
    PhotographyUserControls,
)


def _operator_catalog() -> PhotographerProfileCatalog:
    return PhotographerProfileCatalog(
        profiles=[
            PhotographerProfile(
                profile_id="licensed_editorial_v1",
                profile_version="2026.07",
                profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
                public_display_name="Licensed Editorial Profile",
                supported_scene_ids=["portrait", "landscape"],
                supported_commission_ids=["single_hero", "reference_reshoot"],
                technique_package=PhotographyTechniquePackage(
                    composition=["asymmetric frame with deliberate negative space"],
                    camera_relation=["subject-level camera placement with an intimate but unforced distance"],
                    lighting=["soft directional window light with restrained fill"],
                    color_response=["muted natural palette with gentle highlight rolloff"],
                    retouch_finish=["retain natural texture and avoid beauty-filter smoothing"],
                    forbidden_techniques=["imitative signature or watermark"],
                ),
                rights_status=PhotographerProfileRightsStatus.APPROVED,
                availability_status=PhotographerProfileAvailability.ACTIVE,
                allowed_regions=["CN"],
                review_owner="rights-and-photography-operator",
                reviewed_at="2026-07-12T00:00:00+08:00",
            )
        ],
        catalog_version="photography-p5-operator-test-v1",
    )


def _named_controls(**overrides: object) -> PhotographyUserControls:
    payload: dict[str, object] = {
        "photographer_profile_id": "licensed_editorial_v1",
        "photographer_profile_selection_source": PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
        "explicit_scene_id": "portrait",
    }
    payload.update(overrides)
    return PhotographyUserControls(**payload)


def test_p5_operator_catalog_projects_only_approved_named_records_to_mainline_catalog() -> None:
    catalog = _operator_catalog()
    shared = catalog.shared_catalog()

    public = shared.public_catalog(region="CN")
    named = next(item for item in public["profiles"] if item["profile_id"] == "licensed_editorial_v1")
    assert named["selection_requires_confirmation"] is True
    assert "technique_package_checksum" not in named

    binding = shared.resolve_binding(
        scenario_id="photography",
        profile_id="licensed_editorial_v1",
        selection_source="user_explicit_ui",
        region="CN",
    )
    assert binding.profile_version == "2026.07"
    assert binding.technique_package_checksum == catalog.technique_package_checksum(
        catalog.get("licensed_editorial_v1")
    )

    output = PhotographyScenarioPackPlanner(
        profile_catalog=catalog, named_profiles_enabled=True
    ).plan_from_pinned_binding(
        user_input="Create a quiet editorial portrait of a ceramic artist in her studio.",
        profile_binding=binding,
        controls=PhotographyUserControls(explicit_scene_id="portrait"),
        job_key="p5_mainline_pinned_binding",
    )
    assert output.profile_binding.profile_id == "licensed_editorial_v1"
    assert output.metadata["profile_binding_source"] == "mainline_immutable_binding"


def test_p5_explicit_named_profile_compiles_technique_without_prompting_a_person_name() -> None:
    output = PhotographyScenarioPackPlanner(
        profile_catalog=_operator_catalog(), named_profiles_enabled=True
    ).plan(
        user_input="Create a quiet editorial portrait of a ceramic artist in her studio.",
        controls=_named_controls(),
        job_key="p5_explicit_named_profile",
    )

    named = next(
        item for item in output.technique_contributions if item.capability_id == "photography_named_profile_technique"
    )
    assert output.profile_binding.binding_mode == "named"
    assert named.metadata["profile_selected_by"] == "user_explicit_ui"
    assert named.metadata["profile_name_in_prompt"] is False
    assert "asymmetric frame" in named.prompt_additions[0]
    assert "licensed editorial profile" not in " ".join(named.prompt_additions).lower()
    assert "named_profile_technique_underapplied" in output.review.issue_codes
    assert output.review.status == "ready"


def test_p5_named_profile_never_overrides_reference_locked_technique_channels() -> None:
    output = PhotographyScenarioPackPlanner(
        profile_catalog=_operator_catalog(), named_profiles_enabled=True
    ).plan(
        user_input="Professionally reshoot this portrait while preserving its existing lighting.",
        controls=_named_controls(
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.PROFESSIONAL_RESHOOT,
            preservation_controls={"person_identity": "preserve", "lighting": "preserve", "wardrobe": "prompt_owned"},
        ),
        uploaded_asset_ids=["portrait_reference"],
        job_key="p5_reference_truth_precedence",
    )

    named = next(
        item for item in output.technique_contributions if item.capability_id == "photography_named_profile_technique"
    )
    assert "lighting" in named.facts["constrained_technique_fields"]
    assert all("window light" not in item for item in named.prompt_additions)
    assert "wardrobe" in output.shot_specs[0].allowed_changes
    assert output.review.status == "ready"


def test_p5_technique_compiler_rejects_a_binding_that_does_not_match_the_approved_record() -> None:
    catalog = _operator_catalog()
    binding = catalog.resolve_binding(_named_controls())
    mismatched = binding.model_copy(update={"technique_package_checksum": "wrong"})

    with pytest.raises(ValueError, match="named_profile_binding_mismatch:technique_checksum"):
        catalog.resolve_pinned_profile(mismatched)


def test_p5_default_catalog_keeps_named_profiles_disabled_until_operator_approval() -> None:
    catalog = PhotographerProfileCatalog()

    assert catalog.selectable_named_profiles() == []
    assert [item["profile_id"] for item in catalog.shared_catalog().public_catalog()["profiles"]] == [
        "general_photography"
    ]


def test_p5_named_profile_shadow_output_stays_provider_free_and_does_not_fake_nonhuman_identity() -> None:
    output = PhotographyScenarioPackPlanner(
        profile_catalog=_operator_catalog(), named_profiles_enabled=True
    ).plan(
        user_input="Create a portrait of a dog in a meadow.",
        controls=_named_controls(explicit_scene_id="animal"),
        uploaded_asset_ids=["individual_dog_reference"],
        job_key="p5_nonhuman_shared_boundary",
    )

    payload = json.dumps(output.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "provider_id" not in payload
    assert "native_nonhuman_identity_reference" not in payload
    assert output.metadata["direct_provider_call"] is False
