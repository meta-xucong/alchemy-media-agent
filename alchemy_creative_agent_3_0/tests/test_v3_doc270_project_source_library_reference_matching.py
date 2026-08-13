"""Phase 0 red contracts for Doc270 source-library reference matching.

The fixture follows the public Project Mode/Product API construction path with
local in-memory stores and the deterministic E-Commerce Brain double.  It
never dispatches a generation request, selects an app Provider, contacts MCP
or ImageGen, or writes a live project/job.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _project,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _bind_locked_person_identity,
    _job_payload,
    _save_history_output,
)


def _fixture(tmp_path):
    handlers, catalog = _handlers(tmp_path)
    ecommerce_project = _project(handlers)
    product_ids = [
        _ready_product_upload(
            handlers,
            filename=f"doc270-source-{view}.png",
            color=(70 + index * 25, 120, 160),
        )
        for index, view in enumerate(("front", "side", "rear", "detail"))
    ]
    _add_product_references(handlers, ecommerce_project["project_id"], product_ids)
    face_output_ids = _bind_locked_person_identity(
        handlers,
        catalog,
        project_id=ecommerce_project["project_id"],
    )
    history_output = _save_history_output(
        handlers,
        job_id="doc270-history-job",
        index=71,
    )
    return handlers, ecommerce_project, product_ids, face_output_ids, history_output.output_id


def _expected_original_ids(product_ids: list[str]) -> list[str]:
    return list(product_ids)


def test_doc270_public_source_library_contains_only_active_project_upload_originals(tmp_path) -> None:
    handlers, project, product_ids, face_output_ids, history_output_id = _fixture(tmp_path)

    response = handlers.get_project(project["project_id"])
    library = response["metadata"]["project_source_library"]

    assert library["schema_version"] == "doc270_project_source_library_v1"
    assert library["project_id"] == project["project_id"]
    assert library["snapshot_digest"]
    assert [entry["asset_id"] for entry in library["entries"]] == _expected_original_ids(product_ids)
    assert all(entry["source_type"] == "uploaded" for entry in library["entries"])
    assert all(entry["content_sha256"] for entry in library["entries"])
    assert not set(face_output_ids).intersection(
        {entry["asset_id"] for entry in library["entries"]}
    )
    assert history_output_id not in {entry["asset_id"] for entry in library["entries"]}


def test_doc270_ecommerce_command_freezes_one_server_match_receipt_per_output(tmp_path) -> None:
    handlers, project, product_ids, face_output_ids, _history_output_id = _fixture(tmp_path)
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc270-match-receipt")
    payload["metadata"]["requested_image_count"] = 2
    payload["user_input"] = "Create one front product presentation and one rear construction view."

    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    receipts = record.request.metadata["doc270_reference_resolution_receipts"]

    assert [receipt["output_index"] for receipt in receipts] == [1, 2]
    assert all(receipt["project_id"] == project["project_id"] for receipt in receipts)
    assert all(receipt["state"] == "resolved" for receipt in receipts)
    assert all(receipt["receipt_digest"] for receipt in receipts)
    assert all(
        receipt["matched_source_asset_ids"]
        and set(receipt["matched_source_asset_ids"]).issubset(set(product_ids))
        for receipt in receipts
    )
    assert all(
        not set(receipt["matched_source_asset_ids"]).intersection(set(face_output_ids))
        for receipt in receipts
    )
    assert record.request.metadata["professional_ecommerce_physical_product_projections"]
    assert record.request.metadata["physical_renderer_reference_plans"]


def test_doc270_browser_metadata_cannot_author_match_or_replace_channel_selection(tmp_path) -> None:
    handlers, project, product_ids, face_output_ids, history_output_id = _fixture(tmp_path)
    payload = _job_payload(uploaded_asset_ids=product_ids, key="doc270-forged-match")
    payload["metadata"].update(
        {
            "doc270_reference_resolution_receipts": [
                {
                    "output_index": 1,
                    "state": "resolved",
                    "matched_source_asset_ids": [history_output_id, face_output_ids[0]],
                    "receipt_digest": "browser-authored",
                }
            ],
            "source_evidence_profile": {"view_kind": "rear", "confidence": "certain"},
        }
    )

    created = handlers.post_project_job(project["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    receipt = record.request.metadata["doc270_reference_resolution_receipts"][0]

    assert receipt["authority"] == "v3_project_source_library_matcher"
    assert receipt["matched_source_asset_ids"] != [history_output_id, face_output_ids[0]]
    assert set(receipt["matched_source_asset_ids"]).issubset(set(product_ids))
    assert "source_evidence_profile" not in receipt
    assert record.request.metadata["professional_ecommerce_physical_product_projections"]


def test_doc270_general_and_inactive_photography_do_not_consume_ecommerce_matcher_metadata(tmp_path) -> None:
    handlers, ecommerce_project, product_ids, _face_output_ids, _history_output_id = _fixture(tmp_path)
    general = handlers.post_projects(
        {"user_goal": "Make a simple prompt-only scene.", "primary_template_id": "general_template"}
    )["project"]
    forged = {
        "doc270_reference_resolution_receipts": [{"output_index": 1, "state": "resolved"}],
        "source_evidence_profile": {"view_kind": "rear"},
    }

    payload: dict[str, Any] = {
        "template_id": general["primary_template_id"],
        "user_input": general["user_goal"],
        "uploaded_asset_ids": [],
        "metadata": deepcopy(forged),
    }
    created = handlers.post_project_job(general["project_id"], payload)
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    general_view = handlers.get_project(general["project_id"])
    assert "project_source_library" not in general_view["metadata"]
    assert "current_operation" not in general_view["metadata"]
    photography = handlers.project_service.template_registry.get_manifest("photographer_template")
    assert photography is not None
    assert photography.project_can_create_jobs is False

    # The E-Commerce fixture remains a specialized path; it does not grant the
    # shared matcher authority to either non-E-Commerce project above.
    assert handlers.get_project(ecommerce_project["project_id"])["project"]["primary_template_id"] == "ecommerce_template"
