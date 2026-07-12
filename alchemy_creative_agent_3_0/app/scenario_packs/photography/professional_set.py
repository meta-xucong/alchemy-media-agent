"""Photography-owned professional-set roles and packaging intent."""

from __future__ import annotations

from itertools import combinations

from ...creative_core.rules import stable_id
from .contracts import (
    PhotographerProfileBinding,
    PhotoShotSpec,
    PhotographyBrief,
    PhotographyProfessionalSetPlan,
)


PROFESSIONAL_SET_ROLE_ORDER = [
    "session_hero",
    "environmental_context",
    "detail_or_moment",
]


class PhotographyProfessionalSetDirector:
    """Freeze one coherent set plan without selecting or rendering pixels."""

    def build(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        shot_specs: list[PhotoShotSpec],
        job_key: str,
    ) -> PhotographyProfessionalSetPlan:
        role_order = [shot.role for shot in shot_specs]
        if role_order != PROFESSIONAL_SET_ROLE_ORDER:
            raise ValueError("photography_professional_set_role_contract_mismatch")
        if any(len(shot.metadata.get("differentiated_dimensions") or []) < 2 for shot in shot_specs):
            raise ValueError("photography_professional_set_requires_meaningful_role_differentiation")
        differentiation_fields = (
            "framing_and_crop",
            "camera_position_and_perspective_effect",
            "subject_and_decisive_moment",
            "depth_and_focus_behavior",
            "motion_behavior",
        )
        for left, right in combinations(shot_specs, 2):
            changed = sum(
                getattr(left, field) != getattr(right, field)
                for field in differentiation_fields
            )
            if changed < 2:
                raise ValueError("photography_professional_set_requires_meaningful_role_differentiation")
        palette_anchors = {shot.palette_and_tone_curve for shot in shot_specs}
        profile_checksums = {shot.metadata.get("profile_binding_checksum") for shot in shot_specs}
        immutable_truth = {tuple(shot.immutable_reference_truth) for shot in shot_specs}
        if len(palette_anchors) != 1 or profile_checksums != {profile_binding.technique_package_checksum}:
            raise ValueError("photography_professional_set_coherence_contract_mismatch")
        if len(immutable_truth) != 1:
            raise ValueError("photography_professional_set_reference_truth_drift")

        binding_snapshot = {
            "binding_mode": profile_binding.binding_mode,
            "profile_id": profile_binding.profile_id,
            "profile_version": profile_binding.profile_version,
            "catalog_version": profile_binding.catalog_version,
            "technique_package_checksum": profile_binding.technique_package_checksum,
            "selection_source": (
                profile_binding.selection_source.value
                if profile_binding.selection_source is not None
                else None
            ),
        }
        set_id = stable_id(
            "photography_professional_set",
            job_key,
            brief.brief_id,
            profile_binding.profile_id,
            profile_binding.technique_package_checksum,
            *[shot.shot_id for shot in shot_specs],
        )
        return PhotographyProfessionalSetPlan(
            set_id=set_id,
            role_order=role_order,
            shot_ids_by_role={shot.role: shot.shot_id for shot in shot_specs},
            profile_binding_snapshot=binding_snapshot,
            coherence_contract={
                "profile_binding_checksum": profile_binding.technique_package_checksum,
                "profile_binding_locked_across_roles": True,
                "color_and_finish_anchor": next(iter(palette_anchors)),
                "color_and_finish_locked_across_roles": True,
                "immutable_reference_truth": list(next(iter(immutable_truth))),
                "reference_truth_locked_across_roles": True,
                "role_variation_must_not_mutate_identity_truth": True,
            },
            selection_contract={
                "owner": "shared_final_delivery_resolver",
                "candidate_scope": "all_append_only_attempts_grouped_by_photography_role",
                "newest_attempt_is_automatically_best": False,
                "one_final_winner_per_role": True,
                "retry_superseded_attempts_folded_in_history": True,
            },
            delivery_package={
                "owner": "photography_scenario_pack",
                "role_order": role_order,
                "requested_delivery_count": len(role_order),
                "beginner_surface": "final_role_winners_only",
                "excludes_ecommerce_listing_roles": True,
                "excludes_campaign_or_storyboard_packaging": True,
            },
            metadata={
                "source": "PhotographyProfessionalSetDirector",
                "phase": "P6_professional_set_planning",
                "planning_only": True,
                "direct_provider_call": False,
                "owns_visual_review": False,
                "owns_retry": False,
                "owns_result_selection": False,
                "shared_execution_required": True,
            },
        )
