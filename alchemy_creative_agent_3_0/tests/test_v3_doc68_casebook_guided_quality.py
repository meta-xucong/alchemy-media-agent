from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import ModeAwareRoleDirector
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.casebook_recipes import provider_casebook_prompt_lines


def test_doc68_casebook_is_read_compatible_but_not_emitted_by_new_general_roles() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc68", job_id="job_doc68", user_input="A natural portrait.",
        mode="selection_candidates", requested_image_count=1, subject_type="character",
    ).role_recipes[0].model_dump(mode="json")

    assert "doc68_casebook_recipe" not in recipe["metadata"]
    assert provider_casebook_prompt_lines(recipe) == []


def test_doc68_legacy_casebook_metadata_remains_readable_without_becoming_a_new_plan() -> None:
    legacy_recipe = {
        "metadata": {
            "doc68_casebook_recipe": True,
            "casebook_camera_recipe": "historical camera note",
        }
    }

    assert provider_casebook_prompt_lines(legacy_recipe) == ["Casebook camera recipe: historical camera note"]
