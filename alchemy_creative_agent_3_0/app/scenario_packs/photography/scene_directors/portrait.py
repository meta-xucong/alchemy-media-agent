"""Portrait-specific Photography direction."""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographySceneDomain
from .base import PhotographySceneDirector


class PortraitPhotographyDirector(PhotographySceneDirector):
    scene_domain = PhotographySceneDomain.PORTRAIT
    capability_id = "portrait_photography_direction"
    foundation_capabilities_reused = (
        "reference_channel_policy",
        "human_realism",
        "portrait_identity",
    )

    def _build(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        activation_plan_id: str,
    ) -> CapabilityContribution:
        return self.contribution(
            activation_plan_id=activation_plan_id,
            facts={
                "decisive_moment": (
                    "expression, posture and environmental relation create a credible portrait moment"
                ),
                "framing": (
                    "face, body, hands and environment are framed with intentional portrait hierarchy"
                ),
                "subject_direction": (
                    "direct an alive expression and purposeful posture without a frozen mannequin pose"
                ),
                "material_realism": (
                    "portrait acceptance delegates skin, hair and anatomy realism to Human Realism"
                ),
                "reference_ownership": (
                    "declared person identity remains immutable; hair, makeup, wardrobe, lighting and style "
                    "remain prompt-owned unless explicitly preserved"
                ),
                "profile_binding_id": profile_binding.profile_id,
            },
            prompt_additions=[
                "Direct an alive expression and purposeful posture suited to the requested portrait use.",
                "Frame face, body, hands and environment with intentional portrait hierarchy.",
                "Preserve only declared identity truth; keep prompt-owned styling channels changeable.",
            ],
            negative_additions=[
                "frozen mannequin pose or empty expression",
                "accidental crop through expression-critical face, hands or body language",
                "silent inheritance of source hair, makeup, wardrobe, lighting or style",
            ],
            issue_codes=[
                "portrait_expression_pose_direction_error",
                "portrait_face_body_framing_error",
                "portrait_reference_identity_contract_error",
            ],
        )
