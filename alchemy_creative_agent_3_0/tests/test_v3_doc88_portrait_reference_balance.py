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


DOC88_CODES = [
    "prompt_mood_regression",
    "prompt_color_tone_regression",
    "approved_style_anchor_ignored",
    "identity_repair_damaged_prompt_direction",
    "overconstrained_identity_prompt",
    "scenario_specific_negative_overfit",
]


def _cluster(metadata: dict | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc88",
            scenario_id="general_creative",
            user_input=(
                "Use the uploaded woman as the same person, keep the accepted visual direction, "
                "and create a cool blue evening fountain portrait with quiet documentary mood."
            ),
            metadata={
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc88",
                    "template_id": "general_template",
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "uploaded_face_truth",
                            "asset_id": "uploaded_face_truth",
                            "file_path": "D:/AI/mock_uploaded_face.png",
                            "source_type": "uploaded",
                            "use_policy": "identity",
                        }
                    ],
                    "selected_output_assets": [
                        {
                            "output_id": "approved_output_1",
                            "asset_id": "approved_asset_1",
                            "candidate_id": "candidate_approved_1",
                            "source_type": "generated",
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
        asset_id="asset_doc88_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person portrait with balanced prompt mood and reference identity",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc88",
            asset_id=asset.asset_id,
            visual_prompt="cool blue evening fountain portrait, quiet documentary mood, warm city bokeh, 35mm side-front angle",
            negative_prompt="different person, copied source photo lighting",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["cool evening", "documentary portrait"],
            layout_notes=["portrait cover"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc88", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc88",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc88_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Use the uploaded woman as the same person while preserving the evening fountain mood.",
            "visual_cluster": cluster,
            "role_specific_generation_plan": cluster["role_specific_generation_plan"],
        },
    )


def test_doc88_creates_balance_policy_as_visual_cluster_child_module() -> None:
    cluster = _cluster()

    policy = cluster["portrait_reference_balance_policy"]
    role_plan = cluster["role_specific_generation_plan"]

    assert policy["applies"] is True
    assert policy["metadata"]["approved_visual_anchor_output_ids"] == ["approved_output_1"]
    assert "current request controls" in " ".join(policy["current_prompt_truth_rules"])
    assert "positive visual direction anchors" in " ".join(policy["approved_visual_anchor_rules"])
    assert role_plan["metadata"]["doc88_portrait_reference_balance_policy"] is True
    assert "portrait_reference_balance_policy" in cluster["child_module_ids"]


def test_doc88_provider_prompt_preserves_visual_direction_before_identity_repair() -> None:
    cluster = _cluster()
    prompt = ProductionImageGenerationProvider()._generation_prompt(_request_from_cluster(cluster), [])  # noqa: SLF001

    assert "Visual direction:" in prompt
    assert "Portrait identity contract:" in prompt
    assert "Doc88 balance contract:" in prompt
    assert "Doc88 prompt truth" in prompt
    assert "Selected generated outputs are positive visual direction anchors" in prompt
    assert prompt.index("Visual direction:") < prompt.index("Portrait identity contract:")
    assert prompt.index("Doc88 balance contract:") < prompt.index("Reference inheritance boundary:")
    assert "period/fantasy/editorial" not in prompt


def test_doc88_balance_issue_triggers_bounded_retry_patch() -> None:
    cluster = _cluster(
        {
            "generated_candidates": [
                {
                    "candidate_id": "candidate_doc88",
                    "output_id": "output_doc88",
                    "metadata": {
                        "portrait_balance_issue_codes": [
                            "identity_repair_damaged_prompt_direction",
                            "overconstrained_identity_prompt",
                        ]
                    },
                }
            ],
            "max_visual_retry_attempts": 1,
        }
    )

    review = cluster["portrait_reference_balance_review"]
    report = cluster["quality_review_reports"][0]
    retry = cluster["auto_retry_decisions"][0]
    patch_text = " ".join(
        [
            *retry["retry_patch"]["prompt_additions"],
            *retry["retry_patch"]["negative_additions"],
            *retry["retry_patch"]["identity_reinforcement"],
        ]
    )

    assert review["status"] == "fail_retryable"
    assert "identity_repair_damaged_prompt_direction" in review["issue_codes"]
    assert report["status"] == "fail"
    assert retry["should_retry"] is True
    assert retry["retry_patch"]["preserve_prompt_mood"] is True
    assert retry["retry_patch"]["shorten_overconstrained_identity_guidance"] is True
    assert "current prompt's requested mood" in patch_text
    assert "same person inside the current prompt's atmosphere" in patch_text


def test_doc88_inspector_and_product_api_retry_patch_include_balance_codes() -> None:
    for code in DOC88_CODES:
        assert code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES

    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc88",
            project_id="project_doc88",
            job_id="job_doc88",
            candidate_id="candidate_doc88",
            output_id="output_doc88",
            status="ready",
        ),
        metadata={"post_generation_fake_issue_codes": ["prompt_mood_regression", "scenario_specific_negative_overfit"]},
    )
    inspector_patch = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["identity_reinforcement"],
        ]
    )
    api_patch = V3ProductApiService()._visual_retry_patch_from_issues(["prompt_color_tone_regression"])  # noqa: SLF001
    api_patch_text = " ".join(
        [
            *api_patch["prompt_additions"],
            *api_patch["negative_additions"],
            *api_patch["identity_reinforcement"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "Doc88 balance repair" in inspector_patch
    assert "current prompt's requested mood" in api_patch_text
