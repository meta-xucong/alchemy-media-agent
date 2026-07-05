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
    VISUAL_HUMAN_REAL_CAMERA_TUNING_ID,
    VisionOutputInspector,
    provider_casebook_prompt_lines,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.module import (
    VisualCapabilityClusterModule,
    _looks_like_human_prompt,
)


ROOT = Path(__file__).resolve().parents[1]


def test_doc70_human_real_camera_tuning_is_v3_owned() -> None:
    source = (ROOT / "app" / "shared_capabilities" / "visual_cluster" / "casebook_recipes.py").read_text(
        encoding="utf-8"
    )

    assert VISUAL_HUMAN_REAL_CAMERA_TUNING_ID == "human_real_camera_ai_feel_tuning"
    assert "custom_media_agent_2_0" not in source
    assert "AlchemyOS" not in source
    assert "sub2api" not in source
    assert "requests" not in source
    assert "http://" not in source
    assert "https://" not in source


def test_doc70_human_guidance_adds_real_camera_and_anti_beauty_app_rules() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc70_human",
        job_id="job_doc70_human",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create an East Asian summer beauty portrait photo with a realistic camera feel",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=True,
    )
    positives = " ".join(guidance.positive_prompt_fragments)
    negatives = " ".join(guidance.negative_prompt_fragments)
    retry = " ".join(guidance.retry_patch_templates["artifact_repair"])

    assert guidance.metadata["doc70_human_real_camera_tuning"] is True
    assert guidance.metadata["human_real_camera_tuning_library"] == VISUAL_HUMAN_REAL_CAMERA_TUNING_ID
    assert "soft 35mm or CCD-inspired" in positives
    assert "under-eye texture" in positives
    assert "beauty-app face" in negatives
    assert "idol photocard polish" in negatives
    assert "skin-blur retouching" in negatives
    assert "auto face-slimming" in negatives
    assert "liquified face proportions" in negatives
    assert "camera-ready human realism" in positives
    assert "bright daylight" in positives
    assert "imperfect half-smile" in positives
    assert "uniform luminous skin" in negatives
    assert "sweet K-idol template smile" in negatives
    assert "soft real-camera capture" in retry
    assert "face-slimming filters" in retry
    assert "poreless glow" in retry
    assert "template-smile portraits" in retry


def test_doc70_role_recipe_contains_candid_non_photocard_pressure() -> None:
    plan = ModeAwareRoleDirector().build(
        project_id="project_doc70_roles",
        job_id="job_doc70_roles",
        user_input="same East Asian summer portrait set, realistic camera captured",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    )
    cover = plan.role_recipes[0]
    focus = plan.role_recipes[1]
    cover_text = " ".join([cover.prompt_pressure, *cover.negative_pressure, *cover.review_checks])
    focus_text = " ".join([focus.prompt_pressure, *focus.negative_pressure, *focus.review_checks])

    assert cover.metadata["doc70_human_real_camera_tuning"] is True
    assert "sweet template smile" in cover_text
    assert "imperfect half-smile" in cover_text
    assert "idol photocard face" in cover_text
    assert "candid non-doll expression" in focus_text
    assert "skin-blur retouching" in focus_text


def test_doc70_provider_prompt_renders_real_camera_ai_feel_reduction_atoms() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc70_provider",
        job_id="job_doc70_provider",
        user_input="Create a realistic same-person summer portrait suite",
        mode="delivery_suite",
        requested_image_count=2,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[0].model_dump(mode="json")
    helper_text = "\n".join(provider_casebook_prompt_lines(recipe))

    assert "Prompt atom camera stack:" in helper_text
    assert "soft 35mm or CCD-inspired" in helper_text
    assert "Prompt atom negative guard:" in helper_text
    assert "beauty-app face" in helper_text

    asset = AssetSpec(
        asset_id="asset_doc70_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="same-person portrait suite with less AI face feel",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc70_provider",
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
        condition_plan=ConditionPlan(condition_plan_id="condition_doc70_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc70_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc70_provider",
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

    assert "soft 35mm or CCD-inspired" in final_prompt
    assert "camera-real, directly usable creative image asset for a human photo" in final_prompt
    assert "Polish interpretation:" in final_prompt
    assert "beauty-app face" in final_prompt
    assert "idol photocard polish" in final_prompt
    assert "face slimming" in final_prompt
    assert "V-shaped chin" in final_prompt
    assert "same expression as every output" in final_prompt


def test_doc70_new_ai_feel_issue_codes_create_targeted_retry_patch() -> None:
    report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc70_review",
            project_id="project_doc70_review",
            job_id="job_doc70_review",
            candidate_id="candidate_doc70_review",
            output_id="output_doc70_review",
            status="ready",
        ),
        metadata={
            "post_generation_fake_issue_codes": [
                "beauty_app_face",
                "skin_blur_retouching",
            "perfect_smile_repetition",
            "face_slimming_filter",
            "beautified_facial_geometry",
            "generic_ai_beauty_identity",
        ],
            "post_generation_fake_confidence": 0.92,
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
    assert "beauty_app_face" in [issue["code"] for issue in report.detected_issues]
    assert "skin_blur_retouching" in [issue["code"] for issue in report.detected_issues]
    assert "perfect_smile_repetition" in [issue["code"] for issue in report.detected_issues]
    assert "face_slimming_filter" in [issue["code"] for issue in report.detected_issues]
    assert "beautified_facial_geometry" in [issue["code"] for issue in report.detected_issues]
    assert "generic_ai_beauty_identity" in [issue["code"] for issue in report.detected_issues]
    assert "beauty-app polish" in patch_text
    assert "skin-blur retouching" in patch_text
    assert "perfect smile repeated" in patch_text
    assert "beauty-filter facial reshaping" in patch_text


def test_doc70_stylized_requests_remain_exempt() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_doc70_stylized",
        job_id="job_doc70_stylized",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create an anime portrait illustration with a cinematic summer mood",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=False,
    )

    assert guidance.applies is False


def test_doc70_human_style_signals_reinterpret_premium_as_real_camera() -> None:
    assert _looks_like_human_prompt("高级清爽东方美女写真") is True

    module = VisualCapabilityClusterModule()
    signals = module._style_signals(  # noqa: SLF001
        capability_input=type(
            "FakeCapabilityInput",
            (),
            {"user_input": "高级清爽东方美女写真", "metadata": {}},
        )(),
        project_context={},
        selected_cases=[],
        grammar_lock={},
        history_reference={},
        asset_analyses=[],
    )

    assert "premium real-camera portrait finish" in signals
    assert "premium polished finish" not in signals
