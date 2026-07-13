from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.marketplace_rules import MarketplaceRuleEngine
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_marketplace_text_policy_forbids_local_renderer_without_fixed_text_slots() -> None:
    amazon = MarketplaceRuleEngine().profile(platform_profile="amazon_us", parameters={}, product_profile={})
    assert amazon.metadata["text_policy"]["default"] == "provider_native_only"
    assert amazon.metadata["text_policy"]["local_renderer"] == "forbidden"
    assert "text_forbidden_slots" not in amazon.metadata["text_policy"]


def test_legacy_overlay_field_is_not_treated_as_approved_copy() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create a Shopify product set", product_profile={"product_category": "wireless earbuds"},
        uploaded_asset_ids=["earbuds_front"],
        scenario_parameters={"platform": "shopify", "overlay_copy": {"hero_image": "Do not render"}},
        platform_profile=None, job_key="e7",
    )
    assert output.creative_context is not None
    assert output.creative_context.approved_literal_copy is None
    assert output.recipes == []
