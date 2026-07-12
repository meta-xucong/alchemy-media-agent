from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.category_profiles import (
    CATEGORY_PROFILE_VERSION,
    list_category_profiles,
    resolve_category,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.marketplace_rules import MarketplaceRuleEngine
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_first_release_category_catalog_is_versioned_and_has_five_profiles() -> None:
    profiles = list_category_profiles()

    assert len(profiles) == 5
    assert CATEGORY_PROFILE_VERSION.startswith("v3_ecommerce_categories_")
    assert {profile.category_id for profile in profiles} == {
        "apparel",
        "beauty",
        "electronics",
        "home_kitchen",
        "food_beverage",
    }
    assert all(profile.required_evidence for profile in profiles)
    assert all(profile.review_checks for profile in profiles)


def test_category_resolution_uses_product_category_and_aliases() -> None:
    assert resolve_category("wireless earbuds").category_id == "electronics"
    assert resolve_category("skincare serum").category_id == "beauty"
    assert resolve_category("drink bottle").category_id == "food_beverage"
    assert resolve_category("unclassified object") is None


def test_ozon_profile_is_versioned_and_uses_evidence_slots_without_fixed_export_size() -> None:
    profile = MarketplaceRuleEngine().profile(
        platform_profile="ozon",
        parameters={},
        product_profile={},
    )

    assert profile.platform == "ozon"
    assert profile.market == "RU"
    assert profile.image_slots[:2] == ["main_image", "scenario_image"]
    assert profile.metadata["live_policy_lookup"] is False
    assert profile.export_rules["naming"] == "{slot}_{index}_{platform}.png"
    assert profile.export_rules["dimension_hint"] == "seller placement configuration required"


def test_category_profile_is_attached_without_changing_public_recipe_shape() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create three marketplace images for wireless earbuds",
        product_profile={
            "product_category": "wireless earbuds",
            "selling_points": ["Compact case", "Comfortable fit", "Clear calls"],
        },
        uploaded_asset_ids=["earbuds_front"],
        scenario_parameters={"platform": "amazon_us", "requested_image_count": 3},
        platform_profile=None,
        job_key="e1_earbuds",
    )

    assert output.metadata["category_id"] == "electronics"
    assert output.marketplace_profile.metadata["category_id"] == "electronics"
    assert len(output.recipes) == 3
    assert output.recipes[0].metadata["category_profile_version"] == CATEGORY_PROFILE_VERSION
    assert output.recipes[0].slot == "main_image"


def test_unknown_category_keeps_generic_profile_boundary() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create a product image",
        product_profile={"product_category": "unclassified object"},
        uploaded_asset_ids=["object_front"],
        scenario_parameters={"platform": "amazon_us", "requested_image_count": 2},
        platform_profile=None,
        job_key="e1_unknown",
    )

    assert output.metadata["category_id"] == "generic_product"
    assert output.marketplace_profile.metadata["category_id"] == "generic_product"
    assert len(output.recipes) == 2
