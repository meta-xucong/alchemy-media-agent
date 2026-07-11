from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.category_profiles import resolve_category
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_common_product_descriptions_resolve_to_first_release_category_profiles() -> None:
    assert resolve_category("LED desk lamp").category_id == "home_kitchen"
    assert resolve_category("wireless keyboard").category_id == "electronics"
    assert resolve_category("hydrating face serum").category_id == "beauty"
    assert resolve_category("kitchen storage organizer").category_id == "home_kitchen"
    assert resolve_category("canvas shoulder bag").category_id == "apparel"


def test_conditional_capacity_is_not_reported_missing_for_home_product_without_capacity() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Amazon image set for this LED desk lamp",
        product_profile={
            "product_category": "desk lamp",
            "materials": ["metal", "frosted diffuser"],
            "selling_points": ["Adjustable angle", "Stable metal base", "Soft desk light"],
        },
        uploaded_asset_ids=["lamp_front"],
        scenario_parameters={"platform": "amazon_us"},
        platform_profile=None,
        job_key="e8_lamp_category",
    )

    coverage = output.critic.metadata["category_evidence"]
    assert coverage["category_id"] == "home_kitchen"
    assert "capacity or quantity when confirmed" not in coverage["required"]
    assert coverage["missing"] == []
    assert output.metadata["category_id"] == "home_kitchen"
