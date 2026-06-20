from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


LAB_REFERENCE_ROLES = {
    "subject_reference",
    "product_reference",
    "logo_reference",
    "style_material_reference",
    "composition_reference",
    "negative_reference",
}
LAB_REFERENCE_STRENGTHS = {"required", "strong", "soft"}
LAB_REFERENCE_FEATURE_ID = "rare-style-explorer"


class LabAssetConsent(BaseModel):
    user_confirmed_rights: bool = False
    portrait_identity_allowed: bool = False
    logo_or_trademark_allowed: bool = False
    commercial_use_allowed: bool = False
    source_note: str | None = None

    def has_basic_rights(self) -> bool:
        return bool(self.user_confirmed_rights)


class CreateLabUploadRequest(BaseModel):
    filename: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    feature_id: str = LAB_REFERENCE_FEATURE_ID
    role: Literal[
        "subject_reference",
        "product_reference",
        "logo_reference",
        "style_material_reference",
        "composition_reference",
        "negative_reference",
    ] | None = None
    constraint_strength: Literal["required", "strong", "soft"] = "strong"
    intended_use: str | None = None
    consent: LabAssetConsent | dict[str, Any] = Field(default_factory=LabAssetConsent)

    @field_validator("filename")
    @classmethod
    def filename_required(cls, value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("filename is required")
        return clean


class LabAssetContentUploadRequest(BaseModel):
    content_base64: str
    mime_type: str | None = None


class CreateLabUploadResponse(BaseModel):
    asset_id: str
    upload_url: str
    headers: dict[str, str] = Field(default_factory=dict)


class LabUploadedAsset(BaseModel):
    asset_id: str
    feature_id: str = LAB_REFERENCE_FEATURE_ID
    filename: str
    mime_type: str
    size_bytes: int
    veyra_user_id: int | None = None
    status: Literal["upload_requested", "stored", "ready", "rejected", "failed", "deleted"] = "upload_requested"
    role: str | None = None
    constraint_strength: Literal["required", "strong", "soft"] = "strong"
    intended_use: str | None = None
    consent: LabAssetConsent | dict[str, Any] = Field(default_factory=LabAssetConsent)
    upload_url: str | None = None
    source_url: str | None = None
    thumbnail_url: str | None = None
    storage_path: str | None = None
    brief: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    created_at: str
    updated_at: str


class LabReferenceAssetInput(BaseModel):
    asset_id: str
    role: Literal[
        "subject_reference",
        "product_reference",
        "logo_reference",
        "style_material_reference",
        "composition_reference",
        "negative_reference",
    ] | None = None
    constraint_strength: Literal["required", "strong", "soft"] | None = None
    notes: str | None = None

    @field_validator("asset_id")
    @classmethod
    def asset_id_required(cls, value: str) -> str:
        clean = str(value or "").strip()
        if not clean:
            raise ValueError("asset_id is required")
        return clean
