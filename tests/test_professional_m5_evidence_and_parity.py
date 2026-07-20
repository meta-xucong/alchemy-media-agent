from __future__ import annotations

from pathlib import Path

from services.alchemy_codex_local_adapter.provenance import renderer_parity_receipt
from services.alchemy_codex_local_adapter.professional_binding import (
    persistent_professional_binding_resolver,
)
from alchemy_creative_agent_3_0.app.visual_assets import PersistentVisualAssetCatalog
from alchemy_creative_agent_3_0.tests.professional_mode_test_support import (
    catalog_with_active_face_identity_pack,
)


def test_renderer_parity_requires_exact_host_contract() -> None:
    expected = {
        "renderer": "codex_builtin_imagegen",
        "model": "gpt-image-2",
        "size": "1024x1024",
        "quality": "medium",
        "output_format": "png",
    }
    verified = renderer_parity_receipt(expected_contract=expected, actual_contract=dict(expected))
    assert verified["state"] == "verified"
    assert verified["reason_code"] is None
    assert verified["conversation_only"] is True

    blocked = renderer_parity_receipt(
        expected_contract=expected,
        actual_contract={**expected, "size": "1086x1448"},
    )
    assert blocked["state"] == "blocked"
    assert blocked["mismatch_fields"] == ["size"]
    assert blocked["reason_code"] == "renderer_contract_mismatch"


def test_renderer_parity_does_not_infer_missing_model_or_quality() -> None:
    receipt = renderer_parity_receipt(
        expected_contract={"model": "gpt-image-2", "size": "1024x1024"},
        actual_contract={"renderer": "codex_builtin_imagegen", "size": "1024x1024"},
    )
    assert receipt["state"] == "blocked"
    assert set(receipt["missing_fields"]) == {"model", "quality", "output_format"}


def test_persistent_professional_resolver_uses_only_catalog_metadata(tmp_path: Path) -> None:
    source = catalog_with_active_face_identity_pack()
    catalog = PersistentVisualAssetCatalog(tmp_path)
    asset = source.get("project_professional", "person_1")
    assert asset is not None
    pack = source.get_pack("project_professional", "person_1", "pack_1")
    assert pack is not None
    catalog.save_pack(pack, project_id="project_professional", event_type="activate")
    catalog.save(asset, project_id="project_professional", event_type="activate")

    resolver = persistent_professional_binding_resolver(tmp_path)
    binding = resolver(
        project_id="project_professional",
        people_asset_id="person_1",
        job_id="job_1",
        reference_view_ids=["front_1", "three_quarter_1", "profile_1"],
    )
    assert binding is not None
    assert binding.mode == "professional"
    assert binding.pack_version_id == "pack_1"
    assert binding.identity_view_ids == ["front_1", "three_quarter_1", "profile_1"]
