from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def _plan_amazon_apparel_benchmark() -> object:
    return EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon US apparel listing suite for a cropped embroidered striped shirt.",
        product_profile={
            "product_category": "shirt",
            "visible_attributes": [
                "light blue and white fine vertical stripe",
                "collared neck",
                "front button placket",
                "cropped relaxed silhouette",
                "white floral embroidery on the shirt",
            ],
            "materials": ["cotton blend poplin"],
            "selling_points": [
                "cropped relaxed fit",
                "floral embroidery detail",
                "work-to-weekend styling",
            ],
            "unverified_visual_facts": ["back pintuck detail"],
        },
        uploaded_asset_ids=["apparel_front_reference"],
        scenario_parameters={"platform": "amazon_us", "market": "US"},
        platform_profile=None,
        job_key="e24_amazon_apparel_benchmark",
    )


def test_amazon_apparel_benchmark_has_a_complete_listing_evidence_map() -> None:
    output = _plan_amazon_apparel_benchmark()
    recipes = {recipe.slot: recipe for recipe in output.recipes}

    assert output.metadata["category_id"] == "apparel"
    assert [recipe.slot for recipe in output.recipes] == [
        "main_image",
        "feature_image_1",
        "feature_image_2",
        "detail_image",
        "scenario_image",
        "size_spec_image",
        "trust_comparison_image",
    ]
    assert recipes["main_image"].metadata["platform_compliance_intent_id"] == "amazon_main_image_verified_baseline"
    assert recipes["main_image"].overlay_text is None
    assert recipes["feature_image_1"].metadata["category_slot_guidance_id"] == "apparel_worn_front_fit"
    assert recipes["feature_image_2"].metadata["category_slot_guidance_id"] == "apparel_back_or_side_construction"
    assert recipes["detail_image"].metadata["category_slot_guidance_id"] == "apparel_material_or_embroidery_detail"
    assert recipes["scenario_image"].metadata["lifestyle_scene_category"] == "llm_directed"
    assert recipes["scenario_image"].metadata["category_slot_guidance_id"] == "apparel_real_wear_context"
    assert recipes["trust_comparison_image"].metadata["category_slot_guidance_id"] == "apparel_styling_versatility"
    assert "back pintuck detail" in recipes["feature_image_2"].required_product_facts


def test_amazon_apparel_benchmark_blocks_delivery_on_unverified_visual_facts() -> None:
    output = _plan_amazon_apparel_benchmark()

    check = next(check for check in output.critic.checks if check["id"] == "unverified_visual_fact_confirmation")
    assert check["status"] == "attention"
    assert output.critic.metadata["unverified_visual_facts"] == ["back pintuck detail"]
    assert any("back pintuck detail" in warning for warning in output.warnings)
    assert all(
        recipe.metadata["unverified_visual_facts"] == ["back pintuck detail"]
        for recipe in output.recipes
    )


def test_garment_specific_guidance_does_not_leak_to_bags_or_shoes() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon image suite for this leather handbag.",
        product_profile={"product_category": "bag", "selling_points": ["structured shape"]},
        uploaded_asset_ids=["bag_front_reference"],
        scenario_parameters={"platform": "amazon_us", "market": "US"},
        platform_profile=None,
        job_key="e24_bag_isolation",
    )

    assert output.metadata["category_id"] == "apparel"
    assert all(recipe.metadata["category_slot_guidance_id"].startswith("accessory_") for recipe in output.recipes)
    assert all("garment" not in recipe.metadata["category_slot_guidance"].lower() for recipe in output.recipes)
