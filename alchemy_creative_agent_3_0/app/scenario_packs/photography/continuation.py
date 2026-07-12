"""Photography-owned continuation validation before shared Project Mode integration."""

from __future__ import annotations

from ...creative_core.rules import stable_id
from .contracts import (
    PhotographerProfileBinding,
    PhotographerProfileSelectionSource,
    PhotographyPackOutput,
    PhotographySetContinuationPlan,
    PhotographySetContinuationRequest,
)


class PhotographySetContinuationDirector:
    """Preserve one set/profile contract; never create a private retry path."""

    def plan(
        self,
        *,
        parent_output: PhotographyPackOutput,
        profile_binding: PhotographerProfileBinding,
        request: PhotographySetContinuationRequest,
        job_key: str,
    ) -> PhotographySetContinuationPlan:
        set_plan = parent_output.professional_set_plan
        if set_plan is None:
            raise ValueError("photography_set_continuation_requires_professional_set_parent")
        expected_shot_id = set_plan.shot_ids_by_role.get(request.target_role)
        if expected_shot_id is None or expected_shot_id != request.parent_shot_id:
            raise ValueError("photography_set_continuation_parent_role_mismatch")
        self._validate_profile_reconfirmation(profile_binding, set_plan.profile_binding_snapshot, request)
        parent_shot = next(
            (shot for shot in parent_output.shot_specs if shot.shot_id == request.parent_shot_id),
            None,
        )
        if parent_shot is None:
            raise ValueError("photography_set_continuation_parent_shot_missing")

        return PhotographySetContinuationPlan(
            continuation_id=stable_id(
                "photography_set_continuation",
                job_key,
                set_plan.set_id,
                request.parent_shot_id,
                request.target_role,
                request.correction_note,
                *request.new_reference_asset_ids,
            ),
            root_set_id=set_plan.set_id,
            parent_shot_id=request.parent_shot_id,
            target_role=request.target_role,
            correction_note=request.correction_note,
            new_reference_asset_ids=list(request.new_reference_asset_ids),
            profile_binding_snapshot=dict(set_plan.profile_binding_snapshot),
            immutable_reference_truth=list(parent_shot.immutable_reference_truth),
            coherence_contract=dict(set_plan.coherence_contract),
            metadata={
                "source": "PhotographySetContinuationDirector",
                "phase": "P6_continuation_planning",
                "append_only_child_required": True,
                "changes_profile_binding": False,
                "new_evidence_requires_shared_capability_revalidation": bool(
                    request.new_reference_asset_ids
                ),
                "shared_generation_only": True,
                "shared_review_only": True,
                "shared_retry_only": True,
                "shared_final_delivery_only": True,
                "direct_provider_call": False,
            },
        )

    def _validate_profile_reconfirmation(
        self,
        binding: PhotographerProfileBinding,
        snapshot: dict,
        request: PhotographySetContinuationRequest,
    ) -> None:
        expected = (
            binding.profile_id,
            binding.profile_version,
            binding.technique_package_checksum,
        )
        frozen = (
            snapshot.get("profile_id"),
            snapshot.get("profile_version"),
            snapshot.get("technique_package_checksum"),
        )
        if expected != frozen:
            raise ValueError("photography_continuation_profile_binding_mismatch")
        if binding.binding_mode == "named":
            if request.profile_selection_source != PhotographerProfileSelectionSource.USER_EXPLICIT_UI:
                raise ValueError("named_profile_continuation_requires_explicit_ui_reconfirmation")
            reconfirmed = (
                request.reconfirmed_profile_id,
                request.reconfirmed_profile_version,
                request.reconfirmed_technique_package_checksum,
            )
            if reconfirmed != expected:
                raise ValueError("photography_continuation_profile_binding_mismatch")
            return
        if request.profile_selection_source is not None:
            raise ValueError("general_photography_continuation_must_not_carry_named_selection_source")
        supplied = (
            request.reconfirmed_profile_id,
            request.reconfirmed_profile_version,
            request.reconfirmed_technique_package_checksum,
        )
        if any(value is not None for value in supplied) and supplied != expected:
            raise ValueError("photography_continuation_profile_binding_mismatch")
