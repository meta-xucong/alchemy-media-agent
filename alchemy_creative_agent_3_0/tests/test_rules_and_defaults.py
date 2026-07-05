from alchemy_creative_agent_3_0.app.creative_core.rules import (
    RULE_VERSION,
    detect_industry,
    detect_platforms,
    detect_visual_tones,
    normalize_input,
)
from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.schemas import IndustryCategory, Platform


def test_keyword_mapping_for_industries() -> None:
    assert detect_industry(normalize_input("奶茶夏季新品")) == IndustryCategory.BEVERAGE
    assert detect_industry(normalize_input("烧烤夜宵促销")) == IndustryCategory.RESTAURANT_BARBECUE
    assert detect_industry(normalize_input("火锅套餐")) == IndustryCategory.RESTAURANT_HOTPOT
    assert detect_industry(normalize_input("美甲开业优惠")) == IndustryCategory.LOCAL_SERVICE_BEAUTY
    assert detect_industry(normalize_input("蓝牙耳机淘宝主图")) == IndustryCategory.ECOMMERCE_PRODUCT


def test_beauty_portrait_does_not_become_local_service() -> None:
    assert (
        detect_industry(normalize_input("East Asian summer beauty portrait photo with green-highlighted hair"))
        == IndustryCategory.UNKNOWN
    )
    assert detect_industry(normalize_input("beauty salon opening campaign")) == IndustryCategory.LOCAL_SERVICE_BEAUTY


def test_beauty_portrait_planning_does_not_use_local_service_pack() -> None:
    result = run_creative_planning(
        "Create an East Asian summer beauty portrait photo with green-highlighted hair for a social cover"
    )
    prompt_text = " ".join(
        [
            result.prompt_compilations[0].visual_prompt,
            " ".join(result.prompt_compilations[0].style_notes),
            " ".join(result.prompt_compilations[0].layout_notes),
        ]
    ).lower()

    assert result.commercial_brief.industry == IndustryCategory.UNKNOWN
    assert "service_detail" not in prompt_text
    assert "booking cta" not in prompt_text
    assert result.prompt_compilations[0].provider_notes.get("vertical_pack") != "local_service_agent_family"


def test_platform_mapping_defaults() -> None:
    assert detect_platforms(normalize_input("适合小红书和朋友圈")) == [Platform.XIAOHONGSHU, Platform.WECHAT_MOMENTS]
    assert detect_platforms(normalize_input("适合外卖")) == [Platform.DELIVERY_APP]
    assert detect_platforms(normalize_input("适合美团")) == [Platform.MEITUAN]
    assert detect_platforms(normalize_input("淘宝主图")) == [Platform.TAOBAO]
    assert detect_platforms(normalize_input("门店屏幕")) == [Platform.STORE_SCREEN]


def test_tone_mapping_and_rule_version_metadata() -> None:
    tones = detect_visual_tones(normalize_input("高级、清爽、有食欲、科技感"), IndustryCategory.BEVERAGE)

    assert {"premium", "clean", "fresh", "appetite", "tech"}.issubset(set(tones))
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书，风格要高级。")
    assert result.metadata["rules_version"] == RULE_VERSION
    assert result.creative_job.metadata["rules_version"] == RULE_VERSION


def test_default_series_and_single_image_behavior() -> None:
    default_result = run_creative_planning("做一个火锅店冬季套餐推广图，要热闹、有食欲，但不要太土。")
    single_result = run_creative_planning("只要单张咖啡店海报，适合小红书。")

    assert len(default_result.series_plan.assets) == 3
    assert len(single_result.series_plan.assets) == 1
    assert single_result.series_plan.assets[0].platform == Platform.XIAOHONGSHU

