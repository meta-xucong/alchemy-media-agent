from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def test_doc72_historical_demographic_case_cannot_create_a_runtime_prompt_branch() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc72", job_id="job_doc72", scenario_id="general_creative",
        template_id="general_template", user_input="A bright portrait of an East Asian adult.",
        subject_type="character", variation_mode="single_hero", has_identity_reference=False,
    )

    assert guidance.applies is True
    metadata = guidance.metadata
    assert "human_east_asian_fair_complexion_guard_library" not in metadata
    assert "east asian" not in " ".join(guidance.positive_prompt_fragments).lower()
