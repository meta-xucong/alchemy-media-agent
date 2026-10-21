"""Versioned, bounded image option negotiation; never infer real tool controls."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .client import BridgeError


NATIVE_PROFILES = ("fake-image", "codex-image", "midjourney-manual")
FORMAT_MIMES = {"png": "image/png", "jpeg": "image/jpeg"}


class _Projection(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")


class QualityContract(_Projection):
    values: list[Literal["auto"]] = Field(min_length=1, max_length=1)
    semantics: Literal["unspecified_only"]


class FormatContract(_Projection):
    values: list[Literal["png", "jpeg"]] = Field(min_length=1, max_length=2)
    semantics: Literal["original_artifact_postcondition"]


class FidelityContract(_Projection):
    values: list = Field(max_length=0)
    semantics: Literal["omitted_only"]


class ReferenceContract(_Projection):
    max_count: int = Field(ge=0, le=8)
    semantics: Literal["hash_checked_not_conditioning", "local_image_input_unverified", "not_supported"]


class ImageOptionsContract(_Projection):
    schema_version: Literal["1"]
    quality: QualityContract
    output_format: FormatContract
    input_fidelity: FidelityContract
    references: ReferenceContract


def image_options_projection(value):
    if value is None:
        return None
    try:
        return ImageOptionsContract.model_validate(value).model_dump()
    except ValidationError:
        return None


def native_profile(capabilities, *, profile_id, output_format, reference_count, width, height):
    """Return bounded limits and negotiated options, before any native plan call."""
    profiles = capabilities.get("profiles") if isinstance(capabilities, dict) else None
    if not isinstance(capabilities, dict) or capabilities.get("schema_version") != "1" or not isinstance(profiles, list):
        raise BridgeError("native_profile_capability_unavailable", retryable=False)
    profile = next((p for p in profiles if isinstance(p, dict) and p.get("execution_profile_id") == profile_id
                    and p.get("execution_profile_revision") == "1" and p.get("operation") == "image.generate"), None)
    if profile is None:
        raise BridgeError("native_profile_capability_unavailable", retryable=False)
    limits = profile.get("limits", {})
    if not isinstance(limits, dict) or any(type(limits.get(k)) is not int or limits[k] < 1 for k in
           ("max_output_bytes", "max_image_pixels", "max_dimension")):
        raise BridgeError("invalid_bridge_capabilities", retryable=False)
    limits = {"max_output_bytes": min(limits["max_output_bytes"], 1048576 if profile_id == "fake-image" else 16777216),
              "max_image_pixels": min(limits["max_image_pixels"], 1048576),
              "max_dimension": min(limits["max_dimension"], 1024)}
    if max(width, height) > limits["max_dimension"] or width * height > limits["max_image_pixels"]:
        raise BridgeError("profile_dimensions_exceeded", retryable=False)
    contract = image_options_projection(profile.get("image_options_contract"))
    # Older v1 is valid only for its already-supported fake PNG contract.
    legacy = profile_id == "fake-image" and output_format == "png" and "image_options_contract" not in profile
    if not contract and not legacy:
        raise BridgeError("native_image_options_contract_unavailable", retryable=False)
    if contract:
        if output_format not in contract["output_format"]["values"]:
            raise BridgeError("native_output_format_unsupported", retryable=False)
        if reference_count > contract["references"]["max_count"]:
            raise BridgeError("native_profile_references_unsupported", retryable=False)
        expected = {"fake-image": "hash_checked_not_conditioning", "codex-image": "local_image_input_unverified",
                    "midjourney-manual": "not_supported"}[profile_id]
        if contract["references"]["semantics"] != expected:
            raise BridgeError("native_reference_contract_unavailable", retryable=False)
    return {**profile, "limits": limits, "negotiated_image_options": None if legacy else {
        "schema_version": "1", "quality": "auto", "output_format": output_format}}
