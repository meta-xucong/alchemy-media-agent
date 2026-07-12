from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.marketplace_rules import (
    PROFILE_STATUS,
    PROFILE_VERSION,
    MarketplaceRuleEngine,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_platform_profile_has_frozen_version_status_and_source_lineage() -> None:
    profile = MarketplaceRuleEngine().profile(
        platform_profile="amazon_us",
        parameters={},
        product_profile={},
    )

    assert profile.metadata["profile_id"] == "ecommerce_amazon_us"
    assert profile.metadata["profile_version"] == PROFILE_VERSION
    assert profile.metadata["profile_status"] == PROFILE_STATUS
    assert "confirm category and regional exceptions in Seller Central" in profile.metadata["profile_source_notes"]
    assert profile.metadata["profile_evidence_tier"] == "mixed_verified_and_internal"


def test_export_manifest_carries_platform_category_and_locale_lineage() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Ozon image suite for this drink",
        product_profile={
            "product_category": "drink",
            "selling_points": ["Fresh summer refreshment", "Portable bottle", "Clear package"],
        },
        uploaded_asset_ids=["drink_front"],
        scenario_parameters={"platform": "ozon"},
        platform_profile=None,
        job_key="e4_ozon_lineage",
    )

    export = output.export_package
    assert output.metadata["marketplace_profile_id"] == "ecommerce_ozon_ru"
    assert output.metadata["marketplace_profile_version"] == PROFILE_VERSION
    assert export.metadata["marketplace_profile_id"] == "ecommerce_ozon_ru"
    assert export.metadata["marketplace_profile_version"] == PROFILE_VERSION
    assert export.metadata["marketplace_profile_status"] == PROFILE_STATUS
    assert export.metadata["category_ids"] == ["food_beverage"]
    assert len(export.metadata["category_profile_versions"]) == 1
    assert export.metadata["copy_locale"] == "ru-RU"
    assert all(file["marketplace_profile_version"] == PROFILE_VERSION for file in export.files)
    assert all(file["canvas_source"] == "internal_neutral_fallback" for file in export.files)
    assert export.metadata["evidence_intent_ids"]
    assert "platform_visual_intent_ids" in export.metadata
    assert all("creative_strategy_applied" in file for file in export.files)
    assert any(check["id"] == "platform_profile_lineage" and check["status"] == "done" for check in output.critic.checks)
