from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.commerce_critic import CommerceCritic
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.contracts import EcommerceAssetRecipe
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_full_food_suite_covers_category_evidence_with_slot_targets() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon product image set for this bottled tea",
        product_profile={
            "product_category": "drink",
            "selling_points": ["Fresh summer refreshment", "Portable bottle", "Clear ingredients"],
        },
        uploaded_asset_ids=["tea_front"],
        scenario_parameters={"platform": "amazon_us"},
        platform_profile=None,
        job_key="e3_food_full",
    )

    coverage = output.critic.metadata["category_evidence"]
    recipes = {recipe.slot: recipe for recipe in output.recipes}
    assert coverage["category_id"] == "food_beverage"
    assert coverage["missing"] == []
    assert recipes["main_image"].metadata["category_evidence_targets"] == ["package identity"]
    assert recipes["scenario_image"].metadata["category_evidence_targets"] == ["consumption context"]


def test_constrained_electronics_suite_warns_about_evidence_not_shown() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create three Amazon images for wireless earbuds",
        product_profile={
            "product_category": "wireless earbuds",
            "selling_points": ["Compact case", "Comfortable fit", "Clear calls"],
        },
        uploaded_asset_ids=["earbuds_front"],
        scenario_parameters={"platform": "amazon_us", "requested_image_count": 3},
        platform_profile=None,
        job_key="e3_electronics_short",
    )

    coverage = output.critic.metadata["category_evidence"]
    assert coverage["category_id"] == "electronics"
    assert "real-use context" in coverage["missing"]
    assert any(check["id"] == "category_evidence_coverage" and check["status"] == "attention" for check in output.critic.checks)
    assert any("category evidence" in warning for warning in output.warnings)


def test_uploaded_asset_bookkeeping_does_not_become_a_selling_point() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create a generic marketplace suite",
        product_profile={"product_category": "unclassified object", "selling_points": ["One clear benefit"]},
        uploaded_asset_ids=["object_front"],
        scenario_parameters={"platform": "amazon_us"},
        platform_profile=None,
        job_key="e3_duplicate_benefit",
    )

    assert all("uploaded product/reference image" not in recipe.selling_point.lower() for recipe in output.recipes)
    assert output.metadata["scenario_id"] == "ecommerce"


def test_duplicate_benefit_roles_are_reported_by_commerce_critic() -> None:
    duplicate_recipes = [
        EcommerceAssetRecipe(
            slot="feature_image_1",
            business_goal="understand",
            selling_point="One clear benefit",
            buyer_intent="Understand value",
            visual_scene="Benefit-led visual proof.",
        ),
        EcommerceAssetRecipe(
            slot="feature_image_2",
            business_goal="understand",
            selling_point="One clear benefit",
            buyer_intent="Understand value",
            visual_scene="Same benefit-led visual proof.",
        ),
    ]

    assert CommerceCritic()._duplicate_pairs(duplicate_recipes) == [("feature_image_1", "feature_image_2")]
