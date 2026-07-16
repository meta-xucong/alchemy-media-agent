"""Internal contracts for the first Professional Mode asset module.

These contracts describe reviewed identity evidence and lifecycle state. They
do not contain provider prompts, provider controls, biometric vectors, or
scenario-specific delivery fields.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, Field, field_validator, model_validator

from ..schemas.models import V3BaseModel


FaceViewRole = Literal["standard_front", "three_quarter", "profile"]
PackStatus = Literal["preparing", "review", "active", "failed", "superseded"]
AssetStatus = Literal["draft", "active", "superseded", "blocked"]
ModuleStatus = Literal["draft", "active", "blocked", "superseded"]

FACE_IDENTITY_CHANNELS = (
    "face_geometry",
    "face_feature_relationships",
)
REQUIRED_FACE_VIEW_ROLES = frozenset({"standard_front", "three_quarter", "profile"})


class _StrictVisualAssetModel(V3BaseModel):
    """Prevent prompt/provider/vertical fields from entering asset contracts."""

    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
    )


class RootSourceProvenance(_StrictVisualAssetModel):
    source_type: Literal["uploaded_portrait", "generated_character"]
    source_asset_id: str
    project_id: str
    consent_reference: str | None = None


class IdentityScoreSummary(_StrictVisualAssetModel):
    same_face_score: float = Field(ge=0.0, le=1.0)
    visual_quality_score: float = Field(ge=0.0, le=1.0)
    evidence_codes: list[str] = Field(default_factory=list)

    @field_validator("evidence_codes")
    @classmethod
    def unique_evidence_codes(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("identity evidence codes must be unique")
        return value


class AnchorView(_StrictVisualAssetModel):
    view_id: str
    view_role: FaceViewRole
    output_id: str
    source_candidate_ids: list[str] = Field(min_length=1)
    identity_scores: IdentityScoreSummary
    active: bool = True


class FaceIdentityModule(_StrictVisualAssetModel):
    module_id: str
    people_asset_id: str
    active_version_id: str | None = None
    status: ModuleStatus = "draft"
    owned_channels: tuple[str, ...] = FACE_IDENTITY_CHANNELS

    @model_validator(mode="after")
    def enforce_face_only_scope(self) -> "FaceIdentityModule":
        if set(self.owned_channels) != set(FACE_IDENTITY_CHANNELS):
            raise ValueError("Face Identity Module may own face channels only")
        if self.status == "active" and not self.active_version_id:
            raise ValueError("active Face Identity Module requires an active pack version")
        return self


class IdentityAnchorPackVersion(_StrictVisualAssetModel):
    pack_version_id: str
    people_asset_id: str
    status: PackStatus = "preparing"
    anchor_views: list[AnchorView] = Field(default_factory=list)
    root_source_provenance: RootSourceProvenance
    user_activation_confirmed: bool = False

    @model_validator(mode="after")
    def validate_pack_activation(self) -> "IdentityAnchorPackVersion":
        view_ids = [item.view_id for item in self.anchor_views]
        if len(view_ids) != len(set(view_ids)):
            raise ValueError("anchor view IDs must be unique")
        if self.status == "active":
            roles = {item.view_role for item in self.anchor_views if item.active}
            missing = REQUIRED_FACE_VIEW_ROLES - roles
            if not self.user_activation_confirmed:
                raise ValueError("active pack requires user activation")
            if missing:
                raise ValueError(f"active pack is missing required face views: {sorted(missing)}")
        return self


class PeopleAsset(_StrictVisualAssetModel):
    people_asset_id: str
    project_id: str
    subject_kind: Literal["human_person", "fictional_character"]
    face_identity_module: FaceIdentityModule
    active_pack_version_id: str | None = None
    status: AssetStatus = "draft"

    @model_validator(mode="after")
    def validate_active_asset(self) -> "PeopleAsset":
        if self.face_identity_module.people_asset_id != self.people_asset_id:
            raise ValueError("Face Identity Module must belong to the People Asset")
        if self.status == "active" and not self.active_pack_version_id:
            raise ValueError("active People Asset requires an active pack version")
        return self


class ProfessionalModeBinding(_StrictVisualAssetModel):
    """Sanitized per-job binding passed to the shared semantic planning path."""

    mode: str = "professional"
    job_id: str
    project_id: str
    people_asset_id: str
    face_module_id: str
    pack_version_id: str
    identity_view_ids: list[str] = Field(min_length=1, max_length=3)

    @field_validator("mode")
    @classmethod
    def require_explicit_professional_mode(cls, value: str) -> str:
        if value != "professional":
            raise ValueError("an explicit Professional Mode selection is required")
        return value

    @field_validator("identity_view_ids")
    @classmethod
    def unique_identity_views(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("identity view IDs must be unique")
        return value

    def to_brain_evidence(self) -> dict[str, object]:
        """Return typed identity evidence, never creative/provider instructions."""

        return {
            "mode": self.mode,
            "people_asset_id": self.people_asset_id,
            "pack_version_id": self.pack_version_id,
            "face_module_id": self.face_module_id,
            "identity_view_ids": list(self.identity_view_ids),
            "identity_channels": list(FACE_IDENTITY_CHANNELS),
        }
