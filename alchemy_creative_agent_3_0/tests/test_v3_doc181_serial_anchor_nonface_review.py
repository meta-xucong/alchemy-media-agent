from __future__ import annotations

from alchemy_creative_agent_3_0.app.shared_capabilities.visual_cluster.vision_provider import (
    _professional_serial_anchor_review_context,
)


def test_doc181_rear_head_review_uses_nonface_continuity_evidence() -> None:
    context = _professional_serial_anchor_review_context(
        {
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "rear_head",
        },
        {"professional_identity_quality": {"applies": True}},
        reference_count=3,
    )

    assert context["target_view_role"] == "rear_head"
    assert context["target_face_visibility"] == "not_expected"
    assert context["prior_winner_count"] == 4
    assert context["reviewed_prior_anchor_image_indexes"] == [3, 4]
    assert context["current_brain_direction_authoritative"] is True


def test_doc181_serial_anchor_context_still_requires_frozen_contract() -> None:
    context = _professional_serial_anchor_review_context(
        {
            "professional_identity_reference_strategy": "serial_anchor_pack_root_reuse_v1",
            "professional_reference_stage": "rear_head",
        },
        {"professional_identity_quality": {"applies": False}},
        reference_count=3,
    )

    assert context == {}
