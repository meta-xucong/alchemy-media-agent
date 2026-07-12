from alchemy_creative_agent_3_0.app.product_api.route_handlers import V3ProductRouteHandlers
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan(confirmations: dict[str, str]) -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon listing suite for this striped shirt.",
        product_profile={
            "product_category": "shirt",
            "unverified_visual_facts": ["back pintuck detail", "hidden inner pocket"],
            "product_fact_confirmations": confirmations,
        },
        uploaded_asset_ids=["d4_shirt_reference"],
        scenario_parameters={"platform": "amazon_us", "market": "US"},
        platform_profile=None,
        job_key="d4_fact_confirmation",
    )


def test_owner_confirmation_promotes_only_the_selected_pending_fact() -> None:
    output = _plan({"legacy_fact": "confirmed"})
    facts = {fact.value: fact for fact in output.product_truth.fact_ledger}

    assert facts["back pintuck detail"].source_type == "user_confirmed"
    assert facts["back pintuck detail"].verification == "verified"
    assert facts["hidden inner pocket"].verification == "requires_confirmation"
    assert output.product_truth.metadata["confirmed_fact_ids"] == ["legacy_fact"]
    assert output.product_truth.metadata["confirmation_fact_ids"] == ["legacy_fact_2"]


def test_owner_removal_withholds_the_fact_from_recipe_and_export_attention() -> None:
    output = _plan({"hidden inner pocket": "removed"})

    assert [fact.value for fact in output.product_truth.fact_ledger] == ["back pintuck detail"]
    assert output.product_truth.metadata["removed_fact_ids"] == ["legacy_fact_2"]
    assert all("hidden inner pocket" not in recipe.required_product_facts for recipe in output.recipes)
    assert all("hidden inner pocket" not in warning for warning in output.warnings)


def test_project_mode_passes_persisted_fact_review_metadata_back_to_ecommerce_planning() -> None:
    handlers = V3ProductRouteHandlers()
    project = handlers.post_projects({"user_goal": "Review supplier product facts"})["project"]
    job = handlers.post_project_job(
        project["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create a listing suite for this shirt",
            "commerce_profile_patch": {
                "product_category": "shirt",
                "target_platform": "amazon_us",
                "metadata": {
                    "unverified_visual_facts": ["back pintuck detail"],
                    "product_fact_confirmations": {"back pintuck detail": "confirmed"},
                },
            },
        },
    )

    assert job["ecommerce"]["warnings"] == []
    confirmation_check = next(check for check in job["ecommerce"]["critic_checks"] if check["id"] == "unverified_visual_fact_confirmation")
    assert confirmation_check["status"] == "done"
