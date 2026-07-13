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

        required = self._nonhuman_identity_requirements(context, controls)
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
            requested_image_count=len(output.shot_specs),
            execution_plan=self._execution_plan(context, output, binding),
            safe_summary={
                "scenario_id": "photography",
                "scene_domain": output.brief.scene_domain.value,
                "commission_intent": output.brief.commission_intent.value,
                "delivery_roles": list(output.brief.delivery_roles),
                "profile_binding_mode": str(binding.get("binding_mode") or "general"),
                "named_profile_binding_present": str(binding.get("binding_mode") or "") == "named",
                "shared_execution_only": True,
                "required_capability_ids": required,
                "delivery_mode": controls.delivery_mode.value,
            },
            metadata={
                "contract_version": "photography_llm_first_mainline_005_v1",
                "planner_output_id": output.brief.brief_id,
                "planning_fingerprint": contribution.metadata.get("planning_fingerprint"),
                "source": self.planner_id,
                "direct_provider_call": False,
                "owns_visual_review": False,
                "owns_retry": False,
                "owns_result_selection": False,
                # Legacy P6 continuation validation still reads this opaque
                # record.  It is never a provider prompt source, capability
                # contribution, or substitute for a remote creative result.
                "photography_pack_output": output.model_dump(mode="json"),
                "photography_pack_output_use": "continuation_validation_only",
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
            "delivery_mode": (
                "professional_set"
                if context.selected_mode_id == "professional_set"
                else "single_hero"
            ),
            "reshoot_strength": params.get("reshoot_strength"),
            "explicit_scene_id": params.get("scene_domain") or params.get("explicit_scene_id"),
            "preservation_controls": dict(params.get("preservation_controls") or {}),
            "aspect_ratio": params.get("aspect_ratio"),
            # The profile lives exclusively in the immutable mainline binding.
            "output_count": 3 if context.selected_mode_id == "professional_set" else 1,
        }
        return PhotographyUserControls.model_validate(controls)

    def _execution_plan(self, context, output, binding: dict[str, Any]) -> dict[str, Any]:
        """Translate frozen Photography roles into a non-creative ledger.

        The specialized template owns only role cardinality, immutable profile
        provenance, reference/safety boundaries, and append-only lineage.  It
        must not materialize a local scene, camera, crop, lighting, pose, or
        visual recipe: the remote Central Brain binds that direction later in
        the TemplateDeliverablePlan.
        """

        is_set = output.professional_set_plan is not None
        role_recipes = []
        for shot in output.shot_specs:
            role_recipes.append(
                {
                    "role_id": shot.shot_id,
                    "index": shot.sequence_index,
                    "role_key": shot.role,
                    "label": shot.role.replace("_", " ").title(),
                    "purpose": "",
                    "shot_family": "frozen photography delivery role",
                    "variation_axes": [],
                    "must_keep_rules": [
                        "preserve the frozen photographer profile checksum and shared color/finish anchor",
                    ],
                    "must_not_rules": [],
                    "prompt_pressure": "",
                    "negative_pressure": [],
                    "review_checks": [],
                    "user_visible_summary": [],
                    "metadata": {
                        "owner": "photography_scenario_pack",
                        "photography_role": shot.role,
                        "photography_shot_id": shot.shot_id,
                        "photography_profile_checksum": binding.get("technique_package_checksum"),
                        "creative_direction_owner": "remote_v3_llm_brain",
                        "frozen_contract_only": True,
                        "static_recipe_present": False,
                    },
                }
            )
        set_plan = output.professional_set_plan
        role_order = list(set_plan.role_order) if set_plan is not None else [shot.role for shot in output.shot_specs]
        return {
            "plan_id": stable_id(
                "specialized_photography_role_execution",
                context.job_key,
                set_plan.set_id if set_plan is not None else output.brief.brief_id,
                *[item["role_id"] for item in role_recipes],
            ),
            "project_id": str(context.project_context_snapshot.get("project_id") or "") or None,
            "job_id": context.job_key,
            "mode": "delivery_suite" if is_set else "single_hero",
            "subject_type": output.brief.scene_domain.value,
            "requested_image_count": len(role_recipes),
            "policy": {
                "policy_id": stable_id("photography_role_execution_policy", context.job_key, is_set),
                "mode": "delivery_suite" if is_set else "single_hero",
                "mode_meaning": "frozen professional photography role set" if is_set else "one professional photography hero",
                "visual_distance_budget": "purposeful_professional_variation" if is_set else "single_frame",
                "anchor_strength": "frozen_profile_color_and_reference_truth",
                "scene_change_allowed": bool(is_set),
                "role_strategy": "photography_professional_roles",
                "role_difference_requirement": "each output must remain bound to its own frozen Photography role ID",
                "review_priority": "role coverage, profile fidelity, reference truth, real-pixel quality",
                # A text-to-image professional set has no user-supplied
                # identity evidence to turn into an image-edit chain.  The
                # shared executor must therefore render each frozen role as
                # its own T2I request.  When the user has supplied reference
                # evidence, that evidence remains the only provider input.
                # This is deliberately an execution-neutral policy signal,
                # not a Photography-owned provider route.
                "generated_output_reference_chain": "explicit_references_only",
                "user_visible_label": "Professional photography set" if is_set else "Professional photograph",
                "user_visible_summary": [],
                "metadata": {"owner": "shared_runtime", "scenario_id": "photography"},
            },
            "role_recipes": role_recipes,
            "prompt_additions": [],
            "negative_additions": [],
            "user_visible_summary": [
                "Prepared frozen professional photography role directions for shared execution."
            ],
            "metadata": {
                "owner": "photography_scenario_pack",
                "scenario_id": "photography",
                "execution_owner": "shared_generation_review_retry",
                "creative_direction_owner": "remote_v3_llm_brain",
                "frozen_contract_only": True,
                "professional_set": is_set,
                "photography_set_id": set_plan.set_id if set_plan is not None else None,
                "role_order": role_order,
                "profile_binding_snapshot": (
                    dict(set_plan.profile_binding_snapshot)
                    if set_plan is not None
                    else {
                        "profile_id": binding.get("profile_id"),
                        "profile_version": binding.get("profile_version"),
                        "technique_package_checksum": binding.get("technique_package_checksum"),
                    }
                ),
                "coherence_contract": dict(set_plan.coherence_contract) if set_plan is not None else {},
                "selection_contract": dict(set_plan.selection_contract) if set_plan is not None else {},
                "delivery_package": dict(set_plan.delivery_package) if set_plan is not None else {},
                "direct_provider_call": False,
                "owns_visual_review": False,
                "owns_retry": False,
                "owns_result_selection": False,
                # Central Brain may continue independently after one role's
                # provider failure so the shared Product API can record every
                # role's terminal state and withhold an incomplete set from
                # normal project delivery.
                "require_independent_role_terminal_states": True,
                "requires_real_pixel_review": True,
            },
        }

    def _nonhuman_identity_requirements(
        self,
        context: SpecializedScenarioPlanningContext,
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
            controls.input_mode.value == "reference_to_professional_reshoot"
            and any(marker in context.user_input.lower() for marker in ("same pet", "same animal", "same dog", "same cat", "this pet", "this animal"))
        )
        if not needs_identity:
            return []
        if not typed:
            raise SpecializedScenarioPlanningError("nonhuman_identity_reference_required_for_photography_identity_request")
        if not any(asset.file_path or asset.uri for asset in typed):
            raise SpecializedScenarioPlanningError("nonhuman_identity_reference_unavailable_for_native_high_fidelity")
        return ["nonhuman_subject_identity"]

    def _direction_contribution(self, context, output, binding: dict[str, Any]) -> CapabilityContribution:
        """Keep a validator contribution without local art-direction prose."""

        fingerprint = stable_id(
            "photography_direction",
            context.job_key,
            output.brief.brief_id,
            binding.get("profile_id"),
            binding.get("profile_version"),
            binding.get("technique_package_checksum"),
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
                "creative_direction_owner": "remote_v3_llm_brain",
                "frozen_contract_only": True,
            },
            prompt_additions=[],
            negative_additions=[],
            provider_input_requirements=[],
            review_contract={
                "owner": "shared_visual_review",
                "planning_expectations_only": True,
                "issue_codes": [],
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
                "creative_direction_owner": "remote_v3_llm_brain",
                "static_recipe_present": False,
                "direct_provider_call": False,
                "shared_execution_only": True,
            },
        )
