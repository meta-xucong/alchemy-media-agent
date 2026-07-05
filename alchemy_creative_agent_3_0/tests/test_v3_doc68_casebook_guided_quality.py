from pathlib import Path

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.schemas import (
    AssetSpec,
    AssetType,
    ConditionPlan,
    GenerationPlan,
    Platform,
    PromptCompilationResult,
    ProviderStrategy,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    HumanPhotorealismLayer,
    ModeAwareRoleDirector,
    ProjectIdentityAnchor,
    StrongReferenceClosureBuilder,
    StrongReferenceContinuationPlan,
    VISUAL_CASEBOOK_RECIPE_LIBRARY_ID,
    VisualIdentityLockProfile,
    provider_casebook_prompt_lines,
)


ROOT = Path(__file__).resolve().parents[1]


def test_doc68_casebook_helper_is_v3_owned_without_runtime_v1_v2_coupling() -> None:
    source = (ROOT / "app" / "shared_capabilities" / "visual_cluster" / "casebook_recipes.py").read_text(
        encoding="utf-8"
    )

    assert "custom_media_agent_2_0" not in source
    assert "AlchemyOS" not in source
    assert "sub2api" not in source
    assert "requests" not in source
    assert "http://" not in source
    assert "https://" not in source


def test_doc68_human_photorealism_consumes_casebook_recipe() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc68_portrait",
        job_id="job_doc68_portrait",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="East Asian summer cool portrait, realistic model photo, green-highlighted hair",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=True,
    )

    positive = " ".join(guidance.positive_prompt_fragments)
    negative = " ".join(guidance.negative_prompt_fragments)
    preserve = " ".join(guidance.reference_preserve_rules)
    review = " ".join(guidance.review_targets)
    retry = " ".join(guidance.retry_patch_templates["artifact_repair"])

    assert guidance.metadata["doc68_casebook_recipe"] is True
    assert guidance.metadata["casebook_recipe_library"] == VISUAL_CASEBOOK_RECIPE_LIBRARY_ID
    assert "visible fine pores" in positive
    assert "real shutter-moment" in positive
    assert "over-smoothed influencer face" in negative
    assert "identical face angle" in negative
    assert "different real camera frame" in preserve
    assert "photographed rather than generated" in review
    assert "real photographed skin texture" in retry


def test_doc68_four_general_modes_get_distinct_casebook_overlays() -> None:
    director = ModeAwareRoleDirector()
    expected = {
        "selection_candidates": "close comparable option",
        "delivery_suite": "hero/cover duty",
        "creative_exploration": "new concept lane",
        "format_layout_adaptation": "format and safe-area variation only",
    }

    for mode, role_difference in expected.items():
        plan = director.build(
            project_id=f"project_doc68_{mode}",
            job_id=f"job_doc68_{mode}",
            user_input="same East Asian summer portrait set",
            mode=mode,
            requested_image_count=4,
            subject_type="character",
            scenario_id="general_creative",
            template_id="general_template",
            has_identity_anchor=True,
        )
        first = plan.role_recipes[0]

        assert first.metadata["doc68_casebook_recipe"] is True
        assert first.metadata["casebook_recipe_library"] == VISUAL_CASEBOOK_RECIPE_LIBRARY_ID
        assert role_difference in first.metadata["casebook_role_difference"]
        assert first.variation_axes
        assert first.review_checks


def test_doc68_product_delivery_suite_strengthens_lifestyle_and_detail_roles() -> None:
    director = ModeAwareRoleDirector()
    plan = director.build(
        project_id="project_doc68_product",
        job_id="job_doc68_product",
        user_input="Create a drink product suite with outdoor summer lifestyle and detail images",
        mode="delivery_suite",
        requested_image_count=4,
        subject_type="product",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    )
    by_key = {recipe.role_key: recipe for recipe in plan.role_recipes}

    context = by_key["context_scene"]
    detail = by_key["detail_or_material_closeup"]

    assert context.metadata["doc68_casebook_recipe"] is True
    assert "genuinely lived-in lifestyle/context image" in context.prompt_pressure
    assert "not studio-only" in " ".join(context.review_checks)
    assert "product shape" in " ".join(context.must_keep_rules)
    assert "detail/material proof frame" in detail.prompt_pressure


def test_doc68_ecommerce_vertical_pack_reuses_casebook_without_losing_pack_ownership() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create Aqua Tea ecommerce images: main image, feature image, and outdoor cafe lifestyle scene",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "mode_id": "one_click_product_set",
                "platform_profile": "amazon_us",
                "parameters": {
                    "requested_image_count": 3,
                    "suite_slot_request": ["main_image", "feature_image_1", "scenario_image"],
                },
            },
            "uploaded_asset_ids": ["product_aqua_tea_can"],
            "product_profile": {
                "product_category": "drink",
                "materials": ["turquoise can", "AQUA TEA label"],
                "selling_points": ["summer freshness"],
            },
            "metadata": {"requested_image_count": 3, "variation_mode": "delivery_suite"},
        }
    )
    recipes = [
        asset.metadata["asset_metadata"]["mode_role_recipe"]
        for asset in created.asset_series
    ]
    scenario = next(recipe for recipe in recipes if recipe["role_key"] == "scenario_image")

    assert all(recipe["metadata"]["owned_by"] == "ecommerce_vertical_pack" for recipe in recipes)
    assert all(recipe["metadata"]["doc68_casebook_recipe"] is True for recipe in recipes)
    assert scenario["metadata"]["casebook_recipe_library"] == VISUAL_CASEBOOK_RECIPE_LIBRARY_ID
    assert "genuinely lived-in lifestyle/context image" in scenario["prompt_pressure"]
    assert "preserve product shape" in " ".join(scenario["must_keep_rules"])


def test_doc68_strong_reference_closure_adds_identity_truth_without_clone_pressure() -> None:
    closure = StrongReferenceClosureBuilder().build(
        project_id="project_doc68_reference",
        job_id="job_doc68_reference",
        subject_type="character",
        continuation_plan=StrongReferenceContinuationPlan(
            plan_id="plan_doc68",
            provider_required_reference_ids=["selected_output_1"],
            lock_targets=["person_identity"],
            prompt_additions=["keep the blue seaside light"],
            negative_additions=["do not repeat the source frame exactly"],
        ),
        anchors=[
            ProjectIdentityAnchor(
                anchor_id="anchor_doc68",
                subject_type="character",
                identity_keep_rules=["same broad face shape and green-highlighted hair direction"],
                style_keep_rules=["same summer seaside light"],
                allowed_variations=["change body pose"],
                forbidden_drift=["identity drift"],
            )
        ],
        identity_locks=[
            VisualIdentityLockProfile(
                lock_id="lock_doc68",
                subject_type="character",
                keep_rules=["same body type"],
                forbidden_drift=["face swap"],
                negative_constraints=["same exact still repeated"],
            )
        ],
        human_photorealism=HumanPhotorealismLayer().build(
            project_id="project_doc68_reference",
            job_id="job_doc68_reference",
            scenario_id="general_creative",
            template_id="general_template",
            user_input="realistic portrait",
            subject_type="character",
            variation_mode="delivery_suite",
            has_identity_reference=True,
        ),
    )

    assert closure.metadata["doc68_casebook_recipe"] is True
    assert "vary expression, gaze, head angle" in " ".join(closure.allowed_variations)
    assert "beauty-filter identity replacement" in " ".join(closure.forbidden_drift)
    assert any("new photographed moment" in item for item in closure.provider_prompt_rules)
    assert any("not through repeated expression" in item for item in closure.provider_prompt_rules)


def test_doc68_provider_prompt_consumes_casebook_role_metadata() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc68_provider",
        job_id="job_doc68_provider",
        user_input="Create a same East Asian portrait suite",
        mode="delivery_suite",
        requested_image_count=4,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[2].model_dump(mode="json")
    helper_lines = provider_casebook_prompt_lines(recipe)
    assert any(line.startswith("Casebook camera recipe:") for line in helper_lines)
    assert any(line.startswith("Casebook realism recipe:") for line in helper_lines)

    asset = AssetSpec(
        asset_id="asset_doc68_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="same-person portrait suite angle variation",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc68_provider",
        asset_id=asset.asset_id,
        visual_prompt="clean summer East Asian portrait",
        negative_prompt="visible text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["clean", "summer"],
        layout_notes=["portrait"],
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc68_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc68_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc68_provider",
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

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert "Casebook camera recipe:" in final_prompt
    assert "Casebook realism recipe:" in final_prompt
    assert "Casebook role difference:" in final_prompt
    assert "front-facing duplicate" in final_prompt
