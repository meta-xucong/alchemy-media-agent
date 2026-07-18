from pathlib import Path

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "app"


def _guidance(user_input: str, *, subject_type: str = "character"):
    return HumanPhotorealismLayer().build(
        project_id="project_doc94",
        job_id="job_doc94",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=user_input,
        subject_type=subject_type,
        variation_mode="delivery_suite",
        has_identity_reference=True,
        metadata={"frozen_developmental_age_intent": "current_request_assigns_stage"},
    )


def test_doc94_shared_runtime_has_no_named_scene_recipe_profiles() -> None:
    files = [
        RUNTIME_ROOT / "shared_capabilities/visual_cluster/human_photorealism.py",
        RUNTIME_ROOT / "shared_capabilities/visual_cluster/casebook_recipes.py",
        RUNTIME_ROOT / "generation_router/providers.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8").lower() for path in files)
    for forbidden in (
        "moody_cinematic_traditional",
        "clean_bright_fresh",
        "child_catalog_natural",
        "east asian portrait aesthetic guard",
        "korean glass skin",
        "k-idol",
    ):
        assert forbidden not in source


def test_doc94_low_key_rendering_profile_is_shared_across_unrelated_portrait_scenes() -> None:
    formal = _guidance(
        "Real camera portrait of an adult in formal clothing, low-key cinematic light, cool shadows, natural skin"
    )
    casual = _guidance(
        "Documentary portrait of an adult in casual clothing, dim available light, deep shadows, natural skin"
    )

    assert formal.metadata["human_realism_plugin"]["style_profile"] == "low_key_texture_preserving"
    assert casual.metadata["human_realism_plugin"]["style_profile"] == "low_key_texture_preserving"
    assert formal.metadata["human_realism_plugin"]["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"
    assert casual.metadata["human_realism_plugin"]["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"


def test_doc94_age_fidelity_uses_one_universal_person_contract() -> None:
    younger = _guidance("Real camera portrait of a child model wearing a jacket in soft daylight", subject_type="product")
    older = _guidance("Real camera portrait of a senior adult wearing a jacket in soft daylight", subject_type="product")

    for guidance in (younger, older):
        plugin = guidance.metadata["human_realism_plugin"]
        assert plugin["human_subject_kind"] == "product_on_person"
        assert plugin["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"
        assert plugin["style_profile"] == "high_key_texture_preserving"
