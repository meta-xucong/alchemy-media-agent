from alchemy_creative_agent_3_0.app.generation_router import GenerationRequest, ProductionImageGenerationProvider
from alchemy_creative_agent_3_0.app.product_api.service import (
    VISUAL_AUTO_RETRY_RETRYABLE_ISSUES,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.project_mode.contracts import CreateProjectJobRequest
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


DOC90_PERSON_CODES = [
    "beauty_archetype_overrode_reference",
    "same_type_but_different_person",
    "prompt_face_description_replaced_reference_geometry",
    "generic_sweet_model_replaced_reference",
]

DOC90_PRODUCT_CODES = [
    "product_silhouette_drift",
    "label_or_pattern_drift",
    "material_structure_drift",
    "generic_product_replacement",
]

DOC90_SCENE_CODES = [
    "scene_identity_drift",
    "background_space_drift",
    "camera_mood_drift",
    "reference_scene_replaced",
]


def _cluster(metadata: dict | None = None, *, template_id: str = "general_template") -> dict:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_doc90",
            scenario_id="general_creative",
            user_input=(
                "Use the uploaded woman as the same person, but create an elegant sweet East Asian "
                "portrait with a new scene, new styling, and a soft commercial finish."
            ),
            metadata={
                "requested_image_count": 1,
                "requested_image_size": "1024x1536",
                "effective_variation_mode": "selection_candidates",
                "template_id": template_id,
                "project_context_snapshot": {
                    "project_id": "project_doc90",
                    "template_id": template_id,
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
        asset_id="asset_doc90_provider",
        asset_type=AssetType.SOCIAL_COVER,
        platform=Platform.GENERIC_SOCIAL,
        aspect_ratio="3:4",
        purpose="same-person portrait with advanced reference priority controls",
    )
    return GenerationRequest(
        asset_spec=asset,
        prompt_compilation=PromptCompilationResult(
            prompt_compilation_id="prompt_doc90",
            asset_id=asset.asset_id,
            visual_prompt="sweet East Asian portrait, oval-face beauty wording, new garden scene, soft commercial light",
            negative_prompt="different person, generic AI beauty",
            text_policy="do_not_render_final_text_in_image_model",
            style_notes=["sweet but real", "commercial portrait"],
            layout_notes=["portrait cover"],
        ),
        condition_plan=ConditionPlan(condition_plan_id="condition_doc90", asset_id=asset.asset_id),
        generation_plan=GenerationPlan(
            generation_plan_id="generation_doc90",
            asset_id=asset.asset_id,
            provider_strategy=ProviderStrategy.REFERENCE_CONDITIONED_PROVIDER,
            candidate_count=1,
            max_refine_rounds=0,
        ),
        metadata={
            "job_id": "job_doc90_provider",
            "template_id": "general_template",
            "scenario_id": "general_creative",
            "user_input": "Use the uploaded woman as the same person, not a generic sweet model.",
            "visual_cluster": cluster,
            "role_specific_generation_plan": cluster["role_specific_generation_plan"],
        },
    )


def test_doc90_contract_ignores_unknown_advanced_control_keys() -> None:
    request = CreateProjectJobRequest.model_validate(
        {
            "user_input": "continue the general portrait project",
            "advanced_reference_controls": {
                "preserve_person_identity": True,
                "preserve_product_appearance": False,
                "unsupported_weight": True,
            },
        }
    )

    assert request.advanced_reference_controls == {
        "preserve_person_identity": True,
        "preserve_product_appearance": False,
    }


def test_doc90_general_template_defaults_person_reference_priority_on() -> None:
    cluster = _cluster()
    controls = cluster["metadata"]["advanced_reference_controls"]
    role_plan = cluster["role_specific_generation_plan"]
    review_policy = cluster["strict_visual_review_policy"]

    assert controls["preserve_person_identity"] is True
    assert controls["applies"] is True
    assert controls["source"] == "generic_reference_defaults"
    assert "advanced_reference_priority_controls" in cluster["child_module_ids"]
    assert role_plan["metadata"]["doc90_advanced_reference_controls"] is True
    assert "Doc90 person priority" in " ".join(role_plan["prompt_additions"])
    for code in DOC90_PERSON_CODES:
        assert code in review_policy["retryable_issue_codes"]


def test_doc90_provider_prompt_keeps_reference_identity_above_prompt_face_archetypes() -> None:
    cluster = _cluster()
    prompt = ProductionImageGenerationProvider()._generation_prompt(_request_from_cluster(cluster), [])  # noqa: SLF001

    assert "Doc90 person priority" in prompt
    assert "prompt face-archetype words" in prompt
    assert "must not replace the reference person's facial geometry" in prompt
    assert "same-person impression" in prompt
    assert prompt.index("Visual direction:") < prompt.index("Doc90 person priority")
    assert "Use the uploaded woman as the same person" in prompt
    assert len(prompt) <= ProductionImageGenerationProvider.provider_prompt_target_chars


def test_doc90_explicit_person_priority_off_disables_child_module() -> None:
    cluster = _cluster({"advanced_reference_controls": {"preserve_person_identity": False}})
    controls = cluster["metadata"]["advanced_reference_controls"]

    assert controls["preserve_person_identity"] is False
    assert controls["applies"] is False
    assert controls["source"] == "manual"
    assert "advanced_reference_priority_controls" not in cluster["child_module_ids"]


def test_doc90_product_and_scene_controls_are_generic_general_template_helpers() -> None:
    cluster = _cluster(
        {
            "advanced_reference_controls": {
                "preserve_person_identity": False,
                "preserve_product_appearance": True,
                "preserve_scene_consistency": True,
            }
        }
    )
    controls = cluster["metadata"]["advanced_reference_controls"]
    role_plan_text = " ".join(cluster["role_specific_generation_plan"]["prompt_additions"])
    review_codes = cluster["strict_visual_review_policy"]["retryable_issue_codes"]

    assert controls["template_scope"] == "general_template"
    assert controls["preserve_product_appearance"] is True
    assert controls["preserve_scene_consistency"] is True
    assert "Doc90 product priority" in role_plan_text
    assert "Doc90 scene priority" in role_plan_text
    assert "ecommerce" not in role_plan_text.lower()
    for code in [*DOC90_PRODUCT_CODES, *DOC90_SCENE_CODES]:
        assert code in review_codes


def test_doc90_ecommerce_template_accepts_product_reference_priority_controls() -> None:
    cluster = _cluster(
        {
            "advanced_reference_controls": {
                "preserve_person_identity": False,
                "preserve_product_appearance": True,
                "preserve_scene_consistency": False,
            }
        },
        template_id="ecommerce_template",
    )
    controls = cluster["metadata"]["advanced_reference_controls"]
    role_plan_text = " ".join(cluster["role_specific_generation_plan"]["prompt_additions"])

    assert controls["template_scope"] == "ecommerce_template"
    assert controls["preserve_product_appearance"] is True
    assert controls["applies"] is True
    assert "Doc90 product priority" in role_plan_text
    for code in DOC90_PRODUCT_CODES:
        assert code in cluster["strict_visual_review_policy"]["retryable_issue_codes"]


def test_doc90_retry_issue_codes_flow_through_inspector_and_product_api_patch() -> None:
    for code in [*DOC90_PERSON_CODES, *DOC90_PRODUCT_CODES, *DOC90_SCENE_CODES]:
        assert code in VISUAL_AUTO_RETRY_RETRYABLE_ISSUES

    report = VisionOutputInspector(vision_provider=None).inspect(
        GeneratedOutputResolution(
            resolution_id="resolution_doc90",
            project_id="project_doc90",
            job_id="job_doc90",
            candidate_id="candidate_doc90",
            output_id="output_doc90",
            status="ready",
        ),
        metadata={
            "post_generation_fake_issue_codes": [
                "beauty_archetype_overrode_reference",
                "generic_product_replacement",
                "reference_scene_replaced",
            ]
        },
    )
    inspector_patch = " ".join(
        [
            *report.retry_patch["prompt_additions"],
            *report.retry_patch["negative_additions"],
            *report.retry_patch["identity_reinforcement"],
            *report.retry_patch["product_reinforcement"],
            *report.retry_patch["composition_repair"],
        ]
    )
    api_patch = V3ProductApiService()._visual_retry_patch_from_issues(  # noqa: SLF001
        [
            "same_type_but_different_person",
            "product_silhouette_drift",
            "scene_identity_drift",
        ]
    )
    api_patch_text = " ".join(
        [
            *api_patch["prompt_additions"],
            *api_patch["negative_additions"],
            *api_patch["identity_reinforcement"],
            *api_patch["product_reinforcement"],
            *api_patch["composition_repair"],
        ]
    )

    assert report.status == "fail_retryable"
    assert "Doc90 advanced reference priority repair" in inspector_patch
    assert "prompt face archetype" in api_patch_text
    assert "uploaded object's silhouette" in api_patch_text
    assert "scene continuity" in api_patch_text
