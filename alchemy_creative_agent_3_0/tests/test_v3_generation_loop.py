from alchemy_creative_agent_3_0.app.creative_core.pipeline import run_generation_loop
from alchemy_creative_agent_3_0.app.brand_memory import BrandProfileService, BrandProfileStore
from alchemy_creative_agent_3_0.app.evaluation import MockScoringProvider, RuleBasedRefinementProvider, weighted_overall
from alchemy_creative_agent_3_0.app.generation_router import (
    GenerationRequest,
    MockGenerationProvider,
    rank_evaluated_candidates,
)
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    BrandProfile,
    CommercialBrief,
    ConditionPlan,
    CreativePlan,
    GenerationPlan,
    IndustryCategory,
    LayoutPlan,
    LayoutRegion,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
    Recommendation,
    TextRenderingMode,
)
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4


def _test_store_root(name: str) -> Path:
    # Keep Windows paths well below the legacy MAX_PATH boundary. The feature
    # test needs an isolated store, not a repository-relative artifact.
    root = Path(gettempdir()) / "alchemy_v3_generation" / f"{name}_{uuid4().hex}"
    root.mkdir(parents=True)
    return root


def _generation_request(mock_profile: str = "balanced") -> tuple[
    GenerationRequest,
    AssetSpec,
    CommercialBrief,
    BrandProfile,
    CreativePlan,
    LayoutPlan,
    PromptCompilationResult,
]:
    asset = AssetSpec(
        asset_id="asset_generation_test",
        asset_type=AssetType.MAIN_POSTER,
        platform=Platform.XIAOHONGSHU,
        aspect_ratio="4:5",
        purpose="main commercial campaign poster",
    )
    brief = CommercialBrief(
        brief_id="brief_generation_test",
        job_id="job_generation_test",
        industry=IndustryCategory.BEVERAGE,
        scenario="generic_promotion",
        business_goal="drive purchase",
        target_platforms=[Platform.XIAOHONGSHU],
        commercial_hooks=["promotion"],
        visual_tone=["fresh", "clean"],
    )
    brand = BrandProfile(
        brand_id="brand_generation_test",
        industry=IndustryCategory.BEVERAGE,
        visual_tone=["fresh", "clean"],
        color_palette=["mint green", "cream white"],
    )
    creative = CreativePlan(
        creative_plan_id="creative_generation_test",
        job_id="job_generation_test",
        brief_id=brief.brief_id,
        brand_id=brand.brand_id,
        concept="fresh beverage campaign",
        visual_direction="bright fresh commercial beverage image",
        composition_strategy="a clear beverage subject with prompt-directed natural balance",
        color_strategy=["mint green", "cream white"],
    )
    layout = LayoutPlan(
        layout_plan_id="layout_generation_test",
        asset_id=asset.asset_id,
        platform=asset.platform,
        aspect_ratio=asset.aspect_ratio,
        text_rendering=TextRenderingMode.MODEL_TEXT_ALLOWED,
        visual_hierarchy=["subject clarity", "scene atmosphere"],
        product_area=LayoutRegion(
            name="product_area",
            position="provider_directed",
        ),
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_generation_test",
        asset_id=asset.asset_id,
        visual_prompt="fresh clean beverage poster with mint green palette",
        negative_prompt="unreadable text",
        text_policy="provider_native_text_optional",
        style_notes=["fresh", "clean"],
        layout_notes=["provider-directed composition; no external text regions"],
        provider_notes={
            "text_rendering_owner": "image_provider",
            "provider_native_text": [],
            "provider_native_text_policy": "provider_native_text_optional",
            "text_overlay_required": False,
        },
    )
    condition = ConditionPlan(condition_plan_id="condition_generation_test", asset_id=asset.asset_id)
    generation = GenerationPlan(
        generation_plan_id="generation_test",
        asset_id=asset.asset_id,
        provider_strategy=ProviderStrategy.MOCK_GENERATION,
        candidate_count=4,
        max_refine_rounds=2,
        metadata={"mock_profile": mock_profile},
    )
    request = GenerationRequest(
        asset_spec=asset,
        layout_plan=layout,
        prompt_compilation=prompt,
        condition_plan=condition,
        generation_plan=generation,
    )
    return request, asset, brief, brand, creative, layout, prompt


def test_mock_generation_creates_candidates() -> None:
    request, *_ = _generation_request()
    response = MockGenerationProvider().generate(request)

    assert len(response.candidates) == 4
    assert response.candidates[0].provider == "mock_generation_provider"
    assert response.candidates[0].uri.startswith("mock://v3/")


def test_candidates_are_scored_and_formula_is_used() -> None:
    request, asset, brief, brand, creative, layout, prompt = _generation_request()
    candidate = MockGenerationProvider().generate(request).candidates[0]
    report = MockScoringProvider().score_candidate(candidate, asset, brief, brand, creative, layout, prompt)

    assert report.candidate_id == candidate.candidate_id
    assert report.recommendation == Recommendation.ACCEPT
    assert report.overall_score == weighted_overall(
        report.aesthetic_score,
        report.commercial_score,
        report.brand_consistency_score,
        report.layout_score,
        report.text_region_score,
        report.platform_fit_score,
    )


def test_best_candidate_is_selected_and_hard_failure_is_filtered() -> None:
    request, asset, brief, brand, creative, layout, prompt = _generation_request("hard_failure_first")
    response = MockGenerationProvider().generate(request)
    reports = [
        MockScoringProvider().score_candidate(candidate, asset, brief, brand, creative, layout, prompt)
        for candidate in response.candidates
    ]

    ranked = rank_evaluated_candidates(response.candidates, reports)

    assert ranked
    assert ranked[0][0].candidate_id != response.candidates[0].candidate_id
    assert all(problem.severity != "hard_failure" for problem in ranked[0][1].problems)


def test_retry_creates_refinement_plan_and_required_repairs() -> None:
    request, asset, brief, brand, creative, layout, prompt = _generation_request("needs_refinement")
    candidate = MockGenerationProvider().generate(request).candidates[0]
    report = MockScoringProvider().score_candidate(candidate, asset, brief, brand, creative, layout, prompt)
    refinement = RuleBasedRefinementProvider().propose_refinement(report)

    assert report.recommendation == Recommendation.RETRY
    assert refinement is not None
    assert any("commercial story and conversion cue" in item for item in refinement.prompt_modifications)
    assert not refinement.layout_modifications


def test_repair_mappings_cover_text_fake_and_brand_style() -> None:
    request, asset, brief, brand, creative, layout, prompt = _generation_request()
    provider = MockScoringProvider()
    candidates = MockGenerationProvider().generate(request).candidates
    candidates[0].metadata["forced_problem_codes"] = ["legacy_external_overlay_requested", "provider_native_text_fidelity_failure", "brand_style_missing"]
    report = provider.score_candidate(candidates[0], asset, brief, brand, creative, layout, prompt)
    refinement = RuleBasedRefinementProvider().propose_refinement(report)

    assert refinement is not None
    assert not refinement.layout_modifications
    assert any("provider-native complete-image path" in item for item in refinement.prompt_modifications)
    assert any("final-pixel text fidelity" in item for item in refinement.prompt_modifications)
    assert "inject BrandProfile visual tone and color palette" in refinement.prompt_modifications


def test_generation_loop_accepts_and_packages_selected_candidates() -> None:
    result = run_generation_loop("帮我做一组奶茶店夏季新品促销图，要清爽、高级一点，适合小红书和外卖平台。")

    assert result.metadata["candidate_loop"] is True
    assert result.asset_pack.planning_only is False
    assert result.asset_pack.manifest["selected_candidate_count"] == len(result.series_plan.assets)
    assert result.asset_pack.assets[0].metadata["selected_candidate_id"]
    assert result.asset_pack.assets[0].evaluation_id


def test_retry_budget_is_respected() -> None:
    result = run_generation_loop("帮我做一个活动宣传图，适合小红书。", mock_profile="exhaust_retries")

    assert result.metadata["refinement_plan_count"] == 2
    assert "exhausted refine budget" in " ".join(result.asset_pack.manifest["warnings"])
    assert result.asset_pack.brand_memory_update is None


def test_accepted_candidate_proposes_memory_update_and_rejected_does_not() -> None:
    accepted = run_generation_loop("帮我做一个奶茶店活动宣传图，适合小红书。")
    rejected = run_generation_loop("帮我做一个奶茶店活动宣传图，适合小红书。", mock_profile="all_hard_failure")

    assert accepted.asset_pack.brand_memory_update is not None
    assert accepted.asset_pack.brand_memory_update.applied is False
    assert accepted.asset_pack.brand_memory_update.new_reference_assets
    assert rejected.asset_pack.brand_memory_update is None


def test_explicit_memory_apply_saves_generated_reference_assets_and_platform_history() -> None:
    store = BrandProfileStore(_test_store_root("apply_generated_reference"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_generation_apply",
            industry=IndustryCategory.BEVERAGE,
            is_temporary=False,
            visual_tone=["fresh"],
            color_palette=["mint green"],
        )
    )

    result = run_generation_loop(
        "沿用上次风格，帮我做一个奶茶店活动宣传图，适合小红书。",
        optional_brand_id="brand_generation_apply",
        brand_profile_service=service,
        apply_memory_update=True,
    )
    updated = service.load_profile("brand_generation_apply")

    assert result.asset_pack.brand_memory_update.applied is True
    assert updated is not None
    assert updated.reference_assets
    assert updated.reference_assets[0].metadata["candidate_id"]
    assert updated.reference_assets[0].uri.startswith("mock://v3/")
    assert Platform.XIAOHONGSHU in updated.platform_history


def test_memory_apply_preserves_generated_reference_platform_per_asset() -> None:
    store = BrandProfileStore(_test_store_root("apply_generated_reference_multi"))
    service = BrandProfileService(store)
    service.save_profile(
        BrandProfile(
            brand_id="brand_generation_apply_multi",
            industry=IndustryCategory.BEVERAGE,
            is_temporary=False,
            visual_tone=["fresh"],
            color_palette=["mint green"],
        )
    )

    result = run_generation_loop(
        "沿用上次风格，帮我做一组奶茶店夏季新品促销图，适合小红书和外卖平台。",
        optional_brand_id="brand_generation_apply_multi",
        brand_profile_service=service,
        apply_memory_update=True,
    )
    updated = service.load_profile("brand_generation_apply_multi")
    expected_platforms = {asset.platform for asset in result.series_plan.assets}
    reference_platforms = {Platform(reference.metadata["platform"]) for reference in updated.reference_assets}

    assert updated is not None
    assert set(updated.successful_asset_ids) == {asset.asset_id for asset in result.series_plan.assets}
    assert reference_platforms == expected_platforms
    assert expected_platforms.issubset(set(updated.platform_history))


def test_asset_pack_preserves_selected_vertical_pack_metadata_and_hook() -> None:
    result = run_generation_loop("帮我做一组蓝牙耳机淘宝主图，要科技感、干净。")

    assert result.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.asset_pack.metadata["selected_vertical_pack"] == "ecommerce_agent_family"
    assert result.metadata["vertical_evaluation_policy"]["pack"] == "ecommerce_agent_family"


def test_generation_loop_runs_without_v2_imports() -> None:
    import sys

    run_generation_loop("帮我做一个活动宣传图，适合小红书。")

    forbidden = [name for name in sys.modules if name.startswith("custom_media_agent_2_0")]
    assert forbidden == []
