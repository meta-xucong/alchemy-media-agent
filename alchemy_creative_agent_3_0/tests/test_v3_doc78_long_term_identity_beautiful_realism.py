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


DOC78_ISSUE_CODES = [
    "identity_card_missing",
    "identity_card_not_applied",
    "identity_feature_drift",
    "eyebrow_shape_drift",
    "eye_shape_or_spacing_drift",
    "nose_mouth_relationship_drift",
    "jaw_chin_direction_drift",
    "unflattering_feature_degradation",
    "beautiful_realism_balance_failure",
    "realism_made_subject_less_attractive",
    "pretty_but_too_ai_filtered",
    "real_but_unflattering",
    "skin_texture_beauty_balance_failure",
]


def _cluster(metadata: dict | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc78",
            scenario_id="general_creative",
            user_input=(
                "Create a summer cool East Asian woman portrait suite with the same person, "
                "fresh clean beauty, real camera texture, and different poses and angles."
            ),
            metadata={
                "requested_image_count": 4,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc78",
                    "template_id": "general_template",
                    "context_version": "doc78",
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
        asset_id="asset_doc78_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person summer portrait suite",
    )
    prompt = PromptCompilationResult(
        prompt_compilation_id="prompt_doc78_provider",
        asset_id=asset.asset_id,
        visual_prompt="summer cool East Asian woman portrait, real camera, fresh beautiful realism",
        negative_prompt="visible text, watermark, ugly realism",
        text_policy="do_not_render_final_text_in_image_model",
        style_notes=["real camera", "fresh clean beauty"],
        layout_notes=["portrait cover"],
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=prompt,
        condition_plan=ConditionPlan(condition_plan_id="condition_doc78_provider", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc78_provider",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.DEFAULT_IMAGE_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc78_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Create a summer cool East Asian woman portrait suite",
            "visual_cluster": cluster,
            "role_specific_generation_plan": role_plan,
            "mode_execution_policy": role_plan["policy"],
            "mode_role_recipe": recipe,
        },
    )


def test_doc78_selected_output_becomes_subject_identity_card_truth_source() -> None:
    cluster = _cluster(
        {
            "project_context_snapshot": {
                "project_id": "project_doc78_selected",
                "template_id": "general_template",
                "selected_output_assets": [
                    {
                        "output_id": "selected_identity_output",
                        "candidate_id": "selected_identity_candidate",
                        "asset_id": "selected_identity_asset",
                        "file_path": "D:/AI/mock_selected_identity.png",
                    }
                ],
            }
        }
    )

    card = cluster["subject_identity_card"]
    role_plan = cluster["role_specific_generation_plan"]

    assert card["applies"] is True
    assert card["source_priority"] == "user_selected_output"
    assert card["status"] == "user_selected_identity_ready"
    assert "selected_identity_output" in card["source_output_ids"]
    assert "selected_identity_asset" in card["source_asset_ids"]
    assert any("eyebrow" in rule for rule in card["facial_feature_integrity_rules"])
    assert any("beauty is the visual goal" in rule for rule in card["beautiful_realism_rules"])
    assert role_plan["metadata"]["doc78_subject_identity_card"] is True
    assert "subject_identity_card" in cluster["child_module_ids"]
    assert "beautiful_realism_balance_review" in cluster["child_module_ids"]


def test_doc78_strong_reference_binding_becomes_subject_identity_card_truth_source() -> None:
    cluster = _cluster(
        {
            "project_context_snapshot": {
                "project_id": "project_doc78_binding",
                "template_id": "general_template",
                "selected_reference_assets": [
                    {
                        "asset_ref_id": "reference_identity_asset",
                        "asset_id": "reference_identity_asset",
                        "output_id": "reference_identity_output",
                        "file_path": "D:/AI/mock_reference_identity.png",
                        "use_policy": "identity",
                    }
                ],
            }
        }
    )

    card = cluster["subject_identity_card"]

    assert card["applies"] is True
    assert card["source_priority"] == "strong_reference_binding"
    assert card["status"] == "strong_reference_identity_ready"
    assert "reference_identity_asset" in card["source_asset_ids"]
    assert "reference_identity_output" in card["source_output_ids"]


def test_doc78_text_only_suite_falls_back_to_first_identity_anchor_plan() -> None:
    cluster = _cluster()
    card = cluster["subject_identity_card"]

    assert card["applies"] is True
    assert card["source_priority"] == "planned_first_output_anchor"
    assert card["status"] == "planned_from_identity_hero"
    assert cluster["identity_hero_selection_plan"]["status"] == "planned_first_output_anchor"


def test_doc78_provider_prompt_consumes_subject_card_and_beautiful_realism_rules() -> None:
    cluster = _cluster()
    request = _request_from_cluster(cluster)

    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert "Subject identity card:" in final_prompt
    assert "Beautiful realism balance:" in final_prompt
    assert "Allowed identity-safe variation:" in final_prompt
    assert "eyebrow" in final_prompt
    assert "beauty is the visual goal" in final_prompt


def test_doc84_structured_appearance_rules_enter_subject_card_and_provider_prompt() -> None:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc84",
            scenario_id="general_creative",
            user_input=(
                "Create a same-person portrait suite with one layered translucent ceremonial outfit, "
                "embroidered pattern family, sash structure, sleeve shape, collar direction, and trim placement. "
                "Keep the same appearance asset while changing pose and camera angle."
            ),
            metadata={
                "requested_image_count": 4,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc84",
                    "template_id": "general_template",
                    "selected_reference_assets": [
                        {
                            "asset_ref_id": "appearance_anchor_asset",
                            "asset_id": "appearance_anchor_asset",
                            "output_id": "appearance_anchor_output",
                            "file_path": "D:/AI/mock_appearance_identity.png",
                            "use_policy": "identity",
                        }
                    ],
                },
            },
        ),
        module_ids=["visual_capability_cluster"],
    )
    cluster = result.results[-1].facts["visual_capability_cluster"]
    card = cluster["subject_identity_card"]

    assert card["metadata"]["doc84_structured_appearance_lock"] is True
    assert any("pattern family" in rule for rule in card["appearance_structure_rules"])
    assert any("trim placement" in rule for rule in card["appearance_structure_rules"])

    request = _request_from_cluster(cluster)
    request.metadata["user_input"] = (
        "Create a same-person portrait suite with one layered translucent ceremonial outfit and keep the same appearance asset."
    )
    final_prompt = ProductionImageGenerationProvider()._generation_prompt(request, [])  # noqa: SLF001

    assert "Structured appearance lock:" in final_prompt
    assert "pattern family" in final_prompt
    assert "trim placement" in final_prompt


def test_doc78_beautiful_realism_issues_create_quality_report_and_retry_decision() -> None:
    cluster = _cluster(
        {
            "generated_candidates": [
                {
                    "candidate_id": "candidate_doc78_review",
                    "output_id": "output_doc78_review",
                    "metadata": {
                        "beautiful_realism_issue_codes": [
                            "realism_made_subject_less_attractive",
                            "eyebrow_shape_drift",
                        ]
                    },
                }
            ],
            "max_visual_retry_attempts": 1,
        }
    )

    report = cluster["quality_review_reports"][0]
    retry = cluster["auto_retry_decisions"][0]
    patch_text = " ".join(
        [
            *retry["retry_patch"]["prompt_additions"],
            *retry["retry_patch"]["negative_additions"],
            *retry["retry_patch"]["identity_reinforcement"],
        ]
    )

    assert report["status"] == "retry_recommended"
    assert "realism_made_subject_less_attractive" in [issue["code"] for issue in report["detected_issues"]]
    assert "eyebrow_shape_drift" in [issue["code"] for issue in report["detected_issues"]]
    assert retry["should_retry"] is True
    assert "realism_made_subject_less_attractive" in retry["reason_codes"]
    assert "eyebrow" in patch_text
    assert "less attractive" in patch_text


def test_doc78_visual_inspector_retry_patch_for_beautiful_realism_issue_codes() -> None:
    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc78",
            project_id="project_doc78",
            job_id="job_doc78",
            candidate_id="candidate_doc78",
            output_id="output_doc78",
            status="ready",
        ),
        metadata={
            "post_generation_fake_issue_codes": [
                "realism_made_subject_less_attractive",
                "pretty_but_too_ai_filtered",
            ]
        },
    )

    patch_text = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["artifact_repair"],
            *report.retry_patch["identity_reinforcement"],
        ]
    )

    assert report.status == "fail_retryable"
    assert report.retryable is True
    assert "realism_made_subject_less_attractive" in [issue["code"] for issue in report.detected_issues]
    assert "beautiful realism" in patch_text
    assert "eyebrow" in patch_text
    assert "poreless AI filter" in patch_text


def test_doc78_product_api_retry_whitelist_includes_identity_and_beautiful_realism_codes() -> None:
    for code in DOC78_ISSUE_CODES:
        assert code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES
