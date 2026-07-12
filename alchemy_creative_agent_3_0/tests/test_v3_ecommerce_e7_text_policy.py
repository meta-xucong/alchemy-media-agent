from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.marketplace_rules import MarketplaceRuleEngine
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_text_policy_is_owned_by_marketplace_profile_metadata() -> None:
    amazon = MarketplaceRuleEngine().profile(platform_profile="amazon_us", parameters={}, product_profile={})
    shopify = MarketplaceRuleEngine().profile(platform_profile="shopify", parameters={}, product_profile={})

    assert amazon.metadata["text_policy"]["text_forbidden_slots"] == ["main_image"]
    assert shopify.metadata["text_policy"]["text_forbidden_slots"] == ["hero_image"]
    assert amazon.metadata["text_policy"]["policy_owner"] == "ecommerce_amazon_profile"


def test_explicit_copy_obeys_profile_forbidden_slots_not_global_template_rules() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create a Shopify product set",
        product_profile={"product_category": "wireless earbuds", "selling_points": ["Compact case"]},
        uploaded_asset_ids=["earbuds_front"],
        scenario_parameters={
            "platform": "shopify",
            "requested_image_count": 2,
            "overlay_copy": {"hero_image": "Do not render", "feature_image_1": "Pocket-ready case"},
        },
        platform_profile=None,
        job_key="e7_shopify_policy",
    )

    hero, feature = output.recipes
    assert hero.slot == "hero_image"
    assert hero.overlay_text is None
    assert hero.metadata["copy_plan"]["source"] == "marketplace_profile"
    assert feature.overlay_text is None
    assert feature.provider_native_text == "Pocket-ready case"
    assert feature.metadata["copy_plan"]["policy"] == "text_requested"
