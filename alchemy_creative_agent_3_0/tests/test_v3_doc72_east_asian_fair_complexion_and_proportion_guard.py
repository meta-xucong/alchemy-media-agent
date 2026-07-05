from pathlib import Path

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
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
    GeneratedOutputResolution,
    HumanPhotorealismLayer,
    ModeAwareRoleDirector,
    VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID,
    VisionOutputInspector,
)


ROOT = Path(__file__).resolve().parents[1]


def test_doc72_guard_is_v3_owned() -> None:
    source = (ROOT / "app" / "shared_capabilities" / "visual_cluster" / "casebook_recipes.py").read_text(
        encoding="utf-8"
    )

    assert VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID == "human_east_asian_fair_complexion_guard"
    assert "custom_media_agent_2_0" not in source
    assert "AlchemyOS" not in source
    assert "sub2api" not in source
    assert "requests" not in source


def test_doc72_guidance_protects_fair_complexion_and_portrait_proportion() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc72_human",
        job_id="job_doc72_human",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a summer fresh East Asian beauty portrait photo, natural and commercial",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=True,
    )
    positives = " ".join(guidance.positive_prompt_fragments)
    negatives = " ".join(guidance.negative_prompt_fragments)
    retry = " ".join(guidance.retry_patch_templates["artifact_repair"])

    assert guidance.metadata["doc72_east_asian_fair_complexion_guard"] is True
    assert (
        guidance.metadata["human_east_asian_fair_complexion_guard_library"]
        == VISUAL_HUMAN_EAST_ASIAN_FAIR_COMPLEXION_GUARD_ID
    )
    assert "clean fair luminous complexion" in positives
    assert "do not darken or tan East Asian skin by default" in positives
    assert "natural head-to-body proportion" in positives
    assert "balanced neck and shoulder line" in positives
    assert "harmonious natural facial features" in positives
    assert "suppressed fair complexion" in negatives
    assert "forced tan or bronze cast unless requested" in negatives
    assert "gray-brown skin cast" in negatives
    assert "oversized head" in negatives
    assert "short compressed neck" in negatives
    assert "bad head-to-body ratio" in negatives
    assert "clean fair luminous complexion" in retry
    assert "head-to-body ratio" in retry


def test_doc72_provider_prompt_renders_guard_without_product_language() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc72_provider",
        job_id="job_doc72_provider",
        user_input="Create a clean summer East Asian portrait suite",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[1].model_dump(mode="json")
    asset = AssetSpec(
        asset_id="asset_doc72_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="fresh realistic East Asian portrait suite",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc72_provider",
        asset_id=asset.asset_id,
        visual_prompt="fresh summer East Asian portrait photo",
        negative_prompt="visible text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["fresh", "summer"],
        layout_notes=["portrait"],
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc72_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc72_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc72_provider",
            "mode_execution_policy": {"mode": "delivery_suite"},
            "mode_role_recipe": recipe,
            "role_specific_generation_plan": {"mode": "delivery_suite", "role_recipes": [recipe]},
            "template_id": "general_template",
            "scenario_id": "general_creative",
        },
    )

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001
    lowered = final_prompt.lower()

    assert "East Asian portrait aesthetic guard:" in final_prompt
    assert "clean fair luminous complexion" in final_prompt
    assert "do not darken or tan the skin by default" in final_prompt
    assert "natural head-to-body, neck, shoulder, and upper-body proportions" in final_prompt
    assert "fake whitening masks" in final_prompt
    assert "commercial product image asset" not in lowered
    assert "product label" not in lowered


def test_doc72_subject_focus_role_guards_close_crop_proportions() -> None:
    recipes = ModeAwareRoleDirector().build(
        project_id="project_doc72_role",
        job_id="job_doc72_role",
        user_input="Create a summer East Asian portrait suite with a closer photo",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes
    subject_focus = next(recipe for recipe in recipes if recipe.role_key == "subject_focus")
    text = " ".join(
        [
            subject_focus.prompt_pressure,
            subject_focus.camera_distance,
            *subject_focus.negative_pressure,
            *subject_focus.variation_axes,
        ]
    )

    assert "balanced face scale" in text
    assert "natural neck/shoulder line" in text
    assert "oversized head" in text
    assert "head-to-body proportion" in text


def test_doc72_issue_codes_create_retry_patch() -> None:
    report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc72_review",
            project_id="project_doc72_review",
            job_id="job_doc72_review",
            candidate_id="candidate_doc72_review",
            output_id="output_doc72_review",
            status="ready",
        ),
        metadata={
            "post_generation_fake_issue_codes": [
                "suppressed_fair_complexion",
                "forced_tan_or_bronze_cast",
                "gray_brown_skin_cast",
                "head_body_proportion_distortion",
                "oversized_head",
                "compressed_neck_shoulders",
                "unflattering_face_drift",
            ],
            "post_generation_fake_confidence": 0.92,
        },
    )
    patch_text = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["artifact_repair"],
            *report.retry_patch["composition_repair"],
            *report.retry_patch["negative_additions"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "suppressed_fair_complexion" in [issue["code"] for issue in report.detected_issues]
    assert "head_body_proportion_distortion" in [issue["code"] for issue in report.detected_issues]
    assert "clean fair luminous complexion" in patch_text
    assert "do not darken or tan East Asian skin by default" in patch_text
    assert "fake whitening masks" in patch_text
    assert "head-to-body ratio" in patch_text
    assert "compressed shoulders" in patch_text


def test_doc72_stylized_requests_remain_exempt() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc72_stylized",
        job_id="job_doc72_stylized",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create an anime East Asian summer portrait illustration with clean colors",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=False,
    )

    assert guidance.applies is False
