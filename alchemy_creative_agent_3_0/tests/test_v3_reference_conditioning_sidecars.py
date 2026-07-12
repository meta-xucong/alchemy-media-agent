from pathlib import Path
from uuid import uuid4

from alchemy_creative_agent_3_0.app.agents.generation_router_agent import GenerationRouterAgent
from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.condition_engine import (
    ComfyUISidecarProvider,
    ControlNetProvider,
    DiffusersProvider,
    IPAdapterProvider,
    InstantStyleProvider,
    NoopIdentityConditionProvider,
    NoopProductConditionProvider,
    PhotoMakerProvider,
    ProductConditionRequest,
    ReferenceProductProvider,
    LayoutConditionRequest,
    RuleBasedLayoutMapProvider,
    SimpleReferenceStyleProvider,
    StyleConditionRequest,
)
from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.evaluation import ImageRewardProvider
from alchemy_creative_agent_3_0.app.schemas import BrandProfile, IndustryCategory, Platform, ReferenceAsset


def _store_root(name: str) -> Path:
    root = Path(__file__).resolve().parent / "_runtime_brand_memory" / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True)
    return root


def _reference_brand() -> BrandProfile:
    return BrandProfile(
        brand_id="brand_v34_reference",
        industry=IndustryCategory.BEVERAGE,
        is_temporary=False,
        visual_tone=["fresh", "clean", "premium"],
        color_palette=["mint green", "cream white"],
        layout_preference="center product, top headline",
        reference_assets=[
            ReferenceAsset(
                asset_id="ref_best_style",
                asset_type="previous_final_output",
                source="v3_store",
                purpose="style continuation",
                style_tags=["fresh", "soft_light"],
                uri="mock://v3/reference/ref_best_style",
                score=0.92,
            ),
            ReferenceAsset(
                asset_id="ref_packaging",
                asset_type="product_reference",
                source="user_upload",
                purpose="product appearance",
                style_tags=["clean_packaging"],
                file_path="v3_owned/reference/ref_packaging.png",
                score=0.81,
            ),
        ],
        platform_history=[Platform.XIAOHONGSHU],
    )


def test_simple_reference_style_provider_builds_payload_from_reference_assets() -> None:
    result = run_creative_planning("沿用上次奶茶店的清爽风格，做一个新品图。")
    brand = _reference_brand()
    request = StyleConditionRequest(
        brand_profile=brand,
        asset_spec=result.series_plan.assets[0],
        creative_plan=result.creative_plan,
        reference_assets=brand.reference_assets,
    )
    response = SimpleReferenceStyleProvider().build_style_condition(request)

    assert response.condition_spec.enabled is True
    assert response.condition_spec.provider == "simple_reference_style_provider"
    assert response.condition_spec.reference_asset_ids == ["ref_best_style", "ref_packaging"]
    assert response.provider_payload["brand_palette"] == ["mint green", "cream white"]
    assert "soft_light" in response.condition_spec.metadata["style_tags"]


def test_rule_based_layout_provider_converts_layout_plan_to_condition_map() -> None:
    result = run_creative_planning("帮我做一个奶茶店活动宣传图，适合小红书。")
    request = LayoutConditionRequest(
        asset_spec=result.series_plan.assets[0],
        layout_plan=result.layout_plans[0],
        creative_plan=result.creative_plan,
    )
    response = RuleBasedLayoutMapProvider().build_layout_condition(request)

    assert response.condition_spec.enabled is True
    assert response.condition_spec.provider == "rule_based_layout_map_provider"
    assert response.layout_map["creative_focus"]["subject_area"]["position"] == "provider_directed"
    assert response.layout_map["creative_focus"]["composition_owner"] == "llm_and_image_provider"
    assert not response.layout_map["reserved_text_regions"]
    assert response.condition_spec.metadata["layout_map"]["visual_hierarchy"]


def test_generation_router_routes_reference_and_layout_conditions() -> None:
    store = BrandProfileStore(_store_root("v34_router"))
    service = BrandProfileService(store)
    service.save_profile(_reference_brand())

    result = run_creative_planning(
        "沿用上次奶茶店的清爽风格，做一个端午节活动图。",
        optional_brand_id="brand_v34_reference",
        brand_profile_service=service,
    )
    condition_plan = result.condition_plans[0]

    assert condition_plan.style_condition.enabled is True
    assert condition_plan.style_condition.provider == "simple_reference_style_provider"
    assert "ref_best_style" in condition_plan.style_condition.reference_asset_ids
    assert condition_plan.layout_condition.enabled is True
    assert condition_plan.layout_condition.provider == "rule_based_layout_map_provider"
    assert condition_plan.identity_condition.provider == "noop_identity_condition_provider"
    assert condition_plan.product_condition.provider == "noop_product_condition_provider"
    assert condition_plan.product_condition.reference_asset_ids == ["ref_packaging"]
    assert condition_plan.metadata["provider_routing"]["optional_sidecars"] is True
    assert result.generation_plans[0].metadata["routed_condition_providers"]["style"] == "simple_reference_style_provider"
    assert result.generation_plans[0].metadata["routed_condition_providers"]["product"] == "noop_product_condition_provider"


def test_generation_router_can_be_forced_to_noop_optional_providers() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")
    router = GenerationRouterAgent(enable_reference_conditioning=False, enable_layout_conditioning=False)
    condition_plan, generation_plan = router.create_generation_contracts(
        result.series_plan.assets[0],
        result.brand_profile,
        result.prompt_compilations[0],
        layout_plan=result.layout_plans[0],
        creative_plan=result.creative_plan,
    ).output

    assert condition_plan.style_condition.provider == "noop_style_condition_provider"
    assert condition_plan.layout_condition.provider == "noop_layout_condition_provider"
    assert condition_plan.layout_condition.enabled is False
    assert condition_plan.identity_condition.enabled is False
    assert condition_plan.product_condition.enabled is False
    assert generation_plan.metadata["routed_condition_providers"]["layout"] == "noop_layout_condition_provider"


def test_noop_identity_and_product_providers_record_matching_references() -> None:
    result = run_creative_planning("沿用产品包装和代言人形象，做一个新品活动图。")
    brand = _reference_brand()
    brand.reference_assets.append(
        ReferenceAsset(
            asset_id="ref_spokesperson",
            asset_type="identity_reference",
            source="user_upload",
            purpose="spokesperson identity",
            style_tags=["clean_model"],
            file_path="v3_owned/reference/ref_spokesperson.png",
            score=0.86,
        )
    )
    asset = result.series_plan.assets[0]

    identity = NoopIdentityConditionProvider().build_condition(asset, brand)
    product = NoopProductConditionProvider().build_product_condition(
        ProductConditionRequest(
            brand_profile=brand,
            asset_spec=asset,
            creative_plan=result.creative_plan,
            reference_assets=brand.reference_assets,
        )
    )

    assert identity.enabled is False
    assert identity.reference_asset_ids == ["ref_spokesperson"]
    assert product.condition_spec.enabled is False
    assert product.condition_spec.reference_asset_ids == ["ref_packaging"]
    assert product.condition_spec.metadata["runtime_mode"] == "noop"


def test_heavy_sidecar_facades_are_optional_and_unavailable_without_breaking_core() -> None:
    providers = [
        ImageRewardProvider(),
        IPAdapterProvider(),
        InstantStyleProvider(),
        ControlNetProvider(),
        PhotoMakerProvider(),
        ReferenceProductProvider(),
        ComfyUISidecarProvider(),
        DiffusersProvider(),
    ]

    assert all(provider.is_available() is False for provider in providers)
    assert all(provider.health_check()["available"] is False for provider in providers)
    assert IPAdapterProvider().capabilities().supports_style_conditioning is True
    assert ControlNetProvider().capabilities().supports_layout_conditioning is True
    assert PhotoMakerProvider().capabilities().supports_identity_conditioning is True
    assert ReferenceProductProvider().capabilities().supports_product_conditioning is True
    assert ImageRewardProvider().capabilities().supports_scoring is True

    result = run_creative_planning("帮我做一个活动宣传图，适合小红书。")

    assert result.condition_plans[0].layout_condition.provider == "rule_based_layout_map_provider"
    assert result.asset_pack.assets
