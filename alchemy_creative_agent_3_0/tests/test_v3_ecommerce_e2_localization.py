from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.localization import LOCALIZATION_PROFILE_VERSION, resolve_localization
from alchemy_creative_agent_3_0.app.scenario_packs.ecommerce.pack import EcommerceScenarioPackPlanner


def test_localization_is_context_evidence_not_a_copy_or_slot_generator() -> None:
    assert resolve_localization(platform="amazon", market="US").locale == "en-US"
    assert resolve_localization(platform="ozon", market="RU").locale == "ru-RU"
    assert resolve_localization(platform="taobao", market="CN").locale == "zh-CN"
    assert LOCALIZATION_PROFILE_VERSION.startswith("v3_ecommerce_localization_")


def test_only_explicit_approved_literal_copy_enters_the_brain_context() -> None:
    output = EcommerceScenarioPackPlanner().plan(
        user_input="为 Ozon 做一组饮料图片",
        product_profile={"product_category": "drink"},
        uploaded_asset_ids=["drink_front"],
        scenario_parameters={"platform": "ozon", "approved_literal_copy": "Свежий летний вкус"},
        platform_profile=None,
        job_key="e2_ozon_copy",
    )
    assert output.creative_context is not None
    assert output.creative_context.copy_locale == "ru-RU"
    assert output.creative_context.approved_literal_copy == "Свежий летний вкус"
    assert output.recipes == []
