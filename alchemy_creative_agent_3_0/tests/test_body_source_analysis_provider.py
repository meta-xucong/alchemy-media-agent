"""Deterministic tests for the transient Body source-image analyzer.

The analyzer is a source-analysis boundary, not the existing generated-output
Vision review adapter and not a metadata/count-to-bands shortcut.  A real
provider may read five admitted Body files only during the call; its public
result is a closed seven-band Body profile with no paths, IDs, base64, raw
response, or physical renderer references.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pytest

# Load the established V3 application boundary first.  The shared visual
# package has an existing import-order dependency around CharacterCard; this
# keeps collection focused on the analyzer contract rather than that legacy
# module initialization detail.
from alchemy_creative_agent_3_0.app.llm_brain.adapter import V3LLMBrainAdapter  # noqa: F401
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    BodyProportionAnalysisError,
    BodyProportionEvidenceProfile,
    OpenAICompatibleBodySourceAnalysisProvider,
)


_BANDS = {
    "head_body_scale": "balanced_child_scale",
    "neck_shoulder": "balanced_child_transition",
    "torso_limb": "balanced_child_torso_limb",
    "arm_leg": "balanced_child_arm_leg",
    "developmental_stage": "early_childhood_coherent",
    "stance_ground": "grounded_full_contact",
    "cross_view_support": "front_back_supported",
}
_FORBIDDEN_OUTPUT_TOKENS = (
    "file_path",
    "path",
    "url",
    "asset_id",
    "output_id",
    "provider_id",
    "base64",
    "biometric",
    "wardrobe",
    "hair",
    "scene",
    "lighting",
    "camera",
    "expression",
    "reference_assets",
)


def _body_assets(tmp_path: Path) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    for index in range(5):
        path = tmp_path / f"body-{index}.png"
        content = f"body-image-{index}".encode("utf-8")
        path.write_bytes(content)
        assets.append(
            {
                "asset_id": f"v3_asset_private_{index}",
                "role": "body_proportion_reference",
                "status": "ready",
                "mime_type": "image/png",
                "file_path": str(path),
                "metadata": {
                    "reference_truth_layer": "body_proportion_truth",
                    "body_reference_policy": "body_scale_neck_shoulder_torso_limb_developmental_stage_only",
                    "body_reference_channel": "body_proportion_reference",
                    "source_sha256": hashlib.sha256(content).hexdigest(),
                    "subject_binding": {"server_bound": True},
                    "source_provenance": {"user_provided": True},
                    "consent_reference": "present",
                    "rights_reference": "present",
                    "content_stored": True,
                    "ready_for_v3_runtime": True,
                },
            }
        )
    return assets


class _FakeAnalysisTransport:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response = response if response is not None else {"allowed_bands": dict(_BANDS)}
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def analyze(self, images, *, instructions: str, timeout_seconds: float):
        self.calls.append(
            {
                "images": tuple(images),
                "instructions": instructions,
                "timeout_seconds": timeout_seconds,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


def _provider(transport: _FakeAnalysisTransport) -> OpenAICompatibleBodySourceAnalysisProvider:
    return OpenAICompatibleBodySourceAnalysisProvider(
        api_key=None,
        base_url=None,
        model="test-body-source-analysis",
        transport=transport,
    )


def test_five_admitted_body_files_are_transiently_analyzed_into_closed_profile(tmp_path: Path) -> None:
    transport = _FakeAnalysisTransport()
    profile_payload = _provider(transport).analyze(_body_assets(tmp_path))
    profile = BodyProportionEvidenceProfile.model_validate(profile_payload)

    assert profile.source_mode == "reference_assisted"
    assert profile.source_truth_layer == "body_proportion_truth"
    assert profile.source_count == 5
    assert profile.allowed_bands.model_dump(mode="json") == _BANDS
    assert profile.analysis_receipt.analysis_provider == (
        "configured_body_source_analysis_provider"
    )
    assert len(transport.calls) == 1
    assert len(transport.calls[0]["images"]) == 5
    assert all(item.content for item in transport.calls[0]["images"])
    assert all(item.mime_type == "image/png" for item in transport.calls[0]["images"])
    instructions = transport.calls[0]["instructions"]
    for dimension in _BANDS:
        assert dimension in instructions
    serialized = profile.model_dump_json().lower()
    for token in _FORBIDDEN_OUTPUT_TOKENS:
        assert token not in serialized


def test_missing_body_source_provider_credentials_fail_closed(tmp_path: Path) -> None:
    provider = OpenAICompatibleBodySourceAnalysisProvider(
        api_key=None,
        base_url=None,
        model=None,
    )

    with pytest.raises(
        BodyProportionAnalysisError,
        match="body_proportion_analysis_provider_unavailable",
    ):
        provider.analyze(_body_assets(tmp_path))


def test_body_source_transport_timeout_is_closed_without_raw_error(tmp_path: Path) -> None:
    transport = _FakeAnalysisTransport(error=TimeoutError("private transport detail"))

    with pytest.raises(
        BodyProportionAnalysisError,
        match="body_proportion_analysis_provider_unavailable",
    ):
        _provider(transport).analyze(_body_assets(tmp_path))


@pytest.mark.parametrize(
    "response",
    [
        "{not-json",
        {"allowed_bands": {**_BANDS, "arm_leg": "not-a-closed-band"}},
        {"allowed_bands": dict(_BANDS), "raw_path": "C:/private/body.png"},
        {"allowed_bands": dict(_BANDS), "asset_id": "v3_asset_private_0"},
    ],
)
def test_body_source_invalid_json_or_schema_fails_closed(
    tmp_path: Path,
    response: Any,
) -> None:
    transport = _FakeAnalysisTransport(response=response)

    with pytest.raises(
        BodyProportionAnalysisError,
        match="body_proportion_analysis_profile_invalid",
    ):
        _provider(transport).analyze(_body_assets(tmp_path))


def test_body_source_requires_exactly_five_ready_body_truth_assets(tmp_path: Path) -> None:
    assets = _body_assets(tmp_path)
    assets[0]["metadata"]["ready_for_v3_runtime"] = False

    with pytest.raises(BodyProportionAnalysisError, match="source_not_ready"):
        _provider(_FakeAnalysisTransport()).analyze(assets)

    with pytest.raises(BodyProportionAnalysisError, match="source_count_invalid"):
        _provider(_FakeAnalysisTransport()).analyze(assets[:4])


def test_body_source_result_does_not_create_physical_face_or_mcp_inputs(tmp_path: Path) -> None:
    profile = _provider(_FakeAnalysisTransport()).analyze(_body_assets(tmp_path))
    assert "reference_assets" not in profile
    assert "face_identity_reference" not in profile
    assert "body_proportion_reference" not in profile
