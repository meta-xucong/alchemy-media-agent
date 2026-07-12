from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan(platform: str, slots: list[str], *, parameters: dict | None = None) -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input=f"Create a {platform} ecommerce image set for this desk lamp",
        product_profile={
            "product_category": "desk lamp",
            "selling_points": ["Adjustable angle", "Stable metal base"],
        },
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={"platform": platform, "suite_slot_request": slots, **(parameters or {})},
        platform_profile=None,
        job_key=f"e23_{platform}",
    )


def test_amazon_main_image_keeps_verified_baseline_while_secondary_images_are_evidence_led() -> None:
    output = _plan("amazon_us", ["main_image", "scenario_image"])
    recipes = {recipe.slot: recipe for recipe in output.recipes}

    main = recipes["main_image"]
    secondary = recipes["scenario_image"]
    assert main.metadata["evidence_intent_id"] == "primary_product_truth"
    assert main.metadata["platform_compliance_intent_id"] == "amazon_main_image_verified_baseline"
    assert main.metadata["platform_compliance_evidence_tier"] == "verified_requirement"
    assert "pure-white background" in main.visual_scene.lower()
    assert "category and regional exceptions" in main.visual_scene.lower()
    assert secondary.metadata["evidence_intent_id"] == "verified_use_context"
    assert secondary.metadata["platform_compliance_intent_id"] == "no_verified_platform_visual_override"
    assert "conversion-oriented secondary image" not in secondary.visual_scene.lower()


def test_ozon_default_does_not_impose_scene_led_styling_but_scene_story_is_opt_in() -> None:
    default_output = _plan("ozon", ["main_image", "scenario_image"])
    scene_output = _plan("ozon", ["main_image", "scenario_image"], parameters={"creative_strategy": "scene_story"})
    default_recipes = {recipe.slot: recipe for recipe in default_output.recipes}
    scene_recipes = {recipe.slot: recipe for recipe in scene_output.recipes}

    assert default_recipes["main_image"].metadata["creative_strategy_id"] == "evidence_first"
    assert "scene-led commerce composition" not in default_recipes["main_image"].visual_scene.lower()
    assert default_recipes["scenario_image"].metadata["evidence_intent_id"] == "verified_use_context"
    assert scene_recipes["main_image"].metadata["creative_strategy_id"] == "scene_story"
    assert scene_recipes["main_image"].metadata["creative_strategy_applied"] is False
    assert "restrained, believable scene" not in scene_recipes["main_image"].visual_scene.lower()
    assert scene_recipes["scenario_image"].metadata["creative_strategy_applied"] is True
    assert "restrained, believable scene" in scene_recipes["scenario_image"].visual_scene.lower()


def test_content_hook_is_explicit_and_cannot_create_price_or_promotion_claims() -> None:
    output = _plan("tiktok_shop", [], parameters={"delivery_scope": "content_assets", "creative_strategy": "content_hook"})
    recipes = {recipe.slot: recipe for recipe in output.recipes}

    assert recipes["content_cover"].metadata["creative_strategy_id"] == "content_hook"
    assert "truthful, immediately understandable visual hook" in recipes["content_cover"].visual_scene.lower()
    assert all(recipe.metadata["creative_strategy_id"] == "content_hook" for recipe in output.recipes)
    assert "price, discount, savings, or promotion" not in " ".join(recipe.visual_scene for recipe in output.recipes).lower()
