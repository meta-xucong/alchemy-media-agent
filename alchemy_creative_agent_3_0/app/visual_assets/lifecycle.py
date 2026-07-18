"""Formal project-scoped People Asset lifecycle entry points.

This module is deliberately limited to catalog lifecycle and activation.  It
does not generate pixels, choose prompts, review images, or bypass the shared
Brain/Provider/Vision path.  Anchor-pack preparation remains the injected
``AnchorPackPreparationService`` contract so a host cannot activate a pack
without a complete reviewed result and explicit user confirmation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import ConfigDict, field_validator

from ..schemas.models import V3BaseModel
from .catalog import InMemoryVisualAssetCatalog
from .contracts import FaceIdentityModule, IdentityAnchorPackVersion, PeopleAsset, RootSourceProvenance


class PeopleAssetCreateRequest(V3BaseModel):
    """Server-owned request for a new project-scoped People Asset draft."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    people_asset_id: str | None = None
    subject_kind: Literal["human_person", "fictional_character"] = "human_person"
    root_source_asset_id: str
    consent_reference: str

    @field_validator("root_source_asset_id", "consent_reference")
    @classmethod
    def require_explicit_provenance(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("root source and consent reference are required")
        return value


class PeopleAssetActivationRequest(V3BaseModel):
    """Explicit user confirmation for an already complete reviewed pack."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    pack_version_id: str
    confirm_activation: bool = False

    @field_validator("pack_version_id")
    @classmethod
    def require_pack_version(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("pack_version_id is required")
        return value


class PeopleAssetLifecycleService:
    """Project-scoped catalog operations used by Product API and hosts."""

    def __init__(self, catalog: InMemoryVisualAssetCatalog) -> None:
        self.catalog = catalog

    def create_draft(
        self,
        project_id: str,
        request: PeopleAssetCreateRequest,
    ) -> PeopleAsset:
        project_id = project_id.strip()
        if not project_id:
            raise ValueError("project_id is required")
        people_asset_id = (request.people_asset_id or "").strip() or self._new_asset_id()
        if self.catalog.get(project_id, people_asset_id) is not None:
            raise ValueError("people_asset_already_exists")
        # Root source and consent are attached to the first pack provenance,
        # not copied into a prompt or arbitrary metadata field.  The draft is
        # intentionally not active until a complete pack is activated.
        asset = PeopleAsset(
            people_asset_id=people_asset_id,
            project_id=project_id,
            subject_kind=request.subject_kind,
            face_identity_module=FaceIdentityModule(
                module_id=f"face_{people_asset_id}",
                people_asset_id=people_asset_id,
                status="draft",
            ),
            root_source_provenance=RootSourceProvenance(
                source_type="uploaded_portrait" if request.subject_kind == "human_person" else "generated_character",
                source_asset_id=request.root_source_asset_id,
                project_id=project_id,
                consent_reference=request.consent_reference,
            ),
            status="draft",
        )
        self.catalog.save(asset, project_id=project_id, event_type="create")
        return asset

    def get(self, project_id: str, people_asset_id: str) -> PeopleAsset:
        asset = self.catalog.get(project_id, people_asset_id)
        if asset is None:
            raise KeyError("professional_people_asset_not_found")
        return asset

    def list(self, project_id: str) -> list[PeopleAsset]:
        return self.catalog.list_assets(project_id)

    def activate_pack(
        self,
        project_id: str,
        people_asset_id: str,
        request: PeopleAssetActivationRequest,
    ) -> PeopleAsset:
        if not request.confirm_activation:
            raise ValueError("explicit user confirmation is required to activate the face pack")
        asset = self.get(project_id, people_asset_id)
        pack = self.catalog.get_pack(project_id, people_asset_id, request.pack_version_id)
        if pack is None:
            raise KeyError("professional_people_asset_pack_not_found")
        if (
            asset.root_source_provenance is None
            or pack.root_source_provenance.source_asset_id != asset.root_source_provenance.source_asset_id
            or pack.root_source_provenance.project_id != project_id
        ):
            raise ValueError("anchor pack root does not match the People Asset root provenance")
        if pack.status != "active" or not pack.user_activation_confirmed:
            raise ValueError("only a complete user-confirmed active pack can bind the People Asset")
        if asset.active_pack_version_id and asset.active_pack_version_id != pack.pack_version_id:
            self.catalog.save(asset.model_copy(update={"status": "superseded"}), project_id=project_id, event_type="supersede")
        active = asset.model_copy(
            update={
                "active_pack_version_id": pack.pack_version_id,
                "status": "active",
                "face_identity_module": asset.face_identity_module.model_copy(
                    update={"active_version_id": pack.pack_version_id, "status": "active"}
                ),
            }
        )
        self.catalog.save(active, project_id=project_id, event_type="activate")
        return active

    @staticmethod
    def _new_asset_id() -> str:
        # Deterministic IDs are not required for catalog identity; use a short
        # UUID suffix while keeping the catalog's safe component contract.
        from uuid import uuid4

        return f"person_{uuid4().hex[:16]}"


__all__ = [
    "PeopleAssetActivationRequest",
    "PeopleAssetCreateRequest",
    "PeopleAssetLifecycleService",
]
