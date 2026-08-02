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

from pydantic import ConfigDict, ValidationError, field_validator

from ..schemas.models import V3BaseModel


class BodyProportionAnalysisError(ValueError):
    """Closed failure raised when Body source analysis cannot be trusted."""


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
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model

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
                text={"format": {"type": "json_object"}},
                timeout=timeout_seconds,
                max_output_tokens=1200,
            )
        except Exception as exc:
            raise RuntimeError("body source analysis transport failed") from exc
        output_text = str(getattr(response, "output_text", "") or "").strip()
        if not output_text:
            raise ValueError("body source analysis response was empty")
        try:
            return json.loads(output_text)
        except (TypeError, ValueError) as exc:
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
    _ANALYSIS_INSTRUCTIONS = (
        "Analyze exactly these five admitted Body proportion reference images "
        "for a similar-person Body-only modeling context. Return strict JSON "
        "with exactly one key, allowed_bands, containing only these seven closed "
        "dimensions: head_body_scale, neck_shoulder, torso_limb, arm_leg, "
        "developmental_stage, stance_ground, cross_view_support. Use only the "
        "declared categorical bands. Do not analyze or return Face identity, "
        "hair, wardrobe, scene, lighting, camera, expression, pose style, "
        "provider details, paths, IDs, URLs, raw image data, or biometric data."
    )

    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str | None,
        model: str | None,
        timeout_seconds: float = 90.0,
        transport: BodySourceAnalysisTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.transport = transport or (
            OpenAICompatibleBodySourceAnalysisTransport(
                api_key=api_key or "",
                base_url=base_url or "",
                model=model or "",
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
                instructions=self._ANALYSIS_INSTRUCTIONS,
                timeout_seconds=self.timeout_seconds,
            )
        except BodyProportionAnalysisError:
            raise
        except Exception as exc:
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_provider_unavailable"
            ) from exc
        try:
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
            raise BodyProportionAnalysisError(
                "body_proportion_analysis_profile_invalid"
            ) from exc
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
            profile = BodyProportionEvidenceProfile.model_validate(raw_profile)
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
