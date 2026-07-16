from pathlib import Path

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import HumanPhotorealismLayer
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.human_photorealism import (
    HUMAN_REALISM_REVIEW_DIMENSIONS,
    normalize_human_realism_issue_code,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _inspection_prompt,
    active_review_contract,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


ROOT = Path(__file__).resolve().parents[1]


def _guidance(text: str, *, subject_type: str = "character"):
    return HumanPhotorealismLayer().build(
        project_id="project_doc128",
        job_id="job_doc128",
        scenario_id="general_creative",
        template_id="general_template",
        user_input=text,
        subject_type=subject_type,
        variation_mode="single_hero",
        has_identity_reference=True,
    )


def test_doc128_uses_a_small_shared_constraint_contract_for_real_people() -> None:
    guidance = _guidance(
        "A real-camera portrait of an adult wearing a blue linen shirt in quiet evening light."
    )

    assert guidance.applies is True
    assert guidance.metadata["doc128_shared_constraint_contract"] is True
    assert "doc68_casebook_recipe" not in guidance.metadata
    assert "casebook_recipe_library" not in guidance.metadata
    assert len(guidance.positive_prompt_fragments) <= 3
    assert len(guidance.negative_prompt_fragments) <= 2
    assert len(guidance.review_targets) <= len(HUMAN_REALISM_REVIEW_DIMENSIONS)
    text = "\n".join(
        [
            *guidance.positive_prompt_fragments,
            *guidance.negative_prompt_fragments,
            *guidance.review_targets,
            *guidance.retry_patch_templates.get("prompt_additions", []),
        ]
    ).lower()
    for legacy_fragment in (
        "idol photocard",
        "baby hairs",
        "visible pores",
        "adult hand or forearm",
        "east asian",
        "child model",
    ):
        assert legacy_fragment not in text


def test_doc128_explicit_young_person_is_safe_shared_evidence_not_a_child_recipe() -> None:
    guidance = _guidance(
        "A fully clothed school-age child watering flowers in an ordinary family garden, photographed naturally.",
        subject_type="product",
    )

    plugin = guidance.metadata["human_realism_plugin"]
    safety = guidance.metadata["provider_safety_profile"]
    assert guidance.applies is True
    assert plugin["human_subject_kind"] == "person"
    assert safety["applies"] is True
    assert safety["contract"] == "safety_sensitive_person_v1"
    assert "child" not in " ".join(guidance.positive_prompt_fragments).lower()
    assert "child" not in " ".join(guidance.negative_prompt_fragments).lower()


def test_doc128_product_only_children_garment_does_not_activate_human_realism() -> None:
    guidance = _guidance(
        "A children's blue dress flat lay on a white background, no people.",
        subject_type="product",
    )

    assert guidance.applies is False
    assert guidance.metadata["human_realism_plugin"]["applies"] is False


def test_doc128_legacy_human_codes_are_read_only_aliases_to_shared_dimensions() -> None:
    expected = {
        "doll_like_child_face": "human_rendering_artifact",
        "adultified_child_model": "human_age_or_identity_fidelity",
        "synthetic_child_skin": "human_skin_or_retouch",
        "bad_hands_or_body": "human_anatomy_or_proportion",
        "template_smile": "human_expression_context",
        "flat_scene_lighting": "human_scene_coherence",
    }

    assert set(HUMAN_REALISM_REVIEW_DIMENSIONS) == set(expected.values())
    for legacy, normalized in expected.items():
        assert normalize_human_realism_issue_code(legacy) == normalized
    assert normalize_human_realism_issue_code("product_identity_drift") == "product_identity_drift"
    assert normalize_human_realism_issue_code("age_identity_drift") == "age_identity_drift"
    assert normalize_human_realism_issue_code("same_pose_repetition") == "same_pose_repetition"


def test_doc128_runtime_no_longer_imports_or_materializes_casebook_prompt_stacks() -> None:
    files = [
        ROOT / "app/shared_capabilities/visual_cluster/human_photorealism.py",
        ROOT / "app/shared_capabilities/visual_cluster/mode_role_director.py",
        ROOT / "app/shared_capabilities/visual_cluster/doc66_closure.py",
        ROOT / "app/generation_router/providers.py",
    ]
    source = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "casebook_recipes import" not in source
    assert "provider_casebook_prompt_lines" not in source
    assert "apply_role_recipe_casebook_overlay" not in source


def test_doc128_enforced_vision_contract_exposes_only_shared_human_dimensions(monkeypatch) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    result = ScenarioRuntime().plan_job(
        {
            "user_input": "A real-camera portrait of an adult in a cafe.",
            "scenario_selection": {"scenario_id": "general_creative"},
            "metadata": {"requested_image_count": 1},
        }
    ).planning_result

    contract = active_review_contract(dict(result.metadata))
    prompt = _inspection_prompt(dict(result.metadata))

    assert set(HUMAN_REALISM_REVIEW_DIMENSIONS).issubset(set(contract["issue_codes"]))
    for legacy in ("doll_like_child_face", "adultified_child_model", "synthetic_child_skin"):
        assert legacy not in contract["issue_codes"]
        assert legacy not in prompt
