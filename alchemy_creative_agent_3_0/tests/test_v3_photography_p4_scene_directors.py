import json

from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry
from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    PhotographyInputMode,
    PhotographyReshootStrength,
    PhotographyScenarioPackPlanner,
    PhotographySceneDomain,
    PhotographyUserControls,
)


def test_p4_portrait_director_contributes_scene_owned_direction_only() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create an environmental portrait of a ceramic artist at work",
        controls=PhotographyUserControls(explicit_scene_id="portrait"),
        job_key="p4_portrait_scene",
    )

    assert output.brief.scene_domain == PhotographySceneDomain.PORTRAIT
    assert [item.capability_id for item in output.scene_contributions] == [
        "portrait_photography_direction"
    ]
    contribution = output.scene_contributions[0]
    assert contribution.facts["foundation_capabilities_reused"] == [
        "reference_channel_policy",
        "human_realism",
        "portrait_identity",
    ]
    assert contribution.provider_input_requirements == []
    assert "expression" in output.shot_specs[0].subject_and_decisive_moment
    assert "hands" in output.shot_specs[0].framing_and_crop
    assert output.review.status == "ready"

    payload = json.dumps(contribution.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "landform" not in payload
    assert "foliage" not in payload
    assert "fur" not in payload
    assert "marketplace" not in payload
    assert "listing" not in payload


def test_p4_portrait_reference_keeps_identity_separate_from_prompt_owned_styling() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Professionally reshoot this portrait with a new editorial wardrobe",
        controls=PhotographyUserControls(
            explicit_scene_id="portrait",
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.PROFESSIONAL_RESHOOT,
            preservation_controls={
                "person_identity": "preserve",
                "hair": "prompt_owned",
                "wardrobe": "prompt_owned",
            },
        ),
        uploaded_asset_ids=["portrait_identity_reference"],
        job_key="p4_portrait_reference_ownership",
    )

    shot = output.shot_specs[0]
    assert "person_identity:preserve" in shot.immutable_reference_truth
    assert "hair:prompt_owned" not in shot.immutable_reference_truth
    assert "wardrobe:prompt_owned" not in shot.immutable_reference_truth
    assert {"hair", "wardrobe"} <= set(shot.allowed_changes)


def test_p4_landscape_reference_keeps_scene_truth_separate_from_conditions() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Reshoot this landmark landscape in dramatic evening weather",
        controls=PhotographyUserControls(
            explicit_scene_id="landscape",
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.CREATIVE_REINTERPRETATION,
            preservation_controls={
                "scene_landmark_truth": "preserve",
                "weather": "prompt_owned",
                "lighting": "prompt_owned",
            },
        ),
        uploaded_asset_ids=["landscape_reference"],
        job_key="p4_landscape_reference_ownership",
    )

    shot = output.shot_specs[0]
    assert "scene_landmark_truth:preserve" in shot.immutable_reference_truth
    assert "weather" in shot.allowed_changes
    assert "lighting" in shot.allowed_changes


def test_p4_scene_directors_do_not_expand_named_profile_authority() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a portrait in the style of a famous named photographer",
        controls=PhotographyUserControls(explicit_scene_id="portrait"),
        llm_profile_proposal="untrusted_named_profile",
        job_key="p4_named_profile_authority",
    )

    assert output.profile_binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID
    assert output.profile_binding.binding_mode == "general"
    assert output.metadata["llm_profile_proposal_ignored"] is True
    assert all(
        item.metadata["contains_named_photographer_identity"] is False
        for item in output.scene_contributions
    )


def test_p4_shadow_directors_do_not_register_or_activate_production() -> None:
    before = [pack.scenario_id for pack in ScenarioPackRegistry().list_packs()]
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a still life of glass and stone",
        controls=PhotographyUserControls(explicit_scene_id="still_life"),
        job_key="p4_registry_isolation",
    )
    after = [pack.scenario_id for pack in ScenarioPackRegistry().list_packs()]

    assert before == after
    assert "photography" not in after
    assert output.metadata["production_activation_ready"] is False
    assert output.metadata["registered_in_default_scenario_registry"] is False
    assert all(not item.provider_input_requirements for item in output.scene_contributions)


def test_p4_landscape_director_controls_depth_and_conditions_without_scene_leakage() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a landscape photograph of a misty mountain valley at dawn",
        controls=PhotographyUserControls(explicit_scene_id="landscape"),
        job_key="p4_landscape_scene",
    )

    assert [item.capability_id for item in output.scene_contributions] == [
        "landscape_photography_direction"
    ]
    contribution = output.scene_contributions[0]
    assert contribution.facts["foundation_capabilities_reused"] == [
        "reference_channel_policy",
        "scene_continuity",
        "universal_visual_quality",
    ]
    assert "middle distance" in output.shot_specs[0].framing_and_crop
    assert "weather" in output.shot_specs[0].subject_and_decisive_moment
    assert output.review.status == "ready"

    payload = json.dumps(contribution.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "skin" not in payload
    assert "pose" not in payload
    assert "fur" not in payload
    assert "marketplace" not in payload
    assert "listing" not in payload


def test_p4_still_life_director_preserves_object_truth_without_commerce_packaging() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Professionally reshoot this ceramic vase as a minimal still life",
        controls=PhotographyUserControls(
            explicit_scene_id="still_life",
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.PROFESSIONAL_RESHOOT,
            preservation_controls={
                "object_truth": "preserve",
                "background": "prompt_owned",
            },
        ),
        uploaded_asset_ids=["still_life_reference"],
        job_key="p4_still_life_scene",
    )

    assert [item.capability_id for item in output.scene_contributions] == [
        "still_life_photography_direction"
    ]
    contribution = output.scene_contributions[0]
    assert "reflection" in output.shot_specs[0].surface_texture_and_grain
    assert "object_truth:preserve" in output.shot_specs[0].immutable_reference_truth
    assert "background" in output.shot_specs[0].allowed_changes
    assert contribution.facts["deliverable_boundary"].startswith("still-life photography only")
    assert output.review.status == "ready"

    payload = json.dumps(contribution.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "skin" not in payload
    assert "portrait" not in payload
    assert "fur" not in payload
    assert "session role" not in payload


def test_p4_animal_director_preserves_identity_contract_without_faking_shared_capability() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Professionally reshoot this dog running through a meadow",
        controls=PhotographyUserControls(
            explicit_scene_id="animal",
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.PROFESSIONAL_RESHOOT,
            preservation_controls={
                "nonhuman_subject_identity": "preserve",
                "habitat": "prompt_owned",
            },
        ),
        uploaded_asset_ids=["animal_reference"],
        job_key="p4_animal_scene",
    )

    assert [item.capability_id for item in output.scene_contributions] == [
        "animal_photography_direction"
    ]
    contribution = output.scene_contributions[0]
    assert "gaze" in output.shot_specs[0].subject_and_decisive_moment
    assert "nonhuman_subject_identity:preserve" in output.shot_specs[0].immutable_reference_truth
    assert "habitat" in output.shot_specs[0].allowed_changes
    assert contribution.facts["specific_identity_execution_status"] == (
        "shared_nonhuman_subject_identity_required_before_production"
    )
    assert "nonhuman_subject_identity" not in contribution.facts["foundation_capabilities_reused"]
    assert output.review.status == "ready"

    payload = json.dumps(contribution.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "skin" not in payload
    assert "portrait" not in payload
    assert "landform" not in payload
    assert "marketplace" not in payload
    assert "listing" not in payload


def test_p4_general_scene_activates_no_first_wave_director() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create an abstract photograph about geometry and light",
        job_key="p4_general_neutral",
    )

    assert output.brief.scene_domain == PhotographySceneDomain.GENERAL
    assert output.scene_contributions == []
    assert output.review.status == "ready"
