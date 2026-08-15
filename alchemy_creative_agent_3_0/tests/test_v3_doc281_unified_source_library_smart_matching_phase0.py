"""Phase 0 red contracts for Doc281 unified source-library activation.

These tests use only local in-memory stores and deterministic uploaded image
fixtures. They intentionally assert the next server-owned behavior before its
runtime implementation exists. They never select a live Provider, contact MCP
or ImageGen, write a real Job, or deploy a service.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.product_api.contracts import V3AssetUploadStatusValue
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _add_product_references,
    _job_payload,
    _save_history_output,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc270_phase3_general_activation_contract import (
    _general_payload,
    _general_project,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _ready_product_upload,
)


def _public_safe(value: Any) -> None:
    forbidden = (
        "asset_id",
        "reference_id",
        "sha",
        "digest",
        "path",
        "file",
        "prompt",
        "provider",
        "exception",
        "traceback",
    )
    if isinstance(value, dict):
        for key, nested in value.items():
            assert not any(fragment in str(key).lower() for fragment in forbidden)
            _public_safe(nested)
    elif isinstance(value, list):
        for nested in value:
            _public_safe(nested)


def _assert_general_runtime_authority(handlers: Any, project_id: str) -> None:
    capability = handlers.project_service._doc270_general_activation_capability_lookup()  # noqa: SLF001
    assert isinstance(capability, dict)
    assert capability["enabled"] is True
    identity = handlers.project_service._doc270_general_command_identity_lookup(  # noqa: SLF001
        project_id=project_id,
        template_id="general_template",
    )
    assert isinstance(identity, dict)
    assert identity["project_id"] == project_id
    assert identity["template_id"] == "general_template"
    registry = handlers.project_service._doc270_general_phase2_receipt_registry_lookup(  # noqa: SLF001
        project_id=project_id,
        command_identity=identity,
    )
    assert isinstance(registry, dict)
    assert registry["receipt"]["state"] in {"resolved", "not_applicable", "optional_uncertain"}


@pytest.mark.parametrize(
    "user_input",
    [
        "Create an object image that needs the detail original.",
        "Create a person image with optional environment inspiration.",
        "Create a scene image using a brand or graphic source.",
    ],
)
def test_doc281_general_activation_is_real_server_owned_across_shared_domains(tmp_path, user_input: str) -> None:
    handlers, project, _asset_ids, _snapshot = _general_project(tmp_path)

    _assert_general_runtime_authority(handlers, project["project_id"])
    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": user_input,
            "metadata": {
                "selected_original_asset_ids": ["browser-never-selects"],
                "source_evidence_profile": {"view_kind": "browser-never-certifies"},
            },
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = record.request.metadata["doc270_general_source_activation_receipts"][0]
    assert activation["state"] in {"activated_resolved", "prompt_only"}
    assert "browser-never-selects" not in record.request.uploaded_asset_ids


def test_doc281_general_optional_uncertainty_is_prompt_only_and_never_needs_input(tmp_path) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = handlers.post_projects(
        {
            "user_goal": "Create a prompt-only General image without project originals.",
            "primary_template_id": "general_template",
        }
    )["project"]

    created = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Use an optional uncertain scene original when appropriate.",
        },
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert record.request.metadata.get("doc270_general_source_activation_receipts") == [
        {"state": "prompt_only"}
    ]
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


@pytest.mark.parametrize("fault", ["not_ready", "role_drift"])
def test_doc281_active_historical_product_drift_closes_once_with_sanitized_terminal_operation(
    tmp_path,
    fault: str,
) -> None:
    handlers, _catalog = _handlers(tmp_path)
    project = _project(handlers)
    product_id = _ready_product_upload(
        handlers,
        filename=f"doc281-product-{fault}.png",
        color=(95, 125, 165),
    )
    _add_product_references(handlers, project["project_id"], [product_id])
    upload = handlers.service.get_uploaded_asset(product_id)
    assert upload is not None
    if fault == "not_ready":
        handlers.service.asset_store._save_record(  # noqa: SLF001
            upload.model_copy(update={"status": V3AssetUploadStatusValue.STORED})
        )
    else:
        handlers.service.asset_store._save_record(  # noqa: SLF001
            upload.model_copy(update={"role": "face_reference"})
        )

    first = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-drift-{fault}"),
    )
    second = handlers.post_project_job(
        project["project_id"],
        _job_payload(uploaded_asset_ids=[], key=f"doc281-drift-{fault}"),
    )
    assert first["job_id"] == second["job_id"]
    assert first["status"] == "blocked"
    operation = first["metadata"]["current_operation"]
    assert operation["state"] == "needs_input"
    assert operation["terminal"] is True
    _public_safe(operation)


def test_doc281_explicit_continuation_and_history_never_enter_general_original_match_projection(tmp_path) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)
    _assert_general_runtime_authority(handlers, project["project_id"])
    history = _save_history_output(handlers, job_id="doc281-history", index=281)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": history.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": "doc281-history",
            "created_from_output_id": history.output_id,
            "use_policy": "style",
        },
    )

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    projection = record.request.metadata["doc270_general_original_source_projection"]
    selected = [item["asset_id"] for item in projection["sources"]]
    assert set(selected).issubset(set(asset_ids))
    assert history.output_id not in selected
    assert all(
        reference.source_type != ProjectReferenceSourceType.GENERATED_SELECTED
        or reference.asset_ref_id != history.output_id
        or reference.use_policy == ProjectReferenceUsePolicy.STYLE
        for reference in handlers.project_service._require_project(project["project_id"]).reference_assets  # noqa: SLF001
    )


def test_doc281_new_general_command_replaces_old_terminal_presentation_without_history_reselection(tmp_path) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)
    _assert_general_runtime_authority(handlers, project["project_id"])
    first = handlers.post_project_job(project["project_id"], _general_payload())
    first_record = handlers.service.get_job_record(first["job_id"])
    assert first_record is not None
    first_projection = deepcopy(first_record.request.metadata["doc270_general_original_source_projection"])

    second = handlers.post_project_job(
        project["project_id"],
        {
            **_general_payload(),
            "user_input": "Create a distinct new image from the current request only.",
        },
    )
    second_record = handlers.service.get_job_record(second["job_id"])
    assert second_record is not None
    assert second["job_id"] != first["job_id"]
    assert handlers.get_project(project["project_id"])["metadata"].get("current_operation") is None
    second_projection = second_record.request.metadata["doc270_general_original_source_projection"]
    assert first_projection["state"] == "activated_resolved"
    assert second_projection["state"] == "activated_resolved"
    assert set(item["asset_id"] for item in second_projection["sources"]).issubset(set(asset_ids))


def test_doc281_phase0_contract_keeps_runtime_and_provider_code_unchanged() -> None:
    """Guard the Phase 0 scope: this test module must not imply a provider call."""

    assert Path(__file__).name == "test_v3_doc281_unified_source_library_smart_matching_phase0.py"
