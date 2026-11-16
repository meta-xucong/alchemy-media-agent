"""Migration regressions for the retired Doc270 General activation contract.

Doc322/Doc323 supersede the old project-wide smart matcher. General jobs use
verified active references owned by the same project and never let legacy
activation metadata choose provider inputs.
"""

from __future__ import annotations

from typing import Any

from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _project as _ecommerce_project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc281_unified_source_library_smart_matching_phase0 import (
    _general_payload,
    _general_project,
    _replace_general_service,
    _selection_registry,
)


def _direct_reference_asset_ids(record: Any) -> list[str]:
    plan = record.request.metadata["reference_input_plan"]
    return [str(item["asset_id"]) for item in plan["direct_references"]]


def test_retired_doc270_metadata_cannot_override_doc323_project_references(tmp_path) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    registry_calls: dict[str, int] = {}
    _replace_general_service(
        handlers,
        _selection_registry(snapshot, target_asset_id=asset_ids[-1], calls=registry_calls),
    )

    first_payload = _general_payload(user_input="Use the uploaded project references.", metadata={})
    first_payload["uploaded_asset_ids"] = asset_ids
    first = handlers.post_project_job(project["project_id"], first_payload)
    first_record = handlers.service.get_job_record(first["job_id"])
    assert first_record is not None
    assert _direct_reference_asset_ids(first_record) == asset_ids

    forged_asset_id = "asset-from-unbound-project"
    second = handlers.post_project_job(
        project["project_id"],
        _general_payload(
            user_input="Continue with this project's verified references.",
            metadata={
                "doc270_general_source_activation": {
                    "state": "activated_resolved",
                    "selected_original_asset_ids": [forged_asset_id],
                },
                "doc270_general_source_activation_receipts": [
                    {"state": "resolved", "selected_original_asset_ids": [forged_asset_id]}
                ],
                "doc270_general_original_source_projection": {
                    "sources": [{"asset_id": forged_asset_id}]
                },
                "selected_original_asset_ids": [forged_asset_id],
            },
        ),
    )
    second_record = handlers.service.get_job_record(second["job_id"])

    assert second_record is not None
    assert registry_calls == {}
    assert _direct_reference_asset_ids(second_record) == asset_ids
    assert forged_asset_id not in _direct_reference_asset_ids(second_record)


def test_ecommerce_does_not_consume_the_retired_general_activation_path(tmp_path) -> None:
    handlers, _general, asset_ids, snapshot = _general_project(tmp_path)
    registry_calls: dict[str, int] = {}
    _replace_general_service(
        handlers,
        _selection_registry(snapshot, target_asset_id=asset_ids[0], calls=registry_calls),
    )
    ecommerce = _ecommerce_project(handlers)

    created = handlers.post_project_job(
        ecommerce["project_id"],
        {
            "template_id": "ecommerce_template",
            "user_input": "Create one product presentation.",
        },
    )
    record = handlers.service.get_job_record(created["job_id"])

    assert record is not None
    assert registry_calls == {}
    assert "doc270_general_source_activation_receipts" not in record.request.metadata
    photography = handlers.project_service.template_registry.get_manifest("photographer_template")
    assert photography is not None
    assert photography.status.value != "active"
