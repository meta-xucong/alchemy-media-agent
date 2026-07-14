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


def test_human_photorealism_layer_does_not_activate_for_nonhuman_photoreal_style() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_surreal_landscape",
        job_id="job_surreal_landscape",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=(
            "Create a non-photorealistic surreal floating glass garden above an ocean, "
            "with no people and no products."
        ),
        subject_type="generic",
        variation_mode="creative_exploration",
        has_identity_reference=False,
    )

    assert guidance.applies is False
    assert guidance.metadata["disabled_reason"] == "no_human_signal"


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
    assert plugin["human_subject_kind"] == "product_on_person"
    assert plugin["strictness"] == "commercial_strict"
    assert plugin["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"
    assert plugin["disabled_by_style"] is False
    assert "product_on_person_detected" in plugin["reason_codes"]
    assert "age-inappropriate facial morphology" in guidance.negative_prompt_fragments


def test_doc114_generic_human_realism_recognizes_numeric_age_and_photographic_scene_coherence() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc114_numeric_age",
        job_id="job_doc114_numeric_age",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        user_input=(
            "Create a real-camera apparel-on-model image of a 6-year-old wearing the supplied layered dress, "
            "with a natural candid expression in a softly lit photographed room."
        ),
        subject_type="product",
        variation_mode="delivery_suite",
        has_identity_reference=False,
        metadata={"product_profile": {"product_category": "apparel"}},
    )

    plugin = guidance.metadata["human_realism_plugin"]
    positive_text = " ".join(guidance.positive_prompt_fragments).lower()
    negative_text = " ".join(guidance.negative_prompt_fragments).lower()
    review_text = " ".join(guidance.review_targets).lower()

    assert plugin["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"
    assert "explicit_age_fidelity_signal" in plugin["reason_codes"]
    assert plugin["universal_rendering_profile"]["scene_photographic_coherence"] == "preserve_physical_light_depth_contact"
    assert "caught photographic moment" in positive_text
    assert "physically coherent photographed space" in positive_text
    assert "35mm or ccd-inspired" not in positive_text
    assert "flat evenly lit backdrop" in negative_text
    assert "distinct natural shutter moments" in review_text

    chinese_guidance = layer.build(
        project_id="project_doc114_numeric_age_zh",
        job_id="job_doc114_numeric_age_zh",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        user_input="为穿着连衣裙的6岁人物生成真实摄影电商图，自然表情和真实环境光。",
        subject_type="product",
        variation_mode="delivery_suite",
        has_identity_reference=False,
        metadata={"product_profile": {"product_category": "apparel"}},
    )

    assert chinese_guidance.metadata["human_realism_plugin"]["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"


def test_doc114_generic_scene_and_pose_issue_codes_flow_through_shared_human_review() -> None:
    registry = SharedCapabilityRegistry.with_default_modules()

    result = registry.run(
        CapabilityInput(
            job_id="job_doc114_generic_review",
            scenario_id="general_creative",
            user_input="Create a realistic person wearing a jacket in a naturally lit room.",
            metadata={
                "template_id": "general_template",
                "force_anti_ai_face_issue_codes": [
                    "flat_scene_lighting",
                    "airbrushed_background_texture",
                    "synthetic_material_response",
                    "frozen_centered_pose",
                ],
                "project_context_snapshot": {"project_id": "project_doc114_generic_review"},
            },
        ),
        module_ids=["visual_capability_cluster"],
    )

    review = result.results[-1].facts["visual_capability_cluster"]["anti_ai_face_review"]

    assert review["status"] == "retry_recommended"
    assert set(review["issue_codes"]) == {
        "flat_scene_lighting",
        "airbrushed_background_texture",
        "synthetic_material_response",
        "frozen_centered_pose",
    }
    assert "physical light environment" in " ".join(review["retry_patch"]["artifact_repair"])


def test_doc92_moody_traditional_portrait_suppresses_bright_fresh_skin_pressure() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc92_gufeng",
        job_id="job_doc92_gufeng",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=(
            "国风写实人像摄影，古典柔焦电影美学，清冷忧郁暗调，冷青银白色调，"
            "局部聚光，年轻女性，冷白肤色，柔和高光，古装，梨花背景"
        ),
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=True,
    )

    plugin = guidance.metadata["human_realism_plugin"]
    positives = " ".join(guidance.positive_prompt_fragments).lower()
    negatives = " ".join(guidance.negative_prompt_fragments).lower()

    assert guidance.applies is True
    assert plugin["style_profile"] == "low_key_texture_preserving"
    assert "natural human skin texture" in positives
    assert "clean high-key summer daylight" not in positives
    assert "soft natural bounce light" not in positives
    assert "demographic default" not in positives
    assert "under a low exposure key" in positives
    assert "oily forehead or cheeks in low-key light" in negatives
    assert "waxy nose-bridge highlight" in negatives
    assert "generic high-key commercial face lighting overriding the prompt" in negatives


def test_doc92_bright_summer_portrait_keeps_fresh_commercial_profile() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc92_summer",
        job_id="job_doc92_summer",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a clean bright summer East Asian portrait photo with fresh daylight and healthy clear complexion",
        subject_type="character",
        variation_mode="selection_candidates",
        has_identity_reference=False,
    )

    plugin = guidance.metadata["human_realism_plugin"]
    positives = " ".join(guidance.positive_prompt_fragments).lower()

    assert plugin["style_profile"] == "high_key_texture_preserving"
    assert "under a high exposure key" in positives
    assert "whitening or smoothing filter" in positives


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
    assert plugin["human_subject_kind"] == "product_on_person"
    assert plugin["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"
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


def test_doc104_hand_only_product_context_uses_hand_specific_shared_guidance() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc104_hand",
        job_id="job_doc104_hand",
        scenario_id="general_creative",
        template_id="general_template",
        user_input="Create a product surface scene with an adult hand and visible fingers holding a drink; no face.",
        subject_type="product",
        variation_mode="selection_candidates",
        has_identity_reference=False,
    )

    plugin = guidance.metadata["human_realism_plugin"]
    prompt_text = " ".join(guidance.positive_prompt_fragments).lower()
    negative_text = " ".join(guidance.negative_prompt_fragments).lower()

    assert guidance.applies is True
    assert plugin["human_subject_kind"] == "hand_or_skin_detail"
    assert "correct finger count" in prompt_text
    assert "physically credible finger placement" in prompt_text
    assert "natural eye moisture" not in prompt_text
    assert "micro-expression" not in prompt_text
    assert "extra fingers" in negative_text
    assert "face-slimming" not in negative_text


def test_full_person_context_keeps_incidental_hands_out_of_detail_only_guidance() -> None:
    """A full person outranks incidental anatomy words in every template."""

    layer = HumanPhotorealismLayer()
    guidance = layer.build(
        project_id="project_full_person_hands",
        job_id="job_full_person_hands",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        user_input=(
            "Create a full-body product-on-person photograph of a fictional school-age child "
            "wearing a dress with natural skin texture, expression, hands, and posture."
        ),
        subject_type="product",
        variation_mode="delivery_suite",
        has_identity_reference=False,
    )

    plugin = guidance.metadata["human_realism_plugin"]
    prompt_text = " ".join(guidance.positive_prompt_fragments).lower()

    assert guidance.applies is True
    assert plugin["human_subject_kind"] == "product_on_person"
    assert "hand_or_skin_detail_detected" not in plugin["reason_codes"]
    assert "adult hand or forearm" not in prompt_text
    assert "keep any face out of frame" not in prompt_text


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

    assert "requested or referenced age band" in patch_text
    assert "adultification" in patch_text
    assert "doll-like morphology" in patch_text


def test_doc92_child_model_retry_patch_does_not_depend_on_moody_traditional_style() -> None:
    layer = HumanPhotorealismLayer()

    guidance = layer.build(
        project_id="project_doc92_kidswear",
        job_id="job_doc92_kidswear",
        scenario_id="ecommerce",
        template_id="ecommerce_template",
        user_input="Create a kidswear ecommerce catalog photo with a real child model wearing a blue dress in clean studio light",
        subject_type="product",
        variation_mode="selection_candidates",
        has_identity_reference=False,
        metadata={"product_profile": {"category": "kidswear dress"}},
    )
    retry_text = " ".join(
        [
            *guidance.retry_patch_templates["prompt_additions"],
            *guidance.retry_patch_templates["negative_additions"],
            *guidance.retry_patch_templates["artifact_repair"],
        ]
    ).lower()

    assert guidance.metadata["human_realism_plugin"]["human_subject_kind"] == "product_on_person"
    assert guidance.metadata["human_realism_plugin"]["universal_rendering_profile"]["age_fidelity"] == "follow_explicit_prompt"
    assert "repair age drift" in retry_text
    assert "adultification" in retry_text
    assert "doll-like morphology" in retry_text
