"""Doc168: fresh enforced reference ownership is a Remote-Brain decision."""

from __future__ import annotations

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.adapter import (
    _has_complete_remote_visual_task_profile,
)
from alchemy_creative_agent_3_0.app.llm_brain.prompts import (
    _compact_required_remote_creative_schema,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster import (
    ReferenceChannelPolicyModule,
    StrongReferenceBinding,
)
from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.reference_channel_policy import (
    BrainReferenceChannelOwnershipIntentError,
)


def _portrait_binding() -> StrongReferenceBinding:
    return StrongReferenceBinding(
        binding_id="binding_doc168",
        source_type="uploaded",
        source_id="authorized_identity_root",
        asset_id="authorized_identity_root",
        file_path="D:/authorized/identity.png",
        role="portrait_identity_reference",
        strength="hard",
        use_policy="identity",
        lock_targets=["face_identity"],
        provider_input_required=True,
        confidence=0.99,
    )


def _remote_intent(
    *,
    reference_owned: list[str],
    current_owned: list[str],
    applicability: str = "applicable",
    owner: str = "remote_brain",
) -> dict[str, object]:
    return {
        "applicability": applicability,
        "decision_owner": owner,
        "reference_owned_channels": reference_owned,
        "current_request_owned_channels": current_owned,
        "evidence_ids": ["evidence_user_reference_ownership"],
        "confidence": 0.97,
    }


def _enforced_metadata(intent: dict[str, object] | None) -> dict[str, object]:
    profile: dict[str, object] = {}
    if intent is not None:
        profile["reference_channel_ownership_intent"] = intent
    return {
        "brain_owned_forward_execution": True,
        "require_real_images": True,
        "visual_task_profile": profile,
    }


def _complete_remote_profile() -> dict[str, object]:
    return {
        "rendering_intent": {
            "rendering_mode": "photoreal",
            "stylization_scope": "none",
            "decision_owner": "remote_brain",
        },
        "developmental_age_intent": "current_request_assigns_stage",
        "reference_channel_ownership_intent": _remote_intent(
            reference_owned=["identity_geometry"],
            current_owned=[
                "body_identity",
                "natural_complexion_direction",
                "hair_direction",
                "wardrobe_structure",
                "lighting_color",
                "scene_background",
                "camera_composition",
                "mood_art_direction",
                "style_finish",
            ],
        ),
        "subject_entities": [],
        "visual_intent_tags": [],
        "unknown_requirements": [],
        "confidence": 0.95,
        "evidence": [],
    }


def test_doc168_compact_remote_schema_requires_typed_reference_ownership() -> None:
    profile = _compact_required_remote_creative_schema()["visual_task_profile"]
    intent = profile["reference_channel_ownership_intent"]

    allowed = (
        "identity_geometry|body_identity|natural_complexion_direction|hair_direction|makeup_style|"
        "wardrobe_structure|accessory_system|product_identity|lighting_color|scene_background|"
        "camera_composition|mood_art_direction|style_finish"
    )
    assert intent == {
        "applicability": "applicable|not_applicable|ambiguous",
        "decision_owner": "remote_brain",
        "reference_owned_channels": [allowed],
        "current_request_owned_channels": [allowed],
        "evidence_ids": ["visual_task_profile evidence_id"],
        "confidence": "number from 0 through 1",
    }


def test_doc168_remote_profile_is_incomplete_without_reference_ownership_intent() -> None:
    profile = _complete_remote_profile()
    assert _has_complete_remote_visual_task_profile(profile) is True

    profile.pop("reference_channel_ownership_intent")
    assert _has_complete_remote_visual_task_profile(profile) is False


def test_doc168_enforced_policy_uses_brain_meaning_not_same_word_proximity() -> None:
    prompt = (
        "Use the same person exactly in a new head-and-shoulders camera composition. "
        "Do not inherit source age, hair, wardrobe, scene, light, pose, expression, complexion, or finish."
    )
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc168",
        job_id="job_doc168",
        user_input=prompt,
        subject_type="character",
        template_id="general_template",
        strong_bindings=[_portrait_binding()],
        advanced_reference_controls={"preserve_person_identity": True},
        metadata=_enforced_metadata(
            _remote_intent(
                reference_owned=["identity_geometry"],
                current_owned=[
                    "body_identity",
                    "natural_complexion_direction",
                    "hair_direction",
                    "wardrobe_structure",
                    "lighting_color",
                    "scene_background",
                    "camera_composition",
                    "mood_art_direction",
                    "style_finish",
                ],
            )
        ),
    )
    policy = package.policies[0]

    assert policy.identity_geometry == "hard"
    assert policy.camera_composition == "prompt_owned"
    assert policy.scene_background == "prompt_owned"
    assert policy.lighting_color == "prompt_owned"
    assert policy.natural_complexion_direction == "prompt_owned"
    assert "camera_composition" not in policy.explicit_user_locks
    assert package.prompt_ownership.metadata["resolver"] == "remote_brain_semantic_intent_only"


@pytest.mark.parametrize(
    ("intent", "expected_code"),
    [
        (None, "brain_reference_channel_ownership_intent_missing"),
        (
            _remote_intent(
                reference_owned=["identity_geometry"],
                current_owned=[],
                applicability="ambiguous",
            ),
            "brain_reference_channel_ownership_intent_ambiguous",
        ),
        (
            _remote_intent(
                reference_owned=["identity_geometry"],
                current_owned=[],
                owner="evidence_fallback",
            ),
            "brain_reference_channel_ownership_intent_not_remote",
        ),
    ],
)
def test_doc168_enforced_reference_policy_fails_closed_without_remote_decision(
    intent: dict[str, object] | None,
    expected_code: str,
) -> None:
    with pytest.raises(BrainReferenceChannelOwnershipIntentError, match=expected_code):
        ReferenceChannelPolicyModule().resolve(
            project_id="project_doc168",
            job_id="job_doc168_blocked",
            user_input="Keep the same person in a new portrait.",
            subject_type="character",
            template_id="general_template",
            strong_bindings=[_portrait_binding()],
            advanced_reference_controls={"preserve_person_identity": True},
            metadata=_enforced_metadata(intent),
        )


def test_doc168_brain_can_explicitly_assign_source_wardrobe_without_local_parser() -> None:
    package = ReferenceChannelPolicyModule().resolve(
        project_id="project_doc168",
        job_id="job_doc168_outfit",
        user_input="Create a new portrait from the supplied references.",
        subject_type="character",
        template_id="general_template",
        strong_bindings=[_portrait_binding()],
        advanced_reference_controls={"preserve_person_identity": True},
        metadata=_enforced_metadata(
            _remote_intent(
                reference_owned=["identity_geometry", "wardrobe_structure"],
                current_owned=["scene_background", "camera_composition", "lighting_color"],
            )
        ),
    )

    assert package.policies[0].wardrobe_structure == "hard"
    assert package.policies[0].scene_background == "prompt_owned"
    assert package.policies[0].camera_composition == "prompt_owned"
