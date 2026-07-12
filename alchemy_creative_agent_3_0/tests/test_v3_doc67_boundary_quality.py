from pathlib import Path

from alchemy_creative_agent_3_0.app.product_api import V3ProductApiService
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    HumanPhotorealismLayer,
    ModeQualityProfileBuilder,
    ProjectIdentityAnchor,
    StrongReferenceClosureBuilder,
    StrongReferenceContinuationPlan,
    VisualIdentityLockProfile,
)


ROOT = Path(__file__).resolve().parents[1]


def test_doc67_boundary_keeps_visual_child_modules_out_of_central_and_fallback_brains() -> None:
    central = (ROOT / "app" / "creative_core" / "central_brain.py").read_text(encoding="utf-8")
    fallback = (ROOT / "app" / "llm_brain" / "fallback.py").read_text(encoding="utf-8")

    assert "ModeAwareRoleDirector" not in central
    assert "_reconcile_mode_roles_to_series_plan" not in central
    assert "HumanNaturalVariationPolicy" not in fallback
    assert "human_variation.py" not in fallback


def test_doc67_ecommerce_role_metadata_is_owned_by_ecommerce_pack_not_central_brain() -> None:
    service = V3ProductApiService()
    created = service.create_job(
        {
            "user_input": "Create an Aqua Tea marketplace set with main image, freshness feature image, and real summer cafe scene",
            "scenario_selection": {
                "scenario_id": "ecommerce",
                "mode_id": "one_click_product_set",
                "platform_profile": "amazon_us",
                "parameters": {
                    "requested_image_count": 3,
                    "suite_slot_request": ["main_image", "feature_image_1", "scenario_image"],
                },
            },
            "uploaded_asset_ids": ["product_aqua_tea_can"],
            "product_profile": {
                "product_category": "drink",
                "materials": ["turquoise aluminum can", "printed lime mint label"],
                "selling_points": ["Cold lime mint refreshment", "Portable summer drink"],
            },
            "metadata": {"requested_image_count": 3, "variation_mode": "delivery_suite"},
        }
    )

    slots = [item.metadata["asset_metadata"]["mode_role_recipe"]["role_key"] for item in created.asset_series]
    assert slots == ["main_image", "feature_image_1", "scenario_image"]
    assert all(
        item.metadata["asset_metadata"]["mode_role_recipe"]["metadata"]["owned_by"] == "ecommerce_vertical_pack"
        for item in created.asset_series
    )

    generated = service.generate_job(created.job_id, {"quality_mode": "standard", "metadata": {"requested_image_count": 3}})
    visual_cluster = generated.metadata.get("visual_cluster") or generated.metadata["shared_capabilities"]["visual_cluster"]
    role_plan = visual_cluster["role_specific_generation_plan"]
    candidate_role_keys = [candidate.metadata["mode_role_recipe"]["role_key"] for candidate in generated.candidates]
    record = service.job_store.get(created.job_id)
    feature_prompt = record.generation_result.prompt_compilations[1].visual_prompt

    assert role_plan["metadata"]["doc"] == "60"
    assert role_plan["metadata"]["doc67_boundary_cleanup"] is True
    assert role_plan["metadata"]["owned_by"] == "ecommerce_vertical_pack"
    assert [recipe["role_key"] for recipe in role_plan["role_recipes"]] == slots
    assert candidate_role_keys == slots
    assert "Planned ecommerce slot 2 (feature_image_1)" in feature_prompt
    assert "Planned image role 3 (detail_image)" not in feature_prompt


def test_doc67_human_photorealism_contract_gets_real_photo_detail_without_clone_pressure() -> None:
    guidance = HumanPhotorealismLayer().build(
        project_id="project_portrait",
        job_id="job_portrait",
        scenario_id="general_creative",
        template_id="general",
        user_input="East Asian summer cool portrait, realistic model photo, green-highlighted hair",
        subject_type="character",
        variation_mode="delivery_suite",
        has_identity_reference=True,
    )

    positive = " ".join(guidance.positive_prompt_fragments)
    negative = " ".join(guidance.negative_prompt_fragments)
    preserve = " ".join(guidance.reference_preserve_rules)
    cleanup = " ".join(guidance.reference_do_not_inherit_rules)

    assert guidance.applies is True
    assert "tiny believable skin imperfections" in positive
    assert "real lens perspective" in positive
    assert "generic AI influencer face" in negative
    assert "identical face angle across the whole set" in negative
    assert "not by repeating the exact same still" in preserve
    assert "AI badges" in cleanup


def test_doc67_mode_quality_profiles_penalize_over_cloned_portrait_batches() -> None:
    builder = ModeQualityProfileBuilder()

    delivery = builder.build(project_id="project", job_id="job", mode="delivery_suite", subject_type="character")
    selection = builder.build(project_id="project", job_id="job", mode="selection_candidates", subject_type="character")

    assert "over_cloned_portrait_batch" in delivery.retry_triggers
    assert "over_cloned_portrait_batch" in selection.retry_triggers
    assert any("same face angle" in item for item in delivery.negative_guidance)
    assert any("micro-expression" in item for item in selection.prompt_guidance)


def test_doc67_generic_continuation_and_mode_profile_stay_subject_neutral() -> None:
    closure = StrongReferenceClosureBuilder().build(
        project_id="project",
        job_id="job",
        subject_type="generic",
        continuation_plan=StrongReferenceContinuationPlan(
            plan_id="plan",
            provider_required_reference_ids=["selected_architecture"],
            lock_targets=["visual_direction"],
            prompt_additions=["keep the concrete, oak, and late-afternoon architectural direction"],
        ),
        anchors=[
            ProjectIdentityAnchor(
                anchor_id="anchor",
                subject_type="generic",
                style_keep_rules=["same restrained architecture palette"],
                allowed_variations=["change skylight framing"],
                forbidden_drift=["unrelated visual genre"],
            )
        ],
        identity_locks=[],
        human_photorealism=None,
    )
    profile = ModeQualityProfileBuilder().build(
        project_id="project",
        job_id="job",
        mode="selection_candidates",
        subject_type="generic",
    )

    generic_text = " ".join(
        [
            *closure.allowed_variations,
            *closure.forbidden_drift,
            *closure.provider_prompt_rules,
            *closure.negative_prompt_rules,
            *profile.review_priorities,
            *profile.pass_conditions,
            *profile.retry_triggers,
            *profile.prompt_guidance,
            *profile.negative_guidance,
        ]
    ).lower()
    for person_only_term in ("gaze", "hand placement", "micro-expression", "face angle", "plastic skin", "same_ai_face"):
        assert person_only_term not in generic_text
    assert "same visual direction" in profile.review_priorities
    assert "framing, viewpoint, camera, lighting, or scene depth" in profile.prompt_guidance[0]


def test_doc67_strong_reference_closure_preserves_identity_without_copying_artifacts() -> None:
    closure = StrongReferenceClosureBuilder().build(
        project_id="project",
        job_id="job",
        subject_type="character",
        continuation_plan=StrongReferenceContinuationPlan(
            plan_id="plan",
            provider_required_reference_ids=["selected_output_1"],
            lock_targets=["person_identity"],
            prompt_additions=["keep the blue seaside light"],
            negative_additions=["do not repeat the source frame exactly"],
        ),
        anchors=[
            ProjectIdentityAnchor(
                anchor_id="anchor",
                subject_type="character",
                identity_keep_rules=["same broad face shape and green-highlighted hair direction"],
                style_keep_rules=["same summer seaside light"],
                allowed_variations=["change body pose"],
                forbidden_drift=["identity drift"],
            )
        ],
        identity_locks=[
            VisualIdentityLockProfile(
                lock_id="lock",
                subject_type="character",
                keep_rules=["same body type"],
                forbidden_drift=["face swap"],
                negative_constraints=["same exact still repeated"],
            )
        ],
        human_photorealism=HumanPhotorealismLayer().build(
            project_id="project",
            job_id="job",
            scenario_id="general_creative",
            template_id="general",
            user_input="realistic portrait",
            subject_type="character",
            variation_mode="delivery_suite",
            has_identity_reference=True,
        ),
    )

    assert closure.active is True
    assert "change hand placement, body turn, micro-expression" in " ".join(closure.allowed_variations)
    assert "AI badges" in " ".join(closure.forbidden_drift)
    assert any("do not clone the exact source frame" in item for item in closure.provider_prompt_rules)
