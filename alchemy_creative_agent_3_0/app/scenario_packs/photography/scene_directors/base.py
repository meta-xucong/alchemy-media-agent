"""Shared module-local primitives for Photography scene directors."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographySceneDomain


class PhotographySceneDirector(ABC):
    """Contribute scene-owned direction without activating a shared provider path."""

    scene_domain: PhotographySceneDomain
    capability_id: str
    foundation_capabilities_reused: tuple[str, ...] = ("reference_channel_policy",)

    def build_contribution(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        activation_plan_id: str,
    ) -> CapabilityContribution:
        if brief.scene_domain != self.scene_domain:
            raise ValueError(
                f"{self.capability_id} cannot contribute to {brief.scene_domain.value}"
            )
        return self._build(
            brief=brief,
            profile_binding=profile_binding,
            activation_plan_id=activation_plan_id,
        )

    @abstractmethod
    def _build(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        activation_plan_id: str,
    ) -> CapabilityContribution:
        raise NotImplementedError

    def contribution(
        self,
        *,
        activation_plan_id: str,
        facts: dict,
        prompt_additions: list[str],
        negative_additions: list[str],
        issue_codes: list[str],
    ) -> CapabilityContribution:
        return CapabilityContribution(
            capability_id=self.capability_id,
            capability_version="p4-scene-v1",
            activation_plan_id=activation_plan_id,
            facts={
                "scene_domain": self.scene_domain.value,
                "scene_owned_scope": True,
                "foundation_capabilities_reused": list(self.foundation_capabilities_reused),
                **facts,
            },
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            provider_input_requirements=[],
            review_contract={
                "issue_codes": issue_codes,
                "metadata_only": True,
                "scene_domain": self.scene_domain.value,
                "named_profile_fidelity_active": False,
            },
            retry_contract={
                "bounded_retry_owner": self.capability_id,
                "retry_must_preserve_profile_binding": True,
                "retry_must_preserve_reference_truth": True,
            },
            stages=["scene_direction", "shot_planning", "review_profile"],
            metadata={
                "owner": "photography_module",
                "phase": "P4_shadow_scene_directors",
                "direct_provider_call": False,
                "production_activation_ready": False,
                "contains_named_photographer_identity": False,
            },
        )
