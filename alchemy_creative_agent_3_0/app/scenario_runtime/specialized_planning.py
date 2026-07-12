"""Mainline adapters for specialized Scenario Pack planning contributions.

This boundary deliberately has no provider, image-review, retry, selection, or
result-resolution dependency.  Specialized packs may describe a professional
direction; the shared runtime remains the only execution owner.
"""

from __future__ import annotations

from typing import Any, Protocol

from ..creative_core.rules import stable_id
from ..scenario_packs.photography import (
    PhotographyScenarioPackPlanner,
    PhotographySceneDomain,
    PhotographyUserControls,
)
from ..shared_capabilities import AssetRole
from ..shared_capabilities.activation import CapabilityContribution
from .contracts import SpecializedScenarioPlanningContext, SpecializedScenarioPlanningResult


PHOTOGRAPHY_DIRECTION_CAPABILITY_ID = "photography_direction"


class SpecializedScenarioPlanningError(ValueError):
    """A safe pre-generation block from an active specialized planner."""


class SpecializedScenarioPlanningAdapter(Protocol):
    scenario_id: str

    def plan(self, context: SpecializedScenarioPlanningContext) -> SpecializedScenarioPlanningResult:
        """Return frozen planning facts; never run a provider or a visual retry."""


class PhotographyScenarioPlanningAdapter:
    """Project the isolated Photography planner into the shared runtime.

    ``plan_from_pinned_binding`` is intentionally the only Photography entry.
    Browser/API profile selection happened earlier in ``V3ProductApiService``;
    this adapter merely consumes that immutable snapshot.
    """

    scenario_id = "photography"
    planner_id = "photography_scenario_pack"

    def __init__(self, planner: PhotographyScenarioPackPlanner | None = None) -> None:
        self.planner = planner or PhotographyScenarioPackPlanner(named_profiles_enabled=True)

    def plan(self, context: SpecializedScenarioPlanningContext) -> SpecializedScenarioPlanningResult:
        binding = context.photographer_profile_binding
        if not isinstance(binding, dict):
            raise SpecializedScenarioPlanningError("photography_requires_mainline_profile_binding")
        controls = self._controls(context)
        try:
            output = self.planner.plan_from_pinned_binding(
                user_input=context.user_input,
                profile_binding=binding,
                controls=controls,
                uploaded_asset_ids=[asset.asset_id for asset in context.uploaded_assets],
                job_key=context.job_key,
            )
        except ValueError as exc:
            # A stale named binding must fail closed.  It is never silently
            # swapped for General Photography or reselected by the planner.
            raise SpecializedScenarioPlanningError(str(exc)) from exc

        required = self._nonhuman_identity_requirements(context, output.brief.scene_domain, controls)
        contribution = self._direction_contribution(context, output, binding)
        return SpecializedScenarioPlanningResult(
            planning_id=stable_id(
                "photography_specialized_plan",
                context.job_key,
                contribution.metadata.get("planning_fingerprint"),
            ),
            scenario_id=context.scenario_resolution.manifest.scenario_id,
            template_id="photographer_template",
            planner_id=self.planner_id,
            capability_contribution_draft=contribution,
            required_capability_ids=required,
            requested_image_count=1,
            safe_summary={
                "scenario_id": "photography",
                "scene_domain": output.brief.scene_domain.value,
                "commission_intent": output.brief.commission_intent.value,
                "delivery_roles": list(output.brief.delivery_roles),
                "profile_binding_mode": str(binding.get("binding_mode") or "general"),
                "named_profile_binding_present": str(binding.get("binding_mode") or "") == "named",
                "shared_execution_only": True,
                "required_capability_ids": required,
            },
            metadata={
                "contract_version": "photography_mainline_003_v1",
                "planner_output_id": output.brief.brief_id,
                "planning_fingerprint": contribution.metadata.get("planning_fingerprint"),
                "source": self.planner_id,
                "direct_provider_call": False,
                "owns_visual_review": False,
                "owns_retry": False,
                "owns_result_selection": False,
            },
        )

    def _controls(self, context: SpecializedScenarioPlanningContext) -> PhotographyUserControls:
        parameters = context.metadata.get("scenario_parameters")
        params = dict(parameters) if isinstance(parameters, dict) else {}
        input_mode = params.get("input_mode")
        if context.selected_mode_id == "reference_reshoot":
            input_mode = "reference_to_professional_reshoot"
        controls = {
            "input_mode": input_mode or "text_to_photo",
            "delivery_mode": "single_hero",
            "reshoot_strength": params.get("reshoot_strength"),
            "explicit_scene_id": params.get("scene_domain") or params.get("explicit_scene_id"),
            "preservation_controls": dict(params.get("preservation_controls") or {}),
            "aspect_ratio": params.get("aspect_ratio"),
            # The profile lives exclusively in the immutable mainline binding.
            "output_count": 1,
        }
        return PhotographyUserControls.model_validate(controls)

    def _nonhuman_identity_requirements(
        self,
        context: SpecializedScenarioPlanningContext,
        scene_domain: PhotographySceneDomain,
        controls: PhotographyUserControls,
    ) -> list[str]:
        typed = [
            asset
            for asset in context.uploaded_assets
            if str(asset.role or "") == AssetRole.NONHUMAN_IDENTITY_REFERENCE.value
        ]
        parameters = context.metadata.get("scenario_parameters")
        params = dict(parameters) if isinstance(parameters, dict) else {}
        explicit_identity_request = bool(params.get("preserve_nonhuman_identity")) or any(
            marker in context.user_input.lower()
            for marker in ("same pet", "same animal", "same dog", "same cat", "this pet", "this animal")
        )
        needs_identity = bool(typed) or explicit_identity_request or (
            scene_domain == PhotographySceneDomain.ANIMAL
            and controls.input_mode.value == "reference_to_professional_reshoot"
        )
        if not needs_identity:
            return []
        if not typed:
            raise SpecializedScenarioPlanningError("nonhuman_identity_reference_required_for_photography_identity_request")
        if not any(asset.file_path or asset.uri for asset in typed):
            raise SpecializedScenarioPlanningError("nonhuman_identity_reference_unavailable_for_native_high_fidelity")
        return ["nonhuman_subject_identity"]

    def _direction_contribution(self, context, output, binding: dict[str, Any]) -> CapabilityContribution:
        planned = [*output.technique_contributions, *output.scene_contributions]
        prompt_additions = _dedupe(
            value for contribution in planned for value in contribution.prompt_additions
        )
        negative_additions = _dedupe(
            value for contribution in planned for value in contribution.negative_additions
        )
        issue_codes = _dedupe(
            value
            for contribution in planned
            for value in contribution.review_contract.get("issue_codes", [])
        )
        fingerprint = stable_id(
            "photography_direction",
            context.job_key,
            output.brief.brief_id,
            binding.get("profile_id"),
            binding.get("profile_version"),
            binding.get("technique_package_checksum"),
            *prompt_additions,
            *negative_additions,
        )
        return CapabilityContribution(
            capability_id=PHOTOGRAPHY_DIRECTION_CAPABILITY_ID,
            capability_version="v1",
            activation_plan_id="pending_mainline_activation_plan",
            facts={
                "scene_domain": output.brief.scene_domain.value,
                "commission_intent": output.brief.commission_intent.value,
                "delivery_roles": list(output.brief.delivery_roles),
                "reference_policy": dict(output.brief.reference_policy_summary),
            },
            prompt_additions=prompt_additions,
            negative_additions=negative_additions,
            provider_input_requirements=[],
            review_contract={
                "owner": "shared_visual_review",
                "planning_expectations_only": True,
                "issue_codes": issue_codes,
                "named_profile_fidelity_active": str(binding.get("binding_mode") or "") == "named",
            },
            retry_contract={
                "owner": "shared_visual_retry",
                "retry_must_preserve_profile_binding": True,
                "retry_must_preserve_reference_truth": True,
                "retry_may_not_switch_named_profile": str(binding.get("binding_mode") or "") == "named",
            },
            stages=["creative_strategy", "generation_prompt", "negative_prompt", "post_generation_review", "retry_patch"],
            metadata={
                "owner": "photography_scenario_pack",
                "planning_fingerprint": fingerprint,
                "profile_binding_checksum": binding.get("technique_package_checksum"),
                "profile_name_in_prompt": False,
                "direct_provider_call": False,
                "shared_execution_only": True,
            },
        )


def _dedupe(values) -> list[str]:
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))
