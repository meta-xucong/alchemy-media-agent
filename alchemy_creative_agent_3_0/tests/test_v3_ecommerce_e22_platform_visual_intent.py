from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan(platform: str, slots: list[str]) -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input=f"Create a {platform} ecommerce image set for this desk lamp",
        product_profile={
            "product_category": "desk lamp",
            "selling_points": ["Adjustable angle", "Stable metal base"],
        },
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={"platform": platform, "suite_slot_request": slots},
        platform_profile=None,
        job_key=f"e22_{platform}",
    )


def test_amazon_primary_and_secondary_recipes_use_distinct_internal_visual_intent() -> None:
    output = _plan("amazon_us", ["main_image", "scenario_image"])
    recipes = {recipe.slot: recipe for recipe in output.recipes}

    assert recipes["main_image"].metadata["platform_visual_intent_id"] == "amazon_white_background_primary"
    assert "clean pure-white, product-first listing main image" in recipes["main_image"].visual_scene.lower()
    assert "no props, people, badges, borders, or rendered text" in recipes["main_image"].visual_scene.lower()
    assert recipes["scenario_image"].metadata["platform_visual_intent_id"] == "amazon_narrative_secondary"
    assert "conversion-oriented secondary image" in recipes["scenario_image"].visual_scene.lower()
    assert output.export_package.files[0]["platform_visual_intent_id"] == "amazon_white_background_primary"


def test_ozon_and_taobao_recipes_have_their_own_scene_and_storytelling_directions() -> None:
    ozon = _plan("ozon", ["main_image", "scenario_image"])
    taobao = _plan("taobao", ["main_image", "detail_image"])
    ozon_recipes = {recipe.slot: recipe for recipe in ozon.recipes}
    taobao_recipes = {recipe.slot: recipe for recipe in taobao.recipes}

    assert all(recipe.metadata["platform_visual_intent_id"] == "ozon_mobile_scene_led" for recipe in ozon.recipes)
    assert "scene-led commerce composition" in ozon_recipes["main_image"].visual_scene.lower()
    assert taobao_recipes["main_image"].metadata["platform_visual_intent_id"] == "taobao_high_impact_primary"
    assert "high-impact product-first hero" in taobao_recipes["main_image"].visual_scene.lower()
    assert taobao_recipes["detail_image"].metadata["platform_visual_intent_id"] == "taobao_detail_story"
    assert "rich detail-page storytelling" in taobao_recipes["detail_image"].visual_scene.lower()


def test_platform_visual_intent_is_versioned_planning_metadata_not_a_policy_approval() -> None:
    output = _plan("pinduoduo", ["main_image", "benefit_image"])

    assert all(recipe.metadata["platform_visual_intent_id"] == "pinduoduo_fast_comprehension" for recipe in output.recipes)
    assert all("do not introduce price, discount, savings, or promotion claims" in recipe.visual_scene.lower() for recipe in output.recipes)
    assert output.marketplace_profile.metadata["profile_status"] == "internal_draft"
    assert output.export_package.metadata["platform_visual_intent_ids"]["main_image"] == "pinduoduo_fast_comprehension"
