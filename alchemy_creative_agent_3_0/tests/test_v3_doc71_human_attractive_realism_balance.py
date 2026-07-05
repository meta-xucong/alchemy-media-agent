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
    VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID,
    VISUAL_HUMAN_REAL_CAMERA_TUNING_ID,
    VisionOutputInspector,
)


ROOT = Path(__file__).resolve().parents[1]


def test_doc71_attractive_realism_balance_is_v3_owned() -> None:
    source = (ROOT / "app" / "shared_capabilities" / "visual_cluster" / "casebook_recipes.py").read_text(
        encoding="utf-8"
    )

    assert VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID == "human_attractive_realism_balance_tuning"
    assert "custom_media_agent_2_0" not in source
    assert "AlchemyOS" not in source
    assert "sub2api" not in source
    assert "requests" not in source


def test_doc71_guidance_balances_real_texture_with_healthy_beauty() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc71_human",
        job_id="job_doc71_human",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a fresh bright East Asian summer portrait photo, natural but attractive",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=True,
    )
    positives = " ".join(guidance.positive_prompt_fragments)
    negatives = " ".join(guidance.negative_prompt_fragments)
    retry = " ".join(guidance.retry_patch_templates["artifact_repair"])

    assert guidance.metadata["doc70_human_real_camera_tuning"] is True
    assert guidance.metadata["human_real_camera_tuning_library"] == VISUAL_HUMAN_REAL_CAMERA_TUNING_ID
    assert guidance.metadata["doc71_human_attractive_realism_balance"] is True
    assert (
        guidance.metadata["human_attractive_realism_balance_library"]
        == VISUAL_HUMAN_ATTRACTIVE_REALISM_BALANCE_ID
    )
    assert "healthy clear complexion" in positives
    assert "soft natural bounce light" in positives
    assert "fresh bright skin tone" in positives
    assert "natural skin tone" in positives
    assert "dull complexion" in negatives
    assert "muddy skin tone" in negatives
    assert "underexposed face" in negatives
    assert "harsh facial shadow" in negatives
    assert "skin whitening filter" in negatives
    assert "beauty-app face" in negatives
    assert "soft natural bounce light" in retry
    assert "natural skin tone preserved" in retry


def test_doc71_provider_prompt_renders_attractive_realism_balance() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc71_provider",
        job_id="job_doc71_provider",
        user_input="Create a fresh bright same-person summer portrait suite",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[0].model_dump(mode="json")
    asset = AssetSpec(
        asset_id="asset_doc71_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="fresh realistic same-person portrait suite",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc71_provider",
        asset_id=asset.asset_id,
        visual_prompt="clean summer East Asian portrait photo",
        negative_prompt="visible text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["clean", "summer"],
        layout_notes=["portrait"],
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc71_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc71_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc71_provider",
            "mode_execution_policy": {"mode": "delivery_suite"},
            "mode_role_recipe": recipe,
            "role_specific_generation_plan": {"mode": "delivery_suite", "role_recipes": [recipe]},
            "template_id": "general_template",
            "scenario_id": "general_creative",
        },
    )

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001
    lowered = final_prompt.lower()

    assert "Attractive realism balance:" in final_prompt
    assert "healthy clear complexion" in final_prompt
    assert "soft natural bounce light" in final_prompt
    assert "natural skin tone" in final_prompt
    assert "skin whitening" in final_prompt
    assert "beauty-filter retouch" in final_prompt
    assert "commercial product image asset" not in lowered
    assert "product label" not in lowered


def test_doc71_cover_role_keeps_square_or_vertical_cover_framing() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc71_cover",
        job_id="job_doc71_cover",
        user_input="Create a fresh bright summer portrait suite",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[0]
    text = " ".join([recipe.prompt_pressure, recipe.camera_distance, *recipe.negative_pressure])

    assert "square or vertical cover-safe portrait framing" in text
    assert "horizontal banner crop" in text
    assert "letterboxed portrait" in text


def test_doc71_complexion_issue_codes_create_bounded_retry_patch() -> None:
    report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc71_review",
            project_id="project_doc71_review",
            job_id="job_doc71_review",
            candidate_id="candidate_doc71_review",
            output_id="output_doc71_review",
            status="ready",
        ),
        metadata={
            "post_generation_fake_issue_codes": [
                "dull_complexion",
                "muddy_skin_tone",
                "underexposed_face",
                "harsh_facial_shadow",
                "overly_matte_documentary_look",
                "tired_expression",
                "unflattering_color_cast",
            ],
            "post_generation_fake_confidence": 0.91,
        },
    )
    patch_text = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["artifact_repair"],
            *report.retry_patch["negative_additions"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "dull_complexion" in [issue["code"] for issue in report.detected_issues]
    assert "underexposed_face" in [issue["code"] for issue in report.detected_issues]
    assert "soft natural bounce light" in patch_text
    assert "healthy clear complexion" in patch_text
    assert "natural skin tone preserved" in patch_text
    assert "skin whitening filter" in patch_text


def test_doc71_stylized_requests_remain_exempt() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc71_stylized",
        job_id="job_doc71_stylized",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create an anime summer portrait illustration with bright colors",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=False,
    )

    assert guidance.applies is False
