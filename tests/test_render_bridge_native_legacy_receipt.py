"""Compatibility of persisted native Bridge registration records."""

from __future__ import annotations

from contextlib import nullcontext
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from alchemy_creative_agent_3_0.app.product_api.render_bridge_native import (
    NativeRenderBridgeGateway,
)


def test_registration_status_reads_legacy_binding_with_original_sha256(tmp_path, monkeypatch):
    journal_path = tmp_path / "legacy-registration.json"
    expected = {
        "status": "registered",
        "native_registration_ref": "v3_output_existing",
        "review_status": "passed",
    }
    journal_path.write_text(
        json.dumps(
            {
                "status": "registered",
                "import_key": "legacy-import",
                "binding": {
                    "registration_key": "registration",
                    "project_id": "project",
                    "job_id": "job",
                    "asset_id": "asset",
                    "frozen_request_id": "request",
                    "target_revision": "revision",
                    "prompt_sha256": "legacy-prompt-id",
                    "receipt_id": "receipt",
                    "execution_profile_id": "fake-image",
                    "execution_profile_revision": "1",
                    "uploaded_asset_ids": [],
                    "size": "1024x1024",
                    "output_format": "png",
                    "original_sha256": "legacy-image-digest",
                },
                "outcome": expected,
            }
        ),
        encoding="utf-8",
    )

    gateway = NativeRenderBridgeGateway.__new__(NativeRenderBridgeGateway)
    gateway.enabled = True
    gateway.facade = SimpleNamespace(_target=Mock(return_value=None))
    gateway.service = SimpleNamespace(
        lookup_render_bridge_registration=Mock(return_value={"status": "registered"}),
        resume_render_bridge_review=Mock(
            return_value={
                "status": "registered",
                "native_registration_ref": "v3_output_existing",
                "review_status": "passed",
            }
        ),
    )
    monkeypatch.setattr(gateway, "_journal_path", lambda actor, target: journal_path)
    monkeypatch.setattr(gateway, "_lock", lambda path: nullcontext())
    monkeypatch.setattr(gateway, "_options", lambda *args, **kwargs: None)
    target = SimpleNamespace()

    result = gateway.registration_status(7, target, import_key="legacy-import")

    assert result["status"] == "registered"
    assert result["native_registration_ref"] == "v3_output_existing"
    assert gateway.service.lookup_render_bridge_registration.call_count == 1
    binding = gateway.service.lookup_render_bridge_registration.call_args.args[0]
    assert not hasattr(binding, "original_sha256")
