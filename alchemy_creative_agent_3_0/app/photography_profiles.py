"""Trusted, server-owned photographer-profile selection contracts.

Named profiles are intentionally catalog records, not prompt aliases.  The
Photography scenario pack can register approved records later, while this
shared boundary remains responsible for validation and immutable pinning.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field, field_validator

from .creative_core.rules import stable_id
from .schemas.models import V3BaseModel


GENERAL_PHOTOGRAPHY_PROFILE_ID = "general_photography"
PhotographerSelectionSource = Literal["user_explicit_ui"]
PhotographerBindingMode = Literal["general", "named"]


class PhotographerProfileSelectionError(ValueError):
    """Structured public failure returned by the V3 route adapter."""

    def __init__(self, code: str, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.v3_status_code = status_code


class PhotographerProfileDefinition(V3BaseModel):
    """Approved catalog record. Rights-review internals never enter this model."""

    profile_id: str
    display_name: str
    profile_version: str
    availability: str = "available"
    allowed_regions: list[str] = Field(default_factory=list)
    technique_package_checksum: str

    @field_validator("profile_id", "display_name", "profile_version", "technique_package_checksum")
    @classmethod
    def non_empty_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("photographer profile fields must not be empty")
        return cleaned

    @field_validator("allowed_regions")
    @classmethod
    def normalized_regions(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip().upper() for item in value if item and item.strip()))

    @property
    def is_general(self) -> bool:
        return self.profile_id == GENERAL_PHOTOGRAPHY_PROFILE_ID


class PhotographerProfileBinding(V3BaseModel):
    """Exact immutable selection stored on a job and its continuation snapshot."""

    binding_mode: PhotographerBindingMode
    profile_id: str
    profile_display_name: str
    profile_version: str
    selection_source: PhotographerSelectionSource | None = None
    catalog_version: str
    availability_decision: str
    technique_package_checksum: str
    pinned_at: str


class PhotographerProfileCatalog:
    """Small catalog registry; the Photography module owns future named entries."""

    def __init__(self, profiles: list[PhotographerProfileDefinition] | None = None) -> None:
        general = PhotographerProfileDefinition(
            profile_id=GENERAL_PHOTOGRAPHY_PROFILE_ID,
            display_name="General Photography",
            profile_version="v1",
            technique_package_checksum="general-photography-v1",
        )
        records = [general, *(profiles or [])]
        self._profiles: dict[str, PhotographerProfileDefinition] = {}
        for profile in records:
            self.register(profile)

    @property
    def catalog_version(self) -> str:
        return stable_id(
            "photographer_profile_catalog",
            *[
                f"{item.profile_id}@{item.profile_version}:{item.availability}:{','.join(item.allowed_regions)}:{item.technique_package_checksum}"
                for item in sorted(self._profiles.values(), key=lambda entry: entry.profile_id)
            ],
        )

    def register(self, profile: PhotographerProfileDefinition) -> None:
        if profile.profile_id in self._profiles:
            raise ValueError(f"photographer profile already registered: {profile.profile_id}")
        self._profiles[profile.profile_id] = profile

    def public_catalog(self, *, region: str | None = None) -> dict:
        return {
            "catalog_version": self.catalog_version,
            "default_profile_id": GENERAL_PHOTOGRAPHY_PROFILE_ID,
            "profiles": [
                {
                    "profile_id": profile.profile_id,
                    "display_name": profile.display_name,
                    "profile_version": profile.profile_version,
                    "binding_mode": "general" if profile.is_general else "named",
                    "selection_requires_confirmation": not profile.is_general,
                }
                for profile in sorted(self._profiles.values(), key=lambda entry: (entry.is_general is False, entry.display_name))
                if self._is_publicly_available(profile, region=region)
            ],
        }

    def resolve_binding(
        self,
        *,
        scenario_id: str,
        profile_id: str | None,
        selection_source: PhotographerSelectionSource | None,
        region: str | None = None,
    ) -> PhotographerProfileBinding | None:
        # The public fields are intentionally inert outside Photography.
        if scenario_id != "photography":
            return None
        clean_id = str(profile_id or "").strip() or GENERAL_PHOTOGRAPHY_PROFILE_ID
        profile = self._profiles.get(clean_id)
        if profile is None:
            raise PhotographerProfileSelectionError(
                "photographer_profile_not_found",
                "The requested photographer profile does not exist.",
                status_code=422,
            )
        if profile.is_general:
            if selection_source is not None:
                raise PhotographerProfileSelectionError(
                    "general_profile_does_not_accept_selection_source",
                    "General Photography must not carry a named-profile selection source.",
                    status_code=422,
                )
            return self._binding(profile, mode="general", selection_source=None, availability_decision="general_default")
        if selection_source != "user_explicit_ui":
            raise PhotographerProfileSelectionError(
                "named_profile_requires_explicit_ui_selection",
                "A named photographer profile must be confirmed in the Photography workspace.",
                status_code=422,
            )
        if profile.availability != "available":
            raise PhotographerProfileSelectionError(
                "photographer_profile_unavailable",
                "The selected photographer profile is currently unavailable.",
                status_code=409,
            )
        if profile.allowed_regions and str(region or "").strip().upper() not in set(profile.allowed_regions):
            raise PhotographerProfileSelectionError(
                "photographer_profile_region_restricted",
                "The selected photographer profile is not available in this region.",
                status_code=403,
            )
        return self._binding(profile, mode="named", selection_source="user_explicit_ui", availability_decision="available")

    def _is_publicly_available(self, profile: PhotographerProfileDefinition, *, region: str | None) -> bool:
        if profile.availability != "available":
            return False
        return not profile.allowed_regions or str(region or "").strip().upper() in set(profile.allowed_regions)

    def _binding(
        self,
        profile: PhotographerProfileDefinition,
        *,
        mode: PhotographerBindingMode,
        selection_source: PhotographerSelectionSource | None,
        availability_decision: str,
    ) -> PhotographerProfileBinding:
        return PhotographerProfileBinding(
            binding_mode=mode,
            profile_id=profile.profile_id,
            profile_display_name=profile.display_name,
            profile_version=profile.profile_version,
            selection_source=selection_source,
            catalog_version=self.catalog_version,
            availability_decision=availability_decision,
            technique_package_checksum=profile.technique_package_checksum,
            pinned_at=datetime.now(UTC).isoformat(),
        )


_default_catalog = PhotographerProfileCatalog()


def default_photographer_profile_catalog() -> PhotographerProfileCatalog:
    return _default_catalog
