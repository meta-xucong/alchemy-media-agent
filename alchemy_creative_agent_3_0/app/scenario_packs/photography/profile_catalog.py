"""Inactive, module-local photographer profile catalog."""

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
        technique_payload = profile.technique_package.model_dump(mode="json")
        checksum = hashlib.sha256(
            json.dumps(technique_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()
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
