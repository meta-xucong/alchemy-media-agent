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


DOC86_CODES = [
    "bone_structure_drift",
    "face_shape_drift",
    "cheek_jaw_chin_drift",
    "eye_shape_or_spacing_identity_drift",
    "eyebrow_eye_relationship_drift",
    "nose_mouth_relationship_identity_drift",
    "lip_contour_identity_drift",
    "age_impression_drift",
    "styling_changed_face_geometry",
    "archetype_overrode_reference_identity",
    "same_type_not_same_person",
    "identity_reference_underweighted",
]


def _cluster(metadata: dict | None = None) -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc86",
            scenario_id="general_creative",
            user_input=(
                "Create a period-style portrait of the same uploaded woman. "
                "Change makeup, wardrobe, lighting, and mood, but keep the same person."
            ),
            metadata={
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "delivery_suite",
                "template_id": "general_template",
                "project_context_snapshot": {
                    "project_id": "project_doc86",
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
        asset_id="asset_doc86_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person styled portrait",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc86",
            asset_id=asset.asset_id,
            visual_prompt="ancient styling, delicate editorial beauty, cinematic costume portrait",
            negative_prompt="different person, generic AI beauty",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["period styling", "cinematic"],
            layout_notes=["portrait cover"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc86", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc86",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc86_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Create a period-style portrait of the same uploaded woman",
            "visual_cluster": cluster,
            "role_specific_generation_plan": cluster["role_specific_generation_plan"],
        },
    )


def test_doc86_uploaded_portrait_reference_creates_bone_structure_lock() -> None:
    cluster = _cluster()

    lock = cluster["portrait_bone_structure_lock"]
    styling = cluster["styling_delta_policy"]
    role_plan = cluster["role_specific_generation_plan"]

    assert lock["applies"] is True
    assert lock["priority"] == "hard"
    assert "face width/length ratio" in lock["stable_bone_traits"]
    assert "eye spacing and base eye shape" in lock["stable_feature_relationships"]
    assert "makeup color and intensity" in lock["allowed_surface_changes"]
    assert "same beauty type but different person" in lock["forbidden_geometry_drift"]
    assert styling["applies"] is True
    assert styling["style_prompt_scope"] == "surface_only"
    assert role_plan["metadata"]["doc86_portrait_bone_structure_lock"] is True
    assert "portrait_bone_structure_identity_lock" in cluster["child_module_ids"]


def test_doc86_provider_prompt_places_identity_contract_before_visual_direction() -> None:
    cluster = _cluster()
    prompt = ProductionImageGenerationProvider()._generation_prompt(_request_from_cluster(cluster), [])  # noqa: SLF001

    assert "Portrait identity contract:" in prompt
    assert "Same person under changed styling" in prompt
    assert "Bone structure to preserve" in prompt
    assert "Visual direction:" in prompt
    assert prompt.index("Portrait identity contract:") < prompt.index("Visual direction:")
    assert "period, fantasy, editorial, or cinematic styling" in prompt


def test_doc86_same_type_not_same_person_triggers_retry_patch() -> None:
    cluster = _cluster(
        {
            "generated_candidates": [
                {
                    "candidate_id": "candidate_doc86",
                    "output_id": "output_doc86",
                    "metadata": {"portrait_identity_issue_codes": ["same_type_not_same_person"]},
                }
            ],
            "max_visual_retry_attempts": 1,
        }
    )

    review = cluster["portrait_identity_similarity_review"]
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
    assert "same_type_not_same_person" in review["issue_codes"]
    assert report["status"] == "fail"
    assert retry["should_retry"] is True
    assert "same_type_not_same_person" in retry["reason_codes"]
    assert "same person from the portrait reference" in patch_text
    assert "not merely the same beauty type" in patch_text


def test_doc86_vision_inspector_and_product_api_retry_patch_include_bone_codes() -> None:
    for code in DOC86_CODES:
        assert code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES

    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc86",
            project_id="project_doc86",
            job_id="job_doc86",
            candidate_id="candidate_doc86",
            output_id="output_doc86",
            status="ready",
        ),
        metadata={"post_generation_fake_issue_codes": ["same_type_not_same_person", "bone_structure_drift"]},
    )
    inspector_patch = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["identity_reinforcement"],
        ]
    )
    api_patch = V3ProductApiService()._visual_retry_patch_from_issues(["same_type_not_same_person"])  # noqa: SLF001
    api_patch_text = " ".join(
        [
            *api_patch["prompt_additions"],
            *api_patch["negative_additions"],
            *api_patch["identity_reinforcement"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "same person under changed styling" in inspector_patch
    assert "face-geometry truth source" in api_patch_text
