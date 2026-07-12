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
    GeneratedOutputResolution,
    ModeAwareRoleDirector,
    VISUAL_PROMPT_ATOM_RECIPE_ID,
    VisionOutputInspector,
    prompt_atom_recipe,
    provider_casebook_prompt_lines,
)


ROOT = Path(__file__).resolve().parents[1]


def test_doc69_prompt_atom_helper_is_v3_owned_without_runtime_v1_v2_coupling() -> None:
    source = (ROOT / "app" / "shared_capabilities" / "visual_cluster" / "casebook_recipes.py").read_text(
        encoding="utf-8"
    )

    assert VISUAL_PROMPT_ATOM_RECIPE_ID == "visual_prompt_atom_recipe"
    assert "custom_media_agent_2_0" not in source
    assert "AlchemyOS" not in source
    assert "sub2api" not in source
    assert "requests" not in source
    assert "http://" not in source
    assert "https://" not in source


def test_doc69_portrait_role_recipe_contains_prompt_atom_stacks() -> None:
    plan = ModeAwareRoleDirector().build(
        project_id="project_doc69_portrait",
        job_id="job_doc69_portrait",
        user_input="same East Asian summer portrait suite with realistic camera feel",
        mode="delivery_suite",
        requested_image_count=4,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    )
    recipe = plan.role_recipes[0]
    metadata = recipe.metadata

    assert metadata["doc69_prompt_atom_recipe"] is True
    assert metadata["prompt_atom_recipe_library"] == VISUAL_PROMPT_ATOM_RECIPE_ID
    assert "real lens perspective" in " ".join(metadata["prompt_atom_camera_stack"])
    assert "visible fine pores" in " ".join(metadata["prompt_atom_texture_stack"])
    assert "over-retouched fashion-doll face" in " ".join(metadata["prompt_atom_negative_guard"])
    assert "same person direction" in " ".join(metadata["prompt_atom_review_targets"])
    assert any("real-photo portrait atom stack" in recipe.prompt_pressure for _ in [0])


def test_doc69_product_and_ecommerce_receive_one_reference_truth_atoms() -> None:
    atom = prompt_atom_recipe(mode="delivery_suite", subject_type="product", role_key="scenario_image", index=3)

    assert atom["metadata"]["doc69_prompt_atom_recipe"] is True
    assert "one product truth" in " ".join(atom["metadata"]["prompt_atom_product_truth_guard"])
    assert "flat studio-only repetition" in " ".join(atom["metadata"]["prompt_atom_negative_guard"])

    created = V3ProductApiService().create_job(
        {
            "user_input": "Create Aqua Tea ecommerce suite with main, detail, and outdoor cafe lifestyle images",
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

    assert scenario["metadata"]["doc69_prompt_atom_recipe"] is True
    assert scenario["metadata"]["prompt_atom_recipe_library"] == VISUAL_PROMPT_ATOM_RECIPE_ID
    assert "one product truth" in " ".join(scenario["metadata"]["prompt_atom_product_truth_guard"])
    assert "real-use context" in " ".join(scenario["metadata"]["prompt_atom_review_targets"])


def test_doc69_provider_renders_prompt_atom_lines_from_metadata_only() -> None:
    recipe = ModeAwareRoleDirector().build(
        project_id="project_doc69_provider",
        job_id="job_doc69_provider",
        user_input="Create a realistic same-person summer portrait suite",
        mode="delivery_suite",
        requested_image_count=4,
        subject_type="character",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=True,
    ).role_recipes[1].model_dump(mode="json")
    helper_lines = provider_casebook_prompt_lines(recipe)

    assert any(line.startswith("Prompt atom camera stack:") for line in helper_lines)
    assert any(line.startswith("Prompt atom light/texture stack:") for line in helper_lines)
    assert any(line.startswith("Prompt atom reference guard:") for line in helper_lines)
    assert any(line.startswith("Prompt atom negative guard:") for line in helper_lines)

    asset = AssetSpec(
        asset_id="asset_doc69_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="1:1",
        purpose="same-person portrait suite angle variation",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc69_provider",
        asset_id=asset.asset_id,
        visual_prompt="clean summer portrait photo",
        negative_prompt="visible text",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["clean", "summer"],
        layout_notes=["portrait"],
    )
    request = GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc69_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc69_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc69_provider",
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

    assert "Prompt atom camera stack:" in final_prompt
    assert "Prompt atom light/texture stack:" in final_prompt
    assert "Prompt atom negative guard:" in final_prompt
    assert "over-retouched fashion-doll face" in final_prompt


def test_doc69_generic_role_recipe_does_not_get_product_truth_language() -> None:
    plan = ModeAwareRoleDirector().build(
        project_id="project_doc69_generic",
        job_id="job_doc69_generic",
        user_input="Create a dreamy abstract summer visual set",
        mode="creative_exploration",
        requested_image_count=2,
        subject_type="generic",
        scenario_id="general_creative",
        template_id="general_template",
        has_identity_anchor=False,
    )
    recipe = plan.role_recipes[0].model_dump(mode="json")
    helper_text = "\n".join(provider_casebook_prompt_lines(recipe))

    assert "Prompt atom camera stack:" in helper_text
    assert "Prompt atom product truth:" not in helper_text
    assert "label/logo" not in helper_text
    assert "one product truth" not in helper_text


def test_doc69_new_review_issue_codes_create_retry_patches() -> None:
    resolution = GeneratedOutputResolution(
        resolution_id="resolution_doc69_review",
        project_id="project_doc69_review",
        job_id="job_doc69_review",
        candidate_id="candidate_doc69_review",
        output_id="output_doc69_review",
        status="ready",
    )
    report = VisionOutputInspector().inspect(
        resolution,
        metadata={
            "post_generation_fake_issue_codes": [
                "over_retouching",
                "weak_lifestyle_context",
                "reference_guard_ignored",
            ],
            "post_generation_fake_confidence": 0.91,
        },
    )
    patch = report.retry_patch

    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert "over_retouching" in [issue["code"] for issue in report.detected_issues]
    assert "weak_lifestyle_context" in [issue["code"] for issue in report.detected_issues]
    assert "reference_guard_ignored" in [issue["code"] for issue in report.detected_issues]
    assert any("natural camera" in item for item in patch["prompt_additions"])
    assert any("real-use lifestyle" in item for item in patch["prompt_additions"])
    assert any("selected reference" in item for item in patch["identity_reinforcement"])
    assert any("product or object reference" in item for item in patch["product_reinforcement"])


def test_doc69_local_inspector_flags_lower_right_generated_mark(tmp_path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    clean = tmp_path / "clean.png"
    marked = tmp_path / "marked.png"
    Image.new("RGB", (512, 512), (236, 245, 248)).save(clean)

    image = Image.new("RGB", (512, 512), (236, 245, 248))
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 52)
    except OSError:
        font = ImageFont.load_default()
    draw.text((365, 430), "AI", fill=(150, 150, 150), font=font)
    draw.text((420, 430), "GEN", fill=(165, 165, 165), font=font)
    image.save(marked)

    clean_report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc69_clean",
            job_id="job_doc69_clean",
            output_id="output_doc69_clean",
            file_path=str(clean),
            status="ready",
            provider="openai_gpt_image",
            model="gpt-image-2",
        ),
        metadata={"vision_inspection_mode": "local_image_heuristic"},
    )
    marked_report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc69_marked",
            job_id="job_doc69_marked",
            output_id="output_doc69_marked",
            file_path=str(marked),
            status="ready",
            provider="openai_gpt_image",
            model="gpt-image-2",
        ),
        metadata={"vision_inspection_mode": "local_image_heuristic"},
    )

    assert clean_report.status == "pass"
    assert marked_report.status == "fail_retryable"
    issue_codes = [issue["code"] for issue in marked_report.detected_issues]
    assert "lower_right_mark_artifact" in issue_codes
    assert "ai_generated_badge_trace" in issue_codes
    assert any("lower-right" in item for item in marked_report.retry_patch["negative_additions"])


def test_doc83_local_inspector_does_not_retry_ambiguous_lower_right_texture(tmp_path) -> None:
    from PIL import Image, ImageDraw

    textured = tmp_path / "textured.png"
    image = Image.new("RGB", (512, 512), (236, 245, 248))
    draw = ImageDraw.Draw(image)
    for index in range(28):
        x = 370 + (index * 9) % 120
        y = 440 + (index * 17) % 50
        color = (210 - (index % 5) * 8, 190 + (index % 4) * 9, 180 + (index % 3) * 12)
        draw.ellipse((x, y, x + 26, y + 18), fill=color)
    image.save(textured)

    report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc83_texture",
            job_id="job_doc83_texture",
            output_id="output_doc83_texture",
            file_path=str(textured),
            status="ready",
            provider="openai_gpt_image",
            model="gpt-image-2",
        ),
        metadata={"vision_inspection_mode": "local_image_heuristic"},
    )

    issue_codes = [issue["code"] for issue in report.detected_issues]
    assert report.status == "pass"
    assert report.retryable is False
    assert "lower_right_mark_artifact" not in issue_codes
    assert "ai_generated_badge_trace" not in issue_codes


def test_doc104_local_inspector_does_not_retry_dense_architectural_corner_detail(tmp_path) -> None:
    from PIL import Image, ImageDraw
    from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_inspector import (
        _lower_right_mark_risk,
    )

    architectural = tmp_path / "architectural_corner.png"
    image = Image.new("RGB", (512, 512), (236, 245, 248))
    draw = ImageDraw.Draw(image)
    for index in range(11):
        draw.line((360, 430 + index * 7, 512, 430 + index * 7), fill=(150, 150, 150), width=3)
    for index in range(12):
        draw.line((365 + index * 13, 425, 365 + index * 13, 505), fill=(180, 180, 180), width=2)
    image.save(architectural)
    risk, evidence = _lower_right_mark_risk(architectural)

    report = VisionOutputInspector().inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc104_architecture",
            job_id="job_doc104_architecture",
            output_id="output_doc104_architecture",
            file_path=str(architectural),
            status="ready",
            provider="openai_gpt_image",
            model="gpt-image-2",
        ),
        metadata={"vision_inspection_mode": "local_image_heuristic"},
    )

    assert report.status == "pass"
    assert report.retryable is False
    assert risk is False
    assert evidence["lower_right_edge_ratio"] > 0.22
    assert evidence["lower_right_compact_edge_density"] is False
    assert "lower_right_mark_artifact" not in [issue["code"] for issue in report.detected_issues]
