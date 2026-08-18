"""Phase 3 red contracts for version-gated General source activation.

The tests use the public in-process Project Mode route with local stores.  The
future gate and resolved-receipt lookups are private server seams, never
browser request fields.  No test generates pixels or selects a Provider.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from alchemy_creative_agent_3_0.app.project_mode import V3ProjectModeService, source_library
from alchemy_creative_agent_3_0.app.project_mode import service as project_mode_service
from alchemy_creative_agent_3_0.app.project_mode.contracts import (
    ProjectReferenceSourceType,
    ProjectReferenceUsePolicy,
)
from alchemy_creative_agent_3_0.app.project_mode.ecommerce_view_activation import (
    DisabledEcommerceViewActivationIssuer,
)
from alchemy_creative_agent_3_0.app.project_mode.service import Doc281GeneralSourceRegistry
from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import (
    _handlers,
    _ready_product_upload,
)
from alchemy_creative_agent_3_0.tests.test_v3_doc265_reference_channel_recovery import (
    _save_history_output,
)


def _general_project(tmp_path) -> tuple[Any, dict[str, Any], list[str], dict[str, Any]]:
    handlers, _catalog = _handlers(tmp_path)
    handlers.project_service = V3ProjectModeService(
        product_service=handlers.service,
        project_store=handlers.project_service.project_store,
        project_visual_asset_binding_service=handlers.project_visual_asset_binding_service,
        ecommerce_view_activation_issuer=DisabledEcommerceViewActivationIssuer(),
        doc281_general_source_registry=Doc281GeneralSourceRegistry(),
    )
    project = handlers.post_projects(
        {"user_goal": "Create a source-aware general campaign visual.", "primary_template_id": "general_template"}
    )["project"]
    asset_ids = [
        _ready_product_upload(
            handlers,
            filename=f"phase3-general-{index}.png",
            color=(50 + index * 35, 90 + index * 20, 135),
        )
        for index in range(1, 4)
    ]
    for asset_id in asset_ids:
        record = handlers.service.get_uploaded_asset(asset_id)
        assert record is not None
        handlers.service.asset_store._save_record(record.model_copy(update={"role": "general"}))  # noqa: SLF001
        handlers.post_project_reference(
            project["project_id"],
            {"asset_ref_id": asset_id, "source_type": "uploaded", "use_policy": "general"},
        )
    durable = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
    snapshot = source_library.build_project_source_library(
        project_id=durable.project_id,
        references=durable.reference_assets,
        upload_lookup=handlers.service.get_uploaded_asset,
    )
    return handlers, project, asset_ids, snapshot


def test_doc270_phase3_legacy_fixture_ignores_an_enabled_doc281_environment_registry(tmp_path, monkeypatch) -> None:
    """Legacy Doc270 seams are deterministic even when normal General is enabled."""

    environment_registry = Doc281GeneralSourceRegistry(
        selection_brain=lambda **_kwargs: {
            "state": "prompt_only",
            "output_selections": [],
        }
    )
    assert environment_registry.enabled is True
    monkeypatch.setattr(
        project_mode_service,
        "doc281_general_source_registry_from_environment",
        lambda: environment_registry,
    )

    handlers, _project, _asset_ids, _snapshot = _general_project(tmp_path)

    assert isinstance(handlers.project_service.doc281_general_source_registry, Doc281GeneralSourceRegistry)
    assert handlers.project_service.doc281_general_source_registry.enabled is False
    assert handlers.project_service.doc281_general_source_registry is not environment_registry


def _association_id(handlers: Any, project_id: str, asset_id: str) -> str:
    project = handlers.project_service._require_project(project_id)  # noqa: SLF001
    return next(item.reference_id for item in project.reference_assets if item.asset_ref_id == asset_id)


_TEST_RECEIPT_AUTHORITY = {
    "issuer": "v3_doc270_phase2_receipt_registry",
    "schema_version": "doc270_phase2_registry_entry_v1",
    "version": "doc270_phase3_receipt_registry_v1",
    "capability_id": "doc270_shadow_resolution_registry",
    "capability_version": "doc270_phase3_general_activation_capability_v1",
}


_TEST_COMMAND_IDENTITY_AUTHORITY = {
    "schema_version": "doc270_general_command_identity_v1",
    "issuer": "v3_project_mode_general_command_registry",
    "capability_id": "doc270_general_source_activation",
    "capability_version": "doc270_phase3_general_activation_capability_v1",
}

_TEST_ACTIVATION_CAPABILITY = {
    "schema_version": "doc270_general_activation_capability_v1",
    "issuer": "v3_doc270_general_activation_registry",
    "capability_id": "doc270_general_source_activation",
    "capability_version": "doc270_phase3_general_activation_capability_v1",
    "template_id": "general_template",
    "enabled": True,
}


def _server_command_identity(
    *,
    project_id: str,
    command_id: str = "server-phase3-command-1",
    plan_binding_digest: str = "server-phase3-command-binding-1",
    coalescing_nonce: str = "server-phase3-coalescing-nonce-1",
) -> dict[str, str]:
    identity = {
        **_TEST_COMMAND_IDENTITY_AUTHORITY,
        "project_id": project_id,
        "template_id": "general_template",
        "command_id": command_id,
        "command_plan_binding_digest": plan_binding_digest,
        "coalescing_nonce": coalescing_nonce,
    }
    identity["identity_digest"] = source_library.canonical_digest(identity)
    return identity


def _rehash_command_identity(identity: dict[str, Any]) -> None:
    identity["identity_digest"] = source_library.canonical_digest(
        {key: value for key, value in identity.items() if key != "identity_digest"}
    )


def _rehash_receipt(receipt: dict[str, Any]) -> None:
    receipt["receipt_digest"] = source_library.canonical_digest(
        {key: value for key, value in receipt.items() if key != "receipt_digest"}
    )


def _rehash_registry_entry(entry: dict[str, Any]) -> None:
    entry["receipt_digest"] = _receipt_payload(entry)["receipt_digest"]
    entry["registry_entry_digest"] = source_library.canonical_digest(
        {key: value for key, value in entry.items() if key != "registry_entry_digest"}
    )


def _registered_resolved_receipt(
    *,
    project_id: str,
    snapshot: dict[str, Any],
    association_id: str,
    asset_id: str,
    output_index: int = 1,
    command_identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    command_identity = deepcopy(command_identity) if command_identity is not None else _server_command_identity(project_id=project_id)
    command_plan_binding_digest = str(command_identity["command_plan_binding_digest"])
    entry = next(item for item in snapshot["entries"] if item["reference_id"] == association_id)
    receipt = {
        "schema_version": "doc270_reference_resolution_receipt_v1",
        "project_id": project_id,
        "command_plan_binding_digest": command_plan_binding_digest,
        "command_identity": deepcopy(command_identity),
        "output_index": output_index,
        "output_identity": f"server-phase3-output-{output_index}",
        "requirement_nonce": f"server-phase3-nonce-{output_index}",
        "requirement_digest": f"server-phase3-requirement-{output_index}",
        "source_library_snapshot_digest": snapshot["snapshot_digest"],
        "source_resolver": {"authority": "v3_doc270_shadow_matcher", "version": "doc270_shadow_matcher_v1"},
        "state": "resolved",
        "matched_references": [
            {
                "reference_id": association_id,
                "asset_id": asset_id,
                "content_sha256": entry["content_sha256"],
                "profile_digest": "server-phase3-profile",
            }
        ],
        "evidence_profile_digests": ["server-phase3-profile"],
        "shadow_only": True,
    }
    _rehash_receipt(receipt)
    entry = {
        **deepcopy(_TEST_RECEIPT_AUTHORITY),
        "command_identity": {
            **deepcopy(command_identity),
        },
        "output_identity": receipt["output_identity"],
        "receipt": receipt,
        "receipt_digest": receipt["receipt_digest"],
    }
    _rehash_registry_entry(entry)
    return entry


def _install_private_phase3_server_seams(
    monkeypatch,
    handlers: Any,
    registry_entry: dict[str, Any] | None,
    *,
    command_identity: dict[str, str] | None = None,
    capability: dict[str, Any] | None = None,
) -> None:
    """Future private server seams. Current runtime intentionally does not consume them."""

    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_general_activation_capability_lookup",
        lambda: deepcopy(capability if capability is not None else _TEST_ACTIVATION_CAPABILITY),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_general_phase2_receipt_registry_lookup",
        lambda **_kwargs: deepcopy(registry_entry),
        raising=False,
    )
    monkeypatch.setattr(
        handlers.project_service,
        "_doc270_general_command_identity_lookup",
        lambda **_kwargs: deepcopy(
            command_identity
            or (registry_entry or {}).get("command_identity")
        ),
        raising=False,
    )


def _general_payload(*, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "template_id": "general_template",
        "user_input": "Create a faithful source-aware general image.",
        "metadata": metadata or {},
    }


def _activation_receipt(record: Any) -> dict[str, Any]:
    receipts = record.request.metadata.get("doc270_general_source_activation_receipts")
    assert isinstance(receipts, list) and len(receipts) == 1
    return receipts[0]


def _activation_projection(record: Any) -> dict[str, Any]:
    projection = record.request.metadata.get("doc270_general_original_source_projection")
    assert isinstance(projection, dict)
    return projection


def _receipt_payload(registry_entry: dict[str, Any]) -> dict[str, Any]:
    receipt = registry_entry.get("receipt")
    assert isinstance(receipt, dict)
    return receipt


def _assert_private_receipt_invalid(record: Any) -> None:
    assert _activation_receipt(record) == {"state": "receipt_invalid"}
    assert record.request.uploaded_asset_ids == []
    assert "doc270_general_original_source_projection" not in record.request.metadata


def test_doc270_phase3_absent_server_gate_preserves_general_creation_and_ignores_browser_opt_in(tmp_path) -> None:
    handlers, project, asset_ids, _snapshot = _general_project(tmp_path)
    created = handlers.post_project_job(
        project["project_id"],
        _general_payload(metadata={
            "doc270_general_activation": True,
            "doc270_reference_resolution_receipts": [{"state": "resolved", "asset_id": asset_ids[0]}],
            "selected_original_asset_ids": asset_ids,
        }),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert created["status"] == "planned"
    assert "doc270_general_source_activation_receipts" not in record.request.metadata
    assert "doc270_general_activation" not in record.request.metadata
    assert "doc270_reference_resolution_receipts" not in record.request.metadata


def test_doc270_phase3_enabled_new_general_command_freezes_exact_resolved_source_subset(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[1])
    resolved = _registered_resolved_receipt(project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[1])
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = _activation_receipt(record)
    assert activation["state"] == "activated_resolved"
    assert activation["source_receipt_digest"] == _receipt_payload(resolved)["receipt_digest"]
    assert activation["selected_original_reference_ids"] == [association_id]
    assert activation["selected_original_asset_ids"] == [asset_ids[1]]
    assert activation["source_library_snapshot_digest"] == snapshot["snapshot_digest"]
    assert activation["maximum_sources"] == 1
    projection = _activation_projection(record)
    assert record.request.uploaded_asset_ids == [asset_ids[1]]
    assert projection == {
        "schema_version": "doc270_general_original_source_projection_v1",
        "state": "activated_resolved",
        "source_receipt_digest": _receipt_payload(resolved)["receipt_digest"],
        "source_library_snapshot_digest": snapshot["snapshot_digest"],
        "sources": [
            {
                "reference_id": association_id,
                "asset_id": asset_ids[1],
                "content_sha256": next(
                    entry["content_sha256"]
                    for entry in snapshot["entries"]
                    if entry["reference_id"] == association_id
                ),
                "source_receipt_digest": _receipt_payload(resolved)["receipt_digest"],
            }
        ],
    }
    assert all(asset_id not in record.request.uploaded_asset_ids for asset_id in [asset_ids[0], asset_ids[2]])


def test_doc270_phase3_self_digested_browser_resolved_receipt_is_not_registry_authority(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    forged = _receipt_payload(
        _registered_resolved_receipt(
            project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
        )
    )
    forged["receipt_digest"] = source_library.canonical_digest({key: value for key, value in forged.items() if key != "receipt_digest"})
    _install_private_phase3_server_seams(monkeypatch, handlers, forged)

    created = handlers.post_project_job(
        project["project_id"],
        _general_payload(metadata={"doc270_reference_resolution_receipts": [forged]}),
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    _assert_private_receipt_invalid(record)
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


@pytest.mark.parametrize(
    "mutation",
    ["raw_receipt", "issuer", "schema", "capability", "capability_version", "entry_digest", "receipt_digest", "command_binding"],
)
def test_doc270_phase3_registry_entry_provenance_mismatch_is_receipt_invalid(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    entry = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    lookup_value: dict[str, Any]
    if mutation == "raw_receipt":
        lookup_value = _receipt_payload(entry)
    else:
        lookup_value = entry
        if mutation == "issuer":
            lookup_value["issuer"] = "browser-registry"
            _rehash_registry_entry(lookup_value)
        elif mutation == "schema":
            lookup_value["schema_version"] = "doc270_registry_untrusted_v1"
            _rehash_registry_entry(lookup_value)
        elif mutation == "capability":
            lookup_value["capability_id"] = "browser-capability"
            _rehash_registry_entry(lookup_value)
        elif mutation == "capability_version":
            lookup_value["capability_version"] = "wrong-server-version"
            _rehash_registry_entry(lookup_value)
        elif mutation == "entry_digest":
            lookup_value["registry_entry_digest"] = "0" * 64
        elif mutation == "receipt_digest":
            lookup_value["receipt_digest"] = "1" * 64
            _rehash_registry_entry(lookup_value)
            lookup_value["receipt_digest"] = "1" * 64
        else:
            lookup_value["command_identity"]["command_plan_binding_digest"] = "wrong-server-plan"
            _rehash_registry_entry(lookup_value)
    _install_private_phase3_server_seams(monkeypatch, handlers, lookup_value)

    before_library = deepcopy(handlers.get_project(project["project_id"])["metadata"]["project_source_library"])
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    _assert_private_receipt_invalid(record)
    public_job = handlers.get_job(created["job_id"])
    assert public_job["metadata"].get("doc270_general_source_activation") == {"state": "receipt_invalid"}
    public_text = str(public_job)
    for private in [association_id, asset_ids[0], snapshot["snapshot_digest"], "registry", "wrong-server-plan"]:
        assert private not in public_text
    assert handlers.get_project(project["project_id"])["metadata"]["project_source_library"] == before_library


@pytest.mark.parametrize(
    "mutation",
    ["browser_shaped", "project", "template", "issuer", "schema", "capability", "digest", "binding", "missing", "extra"],
)
def test_doc270_phase3_malformed_server_command_identity_cannot_activate(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    valid_identity = _server_command_identity(project_id=project["project_id"])
    entry = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0], command_identity=valid_identity
    )
    identity = deepcopy(valid_identity)
    if mutation == "browser_shaped":
        identity = {"authority": "browser", "command_id": valid_identity["command_id"], "identity_digest": "self-digested"}
    elif mutation == "project":
        identity["project_id"] = "project-browser-other"
        _rehash_command_identity(identity)
    elif mutation == "template":
        identity["template_id"] = "ecommerce_template"
        _rehash_command_identity(identity)
    elif mutation == "issuer":
        identity["issuer"] = "browser-command-registry"
        _rehash_command_identity(identity)
    elif mutation == "schema":
        identity["schema_version"] = "doc270_browser_command_identity_v1"
        _rehash_command_identity(identity)
    elif mutation == "capability":
        identity["capability_id"] = "browser-capability"
        _rehash_command_identity(identity)
    elif mutation == "digest":
        identity["identity_digest"] = "0" * 64
    elif mutation == "binding":
        identity["command_plan_binding_digest"] = "wrong-plan-binding"
        _rehash_command_identity(identity)
    elif mutation == "missing":
        identity.pop("coalescing_nonce")
        _rehash_command_identity(identity)
    else:
        identity["browser_extra"] = True
        _rehash_command_identity(identity)
    _install_private_phase3_server_seams(monkeypatch, handlers, entry, command_identity=identity)

    created = handlers.post_project_job(
        project["project_id"], _general_payload(metadata={"server_command_identity": "browser-never-authoritative"})
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    _assert_private_receipt_invalid(record)
    assert handlers.get_job(created["job_id"])["metadata"].get("doc270_general_source_activation") == {"state": "receipt_invalid"}


def test_doc270_phase3_missing_server_command_identity_preserves_existing_general_creation(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    entry = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    _install_private_phase3_server_seams(monkeypatch, handlers, entry, command_identity=None)
    monkeypatch.setattr(handlers.project_service, "_doc270_general_command_identity_lookup", lambda **_kwargs: None, raising=False)

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert created["status"] == "planned"
    assert "doc270_general_source_activation_receipts" not in record.request.metadata
    assert "doc270_general_original_source_projection" not in record.request.metadata
    assert "doc270_general_source_activation" not in handlers.get_job(created["job_id"])["metadata"]


@pytest.mark.parametrize("mutation", ["schema", "issuer", "capability", "version", "template", "enabled", "extra"])
def test_doc270_phase3_malformed_activation_capability_preserves_no_gate_path(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    entry = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    capability = deepcopy(_TEST_ACTIVATION_CAPABILITY)
    if mutation == "schema":
        capability["schema_version"] = "browser-capability-v1"
    elif mutation == "issuer":
        capability["issuer"] = "browser-capability"
    elif mutation == "capability":
        capability["capability_id"] = "wrong-capability"
    elif mutation == "version":
        capability["capability_version"] = "wrong-version"
    elif mutation == "template":
        capability["template_id"] = "ecommerce_template"
    elif mutation == "enabled":
        capability["enabled"] = False
    else:
        capability["browser_extra"] = True
    _install_private_phase3_server_seams(monkeypatch, handlers, entry, capability=capability)

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert created["status"] == "planned"
    assert "doc270_general_source_activation_receipts" not in record.request.metadata
    assert "doc270_general_original_source_projection" not in record.request.metadata
    assert "doc270_general_source_activation" not in handlers.get_job(created["job_id"])["metadata"]


@pytest.mark.parametrize(
    "mutation",
    ["project", "snapshot", "asset", "sha", "cap", "output", "source_resolver", "evidence_digests", "profile_relation", "shadow_only"],
)
def test_doc270_phase3_mismatched_resolved_receipt_never_selects_or_forwards_originals(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    resolved = _registered_resolved_receipt(project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0])
    receipt = _receipt_payload(resolved)
    if mutation == "project":
        receipt["project_id"] = "project-other"
    elif mutation == "snapshot":
        receipt["source_library_snapshot_digest"] = "0" * 64
    elif mutation == "asset":
        receipt["matched_references"][0]["asset_id"] = asset_ids[2]
    elif mutation == "sha":
        receipt["matched_references"][0]["content_sha256"] = "e" * 64
    elif mutation == "cap":
        receipt["matched_references"].append(deepcopy(receipt["matched_references"][0]))
        receipt["evidence_profile_digests"].append("server-phase3-profile")
    elif mutation == "output":
        receipt["output_identity"] = "server-output-other"
    elif mutation == "source_resolver":
        receipt["source_resolver"] = {"authority": "unregistered", "version": "v0"}
    elif mutation == "evidence_digests":
        receipt["evidence_profile_digests"] = ["wrong-evidence-profile"]
    elif mutation == "profile_relation":
        receipt["matched_references"][0]["profile_digest"] = "different-profile"
    else:
        receipt["shadow_only"] = False
    _rehash_receipt(receipt)
    _rehash_registry_entry(resolved)
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    _assert_private_receipt_invalid(record)
    assert created["status"] == "planned"


@pytest.mark.parametrize("state", ["no_reference", "optional_uncertain", "insufficient_evidence", "invalid"])
def test_doc270_phase3_nonresolved_or_prompt_only_general_preserves_prompt_only_planned_path(tmp_path, monkeypatch, state: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    authority_object = _registered_resolved_receipt(project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0])
    receipt = _receipt_payload(authority_object)
    receipt["state"] = state
    if state == "no_reference":
        receipt["matched_references"] = []
        receipt["evidence_profile_digests"] = []
    _rehash_receipt(receipt)
    _rehash_registry_entry(authority_object)
    _install_private_phase3_server_seams(monkeypatch, handlers, authority_object)

    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = _activation_receipt(record)
    assert activation == {"state": "prompt_only"}
    assert record.request.uploaded_asset_ids == []
    assert "doc270_general_original_source_projection" not in record.request.metadata
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


def test_doc270_phase3_no_source_general_command_remains_prompt_only_without_gate(tmp_path) -> None:
    handlers, _project, _asset_ids, _snapshot = _general_project(tmp_path)
    no_source = handlers.post_projects(
        {"user_goal": "Create a prompt-only abstract campaign image.", "primary_template_id": "general_template"}
    )["project"]
    created = handlers.post_project_job(no_source["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert created["status"] == "planned"
    assert record.request.uploaded_asset_ids == []
    assert "doc270_general_source_activation_receipts" not in record.request.metadata
    assert "current_operation" not in created["metadata"]


def test_doc270_phase3_activation_is_new_command_only_and_public_projection_is_safe(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    resolved = _registered_resolved_receipt(project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0])
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = _activation_receipt(record)
    reloaded = handlers.get_job(created["job_id"])
    assert reloaded["job_id"] == created["job_id"]
    assert reloaded["metadata"].get("doc270_general_source_activation") == {"state": "activated_resolved"}
    public_text = str(reloaded)
    for private in [association_id, asset_ids[0], snapshot["snapshot_digest"], _receipt_payload(resolved)["receipt_digest"], "server-phase3-profile"]:
        assert private not in public_text
    assert activation["source_receipt_digest"] == _receipt_payload(resolved)["receipt_digest"]


@pytest.mark.parametrize("mutation", ["duplicate", "mixed_asset", "order", "raw_evidence"])
def test_doc270_phase3_corrupt_frozen_projection_fails_closed_and_stays_private(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    resolved = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    projection = _activation_projection(record)
    source = deepcopy(projection["sources"][0])
    if mutation == "duplicate":
        projection["sources"].append(source)
    elif mutation == "mixed_asset":
        projection["sources"][0]["asset_id"] = asset_ids[2]
    elif mutation == "order":
        record.request.uploaded_asset_ids = [asset_ids[2], asset_ids[0]]
    else:
        projection["registry_entry_digest"] = "private-registry-data-must-not-project"
    record.request.metadata["doc270_general_original_source_projection"] = projection
    handlers.service.job_store.save(record)

    public = handlers.get_job(created["job_id"])
    assert public["metadata"].get("doc270_general_source_activation") == {"state": "receipt_invalid"}
    assert "doc270_general_original_source_projection" not in public["metadata"]
    assert "private-registry-data-must-not-project" not in str(public["metadata"])


def test_doc270_phase3_gate_never_backfills_an_old_job_and_new_command_has_its_own_receipt(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    old = handlers.post_project_job(project["project_id"], _general_payload())
    old_record = handlers.service.get_job_record(old["job_id"])
    assert old_record is not None
    assert "doc270_general_source_activation_receipts" not in old_record.request.metadata

    association_id = _association_id(handlers, project["project_id"], asset_ids[2])
    resolved = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[2]
    )
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    assert "doc270_general_source_activation" not in handlers.get_job(old["job_id"])["metadata"]

    fresh = handlers.post_project_job(project["project_id"], _general_payload())
    fresh_record = handlers.service.get_job_record(fresh["job_id"])
    assert fresh_record is not None
    assert fresh["job_id"] != old["job_id"]
    assert _activation_receipt(fresh_record)["source_receipt_digest"] == _receipt_payload(resolved)["receipt_digest"]


def test_doc270_phase3_same_server_command_identity_replays_one_job_and_receipt_without_rematch(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    first_identity = _server_command_identity(project_id=project["project_id"])
    second_identity = _server_command_identity(
        project_id=project["project_id"],
        command_id="server-phase3-command-2",
        plan_binding_digest="server-phase3-command-binding-2",
        coalescing_nonce="server-phase3-coalescing-nonce-2",
    )
    first_entry = _registered_resolved_receipt(
        project_id=project["project_id"],
        snapshot=snapshot,
        association_id=association_id,
        asset_id=asset_ids[0],
        command_identity=first_identity,
    )
    second_entry = _registered_resolved_receipt(
        project_id=project["project_id"],
        snapshot=snapshot,
        association_id=_association_id(handlers, project["project_id"], asset_ids[1]),
        asset_id=asset_ids[1],
        command_identity=second_identity,
    )
    calls = {"receipt": 0}
    identities = iter(
        [
            first_identity,
            first_identity,
            second_identity,
        ]
    )
    entries = iter([first_entry, second_entry])

    def lookup(**_kwargs):
        calls["receipt"] += 1
        return deepcopy(next(entries))

    _install_private_phase3_server_seams(monkeypatch, handlers, first_entry)
    monkeypatch.setattr(handlers.project_service, "_doc270_general_command_identity_lookup", lambda **_kwargs: next(identities), raising=False)
    monkeypatch.setattr(handlers.project_service, "_doc270_general_phase2_receipt_registry_lookup", lookup, raising=False)
    first = handlers.post_project_job(
        project["project_id"], _general_payload(metadata={"server_command_identity": "browser-forged-a"})
    )
    second = handlers.post_project_job(
        project["project_id"], _general_payload(metadata={"server_command_identity": "browser-forged-b", "selected_original_asset_ids": asset_ids})
    )
    third = handlers.post_project_job(project["project_id"], _general_payload())
    first_record = handlers.service.get_job_record(first["job_id"])
    third_record = handlers.service.get_job_record(third["job_id"])
    assert first_record is not None
    assert third_record is not None
    assert second["job_id"] == first["job_id"]
    assert third["job_id"] != first["job_id"]
    assert len(handlers.project_service._require_project(project["project_id"]).job_ids) == 2  # noqa: SLF001
    assert calls["receipt"] == 2
    assert handlers.get_job(first["job_id"])["metadata"]["doc270_general_source_activation"] == {"state": "activated_resolved"}
    assert _activation_receipt(first_record)["source_receipt_digest"] == _receipt_payload(first_entry)["receipt_digest"]
    assert _activation_receipt(third_record)["source_receipt_digest"] == _receipt_payload(second_entry)["receipt_digest"]


def test_doc270_phase3_refresh_history_and_retry_shaped_generation_do_not_rematch_or_replace_frozen_originals(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    resolved = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    calls = {"receipt": 0}

    def lookup(**_kwargs):
        calls["receipt"] += 1
        return deepcopy(resolved)

    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    monkeypatch.setattr(handlers.project_service, "_doc270_general_phase2_receipt_registry_lookup", lookup, raising=False)
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    frozen = deepcopy(_activation_receipt(record))
    generated = {"calls": 0}

    def retry_shaped_generate(job_id: str, _payload: dict[str, Any]):
        generated["calls"] += 1
        assert job_id == created["job_id"]
        return handlers.service.get_job(job_id)

    monkeypatch.setattr(handlers.service, "generate_job", retry_shaped_generate)

    handlers.get_project(project["project_id"])
    handlers.get_job(created["job_id"])
    handlers.get_project(project["project_id"])
    handlers.post_project_job_generate(
        project["project_id"],
        created["job_id"],
        {"metadata": {"retry_attempt": 1, "server_command_identity": "browser-forged-retry"}},
    )

    reloaded = handlers.service.get_job_record(created["job_id"])
    assert reloaded is not None
    assert _activation_receipt(reloaded) == frozen
    assert calls["receipt"] == 1
    assert generated == {"calls": 1}


def test_doc270_phase3_continuation_selection_stays_separate_from_activated_original_channel(tmp_path, monkeypatch) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    source_job = handlers.post_project_job(project["project_id"], _general_payload())
    continuation = _save_history_output(handlers, job_id=source_job["job_id"], index=270)
    handlers.post_project_reference(
        project["project_id"],
        {
            "asset_ref_id": continuation.output_id,
            "source_type": "generated_selected",
            "created_from_job_id": source_job["job_id"],
            "created_from_output_id": continuation.output_id,
            "use_policy": "style",
        },
    )
    association_id = _association_id(handlers, project["project_id"], asset_ids[1])
    resolved = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[1]
    )
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    activation = _activation_receipt(record)
    projection = _activation_projection(record)
    assert activation["selected_original_asset_ids"] == [asset_ids[1]]
    assert continuation.output_id not in activation["selected_original_asset_ids"]
    assert continuation.output_id not in str(projection)
    assert record.request.uploaded_asset_ids == [asset_ids[1]]
    assert any(
        item.asset_ref_id == continuation.output_id
        and item.source_type == ProjectReferenceSourceType.GENERATED_SELECTED
        and item.use_policy == ProjectReferenceUsePolicy.STYLE
        for item in handlers.project_service._require_project(project["project_id"]).reference_assets  # noqa: SLF001
    )
    public = handlers.get_project(project["project_id"])["metadata"]
    assert continuation.output_id not in str(public["project_source_library"])
    assert continuation.output_id in str(public["project_outputs"])


@pytest.mark.parametrize("mutation", ["file_drift", "cross_project", "generated_candidate"])
def test_doc270_phase3_source_drift_or_nonoriginal_candidate_fails_to_prompt_only(tmp_path, monkeypatch, mutation: str) -> None:
    handlers, project, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, project["project_id"], asset_ids[0])
    resolved = _registered_resolved_receipt(
        project_id=project["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    receipt = _receipt_payload(resolved)
    if mutation == "file_drift":
        record = handlers.service.get_uploaded_asset(asset_ids[0])
        assert record is not None
        Path(str(record.file_path)).write_bytes(b"doc270-phase3-stale-source")
    elif mutation == "cross_project":
        other = handlers.post_projects({"user_goal": "Other project.", "primary_template_id": "general_template"})["project"]
        handlers.post_project_reference(
            other["project_id"],
            {"asset_ref_id": asset_ids[1], "source_type": "uploaded", "use_policy": "general"},
        )
        other_reference = _association_id(handlers, other["project_id"], asset_ids[1])
        receipt["matched_references"][0]["reference_id"] = other_reference
    else:
        durable = handlers.project_service._require_project(project["project_id"])  # noqa: SLF001
        durable.reference_assets[0] = durable.reference_assets[0].model_copy(
            update={"source_type": ProjectReferenceSourceType.GENERATED_SELECTED}
        )
        handlers.project_service.project_store.save_project(durable)
    _rehash_receipt(receipt)
    _rehash_registry_entry(resolved)
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    created = handlers.post_project_job(project["project_id"], _general_payload())
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    _assert_private_receipt_invalid(record)
    assert created["status"] == "planned"
    assert "current_operation" not in created["metadata"]


def test_doc270_phase3_ecommerce_and_photography_do_not_consume_general_activation_gate(tmp_path, monkeypatch) -> None:
    from alchemy_creative_agent_3_0.tests.test_v3_doc264_ecommerce_legacy_reference_recovery import _project

    handlers, general, asset_ids, snapshot = _general_project(tmp_path)
    association_id = _association_id(handlers, general["project_id"], asset_ids[0])
    resolved = _registered_resolved_receipt(
        project_id=general["project_id"], snapshot=snapshot, association_id=association_id, asset_id=asset_ids[0]
    )
    _install_private_phase3_server_seams(monkeypatch, handlers, resolved)
    ecommerce = _project(handlers)
    created = handlers.post_project_job(
        ecommerce["project_id"],
        {"template_id": "ecommerce_template", "user_input": "Create one product presentation."},
    )
    record = handlers.service.get_job_record(created["job_id"])
    assert record is not None
    assert "doc270_general_source_activation_receipts" not in record.request.metadata
    photography = handlers.project_service.template_registry.get_manifest("photographer_template")
    assert photography is not None
    assert photography.template_id == "photographer_template"
    assert photography.status.value != "active"
