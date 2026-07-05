from pathlib import Path

from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.service import VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
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
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    GeneratedOutputResolution,
    VisionOutputInspector,
)


def _cluster(metadata: dict | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc77",
            scenario_id="general_creative",
            user_input=(
                "Create a summer cool East Asian woman portrait set with clean daylight, "
                "real camera texture, and polished social-cover aesthetics."
            ),
            metadata={
                "requested_image_count": 4,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc77",
                    "template_id": "general_template",
                    "context_version": "doc77",
                },
                **(metadata or {}),
            },
        ),
        module_ids=["visual_capability_cluster"],
    )
    return result.results[-1].facts["visual_capability_cluster"]


def _request_from_cluster(cluster: dict) -> GenerationRequest:
    role_plan = cluster["role_specific_generation_plan"]
    recipe = role_plan["role_recipes"][0]
    asset = AssetSpec(
        asset_id="asset_doc77_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="summer portrait set",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc77_provider",
        asset_id=asset.asset_id,
        visual_prompt="summer cool East Asian portrait, real camera, clean bright aesthetic",
        negative_prompt="visible text, watermark, generic stock photo",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["real camera", "fresh daylight"],
        layout_notes=["portrait cover"],
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc77_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc77_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc77_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Create a summer cool East Asian portrait set",
            "visual_cluster": cluster,
            "role_specific_generation_plan": role_plan,
            "mode_execution_policy": role_plan["policy"],
            "mode_role_recipe": recipe,
        },
    )


def test_doc77_visual_inspector_retry_patch_for_aesthetic_issue_codes() -> None:
    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc77",
            project_id="project_doc77",
            job_id="job_doc77",
            candidate_id="candidate_doc77",
            output_id="output_doc77",
            status="ready",
        ),
        metadata={
            "post_generation_fake_issue_codes": [
                "weak_aesthetic_finish",
                "overprocessed_hdr_finish",
                "weak_subject_readability",
            ]
        },
    )

    patch_text = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["composition_repair"],
            *report.retry_patch["artifact_repair"],
        ]
    )

    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert "weak_aesthetic_finish" in [issue["code"] for issue in report.detected_issues]
    assert "foundation aesthetic finish" in patch_text
    assert "generic stock photo" in patch_text
    assert "overprocessed HDR" in patch_text


def test_doc77_local_image_heuristic_flags_objective_low_quality_file(tmp_path: Path) -> None:
    image_path = tmp_path / "tiny_washed_out.png"
    Image.new("RGB", (256, 256), (255, 255, 255)).save(image_path)

    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc77_local",
            project_id="project_doc77",
            job_id="job_doc77_local",
            candidate_id="candidate_doc77_local",
            output_id="output_doc77_local",
            file_path=str(image_path),
            width=256,
            height=256,
            provider="openai_gpt_image",
            model="gpt-image-2",
            status="ready",
        ),
        metadata={"vision_inspection_mode": "local_image_heuristic", "enable_local_aesthetic_heuristics": True},
    )

    issue_codes = [issue["code"] for issue in report.detected_issues]

    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert "low_resolution_output" in issue_codes
    assert "overexposed_washout" in issue_codes
    assert report.evidence["local_aesthetic_heuristic"] == "doc77_conservative_file_level"


def test_doc77_strict_policy_exposes_foundation_aesthetic_stability_rules() -> None:
    cluster = _cluster()
    strict_policy = cluster["strict_visual_review_policy"]
    role_keys = [recipe["role_key"] for recipe in cluster["role_specific_generation_plan"]["role_recipes"]]

    assert strict_policy["metadata"]["doc"] == "77"
    assert "weak_aesthetic_finish" in strict_policy["retryable_issue_codes"]
    assert "overprocessed_hdr_finish" in strict_policy["retryable_issue_codes"]
    assert any("Foundation aesthetic stability" in item for item in strict_policy["prompt_additions"])
    assert "generic stock photo finish" in strict_policy["negative_additions"]
    assert "aesthetic stability" in strict_policy["review_focus"]
    assert role_keys == [
        "cover_hero",
        "subject_focus",
        "side_or_three_quarter_angle",
        "wide_scene_or_context",
    ]


def test_doc77_provider_prompt_consumes_strict_aesthetic_rules() -> None:
    cluster = _cluster()
    request = _request_from_cluster(cluster)

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert "Strict visual review rules:" in final_prompt
    assert "Foundation aesthetic stability" in final_prompt
    assert "generic stock photo finish" in final_prompt
    assert "overprocessed HDR finish" in final_prompt


def test_doc77_product_api_retry_whitelist_includes_aesthetic_stability_codes() -> None:
    for code in [
        "weak_aesthetic_finish",
        "generic_stock_photo_finish",
        "flat_low_contrast_finish",
        "overexposed_washout",
        "underexposed_muddy_frame",
        "unbalanced_color_grade",
        "weak_subject_readability",
        "weak_depth_and_material_separation",
        "unstable_composition_balance",
        "overprocessed_hdr_finish",
        "uncanny_micro_detail",
        "low_resolution_output",
    ]:
        assert code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
