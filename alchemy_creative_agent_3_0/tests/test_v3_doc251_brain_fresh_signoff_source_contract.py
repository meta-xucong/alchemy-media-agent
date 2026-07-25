"""Doc251: fresh Face standard-front signoff owns MCP source availability."""

from __future__ import annotations

import base64
import io
from copy import deepcopy

import pytest
from PIL import Image

from alchemy_creative_agent_3_0.app.llm_brain import V3LLMBrainAdapter
from alchemy_creative_agent_3_0.app.product_api.service import (
    ProductJobStatusValue,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime
from alchemy_creative_agent_3_0.app.visual_assets.runtime_bridge import (
    ProfessionalModeRuntimeBridge,
)
from alchemy_creative_agent_3_0.tests.ecommerce_test_support import (
    EcommerceRemoteBrainTestProvider,
)


CAPTURE_SCOPE = "character_card_face_identity"
OPERATION_ID = "visual_asset_doc251:standard_front:1:round1"


class _Doc251BrainProvider(EcommerceRemoteBrainTestProvider):
    def __init__(self, *, finalizer_fault: str | None = None) -> None:
        super().__init__()
        self.finalizer_fault = finalizer_fault

    def run(self, request):  # noqa: ANN001
        payload = super().run(request)
        if request.stage != "provider_prompt_finalize":
            return payload
        prompts = payload.get("canonical_provider_prompts")
        if not isinstance(prompts, list):
            return payload
        if self.finalizer_fault == "missing_anchor_signature":
            for item in prompts:
                if isinstance(item, dict):
                    item.pop("professional_anchor_view_decision", None)
        elif self.finalizer_fault == "malformed_duplicate_prompt":
            prompts.append(deepcopy(prompts[0]))
        return payload


def _service(provider: _Doc251BrainProvider | None = None) -> V3ProductApiService:
    provider = provider or _Doc251BrainProvider()
    return V3ProductApiService(
        scenario_runtime=ScenarioRuntime(llm_brain_adapter=V3LLMBrainAdapter(provider=provider))
    )


def _png_b64() -> str:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 48), (180, 140, 125)).save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _ready_asset(service: V3ProductApiService) -> str:
    record = service.create_uploaded_asset(
        {
            "filename": "doc251-source.png",
            "mime_type": "image/png",
            "size_bytes": 100,
            "role": "face_reference",
        }
    )
    service.store_uploaded_asset_content(
        record.asset_id,
        {"content_base64": _png_b64(), "mime_type": "image/png"},
    )
    service.complete_uploaded_asset(record.asset_id)
    return record.asset_id


def _request(*, asset_id: str, project_id: str = "project_doc251") -> dict[str, object]:
    return {
        "user_input": "Prepare one Character Card Face Identity standard-front capture.",
        "scenario_selection": {"scenario_id": "general_creative"},
        "uploaded_asset_ids": [asset_id],
        "metadata": {
            "project_id": project_id,
            "requested_image_count": 1,
            "require_real_images": True,
            "professional_anchor_candidate_index": 1,
        },
    }


def test_doc251_missing_fresh_standard_front_signature_blocks_before_source_reuse(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = _service(_Doc251BrainProvider(finalizer_fault="missing_anchor_signature"))
    service.asset_store.storage_root = tmp_path / "uploads"
    asset_id = _ready_asset(service)

    status = service.create_professional_anchor_preparation_job(
        _request(asset_id=asset_id),
        view_role="standard_front",
        reference_evidence_ids=[asset_id],
        capture_scope=CAPTURE_SCOPE,
        generation_channel="mcp",
        mcp_operation_id=OPERATION_ID,
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    record = service.job_store.get(status.job_id)
    assert record is not None
    outcome = record.request.metadata.get("remote_creative_brain_outcome")
    assert isinstance(outcome, dict)
    assert outcome["reason_code"] == "professional_anchor_view_decision_missing"


def test_doc251_malformed_fresh_standard_front_signature_is_contract_invalid(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = _service(_Doc251BrainProvider(finalizer_fault="malformed_duplicate_prompt"))
    service.asset_store.storage_root = tmp_path / "uploads"
    asset_id = _ready_asset(service)

    status = service.create_professional_anchor_preparation_job(
        _request(asset_id=asset_id),
        view_role="standard_front",
        reference_evidence_ids=[asset_id],
        capture_scope=CAPTURE_SCOPE,
        generation_channel="mcp",
        mcp_operation_id=OPERATION_ID,
    )

    assert status.status == ProductJobStatusValue.BLOCKED
    record = service.job_store.get(status.job_id)
    assert record is not None
    outcome = record.request.metadata.get("remote_creative_brain_outcome")
    assert isinstance(outcome, dict)
    assert outcome["reason_code"] == "remote_creative_brain_prompt_signoff_invalid"


def test_doc251_fresh_mcp_standard_front_source_job_has_complete_reuse_binding(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = _service()
    service.asset_store.storage_root = tmp_path / "uploads"
    asset_id = _ready_asset(service)

    source_status = service.create_professional_anchor_preparation_job(
        _request(asset_id=asset_id),
        view_role="standard_front",
        reference_evidence_ids=[asset_id],
        capture_scope=CAPTURE_SCOPE,
        generation_channel="mcp",
        mcp_operation_id=OPERATION_ID,
    )
    assert source_status.status == ProductJobStatusValue.PLANNED

    source_record = service.job_store.get(source_status.job_id)
    assert source_record is not None
    source_metadata = dict(source_record.request.metadata or {})
    assert source_metadata["generation_channel"] == "mcp"
    assert source_metadata["mcp_operation_id"] == OPERATION_ID
    assert source_metadata["professional_anchor_rendering_contract"] == (
        "size:1024x1536|quality:strict|reference_card"
    )
    assert source_metadata["requested_image_size"] == "1024x1536"
    assert source_metadata["quality_mode"] == "strict"

    continuation = service.create_professional_anchor_preparation_job(
        _request(asset_id=asset_id),
        view_role="standard_front",
        reference_evidence_ids=[asset_id],
        stage_plan_source_job_id=source_status.job_id,
        capture_scope=CAPTURE_SCOPE,
        generation_channel="mcp",
        mcp_operation_id=OPERATION_ID,
    )

    assert continuation.status == ProductJobStatusValue.PLANNED
    continuation_record = service.job_store.get(continuation.job_id)
    assert continuation_record is not None
    reuse = continuation_record.request.metadata.get("trusted_professional_anchor_view_decision_reuse")
    assert isinstance(reuse, dict)
    assert reuse["source_binding"] == reuse["current_binding"]
    binding = reuse["current_binding"]
    assert binding["source_asset_id"] == asset_id
    assert binding["operation_context"] == OPERATION_ID
    assert binding["rendering_contract"] == "size:1024x1536|quality:strict|reference_card"
    assert binding["candidate_contract"] == "standard_front:candidate:1"
    assert len(binding["source_sha256"]) == 64


def test_doc251_provider_channel_signed_job_is_not_exact_bound_mcp_source(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    service = _service()
    service.asset_store.storage_root = tmp_path / "uploads"
    asset_id = _ready_asset(service)

    provider_source = service.create_professional_anchor_preparation_job(
        _request(asset_id=asset_id),
        view_role="standard_front",
        reference_evidence_ids=[asset_id],
        capture_scope=CAPTURE_SCOPE,
        generation_channel="provider",
    )
    assert provider_source.status == ProductJobStatusValue.PLANNED

    with pytest.raises(ValueError, match="professional_anchor_view_decision_reuse"):
        service.create_professional_anchor_preparation_job(
            _request(asset_id=asset_id),
            view_role="standard_front",
            reference_evidence_ids=[asset_id],
            stage_plan_source_job_id=provider_source.job_id,
            capture_scope=CAPTURE_SCOPE,
            generation_channel="mcp",
            mcp_operation_id=OPERATION_ID,
        )
