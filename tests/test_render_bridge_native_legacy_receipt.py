"""Recover an upgrade-era native Bridge receipt against real stored records."""

from __future__ import annotations

import base64
from contextlib import nullcontext
from dataclasses import asdict
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from PIL import Image

from alchemy_creative_agent_3_0.app.generation_router.render_bridge_provider import (
    RenderBridgeRegistration,
)
from alchemy_creative_agent_3_0.app.product_api.outputs import V3GeneratedOutputStore
from alchemy_creative_agent_3_0.app.product_api.render_bridge_native import (
    NativeRenderBridgeGateway,
)
from alchemy_creative_agent_3_0.app.product_api.contracts import (
    CreateCreativeJobRequest,
    ProductJobStatusValue,
)
from alchemy_creative_agent_3_0.app.product_api.service import (
    PersistentProductJobStore,
    ProductJobRecord,
    V3ProductApiService,
)
from alchemy_creative_agent_3_0.app.scenario_runtime import ScenarioRuntime


def test_registration_status_recovers_legacy_finalizing_binding_and_original_output(tmp_path, monkeypatch):
    monkeypatch.setenv("V3_LLM_BRAIN_ENABLED", "false")
    monkeypatch.setenv("V3_CAPABILITY_ACTIVATION_MODE", "enforced")
    planned = ScenarioRuntime().plan_job(
        {
            "user_input": "A blue ceramic vase on a plain wooden table.",
            "scenario_selection": {
                "scenario_id": "general_creative",
                "parameters": {"requested_image_count": 1},
            },
        }
    ).planning_result
    assert planned is not None
    job_id = planned.creative_job.job_id
    old_output_id = "v3_output_aaaaaaaaaaaaaaaaaaaa"
    binding = RenderBridgeRegistration(
        registration_key="registration-key",
        project_id="project",
        job_id=job_id,
        asset_id=planned.series_plan.assets[0].asset_id,
        frozen_request_id="frozen-request",
        target_revision="revision",
        prompt_sha256="prompt-id",
        receipt_id="bridge-receipt",
    )
    # These literal values model fields saved by the pre-upgrade writer. The
    # compatibility path reads them but does not calculate or verify a digest.
    legacy_image_digest = "legacy-image-digest"
    legacy_reference_digests = ["legacy-reference-digest"]
    journal_binding = asdict(binding)
    journal_binding["original_sha256"] = legacy_image_digest
    journal_binding["reference_sha256"] = legacy_reference_digests
    journal_binding.pop("output_format")
    journal_path = tmp_path / "legacy-registration.json"
    journal_path.write_text(
        json.dumps({"status": "registered", "import_key": "legacy-import", "binding": journal_binding,
                    "outcome": {"status": "registered", "native_registration_ref": old_output_id}}),
        encoding="utf-8",
    )

    legacy_output_receipt = {
        **binding.safe_metadata(),
        "output_id": old_output_id,
        "original_sha256": legacy_image_digest,
        "reference_sha256": legacy_reference_digests,
    }
    image = io.BytesIO()
    Image.new("RGB", (32, 32), "blue").save(image, format="PNG")
    original_bytes = image.getvalue()
    output_store = V3GeneratedOutputStore(tmp_path / "outputs")
    output = output_store.save_base64_output(
        job_id=job_id,
        candidate_id="candidate-legacy",
        asset_id=binding.asset_id,
        provider="render_bridge_receipt_provider",
        model="fake-image",
        encoded_image=base64.b64encode(original_bytes).decode("ascii"),
        output_id=old_output_id,
        mime_type="image/png",
        output_format="png",
        metadata={
            "project_id": binding.project_id,
            "provider_raw_summary": {"render_bridge_registration": legacy_output_receipt},
        },
        preserve_original_bytes=True,
        include_content_hash=False,
    )

    output_assets = [
        asset.model_copy(
            update={"metadata": {**asset.metadata, "output_id": old_output_id}}
        )
        if asset.asset_id == binding.asset_id
        else asset
        for asset in planned.asset_pack.assets
    ]
    assert any(asset.asset_id == binding.asset_id for asset in output_assets)
    generation_result = planned.model_copy(
        update={
            "metadata": {**planned.metadata, "render_bridge_registration": legacy_output_receipt},
            "asset_pack": planned.asset_pack.model_copy(update={"assets": output_assets}),
        }
    )
    original_store = PersistentProductJobStore(tmp_path / "jobs")
    original_job = ProductJobRecord(
        request=CreateCreativeJobRequest(user_input="A blue ceramic vase on a plain wooden table."),
        status=ProductJobStatusValue.FINALIZING,
        job_id_value=job_id,
        generation_result=generation_result,
    )
    original_store.save(original_job)
    # A fresh store instance must deserialize the pre-upgrade task from disk;
    # the recovery assertion must not pass through an in-memory object.
    job_store = PersistentProductJobStore(tmp_path / "jobs")
    restored_job = job_store.get(job_id)
    assert restored_job is not None
    assert restored_job is not original_job
    assert restored_job.status == ProductJobStatusValue.FINALIZING
    assert restored_job.generation_result is not None
    assert any(
        asset.asset_id == binding.asset_id and asset.metadata["output_id"] == old_output_id
        for asset in restored_job.generation_result.asset_pack.assets
    )
    service = V3ProductApiService.__new__(V3ProductApiService)
    service.job_store = job_store
    service.output_store = output_store

    def resume_review(record, request, *, review_only, assert_current):
        assert record.status == ProductJobStatusValue.FINALIZING
        assert review_only is True
        assert_current()

    service._resume_finalizing_generation_review = resume_review

    gateway = NativeRenderBridgeGateway.__new__(NativeRenderBridgeGateway)
    gateway.enabled = True
    target = SimpleNamespace(project_id=binding.project_id)
    gateway.facade = SimpleNamespace(
        _target=Mock(
            return_value=(restored_job, SimpleNamespace(status="active"), binding.target_revision)
        )
    )
    gateway._admit_references = Mock(return_value=None)
    gateway.service = service
    monkeypatch.setattr(gateway, "_journal_path", lambda actor, target: journal_path)
    monkeypatch.setattr(gateway, "_lock", lambda path: nullcontext())
    monkeypatch.setattr(gateway, "_options", lambda *args, **kwargs: None)

    result = gateway.registration_status(7, target, import_key="legacy-import")

    assert result["status"] == "registered"
    assert result["review_pending"] is True
    assert result["native_registration_ref"] == old_output_id
    assert output.output_id == old_output_id
    assert Path(output.file_path).read_bytes() == original_bytes
    assert service.get_job_record(job_id) is restored_job
