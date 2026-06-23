from pathlib import Path
from uuid import uuid4

from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.brand_memory.preference_update import should_apply_memory_update
from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_creative_planning
from alchemy_creative_agent_3_0.app.schemas import (
    BrandProfile,
    CreativeJob,
    CommercialBrief,
    IndustryCategory,
    MemoryUpdate,
    Platform,
    ReferenceAsset,
)


def _test_store_root(name: str) -> Path:
    root = Path(__file__).resolve().parent / "_runtime_brand_memory" / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True)
    return root


def test_temporary_brand_profile_when_no_brand_id() -> None:
    result = run_creative_planning("帮我做一组奶茶店夏季新品促销图，要清爽、高级一点。")

    assert result.brand_profile.is_temporary is True
    assert result.brand_profile.brand_id.startswith("temp_brand_job_")
    assert "fresh" in result.brand_profile.visual_tone


def test_brand_profile_save_and_load() -> None:
    store = BrandProfileStore(_test_store_root("continuation"))
    service = BrandProfileService(store)
    profile = BrandProfile(
        brand_id="brand_test_001",
        industry=IndustryCategory.BEVERAGE,
        is_temporary=False,
        visual_tone=["fresh", "clean", "premium"],
        color_palette=["mint green", "cream white"],
        layout_preference="center product, top headline",
        reference_assets=[
            ReferenceAsset(
                asset_id="asset_best_001",
                asset_type="previous_final_output",
                source="v3_store",
                style_tags=["fresh", "clean"],
            )
        ],
        platform_history=[Platform.XIAOHONGSHU],
    )
    service.save_profile(profile)

    loaded = service.load_profile("brand_test_001")

    assert loaded is not None
    assert loaded.brand_id == "brand_test_001"
    assert loaded.is_temporary is False
    assert loaded.color_palette == ["mint green", "cream white"]


def test_continuation_request_loads_brand_profile() -> None:
    store = BrandProfileStore(_test_store_root("continuation_load"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_test_001",
            industry=IndustryCategory.BEVERAGE,
            is_temporary=False,
            visual_tone=["fresh", "clean", "premium"],
            color_palette=["mint green", "cream white"],
            layout_preference="center product, top headline",
            reference_assets=[
                ReferenceAsset(
                    asset_id="asset_best_001",
                    asset_type="previous_final_output",
                    source="v3_store",
                    style_tags=["fresh", "clean"],
                )
            ],
            platform_history=[Platform.XIAOHONGSHU],
        )
    )

    result = run_creative_planning(
        "沿用上次奶茶店的清爽风格，帮我做一个端午节活动图。",
        optional_brand_id="brand_test_001",
        brand_profile_service=service,
    )

    assert result.brand_profile.is_temporary is False
    assert result.brand_profile.brand_id == "brand_test_001"
    assert result.brand_profile.metadata["loaded_from_v3_store"] is True
    assert result.brand_profile.metadata["continuation_request"] is True
    assert "mint green" in result.prompt_compilations[0].visual_prompt
    assert result.condition_plans[0].style_condition.enabled is True
    assert result.asset_pack.brand_memory_update.applied is False


def test_missing_brand_id_falls_back_to_temporary_profile() -> None:
    service = BrandProfileService(BrandProfileStore(_test_store_root("missing")))
    result = run_creative_planning("沿用上次风格，做一个活动图。", optional_brand_id="brand_missing", brand_profile_service=service)

    assert result.brand_profile.is_temporary is True
    assert "not found" in result.brand_profile.metadata["warnings"][0]


def test_brand_profile_created_from_commercial_brief() -> None:
    service = BrandProfileService(BrandProfileStore(_test_store_root("from_brief")))
    job = CreativeJob(job_id="job_profile", raw_user_input="奶茶店清爽促销")
    brief = CommercialBrief(
        brief_id="brief_profile",
        job_id=job.job_id,
        industry=IndustryCategory.BEVERAGE,
        scenario="generic_promotion",
        business_goal="drive purchase",
        target_platforms=[Platform.XIAOHONGSHU],
        visual_tone=["fresh", "clean"],
        copy_strategy="short friendly promotion copy",
    )

    profile = service.create_profile_from_brief(job, brief, brand_id="brand_from_brief", brand_name="Test Tea")

    assert profile.brand_id == "brand_from_brief"
    assert profile.brand_name == "Test Tea"
    assert profile.is_temporary is False
    assert profile.industry == IndustryCategory.BEVERAGE
    assert profile.platform_history == [Platform.XIAOHONGSHU]
    assert {"fresh", "clean"}.issubset(set(profile.visual_tone))


def test_brand_profile_influences_creative_plan() -> None:
    store = BrandProfileStore(_test_store_root("creative_influence"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_creative",
            industry=IndustryCategory.BEVERAGE,
            is_temporary=False,
            visual_tone=["fresh", "premium"],
            color_palette=["mint green", "cream white"],
            layout_preference="asymmetric product on right with calm negative space",
            copywriting_tone="gentle repeatable brand voice",
        )
    )

    result = run_creative_planning("沿用上次风格，帮我做一个端午活动图。", "brand_creative", service)

    assert "fresh" in result.creative_plan.visual_direction
    assert "mint green" in result.creative_plan.consistency_strategy
    assert "asymmetric product on right" in result.creative_plan.composition_strategy
    assert result.creative_plan.copy_strategy == "gentle repeatable brand voice"


def test_brand_profile_influences_prompt_compilation() -> None:
    store = BrandProfileStore(_test_store_root("prompt_influence"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_prompt",
            industry=IndustryCategory.BEVERAGE,
            is_temporary=False,
            visual_tone=["fresh", "clean"],
            color_palette=["mint green", "cream white"],
            layout_preference="center product, top headline",
            typography_preference="rounded bold Chinese headline",
            copywriting_tone="warm concise CTA",
        )
    )

    result = run_creative_planning("沿用上次风格，做一个新品促销图。", "brand_prompt", service)
    prompt = result.prompt_compilations[0]

    assert "mint green" in prompt.visual_prompt
    assert "warm concise CTA" in prompt.visual_prompt
    assert "brand layout preference: center product, top headline" in prompt.layout_notes
    assert prompt.provider_notes["copywriting_tone"] == "warm concise CTA"
    assert prompt.metadata["brand_consistency_metadata"] is True


def test_rejected_style_tags_in_negative_direction() -> None:
    store = BrandProfileStore(_test_store_root("negative_tags"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_negative",
            industry=IndustryCategory.RESTAURANT_HOTPOT,
            is_temporary=False,
            visual_tone=["warm", "appetite"],
            color_palette=["warm red", "cream white"],
            rejected_style_tags=["avoid_tacky", "avoid_clutter"],
        )
    )

    result = run_creative_planning("沿用上次风格，做一个火锅套餐图。", "brand_negative", service)

    assert "avoid_tacky" in result.creative_plan.negative_direction
    assert "avoid_clutter" in result.prompt_compilations[0].negative_prompt
    assert result.prompt_compilations[0].provider_notes["negative_style_constraints"] == "avoid_tacky, avoid_clutter"


def test_continuation_without_brand_id_warns_and_uses_temporary_profile() -> None:
    result = run_creative_planning("沿用上次风格，帮我做一个端午节活动图。")

    assert result.creative_job.metadata["continuation_request"] is True
    assert result.brand_profile.is_temporary is True
    assert "no brand_id" in result.brand_profile.metadata["warnings"][0]


def test_memory_update_is_proposed_not_applied_by_default() -> None:
    result = run_creative_planning("帮我做一组奶茶店夏季新品促销图，要清爽。")
    update = result.asset_pack.brand_memory_update

    assert update is not None
    assert update.action == "propose"
    assert update.accepted_asset_ids
    assert update.applied is False
    assert update.metadata["planning_only"] is True
    assert should_apply_memory_update(update) is False


def test_mock_rejected_candidate_does_not_update_memory() -> None:
    update = MemoryUpdate(
        memory_update_id="memory_update_rejected",
        brand_id="brand_rejected",
        action="propose",
        accepted_asset_ids=["asset_bad"],
        applied=False,
        metadata={"planning_only": False, "candidate_rejected": True},
    )

    assert should_apply_memory_update(update) is False


def test_accepted_output_can_apply_memory_update_when_explicit() -> None:
    store = BrandProfileStore(_test_store_root("accepted_apply"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_apply",
            industry=IndustryCategory.BEVERAGE,
            is_temporary=False,
            visual_tone=["fresh"],
            color_palette=["mint green"],
        )
    )
    update = MemoryUpdate(
        memory_update_id="memory_update_apply",
        brand_id="brand_apply",
        action="propose",
        accepted_asset_ids=["asset_good"],
        new_style_tags=["premium"],
        applied=False,
        metadata={"planning_only": False},
    )

    updated_profile = service.apply_memory_update(update)

    assert updated_profile is not None
    assert "asset_good" in updated_profile.successful_asset_ids
    assert "premium" in updated_profile.visual_tone
    assert update.applied is True


def test_brand_memory_preserves_selected_vertical_pack_metadata() -> None:
    result = run_creative_planning("帮我做一组蓝牙耳机淘宝主图，要科技感、干净。")

    assert result.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.creative_plan.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.asset_pack.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.brand_profile.industry == IndustryCategory.ECOMMERCE_PRODUCT


def test_default_vertical_pack_still_works_with_brand_memory() -> None:
    result = run_creative_planning("帮我做一个活动宣传图，适合小红书，风格要高级。")

    assert result.metadata["selected_vertical_pack"] == "default_commercial_pack"
    assert result.brand_profile.is_temporary is True
    assert result.prompt_compilations[0].provider_notes["brand_consistency"]
