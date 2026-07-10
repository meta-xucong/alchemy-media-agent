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
from alchemy_creative_agent_3_0.app.shared_capabilities import (
    CapabilityInput,
    SharedCapabilityRegistry,
)


def _cluster(metadata: dict | None = None, *, user_input: str | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc75",
            scenario_id="general_creative",
            user_input=user_input
            or (
                "Create a summer cool East Asian woman portrait suite for a social cover campaign. "
                "Keep the same young woman direction with seaside daylight and green-highlighted dark hair."
            ),
            metadata={
                "requested_image_count": 4,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc75",
                    "template_id": "general_template",
                    "context_version": "doc75",
                },
                **(metadata or {}),
            },
        ),
        module_ids=["visual_capability_cluster"],
    )
    assert result.results
    return result.results[-1].facts["visual_capability_cluster"]


def _request_from_cluster(cluster: dict) -> GenerationRequest:
    role_plan = cluster["role_specific_generation_plan"]
    recipe = role_plan["role_recipes"][0]
    asset = AssetSpec(
        asset_id="asset_doc75_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person summer portrait suite",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc75_provider",
        asset_id=asset.asset_id,
        visual_prompt="summer cool East Asian beauty portrait at the seaside, real commercial photo",
        negative_prompt="visible text, watermark",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["fresh summer", "real camera"],
        layout_notes=["portrait cover"],
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc75_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc75_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc75_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Create a summer cool East Asian woman portrait suite",
            "visual_cluster": cluster,
            "role_specific_generation_plan": role_plan,
            "mode_execution_policy": role_plan["policy"],
            "mode_role_recipe": recipe,
        },
    )


def test_doc75_visual_cluster_exposes_identity_hero_and_strict_policy() -> None:
    cluster = _cluster()

    identity_plan = cluster["identity_hero_selection_plan"]
    strict_policy = cluster["strict_visual_review_policy"]
    role_plan = cluster["role_specific_generation_plan"]
    primary_recipe = role_plan["role_recipes"][0]
    role_keys = [recipe["role_key"] for recipe in role_plan["role_recipes"]]

    assert identity_plan["applies"] is True
    assert identity_plan["status"] == "planned_first_output_anchor"
    assert identity_plan["strategy"] == "first_output_identity_master_then_expand"
    assert identity_plan["primary_role_key"] == "cover_hero"
    assert primary_recipe["metadata"]["identity_hero_candidate"] is True
    assert role_plan["metadata"]["doc75_identity_hero_selection"] is True

    assert strict_policy["applies"] is True
    assert strict_policy["strictness"] == "commercial_strict"
    assert "generic_ai_beauty_identity" in strict_policy["retryable_issue_codes"]
    assert "poreless glass-like skin" in strict_policy["negative_additions"]
    assert "3D render" in strict_policy["negative_additions"]
    assert role_plan["metadata"]["doc75_strict_visual_review"] is True
    assert role_keys == [
        "cover_hero",
        "subject_focus",
        "side_or_three_quarter_angle",
        "wide_scene_or_context",
    ]
    assert "identity_hero_selector" in cluster["child_module_ids"]
    assert "strict_visual_review_policy" in cluster["child_module_ids"]


def test_doc75_user_selected_reference_wins_identity_hero_selection() -> None:
    cluster = _cluster(
        {
            "project_context_snapshot": {
                "project_id": "project_doc75_selected",
                "template_id": "general_template",
                "selected_output_assets": [
                    {
                        "output_id": "selected_identity_output",
                        "candidate_id": "selected_identity_candidate",
                        "file_path": "D:/AI/mock_selected_identity.png",
                    }
                ],
            }
        }
    )

    identity_plan = cluster["identity_hero_selection_plan"]

    assert identity_plan["status"] == "user_anchor_ready"
    assert identity_plan["strategy"] == "use_user_selected_identity_master"
    assert identity_plan["selected_output_id"] == "selected_identity_output"
    assert identity_plan["selected_candidate_id"] == "selected_identity_candidate"
    assert identity_plan["provider_reference_expected"] is False


def test_doc75_strict_issue_codes_create_auto_retry_decision() -> None:
    cluster = _cluster(
        {
            "generated_candidates": [
                {
                    "candidate_id": "candidate_doc75_review",
                    "output_id": "output_doc75_review",
                    "metadata": {
                        "mode_role_recipe": {"role_key": "cover_hero"},
                        "strict_visual_review_issue_codes": ["generic_ai_beauty_identity"],
                    },
                }
            ],
            "max_visual_retry_attempts": 1,
        }
    )

    reports = cluster["quality_review_reports"]
    retry = cluster["auto_retry_decisions"][0]

    assert reports[0]["status"] == "fail"
    assert "generic_ai_beauty_identity" in [issue["code"] for issue in reports[0]["detected_issues"]]
    assert retry["should_retry"] is True
    assert "generic_ai_beauty_identity" in retry["reason_codes"]
    assert "generic AI beauty identity" in " ".join(retry["retry_patch"]["negative_additions"])


def test_doc75_provider_prompt_consumes_identity_hero_and_strict_review_rules() -> None:
    cluster = _cluster()
    request = _request_from_cluster(cluster)

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert "Suite director rules:" in final_prompt
    assert "Identity hero selection:" in final_prompt
    assert "Strict visual pass conditions:" in final_prompt
    assert "identity master" in final_prompt
    assert "generic AI beauty" in final_prompt
    assert "poreless glass-like skin" in final_prompt
    assert "3D render" in final_prompt


def test_doc75_product_api_retry_whitelist_includes_strict_human_and_suite_codes() -> None:
    assert "generic_ai_beauty_identity" in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
    assert "same_expression_repetition" in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
    assert "same_head_angle_repetition" in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
    assert "role_collapse" in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
    assert "head_body_proportion_distortion" in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
    assert "lower_right_mark_artifact" in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
