"""Compile an explicitly pinned named profile into observable technique facts.

The compiler intentionally receives a pre-resolved binding.  It cannot choose
or substitute a photographer profile, and it does not insert a photographer's
name into a rendering prompt.
"""

from __future__ import annotations

from ....shared_capabilities.activation import CapabilityContribution
from ..contracts import PhotographerProfileBinding, PhotographyBrief, PhotographyTechniquePackage
from ..profile_catalog import PhotographerProfileCatalog


_TECHNIQUE_FIELDS = (
    "composition",
    "camera_relation",
    "depth_and_focus",
    "motion_treatment",
    "lighting",
    "exposure_and_tone",
    "color_response",
    "texture_and_grain",
    "subject_direction",
    "retouch_finish",
)

_REFERENCE_LOCK_TO_TECHNIQUE_FIELDS = {
    "composition": {"composition"},
    "camera": {"camera_relation", "depth_and_focus", "motion_treatment"},
    "lighting": {"lighting", "exposure_and_tone"},
    "color": {"color_response"},
    "finish": {"texture_and_grain", "retouch_finish"},
}


class NamedPhotographerTechniqueCompiler:
    """Compile only the exact, explicitly selected operator-reviewed record."""

    capability_id = "photography_named_profile_technique"

    def build_contribution(
        self,
        *,
        brief: PhotographyBrief,
        profile_binding: PhotographerProfileBinding,
        profile_catalog: PhotographerProfileCatalog,
        activation_plan_id: str,
    ) -> CapabilityContribution:
        if profile_binding.binding_mode != "named":
            raise ValueError("named_profile_technique_requires_named_binding")
        profile = profile_catalog.resolve_pinned_profile(profile_binding)
        constrained_fields = self._constrained_fields(brief)
        applied = {
            name: list(getattr(profile.technique_package, name))
            for name in _TECHNIQUE_FIELDS
            if name not in constrained_fields and getattr(profile.technique_package, name)
        }
        constrained = {
            name: list(getattr(profile.technique_package, name))
            for name in _TECHNIQUE_FIELDS
            if name in constrained_fields and getattr(profile.technique_package, name)
        }
        prompt_additions = [
            technique
            for name in _TECHNIQUE_FIELDS
            for technique in applied.get(name, [])
        ]
        return CapabilityContribution(
            capability_id=self.capability_id,
            capability_version="p5-named-profile-v1",
            activation_plan_id=activation_plan_id,
            facts={
                "profile_id": profile_binding.profile_id,
                "profile_version": profile_binding.profile_version,
                "technique_package_checksum": profile_binding.technique_package_checksum,
                "applied_technique_fields": sorted(applied),
                "constrained_technique_fields": sorted(constrained),
                "reference_truth_precedence": bool(constrained),
            },
            prompt_additions=prompt_additions,
            negative_additions=list(profile.technique_package.forbidden_techniques),
            provider_input_requirements=[],
            review_contract={
                "issue_codes": [
                    "named_profile_technique_underapplied",
                    "named_profile_technique_overapplied",
                    "named_profile_overrode_reference_truth",
                ],
                "named_profile_fidelity_active": True,
                "declared_dimensions": sorted(applied),
                "metadata_only": True,
            },
            retry_contract={
                "retry_must_preserve_profile_binding": True,
                "retry_must_preserve_reference_truth": True,
                "retry_may_not_switch_named_profile": True,
            },
            stages=["technique_compilation", "shot_planning", "review_profile"],
            metadata={
                "owner": "photography_module",
                "phase": "P5_named_profile_shadow_runtime",
                "direct_provider_call": False,
                "profile_selected_by": "user_explicit_ui",
                "profile_name_in_prompt": False,
            },
        )

    def _constrained_fields(self, brief: PhotographyBrief) -> set[str]:
        controls = brief.reference_policy_summary.get("preservation_controls", {})
        if not isinstance(controls, dict):
            return set()
        locked_channels = {
            str(channel).strip().lower()
            for channel, value in controls.items()
            if str(value).strip().lower() in {"preserve", "lock", "required"}
        }
        return {
            technique_field
            for channel, technique_fields in _REFERENCE_LOCK_TO_TECHNIQUE_FIELDS.items()
            if channel in locked_channels
            for technique_field in technique_fields
        }
