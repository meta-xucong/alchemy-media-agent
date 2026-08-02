"""Red tests for the server-owned Body proportion evidence/profile boundary.

Correction model
----------------
The previous reference-partition change correctly keeps five admitted Body
references out of physical ImageGen inputs, but that is only input isolation.
It does not prove that a Body owner has analysed those references or that the
result reaches a Brain/body-generation request.  This feature therefore needs
one typed source-analysis boundary between the admitted Body evidence and the
Brain request.

The intended owner is a server-owned Body proportion analyzer/receipt
projector, consumed by the Brain/body-generation request builder.  The
profile is not a partition/hash receipt and must contain only closed bands for
head/body scale, neck/shoulder, torso/limb, arm/leg, developmental stage,
stance/ground contact, and cross-view support.  It must never carry raw paths,
URLs, asset/output/provider IDs, base64, biometric vectors, wardrobe, hair,
scene, expression, or photography-channel data.

This file intentionally starts red against the current implementation.  It
also locks isolation: inference-first, ordinary, and Face-only requests do
not inherit observed Body proportion evidence, while legacy requests without
the new profile remain readable.
"""

from __future__ import annotations

from copy import deepcopy
import json
from types import SimpleNamespace
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.llm_brain.adapter import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.shared_capabilities.activation import CapabilityActivationError
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    BodyProportionAnalysisError,
    BodyProportionEvidenceProfile,
    BodyProportionSourceAnalysisAdapter,
    BodySourceAnalysisAssetEnvelope,
    ConfiguredBodySourceAnalysisProvider,
)


_PROFILE_KEY = "professional_body_proportion_evidence_profile"
_PROFILE_VERSION = "body_proportion_evidence_profile_v1"
_ALLOWED_PROFILE_KEYS = {
    "contract_version",
    "source_mode",
    "source_truth_layer",
    "allowed_bands",
    "source_count",
    "analysis_receipt",
}
_ALLOWED_BANDS = {
    "head_body_scale",
    "neck_shoulder",
    "torso_limb",
    "arm_leg",
    "developmental_stage",
    "stance_ground",
    "cross_view_support",
}
_EXPECTED_BAND_VALUES = {
    "head_body_scale": "balanced_child_scale",
    "neck_shoulder": "balanced_child_transition",
    "torso_limb": "balanced_child_torso_limb",
    "arm_leg": "balanced_child_arm_leg",
    "developmental_stage": "early_childhood_coherent",
    "stance_ground": "grounded_full_contact",
    "cross_view_support": "front_back_supported",
}
_CLOSED_BAND_VALUES = {
    "head_body_scale": {"compact_child_scale", "balanced_child_scale", "elongated_child_scale"},
    "neck_shoulder": {
        "narrow_child_transition",
        "balanced_child_transition",
        "broad_child_transition",
    },
    "torso_limb": {
        "short_child_torso_limb",
        "balanced_child_torso_limb",
        "long_child_torso_limb",
    },
    "arm_leg": {"short_child_arm_leg", "balanced_child_arm_leg", "long_child_arm_leg"},
    "developmental_stage": {
        "early_childhood_coherent",
        "middle_childhood_coherent",
        "adolescent_coherent",
    },
    "stance_ground": {"grounded_full_contact", "toe_weighted_contact", "dynamic_contact"},
    "cross_view_support": {"front_only", "front_back_supported", "multi_view_supported"},
}
_FORBIDDEN_TOKENS = {
    "path",
    "url",
    "asset_id",
    "output_id",
    "provider_id",
    "provider_payload",
    "base64",
    "biometric",
    "wardrobe",
    "hair",
    "scene",
    "expression",
    "lighting",
    "camera",
    "photography",
}


def _body_evidence_assets() -> list[dict[str, Any]]:
    return [
        {
            "asset_id": f"body-reference-{index}",
            "role": "body_proportion_reference",
            "reference_truth_layer": "body_proportion_truth",
            "file_path": f"C:/private/body-reference-{index}.png",
            "url": f"https://private.invalid/body-reference-{index}",
            "output_id": f"output-{index}",
            "provider_id": "provider-private",
            "provider_input_required": False,
            "base64": "must-not-cross-boundary",
        }
        for index in range(5)
    ]


def _reference_assisted_metadata() -> dict[str, Any]:
    return {
        "professional_mode": True,
        "professional_body_proportion_receipt_required": True,
        "local_mcp_professional_relay": True,
        "professional_body_proportion_contract_source": (
            "server_owned_professional_binding_resolver"
        ),
        "professional_mode_binding_record": {
            "server_owned_binding_resolver_validated": True,
        },
        "professional_character_card_preparation": True,
        "professional_character_card_stage": "body_silhouette",
        "professional_character_card_slot": "body.front_full",
        "professional_character_card_body_refresh_source_mode": "reference_assisted",
        "professional_character_card_body_model_context": (
            "similar_person_body_reference_assisted_v1"
        ),
        "professional_anchor_reference_assets": _body_evidence_assets(),
    }


def _trusted_internal_source_analysis_assets() -> list[BodySourceAnalysisAssetEnvelope]:
    """Build the server-owned analyzer proof used by legacy runtime seams."""

    return [
        BodySourceAnalysisAssetEnvelope(
            asset_id=f"v3-body-source-{index}",
            role="body_proportion_reference",
            reference_truth_layer="body_proportion_truth",
            file_path=f"C:/private/body-source-{index}.png",
            mime_type="image/png",
            source_sha256=(f"{index + 1:02x}" * 32),
            source_provenance="user_provided_body_reference",
            consent_reference="consent-body-reference",
            rights_reference="rights-body-reference",
        )
        for index in range(5)
    ]


def _fake_body_owner_source_analysis(body_assets: list[dict[str, Any]]) -> dict[str, Any]:
    """Deterministic source-analysis seam used to expose the missing owner.

    This fake deliberately consumes admitted Body assets but emits only the
    future closed receipt.  It does not claim to run pixel/Vision analysis;
    the production implementation must replace this seam before final
    reference-assisted refresh is allowed.
    """

    assert len(body_assets) == 5
    assert all(asset["role"] == "body_proportion_reference" for asset in body_assets)
    assert all(asset["reference_truth_layer"] == "body_proportion_truth" for asset in body_assets)
    return {
        "contract_version": _PROFILE_VERSION,
        "source_mode": "reference_assisted",
        "source_truth_layer": "body_proportion_truth",
        "allowed_bands": {
            **_EXPECTED_BAND_VALUES,
        },
        "source_count": 5,
        "analysis_receipt": {
            "owner": "server_owned_body_proportion_analysis",
            "status": "complete",
            "analysis_provider": "configured_body_source_analysis_provider",
        },
    }


def _trusted_internal_body_analysis_metadata() -> dict[str, Any]:
    metadata = _reference_assisted_metadata()
    metadata["professional_body_proportion_analysis_receipt"] = BodyProportionSourceAnalysisAdapter().analyze(
        metadata["professional_anchor_reference_assets"],
        source_mode="reference_assisted",
        analyzer=lambda assets: _fake_body_owner_source_analysis(
            list(assets)
        ),
    )
    return metadata


def test_body_source_analysis_adapter_requires_real_analyzer_output() -> None:
    metadata = _reference_assisted_metadata()

    with pytest.raises(BodyProportionAnalysisError, match="body_proportion_analysis_missing"):
        BodyProportionSourceAnalysisAdapter().analyze(
            metadata["professional_anchor_reference_assets"],
            source_mode="reference_assisted",
            analyzer=None,
        )


def test_configured_body_source_provider_is_the_explicit_real_analyzer_boundary() -> None:
    metadata = _reference_assisted_metadata()
    calls: list[int] = []
    provider = ConfiguredBodySourceAnalysisProvider(
        lambda assets: (
            calls.append(len(assets))
            or _fake_body_owner_source_analysis(list(assets))
        )
    )

    profile = BodyProportionSourceAnalysisAdapter().analyze(
        metadata["professional_anchor_reference_assets"],
        source_mode="reference_assisted",
        analyzer=provider,
    )

    assert isinstance(profile, BodyProportionEvidenceProfile)
    assert calls == [5]


def _typed_profile_as_dict() -> dict[str, Any]:
    metadata = _trusted_internal_body_analysis_metadata()
    profile = metadata["professional_body_proportion_analysis_receipt"]
    assert isinstance(profile, BodyProportionEvidenceProfile)
    return profile.model_dump(mode="json")


def _build_body_brain_request(metadata: dict[str, Any], *, stage: str = "generate"):
    return V3LLMBrainAdapter().build_request(
        user_input="Build the professional Body Silhouette request.",
        job_id="job-body-proportion-profile-red-test",
        stage=stage,
        scenario_id="general_creative",
        template_id="general_template",
        metadata=metadata,
    )


def _assert_no_forbidden_profile_data(value: Any) -> None:
    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True).lower()
    for token in _FORBIDDEN_TOKENS:
        assert token not in serialized


def test_five_admitted_body_refs_become_typed_profile_consumed_by_brain_body_request() -> None:
    metadata = _trusted_internal_body_analysis_metadata()
    request = _build_body_brain_request(metadata)

    context = request.metadata["professional_body_proportion_server_context"]
    profile = context["body_proportion_evidence_profile"]

    assert set(profile) == _ALLOWED_PROFILE_KEYS
    assert profile["contract_version"] == _PROFILE_VERSION
    assert profile["source_mode"] == "reference_assisted"
    assert profile["source_truth_layer"] == "body_proportion_truth"
    assert set(profile["allowed_bands"]) == _ALLOWED_BANDS
    assert profile["allowed_bands"] == _EXPECTED_BAND_VALUES
    for dimension, value in profile["allowed_bands"].items():
        assert value in _CLOSED_BAND_VALUES[dimension]
    assert profile["source_count"] == 5
    assert profile["analysis_receipt"] == {
        "owner": "server_owned_body_proportion_analysis",
        "status": "complete",
        "analysis_provider": "configured_body_source_analysis_provider",
    }
    _assert_no_forbidden_profile_data(profile)


def test_public_metadata_cannot_forge_completed_body_profile() -> None:
    metadata = _reference_assisted_metadata()
    metadata["professional_body_proportion_evidence_profile"] = _fake_body_owner_source_analysis(
        metadata["professional_anchor_reference_assets"]
    )

    with pytest.raises(ValueError, match="body_proportion_analysis_untrusted"):
        _build_body_brain_request(metadata)


def test_product_api_treats_analysis_receipt_as_server_owned_metadata() -> None:
    assert "professional_body_proportion_analysis_receipt" in (
        V3ProductApiService._SERVER_OWNED_RUNTIME_METADATA
    )

    service = object.__new__(V3ProductApiService)
    request = type("PublicRequest", (), {"metadata": {
        "professional_body_proportion_analysis_receipt": {
            "profile": _fake_body_owner_source_analysis(_body_evidence_assets()),
        }
    }})()

    with pytest.raises(ValueError, match="runtime_metadata_server_owned"):
        service._assert_runtime_metadata_server_owned(  # noqa: SLF001
            request,
            trusted_capability_plan_reuse=False,
            trusted_professional_character_card=False,
            trusted_professional_anchor_preparation=False,
        )


def test_reference_assisted_without_server_owned_analysis_receipt_fails_closed() -> None:
    metadata = _reference_assisted_metadata()

    with pytest.raises(ValueError, match="body_proportion_analysis_missing"):
        _build_body_brain_request(metadata)


def test_partition_hash_or_raw_refs_alone_cannot_be_promoted_to_complete_profile() -> None:
    partition_only = _reference_assisted_metadata()
    partition_only.pop("professional_anchor_reference_assets")
    partition_only["body_mcp_reference_partition"] = {
        "contract_version": "body_mcp_reference_partition_v1",
        "body_proportion_reference": {
            "asset_count": 5,
            "asset_hashes": [f"body-hash-{index}" for index in range(5)],
        },
    }
    raw_refs_only = _reference_assisted_metadata()

    for metadata in (partition_only, raw_refs_only):
        with pytest.raises(ValueError, match="body_proportion_analysis_missing"):
            _build_body_brain_request(metadata)


@pytest.mark.parametrize(
    ("mutation", "error_code"),
    [
        (
            lambda profile: profile.update({"source_mode": "inference_first"}),
            "body_proportion_analysis_source_mode_invalid",
        ),
        (
            lambda profile: profile.update({"source_truth_layer": "identity_continuity"}),
            "body_proportion_analysis_truth_layer_invalid",
        ),
        (
            lambda profile: profile.update({"source_count": 4}),
            "body_proportion_analysis_source_count_invalid",
        ),
        (
            lambda profile: profile["allowed_bands"].update({"hair": "short"}),
            "body_proportion_analysis_band_invalid",
        ),
        (
            lambda profile: profile.update({"file_path": "C:/private/raw.png"}),
            "body_proportion_analysis_field_forbidden",
        ),
    ],
)
def test_trusted_body_analysis_receipt_is_closed_and_validated(mutation, error_code: str) -> None:
    metadata = _reference_assisted_metadata()
    profile = _typed_profile_as_dict()
    mutation(profile)
    metadata["professional_body_proportion_analysis_receipt"] = profile

    with pytest.raises(ValueError, match="body_proportion_analysis_untrusted"):
        _build_body_brain_request(metadata)


def test_trusted_observed_profile_cannot_cross_into_inference_first() -> None:
    metadata = _trusted_internal_body_analysis_metadata()
    metadata["professional_character_card_body_refresh_source_mode"] = "inference_first"

    with pytest.raises(ValueError, match="body_proportion_analysis_source_mode_invalid"):
        _build_body_brain_request(metadata)


def test_trusted_observed_profile_is_strict_body_stage_only() -> None:
    metadata = _trusted_internal_body_analysis_metadata()
    metadata["professional_character_card_stage"] = "expression_set"
    metadata["professional_character_card_slot"] = "expression.front"

    with pytest.raises(ValueError, match="body_proportion_analysis_stage_invalid"):
        _build_body_brain_request(metadata)


def test_ordinary_mcp_with_same_internal_field_does_not_project_observed_profile() -> None:
    metadata = _trusted_internal_body_analysis_metadata()
    metadata.pop("professional_mode")
    metadata.pop("professional_body_proportion_receipt_required")
    metadata.pop("local_mcp_professional_relay")
    metadata.pop("professional_body_proportion_contract_source")
    metadata.pop("professional_mode_binding_record")

    request = _build_body_brain_request(metadata)

    assert "professional_body_proportion_server_context" not in request.metadata


def test_inference_first_does_not_project_observed_body_profile() -> None:
    metadata = _reference_assisted_metadata()
    metadata["professional_character_card_body_refresh_source_mode"] = "inference_first"
    metadata.pop("professional_anchor_reference_assets")

    request = _build_body_brain_request(metadata)

    assert _PROFILE_KEY not in request.metadata


def test_ordinary_and_face_identity_requests_do_not_inherit_body_profile() -> None:
    ordinary = _build_body_brain_request(
        {
            "professional_anchor_reference_assets": _body_evidence_assets(),
        }
    )
    face_only = _build_body_brain_request(
        {
            "professional_mode": True,
            "professional_character_card_body_refresh_source_mode": "inference_first",
            "professional_anchor_reference_assets": [
                {
                    "role": "face_reference",
                    "reference_truth_layer": "identity_continuity",
                }
            ],
        }
    )

    assert _PROFILE_KEY not in ordinary.metadata
    assert _PROFILE_KEY not in face_only.metadata


def test_legacy_readback_without_profile_remains_compatible() -> None:
    request = _build_body_brain_request(
        {
            "professional_character_card_body_refresh_source_mode": "inference_first",
        }
    )

    assert _PROFILE_KEY not in request.metadata


@pytest.mark.parametrize(
    "mutation",
    [
        lambda profile: profile.update({"source_mode": "inference_first"}),
        lambda profile: profile.update({"source_truth_layer": "identity_continuity"}),
        lambda profile: profile.update({"source_count": 4}),
        lambda profile: profile["allowed_bands"].update({"head_body_scale": "not_a_closed_band"}),
        lambda profile: profile.update({"raw_path": "C:/private/body.png"}),
        lambda profile: profile["analysis_receipt"].update({"analysis_provider": "provider-id-raw"}),
    ],
)
def test_body_source_analyzer_output_schema_is_validated_before_projection(mutation) -> None:
    metadata = _reference_assisted_metadata()
    raw_profile = _fake_body_owner_source_analysis(
        metadata["professional_anchor_reference_assets"]
    )
    mutation(raw_profile)

    with pytest.raises(BodyProportionAnalysisError, match="body_proportion_analysis_profile_invalid"):
        BodyProportionSourceAnalysisAdapter().analyze(
            metadata["professional_anchor_reference_assets"],
            source_mode="reference_assisted",
            analyzer=lambda _assets: deepcopy(raw_profile),
        )


class _FakeBodySourceAnalysisProvider:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], ...]] = []

    def analyze(self, admitted_body_assets):
        self.calls.append(tuple(dict(asset) for asset in admitted_body_assets))
        return _fake_body_owner_source_analysis(list(admitted_body_assets))


class _UnavailableBodySourceAnalysisProvider:
    def analyze(self, _admitted_body_assets):
        raise RuntimeError("provider transport details must stay private")


class _CapturingBrainAdapter:
    def __init__(self) -> None:
        self.request_metadata: dict[str, Any] | None = None

    def build_request(self, *, metadata, scenario_id, **_kwargs):
        self.request_metadata = metadata
        return SimpleNamespace(metadata=metadata, scenario_id=scenario_id)

    def run(self, _request):
        return object()


def test_runtime_body_owner_call_site_consumes_admitted_refs_through_injected_provider() -> None:
    provider = _FakeBodySourceAnalysisProvider()
    runtime = ScenarioRuntime(body_proportion_source_analyzer=provider)

    profile = runtime._body_proportion_profile_for_brain(  # noqa: SLF001
        SimpleNamespace(
            metadata=_reference_assisted_metadata(),
            body_source_analysis_assets=_trusted_internal_source_analysis_assets(),
        ),
        stage="plan",
    )

    assert isinstance(profile, BodyProportionEvidenceProfile)
    assert len(provider.calls) == 1
    assert len(provider.calls[0]) == 5
    assert all(asset["role"] == "body_proportion_reference" for asset in provider.calls[0])
    _assert_no_forbidden_profile_data(profile.model_dump(mode="json"))


def test_runtime_body_owner_call_site_without_configured_provider_fails_closed() -> None:
    runtime = ScenarioRuntime()

    with pytest.raises(CapabilityActivationError, match="body_proportion_analysis_missing"):
        runtime._body_proportion_profile_for_brain(  # noqa: SLF001
            SimpleNamespace(
                metadata=_reference_assisted_metadata(),
                body_source_analysis_assets=_trusted_internal_source_analysis_assets(),
            ),
            stage="plan",
        )


def test_body_source_provider_unavailable_fails_closed_without_raw_error_projection() -> None:
    metadata = _reference_assisted_metadata()

    with pytest.raises(
        BodyProportionAnalysisError,
        match="body_proportion_analysis_provider_unavailable",
    ):
        BodyProportionSourceAnalysisAdapter().analyze(
            metadata["professional_anchor_reference_assets"],
            source_mode="reference_assisted",
            analyzer=_UnavailableBodySourceAnalysisProvider(),
        )


def test_runtime_forwards_only_typed_profile_and_rejects_raw_projection() -> None:
    provider = _FakeBodySourceAnalysisProvider()
    runtime = ScenarioRuntime(body_proportion_source_analyzer=provider)
    metadata = _reference_assisted_metadata()
    typed_profile = _trusted_internal_body_analysis_metadata()[
        "professional_body_proportion_analysis_receipt"
    ]
    metadata["professional_body_proportion_analysis_receipt"] = typed_profile

    resolved = runtime._body_proportion_profile_for_brain(  # noqa: SLF001
        SimpleNamespace(metadata=metadata),
        stage="plan",
    )
    assert resolved is typed_profile
    assert provider.calls == []

    metadata["professional_body_proportion_analysis_receipt"] = typed_profile.model_dump(mode="json")
    with pytest.raises(CapabilityActivationError, match="body_proportion_analysis_untrusted"):
        runtime._body_proportion_profile_for_brain(  # noqa: SLF001
            SimpleNamespace(metadata=metadata),
            stage="plan",
        )


def test_runtime_run_llm_brain_forwards_injected_profile_into_brain_request(monkeypatch) -> None:
    provider = _FakeBodySourceAnalysisProvider()
    brain_adapter = _CapturingBrainAdapter()
    runtime = ScenarioRuntime(
        body_proportion_source_analyzer=provider,
        llm_brain_adapter=brain_adapter,
    )
    request = type("RuntimeRequest", (), {})()
    request.metadata = _reference_assisted_metadata()
    request.body_source_analysis_assets = _trusted_internal_source_analysis_assets()
    request.user_input = "Build a Body Silhouette request."
    request.product_profile = {}
    request.uploaded_assets = []
    request.uploaded_asset_ids = []
    resolution = SimpleNamespace(
        manifest=SimpleNamespace(scenario_id="general_creative"),
    )
    monkeypatch.setattr(
        runtime,
        "_frozen_remote_creative_brain_for_execution",
        lambda _request, _resolution, **_kwargs: None,
    )
    monkeypatch.setattr(
        runtime,
        "_brain_runtime_metadata",
        lambda _request, _resolution, **_kwargs: dict(_request.metadata),
    )
    monkeypatch.setattr(runtime, "_runtime_job_id", lambda *_args: "job-body-profile")
    monkeypatch.setattr(runtime, "_template_id", lambda *_args: "general_template")

    result = runtime._run_llm_brain(  # noqa: SLF001
        request,
        resolution,
        None,
        stage="plan",
    )

    assert result is not None
    assert brain_adapter.request_metadata is not None
    forwarded = brain_adapter.request_metadata[
        "professional_body_proportion_analysis_receipt"
    ]
    assert isinstance(forwarded, BodyProportionEvidenceProfile)
    assert len(provider.calls) == 1
