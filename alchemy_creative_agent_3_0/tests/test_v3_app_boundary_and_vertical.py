from alchemy_creative_agent_3_0.app.app_shell import (
    API_NAMESPACE,
    PRODUCT_API_NAMESPACE,
    get_navigation_entry,
    get_product_route_aliases,
    get_route_contracts,
    get_ui_contract,
)
from alchemy_creative_agent_3_0.app.platform_adapters import V3AccountAdapter, V3BalanceAdapter, V3DeploymentAdapter
from alchemy_creative_agent_3_0.app.schemas import CommercialBrief, CreativeJob, IndustryCategory, Platform
from alchemy_creative_agent_3_0.app.vertical_agents import VerticalAgentRegistry


def _job() -> CreativeJob:
    return CreativeJob(job_id="job_test", raw_user_input="test")


def test_app_shell_contract_reserves_v3_entry_and_routes() -> None:
    nav = get_navigation_entry()
    routes = get_route_contracts()
    ui = get_ui_contract()

    assert nav["title_bar_entry"] is True
    assert nav["owned_by"] == "alchemy_creative_agent_3_0"
    assert API_NAMESPACE == "/api/v3/creative-agent"
    assert routes["create_job"] == "/api/v3/creative-agent/jobs"
    assert PRODUCT_API_NAMESPACE == "/v3"
    assert routes["create_creative_job"] == "/v3/creative-jobs"
    assert get_product_route_aliases()["select_creative_job"] == "/v3/creative-jobs/{job_id}/select"
    assert ui["calls_only_v3_api_namespace"] == "/api/v3/creative-agent"
    assert ui["does_not_share_v1_v2_workflow_state"] is True


def test_platform_adapters_are_mock_boundaries() -> None:
    assert V3AccountAdapter().current_account().metadata["runtime_mode"] == "mock_boundary"
    estimate = V3BalanceAdapter().estimate_planning_cost(asset_count=3)
    assert estimate.credits_required == 0
    assert V3BalanceAdapter().has_available_credits(0) is True
    deployment = V3DeploymentAdapter().current_deployment()
    assert deployment.route_namespace == "/api/v3/creative-agent"
    assert deployment.metadata["runtime_coupled_to_v1_v2"] is False


def test_vertical_agent_registry_selects_expected_stubs_and_fallback() -> None:
    registry = VerticalAgentRegistry()
    default_brief = CommercialBrief(
        brief_id="brief_default",
        job_id="job_test",
        industry=IndustryCategory.UNKNOWN,
        scenario="brand_or_commercial_poster",
        business_goal="test",
        target_platforms=[Platform.GENERIC_SOCIAL],
    )
    ecommerce_brief = default_brief.model_copy(update={"industry": IndustryCategory.ECOMMERCE_PRODUCT})
    restaurant_brief = default_brief.model_copy(update={"industry": IndustryCategory.RESTAURANT_HOTPOT})

    assert registry.select_pack(_job(), default_brief).name == "default_commercial_pack"
    # Product intent alone stays in the neutral path.  E-Commerce is selected
    # only by an explicit E-Commerce template/scenario request.
    assert registry.select_pack(_job(), ecommerce_brief).name == "default_commercial_pack"
    assert registry.select_pack(_job(), restaurant_brief).name == "restaurant_agent_family"


def test_beverage_request_with_delivery_channel_does_not_select_restaurant_pack() -> None:
    registry = VerticalAgentRegistry()
    beverage_brief = CommercialBrief(
        brief_id="brief_beverage",
        job_id="job_beverage",
        industry=IndustryCategory.BEVERAGE,
        scenario="new_product_promotion",
        business_goal="promote a new beverage product",
        target_platforms=[Platform.XIAOHONGSHU, Platform.DELIVERY_APP],
    )
    beverage_job = CreativeJob(
        job_id="job_beverage",
        raw_user_input="奶茶店新品促销，小红书和外卖平台",
    )

    selected_pack = registry.select_pack(beverage_job, beverage_brief)

    assert selected_pack.name == "default_commercial_pack"


def test_human_styling_request_does_not_select_ecommerce_pack_from_soft_apparel_words() -> None:
    registry = VerticalAgentRegistry()
    misclassified_brief = CommercialBrief(
        brief_id="brief_human_style",
        job_id="job_human_style",
        industry=IndustryCategory.ECOMMERCE_PRODUCT,
        scenario="brand_or_commercial_poster",
        business_goal="test",
        target_platforms=[Platform.GENERIC_SOCIAL],
    )
    human_style_job = CreativeJob(
        job_id="job_human_style",
        raw_user_input=(
            "Create a same-person portrait series with one layered translucent outfit, "
            "embroidered pattern family, sash, sleeve shape, and collar detail."
        ),
        optional_template_id="general_template",
        metadata={"template_id": "general_template", "scenario_id": "general_creative"},
    )

    assert registry.select_pack(human_style_job, misclassified_brief).name == "default_commercial_pack"
