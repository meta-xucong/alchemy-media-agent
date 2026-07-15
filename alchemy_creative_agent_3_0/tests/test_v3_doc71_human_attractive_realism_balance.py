from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def test_doc71_historical_beauty_tuning_cannot_override_prompt_owned_style() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc71", job_id="job_doc71", scenario_id="general_creative",
        template_id="general_template", user_input="A low-key real-camera portrait of an adult.",
        subject_type="character", variation_mode="single_hero", has_identity_reference=False,
    )

    assert guidance.applies is True
    assert guidance.metadata["human_realism_plugin"]["style_profile"] == "low_key_texture_preserving"
    assert "summer" not in " ".join(guidance.positive_prompt_fragments).lower()
    assert "bright summer" not in " ".join(guidance.positive_prompt_fragments).lower()
