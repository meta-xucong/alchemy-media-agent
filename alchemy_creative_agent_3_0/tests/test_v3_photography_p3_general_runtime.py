import json
from pathlib import Path

import pytest

from alchemy_creative_agent_3_0.app.scenario_packs import ScenarioPackRegistry
from alchemy_creative_agent_3_0.app.scenario_packs.photography import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileCatalog,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographerProfileSelectionSource,
    PhotographyInputMode,
    PhotographyReshootStrength,
    PhotographyScenarioPackPlanner,
    PhotographySceneDomain,
    PhotographyTechniquePackage,
    PhotographyUserControls,
)


def _named_catalog() -> PhotographerProfileCatalog:
    return PhotographerProfileCatalog(
        profiles=[
            PhotographerProfile(
                profile_id="named_test_profile",
                profile_kind=PhotographerProfileKind.NAMED_PHOTOGRAPHER,
                public_display_name="Named Test Profile",
                supported_scene_ids=["portrait"],
                supported_commission_ids=["single_hero"],
                technique_package=PhotographyTechniquePackage(
                    lighting=["signature test light"],
                    composition=["signature test composition"],
                ),
                rights_status=PhotographerProfileRightsStatus.APPROVED,
                availability_status=PhotographerProfileAvailability.ACTIVE,
                review_owner="test",
                reviewed_at="2026-07-12T00:00:00+08:00",
            )
        ],
        catalog_version="test-catalog-v1",
    )


def test_p3_general_planner_builds_single_hero_photography_plan() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a moody low-key portrait of a ceramic artist in her studio",
        controls=PhotographyUserControls(explicit_scene_id="portrait"),
        job_key="job_portrait_p3",
    )

    assert output.profile_binding.binding_mode == "general"
    assert output.profile_binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID
    assert output.brief.scene_domain == PhotographySceneDomain.PORTRAIT
    assert output.brief.metadata["mood_family"] == "low_key_or_moody"
    assert output.metadata["planning_only"] is True
    assert output.metadata["direct_provider_call"] is False
    assert output.metadata["registered_in_default_scenario_registry"] is False
    assert {item.capability_id for item in output.technique_contributions} == {
        "photography_camera_optics",
        "photography_lighting_direction",
        "photography_composition_direction",
        "photography_color_finish",
        "photography_retouch_direction",
    }
    assert all(not item.provider_input_requirements for item in output.technique_contributions)
    assert output.shot_specs[0].role == "hero_photograph"
    assert "low-key" in output.shot_specs[0].lighting_map_and_exposure_key
    assert output.review.status == "ready"
    assert output.review.metadata["real_output_review_status"] == "not_run_until_production_activation"


def test_free_text_or_llm_named_suggestion_cannot_activate_profile() -> None:
    output = PhotographyScenarioPackPlanner(profile_catalog=_named_catalog()).plan(
        user_input="Make a portrait in the style of a famous photographer",
        llm_profile_proposal="named_test_profile",
        job_key="job_llm_profile_ignored",
    )

    assert output.profile_binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID
    assert output.profile_binding.binding_mode == "general"
    assert output.metadata["llm_profile_proposal_ignored"] is True
    assert "llm_profile_proposal_ignored_named_profiles_require_explicit_ui" in output.warnings
    assert all(
        contribution.metadata["contains_named_photographer_identity"] is False
        for contribution in output.technique_contributions
    )


def test_explicit_named_profile_is_blocked_in_p3_without_general_fallback() -> None:
    controls = PhotographyUserControls(
        photographer_profile_id="named_test_profile",
        photographer_profile_selection_source=PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
    )

    with pytest.raises(ValueError, match="named_profiles_not_active_in_p3"):
        PhotographyScenarioPackPlanner(profile_catalog=_named_catalog()).plan(
            user_input="Create a studio portrait",
            controls=controls,
            job_key="job_named_blocked",
        )


def test_reference_reshoot_keeps_declared_truth_separate_from_allowed_changes() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Turn this ordinary portrait into a polished professional reshoot",
        controls=PhotographyUserControls(
            input_mode=PhotographyInputMode.REFERENCE_TO_PROFESSIONAL_RESHOOT,
            reshoot_strength=PhotographyReshootStrength.PROFESSIONAL_RESHOOT,
            preservation_controls={
                "person_identity": "preserve",
                "wardrobe": "prompt_owned",
            },
        ),
        uploaded_asset_ids=["portrait_reference_1"],
        job_key="job_reference_reshoot",
    )

    assert output.brief.commission_intent == "reference_reshoot"
    assert output.brief.reference_policy_summary["channel_policy"].startswith("preserve declared truth only")
    assert "person_identity:preserve" in output.shot_specs[0].immutable_reference_truth
    assert "wardrobe:prompt_owned" not in output.shot_specs[0].immutable_reference_truth
    assert output.shot_specs[0].allowed_changes == ["wardrobe", "camera", "lighting", "staging", "finish"]
    assert output.profile_binding.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID


def test_landscape_scene_uses_scene_specific_general_photography_guidance() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a professional landscape photograph of a misty coast at sunrise",
        job_key="job_landscape_p3",
    )

    assert output.brief.scene_domain == PhotographySceneDomain.LANDSCAPE
    assert "foreground" in output.shot_specs[0].framing_and_crop
    assert "sky" in output.shot_specs[0].surface_texture_and_grain
    assert "photography_lighting_plausibility_error" in output.review.issue_codes


def test_p3_photography_planner_has_no_registry_or_provider_side_effects() -> None:
    before = [pack.scenario_id for pack in ScenarioPackRegistry().list_packs()]

    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a still life photograph of a watch on a dark stone surface",
        job_key="job_isolation_p3",
    )

    after = [pack.scenario_id for pack in ScenarioPackRegistry().list_packs()]
    assert before == after
    assert "photography" not in after
    assert output.brief.scene_domain == PhotographySceneDomain.STILL_LIFE
    payload = json.dumps(output.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "provider_id" not in payload
    assert "source_url" not in payload


def test_unknown_scene_uses_general_grammar_without_human_or_animal_leakage() -> None:
    output = PhotographyScenarioPackPlanner().plan(
        user_input="Create a professional abstract photograph with unusual geometry",
        job_key="job_general_scene_p3",
    )

    assert output.brief.scene_domain == PhotographySceneDomain.GENERAL
    combined = json.dumps(output.model_dump(mode="json"), ensure_ascii=False).lower()
    assert "malformed face, hands or human anatomy" not in combined
    assert "malformed animal anatomy" not in combined
    lighting = next(
        item for item in output.technique_contributions if item.capability_id == "photography_lighting_direction"
    )
    assert lighting.facts["human_realism_relevant"] is False


def test_p3_photography_package_has_no_forbidden_runtime_dependencies() -> None:
    import alchemy_creative_agent_3_0.app.scenario_packs.photography as photography

    package_root = Path(photography.__file__).parent
    source = "\n".join(path.read_text(encoding="utf-8") for path in package_root.rglob("*.py"))

    forbidden = (
        "custom_media_agent_docs",
        "src_skeleton.app",
        "generation_router.providers",
        "product_api.service",
        ".providers import",
    )
    assert not any(token in source for token in forbidden)
