from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import ModeAwareRoleDirector


def test_doc69_prompt_atoms_are_retired_for_new_role_recipes() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc69", job_id="job_doc69", user_input="An abstract summer visual.",
        mode="creative_exploration", requested_image_count=1, subject_type="generic",
    ).role_recipes[0]

    assert "doc69_prompt_atom_recipe" not in recipe.metadata
    assert not any(key.startswith("prompt_atom_") for key in recipe.metadata)
