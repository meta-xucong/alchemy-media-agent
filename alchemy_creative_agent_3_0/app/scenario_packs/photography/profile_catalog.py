"""Operator-reviewed Photography profile records and shared-catalog projection.

This module owns the technique packages that a Photography release may use.
It never becomes a second public selection authority: browser/API selection and
immutable job binding are owned by :mod:`app.photography_profiles`.
"""

from __future__ import annotations

import hashlib
import json

from .contracts import (
    GENERAL_PHOTOGRAPHY_PROFILE_ID,
    PhotographerProfile,
    PhotographerProfileAvailability,
    PhotographerProfileBinding,
    PhotographerProfileKind,
    PhotographerProfileRightsStatus,
    PhotographerProfileSelectionSource,
    PhotographyTechniquePackage,
    PhotographyUserControls,
)


GENERAL_PHOTOGRAPHY_PROFILE = PhotographerProfile(
    profile_id=GENERAL_PHOTOGRAPHY_PROFILE_ID,
    profile_version="p1-v1",
    profile_kind=PhotographerProfileKind.GENERAL,
    public_display_name="General Photography",
    public_description="Scene-appropriate professional photography without a named photographer identity.",
    supported_scene_ids=["portrait", "landscape", "still_life", "animal"],
    supported_commission_ids=["single_hero", "professional_session", "reference_reshoot"],
    technique_package=PhotographyTechniquePackage(
        metadata={
            "selection_policy": "scene_and_commission_modules_only",
            "contains_named_photographer_identity": False,
        }
    ),
    rights_status=PhotographerProfileRightsStatus.NOT_APPLICABLE,
    availability_status=PhotographerProfileAvailability.ACTIVE,
    metadata={
        "default": True,
        "named_profile": False,
        "production_activation_ready": False,
    },
)


class PhotographerProfileCatalog:
    """Trusted profile records without global registration or runtime side effects."""

    def __init__(
        self,
        profiles: list[PhotographerProfile] | None = None,
        *,
        catalog_version: str = "photography-p1-inactive-v1",
    ) -> None:
        self.catalog_version = catalog_version
        self._profiles: dict[str, PhotographerProfile] = {}
        self.register(GENERAL_PHOTOGRAPHY_PROFILE)
        for profile in profiles or []:
            self.register(profile)

    def register(self, profile: PhotographerProfile) -> None:
        if profile.profile_id in self._profiles:
            raise ValueError(f"photographer profile already registered: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> PhotographerProfile | None:
        return self._profiles.get(profile_id)

    def list_profiles(self) -> list[PhotographerProfile]:
        return [self._profiles[key] for key in sorted(self._profiles)]

    def selectable_named_profiles(self) -> list[PhotographerProfile]:
        return [
            profile
            for profile in self.list_profiles()
            if profile.profile_kind == PhotographerProfileKind.NAMED_PHOTOGRAPHER
            and profile.availability_status == PhotographerProfileAvailability.ACTIVE
            and profile.rights_status
            in {
                PhotographerProfileRightsStatus.APPROVED,
                PhotographerProfileRightsStatus.APPROVED_WITH_CONSTRAINTS,
            }
        ]

    def shared_catalog(self):
        """Project approved named records onto the foundation-owned API catalog.

        A composition root may pass the returned catalog to
        ``V3ProductApiService``.  The public route then remains the sole source
        for the frontend; this method does not register a global catalog or
        activate the Photography Scenario Pack by import side effect.
        """
        from ...photography_profiles import (
            PhotographerProfileCatalog as SharedPhotographerProfileCatalog,
            PhotographerProfileDefinition,
        )

        return SharedPhotographerProfileCatalog(
            [
                PhotographerProfileDefinition(
                    profile_id=profile.profile_id,
                    display_name=profile.public_display_name,
                    profile_version=profile.profile_version,
                    availability="available",
                    allowed_regions=profile.allowed_regions,
                    technique_package_checksum=self.technique_package_checksum(profile),
                )
                for profile in self.selectable_named_profiles()
            ]
        )

    def resolve_pinned_profile(self, binding: PhotographerProfileBinding) -> PhotographerProfile:
        """Load the exact local technique record represented by a frozen binding."""
        profile = self.get(binding.profile_id)
        if profile is None:
            raise ValueError("named_profile_binding_mismatch:profile_not_in_operator_catalog")
        if binding.binding_mode == "general":
            if profile.profile_id != GENERAL_PHOTOGRAPHY_PROFILE_ID:
                raise ValueError("named_profile_binding_mismatch:general_profile_id")
            return profile
        if profile.profile_kind != PhotographerProfileKind.NAMED_PHOTOGRAPHER:
            raise ValueError("named_profile_binding_mismatch:not_named_profile")
        if binding.selection_source != PhotographerProfileSelectionSource.USER_EXPLICIT_UI:
            raise ValueError("named_profile_not_explicitly_selected")
        if binding.profile_version != profile.profile_version:
            raise ValueError("named_profile_binding_mismatch:version")
        if binding.technique_package_checksum != self.technique_package_checksum(profile):
            raise ValueError("named_profile_binding_mismatch:technique_checksum")
        return profile

    def resolve_binding(self, controls: PhotographyUserControls) -> PhotographerProfileBinding:
        requested_id = controls.photographer_profile_id
        if requested_id in {None, GENERAL_PHOTOGRAPHY_PROFILE_ID}:
            return self._binding(GENERAL_PHOTOGRAPHY_PROFILE, selection_source=None, binding_mode="general")

        if controls.photographer_profile_selection_source != PhotographerProfileSelectionSource.USER_EXPLICIT_UI:
            raise ValueError("named_profile_requires_explicit_ui_selection")

        profile = self.get(requested_id)
        if profile is None or profile.profile_kind != PhotographerProfileKind.NAMED_PHOTOGRAPHER:
            raise ValueError("named_profile_unavailable")
        if profile.availability_status != PhotographerProfileAvailability.ACTIVE:
            raise ValueError(f"named_profile_unavailable:{profile.availability_status.value}")
        if profile.rights_status not in {
            PhotographerProfileRightsStatus.APPROVED,
            PhotographerProfileRightsStatus.APPROVED_WITH_CONSTRAINTS,
        }:
            raise ValueError(f"named_profile_unavailable:{profile.rights_status.value}")

        return self._binding(
            profile,
            selection_source=PhotographerProfileSelectionSource.USER_EXPLICIT_UI,
            binding_mode="named",
        )

    def _binding(
        self,
        profile: PhotographerProfile,
        *,
        selection_source: PhotographerProfileSelectionSource | None,
        binding_mode: str,
    ) -> PhotographerProfileBinding:
        checksum = self.technique_package_checksum(profile)
        return PhotographerProfileBinding(
            binding_mode=binding_mode,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            selection_source=selection_source,
            catalog_version=self.catalog_version,
            availability_decision=profile.availability_status,
            technique_package_checksum=checksum,
            metadata={
                "profile_kind": profile.profile_kind.value,
                "selection_is_llm_authorized": False,
                "production_activation_ready": False,
            },
        )

    def technique_package_checksum(self, profile: PhotographerProfile) -> str:
        """Stable checksum used by both the shared binding and local compiler."""
        technique_payload = profile.technique_package.model_dump(mode="json")
        return hashlib.sha256(
            json.dumps(technique_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()


_default_operator_catalog = PhotographerProfileCatalog()


def default_photography_operator_catalog() -> PhotographerProfileCatalog:
    """Return the deployed operator-record source used by the default composition root.

    Deployments that offer named profiles must construct this catalog from their
    reviewed records before initializing the Product API.  Its shared catalog
    projection is the sole browser/API selection authority.
    """

    return _default_operator_catalog
