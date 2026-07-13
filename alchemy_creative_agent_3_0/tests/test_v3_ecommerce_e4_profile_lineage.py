from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.marketplace_rules import PROFILE_STATUS, PROFILE_VERSION, MarketplaceRuleEngine
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_platform_constraints_have_frozen_lineage_without_policy_claims_or_slots() -> None:
    profile = MarketplaceRuleEngine().profile(platform_profile="amazon_us", parameters={}, product_profile={})
    assert profile.metadata["profile_id"] == "ecommerce_amazon_us"
    assert profile.metadata["profile_version"] == PROFILE_VERSION
    assert profile.metadata["profile_status"] == PROFILE_STATUS
    assert profile.image_slots == []


def test_context_carries_platform_lineage_for_remote_brain() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create Ozon images for tea", product_profile={"product_category": "drink"}, uploaded_asset_ids=["tea"],
        scenario_parameters={"platform": "ozon"}, platform_profile=None, job_key="e4",
    )
    context = output.creative_context
    assert context is not None
    assert context.platform_constraints["profile_id"] == "ecommerce_ozon_ru"
    assert output.export_package.files == []
    assert any(check["id"] == "platform_constraint_lineage" and check["status"] == "done" for check in output.critic.checks)
