import json

from alchemy_creative_agent_3_0.app.shared_capabilities import CapabilityInput, SharedCapabilityRegistry
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import (
    ActivatedCapability,
    CapabilityActivationPlan,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.base import (
    VisualPluginContext,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.plugins.human_realism import (
    HumanRealismPlugin,
)


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


def _ecommerce_review_context() -> dict:
    return {
        "contract_version": "ecommerce_human_realism_review_context_v1",
        "owner": "shared_human_realism_review",
        "source": "ecommerce_creative_risk_preflight",
        "source_contract_version": "ecommerce_creative_risk_preflight_v1",
        "applies_to": "ecommerce",
        "mode": "professional",
        "requested_image_count": 2,
        "risk_items_by_output": [
            {
                "output_index": 1,
                "risk_family": ["pasted_face", "head_body_scale_mismatch"],
                "primary_goal_hint": "emotion_hero",
                "risk_level": "medium",
                "strategy_policy": [
                    "action_triggered_expression",
                    "separate_composition_reference_from_identity",
                ],
                "professional_identity_hint": {
                    "preferred_identity_view_kind": "front",
                    "identity_strategy": "secondary_face",
                    "source": "professional_binding_resolver",
                },
            }
        ],
        "global_risks": ["pasted_face"],
        "post_review_authority": "shared_human_realism_review",
        "retry_authority": "shared_human_realism_review",
        "ecommerce_may_score_pixels": False,
        "ecommerce_may_trigger_retry": False,
    }


def _human_realism_plugin_contribution(guidance):
    active = ActivatedCapability(
        capability_id="human_realism",
        version="v1",
        selected_profile="balanced",
    )
    plan = CapabilityActivationPlan(
        plan_id="plan_human_realism",
        fingerprint="fp_human_realism",
        job_id="job_human_realism",
        task_profile_id="profile_human_realism",
        template_id="ecommerce_template",
        scenario_id="ecommerce",
        active_capabilities=[active],
        dependency_order=["human_realism"],
    )
    return HumanRealismPlugin().contribute(
        VisualPluginContext(
            plan=plan,
            active=active,
            cluster={"human_photorealism_guidance": guidance.model_dump(mode="json")},
        )
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


def test_ecommerce_risk_context_reaches_shared_human_review_without_prompt_or_retry_authority() -> None:
    guidance = _build(
        "Professional ecommerce photo of a real child model wearing a product in a natural lifestyle scene.",
        subject_type="product",
        metadata={
            "brain_owned_forward_execution": True,
            "ecommerce_human_realism_review_context": _ecommerce_review_context(),
        },
    )

    assert guidance.applies is True
    assert guidance.positive_prompt_fragments == []
    assert guidance.negative_prompt_fragments == []
    assert guidance.retry_patch_templates == {}
    assert (
        guidance.metadata["ecommerce_human_realism_review_context"]["owner"]
        == "shared_human_realism_review"
    )

    contribution = _human_realism_plugin_contribution(guidance)

    assert contribution.prompt_additions == []
    assert contribution.negative_additions == []
    assert (
        contribution.review_contract["ecommerce_human_realism_review_context"]["source"]
        == "ecommerce_creative_risk_preflight"
    )
    assert contribution.review_contract["post_review_authority"] == "shared_human_realism_review"
    assert contribution.review_contract["ecommerce_may_score_pixels"] is False
    assert (
        contribution.retry_contract["metadata"]["retry_authority"]
        == "shared_human_realism_review"
    )
    assert contribution.retry_contract["metadata"]["ecommerce_may_trigger_retry"] is False
    serialized = json.dumps(contribution.model_dump(mode="json"), ensure_ascii=False)
    for forbidden in ("v3_output", "asset_id", "D:", "original.png", "provider_payload"):
        assert forbidden not in serialized


def test_general_human_realism_has_no_ecommerce_review_context() -> None:
    guidance = _build("Create a realistic portrait of an adult in a studio.")

    contribution = _human_realism_plugin_contribution(guidance)

    assert "ecommerce_human_realism_review_context" not in guidance.metadata
    assert "ecommerce_human_realism_review_context" not in contribution.review_contract
    assert "ecommerce_human_realism_review_context" not in contribution.retry_contract.get(
        "metadata",
        {},
    )


def test_malformed_ecommerce_review_context_is_not_forwarded_to_shared_review() -> None:
    unsafe_context = {
        **_ecommerce_review_context(),
        "file_path": "D:/unsafe/original.png",
    }
    guidance = _build(
        "Professional ecommerce photo of a real person wearing a product.",
        subject_type="product",
        metadata={"ecommerce_human_realism_review_context": unsafe_context},
    )

    contribution = _human_realism_plugin_contribution(guidance)

    assert "ecommerce_human_realism_review_context" not in guidance.metadata
    assert "ecommerce_human_realism_review_context" not in contribution.review_contract


def test_ecommerce_review_context_rejects_unknown_or_invalid_closed_enum_values() -> None:
    cases = []
    cases.append({"mode": "other_mode"})
    cases.append({"source_contract_version": "ecommerce_creative_risk_preflight_v999"})
    cases.append({"global_risks": ["unknown_risk"]})
    cases.append({"global_risks": ["pasted_face", "pasted_face"]})
    cases.append({"global_risks": ["template_expression"]})
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "risk_family": ["unknown_risk"],
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "risk_family": [],
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "risk_family": ["pasted_face", "pasted_face"],
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "strategy_policy": [],
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "strategy_policy": [
                        "action_triggered_expression",
                        "action_triggered_expression",
                    ],
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                _ecommerce_review_context()["risk_items_by_output"][0],
                _ecommerce_review_context()["risk_items_by_output"][0],
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "primary_goal_hint": "unknown_goal",
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "risk_level": "severe",
                }
            ]
        }
    )
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "strategy_policy": ["unknown_strategy"],
                }
            ]
        }
    )
    bad_hint = {
        **_ecommerce_review_context()["risk_items_by_output"][0]["professional_identity_hint"],
        "preferred_identity_view_kind": "sideways",
    }
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "professional_identity_hint": bad_hint,
                }
            ]
        }
    )
    bad_strategy_hint = {
        **_ecommerce_review_context()["risk_items_by_output"][0]["professional_identity_hint"],
        "identity_strategy": "coherent_secondary_turn",
    }
    cases.append(
        {
            "risk_items_by_output": [
                {
                    **_ecommerce_review_context()["risk_items_by_output"][0],
                    "professional_identity_hint": bad_strategy_hint,
                }
            ]
        }
    )

    for override in cases:
        context = {**_ecommerce_review_context(), **override}
        guidance = _build(
            "Professional ecommerce photo of a real person wearing a product.",
            subject_type="product",
            metadata={"ecommerce_human_realism_review_context": context},
        )
        contribution = _human_realism_plugin_contribution(guidance)

        assert "ecommerce_human_realism_review_context" not in guidance.metadata
        assert "ecommerce_human_realism_review_context" not in contribution.review_contract
