import base64
from io import BytesIO
from pathlib import Path

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import ModeAwareRoleDirector
from app.schemas import ImageGenerationResult


def _png_base64(width: int = 96, height: int = 72) -> str:
    from PIL import Image

    image = Image.new("RGB", (width, height), color=(66, 109, 134))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def test_doc59_mode_role_director_makes_four_modes_distinct() -> None:
    director = ModeAwareRoleDirector()
    expected = {
        "selection_candidates": ("near_neighbor_candidates", "candidate_best_frame"),
        "delivery_suite": ("purposeful_delivery_roles", "cover_hero"),
        "creative_exploration": ("concept_lanes", "concept_clean_bright"),
        "format_layout_adaptation": ("format_roles", "vertical_cover"),
    }

    for mode, (strategy, first_role) in expected.items():
        plan = director.build(
            project_id="project_doc59",
            job_id="job_doc59",
            user_input="same East Asian summer portrait set",
            mode=mode,
            requested_image_count=4,
            subject_type="character",
            scenario_id="general_creative",
            template_id="general_template",
            has_identity_anchor=True,
        )

        assert plan.mode == mode
        assert plan.policy.role_strategy == strategy
        assert plan.role_recipes[0].role_key == first_role
        assert len({recipe.role_key for recipe in plan.role_recipes}) == 4
        assert all(recipe.prompt_pressure for recipe in plan.role_recipes)


def test_doc60_ecommerce_recipe_aligned_roles_keep_requested_slots() -> None:
    director = ModeAwareRoleDirector()

    plan = director.build_from_ecommerce_recipes(
        project_id="project_doc60",
        job_id="job_doc60",
        user_input="Create an ecommerce product suite",
        requested_image_count=3,
        ecommerce_recipes=[
            {"slot": "main_image", "business_goal": "click", "visual_scene": "clean hero"},
            {
                "slot": "feature_image_1",
                "business_goal": "understand",
                "selling_point": "summer freshness",
                "visual_scene": "feature proof with lime and condensation",
                "required_product_facts": ["turquoise can", "lime mint label"],
            },
            {"slot": "scenario_image", "business_goal": "desire", "visual_scene": "real outdoor cafe table"},
        ],
        template_id="ecommerce",
        scenario_id="ecommerce",
    )

    assert plan.metadata["doc"] == "60"
    assert plan.metadata["ecommerce_recipe_aligned"] is True
    assert [recipe.role_key for recipe in plan.role_recipes] == ["main_image", "feature_image_1", "scenario_image"]
    assert plan.role_recipes[1].metadata["ecommerce_slot"] == "feature_image_1"
    assert "lime mint label" in " ".join(plan.role_recipes[1].must_keep_rules)
    assert "without rendered text" in plan.role_recipes[1].prompt_pressure


def test_doc60_ecommerce_role_review_detects_slot_mismatch() -> None:
    director = ModeAwareRoleDirector()
    plan = director.build_from_ecommerce_recipes(
        project_id="project_doc60_review",
        job_id="job_doc60_review",
        user_input="Create an ecommerce product suite",
        requested_image_count=3,
        ecommerce_recipes=[
            {"slot": "main_image"},
            {"slot": "feature_image_1"},
            {"slot": "scenario_image"},
        ],
    )

    review = director.review(
        project_id="project_doc60_review",
        job_id="job_doc60_review",
        role_plan=plan,
        generated_candidates=[
            {"metadata": {"mode_role_recipe": {"role_key": "main_image"}}},
            {"metadata": {"mode_role_recipe": {"role_key": "scenario_image"}}},
            {"metadata": {"mode_role_recipe": {"role_key": "detail_image"}}},
        ],
    )

    assert review.status == "retry_recommended"
    assert "ecommerce_slot_mismatch" in review.issue_codes
    assert "requested listing slot ignored" in " ".join(review.retry_patch["negative_additions"])


def test_doc62_portrait_delivery_roles_have_natural_role_lanes() -> None:
    director = ModeAwareRoleDirector()

    plan = director.build(
        project_id="project_doc62",
        job_id="job_doc62",
        user_input="Create a same East Asian beauty portrait suite",
        mode="delivery_suite",
        requested_image_count=4,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    )

    role_metadata = {recipe.role_key: recipe.metadata for recipe in plan.role_recipes}
    assert set(role_metadata) == {
        "cover_hero",
        "subject_focus",
        "side_or_three_quarter_angle",
        "wide_scene_or_context",
    }
    assert all(metadata["doc"] == "62" for metadata in role_metadata.values())
    assert all(metadata["portrait_suite_director"] is True for metadata in role_metadata.values())
    assert "direct or near-camera gaze" in role_metadata["cover_hero"]["gaze_lane"]
    assert "slightly off-camera" in role_metadata["subject_focus"]["gaze_lane"]
    assert "away from camera" in role_metadata["side_or_three_quarter_angle"]["gaze_lane"]
    assert "three-quarter or full-body" in role_metadata["wide_scene_or_context"]["subject_scale_lane"]
    assert len({metadata["pose_lane"] for metadata in role_metadata.values()}) == 4
    assert all("same recognizable person direction" in recipe.must_keep_rules for recipe in plan.role_recipes)


def test_visual_cluster_exposes_doc59_role_plan_and_review(tmp_path: Path) -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        CapabilityInput(
            job_id="job_doc59_cluster",
            scenario_id="general_creative",
            user_input="Create a same-person summer portrait suite with different camera duties",
            metadata={
                "requested_image_count": 4,
                "effective_variation_mode": "delivery_suite",
                "project_context_snapshot": {
                    "project_id": "project_doc59_cluster",
                    "template_id": "general_template",
                    "selected_output_assets": [{"output_id": "v3_output_anchor"}],
                    "selected_reference_assets": [{"asset_ref_id": "v3_output_anchor", "use_policy": "identity"}],
                },
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    role_plan = cluster["role_specific_generation_plan"]
    mode_review = cluster["mode_differentiation_review"]

    assert role_plan["mode"] == "delivery_suite"
    assert role_plan["policy"]["role_strategy"] == "purposeful_delivery_roles"
    assert [item["role_key"] for item in role_plan["role_recipes"][:4]] == [
        "cover_hero",
        "subject_focus",
        "side_or_three_quarter_angle",
        "wide_scene_or_context",
    ]
    assert mode_review["status"] == "planned"
    assert cluster["mode_execution_policy"]["mode"] == "delivery_suite"
    assert cluster["general_suite_role_plan"]["metadata"]["role_specific_generation_plan"]["mode"] == "delivery_suite"


def test_product_api_mock_generation_persists_distinct_doc59_roles() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create a same East Asian summer portrait suite with cover, closeup, side angle, and wide scene",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "preset_id": "social_cover",
                "parameters": {"use_case_library": True},
            },
            "metadata": {
                "requested_image_count": 4,
                "effective_variation_mode": "delivery_suite",
                "variation_mode": "delivery_suite",
                "template_id": "general_template",
            },
        }
    )

    generated = service.generate_job(
        created.job_id,
        {"quality_mode": "standard", "metadata": {"requested_image_count": 4}},
    )

    role_keys = [
        item.metadata["asset_metadata"]["mode_role_recipe"]["role_key"]
        for item in generated.asset_series
    ]
    candidate_role_keys = [
        item.metadata["mode_role_recipe"]["role_key"]
        for item in generated.candidates
    ]

    assert generated.status == "generated"
    assert role_keys == [
        "cover_hero",
        "subject_focus",
        "side_or_three_quarter_angle",
        "wide_scene_or_context",
    ]
    assert candidate_role_keys == role_keys
    assert generated.metadata["post_generation_review"]["metadata"]["mode_differentiation_review"]["status"] == "pass"


def test_doc59_role_plan_reconciles_to_default_series_count_without_false_retry() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create the first clean premium launch poster",
            "scenario_selection": {"scenario_id": "general_creative", "preset_id": "social_cover"},
            "metadata": {
                "effective_variation_mode": "delivery_suite",
                "variation_mode": "delivery_suite",
                "template_id": "general_template",
            },
        }
    )

    generated = service.generate_job(created.job_id, {"quality_mode": "standard"})
    visual_cluster = generated.metadata.get("visual_cluster") or generated.metadata["shared_capabilities"]["visual_cluster"]
    role_plan = visual_cluster["role_specific_generation_plan"]
    mode_review = visual_cluster["mode_differentiation_review"]
    retry_decisions = visual_cluster["auto_retry_decisions"]

    assert generated.status == "generated"
    assert len(generated.asset_series) == 3
    assert role_plan["requested_image_count"] == 3
    assert len(role_plan["role_recipes"]) == 3
    assert visual_cluster["mode_role_plan_reconciled_to_series"] is True
    assert mode_review["status"] == "pass"
    assert not any(
        decision.get("should_retry")
        and (decision.get("metadata") or {}).get("source") == "mode_differentiation_review"
        for decision in retry_decisions
    )


def test_production_provider_prompt_consumes_doc59_role_contract(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    observed_prompt = ""

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        nonlocal observed_prompt
        observed_prompt = app_request.prompt_plan.variables["generation_prompt"]
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    asset = AssetSpec(
        asset_id="asset_doc59_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="same-person portrait suite side angle",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc59_provider",
        asset_id=asset.asset_id,
        visual_prompt="clean summer East Asian portrait",
        negative_prompt="visible text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["clean", "summer"],
        layout_notes=["portrait"],
    )
    recipe = {
        "role_key": "side_or_three_quarter_angle",
        "label": "Angle variation",
        "purpose": "Side or three-quarter view",
        "prompt_pressure": "Create a side or three-quarter angle from the same shoot.",
        "shot_family": "angle portrait",
        "camera_distance": "medium",
        "angle_rule": "side or three-quarter",
        "crop_rule": "different framing",
        "scene_rule": "same shoot",
        "must_keep_rules": ["same recognizable person direction"],
        "must_not_rules": ["same exact still repeated"],
        "negative_pressure": ["same crop for every output"],
    }
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        response = provider.generate(
            GenerationRequest(
                asset_spec=asset,
                prompt_compilation=prompt,
                condition_plan=ConditionPlan(condition_plan_id="condition_doc59_provider", asset_id=asset.asset_id),
                generation_plan=GenerationPlan(
                    generation_plan_id="generation_doc59_provider",
                    asset_id=asset.asset_id,
                    provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
                    candidate_count=1,
                    max_refine_rounds=0,
                ),
                metadata={
                    "job_id": "job_doc59_provider",
                    "mode_execution_policy": {
                        "mode": "delivery_suite",
                        "role_difference_requirement": "different shot family or different image duty",
                    },
                    "mode_role_recipe": recipe,
                    "role_specific_generation_plan": {"mode": "delivery_suite", "role_recipes": [recipe]},
                },
            )
        )
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert "Role-specific generation contract" in observed_prompt
    assert "side or three-quarter" in observed_prompt
    assert response.candidates[0].metadata["mode_role_recipe"]["role_key"] == "side_or_three_quarter_angle"


def test_production_provider_prompt_consumes_doc62_portrait_role_lanes(tmp_path, monkeypatch) -> None:
    from app.config import settings

    old_key = settings.openai_api_key
    old_provider = settings.default_image_provider
    settings.openai_api_key = "test-key"
    settings.default_image_provider = "openai_gpt_image"

    observed_prompt = ""

    async def fake_generate(self, provider_name, app_request):  # noqa: ANN001
        nonlocal observed_prompt
        observed_prompt = app_request.prompt_plan.variables["generation_prompt"]
        return ImageGenerationResult(
            provider="openai_gpt_image",
            model="test-image-model",
            outputs=[
                {"b64_json": _png_base64(96, 72), "mime_type": "image/png", "format": "png", "width": 96, "height": 72},
            ],
        )

    monkeypatch.setattr(ProductionImageGenerationProvider, "_generate_with_app_provider", fake_generate)
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc62_provider",
        job_id="job_doc62_provider",
        user_input="Create a same East Asian portrait suite",
        mode="delivery_suite",
        requested_image_count=4,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[2].model_dump(mode="json")
    asset = AssetSpec(
        asset_id="asset_doc62_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="same-person portrait suite angle variation",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc62_provider",
        asset_id=asset.asset_id,
        visual_prompt="clean summer East Asian portrait",
        negative_prompt="visible text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["clean", "summer"],
        layout_notes=["portrait"],
    )
    try:
        provider = ProductionImageGenerationProvider(output_store=V3GeneratedOutputStore(tmp_path / "outputs"))
        provider.generate(
            GenerationRequest(
                asset_spec=asset,
                prompt_compilation=prompt,
                condition_plan=ConditionPlan(condition_plan_id="condition_doc62_provider", asset_id=asset.asset_id),
                generation_plan=GenerationPlan(
                    generation_plan_id="generation_doc62_provider",
                    asset_id=asset.asset_id,
                    provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
                    candidate_count=1,
                    max_refine_rounds=0,
                ),
                metadata={
                    "job_id": "job_doc62_provider",
                    "mode_execution_policy": {
                        "mode": "delivery_suite",
                        "role_difference_requirement": "different shot family or different image duty",
                    },
                    "mode_role_recipe": recipe,
                    "role_specific_generation_plan": {"mode": "delivery_suite", "role_recipes": [recipe]},
                    "template_id": "general_template",
                    "scenario_id": "general_creative",
                },
            )
        )
    finally:
        settings.openai_api_key = old_key
        settings.default_image_provider = old_provider

    assert "Role expression lane:" in observed_prompt
    assert "Role gaze lane: away from camera or toward the scene" in observed_prompt
    assert "Role pose lane: visible body turn" in observed_prompt
    assert "Clone avoidance: do not make another front-facing duplicate" in observed_prompt
    assert "Keep: same recognizable person direction" in observed_prompt
