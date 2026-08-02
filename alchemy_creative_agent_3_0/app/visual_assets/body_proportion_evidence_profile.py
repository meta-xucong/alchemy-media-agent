"""Closed Body proportion evidence/profile contracts.

This module owns the boundary between server-admitted Body evidence and the
Brain/body-generation request.  It does not infer proportions from a count,
hash, or metadata-only partition.  A caller must supply a real source-analysis
adapter; when none is available the boundary fails closed.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any, Callable, Literal, Protocol

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
