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


def test_doc91_ecommerce_kidswear_model_activates_human_realism_for_product_subject() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc91_kidswear",
        job_id="job_doc91_kidswear",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        user_input="Create an ecommerce kidswear catalog photo, child model wearing the outfit, avoid doll-like face",
        subject_type="product",
        variation_mode="delivery_suite",
        has_identity_reference=False,
        metadata={
            "product_profile": {"category": "kidswear clothing", "audience": "children"},
            "template_policy": {"identity_lock_default": "product"},
        },
    )

    plugin = guidance.metadata["human_realism_plugin"]

    assert guidance.applies is True
    assert plugin["applies"] is True
    assert plugin["subject_type"] == "product"
    assert plugin["human_subject_kind"] == "child_or_teen_model"
    assert plugin["strictness"] == "child_strict"
    assert plugin["disabled_by_style"] is False
    assert "ecommerce_human_model_detected" in plugin["reason_codes"]
    assert "doll-like child face" in guidance.negative_prompt_fragments


def test_doc91_visual_cluster_exports_plugin_metadata_for_product_on_model() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        CapabilityInput(
            job_id="job_doc91_cluster",
            scenario_id="ecommerce",
            user_input="Generate a kidswear product image with a real child model wearing the jacket",
            product_profile={"category": "kidswear apparel", "product_name": "summer jacket"},
            metadata={
                "template_id": "ecommerce_template",
                "requested_image_count": 2,
                "project_context_snapshot": {"project_id": "project_doc91_cluster", "template_id": "ecommerce_template"},
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    cluster = result.results[-1].facts["visual_capability_cluster"]

    assert cluster["human_photorealism_guidance"]["applies"] is True
    plugin = cluster["metadata"]["human_realism_plugin"]

    assert plugin["applies"] is True
    assert plugin["subject_type"] == "product"
    assert plugin["human_subject_kind"] == "child_or_teen_model"
    assert "human_photorealism_layer" in cluster["child_module_ids"]
    assert "anti_ai_face_review" in cluster["child_module_ids"]


def test_doc91_product_only_request_does_not_force_human_realism() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc91_product_only",
        job_id="job_doc91_product_only",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        user_input="Create a clean white-background product photo of a ceramic mug",
        subject_type="product",
        variation_mode="delivery_suite",
        has_identity_reference=False,
        metadata={"product_profile": {"category": "ceramic mug"}},
    )

    assert guidance.applies is False
    assert guidance.metadata["human_realism_plugin"]["applies"] is False
    assert guidance.metadata["disabled_reason"] == "no_human_signal"


def test_doc91_child_face_retry_patch_is_owned_by_human_realism_plugin() -> None:
    layer = HumanPhotorealismLayer()

    patch = layer.retry_patch_for_issue_codes(["doll_like_child_face"], child_model=True)
    patch_text = " ".join(
        [
            *patch["prompt_additions"],
            *patch["negative_additions"],
            *patch["artifact_repair"],
        ]
    )

    assert "real child or teen photography" in patch_text
    assert "doll-like child face" in patch_text
    assert "pageant" in patch_text
