from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan_with_positioning(positioning: str) -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon ecommerce image set for this adjustable desk lamp",
        product_profile={
            "product_category": "desk lamp",
            "price_positioning": positioning,
            "selling_points": ["Adjustable angle", "Stable metal base"],
        },
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={"platform": "amazon_us", "requested_image_count": 2},
        platform_profile=None,
        job_key=f"e20_{positioning}",
    )


def test_price_positioning_reaches_every_recipe_as_non_claim_visual_direction() -> None:
    output = _plan_with_positioning("premium")

    assert output.commerce_brief.metadata["price_positioning"] == "premium"
    assert output.commerce_brief.metadata["price_positioning_label"] == "premium visual positioning"
    assert "restrained composition" in output.commerce_brief.visual_strategy[-1].lower()
    assert output.recipes
    assert all(recipe.metadata["price_positioning"] == "premium" for recipe in output.recipes)
    assert all(recipe.metadata["price_positioning_label"] == "premium visual positioning" for recipe in output.recipes)
    assert all("restrained composition" in recipe.visual_scene.lower() for recipe in output.recipes)
    assert all("do not invent luxury provenance" in recipe.visual_scene.lower() for recipe in output.recipes)


def test_value_positioning_explicitly_forbids_discount_and_price_comparison_copy() -> None:
    output = _plan_with_positioning("value")

    assert output.commerce_brief.metadata["price_positioning"] == "value"
    assert all("do not add discount badges, price comparisons, or savings claims" in recipe.visual_scene.lower() for recipe in output.recipes)


def test_unknown_price_positioning_is_ignored_for_backward_compatible_planning() -> None:
    output = _plan_with_positioning("unverified luxury tier")

    assert "price_positioning" not in output.commerce_brief.metadata
    assert all("price_positioning" not in recipe.metadata for recipe in output.recipes)
