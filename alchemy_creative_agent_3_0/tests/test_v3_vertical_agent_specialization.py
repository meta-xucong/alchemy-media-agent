from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning, run_generation_loop
from alchemy_creative_agent_3_0.app.schemas import IndustryCategory, Platform
from alchemy_creative_agent_3_0.app.vertical_agents import VerticalAgentRegistry


def test_v36_ecommerce_pack_specializes_standard_schema_outputs() -> None:
    result = run_creative_planning("帮我做一组蓝牙耳机淘宝主图和详情页，要干净科技感，突出降噪和续航。")

    assert result.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.metadata["vertical_pack_metadata"]["extends_v3_standard_schemas"] is True
    assert result.metadata["vertical_pack_metadata"]["forks_runtime"] is False
    assert "product clarity" in result.commercial_brief.commercial_hooks
    assert "feature_callout_space_required" in result.prompt_compilations[0].provider_notes
    assert result.layout_plans[0].product_area.position == "center_product_hero"
    assert all(asset.metadata["selected_vertical_pack"] == "ecommerce_agent_family" for asset in result.series_plan.assets)


def test_v36_restaurant_pack_specializes_food_conversion_outputs() -> None:
    result = run_creative_planning("帮我做一组火锅店冬季双人套餐美团团购图，要热气腾腾但干净。")

    assert result.metadata["selected_vertical_pack"] == "restaurant_agent_family"
    assert "appetite trigger" in result.commercial_brief.commercial_hooks
    assert result.layout_plans[0].product_area.position == "center_food_hero"
    assert result.prompt_compilations[0].provider_notes["food_appetite_required"] is True


def test_v36_brand_character_pack_selects_from_intent_and_preserves_original_identity_policy() -> None:
    result = run_creative_planning("为一个原创品牌IP形象做社交海报，突出角色表情和品牌故事。")

    assert result.metadata["selected_vertical_pack"] == "brand_ip_agent_family"
    assert result.commercial_brief.scenario == "brand_character"
    assert "recognizable character identity" in result.commercial_brief.commercial_hooks
    assert result.prompt_compilations[0].provider_notes["avoid_unlicensed_or_named_characters"] is True
    assert result.layout_plans[0].product_area.position == "center_character_anchor"


def test_v36_story_scene_pack_selects_from_intent_without_runtime_fork() -> None:
    result = run_creative_planning("做一套原创漫剧分镜封面，保持主角连续性和场景氛围，适合短视频封面。")

    assert result.metadata["selected_vertical_pack"] == "ai_manga_drama_agent_family"
    assert result.commercial_brief.scenario == "story_scene"
    assert result.prompt_compilations[0].provider_notes["original_characters_only"] is True
    assert result.layout_plans[0].product_area.position == "center_story_scene"
    assert result.metadata["v3_independent_runtime"] is True


def test_v36_local_service_pack_specializes_booking_conversion_outputs() -> None:
    result = run_creative_planning("给美甲店做开业优惠小红书宣传图，突出预约和干净高级的服务效果。")

    assert result.metadata["selected_vertical_pack"] == "local_service_agent_family"
    assert "appointment intent" in result.commercial_brief.commercial_hooks
    assert result.prompt_compilations[0].provider_notes["booking_cta_space_required"] is True
    assert result.layout_plans[0].product_area.position == "center_service_result"


def test_v36_vertical_registry_uses_priority_and_default_fallback() -> None:
    registry = VerticalAgentRegistry()

    ecommerce_job = run_creative_planning("淘宝耳机主图").creative_job
    ecommerce_brief = run_creative_planning("淘宝耳机主图").commercial_brief
    fallback = run_creative_planning("做一个普通活动宣传图，适合小红书。")

    assert registry.select_pack(ecommerce_job, ecommerce_brief).name == "ecommerce_agent_family"
    assert fallback.commercial_brief.industry == IndustryCategory.UNKNOWN
    assert fallback.metadata["selected_vertical_pack"] == "default_commercial_pack"
    assert fallback.asset_pack.metadata["selected_vertical_pack"] == "default_commercial_pack"


def test_v36_generation_result_preserves_vertical_policy_and_pack_metadata() -> None:
    result = run_generation_loop("帮我做一组蓝牙耳机京东主图，要科技感、干净。")

    assert result.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.metadata["vertical_evaluation_policy"]["mode"] == "ecommerce_product_clarity"
    assert result.metadata["vertical_evaluation_policy"]["commercial_score_delta"] > 0
    assert result.asset_pack.manifest["selected_vertical_pack"] == "ecommerce_agent_family"
    assert {asset.platform for asset in result.series_plan.assets}.issubset(
        {Platform.JD, Platform.ECOMMERCE_GENERIC, Platform.GENERIC_SOCIAL, Platform.XIAOHONGSHU}
    )
