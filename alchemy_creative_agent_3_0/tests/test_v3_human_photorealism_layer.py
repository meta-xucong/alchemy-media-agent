from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer


def _build(text: str, *, subject_type: str = "character", metadata: dict | None = None):
    return HumanPhotorealismLayer().build(
        project_id="project_human_realism",
        job_id="job_human_realism",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=text,
        subject_type=subject_type,
        variation_mode="single_hero",
        has_identity_reference=True,
        metadata=metadata,
    )


def test_human_realism_activates_for_a_real_person_with_compact_shared_guidance() -> None:
    guidance = _build("Create a real-camera editorial portrait of an adult in a blue shirt at dusk.")

    assert guidance.applies is True
    assert guidance.metadata["doc128_shared_constraint_contract"] is True
    assert len(guidance.positive_prompt_fragments) == 3
    assert len(guidance.negative_prompt_fragments) == 1
    assert guidance.metadata["human_realism_plugin"]["human_subject_kind"] in {"person", "product_on_person"}


def test_human_realism_does_not_override_a_stylized_person_request() -> None:
    guidance = _build("Create an anime manga illustration of a fantasy girl.")

    assert guidance.applies is False
    assert guidance.metadata["disabled_reason"] == "stylized_request"


def test_object_artwork_does_not_suppress_visible_real_person_activation() -> None:
    guidance = _build(
        "Create a realistic photo of a model wearing a shirt with a front illustration print.",
        subject_type="product",
    )

    assert guidance.applies is True
    assert guidance.metadata["human_realism_plugin"]["disabled_by_style"] is False


def test_product_only_flat_lay_does_not_activate_human_realism() -> None:
    guidance = _build(
        "A children's blue dress flat lay on a white background, no people.",
        subject_type="product",
    )

    assert guidance.applies is False
    assert guidance.metadata["disabled_reason"] == "no_visible_person_evidence"


def test_explicit_young_person_uses_shared_safety_profile_without_a_child_recipe() -> None:
    guidance = _build(
        "A fully clothed school-age child watering flowers in an ordinary family garden, photographed naturally.",
        subject_type="product",
    )

    assert guidance.applies is True
    assert guidance.metadata["provider_safety_profile"]["applies"] is True
    assert guidance.metadata["provider_safety_profile"]["contract"] == "safety_sensitive_person_v1"
    text = " ".join([*guidance.positive_prompt_fragments, *guidance.negative_prompt_fragments]).lower()
    assert "child" not in text
    assert "adultification" not in text


def test_hand_detail_stays_a_shared_non_face_contract() -> None:
    guidance = _build(
        "A product scene with an adult hand holding a glass, no face.",
        subject_type="product",
    )

    assert guidance.applies is True
    assert guidance.metadata["human_realism_plugin"]["human_subject_kind"] == "hand_or_skin_detail"
    assert not any("face" in item.lower() for item in guidance.positive_prompt_fragments)


def test_legacy_issue_codes_normalize_before_shared_retry() -> None:
    layer = HumanPhotorealismLayer()
    guidance = _build("A real-camera portrait of an adult.")
    review = layer.review(
        guidance=guidance,
        project_id="project_human_realism",
        job_id="job_human_realism",
        issue_codes=["doll_like_child_face", "synthetic_child_skin", "bad_hands_or_body"],
    )

    assert set(review.issue_codes) == {
        "human_rendering_artifact",
        "human_skin_or_retouch",
        "human_anatomy_or_proportion",
    }
    retry = layer.retry_patch_for_issue_codes(["adultified_child_model"])
    assert retry["review_dimensions"] == ["human_developmental_age_coherence"]
    assert len(retry["prompt_additions"]) == 1


def test_visual_cluster_keeps_shared_human_review_and_bounded_retry() -> None:
    result = SharedCapabilityRegistry.with_default_modules().run(
        CapabilityInput(
            job_id="job_cluster_human_realism",
            scenario_id="general_creative",
            user_input="Create a realistic person wearing a jacket in a naturally lit room.",
            metadata={
                "template_id": "general_template",
                "force_anti_ai_face_issue_codes": ["plastic_skin", "flat_scene_lighting"],
                "project_context_snapshot": {"project_id": "project_cluster_human_realism"},
            },
        ),
        module_ids=["visual_capability_cluster"],
    )
    cluster = result.results[-1].facts["visual_capability_cluster"]
    review = cluster["anti_ai_face_review"]

    assert review["status"] == "retry_recommended"
    assert set(review["issue_codes"]) == {"human_skin_or_retouch", "human_scene_coherence"}
    assert "human_photorealism_layer" in cluster["child_module_ids"]
