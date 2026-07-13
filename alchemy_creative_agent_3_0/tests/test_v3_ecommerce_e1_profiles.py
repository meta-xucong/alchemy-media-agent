from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.category_profiles import CATEGORY_PROFILE_VERSION, list_category_profiles, resolve_category
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.marketplace_rules import MarketplaceRuleEngine


def test_category_catalog_is_versioned_evidence_questions_not_a_suite_map() -> None:
    profiles = list_category_profiles()
    assert len(profiles) == 5
    assert CATEGORY_PROFILE_VERSION.startswith("v3_ecommerce_evidence_questions_")
    assert all(profile.required_evidence and profile.review_checks for profile in profiles)
    assert all(profile.metadata()["creative_slot_map_present"] is False for profile in profiles)


def test_category_resolution_and_platform_constraints_do_not_create_slots() -> None:
    assert resolve_category("wireless earbuds").category_id == "electronics"
    assert resolve_category("skincare serum").category_id == "beauty"
    profile = MarketplaceRuleEngine().profile(platform_profile="ozon", parameters={}, product_profile={})
    assert profile.platform == "ozon"
    assert profile.image_slots == []
    assert profile.metadata["creative_slot_map_present"] is False
    assert profile.export_rules["naming"] == "{opaque_output_id}.png"
