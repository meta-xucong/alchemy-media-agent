"""Deterministic tests for the transient Body source-image analyzer.

The analyzer is a source-analysis boundary, not the existing generated-output
Vision review adapter and not a metadata/count-to-bands shortcut.  A real
provider may read five admitted Body files only during the call; its public
result is a closed seven-band Body profile with no paths, IDs, base64, raw
response, or physical renderer references.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace
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
    BodySourceImagePayload,
    OpenAICompatibleBodySourceAnalysisProvider,
    OpenAICompatibleBodySourceAnalysisTransport,
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


def test_invalid_output_text_exposes_only_safe_response_shape_projection(tmp_path: Path) -> None:
    response = {"allowed_bands": {**_BANDS, "unexpected": "closed"}}
    provider = _provider(_FakeAnalysisTransport(response=response))

    with pytest.raises(
        BodyProportionAnalysisError,
        match="body_proportion_analysis_profile_invalid",
    ):
        provider.analyze(_body_assets(tmp_path))

    projection = provider.last_response_shape_projection
    assert projection == {
        "output_text_present": False,
        "output_text_type": "absent",
        "json_parse_status": "not_applicable",
        "response_top_level_type": "object",
        "response_top_level_keys": ["allowed_bands"],
        "response_unknown_field_count": 0,
        "response_missing_field_count": 0,
        "allowed_bands_type": "object",
        "allowed_bands_keys": sorted((*_BANDS, "unexpected")),
        "allowed_bands_unknown_field_count": 1,
        "allowed_bands_missing_field_count": 0,
        "schema_code": "body_proportion_analysis_profile_invalid",
    }
    assert "raw_response" not in projection
    assert "provider_payload" not in projection
    assert "closed" not in projection["allowed_bands_keys"]


def test_output_text_json_shape_projection_has_no_response_values(tmp_path: Path) -> None:
    response = '{"allowed_bands": {"unexpected": "redacted"}}'
    provider = _provider(_FakeAnalysisTransport(response=response))

    with pytest.raises(
        BodyProportionAnalysisError,
        match="body_proportion_analysis_profile_invalid",
    ):
        provider.analyze(_body_assets(tmp_path))

    projection = provider.last_response_shape_projection
    assert projection["output_text_present"] is True
    assert projection["output_text_type"] == "string"
    assert projection["json_parse_status"] == "success"
    assert projection["response_top_level_type"] == "object"
    assert projection["response_top_level_keys"] == ["allowed_bands"]
    assert projection["allowed_bands_keys"] == ["unexpected"]
    assert projection["allowed_bands_unknown_field_count"] == 1
    assert projection["allowed_bands_missing_field_count"] == 7
    assert projection["schema_code"] == "body_proportion_analysis_profile_invalid"
    assert "redacted" not in str(projection)


@pytest.mark.parametrize(
    ("case_name", "mutate", "expected_band_state"),
    [
        (
            "missing",
            lambda bands: bands.pop("arm_leg"),
            {
                "present": False,
                "value_type": "absent",
                "allowed_membership": "missing",
                "closed_code": "body_proportion_analysis_profile_invalid",
            },
        ),
        (
            "unknown_key",
            lambda bands: bands.update({"unexpected_band": "hidden"}),
            {
                "present": True,
                "value_type": "string",
                "allowed_membership": "allowed",
                "closed_code": "none",
            },
        ),
        (
            "non_string",
            lambda bands: bands.update({"arm_leg": 3}),
            {
                "present": True,
                "value_type": "number",
                "allowed_membership": "not_applicable",
                "closed_code": "body_proportion_analysis_profile_invalid",
            },
        ),
        (
            "invalid_literal",
            lambda bands: bands.update({"arm_leg": "natural_child_proportion"}),
            {
                "present": True,
                "value_type": "string",
                "allowed_membership": "not_allowed",
                "closed_code": "body_proportion_analysis_profile_invalid",
            },
        ),
        (
            "valid_literal",
            lambda bands: None,
            {
                "present": True,
                "value_type": "string",
                "allowed_membership": "allowed",
                "closed_code": "none",
            },
        ),
    ],
)
def test_per_band_value_projection_is_closed_and_value_free(
    tmp_path: Path,
    case_name: str,
    mutate,
    expected_band_state: dict[str, Any],
) -> None:
    bands = dict(_BANDS)
    mutate(bands)
    provider = _provider(_FakeAnalysisTransport(response={"allowed_bands": bands}))

    if case_name in {"missing", "non_string", "invalid_literal", "unknown_key"}:
        with pytest.raises(
            BodyProportionAnalysisError,
            match="body_proportion_analysis_profile_invalid",
        ):
            provider.analyze(_body_assets(tmp_path))
    else:
        provider.analyze(_body_assets(tmp_path))

    projection = provider.last_response_value_projection
    assert projection["unknown_band_key_count"] == (1 if case_name == "unknown_key" else 0)
    assert projection["unknown_band_keys"] == (
        ["unexpected_band"] if case_name == "unknown_key" else []
    )
    assert projection["schema_code"] == (
        "body_proportion_analysis_profile_invalid"
        if case_name in {"missing", "non_string", "invalid_literal", "unknown_key"}
        else "body_proportion_analysis_profile_valid"
    )
    states = {item["band"]: item for item in projection["per_band"]}
    assert states["arm_leg"] == {
        "band": "arm_leg",
        **expected_band_state,
    }
    assert all("value" not in item for item in projection["per_band"])
    assert all(
        forbidden not in str(projection)
        for forbidden in ("natural_child_proportion", "hidden", "raw_response")
    )


def test_body_analysis_request_contract_exposes_only_exact_literal_members() -> None:
    provider = _provider(_FakeAnalysisTransport())
    contract = provider.analysis_response_schema
    expected_schema = BodyProportionEvidenceProfile.model_json_schema()
    expected_bands = expected_schema["$defs"]["BodyProportionEvidenceBands"]["properties"]

    assert contract["type"] == "object"
    assert contract["additionalProperties"] is False
    assert set(contract["required"]) == {"allowed_bands"}
    assert set(contract["properties"]) == {"allowed_bands"}
    actual_bands = contract["properties"]["allowed_bands"]["properties"]
    assert set(actual_bands) == set(expected_bands)
    for band_name, band_schema in expected_bands.items():
        assert actual_bands[band_name] == {
            "type": "string",
            "enum": band_schema["enum"],
        }
    assert contract["properties"]["allowed_bands"]["additionalProperties"] is False
    assert "natural language" not in str(contract).lower()
    assert "balanced fallback" not in str(contract).lower()


def test_responses_transport_sends_same_closed_literal_schema(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class _Responses:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(output_text=json.dumps({"allowed_bands": _BANDS}))

    class _Client:
        responses = _Responses()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=lambda **_: _Client()))
    transport = OpenAICompatibleBodySourceAnalysisTransport(
        api_key="test-key",
        base_url="https://vision.example/v1",
        model="body-model",
    )

    transport.analyze(
        [BodySourceImagePayload(content=b"body", mime_type="image/png")],
        instructions="closed instructions",
        timeout_seconds=1,
    )

    response_format = captured["text"]["format"]
    assert response_format["type"] == "json_schema"
    assert response_format["name"] == "body_proportion_analysis_v1"
    assert response_format["strict"] is True
    assert response_format["schema"] == _provider(_FakeAnalysisTransport()).analysis_response_schema
