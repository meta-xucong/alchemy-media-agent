"""Red tests for the ProductApi -> ScenarioRuntime Body analyzer envelope.

The public Character Card metadata contains only server-owned selectors.  The
source analyzer needs a separate, typed internal projection built from the
resolved upload records.  That projection must never become Brain metadata or
physical Provider reference input.
"""

from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    V3AssetUploadStatusValue,
    V3UploadedAssetRecord,
)
from alchemy_creative_agent_3_0.app.product_api.service import V3ProductApiService
from alchemy_creative_agent_3_0.app.scenario_runtime.contracts import ScenarioRuntimeRequest
from alchemy_creative_agent_3_0.app.scenario_runtime.runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.body_proportion_evidence_profile import (
    BodyProportionEvidenceProfile,
)
from alchemy_creative_agent_3_0.app.visual_assets.character_card import BodySourceAdmission


_BODY_IDS = [f"v3_asset_{index:016x}" for index in range(1, 6)]
_FACE_IDS = ["face-front", "face-profile", "face-rear"]
_BODY_BANDS = {
    "head_body_scale": "balanced_child_scale",
    "neck_shoulder": "balanced_child_transition",
    "torso_limb": "balanced_child_torso_limb",
    "arm_leg": "balanced_child_arm_leg",
    "developmental_stage": "early_childhood_coherent",
    "stance_ground": "grounded_full_contact",
    "cross_view_support": "front_back_supported",
}


class _UploadStore:
    def __init__(self, records: dict[str, V3UploadedAssetRecord]) -> None:
        self.records = records

    def get_upload(self, asset_id: str) -> V3UploadedAssetRecord | None:
        return self.records.get(asset_id)

    def resolve_uploaded_assets(self, _asset_ids: list[str]) -> list[Any]:
        return []


class _CapturingAnalyzer:
    def __init__(self) -> None:
        self.calls: list[tuple[dict[str, Any], ...]] = []

    def analyze(self, admitted_body_assets):
        captured = tuple(dict(asset) for asset in admitted_body_assets)
        self.calls.append(captured)
        assert len(captured) == 5
        required = {
            "asset_id",
            "role",
            "reference_truth_layer",
            "file_path",
            "mime_type",
            "metadata",
        }
        assert all(required <= set(asset) for asset in captured)
        for asset in captured:
            metadata = asset["metadata"]
            assert metadata["content_stored"] is True
            assert metadata["ready_for_v3_runtime"] is True
            assert len(metadata["source_sha256"]) == 64
            assert metadata["source_provenance"]
            assert metadata["consent_reference"]
            assert metadata["rights_reference"]
        return {
            "contract_version": "body_proportion_evidence_profile_v1",
            "source_mode": "reference_assisted",
            "source_truth_layer": "body_proportion_truth",
            "allowed_bands": dict(_BODY_BANDS),
            "source_count": 5,
            "analysis_receipt": {
                "owner": "server_owned_body_proportion_analysis",
                "status": "complete",
                "analysis_provider": "configured_body_source_analysis_provider",
            },
        }


def _records(tmp_path: Path, *, mutate: str | None = None) -> dict[str, V3UploadedAssetRecord]:
    records: dict[str, V3UploadedAssetRecord] = {}
    for index, asset_id in enumerate(_BODY_IDS):
        content = f"body-source-{index}".encode("utf-8")
        path = tmp_path / f"source-{index}.png"
        path.write_bytes(content)
        metadata: dict[str, Any] = {
            "content_stored": True,
            "ready_for_v3_runtime": True,
            "source_sha256": sha256(content).hexdigest(),
            "source_provenance": "user_provided_body_reference",
            "consent_reference": "user_consent_body_reference",
            "rights_reference": "user_rights_body_reference",
            "reference_truth_layer": "body_proportion_truth",
        }
        if mutate == "readiness" and index == 0:
            metadata.pop("ready_for_v3_runtime")
        if mutate == "hash" and index == 0:
            metadata["source_sha256"] = "0" * 64
        if mutate == "provenance" and index == 0:
            metadata.pop("source_provenance")
        if mutate == "consent" and index == 0:
            metadata.pop("consent_reference")
        if mutate == "rights" and index == 0:
            metadata.pop("rights_reference")
        records[asset_id] = V3UploadedAssetRecord(
            asset_id=asset_id,
            filename=path.name,
            mime_type="image/png",
            size_bytes=len(content),
            role="body_proportion_reference",
            status=V3AssetUploadStatusValue.READY,
            file_path=str(path),
            created_at="2026-01-01T00:00:00Z",
            updated_at="2026-01-01T00:00:00Z",
            metadata=metadata,
        )
    return records


def _request_metadata() -> dict[str, Any]:
    admission = BodySourceAdmission(
        source_class="observed",
        body_evidence_ids=list(_BODY_IDS),
        body_reference_role="body_proportion_reference",
        body_reference_truth_layer="body_proportion_truth",
        face_reference_output_ids=list(_FACE_IDS),
    )
    body_refs = [
        {
            "asset_id": asset_id,
            "role": "body_proportion_reference",
            "reference_truth_layer": "body_proportion_truth",
            "provider_input_required": False,
        }
        for asset_id in _BODY_IDS
    ]
    face_refs = [
        {
            "asset_id": asset_id,
            "output_id": asset_id,
            "role": "face_reference",
            "provider_input_required": True,
        }
        for asset_id in _FACE_IDS
    ]
    return {
        "professional_mode": True,
        "professional_character_card_preparation": True,
        "professional_character_card_stage": "body_silhouette",
        "professional_character_card_slot": "body.front_full",
        "professional_character_card_source_class": "observed",
        "professional_character_card_body_refresh_source_mode": "reference_assisted",
        "professional_character_card_body_refresh_target_age_scope": "age_6_child_only",
        "professional_character_card_body_model_context": "similar_person_body_reference_assisted_v1",
        "professional_character_card_reference_output_ids": list(_FACE_IDS),
        "professional_character_card_body_source_admission": admission.model_dump(mode="json"),
        "professional_anchor_reference_assets": [*face_refs, *body_refs],
    }


def _runtime_request(service: V3ProductApiService) -> ScenarioRuntimeRequest:
    request = CreateCreativeJobRequest(
        user_input="server-owned Body source analysis",
        professional_mode="professional",
        people_asset_id="people-asset",
        metadata=_request_metadata(),
    )
    payload = service._runtime_request_payload(request)  # noqa: SLF001
    return ScenarioRuntimeRequest.model_validate(payload)


def test_productapi_runtime_projection_dispatches_typed_analyzer_once(tmp_path: Path) -> None:
    analyzer = _CapturingAnalyzer()
    service = V3ProductApiService(
        asset_store=_UploadStore(_records(tmp_path)),
        body_proportion_source_analyzer=analyzer,
    )
    request = _runtime_request(service)

    profile = service.scenario_runtime._body_proportion_profile_for_brain(  # noqa: SLF001
        request,
        stage="plan",
    )

    assert isinstance(profile, BodyProportionEvidenceProfile)
    assert len(analyzer.calls) == 1


@pytest.mark.parametrize("mutate", ["readiness", "hash", "provenance", "consent", "rights"])
def test_productapi_projection_fails_before_runtime_plan_for_untrusted_source(
    tmp_path: Path,
    mutate: str,
) -> None:
    service = V3ProductApiService(
        asset_store=_UploadStore(_records(tmp_path, mutate=mutate)),
        body_proportion_source_analyzer=_CapturingAnalyzer(),
    )
    request = CreateCreativeJobRequest(
        user_input="server-owned Body source analysis",
        professional_mode="professional",
        people_asset_id="people-asset",
        metadata=_request_metadata(),
    )

    with pytest.raises(ValueError, match="body_proportion_analysis_source_"):
        service._runtime_request_payload(request)  # noqa: SLF001


def test_internal_source_envelope_does_not_enter_brain_or_physical_reference_assets(
    tmp_path: Path,
) -> None:
    service = V3ProductApiService(
        asset_store=_UploadStore(_records(tmp_path)),
        body_proportion_source_analyzer=_CapturingAnalyzer(),
    )
    request = _runtime_request(service)
    metadata = request.metadata
    assert "body_source_analysis_assets" not in metadata
    assert all(item.get("role") != "body_proportion_reference" for item in metadata.get("reference_assets", []))

    brain_metadata = service.scenario_runtime._brain_runtime_metadata(  # noqa: SLF001
        request,
        SimpleNamespace(
            manifest=SimpleNamespace(
                scenario_id="general_creative",
                display_name="General Creative",
            ),
            status=SimpleNamespace(value="active"),
            selected_mode_id="freeform",
            selected_preset_id=None,
        ),
    )
    assert all(
        item.get("role") != "body_proportion_reference"
        for item in brain_metadata.get("professional_anchor_reference_assets", [])
    )
    serialized = str(brain_metadata).lower()
    assert "v3_asset_" not in serialized
    assert "source_sha256" not in serialized
    assert "consent_reference" not in serialized


def test_inference_first_does_not_consume_observed_internal_source_envelope(tmp_path: Path) -> None:
    service = V3ProductApiService(
        asset_store=_UploadStore(_records(tmp_path)),
        body_proportion_source_analyzer=_CapturingAnalyzer(),
    )
    metadata = _request_metadata()
    metadata["professional_character_card_source_class"] = "brain_inferred"
    metadata["professional_character_card_body_refresh_source_mode"] = "inference_first"
    metadata["professional_character_card_body_source_admission"] = None
    request = SimpleNamespace(metadata=metadata)

    assert service.scenario_runtime._body_proportion_profile_for_brain(  # noqa: SLF001
        request,
        stage="plan",
    ) is None
