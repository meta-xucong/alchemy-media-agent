from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def test_doc70_observations_are_represented_by_doc128_shared_dimensions() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc70", job_id="job_doc70", scenario_id="general_creative",
        template_id="general_template", user_input="A real-camera portrait of an adult.",
        subject_type="character", variation_mode="single_hero", has_identity_reference=False,
    )

    assert guidance.applies is True
    assert guidance.metadata["doc128_shared_constraint_contract"] is True
    assert guidance.review_targets == [
        "human_rendering_artifact",
        "human_anatomy_or_proportion",
        "human_age_or_identity_fidelity",
        "human_skin_or_retouch",
        "human_scene_coherence",
    ]
