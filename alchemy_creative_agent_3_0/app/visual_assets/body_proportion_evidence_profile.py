"""Closed Body proportion evidence/profile contracts.

This module owns the boundary between server-admitted Body evidence and the
Brain/body-generation request.  It does not infer proportions from a count,
hash, or metadata-only partition.  A caller must supply a real source-analysis
adapter; when none is available the boundary fails closed.
"""

from __future__ import annotations

import base64
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import ConfigDict, StrictInt, StrictStr, ValidationError, field_validator, model_validator

from ..schemas.models import V3BaseModel


class BodyProportionAnalysisError(ValueError):
    """Closed failure raised when Body source analysis cannot be trusted."""


BODY_REFRESH_ANALYSIS_CONTEXT_SCHEMA_VERSION = "body_refresh_analysis_context_v2"


_CLOSED_ANALYSIS_ERROR_CODES = frozenset(
    {
        "body_proportion_analysis_missing",
        "body_proportion_analysis_provider_unavailable",
        "body_proportion_analysis_profile_invalid",
        "body_proportion_analysis_source_mode_invalid",
        "body_proportion_analysis_source_count_invalid",
        "body_proportion_analysis_source_invalid",
        "body_proportion_analysis_role_invalid",
        "body_proportion_analysis_truth_layer_invalid",
        "body_proportion_analysis_source_not_ready",
        "body_proportion_analysis_source_hash_mismatch",
    }
)


class BodyProportionEvidenceBands(V3BaseModel):
    """Closed categorical Body-owned analysis bands."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    head_body_scale: Literal[
        "compact_child_scale",
        "balanced_child_scale",
        "elongated_child_scale",
    ]
    neck_shoulder: Literal[
        "narrow_child_transition",
        "balanced_child_transition",
        "broad_child_transition",
    ]
    torso_limb: Literal[
        "short_child_torso_limb",
        "balanced_child_torso_limb",
        "long_child_torso_limb",
    ]
    arm_leg: Literal[
        "short_child_arm_leg",
        "balanced_child_arm_leg",
        "long_child_arm_leg",
    ]
    developmental_stage: Literal[
        "early_childhood_coherent",
        "middle_childhood_coherent",
        "adolescent_coherent",
    ]
    stance_ground: Literal[
        "grounded_full_contact",
        "toe_weighted_contact",
        "dynamic_contact",
    ]
    cross_view_support: Literal[
        "front_only",
        "front_back_supported",
        "multi_view_supported",
    ]


_BODY_PROPORTION_BAND_KEYS = frozenset(BodyProportionEvidenceBands.model_fields)
_BODY_PROPORTION_ALLOWED_VALUES = {
    field_name: frozenset(
        field_schema.get("enum", ())
    )
    for field_name, field_schema in BodyProportionEvidenceBands.model_json_schema().get(
        "properties",
        {},
    ).items()
}


def _build_body_analysis_response_schema() -> dict[str, Any]:
    band_schema = BodyProportionEvidenceBands.model_json_schema()
    band_properties = band_schema.get("properties", {})
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "allowed_bands": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    field_name: {
                        "type": "string",
                        "enum": list(field_schema.get("enum", ())),
                    }
                    for field_name, field_schema in band_properties.items()
                },
                "required": sorted(band_properties),
            }
        },
        "required": ["allowed_bands"],
    }


_BODY_MORPHOLOGY_ANALYSIS_FIELDS = (
    "relative_head_to_stature",
    "shoulder_to_head",
    "torso_to_leg",
    "arm_to_leg",
    "build",
    "neck_shoulder",
    "developmental_stage_context",
    "stance_ground",
    "cross_view_support",
)


def build_body_morphology_analysis_response_schema() -> dict[str, Any]:
    """Return the exact v2 source-image analyzer response contract."""

    properties = BodyMorphologyEvidenceProfile.model_json_schema().get("properties", {})
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            field_name: {
                "type": "string",
                "enum": list(properties[field_name].get("enum", ())),
            }
            for field_name in _BODY_MORPHOLOGY_ANALYSIS_FIELDS
        },
        "required": list(_BODY_MORPHOLOGY_ANALYSIS_FIELDS),
    }
_BODY_ANALYSIS_RESPONSE_KEYS = frozenset({"allowed_bands"})
_BODY_ANALYSIS_SHAPE_CODES = frozenset(
    {
        "none",
        "body_proportion_analysis_profile_valid",
        "body_proportion_analysis_profile_invalid",
        "body_proportion_analysis_provider_unavailable",
    }
)
_MISSING_RESPONSE_VALUE = object()


def _safe_response_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    return "other"


def _safe_response_keys(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    return sorted(
        key if isinstance(key, str) else "<non_string_key>"
        for key in value
    )


def _safe_response_shape_projection(
    raw_response: Any,
    *,
    output_text: Any = _MISSING_RESPONSE_VALUE,
    schema_code: str = "none",
) -> dict[str, Any]:
    """Return only bounded response-shape facts; never return response values."""

    if schema_code not in _BODY_ANALYSIS_SHAPE_CODES:
        schema_code = "body_proportion_analysis_profile_invalid"

    if output_text is _MISSING_RESPONSE_VALUE:
        output_text_value = raw_response if isinstance(raw_response, str) else None
    else:
        output_text_value = output_text
    output_text_present = output_text_value is not None
    output_text_type = (
        _safe_response_type(output_text_value) if output_text_present else "absent"
    )

    parsed_response = raw_response
    json_parse_status = "not_applicable"
    if output_text_present:
        if isinstance(output_text_value, str):
            try:
                parsed_response = json.loads(output_text_value)
                json_parse_status = "success"
            except (TypeError, ValueError):
                parsed_response = _MISSING_RESPONSE_VALUE
                json_parse_status = "failed"
        else:
            parsed_response = _MISSING_RESPONSE_VALUE
            json_parse_status = "not_attempted"

    if parsed_response is _MISSING_RESPONSE_VALUE:
        response_top_level_type = "unknown"
        response_top_level_keys: list[str] = []
        response_unknown_field_count = 0
        response_missing_field_count = len(_BODY_ANALYSIS_RESPONSE_KEYS)
        allowed_bands_type = "absent"
        allowed_bands_keys: list[str] = []
        allowed_bands_unknown_field_count = 0
        allowed_bands_missing_field_count = len(_BODY_PROPORTION_BAND_KEYS)
    else:
        response_top_level_type = _safe_response_type(parsed_response)
        response_top_level_keys = _safe_response_keys(parsed_response)
        response_key_set = set(response_top_level_keys)
        response_unknown_field_count = len(
            response_key_set - _BODY_ANALYSIS_RESPONSE_KEYS
        )
        response_missing_field_count = len(
            _BODY_ANALYSIS_RESPONSE_KEYS - response_key_set
        )
        bands = (
            parsed_response.get("allowed_bands")
            if isinstance(parsed_response, Mapping)
            else None
        )
        if isinstance(bands, Mapping):
            allowed_bands_type = "object"
            allowed_bands_keys = _safe_response_keys(bands)
            band_key_set = set(allowed_bands_keys)
            allowed_bands_unknown_field_count = len(
                band_key_set - _BODY_PROPORTION_BAND_KEYS
            )
            allowed_bands_missing_field_count = len(
                _BODY_PROPORTION_BAND_KEYS - band_key_set
            )
        else:
            allowed_bands_type = "absent"
            allowed_bands_keys = []
            allowed_bands_unknown_field_count = 0
            allowed_bands_missing_field_count = len(_BODY_PROPORTION_BAND_KEYS)

    return {
        "output_text_present": output_text_present,
        "output_text_type": output_text_type,
        "json_parse_status": json_parse_status,
        "response_top_level_type": response_top_level_type,
        "response_top_level_keys": response_top_level_keys,
        "response_unknown_field_count": response_unknown_field_count,
        "response_missing_field_count": response_missing_field_count,
        "allowed_bands_type": allowed_bands_type,
        "allowed_bands_keys": allowed_bands_keys,
        "allowed_bands_unknown_field_count": allowed_bands_unknown_field_count,
        "allowed_bands_missing_field_count": allowed_bands_missing_field_count,
        "schema_code": schema_code,
    }


def _safe_response_value_projection(
    raw_response: Any,
    *,
    output_text: Any = _MISSING_RESPONSE_VALUE,
    schema_code: str = "none",
) -> dict[str, Any]:
    """Classify band values without returning any band value itself."""

    shape = _safe_response_shape_projection(
        raw_response,
        output_text=output_text,
        schema_code=schema_code,
    )
    if output_text is _MISSING_RESPONSE_VALUE:
        output_text_value = raw_response if isinstance(raw_response, str) else None
    else:
        output_text_value = output_text
    parsed_response = raw_response
    if isinstance(output_text_value, str):
        try:
            parsed_response = json.loads(output_text_value)
        except (TypeError, ValueError):
            parsed_response = _MISSING_RESPONSE_VALUE
    bands = (
        parsed_response.get("allowed_bands")
        if isinstance(parsed_response, Mapping)
        else None
    )
    band_key_set = set(_safe_response_keys(bands))
    unknown_band_keys = sorted(band_key_set - _BODY_PROPORTION_BAND_KEYS)
    per_band: list[dict[str, Any]] = []
    for band_name in sorted(_BODY_PROPORTION_BAND_KEYS):
        if not isinstance(bands, Mapping) or band_name not in bands:
            per_band.append(
                {
                    "band": band_name,
                    "present": False,
                    "value_type": "absent",
                    "allowed_membership": "missing",
                    "closed_code": "body_proportion_analysis_profile_invalid",
                }
            )
            continue
        band_value = bands[band_name]
        value_type = _safe_response_type(band_value)
        if not isinstance(band_value, str):
            allowed_membership = "not_applicable"
            closed_code = "body_proportion_analysis_profile_invalid"
        elif band_value in _BODY_PROPORTION_ALLOWED_VALUES.get(band_name, ()):
            allowed_membership = "allowed"
            closed_code = "none"
        else:
            allowed_membership = "not_allowed"
            closed_code = "body_proportion_analysis_profile_invalid"
        per_band.append(
            {
                "band": band_name,
                "present": True,
                "value_type": value_type,
                "allowed_membership": allowed_membership,
                "closed_code": closed_code,
            }
        )
    return {
        "unknown_band_key_count": len(unknown_band_keys),
        "unknown_band_keys": unknown_band_keys,
        "per_band": per_band,
        "schema_code": shape["schema_code"],
    }


class BodyProportionAnalysisReceipt(V3BaseModel):
    """Server-owned proof that a Body profile came from source analysis."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    owner: Literal["server_owned_body_proportion_analysis"]
    status: Literal["complete"]
    analysis_provider: Literal["configured_body_source_analysis_provider"]


class BodySourceAnalysisProvider(Protocol):
    """Configured Body-owner source-image analysis boundary.

    This is deliberately separate from the shared generated-output Vision
    inspection provider.  Implementations receive only server-resolved Body
    evidence and must return a closed profile payload; they must never return
    raw image data, paths, IDs, or biometric vectors.
    """

    def analyze(
        self,
        admitted_body_assets: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        """Analyze admitted Body evidence into a closed profile payload."""


@dataclass(frozen=True, slots=True)
class BodySourceImagePayload:
    """Transient image bytes passed to a source-analysis transport.

    The transport receives bytes and MIME type only.  It never receives or
    returns a public asset ID, filesystem path, URL, or stored reference.
    """

    content: bytes
    mime_type: str


class BodySourceAnalysisAssetEnvelope(V3BaseModel):
    """Typed internal proof for one server-resolved Body source image.

    This envelope is intentionally carried outside public request metadata and
    is consumed only by the Body source-analysis adapter.  It may contain the
    server's transient file locator and provenance proof, but it must never be
    copied into Brain metadata, Provider reference inputs, or public status.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    asset_id: str
    role: Literal["body_proportion_reference"]
    reference_truth_layer: Literal["body_proportion_truth"]
    file_path: str
    mime_type: Literal["image/png", "image/jpeg", "image/webp"]
    source_sha256: str
    content_stored: Literal[True] = True
    ready_for_v3_runtime: Literal[True] = True
    source_provenance: str
    consent_reference: str
    rights_reference: str

    @field_validator("asset_id", "file_path", "source_provenance", "consent_reference", "rights_reference")
    @classmethod
    def require_nonempty_internal_value(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("body_proportion_analysis_source_invalid")
        return cleaned

    @field_validator("source_sha256")
    @classmethod
    def require_sha256(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(char not in "0123456789abcdef" for char in cleaned):
            raise ValueError("body_proportion_analysis_source_hash_mismatch")
        return cleaned

    def to_analyzer_record(self) -> dict[str, Any]:
        """Build the ephemeral mapping accepted by the analyzer adapter."""

        return {
            "asset_id": self.asset_id,
            "role": self.role,
            "reference_truth_layer": self.reference_truth_layer,
            "file_path": self.file_path,
            "mime_type": self.mime_type,
            "metadata": {
                "content_stored": True,
                "ready_for_v3_runtime": True,
                "source_sha256": self.source_sha256,
                "source_provenance": self.source_provenance,
                "consent_reference": self.consent_reference,
                "rights_reference": self.rights_reference,
                "reference_truth_layer": self.reference_truth_layer,
            },
        }


class BodySourceAnalysisTransport(Protocol):
    """Provider-neutral transport for one structured multimodal analysis."""

    def analyze(
        self,
        images: Sequence[BodySourceImagePayload],
        *,
        instructions: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any] | str:
        """Return only the structured analyzer response for this call."""


class ConfiguredBodySourceAnalysisProvider:
    """Explicit deployment adapter for one real Body source analyzer.

    The application does not instantiate this with a deterministic fallback.
    Deployment code must provide the real source-image analyzer; the
    surrounding typed adapter validates its result and converts availability
    failures into a closed error.
    """

    provider_name = "configured_body_source_analysis_provider"

    def __init__(
        self,
        analyze_fn: Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]],
    ) -> None:
        if not callable(analyze_fn):
            raise TypeError("body source analysis provider must be callable")
        self._analyze_fn = analyze_fn

    def analyze(
        self,
        admitted_body_assets: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        return self._analyze_fn(admitted_body_assets)


class OpenAICompatibleBodySourceAnalysisTransport:
    """Structured multimodal transport, separate from generated-output review.

    This adapter has no review/output semantics and performs no retry or
    fallback.  Image bytes are encoded only while constructing the upstream
    request and the response is parsed immediately into a JSON object.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        profile_version: str = "v1",
    ) -> None:
        if profile_version not in {"v1", "v2"}:
            raise ValueError("body_refresh_analysis_profile_version_invalid")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.profile_version = profile_version
        self.last_response_shape_projection: dict[str, Any] | None = None
        self.last_response_value_projection: dict[str, Any] | None = None

    def analyze(
        self,
        images: Sequence[BodySourceImagePayload],
        *,
        instructions: str,
        timeout_seconds: float,
    ) -> Mapping[str, Any] | str:
        if not self.api_key or not self.base_url or not self.model:
            raise RuntimeError("body source analysis provider unavailable")
        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                max_retries=0,
            )
            content: list[dict[str, Any]] = [
                {"type": "input_text", "text": instructions}
            ]
            for image in images:
                encoded = base64.b64encode(image.content).decode("ascii")
                content.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{image.mime_type};base64,{encoded}",
                    }
                )
            response = client.responses.create(
                model=self.model,
                input=[{"role": "user", "content": content}],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": (
                            "body_morphology_analysis_v2"
                            if self.profile_version == "v2"
                            else "body_proportion_analysis_v1"
                        ),
                        "strict": True,
                        "schema": (
                            build_body_morphology_analysis_response_schema()
                            if self.profile_version == "v2"
                            else _build_body_analysis_response_schema()
                        ),
                    }
                },
                timeout=timeout_seconds,
                max_output_tokens=1200,
            )
        except Exception as exc:
            raise RuntimeError("body source analysis transport failed") from exc
        output_text = str(getattr(response, "output_text", "") or "").strip()
        self.last_response_shape_projection = _safe_response_shape_projection(
            output_text,
            output_text=output_text if output_text else None,
        )
        self.last_response_value_projection = _safe_response_value_projection(
            output_text,
            output_text=output_text if output_text else None,
        )
        if not output_text:
            self.last_response_shape_projection["schema_code"] = (
                "body_proportion_analysis_provider_unavailable"
            )
            self.last_response_value_projection["schema_code"] = (
                "body_proportion_analysis_provider_unavailable"
            )
            raise ValueError("body source analysis response was empty")
        try:
            return json.loads(output_text)
        except (TypeError, ValueError) as exc:
            self.last_response_shape_projection["schema_code"] = (
                "body_proportion_analysis_provider_unavailable"
            )
            self.last_response_value_projection["schema_code"] = (
                "body_proportion_analysis_provider_unavailable"
            )
            raise ValueError("body source analysis response was not valid JSON") from exc


class OpenAICompatibleBodySourceAnalysisProvider:
    """Configured server-owned Body source-image analysis implementation.

    It reads exactly five already-admitted Body files for one transient call,
    sends only a closed Body-owned analysis instruction, and returns a typed
    safe profile payload.  It never persists the source bytes or upstream
    response and does not produce physical renderer references.
    """

    provider_name = "configured_body_source_analysis_provider"
    _ANALYSIS_RESPONSE_KEYS = frozenset({"allowed_bands"})
    analysis_response_schema = _build_body_analysis_response_schema()
    _ANALYSIS_INSTRUCTIONS = (
        "Analyze exactly these five admitted Body proportion reference images "
        "for a similar-person Body-only modeling context. Return strict JSON "
        "matching the closed schema contract. Each field must use exactly one "
        "canonical literal from the following band table; do not paraphrase, "
        "translate, alias, or infer defaults. Canonical literal table: "
        + json.dumps(
            {
                field_name: sorted(values)
                for field_name, values in _BODY_PROPORTION_ALLOWED_VALUES.items()
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + ". Do not analyze or return Face identity, hair, wardrobe, scene, "
        "lighting, camera, expression, pose style, provider details, paths, "
        "IDs, URLs, raw image data, or biometric data."
    )

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        profile_version: str = "v1",
        timeout_seconds: float = 90.0,
        transport: BodySourceAnalysisTransport | None = None,
    ) -> None:
        if profile_version not in {"v1", "v2"}:
            raise ValueError("body_refresh_analysis_profile_version_invalid")
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.profile_version = profile_version
        self.analysis_response_schema = (
            build_body_morphology_analysis_response_schema()
            if profile_version == "v2"
            else _build_body_analysis_response_schema()
        )
        self.analysis_instructions = (
            "Analyze exactly five admitted Body proportion reference images. Return only strict JSON "
            "with these exact canonical morphology fields and no prose, identity, hair, clothing, scene, "
            "lighting, camera, expression, path, ID, URL, raw image, or biometric data: "
            + json.dumps(self.analysis_response_schema["properties"], sort_keys=True, separators=(",", ":"))
            if profile_version == "v2"
            else self._ANALYSIS_INSTRUCTIONS
        )
        self.timeout_seconds = timeout_seconds
        self.last_response_shape_projection: dict[str, Any] | None = None
        self.last_response_value_projection: dict[str, Any] | None = None
        self.transport = transport or (
            OpenAICompatibleBodySourceAnalysisTransport(
                api_key=api_key or "",
                base_url=base_url or "",
                model=model or "",
                profile_version=profile_version,
            )
            if api_key and base_url and model
            else None
        )

    def available(self, *, force: bool = False) -> bool:
        """Return whether a configured transport can run source analysis."""

        del force
        return self.transport is not None

    def analyze(
        self,
        admitted_body_assets: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        if not self.available(force=True):
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_provider_unavailable"
            )
        images = self._read_admitted_body_images(admitted_body_assets)
        try:
            raw_response = self.transport.analyze(  # type: ignore[union-attr]
                images,
                instructions=self.analysis_instructions,
                timeout_seconds=self.timeout_seconds,
            )
        except BodyProportionAnalysisError:
            raise
        except Exception as exc:
            transport_projection = getattr(
                self.transport,
                "last_response_shape_projection",
                None,
            )
            self.last_response_shape_projection = (
                dict(transport_projection)
                if isinstance(transport_projection, Mapping)
                else _safe_response_shape_projection(
                    None,
                    schema_code="body_proportion_analysis_provider_unavailable",
                )
            )
            transport_value_projection = getattr(
                self.transport,
                "last_response_value_projection",
                None,
            )
            self.last_response_value_projection = (
                dict(transport_value_projection)
                if isinstance(transport_value_projection, Mapping)
                else _safe_response_value_projection(
                    None,
                    schema_code="body_proportion_analysis_provider_unavailable",
                )
            )
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_provider_unavailable"
            ) from exc
        transport_projection = getattr(
            self.transport,
            "last_response_shape_projection",
            None,
        )
        self.last_response_shape_projection = (
            dict(transport_projection)
            if isinstance(transport_projection, Mapping)
            else _safe_response_shape_projection(raw_response)
        )
        transport_value_projection = getattr(
            self.transport,
            "last_response_value_projection",
            None,
        )
        self.last_response_value_projection = (
            dict(transport_value_projection)
            if isinstance(transport_value_projection, Mapping)
            else _safe_response_value_projection(raw_response)
        )
        try:
            if self.profile_version == "v2":
                payload = self._parse_morphology_response(raw_response)
                profile = BodyMorphologyEvidenceProfile.model_validate(
                    {
                        "contract_version": "body_morphology_evidence_profile_v2",
                        "source_mode": "reference_assisted",
                        "source_truth_layer": "body_proportion_truth",
                        **payload,
                        "source_count": 5,
                        "analysis_receipt": {
                            "owner": "server_owned_body_proportion_analysis",
                            "status": "complete",
                            "analysis_provider": self.provider_name,
                        },
                    }
                )
            else:
                payload = self._parse_response(raw_response)
                profile = BodyProportionEvidenceProfile.model_validate(
                    {
                        "contract_version": "body_proportion_evidence_profile_v1",
                        "source_mode": "reference_assisted",
                        "source_truth_layer": "body_proportion_truth",
                        "allowed_bands": payload["allowed_bands"],
                        "source_count": 5,
                        "analysis_receipt": {
                            "owner": "server_owned_body_proportion_analysis",
                            "status": "complete",
                            "analysis_provider": self.provider_name,
                        },
                    }
                )
        except BodyProportionAnalysisError:
            raise
        except (ValidationError, TypeError, ValueError, KeyError) as exc:
            self.last_response_shape_projection = {
                **(self.last_response_shape_projection or {}),
                "schema_code": "body_proportion_analysis_profile_invalid",
            }
            self.last_response_value_projection = {
                **(self.last_response_value_projection or {}),
                "schema_code": "body_proportion_analysis_profile_invalid",
            }
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_profile_invalid"
            ) from exc
        self.last_response_shape_projection = {
            **(self.last_response_shape_projection or {}),
            "schema_code": "body_proportion_analysis_profile_valid",
        }
        self.last_response_value_projection = {
            **(self.last_response_value_projection or {}),
            "schema_code": "body_proportion_analysis_profile_valid",
        }
        return profile.model_dump(mode="json")

    @classmethod
    def _parse_response(cls, raw_response: Mapping[str, Any] | str) -> dict[str, Any]:
        if isinstance(raw_response, str):
            raw_response = json.loads(raw_response)
        if not isinstance(raw_response, Mapping):
            raise TypeError("body source analysis response must be an object")
        if set(raw_response) != cls._ANALYSIS_RESPONSE_KEYS:
            raise ValueError("body source analysis response has unknown fields")
        bands = raw_response.get("allowed_bands")
        if not isinstance(bands, Mapping):
            raise TypeError("body source analysis bands must be an object")
        return {"allowed_bands": dict(bands)}

    @staticmethod
    def _parse_morphology_response(raw_response: Mapping[str, Any] | str) -> dict[str, Any]:
        if isinstance(raw_response, str):
            raw_response = json.loads(raw_response)
        if not isinstance(raw_response, Mapping):
            raise TypeError("body morphology analysis response must be an object")
        if set(raw_response) != set(_BODY_MORPHOLOGY_ANALYSIS_FIELDS):
            raise ValueError("body morphology analysis response has unknown fields")
        return {field: raw_response[field] for field in _BODY_MORPHOLOGY_ANALYSIS_FIELDS}

    @staticmethod
    def _read_admitted_body_images(
        admitted_body_assets: Sequence[Mapping[str, Any]],
    ) -> list[BodySourceImagePayload]:
        if len(admitted_body_assets) != 5:
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_source_count_invalid"
            )
        images: list[BodySourceImagePayload] = []
        for asset in admitted_body_assets:
            if not isinstance(asset, Mapping):
                raise BodyProportionAnalysisError("body_proportion_analysis_source_invalid")
            metadata = asset.get("metadata")
            metadata = metadata if isinstance(metadata, Mapping) else {}
            role = asset.get("role") or metadata.get("role")
            truth_layer = asset.get("reference_truth_layer") or metadata.get(
                "reference_truth_layer"
            )
            if role != "body_proportion_reference":
                raise BodyProportionAnalysisError("body_proportion_analysis_role_invalid")
            if truth_layer != "body_proportion_truth":
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_truth_layer_invalid"
                )
            if metadata.get("content_stored") is not True or metadata.get(
                "ready_for_v3_runtime"
            ) is not True:
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_source_not_ready"
                )
            for field, error_code in (
                ("source_provenance", "body_proportion_analysis_source_invalid"),
                ("consent_reference", "body_proportion_analysis_source_invalid"),
                ("rights_reference", "body_proportion_analysis_source_invalid"),
            ):
                if not metadata.get(field):
                    raise BodyProportionAnalysisError(error_code)
            source_sha256 = str(metadata.get("source_sha256") or "").strip().lower()
            if len(source_sha256) != 64:
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_source_hash_mismatch"
                )
            raw_path = asset.get("file_path") or metadata.get("file_path")
            if not isinstance(raw_path, str) or not raw_path.strip():
                raise BodyProportionAnalysisError("body_proportion_analysis_source_invalid")
            path = Path(raw_path)
            try:
                content = path.read_bytes()
            except Exception as exc:
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_provider_unavailable"
                ) from exc
            if hashlib.sha256(content).hexdigest() != source_sha256:
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_source_hash_mismatch"
                )
            mime_type = str(asset.get("mime_type") or metadata.get("mime_type") or "").strip().lower()
            if mime_type not in {"image/png", "image/jpeg", "image/webp"}:
                raise BodyProportionAnalysisError("body_proportion_analysis_source_invalid")
            images.append(BodySourceImagePayload(content=content, mime_type=mime_type))
        return images


def _lab_vision_enabled() -> bool:
    """Read the existing V3 lab-vision enablement without owning its config."""

    from ..shared_capabilities.visual_cluster.vision_provider import (
        _lab_vision_enabled as read_lab_vision_enabled,
    )

    return bool(read_lab_vision_enabled())


def _lab_vision_setting(field: str) -> Any:
    """Read only the existing lab-vision route's safe setting fields."""

    from ..shared_capabilities.visual_cluster.vision_provider import (
        _lab_vision_setting as read_lab_vision_setting,
    )

    return read_lab_vision_setting(field)


def create_configured_body_source_analysis_provider() -> (
    OpenAICompatibleBodySourceAnalysisProvider | None
):
    """Construct the Body analyzer only from a complete lab-vision route.

    This is configuration wiring, not generated-output inspection.  It reads
    only the existing lab-vision provider's credential/base/model resolution;
    it never falls back to the DeepSeek text Brain or an image renderer.
    """

    if not _lab_vision_enabled():
        return None
    api_key = _lab_vision_setting("api_key")
    base_url = _lab_vision_setting("base_url")
    model = _lab_vision_setting("model")
    if not all(isinstance(value, str) and value.strip() for value in (api_key, base_url, model)):
        return None
    return OpenAICompatibleBodySourceAnalysisProvider(
        api_key=api_key.strip(),
        base_url=base_url.strip(),
        model=model.strip(),
        profile_version="v2",
    )


class BodyProportionEvidenceProfile(V3BaseModel):
    """Typed, public-safe result of Body-only proportion source analysis."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    contract_version: Literal["body_proportion_evidence_profile_v1"]
    source_mode: Literal["reference_assisted"]
    source_truth_layer: Literal["body_proportion_truth"]
    allowed_bands: BodyProportionEvidenceBands
    source_count: int
    analysis_receipt: BodyProportionAnalysisReceipt

    @field_validator("source_count")
    @classmethod
    def require_five_admitted_sources(cls, value: int) -> int:
        if type(value) is not int or value != 5:
            raise ValueError("body_proportion_analysis_source_count_invalid")
        return value


class BodyMorphologyEvidenceProfile(V3BaseModel):
    """Richer closed Body morphology result for a new observed refresh.

    These are categorical, non-biometric morphology bands.  They deliberately
    do not carry raw source references, measurements, vectors, identity, hair,
    clothing, scene, or provider data.  The v2 contract supersedes the older
    generic ``allowed_bands`` profile for new strict Body refresh attempts.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    contract_version: Literal["body_morphology_evidence_profile_v2"]
    source_mode: Literal["reference_assisted"]
    source_truth_layer: Literal["body_proportion_truth"]
    relative_head_to_stature: Literal[
        "larger",
        "proportional",
        "smaller",
    ]
    shoulder_to_head: Literal[
        "narrower",
        "proportional",
        "wider",
    ]
    torso_to_leg: Literal[
        "shorter_torso",
        "proportional",
        "longer_torso",
    ]
    arm_to_leg: Literal[
        "relatively_shorter",
        "proportional",
        "relatively_longer",
    ]
    build: Literal[
        "slender",
        "medium",
        "sturdy",
    ]
    neck_shoulder: Literal[
        "narrow_transition",
        "proportional_transition",
        "wide_transition",
    ]
    developmental_stage_context: Literal[
        "early_stage_context",
        "middle_stage_context",
        "later_stage_context",
        "adult_stage_context",
        "unknown_stage_context",
    ]
    stance_ground: Literal[
        "grounded_full_contact",
        "toe_weighted_contact",
        "dynamic_contact",
    ]
    cross_view_support: Literal[
        "front_only",
        "front_back_supported",
        "multi_view_supported",
    ]
    source_count: StrictInt
    analysis_receipt: BodyProportionAnalysisReceipt

    @field_validator("source_count")
    @classmethod
    def require_five_admitted_sources(cls, value: int) -> int:
        if type(value) is not int or value != 5:
            raise ValueError("body_proportion_analysis_source_count_invalid")
        return value


class BodyRefreshAnalysisContext(V3BaseModel):
    """One immutable, server-owned analysis result for a Body refresh.

    The context is an in-memory hand-off from the Product API refresh owner to
    the Character Card candidate fan-out.  It deliberately retains the typed
    profile and only safe digests for lifecycle persistence; source paths,
    provenance, upload IDs, and provider responses never belong here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    contract_version: Literal["body_refresh_analysis_context_v1", "body_refresh_analysis_context_v2"] = (
        "body_refresh_analysis_context_v1"
    )
    schema_version: Literal["body_proportion_evidence_profile_v1", "body_morphology_evidence_profile_v2"] = (
        "body_proportion_evidence_profile_v1"
    )
    source_mode: Literal["reference_assisted"]
    attempt_id: StrictStr
    append_only_revision: StrictInt = 1
    source_binding_digest: StrictStr
    source_evidence_id_digest: StrictStr
    profile_digest: StrictStr
    profile: BodyProportionEvidenceProfile | BodyMorphologyEvidenceProfile

    @field_validator("attempt_id")
    @classmethod
    def require_server_attempt_id(cls, value: str) -> str:
        cleaned = value.strip()
        prefix = "body_refresh_attempt_"
        suffix = cleaned[len(prefix):] if cleaned.startswith(prefix) else ""
        if len(suffix) != 32 or any(char not in "0123456789abcdef" for char in suffix):
            raise ValueError("body_refresh_analysis_attempt_invalid")
        return cleaned

    @field_validator("append_only_revision")
    @classmethod
    def require_positive_revision(cls, value: int) -> int:
        if type(value) is not int or value < 1:
            raise ValueError("body_refresh_analysis_revision_invalid")
        return value

    @field_validator("source_binding_digest", "source_evidence_id_digest", "profile_digest")
    @classmethod
    def require_sha256_digest(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if len(cleaned) != 64 or any(char not in "0123456789abcdef" for char in cleaned):
            raise ValueError("body_refresh_analysis_digest_invalid")
        return cleaned

    @model_validator(mode="after")
    def validate_profile_contract(self) -> "BodyRefreshAnalysisContext":
        if self.profile.source_mode != self.source_mode:
            raise ValueError("body_refresh_analysis_profile_source_mode_mismatch")
        expected_context_version = (
            "body_refresh_analysis_context_v2"
            if isinstance(self.profile, BodyMorphologyEvidenceProfile)
            else "body_refresh_analysis_context_v1"
        )
        expected_schema_version = (
            "body_morphology_evidence_profile_v2"
            if isinstance(self.profile, BodyMorphologyEvidenceProfile)
            else "body_proportion_evidence_profile_v1"
        )
        if self.contract_version != expected_context_version or self.schema_version != expected_schema_version:
            raise ValueError("body_refresh_analysis_context_schema_mismatch")
        expected_profile_digest = hashlib.sha256(
            json.dumps(
                self.profile.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if self.profile_digest != expected_profile_digest:
            raise ValueError("body_refresh_analysis_profile_digest_mismatch")
        return self

    @classmethod
    def from_analysis(
        cls,
        *,
        attempt_id: str,
        append_only_revision: int,
        admitted_body_assets: Sequence[BodySourceAnalysisAssetEnvelope],
        profile: BodyProportionEvidenceProfile | BodyMorphologyEvidenceProfile,
    ) -> "BodyRefreshAnalysisContext":
        if len(admitted_body_assets) != 5:
            raise ValueError("body_refresh_analysis_source_count_invalid")
        source_ids = [asset.asset_id for asset in admitted_body_assets]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("body_refresh_analysis_source_ids_invalid")
        source_binding = [asset.source_sha256 for asset in admitted_body_assets]
        source_binding_digest = hashlib.sha256(
            json.dumps(source_binding, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        source_evidence_id_digest = hashlib.sha256(
            json.dumps(source_ids, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        profile_digest = hashlib.sha256(
            json.dumps(
                profile.model_dump(mode="json"),
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        is_morphology_v2 = isinstance(profile, BodyMorphologyEvidenceProfile)
        return cls(
            contract_version=(
                "body_refresh_analysis_context_v2"
                if is_morphology_v2
                else "body_refresh_analysis_context_v1"
            ),
            schema_version=(
                "body_morphology_evidence_profile_v2"
                if is_morphology_v2
                else "body_proportion_evidence_profile_v1"
            ),
            source_mode="reference_assisted",
            attempt_id=attempt_id,
            append_only_revision=append_only_revision,
            source_binding_digest=source_binding_digest,
            source_evidence_id_digest=source_evidence_id_digest,
            profile_digest=profile_digest,
            profile=profile,
        )

    def safe_metadata(self) -> dict[str, Any]:
        """Return the only context projection allowed into a job record."""

        return {
            "contract_version": self.contract_version,
            "schema_version": self.schema_version,
            "source_mode": self.source_mode,
            "attempt_id": self.attempt_id,
            "append_only_revision": self.append_only_revision,
            "source_binding_digest": self.source_binding_digest,
            "source_evidence_id_digest": self.source_evidence_id_digest,
            "profile_digest": self.profile_digest,
        }


def require_explicit_body_morphology_profile_version(profile_version: str) -> str:
    """Require the new morphology contract at a fresh strict Body boundary."""

    if profile_version != "v2":
        raise ValueError("body_refresh_analysis_profile_version_v2_required")
    return profile_version


def require_current_body_refresh_analysis_context(
    context: BodyRefreshAnalysisContext,
) -> BodyRefreshAnalysisContext:
    """Reject generic v1 contexts for new strict attempts/resume."""

    if not isinstance(context, BodyRefreshAnalysisContext):
        raise ValueError("body_refresh_analysis_context_superseded")
    if (
        context.contract_version != "body_refresh_analysis_context_v2"
        or context.schema_version != "body_morphology_evidence_profile_v2"
        or not isinstance(context.profile, BodyMorphologyEvidenceProfile)
    ):
        raise ValueError("body_refresh_analysis_context_superseded")
    return context


class BodyProportionSourceAnalysisAdapter:
    """Validate admitted Body inputs and one injected source-analysis result.

    The injected provider/callable is the real Vision/source-analysis
    integration point.
    There is intentionally no default deterministic analyzer: without a real
    result this adapter raises ``body_proportion_analysis_missing``.
    """

    def analyze(
        self,
        admitted_body_assets: Sequence[Mapping[str, Any]],
        *,
        source_mode: str,
        profile_version: str,
        analyzer: BodySourceAnalysisProvider
        | Callable[[Sequence[Mapping[str, Any]]], Mapping[str, Any]]
        | None,
    ) -> BodyProportionEvidenceProfile:
        if source_mode != "reference_assisted":
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_source_mode_invalid"
            )
        self._validate_admitted_body_assets(admitted_body_assets)
        if analyzer is None:
            raise BodyProportionAnalysisError("body_proportion_analysis_missing")
        try:
            if callable(analyzer):
                raw_profile = analyzer(tuple(admitted_body_assets))
            else:
                raw_profile = analyzer.analyze(tuple(admitted_body_assets))
            profile_model = (
                BodyMorphologyEvidenceProfile
                if profile_version == "v2"
                else BodyProportionEvidenceProfile
            )
            profile = profile_model.model_validate(raw_profile)
        except BodyProportionAnalysisError as exc:
            code = str(exc)
            if code in _CLOSED_ANALYSIS_ERROR_CODES:
                raise
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_provider_unavailable"
            ) from exc
        except (ValidationError, TypeError, ValueError) as exc:
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_profile_invalid"
            ) from exc
        except Exception as exc:
            # Provider availability/transport failures are closed at this
            # boundary.  Do not leak provider exception text or pretend that
            # a partition/count was a completed analysis.
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_provider_unavailable"
            ) from exc
        if profile.source_mode != source_mode:
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_source_mode_invalid"
            )
        return profile

    @staticmethod
    def _validate_admitted_body_assets(
        admitted_body_assets: Sequence[Mapping[str, Any]],
    ) -> None:
        if len(admitted_body_assets) != 5:
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_source_count_invalid"
            )
        for asset in admitted_body_assets:
            if not isinstance(asset, Mapping):
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_source_invalid"
                )
            if asset.get("role") != "body_proportion_reference":
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_role_invalid"
                )
            metadata = asset.get("metadata")
            truth_layer = asset.get("reference_truth_layer")
            if isinstance(metadata, Mapping):
                truth_layer = truth_layer or metadata.get("reference_truth_layer")
            if truth_layer != "body_proportion_truth":
                raise BodyProportionAnalysisError(
                    "body_proportion_analysis_truth_layer_invalid"
                )
