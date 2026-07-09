from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.service import (
    VISUAL_AUTO_RETRY_RETRYABLE_ISSUES,
    V3ProductApiService,
)
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


DOC87_CODES = [
    "source_lighting_overinherited",
    "source_color_temperature_overinherited",
    "source_scene_overinherited",
    "source_wardrobe_overinherited",
    "source_camera_mood_overinherited",
    "reference_used_as_style_when_identity_only",
    "prompt_style_underweighted",
    "makeup_changed_face_geometry",
    "hair_change_replaced_identity",
    "retry_repaired_artifact_but_changed_identity",
]


def _cluster(metadata: dict | None = None, *, user_input: str | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc87",
            scenario_id="general_creative",
            user_input=user_input
            or (
                "Use the uploaded woman as the same person, but create a cool blue-gray evening "
                "cinematic fountain portrait with warm city lights and a new side-front camera angle."
            ),
            metadata={
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc87",
                    "template_id": "general_template",
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "uploaded_face_truth",
                            "asset_id": "uploaded_face_truth",
                            "file_path": "D:/AI/mock_uploaded_face_warm_beach.png",
                            "source_type": "uploaded",
                            "use_policy": "identity",
                        }
                    ],
                },
                **(metadata or {}),
            },
        ),
        module_ids=["visual_capability_cluster"],
    )
    assert result.results
    return result.results[-1].facts["visual_capability_cluster"]


def _request_from_cluster(cluster: dict) -> GenerationRequest:
    asset = AssetSpec(
        asset_id="asset_doc87_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person portrait with prompt-owned style direction",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc87",
            asset_id=asset.asset_id,
            visual_prompt="cool blue-gray evening fountain portrait, warm city bokeh, documentary 35mm side-front angle",
            negative_prompt="different person, copied source beach lighting",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["evening city", "cinematic documentary"],
            layout_notes=["portrait cover"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc87", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc87",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc87_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Use the uploaded woman as the same person but follow the new evening fountain prompt.",
            "visual_cluster": cluster,
            "role_specific_generation_plan": cluster["role_specific_generation_plan"],
        },
    )


def test_doc87_uploaded_portrait_reference_is_identity_truth_not_style_truth() -> None:
    cluster = _cluster()

    policy = cluster["portrait_reference_influence_policy"]
    role_plan = cluster["role_specific_generation_plan"]

    assert policy["applies"] is True
    assert policy["identity_truth_strength"] == "hard"
    assert policy["lighting_color_scene_strength"] == "prompt_owned"
    assert "source lighting" in policy["blocked_reference_channels"]
    assert "lighting" in policy["prompt_owned_channels"]
    assert role_plan["metadata"]["doc87_portrait_reference_identity_style_separation"] is True
    assert "portrait_reference_identity_style_separator" in cluster["child_module_ids"]


def test_doc87_provider_prompt_blocks_source_style_before_visual_direction() -> None:
    cluster = _cluster()
    prompt = ProductionImageGenerationProvider()._generation_prompt(_request_from_cluster(cluster), [])  # noqa: SLF001

    assert "Reference inheritance boundary:" in prompt
    assert "Identity comes from the reference; direction comes from the prompt." in prompt
    assert "Do not copy the reference image's original lighting" in prompt
    assert "source lighting" in prompt
    assert "original facial outline width" in prompt
    assert "temple-cheek-jaw contour" in prompt
    assert "eye size family" in prompt
    assert "mouth scale" in prompt
    assert "same archetype is not enough" in prompt
    assert "narrow-faced" in prompt or "narrower" in prompt
    assert "Visual direction:" in prompt
    assert prompt.index("Reference inheritance boundary:") < prompt.index("Visual direction:")


def test_doc87_source_lighting_overinheritance_triggers_style_boundary_retry() -> None:
    cluster = _cluster(
        {
            "generated_candidates": [
                {
                    "candidate_id": "candidate_doc87",
                    "output_id": "output_doc87",
                    "metadata": {"portrait_style_boundary_issue_codes": ["source_lighting_overinherited"]},
                }
            ],
            "max_visual_retry_attempts": 1,
        }
    )

    review = cluster["portrait_identity_style_separation_review"]
    retry = cluster["auto_retry_decisions"][0]
    patch_text = " ".join(
        [
            *retry["retry_patch"]["prompt_additions"],
            *retry["retry_patch"]["negative_additions"],
            *retry["retry_patch"]["identity_reinforcement"],
        ]
    )

    assert review["status"] == "fail_retryable"
    assert "source_lighting_overinherited" in review["issue_codes"]
    assert retry["should_retry"] is True
    assert "source_lighting_overinherited" in retry["reason_codes"]
    assert "preserve the same person's face geometry" in patch_text
    assert "do not copy source lighting" in patch_text


def test_doc87_inspector_and_product_api_include_reference_boundary_codes() -> None:
    for code in DOC87_CODES:
        assert code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES

    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc87",
            project_id="project_doc87",
            job_id="job_doc87",
            candidate_id="candidate_doc87",
            output_id="output_doc87",
            status="ready",
        ),
        metadata={"post_generation_fake_issue_codes": ["source_scene_overinherited", "retry_repaired_artifact_but_changed_identity"]},
    )
    inspector_patch = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["identity_reinforcement"],
        ]
    )
    api_patch = V3ProductApiService()._visual_retry_patch_from_issues(["source_scene_overinherited"])  # noqa: SLF001
    api_patch_text = " ".join(
        [
            *api_patch["prompt_additions"],
            *api_patch["negative_additions"],
            *api_patch["identity_reinforcement"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "source scene" in inspector_patch
    assert "preserve the same person's face geometry" in inspector_patch
    assert "do not copy source lighting" in api_patch_text
