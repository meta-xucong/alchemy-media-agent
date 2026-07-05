from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def test_human_photorealism_layer_enables_for_real_portrait_request() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_portrait",
        job_id="job_portrait",
        scenario_id="general_creative",
        template_id="general_creative",
        user_input="Create an East Asian summer beauty portrait photo with a cool clean editorial mood",
        subject_type="character",
        variation_mode="selection_candidates",
        has_identity_reference=True,
    )

    assert guidance.applies is True
    assert guidance.realism_level == "commercial_photoreal"
    assert any("natural human skin texture" in item for item in guidance.positive_prompt_fragments)
    assert "plastic skin" in guidance.negative_prompt_fragments
    assert any("do not inherit over-smoothed skin" in item for item in guidance.reference_do_not_inherit_rules)


def test_human_photorealism_layer_does_not_override_stylized_requests() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_anime",
        job_id="job_anime",
        scenario_id="general_creative",
        template_id="general_creative",
        user_input="Create an anime manga portrait illustration of a fantasy girl",
        subject_type="character",
        variation_mode="creative_explore",
        has_identity_reference=False,
    )

    assert guidance.applies is False
    assert guidance.metadata["disabled_reason"] == "stylized_request"


def test_visual_cluster_exports_human_photorealism_and_commercial_quality_review() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        CapabilityInput(
            job_id="job_human_cluster",
            scenario_id="general_creative",
            user_input="Create three same-model East Asian summer portrait alternatives with natural pose changes",
            metadata={
                "template_id": "general_creative",
                "requested_image_count": 3,
                "variation_mode": "selection_candidates",
                "project_context_snapshot": {
                    "project_id": "project_human_cluster",
                    "template_id": "general_creative",
                    "selected_output_assets": [
                        {
                            "output_id": "selected_model_frame",
                            "asset_id": "selected_model_frame",
                            "file_path": "C:/tmp/selected_model_frame.png",
                        }
                    ],
                },
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]

    assert cluster["human_photorealism_guidance"]["applies"] is True
    assert cluster["anti_ai_face_review"]["status"] == "planned"
    assert cluster["visual_commercial_quality_review"]["human_realism_status"] == "planned"
    assert "human_photorealism_layer" in cluster["child_module_ids"]
    assert any(
        "natural human skin texture" in item
        for item in cluster["role_specific_generation_plan"]["prompt_additions"]
    )
    assert any(
        "do not inherit over-smoothed skin" in item
        for item in cluster["strong_reference_continuation_plan"]["negative_additions"]
    )


def test_visual_cluster_ai_face_issue_feeds_retry_decision() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        CapabilityInput(
            job_id="job_ai_face_retry",
            scenario_id="general_creative",
            user_input="Create a realistic commercial portrait photo of an East Asian woman",
            metadata={
                "template_id": "general_creative",
                "force_anti_ai_face_issue_codes": ["plastic_skin", "template_smile"],
                "project_context_snapshot": {"project_id": "project_ai_face_retry", "template_id": "general_creative"},
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]
    decision = cluster["auto_retry_decisions"][0]
    patch_text = " ".join(
        [
            *decision["retry_patch"]["prompt_additions"],
            *decision["retry_patch"]["negative_additions"],
        ]
    )

    assert cluster["anti_ai_face_review"]["status"] == "retry_recommended"
    assert "plastic_skin" in decision["reason_codes"]
    assert decision["should_retry"] is True
    assert "natural human skin texture" in patch_text
    assert "plastic skin" in patch_text
