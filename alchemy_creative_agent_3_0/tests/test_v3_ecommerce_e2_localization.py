from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.localization import (
    LOCALIZATION_PROFILE_VERSION,
    resolve_localization,
)
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_localization_defaults_follow_marketplace_without_claiming_translation() -> None:
    assert resolve_localization(platform="amazon", market="US").locale == "en-US"
    assert resolve_localization(platform="ozon", market="RU").locale == "ru-RU"
    assert resolve_localization(platform="taobao", market="CN").locale == "zh-CN"
    assert resolve_localization(platform="amazon", market="US", requested_locale="zh_CN").locale == "zh-CN"
    assert LOCALIZATION_PROFILE_VERSION.startswith("v3_ecommerce_localization_")


def test_main_image_forbids_copy_and_secondary_slot_passes_user_copy_to_provider() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create a marketplace product set",
        product_profile={"product_category": "wireless earbuds", "selling_points": ["Compact case"]},
        uploaded_asset_ids=["earbuds_front"],
        scenario_parameters={
            "platform": "amazon_us",
            "requested_image_count": 2,
            "overlay_copy": {"main_image": "Forbidden main badge", "feature_image_1": "Pocket-ready case"},
        },
        platform_profile=None,
        job_key="e2_amazon_copy",
    )

    main_image, feature = output.recipes
    assert main_image.slot == "main_image"
    assert main_image.overlay_text is None
    assert main_image.metadata["copy_plan"]["policy"] == "text_forbidden"
    assert feature.overlay_text is None
    assert feature.provider_native_text == "Pocket-ready case"
    assert feature.metadata["copy_plan"]["source"] == "user_supplied"
    assert feature.metadata["copy_plan"]["provider_native_text"] is True
    assert output.critic.metadata["localization_review_slots"] == []


def test_unsupplied_russian_copy_remains_an_llm_creative_direction() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Ozon listing image set for this drink",
        product_profile={"product_category": "drink", "selling_points": ["Fresh summer refreshment"]},
        uploaded_asset_ids=["drink_front"],
        scenario_parameters={"platform": "ozon", "requested_image_count": 2},
        platform_profile=None,
        job_key="e2_ozon_copy",
    )

    scenario = output.recipes[1]
    copy_plan = scenario.metadata["copy_plan"]
    assert output.marketplace_profile.metadata["copy_locale"] == "ru-RU"
    assert copy_plan["copy_locale"] == "ru-RU"
    assert copy_plan["source"] == "llm_creative_direction"
    assert copy_plan["text"] is None
    assert copy_plan["needs_localization_review"] is False
    assert output.critic.metadata["localization_review_slots"] == []
    assert output.export_package.files[1]["provider_native_text"] is None
    assert output.export_package.metadata["localization_review_required"] is False


def test_user_supplied_russian_copy_clears_metadata_localization_review() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="Create an Ozon listing image set for this drink",
        product_profile={"product_category": "drink", "selling_points": ["Fresh summer refreshment"]},
        uploaded_asset_ids=["drink_front"],
        scenario_parameters={
            "platform": "ozon",
            "requested_image_count": 2,
            "overlay_copy": {"scenario_image": "Свежий летний вкус"},
        },
        platform_profile=None,
        job_key="e2_ozon_supplied",
    )

    assert output.recipes[1].overlay_text is None
    assert output.recipes[1].provider_native_text == "Свежий летний вкус"
    assert output.recipes[1].metadata["copy_plan"]["needs_localization_review"] is False
    assert output.critic.metadata["localization_review_slots"] == []
    assert output.export_package.metadata["localization_review_required"] is False
