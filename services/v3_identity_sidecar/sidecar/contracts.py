from __future__ import annotations

from typing import Any, Literal

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ReferenceManifestItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    asset_id: str | None = None
    source_asset_id: str | None = None
    truth_layer: Literal["portrait_identity_truth"]
    derivative_kind: str | None = None

    @field_validator("field")
    @classmethod
    def validate_field(cls, value: str) -> str:
        if not value.startswith("reference_") or not value.removeprefix("reference_").isdigit():
            raise ValueError("reference field must use reference_<index>")
        return value


class RequestedCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity_conditioning: bool = True
    multi_reference: bool = False
    identity_native_local_repair: bool = False


class RepairManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    active: bool = False
    canvas_field: str | None = None
    mask_field: str | None = None


class IdentityGenerationManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: Literal["doc98-v1"]
    operation: Literal["identity_reference_generation"]
    backend_family: str
    model: str
    prompt: str = Field(min_length=1)
    negative_constraints: list[str] = Field(default_factory=list)
    count: int = Field(default=1, ge=1, le=1)
    size: str = "auto"
    quality: Literal["low", "medium", "high", "auto"] = "auto"
    output_format: Literal["png", "jpeg", "webp"] = "png"
    idempotency_key: str | None = None
    trace_id: str | None = None
    input_fidelity: Literal["low", "high"] = "high"
    reference_manifest: list[ReferenceManifestItem] = Field(min_length=1)
    requested_capabilities: RequestedCapabilities = Field(default_factory=RequestedCapabilities)
    repair: RepairManifest = Field(default_factory=RepairManifest)

    @field_validator("size")
    @classmethod
    def validate_size(cls, value: str) -> str:
        if value != "auto" and re.fullmatch(r"\d{3,4}x\d{3,4}", value) is None:
            raise ValueError("size must be auto or WIDTHxHEIGHT")
        return value

    @model_validator(mode="after")
    def validate_identity_contract(self):
        expected_fields = [f"reference_{index}" for index in range(len(self.reference_manifest))]
        actual_fields = [item.field for item in self.reference_manifest]
        if actual_fields != expected_fields:
            raise ValueError("reference_manifest fields must be contiguous and ordered from reference_0")
        if not self.requested_capabilities.identity_conditioning:
            raise ValueError("identity_conditioning must be requested")
        if self.requested_capabilities.multi_reference != (len(self.reference_manifest) > 1):
            raise ValueError("multi_reference must match the reference count")
        if self.repair.active:
            if not self.requested_capabilities.identity_native_local_repair:
                raise ValueError("active repair must request identity_native_local_repair")
            if not self.repair.canvas_field or not self.repair.mask_field:
                raise ValueError("active repair requires canvas_field and mask_field")
        elif self.repair.canvas_field or self.repair.mask_field:
            raise ValueError("inactive repair cannot declare canvas or mask fields")
        return self


class BackendCapabilities(BaseModel):
    configured: bool
    healthy: bool
    identity_conditioning: bool
    multi_reference: bool
    identity_native_local_repair: bool
    max_reference_images: int
    provider: str
    model: str
    backend: str
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackendImage(BaseModel):
    content: bytes
    mime_type: str = "image/png"
    width: int | None = None
    height: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BackendGenerationResult(BaseModel):
    provider: str
    model: str
    images: list[BackendImage]
    metadata: dict[str, Any] = Field(default_factory=dict)
