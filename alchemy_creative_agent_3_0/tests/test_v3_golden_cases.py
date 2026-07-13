from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.schemas import IndustryCategory, Platform, ProviderStrategy, TextRenderingMode


def _platform_assets(result, platform):
    return [asset for asset in result.series_plan.assets if asset.platform == platform]


def _assert_global_foundation_shape(result) -> None:
    assert result.creative_job.raw_user_input
    assert result.series_plan.assets
    assert result.layout_plans
    assert result.prompt_compilations
    assert result.condition_plans
    assert result.generation_plans
    assert result.evaluation_reports
    assert result.asset_pack.planning_only is True
    for generation_plan in result.generation_plans:
        assert generation_plan.provider_strategy == ProviderStrategy.PLANNING_ONLY
    for layout in result.layout_plans:
        assert layout.text_rendering in {TextRenderingMode.NO_TEXT, TextRenderingMode.MODEL_TEXT_ALLOWED}
        assert layout.reserved_text_regions == []
    for prompt in result.prompt_compilations:
        assert prompt.provider_notes["text_rendering_owner"] == "image_provider"
        assert prompt.provider_notes["text_overlay_required"] is False


def test_golden_milk_tea_xiaohongshu_delivery() -> None:
    result = run_creative_planning("帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.BEVERAGE
    assert Platform.XIAOHONGSHU in result.commercial_brief.target_platforms
    assert Platform.DELIVERY_APP in result.commercial_brief.target_platforms
    assert {"fresh", "clean", "premium"}.issubset(set(result.commercial_brief.visual_tone))
    assert _platform_assets(result, Platform.XIAOHONGSHU)[0].aspect_ratio == "4:5"
    assert _platform_assets(result, Platform.DELIVERY_APP)[0].aspect_ratio == "1:1"
    assert result.brand_profile.is_temporary is True
    assert result.brand_profile.industry == IndustryCategory.BEVERAGE


def test_golden_barbecue_wechat_meituan() -> None:
    result = run_creative_planning("帮我做一组烧烤店夜宵促销图，干净高级一点，适合朋友圈和美团。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.RESTAURANT_BARBECUE
    assert Platform.WECHAT_MOMENTS in result.commercial_brief.target_platforms
    assert Platform.MEITUAN in result.commercial_brief.target_platforms
    assert "appetite" in result.commercial_brief.visual_tone
    assert "clean premium late-night" in result.creative_plan.visual_direction
    assert result.metadata["selected_vertical_pack"] == "restaurant_agent_family"


def test_golden_hotpot_default_series() -> None:
    result = run_creative_planning("做一个火锅店冬季套餐推广图，要热闹、有食欲，但不要太土。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.RESTAURANT_HOTPOT
    assert len(result.series_plan.assets) == 3
    assert "avoid_tacky" in result.creative_plan.negative_direction
    assert "warm steam" in result.creative_plan.materials_and_props


def test_golden_beauty_xiaohongshu_wechat() -> None:
    result = run_creative_planning("帮我做一个美甲店开业优惠图，适合小红书和朋友圈，风格要高级、温柔、干净。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.LOCAL_SERVICE_BEAUTY
    assert result.commercial_brief.scenario == "opening_promotion"
    assert {Platform.XIAOHONGSHU, Platform.WECHAT_MOMENTS}.issubset(set(result.commercial_brief.target_platforms))
    assert {"premium", "gentle", "clean"}.issubset(set(result.commercial_brief.visual_tone))


def test_golden_ecommerce_taobao_headphones() -> None:
    result = run_creative_planning("帮我做一组蓝牙耳机淘宝主图，要科技感、干净、突出降噪和续航。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.ECOMMERCE_PRODUCT
    assert Platform.TAOBAO in result.commercial_brief.target_platforms
    assert {"tech", "clean"}.issubset(set(result.commercial_brief.visual_tone))
    assert {"noise cancellation", "battery life"}.issubset(set(result.commercial_brief.selling_points))
    assert result.series_plan.assets[0].aspect_ratio == "1:1"
    assert result.metadata["selected_vertical_pack"] == "default_commercial_pack"


def test_golden_minimal_input_defaults() -> None:
    result = run_creative_planning("做一张咖啡店海报。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.BEVERAGE
    assert result.creative_job.requires_clarification is False
    assert len(result.series_plan.assets) == 3


def test_golden_explicit_chinese_text_is_provider_native() -> None:
    result = run_creative_planning("做一张火锅店海报，标题写“冬季双人套餐 128 元”，下面写“今日下单送小酥肉”。")
    _assert_global_foundation_shape(result)

    first_layout = result.layout_plans[0]
    assert first_layout.headline_area is None
    assert first_layout.cta_area is None
    assert first_layout.text_rendering == TextRenderingMode.MODEL_TEXT_ALLOWED
    assert first_layout.metadata["provider_native_literal_text"] == ["冬季双人套餐 128 元", "今日下单送小酥肉"]


def test_golden_unknown_industry_platform_still_plans() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书，风格要高级。")
    _assert_global_foundation_shape(result)

    assert result.commercial_brief.industry == IndustryCategory.UNKNOWN
    assert result.series_plan.assets[0].platform == Platform.XIAOHONGSHU
    assert result.series_plan.assets[0].aspect_ratio == "4:5"
    assert "premium" in result.commercial_brief.visual_tone

